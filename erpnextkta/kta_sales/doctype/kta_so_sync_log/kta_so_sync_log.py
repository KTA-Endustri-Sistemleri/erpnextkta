# Copyright (c) 2025, Framras AS and contributors
# For license information, please see license.txt

# import frappe
import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, today
from erpnext.controllers.accounts_controller import update_child_qty_rate
from erpnext.utilities.transaction_base import UOMMustBeIntegerError


from erpnextkta.kta_sales.doctype.kta_sales_order_update.kta_sales_order_update import (
    adjust_sales_order_update_with_shipments,
    get_customer_and_item,
    get_sales_order_update_doc,
)
class KTASOSyncLog(Document):
	pass


@frappe.whitelist()
def sync_sales_orders_from_sales_order_update(
    sales_order_update_name=None, sales_order_update_reference=None
):
    """
    Sales Order Update'den senkronizasyon başlat.
    """
    reference_name = sales_order_update_reference or sales_order_update_name
    if not reference_name:
        frappe.throw(_("Sales Order Update seçilmedi."))
    return _sync_sales_orders_from_sales_order_update(reference_name)


@frappe.whitelist()
def sync_sales_orders_from_comparison(comparison_name):
    """
    Karşılaştırmadan Sales Order'ları senkronize et.
    """
    comparison = frappe.get_doc("KTA Sales Order Update Comparison", comparison_name)
    return _sync_sales_orders_from_sales_order_update(
        comparison.current_sales_order_update, comparison=comparison
    )


def _sync_sales_orders_from_sales_order_update(sales_order_update_name, comparison=None):
    """
    Seçilen Sales Order Update için sevkiyat düşülmüş değişiklikleri üretip ERP'ye uygular.
    """
    sales_order_update_doc = get_sales_order_update_doc(sales_order_update_name)
    sync_changes = [
        frappe._dict(change)
        for change in build_sales_order_sync_changes(sales_order_update_doc.name)
    ]

    sync_log = frappe.new_doc("KTA SO Sync Log")
    sync_log.sales_order_update = sales_order_update_doc.name
    if comparison:
        sync_log.comparison = comparison.name
    sync_log.sync_date = frappe.utils.now()
    sync_log.status = "In Progress"
    sync_log.total_changes = len(sync_changes)

    created = updated = closed = errors = 0

    try:
        if not sync_changes:
            sync_log.status = "Completed"
            sync_log.comment = "No changes detected for this Sales Order Update."
            sync_log.save()
            sales_order_update_doc.last_sync_log = sync_log.name
            sales_order_update_doc.save()
            return {
                "sync_log": sync_log.name,
                "created": 0,
                "updated": 0,
                "closed": 0,
                "errors": 0,
                "info": "No changes detected",
            }

        changes_by_so = group_changes_by_sales_order(sync_changes)

        for so_identifier, so_changes in changes_by_so.items():
            try:
                result = process_sales_order_batch(so_identifier, so_changes)

                for detail in result["details"]:
                    sync_log.append("sync_details", detail)

                created += result.get("created", 0)
                updated += result.get("updated", 0)
                closed += result.get("closed", 0)
                errors += result.get("errors", 0)

            except Exception:
                errors += len(so_changes)
                frappe.log_error("SO Sync Batch", frappe.get_traceback())

        sync_log.created_so = created
        sync_log.updated_so = updated
        sync_log.closed_so = closed
        sync_log.errors = errors
        sync_log.status = "Completed" if errors == 0 else "Failed"

        if comparison:
            comparison.status = "Synced"
            comparison.save()

        sales_order_update_doc.last_sync_log = sync_log.name
        sales_order_update_doc.save()

    except Exception:
        sync_log.status = "Failed"
        sync_log.error_log = frappe.get_traceback()
        frappe.log_error("SO Sync Critical Error", frappe.get_traceback())

    sync_log.save()
    frappe.db.commit()

    result = {
        "sync_log": sync_log.name,
        "created": created,
        "updated": updated,
        "closed": closed,
        "errors": errors,
    }

    return result


