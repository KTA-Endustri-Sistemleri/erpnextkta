from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from erpnextkta.kta_sales.doctype.kta_sales_order_update.kta_sales_order_update import (
    adjust_sales_order_update_with_shipments,
    get_customer_and_item,
)


class KTASalesOrderUpdateComparison(Document):
    pass


DOCTYPE_KTA_SALES_ORDER_UPDATE = "KTA Sales Order Update"


@frappe.whitelist()
def compare_sales_order_update_documents(current_sales_order_update_name):
    """
    Verilen KTA Sales Order Update dokümanını, creation sırasına göre ondan önce gelen kayıtla karşılaştır.
    """
    resolved_name = current_sales_order_update_name
    current = frappe.get_doc(DOCTYPE_KTA_SALES_ORDER_UPDATE, resolved_name)

    all_heads = frappe.get_all(
        DOCTYPE_KTA_SALES_ORDER_UPDATE,
        fields=["name", "creation"],
        order_by="creation asc",
    )

    current_index = None
    for idx, row in enumerate(all_heads):
        if row.name == current.name:
            current_index = idx
            break

    if current_index is None:
        frappe.throw(_("Current Sales Order Update kaydı bulunamadı: {0}").format(current.name))

    if current_index == 0:
        frappe.msgprint(_("Karşılaştırma için önceki Sales Order Update kaydı bulunamadı (bu ilk kayıt)."))
        return

    previous_sales_order_update_name = all_heads[current_index - 1].name

    comparison_doc = frappe.new_doc("KTA Sales Order Update Comparison")
    comparison_doc.comparison_date = frappe.utils.now()
    comparison_doc.previous_sales_order_update = previous_sales_order_update_name
    comparison_doc.current_sales_order_update = current_sales_order_update_name
    comparison_doc.status = "Draft"

    previous_data = get_sales_order_update_data(previous_sales_order_update_name, apply_shipments=False)
    current_data = get_sales_order_update_data(resolved_name, apply_shipments=False)

    changes = detect_changes(previous_data, current_data)

    for change in changes:
        comparison_doc.append("changes", change)

    comparison_doc.save()
    frappe.db.commit()

    return comparison_doc.name


def get_sales_order_update_data(sales_order_update_name, apply_shipments=False):
    """Sales Order Update verilerini unique key ile dict olarak getir."""
    rows = frappe.db.sql(
        """
        SELECT
            order_no,
            NULL AS order_item,
            part_no_customer,
            delivery_date,
            delivery_quantity,
            NULL AS efz,
            plant_no_customer
        FROM `tabKTA Sales Order Update Entry`
        WHERE parent = %s AND parenttype = %s
        ORDER BY order_no, part_no_customer, plant_no_customer, delivery_date
    """,
        (sales_order_update_name, DOCTYPE_KTA_SALES_ORDER_UPDATE),
        as_dict=True,
    )

    if apply_shipments:
        rows = adjust_sales_order_update_with_shipments(rows)

    data_dict = defaultdict(list)
    for row in rows:
        key = f"{row.order_no}_{row.part_no_customer}_{row.plant_no_customer}"
        data_dict[key].append(row)

    for key in data_dict:
        data_dict[key].sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
        )

    return data_dict