def build_sales_order_sync_changes(sales_order_update_name):
    """
    Sales Order Update satırlarını grupla ve sadece NET değişiklikleri tespit et.
    """
    rows = frappe.db.sql(
        """
        SELECT
            order_no,
            part_no_customer,
            delivery_date,
            delivery_quantity,
            plant_no_customer
        FROM `tabKTA Sales Order Update Entry`
        WHERE parent = %s
        ORDER BY order_no, part_no_customer, plant_no_customer, delivery_date
        """,
        (sales_order_update_name,),
        as_dict=True,
    )

    if not rows:
        return []

    adjusted_rows = adjust_sales_order_update_with_shipments(rows)
    far_future = getdate("2199-12-31")

    plan_rows_by_key = defaultdict(list)
    customers = set()

    for row in adjusted_rows:
        if not row.order_no:
            continue

        customer, item_code = get_customer_and_item(
            row.plant_no_customer,
            row.part_no_customer,
        )

        if not (customer and item_code):
            continue

        plan_entry = frappe._dict(
            {
                "customer": customer,
                "order_no": row.order_no,
                "order_item": None,
                "part_no_customer": row.part_no_customer,
                "plant_no_customer": row.plant_no_customer,
                "item": item_code,
                "delivery_date": row.delivery_date,
                "planned_qty": flt(row.delivery_quantity or 0),
                "new_efz": None,
            }
        )

        key = (customer, row.order_no, item_code)
        plan_rows_by_key[key].append(plan_entry)
        customers.add(customer)

    for plan_list in plan_rows_by_key.values():
        plan_list.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )

    changes = []
    open_sales_orders = fetch_open_sales_orders_with_item_dates(customers)

    erp_rows_by_key = defaultdict(list)

    for so in open_sales_orders:
        if not so.po_no:
            continue

        pending_qty = flt(getattr(so, "pending_qty", 0))
        if pending_qty is None or pending_qty == 0:
            pending_qty = flt(so.qty) - flt(so.delivered_qty)
        pending_qty = max(pending_qty, 0)
        if pending_qty <= 0:
            continue

        key = (so.customer, so.po_no, so.item_code)
        erp_rows_by_key[key].append(
            frappe._dict(
                {
                    "sales_order": so.sales_order,
                    "sales_order_item": so.sales_order_item,
                    "delivery_date": so.item_delivery_date,
                    "qty": flt(so.qty),
                    "delivered_qty": flt(so.delivered_qty),
                    "pending_qty": pending_qty,
                }
            )
        )

    for erp_list in erp_rows_by_key.values():
        erp_list.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )

    all_keys = set(plan_rows_by_key.keys()) | set(erp_rows_by_key.keys())

    for key in all_keys:
        plan_rows = list(plan_rows_by_key.get(key, []))
        erp_rows = list(erp_rows_by_key.get(key, []))

        customer, order_no, item_code = key

        sig_to_plan_idx = defaultdict(list)
        for i, r in enumerate(plan_rows):
            sig = (str(r.delivery_date), int(r.planned_qty or 0))
            sig_to_plan_idx[sig].append(i)

        matched_plan_idx = set()
        matched_erp_idx = set()

        for j, erp in enumerate(erp_rows):
            open_qty = max(flt(getattr(erp, "pending_qty", 0)), 0)
            sig = (str(erp.delivery_date), int(open_qty))

            if sig_to_plan_idx.get(sig):
                i = sig_to_plan_idx[sig].pop()
                matched_plan_idx.add(i)
                matched_erp_idx.add(j)

        unmatched_plan = [r for i, r in enumerate(plan_rows) if i not in matched_plan_idx]
        unmatched_erp = [r for j, r in enumerate(erp_rows) if j not in matched_erp_idx]

        if not unmatched_plan and not unmatched_erp:
            continue

        plan_by_date = defaultdict(list)
        erp_by_date = defaultdict(list)

        for r in unmatched_plan:
            plan_by_date[str(r.delivery_date)].append(r)

        for r in unmatched_erp:
            erp_by_date[str(r.delivery_date)].append(r)

        common_dates = set(plan_by_date.keys()) & set(erp_by_date.keys())

        dates_to_drop_from_plan = set()
        dates_to_drop_from_erp = set()

        for date_str in common_dates:
            plan_list = plan_by_date[date_str]
            erp_list = erp_by_date[date_str]

            plan_total = sum(int(r.planned_qty or 0) for r in plan_list)
            erp_total = sum(int(flt(getattr(r, "pending_qty", 0))) for r in erp_list)

            sample_plan = plan_list[0] if plan_list else None
            sample_erp = erp_list[0] if erp_list else None

            if plan_total == erp_total:
                dates_to_drop_from_plan.add(date_str)
                dates_to_drop_from_erp.add(date_str)
            else:
                qty_diff = plan_total - erp_total

                change_type = "Miktar Artışı" if qty_diff > 0 else "Miktar Azalışı"

                matched_so = sample_erp.sales_order if sample_erp else None
                matched_so_item = sample_erp.sales_order_item if sample_erp else None

                changes.append(
                    {
                        "order_no": order_no,
                        "order_item": sample_plan.order_item
                        if sample_plan
                        else (sample_erp.sales_order_item if sample_erp else None),
                        "part_no_customer": sample_plan.part_no_customer if sample_plan else None,
                        "plant_no_customer": sample_plan.plant_no_customer if sample_plan else None,
                        "customer": customer,
                        "item": item_code,
                        "change_type": change_type,
                        "old_delivery_date": date_str,
                        "new_delivery_date": date_str,
                        "old_delivery_quantity": erp_total,
                        "new_delivery_quantity": plan_total,
                        "difference": qty_diff,
                        "old_efz": sample_erp.sales_order if sample_erp else None,
                        "new_efz": sample_plan.new_efz if sample_plan else None,
                        "action_required": 1,
                        "action_status": "Beklemede",
                        "matched_sales_order": matched_so,
                        "matched_sales_order_item": matched_so_item,
                    }
                )

                dates_to_drop_from_plan.add(date_str)
                dates_to_drop_from_erp.add(date_str)

        if dates_to_drop_from_plan:
            unmatched_plan = [
                r for r in unmatched_plan if str(r.delivery_date) not in dates_to_drop_from_plan
            ]
        if dates_to_drop_from_erp:
            unmatched_erp = [
                r for r in unmatched_erp if str(r.delivery_date) not in dates_to_drop_from_erp
            ]

        if not unmatched_plan and not unmatched_erp:
            continue

        unmatched_plan.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )
        unmatched_erp.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )

        plan_with_ref = []
        plan_without_ref = []

        for plan in unmatched_plan:
            if plan.order_item:
                plan_with_ref.append(plan)
            else:
                plan_without_ref.append(plan)

        for plan in plan_with_ref:
            matched_erp = None
            matched_idx = None

            for idx, erp in enumerate(unmatched_erp):
                if erp.sales_order_item == plan.order_item:
                    matched_erp = erp
                    matched_idx = idx
                    break

            if matched_erp:
                unmatched_erp.pop(matched_idx)

                open_qty = max(flt(getattr(matched_erp, "pending_qty", 0)), 0)
                new_qty = flt(plan.planned_qty)
                old_date = matched_erp.delivery_date
                new_date = plan.delivery_date or old_date

                change_type = determine_change_type_for_sync(open_qty, new_qty, old_date, new_date)

                if change_type:
                    changes.append(
                        {
                            "order_no": order_no,
                            "order_item": plan.order_item,
                            "part_no_customer": plan.part_no_customer,
                            "plant_no_customer": plan.plant_no_customer,
                            "customer": customer,
                            "item": item_code,
                            "change_type": change_type,
                            "old_delivery_date": old_date,
                            "new_delivery_date": new_date,
                            "old_delivery_quantity": open_qty,
                            "new_delivery_quantity": new_qty,
                            "difference": new_qty - open_qty,
                            "old_efz": None,
                            "new_efz": plan.new_efz,
                            "action_required": 1,
                            "action_status": "Beklemede",
                            "matched_sales_order": matched_erp.sales_order,
                            "matched_sales_order_item": matched_erp.sales_order_item,
                        }
                    )
            else:
                plan_without_ref.append(plan)

        unmatched_plan = plan_without_ref

        i = j = 0
        len_plan = len(unmatched_plan)
        len_erp = len(unmatched_erp)

        while i < len_plan and j < len_erp:
            plan = unmatched_plan[i]
            erp = unmatched_erp[j]

            open_qty = max(flt(getattr(erp, "pending_qty", 0)), 0)
            new_qty = flt(plan.planned_qty)
            old_date = erp.delivery_date
            new_date = plan.delivery_date or old_date

            change_type = determine_change_type_for_sync(open_qty, new_qty, old_date, new_date)

            if change_type:
                changes.append(
                    {
                        "order_no": order_no,
                        "order_item": plan.order_item,
                        "part_no_customer": plan.part_no_customer,
                        "plant_no_customer": plan.plant_no_customer,
                        "customer": customer,
                        "item": item_code,
                        "change_type": change_type,
                        "old_delivery_date": old_date,
                        "new_delivery_date": new_date,
                        "old_delivery_quantity": open_qty,
                        "new_delivery_quantity": new_qty,
                        "difference": new_qty - open_qty,
                        "old_efz": None,
                        "new_efz": plan.new_efz,
                        "action_required": 1,
                        "action_status": "Beklemede",
                        "matched_sales_order": erp.sales_order,
                        "matched_sales_order_item": erp.sales_order_item,
                    }
                )

            i += 1
            j += 1

        while i < len_plan:
            plan = unmatched_plan[i]

            if flt(plan.planned_qty) > 0:
                changes.append(
                    {
                        "order_no": order_no,
                        "order_item": plan.order_item,
                        "part_no_customer": plan.part_no_customer,
                        "plant_no_customer": plan.plant_no_customer,
                        "customer": customer,
                        "item": item_code,
                        "change_type": "Yeni Satır",
                        "old_delivery_date": None,
                        "new_delivery_date": plan.delivery_date,
                        "old_delivery_quantity": 0,
                        "new_delivery_quantity": plan.planned_qty,
                        "difference": plan.planned_qty,
                        "old_efz": None,
                        "new_efz": plan.new_efz,
                        "action_required": 1,
                        "action_status": "Beklemede",
                        "matched_sales_order": None,
                        "matched_sales_order_item": None,
                    }
                )

            i += 1

        while j < len_erp:
            erp = unmatched_erp[j]
            open_qty = max(flt(getattr(erp, "pending_qty", 0)), 0)

            if open_qty > 0:
                changes.append(
                    {
                        "order_no": order_no,
                        "order_item": None,
                        "part_no_customer": None,
                        "plant_no_customer": None,
                        "customer": customer,
                        "item": item_code,
                        "change_type": "Silinen Satır",
                        "old_delivery_date": erp.delivery_date,
                        "new_delivery_date": erp.delivery_date,
                        "old_delivery_quantity": open_qty,
                        "new_delivery_quantity": 0,
                        "difference": -open_qty,
                        "old_efz": None,
                        "new_efz": None,
                        "action_required": 1,
                        "action_status": "Beklemede",
                        "matched_sales_order": erp.sales_order,
                        "matched_sales_order_item": erp.sales_order_item,
                    }
                )

            j += 1

    return changes


def fetch_open_sales_orders_with_item_dates(customers):
    """
    Sales Order Item seviyesindeki delivery_date'i getir.
    """
    if not customers:
        return []

    placeholders = ", ".join(["%s"] * len(customers))
    query = f"""
        SELECT
            so.name AS sales_order,
            soi.name AS sales_order_item,
            so.customer,
            so.po_no,
            soi.item_code,
            soi.qty,
            soi.delivered_qty,
            (soi.qty - IFNULL(soi.delivered_qty, 0)) AS pending_qty,
            soi.delivery_date AS item_delivery_date
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON so.name = soi.parent
        WHERE so.docstatus = 1
          AND so.status IN ('To Deliver', 'To Deliver and Bill')
          AND so.customer IN ({placeholders})
        ORDER BY so.customer, so.po_no, soi.item_code, soi.delivery_date
    """

    return frappe.db.sql(query, tuple(customers), as_dict=True)


def determine_change_type_for_sync(open_qty, new_qty, old_date, new_date):
    """
    Sales Order Update planı ile ERP'deki açık miktarı karşılaştırarak change_type belirle.
    """
    open_qty = flt(open_qty)
    new_qty = flt(new_qty)

    if new_qty <= 0 and open_qty <= 0:
        return None

    if new_qty <= 0 and open_qty > 0:
        return "Silinen Satır"

    date_changed = False
    if new_date and old_date:
        date_changed = getdate(new_date) != getdate(old_date)
    elif new_date and not old_date:
        date_changed = True

    qty_changed = abs(new_qty - open_qty) > 0.0001

    if not qty_changed and not date_changed:
        return None

    if qty_changed and date_changed:
        return "Tarih ve Miktar Değişikliği"

    if qty_changed:
        return "Miktar Artışı" if new_qty > open_qty else "Miktar Azalışı"

    if date_changed:
        return "Tarih Değişikliği"

    return None