def detect_changes(previous_data, current_data):
    """
    İki Sales Order Update veri seti arasındaki değişiklikleri tespit et.
    """
    changes = []
    all_keys = set(previous_data.keys()) | set(current_data.keys())

    for key in all_keys:
        prev_rows = previous_data.get(key, [])
        curr_rows = current_data.get(key, [])

        sig_to_prev_idx = defaultdict(list)
        for i, r in enumerate(prev_rows):
            sig = (str(r.delivery_date), int(r.delivery_quantity or 0))
            sig_to_prev_idx[sig].append(i)

        matched_prev_idx = set()
        matched_curr_idx = set()

        for j, curr in enumerate(curr_rows):
            sig = (str(curr.delivery_date), int(curr.delivery_quantity or 0))
            if sig_to_prev_idx.get(sig):
                i = sig_to_prev_idx[sig].pop()
                matched_prev_idx.add(i)
                matched_curr_idx.add(j)

        unmatched_prev = [r for i, r in enumerate(prev_rows) if i not in matched_prev_idx]
        unmatched_curr = [r for j, r in enumerate(curr_rows) if j not in matched_curr_idx]

        if not unmatched_prev and not unmatched_curr:
            continue

        prev_by_date = defaultdict(list)
        curr_by_date = defaultdict(list)

        for r in unmatched_prev:
            prev_by_date[str(r.delivery_date)].append(r)

        for r in unmatched_curr:
            curr_by_date[str(r.delivery_date)].append(r)

        common_dates = set(prev_by_date.keys()) & set(curr_by_date.keys())

        dates_to_drop_from_prev = set()
        dates_to_drop_from_curr = set()

        for date_str in common_dates:
            prev_list = prev_by_date[date_str]
            curr_list = curr_by_date[date_str]

            prev_total = sum(int(r.delivery_quantity or 0) for r in prev_list)
            curr_total = sum(int(r.delivery_quantity or 0) for r in curr_list)

            sample = curr_list[0] if curr_list else prev_list[0]

            if prev_total == curr_total:
                dates_to_drop_from_prev.add(date_str)
                dates_to_drop_from_curr.add(date_str)
            else:
                qty_diff = curr_total - prev_total
                change_type = "Miktar Artışı" if qty_diff > 0 else "Miktar Azalışı"

                customer, item = get_customer_and_item(
                    sample.plant_no_customer,
                    sample.part_no_customer,
                )

                changes.append(
                    {
                        "order_no": sample.order_no,
                        "order_item": sample.order_item,
                        "part_no_customer": sample.part_no_customer,
                        "plant_no_customer": sample.plant_no_customer,
                        "customer": customer,
                        "item": item,
                        "change_type": change_type,
                        "old_delivery_date": sample.delivery_date,
                        "new_delivery_date": sample.delivery_date,
                        "old_delivery_quantity": prev_total,
                        "new_delivery_quantity": curr_total,
                        "difference": qty_diff,
                        "old_efz": prev_list[0].efz if prev_list else None,
                        "new_efz": curr_list[0].efz if curr_list else None,
                        "action_required": 1,
                        "action_status": "Beklemede",
                    }
                )

                dates_to_drop_from_prev.add(date_str)
                dates_to_drop_from_curr.add(date_str)

        if dates_to_drop_from_prev:
            unmatched_prev = [
                r for r in unmatched_prev if str(r.delivery_date) not in dates_to_drop_from_prev
            ]
        if dates_to_drop_from_curr:
            unmatched_curr = [
                r for r in unmatched_curr if str(r.delivery_date) not in dates_to_drop_from_curr
            ]

        if not unmatched_prev and not unmatched_curr:
            continue

        unmatched_prev.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
        )
        unmatched_curr.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
        )

        i = j = 0
        len_prev = len(unmatched_prev)
        len_curr = len(unmatched_curr)

        while i < len_prev and j < len_curr:
            prev = unmatched_prev[i]
            curr = unmatched_curr[j]

            customer, item = get_customer_and_item(
                curr.plant_no_customer,
                curr.part_no_customer,
            )

            date_changed = curr.delivery_date != prev.delivery_date
            qty_changed = curr.delivery_quantity != prev.delivery_quantity
            qty_diff = (curr.delivery_quantity or 0) - (prev.delivery_quantity or 0)

            if date_changed and qty_changed:
                change_type = "Tarih ve Miktar Değişikliği"
            elif date_changed:
                change_type = "Tarih Değişikliği"
            else:
                if qty_diff > 0:
                    change_type = "Miktar Artışı"
                elif qty_diff < 0:
                    change_type = "Miktar Azalışı"
                else:
                    i += 1
                    j += 1
                    continue

            changes.append(
                {
                    "order_no": curr.order_no,
                    "order_item": curr.order_item,
                    "part_no_customer": curr.part_no_customer,
                    "plant_no_customer": curr.plant_no_customer,
                    "customer": customer,
                    "item": item,
                    "change_type": change_type,
                    "old_delivery_date": prev.delivery_date,
                    "new_delivery_date": curr.delivery_date,
                    "old_delivery_quantity": prev.delivery_quantity,
                    "new_delivery_quantity": curr.delivery_quantity,
                    "difference": qty_diff,
                    "old_efz": prev.efz,
                    "new_efz": curr.efz,
                    "action_required": 1,
                    "action_status": "Beklemede",
                }
            )

            i += 1
            j += 1

        while i < len_prev:
            prev = unmatched_prev[i]
            customer, item = get_customer_and_item(
                prev.plant_no_customer,
                prev.part_no_customer,
            )

            changes.append(
                {
                    "order_no": prev.order_no,
                    "order_item": prev.order_item,
                    "part_no_customer": prev.part_no_customer,
                    "plant_no_customer": prev.plant_no_customer,
                    "customer": customer,
                    "item": item,
                    "change_type": "Silinen Satır",
                    "old_delivery_date": prev.delivery_date,
                    "old_delivery_quantity": prev.delivery_quantity,
                    "old_efz": prev.efz,
                    "action_required": 1,
                    "action_status": "Beklemede",
                }
            )

            i += 1

        while j < len_curr:
            curr = unmatched_curr[j]
            customer, item = get_customer_and_item(
                curr.plant_no_customer,
                curr.part_no_customer,
            )

            changes.append(
                {
                    "order_no": curr.order_no,
                    "order_item": curr.order_item,
                    "part_no_customer": curr.part_no_customer,
                    "plant_no_customer": curr.plant_no_customer,
                    "customer": customer,
                    "item": item,
                    "change_type": "Yeni Satır",
                    "new_delivery_date": curr.delivery_date,
                    "new_delivery_quantity": curr.delivery_quantity,
                    "new_efz": curr.efz,
                    "action_required": 1,
                    "action_status": "Beklemede",
                }
            )

            j += 1

    return changes