def group_changes_by_sales_order(changes):
    """
    Değişiklikleri Sales Order bazında grupla.
    """
    grouped = defaultdict(list)
    so_cache = {}

    for change in changes:
        customer = change.customer
        order_no = change.order_no
        item_code = change.item

        so_name = getattr(change, "matched_sales_order", None)

        if not so_name and customer and order_no and item_code and change.change_type != "Yeni Satır":
            key = (customer, order_no, item_code)
            available = so_cache.get(key)
            if available is None:
                rows = frappe.db.sql(
                    """
                    SELECT DISTINCT so.name
                    FROM `tabSales Order` so
                    INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
                    WHERE so.customer = %s
                        AND so.po_no = %s
                        AND soi.item_code = %s
                        AND so.docstatus = 1
                        AND so.status IN ('To Deliver', 'To Deliver and Bill')
                    ORDER BY soi.delivery_date, so.transaction_date, so.name
                """,
                    (customer, order_no, item_code),
                    as_dict=True,
                )
                available = [row.name for row in rows]
                so_cache[key] = available

            if available:
                so_name = available.pop(0)

        if so_name:
            key = (customer, order_no, so_name)
        else:
            key = (customer, order_no or "-", "NEW")

        grouped[key].append(change)

    return grouped


def process_sales_order_batch(so_identifier, changes):
    """
    Detayları doğru şekilde kaydet.
    """
    customer, order_no, so_name = so_identifier
    details = []
    created = updated = closed = errors = 0

    if so_name == "NEW":
        for change in changes:
            details.append(
                {
                    "action": "Error",
                    "sales_order": None,
                    "customer": customer,
                    "item": change.item,
                    "order_no": change.order_no,
                    "order_item": change.order_item,
                    "old_qty": change.old_delivery_quantity,
                    "new_qty": change.new_delivery_quantity,
                    "old_date": change.old_delivery_date,
                    "new_date": change.new_delivery_date,
                    "change_type": change.change_type,
                    "error_message": _("PO {0} için ERPNext'te Sales Order bulunamadı. Manuel oluşturulmalı.").format(
                        order_no
                    ),
                }
            )

        errors = len(changes)

    else:
        result = update_existing_sales_order_batch(so_name, changes)
        details.extend(result["details"])
        updated = result.get("updated", 0)
        closed = result.get("closed", 0)
        errors = result.get("errors", 0)

    return {
        "details": details,
        "created": created,
        "updated": updated,
        "closed": closed,
        "errors": errors,
    }


def update_existing_sales_order_batch(so_name, changes):
    """
    Sales Order Item seviyesinde delivery_date güncelle.
    """
    details = []
    updated = closed = errors = 0
    earliest_new_order_date = None

    try:
        so = frappe.get_doc("Sales Order", so_name)

        if not so.items:
            frappe.log_error(f"Sales Order {so_name} has no items", "SO Update Error")
            return {
                "details": [
                    {
                        "action": "Error",
                        "sales_order": so_name,
                        "customer": so.customer if getattr(so, "customer", None) else None,
                        "error_message": _("Sales Order'da hiç item yok."),
                    }
                ],
                "updated": 0,
                "closed": 0,
                "errors": 1,
            }

        for change in changes:
            target_item = None
            for item in so.items:
                if item.item_code == getattr(change, "item", None):
                    target_item = item
                    break

            if not target_item:
                details.append(
                    {
                        "action": "Error",
                        "sales_order": so_name,
                        "customer": so.customer,
                        "item": getattr(change, "item", None),
                        "order_no": so.po_no,
                        "change_type": getattr(change, "change_type", None),
                        "error_message": _("Sales Order içinde eşleşen item bulunamadı."),
                    }
                )
                errors += 1
                continue

            change_type = getattr(change, "change_type", None)
            item_dict = target_item.as_dict()
            new_date = target_item.delivery_date
            action = None
            new_pending_qty = flt(getattr(change, "new_delivery_quantity", 0) or 0)

            if change_type != "Silinen Satır" and new_pending_qty <= 0:
                change_type = "Silinen Satır"
                if hasattr(change, "change_type"):
                    change.change_type = "Silinen Satır"
                change.new_delivery_quantity = 0

            detail_entry = None
            needs_update = False

            if change_type == "Silinen Satır":
                delivered_qty = flt(target_item.delivered_qty)
                billed_amt = flt(getattr(target_item, "billed_amt", 0))
                rate_for_billing = flt(target_item.rate) or flt(getattr(target_item, "base_rate", 0))
                billed_qty = flt(billed_amt / rate_for_billing) if rate_for_billing else 0
                protected_qty = max(delivered_qty, billed_qty)

                if protected_qty == 0 and len(so.items) == 1:
                    so.cancel()
                    frappe.delete_doc("Sales Order", so_name, force=1, ignore_permissions=True)

                    details.append(
                        {
                            "action": "Closed",
                            "sales_order": so_name,
                            "customer": so.customer,
                            "item": target_item.item_code,
                            "order_no": so.po_no,
                            "old_qty": target_item.qty,
                            "new_qty": 0,
                            "old_date": target_item.delivery_date,
                            "new_date": target_item.delivery_date,
                            "change_type": _("Silinen Satır (SO cancelled & deleted - no deliveries made)"),
                        }
                    )

                    return {
                        "details": details,
                        "updated": updated,
                        "closed": closed + 1,
                        "errors": errors,
                    }

                reason_bits = []
                if delivered_qty > 0:
                    reason_bits.append(_("Teslim edilen qty"))

                if billed_qty > delivered_qty:
                    reason_bits.append(_("Faturalandırılan qty"))

                if protected_qty > 0:
                    new_total_qty = protected_qty
                else:
                    new_total_qty = 0
                    reason_bits = [_("Teslimat yok, qty sıfırlandı")]

                detail_change_type = "Silinen Satır (" + " ve ".join(reason_bits) + ")"

                item_dict["qty"] = new_total_qty
                item_dict["delivery_date"] = target_item.delivery_date
                action = "Closed"
                needs_update = True

                detail_entry = {
                    "action": "Closed",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "new_qty": new_total_qty,
                    "old_date": target_item.delivery_date,
                    "new_date": target_item.delivery_date,
                    "change_type": detail_change_type,
                }

            elif change_type in [
                "Miktar Artışı",
                "Miktar Azalışı",
                "Tarih Değişikliği",
                "Tarih ve Miktar Değişikliği",
            ]:
                desired_pending_qty = max(flt(getattr(change, "new_delivery_quantity", 0) or 0), 0)
                new_total_qty = flt(target_item.delivered_qty) + desired_pending_qty
                item_dict["qty"] = new_total_qty

                new_date = getattr(change, "new_delivery_date", None) or target_item.delivery_date
                item_dict["delivery_date"] = new_date
                if new_date:
                    if earliest_new_order_date is None or getdate(new_date) < getdate(earliest_new_order_date):
                        earliest_new_order_date = new_date
                action = "Updated"
                needs_update = True

                detail_entry = {
                    "action": "Updated",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "new_qty": new_total_qty,
                    "old_date": target_item.delivery_date,
                    "new_date": new_date,
                    "change_type": change_type,
                }

            elif change_type == "Yeni Satır":
                details.append(
                    {
                        "action": "Error",
                        "sales_order": so_name,
                        "customer": so.customer,
                        "item": target_item.item_code,
                        "order_no": so.po_no,
                        "old_qty": target_item.qty,
                        "new_qty": getattr(change, "new_delivery_quantity", None),
                        "old_date": target_item.delivery_date,
                        "new_date": getattr(change, "new_delivery_date", None),
                        "change_type": _("Yeni Satır (ERP'ye eklenmedi)"),
                        "error_message": _(
                            "Kural: Her Sales Order tek satır. Yeni satır ERP'de manuel açılmalı."
                        ),
                    }
                )
                errors += 1
                continue

            else:
                details.append(
                    {
                        "action": "Error",
                        "sales_order": so_name,
                        "customer": so.customer,
                        "item": target_item.item_code,
                        "order_no": so.po_no,
                        "old_qty": target_item.qty,
                        "old_date": target_item.delivery_date,
                        "change_type": change_type,
                        "error_message": f"Bilinmeyen change_type: {change_type}",
                    }
                )
                errors += 1
                continue

            if not needs_update:
                continue

            delivery_date_value = item_dict.get("delivery_date") or target_item.delivery_date
            delivery_date_str = str(getdate(delivery_date_value)) if delivery_date_value else None

            trans_items = [
                {
                    "docname": target_item.name,
                    "item_code": target_item.item_code,
                    "qty": item_dict["qty"],
                    "rate": target_item.rate,
                    "uom": target_item.uom,
                    "conversion_factor": target_item.conversion_factor,
                    "delivery_date": delivery_date_str,
                }
            ]

            update_child_qty_rate(
                parent_doctype="Sales Order",
                trans_items=json.dumps(trans_items),
                parent_doctype_name=so.name,
                child_docname="items",
            )

            if action == "Closed":
                closed += 1
            elif action == "Updated":
                updated += 1

            so.reload()

            if detail_entry:
                details.append(detail_entry)

        if so.docstatus == 1:
            has_delivery_or_billing = any(
                flt(it.delivered_qty) > 0 or flt(getattr(it, "billed_amt", 0)) > 0 for it in so.items
            )
            all_zero_qty = all(flt(it.qty) <= 0 for it in so.items)

            if all_zero_qty and not has_delivery_or_billing:
                so.cancel()
                frappe.delete_doc("Sales Order", so_name, force=1, ignore_permissions=True)

                details.append(
                    {
                        "action": "Closed",
                        "sales_order": so_name,
                        "customer": so.customer,
                        "order_no": so.po_no,
                        "change_type": _("Silinen Satır (SO cancelled & deleted - all items removed)"),
                    }
                )

                return {
                    "details": details,
                    "updated": updated,
                    "closed": closed + 1,
                    "errors": errors,
                }

        if earliest_new_order_date and getdate(earliest_new_order_date) < getdate(so.transaction_date):
            so.db_set("transaction_date", earliest_new_order_date, update_modified=False)

        return {
            "details": details,
            "updated": updated,
            "closed": closed,
            "errors": errors,
        }

    except UOMMustBeIntegerError:
        # UOM hatasını saklama, kullanıcı aynen görsün
        raise

    except Exception:
        # title kısa, detay traceback
        frappe.log_error("SO Update", frappe.get_traceback())

        for change in changes:
            details.append(
                {
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": getattr(so, "customer", None) if "so" in locals() else getattr(change, "customer", None),
                    "item": getattr(change, "item", None),
                    "order_no": getattr(change, "order_no", None),
                    "order_item": getattr(change, "order_item", None),
                    "old_qty": getattr(change, "old_delivery_quantity", None),
                    "new_qty": getattr(change, "new_delivery_quantity", None),
                    "old_date": getattr(change, "old_delivery_date", None),
                    "new_date": getattr(change, "new_delivery_date", None),
                    "change_type": getattr(change, "change_type", None),
                    "error_message": _("İşlem hatası, detaylar için Error Log kaydına bakınız."),
                }
            )

        return {
            "details": details,
            "updated": 0,
            "closed": 0,
            "errors": len(changes),
        }


def update_so_item_qty_rate(so_name, item_name, new_qty, rate):
    """
    ERPNext API fonksiyonunu çağırarak SO Item güncelle.
    """
    from erpnext.controllers.accounts_controller import update_child_qty_rate as _update

    try:
        _update(
            parent_doctype="Sales Order",
            trans_items=[
                {
                    "docname": item_name,
                    "qty": new_qty,
                    "rate": rate,
                }
            ],
            parent_doctype_name=so_name,
        )

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(
            f"update_child_qty_rate failed for SO {so_name}, Item {item_name}: {str(e)}",
            "SO Item Update Error",
        )
        raise


def get_item_rate(item_code, customer):
    """
    Item için müşteriye özel fiyat al.
    """
    rate = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "customer": customer,
            "selling": 1,
        },
        "price_list_rate",
    )

    if not rate:
        default_price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")

        if default_price_list:
            rate = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": item_code,
                    "price_list": default_price_list,
                    "selling": 1,
                },
                "price_list_rate",
            )

    if not rate:
        rate = frappe.db.get_value("Item", item_code, "standard_rate")

    return flt(rate, 2) or 0
