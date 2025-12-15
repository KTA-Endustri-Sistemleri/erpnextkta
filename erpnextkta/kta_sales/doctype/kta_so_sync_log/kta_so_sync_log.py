import json
from collections import defaultdict, Counter
import time
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, today, cstr
from erpnext.controllers.accounts_controller import update_child_qty_rate
from erpnext.utilities.transaction_base import UOMMustBeIntegerError


from erpnextkta.kta_sales.doctype.kta_sales_order_update.kta_sales_order_update import (
    adjust_sales_order_update_with_shipments,
    get_sales_order_update_doc,
)
class KTASOSyncLog(Document):
	pass


@frappe.whitelist()
def sync_sales_orders_from_sales_order_update(
    sales_order_update_name=None, sales_order_update_reference=None
):
    """
    Sales Order Update'den senkronizasyonu background job olarak başlat.
    """
    reference_name = sales_order_update_reference or sales_order_update_name
    if not reference_name:
        frappe.throw(_("Sales Order Update seçilmedi."))

    job, sync_log = enqueue_sales_order_sync(reference_name)
    return {
        "status": "queued",
        "job_id": job.id if job else None,
        "info": _("Sales Order senkronizasyonu kuyruğa alındı."),
        "sync_log": sync_log.name if sync_log else None,
    }


@frappe.whitelist()
def sync_sales_orders_from_comparison(comparison_name):
    """
    Karşılaştırmadan Sales Order'ları senkronizasyonu background job olarak başlat.
    """
    comparison = frappe.get_doc("KTA Sales Order Update Comparison", comparison_name)
    job, sync_log = enqueue_sales_order_sync(
        comparison.current_sales_order_update, comparison=comparison
    )

    return {
        "status": "queued",
        "job_id": job.id if job else None,
        "info": _("Karşılaştırma senkronizasyonu kuyruğa alındı."),
        "sync_log": sync_log.name if sync_log else None,
    }


def enqueue_sales_order_sync(sales_order_update_name, comparison=None):
    """Senkronizasyon işlemini uzun kuyrukta çalıştır."""
    sales_order_update_doc = get_sales_order_update_doc(sales_order_update_name)
    sync_log = create_sync_log_doc(sales_order_update_doc, comparison=comparison)

    comparison_name = comparison.name if comparison else None
    job_name = f"KTA SO Sync {sales_order_update_name}"

    job = frappe.enqueue(
        "erpnextkta.kta_sales.doctype.kta_so_sync_log.kta_so_sync_log.run_sales_order_sync_job",
        queue="long",
        job_name=job_name,
        sales_order_update_name=sales_order_update_name,
        comparison_name=comparison_name,
        sync_log_name=sync_log.name,
    )

    return job, sync_log


def run_sales_order_sync_job(sales_order_update_name, comparison_name=None, sync_log_name=None):
    """Worker içinde gerçek senkronizasyonu çalıştır."""
    comparison = None
    if comparison_name:
        comparison = frappe.get_doc("KTA Sales Order Update Comparison", comparison_name)

    return _sync_sales_orders_from_sales_order_update(
        sales_order_update_name, comparison=comparison, sync_log_name=sync_log_name
    )


def _sync_sales_orders_from_sales_order_update(sales_order_update_name, comparison=None, sync_log_name=None):
    """
    Seçilen Sales Order Update için sevkiyat düşülmüş değişiklikleri üretip ERP'ye uygular.
    """
    sales_order_update_doc = get_sales_order_update_doc(sales_order_update_name)
    sync_log = get_or_create_sync_log_doc(
        sales_order_update_doc, comparison=comparison, sync_log_name=sync_log_name
    )

    now_ts = frappe.utils.now()
    sync_log.db_set("status", "In Progress", update_modified=False)
    sync_log.db_set("sync_date", now_ts, update_modified=False)
    sync_log.status = "In Progress"
    sync_log.sync_date = now_ts

    sync_changes = [
        frappe._dict(change)
        for change in build_sales_order_sync_changes(sales_order_update_doc.name)
    ]

    sync_log.db_set("total_changes", len(sync_changes), update_modified=False)
    sync_log.total_changes = len(sync_changes)

    created = updated = closed = errors = 0

    try:
        if not sync_changes:
            sync_log.status = "Completed"
            sync_log.comment = "No changes detected for this Sales Order Update."
            sync_log.save()
            sales_order_update_doc.db_set("last_sync_log", sync_log.name, update_modified=False)
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
            comparison.db_set("status", "Synced", update_modified=False)

        sales_order_update_doc.db_set("last_sync_log", sync_log.name, update_modified=False)

    except Exception as e:
        # KTA SO Sync Log üzerinde sadece kısa bir özet sakla
        sync_log.status = "Failed"
        # error_log alanın Data(140) ise güvenli tarafta kalmak için truncate et
        # error_log alanın Data(140) ise güvenli tarafta kalmak için truncate et
        try:
            sync_log.error_log = cstr(e)[:140]
        except Exception:
            sync_log.error_log = str(e)[:140]

        # Tam traceback’i Error Log’a yaz
        frappe.log_error("SO Sync Critical Error", frappe.get_traceback())

    # Link alanlarında silinmiş belgeler olabilir, validation hatasını önlemek için temizle
    for detail in sync_log.get("sync_details", []):
        so_value = detail.get("sales_order")
        if so_value and not frappe.db.exists("Sales Order", so_value):
            detail.sales_order = None

    # Child tablodaki linkler silinmiş olabilir, validation hatasını önlemek için atla
    sync_log.flags.ignore_links = True

    # Guarantee save/commit even if above except had issues   
    try:
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error("Final sync_log.save failed", frappe.get_traceback())

    result = {
        "sync_log": sync_log.name,
        "created": created,
        "updated": updated,
        "closed": closed,
        "errors": errors,
    }

    return result


def get_or_create_sync_log_doc(sales_order_update_doc, comparison=None, sync_log_name=None):
    """Retrieve provided log, fallback to pending one, otherwise create new."""
    if sync_log_name:
        return frappe.get_doc("KTA SO Sync Log", sync_log_name)

    filters = {"sales_order_update": sales_order_update_doc.name}
    if comparison:
        filters["comparison"] = comparison.name
    filters["status"] = ["in", ["Draft", "In Progress"]]

    existing = frappe.get_all(
        "KTA SO Sync Log", filters=filters, fields=["name"], order_by="creation desc", limit=1
    )

    if existing:
        return frappe.get_doc("KTA SO Sync Log", existing[0].name)

    return create_sync_log_doc(sales_order_update_doc, comparison=comparison)


def create_sync_log_doc(sales_order_update_doc, comparison=None):
    """Create a fresh sync log record for the given Sales Order Update."""
    sync_log = frappe.new_doc("KTA SO Sync Log")
    sync_log.sales_order_update = sales_order_update_doc.name
    if comparison:
        sync_log.comparison = comparison.name
    sync_log.sync_date = frappe.utils.now()
    sync_log.status = "Draft"
    sync_log.total_changes = 0
    sync_log.insert(ignore_permissions=True)
    frappe.db.commit()
    return sync_log


def build_sales_order_sync_changes(sales_order_update_name):
    rows = frappe.db.sql(
        """
        SELECT order_no, part_no_customer, delivery_date, delivery_quantity, plant_no_customer, plant
        FROM `tabKTA Sales Order Update Entry`
        WHERE parent = %s
        ORDER BY order_no, part_no_customer, plant_no_customer, delivery_date
        """,
        (sales_order_update_name,),
        as_dict=True,
    )

    if not rows:
        frappe.log_error("Hiç plan satırı yok", "SO Sync - No Rows")
        return []

    adjusted_rows = adjust_sales_order_update_with_shipments(rows)
    plan_rows_by_key = defaultdict(list)
    customer_item_cache = {}

    # 1) PLAN TARAFINI GRUPLA
    for row in adjusted_rows:
        if not row.order_no or not row.part_no_customer:
            continue

        cache_key = (row.plant or row.plant_no_customer, row.part_no_customer)
        cached_values = customer_item_cache.get(cache_key)

        if not cached_values:
            customer_value = cstr(row.plant or row.plant_no_customer).strip()
            item_value = cstr(row.part_no_customer).strip()
            if not (customer_value and item_value):
                continue

            cached_values = frappe._dict({"customer": customer_value, "item_code": item_value})
            customer_item_cache[cache_key] = cached_values

        order_no = cstr(row.order_no).strip()
        item_code = cached_values.item_code
        customer = cached_values.customer

        plan_entry = frappe._dict(
            {
                "order_no": order_no,
                "order_item": None,
                "part_no_customer": item_code,
                "plant_no_customer": row.plant_no_customer,
                "customer": customer,
                "item": item_code,
                "delivery_date": row.delivery_date,
                "planned_qty": flt(row.delivery_quantity or 0),
            }
        )
        key = (customer, order_no, item_code)
        plan_rows_by_key[key].append(plan_entry)

    for lst in plan_rows_by_key.values():
        lst.sort(key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01"))

    # 2) ERP TARAFINI ÇEK & GRUPLA
    erp_rows = fetch_open_sales_orders_with_item_dates()
    erp_rows_by_key = defaultdict(list)

    for so in erp_rows:
        if not so.po_no or not so.item_code:
            continue
        order_no = cstr(so.po_no).strip()
        item_code = cstr(so.item_code).strip()
        pending_qty = flt(so.pending_qty or (so.qty - so.delivered_qty))
        if pending_qty <= 0:
            continue

        key = (so.customer, order_no, item_code)
        erp_rows_by_key[key].append(frappe._dict({
            "sales_order": so.sales_order,
            "sales_order_item": so.sales_order_item,
            "customer": so.customer,
            "order_no": order_no,
            "item_code": item_code,
            "delivery_date": so.item_delivery_date,
            "qty": flt(so.qty),
            "delivered_qty": flt(so.delivered_qty),
            "pending_qty": pending_qty,
        }))

    for lst in erp_rows_by_key.values():
        lst.sort(key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01"))

    # 3) KARŞILAŞTIRMA MANTIĞI
    changes = []
    all_keys = set(plan_rows_by_key.keys()) | set(erp_rows_by_key.keys())

    for key in all_keys:
        plan_rows = list(plan_rows_by_key.get(key, []))
        erp_rows = list(erp_rows_by_key.get(key, []))
        customer, order_no, item_code = key

        # ADIM 1: Tam eşleşme (tarih + qty)
        matched_plan_indices = set()
        matched_erp_indices = set()

        for p_idx, plan_row in enumerate(plan_rows):
            for e_idx, erp_row in enumerate(erp_rows):
                if e_idx in matched_erp_indices:
                    continue
                
                if (str(plan_row.delivery_date) == str(erp_row.delivery_date) and
                    abs(flt(plan_row.planned_qty) - flt(erp_row.pending_qty)) < 0.001):
                    matched_plan_indices.add(p_idx)
                    matched_erp_indices.add(e_idx)
                    break

        # Eşleşmeyenleri ayır
        unmatched_plan = [r for idx, r in enumerate(plan_rows) if idx not in matched_plan_indices]
        unmatched_erp = [r for idx, r in enumerate(erp_rows) if idx not in matched_erp_indices]

        # ADIM 2: Aynı tarihteki satırları grupla
        plan_by_date = defaultdict(list)
        erp_by_date = defaultdict(list)

        for idx, r in enumerate(unmatched_plan):
            plan_by_date[str(r.delivery_date)].append((idx, r))
        
        for idx, r in enumerate(unmatched_erp):
            erp_by_date[str(r.delivery_date)].append((idx, r))

        used_plan_indices = set()
        used_erp_indices = set()

        # Ortak tarihlerde sadece qty farklı olanları eşleştir
        common_dates = set(plan_by_date.keys()) & set(erp_by_date.keys())
        
        for date_key in sorted(common_dates):
            plan_date_items = plan_by_date[date_key]
            erp_date_items = erp_by_date[date_key]
            
            # Tarihe göre sıralı eşleştir
            for i in range(min(len(plan_date_items), len(erp_date_items))):
                p_idx, p_row = plan_date_items[i]
                e_idx, e_row = erp_date_items[i]
                
                if p_idx in used_plan_indices or e_idx in used_erp_indices:
                    continue
                
                # Qty değişikliği
                plan_qty = flt(p_row.planned_qty or 0)
                erp_qty = flt(e_row.pending_qty or 0)
                qty_diff = abs(plan_qty - erp_qty)
                if qty_diff > 0.001 or plan_qty <= 0:
                    change_type = "Miktar Artışı" if plan_qty > erp_qty else "Miktar Azalışı"
                    if plan_qty <= 0:
                        change_type = "Silinen Satır"
                        plan_qty = 0

                    changes.append({
                        "order_no": order_no,
                        "item": item_code,
                        "customer": customer,
                        "matched_sales_order": e_row.sales_order,
                        "order_item": e_row.sales_order_item,
                        "change_type": change_type,
                        "old_delivery_date": e_row.delivery_date,
                        "new_delivery_date": p_row.delivery_date,
                        "old_delivery_quantity": erp_qty,
                        "new_delivery_quantity": plan_qty,
                    })
                    
                    used_plan_indices.add(p_idx)
                    used_erp_indices.add(e_idx)

        # ADIM 3: Kalan satırları tarih sırasına göre eşleştir (hem tarih hem qty değişir)
        remaining_plan = [(idx, r) for idx, r in enumerate(unmatched_plan) if idx not in used_plan_indices]
        remaining_erp = [(idx, r) for idx, r in enumerate(unmatched_erp) if idx not in used_erp_indices]

        min_len = min(len(remaining_plan), len(remaining_erp))
        
        for i in range(min_len):
            p_idx, p_row = remaining_plan[i]
            e_idx, e_row = remaining_erp[i]
            plan_qty = flt(p_row.planned_qty or 0)
            erp_qty = flt(e_row.pending_qty or 0)

            if plan_qty <= 0:
                change_type = "Silinen Satır"
                plan_qty = 0
            else:
                date_changed = p_row.delivery_date != e_row.delivery_date
                qty_changed = abs(plan_qty - erp_qty) > 0.001

                if date_changed and qty_changed:
                    change_type = "Tarih ve Miktar Değişikliği"
                elif date_changed:
                    change_type = "Tarih Değişikliği"
                elif qty_changed:
                    change_type = "Miktar Artışı" if plan_qty > erp_qty else "Miktar Azalışı"
                else:
                    continue

            changes.append({
                "order_no": order_no,
                "item": item_code,
                "customer": customer,
                "matched_sales_order": e_row.sales_order,
                "order_item": e_row.sales_order_item,
                "change_type": change_type,
                "old_delivery_date": e_row.delivery_date,
                "new_delivery_date": p_row.delivery_date,
                "old_delivery_quantity": erp_qty,
                "new_delivery_quantity": plan_qty,
            })

        # ADIM 4: ERP'de fazla - silinecek
        for i in range(min_len, len(remaining_erp)):
            e_idx, e_row = remaining_erp[i]
            changes.append({
                "order_no": order_no,
                "item": item_code,
                "customer": customer,
                "matched_sales_order": e_row.sales_order,
                "order_item": e_row.sales_order_item,
                "change_type": "Silinen Satır",
                "old_delivery_date": e_row.delivery_date,
                "old_delivery_quantity": e_row.pending_qty,
            })

        # ADIM 5: Plan'da fazla - yeni satır (sync log'a kaydedilecek)
        for i in range(min_len, len(remaining_plan)):
            p_idx, p_row = remaining_plan[i]
            plan_qty = flt(p_row.planned_qty or 0)
            if plan_qty <= 0:
                continue
            changes.append({
                "order_no": order_no,
                "item": item_code,
                "customer": customer,
                "change_type": "Yeni Satır",
                "new_delivery_date": p_row.delivery_date,
                "new_delivery_quantity": plan_qty,
            })

    return changes


def process_sales_order_batch(so_identifier, changes):
    """
    Detayları doğru şekilde kaydet ve yeni siparişleri de sync log'a ekle.
    """
    customer, order_no, so_name = so_identifier
    details = []
    created = updated = closed = errors = 0

    if so_name == "NEW":
        # Yeni sipariş gerekli - sync log'a kaydet
        for change in changes:
            details.append({
                "action": "New Order Required",
                "sales_order": None,
                "customer": customer,
                "item": change.item,
                "order_no": change.order_no,
                "order_item": getattr(change, "order_item", None),
                "old_qty": None,
                "new_qty": change.new_delivery_quantity,
                "old_date": None,
                "new_date": change.new_delivery_date,
                "change_type": change.change_type,
                "error_message": _("PO {0}, Item {1} için yeni Sales Order manuel oluşturulmalı.").format(
                    order_no, change.item
                ),
            })
        errors = len(changes)
    else:
        try:
            result = update_existing_sales_order_batch(so_name, changes)
            details.extend(result["details"])
            updated = result.get("updated", 0)
            closed = result.get("closed", 0)
            errors = result.get("errors", 0)
        except Exception as e:
            frappe.log_error("SO Batch Update Failed", frappe.get_traceback())
            # Hata durumunda her değişiklik için detay kaydı oluştur
            for change in changes:
                details.append({
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": customer,
                    "item": getattr(change, "item", None),
                    "order_no": getattr(change, "order_no", None),
                    "order_item": getattr(change, "order_item", None),
                    "old_qty": getattr(change, "old_delivery_quantity", None),
                    "new_qty": getattr(change, "new_delivery_quantity", None),
                    "old_date": getattr(change, "old_delivery_date", None),
                    "new_date": getattr(change, "new_delivery_date", None),
                    "change_type": getattr(change, "change_type", None),
                    "error_message": cstr(e)[:140],
                })
            errors = len(changes)

    return {
        "details": details,
        "created": created,
        "updated": updated,
        "closed": closed,
        "errors": errors,
    }


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

        # Yeni satırlar için mevcut SO araması yapma
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

def fetch_open_sales_orders_with_item_dates():
    """
    Sales Order Item seviyesindeki delivery_date'i getir.
    Tüm açık siparişleri çeker, customer filtresi yok.
    """
    return frappe.db.sql(
        """
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
          AND so.po_no IS NOT NULL
          AND so.po_no != ''
        ORDER BY so.po_no, soi.item_code, soi.delivery_date
        """,
        as_dict=True,
    )

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
    Sales Order Item seviyesinde delivery_date ve qty güncelle.
    Tüm hataları ve değişiklikleri detaylı kaydeder.
    """
    details = []
    updated = closed = errors = 0
    start_ts = time.perf_counter()

    try:
        so = frappe.get_doc("Sales Order", so_name)
        
        if not so.items:
            details.append({
                "action": "Error",
                "sales_order": so_name,
                "customer": so.customer if hasattr(so, "customer") else None,
                "error_message": _("Sales Order'da hiç item yok."),
            })
            return {
                "details": details,
                "updated": 0,
                "closed": 0,
                "errors": 1,
            }

        # Item mapping
        item_map_by_name = {it.name: it for it in so.items}
        item_map_by_code = defaultdict(list)
        for it in so.items:
            item_map_by_code[it.item_code].append(it)

        for lst in item_map_by_code.values():
            lst.sort(key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01"))

        def remove_from_code_map(target):
            candidates = item_map_by_code.get(target.item_code)
            if not candidates:
                return
            for idx, cand in enumerate(candidates):
                if cand.name == target.name:
                    candidates.pop(idx)
                    break

        def resolve_target_item(change):
            item_code = getattr(change, "item", None)
            order_item_name = getattr(change, "order_item", None)

            if order_item_name:
                target = item_map_by_name.pop(order_item_name, None)
                if target:
                    remove_from_code_map(target)
                    return target

            if not item_code:
                return None

            candidates = item_map_by_code.get(item_code) or []
            if not candidates:
                return None

            desired_date = getattr(change, "old_delivery_date", None) or getattr(
                change, "new_delivery_date", None
            )
            if desired_date:
                desired_date = getdate(desired_date)
                for idx, cand in enumerate(candidates):
                    cand_date = getdate(cand.delivery_date) if cand.delivery_date else None
                    if cand_date == desired_date:
                        target = candidates.pop(idx)
                        item_map_by_name.pop(target.name, None)
                        return target

            target = candidates.pop(0)
            item_map_by_name.pop(target.name, None)
            return target

        trans_items = []
        delivery_dates_to_set = []
        order_deleted = False

        for change in changes:
            item_code = getattr(change, "item", None)
            target_item = resolve_target_item(change)
            
            if not target_item:
                details.append({
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": item_code,
                    "order_no": so.po_no,
                    "change_type": getattr(change, "change_type", None),
                    "new_qty": getattr(change, "new_delivery_quantity", None),
                    "new_date": getattr(change, "new_delivery_date", None),
                    "error_message": _("Sales Order içinde eşleşen item bulunamadı."),
                })
                errors += 1
                continue

            change_type = getattr(change, "change_type", None)
            new_pending_qty = flt(getattr(change, "new_delivery_quantity", 0) or 0)

            # Yeni satır durumu - SO'ya eklenemez, sync log'a kaydedilir
            if change_type == "Yeni Satır":
                details.append({
                    "action": "New Line Required",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": item_code,
                    "order_no": so.po_no,
                    "new_qty": new_pending_qty,
                    "new_date": getattr(change, "new_delivery_date", None),
                    "change_type": _("Yeni Satır"),
                    "error_message": _("PO {0}, Item {1} için yeni delivery line eklenmelidir. Manuel işlem gerekli.").format(
                        so.po_no, item_code
                    ),
                })
                errors += 1
                continue

            # Silinen satır kontrolü
            if change_type != "Silinen Satır" and new_pending_qty <= 0:
                change_type = "Silinen Satır"
                if hasattr(change, "change_type"):
                    change.change_type = "Silinen Satır"
                change.new_delivery_quantity = 0

            # Silinen satır işleme
            if change_type == "Silinen Satır":
                delivered_qty = flt(target_item.delivered_qty)
                billed_amt = flt(getattr(target_item, "billed_amt", 0))
                rate_for_billing = flt(target_item.rate) or flt(getattr(target_item, "base_rate", 0))
                billed_qty = flt(billed_amt / rate_for_billing) if rate_for_billing else 0

                if delivered_qty <= 0 and billed_qty <= 0:
                    so.cancel()
                    frappe.delete_doc("Sales Order", so_name, force=1, ignore_permissions=True)

                    details.append({
                        "action": "Closed",
                        "sales_order": so_name,
                        "customer": so.customer,
                        "item": target_item.item_code,
                        "order_no": so.po_no,
                        "old_qty": target_item.qty,
                        "new_qty": 0,
                        "old_date": target_item.delivery_date,
                        "new_date": target_item.delivery_date,
                        "change_type": _("Silinen Satır (SO iptal edildi ve silindi)"),
                    })
                    closed += 1
                    order_deleted = True
                    break

                new_total_qty = max(delivered_qty, billed_qty)
                note_bits = []
                if delivered_qty > 0:
                    note_bits.append(_("Teslim edilen qty: {0}").format(delivered_qty))
                if billed_qty > delivered_qty:
                    note_bits.append(_("Faturalandırılan qty: {0}").format(billed_qty))

                trans_items.append({
                    "docname": target_item.name,
                    "item_code": target_item.item_code,
                    "qty": new_total_qty,
                    "rate": target_item.rate,
                    "uom": target_item.uom,
                    "conversion_factor": target_item.conversion_factor,
                    "delivery_date": str(getdate(target_item.delivery_date)) if target_item.delivery_date else None,
                })

                details.append({
                    "action": "Closed",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "new_qty": new_total_qty,
                    "old_date": target_item.delivery_date,
                    "new_date": target_item.delivery_date,
                    "change_type": "Silinen Satır (" + ", ".join(note_bits or [_("Teslimat miktarına çekildi")]) + ")",
                })
                closed += 1
                if target_item.delivery_date:
                    delivery_dates_to_set.append(getdate(target_item.delivery_date))
                continue

            # Miktar/tarih değişiklikleri
            elif change_type in ["Miktar Artışı", "Miktar Azalışı", "Tarih Değişikliği", "Tarih ve Miktar Değişikliği"]:
                desired_pending_qty = max(flt(getattr(change, "new_delivery_quantity", 0) or 0), 0)
                new_total_qty = flt(target_item.delivered_qty) + desired_pending_qty
                new_date = getattr(change, "new_delivery_date", None) or target_item.delivery_date

                # Transaction date için yeni delivery_date'i topla
                if new_date:
                    delivery_dates_to_set.append(getdate(new_date))

                trans_items.append({
                    "docname": target_item.name,
                    "item_code": target_item.item_code,
                    "qty": new_total_qty,
                    "rate": target_item.rate,
                    "uom": target_item.uom,
                    "conversion_factor": target_item.conversion_factor,
                    "delivery_date": str(getdate(new_date)) if new_date else None,
                })

                details.append({
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
                })

            else:
                details.append({
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "old_date": target_item.delivery_date,
                    "change_type": change_type,
                    "error_message": _("Bilinmeyen change_type: {0}").format(change_type),
                })
                errors += 1
                continue

        if order_deleted:
            return {
                "details": details,
                "updated": updated,
                "closed": closed,
                "errors": errors,
            }

        # Güncellenecek teslimat tarihleri için Sales Order transaction/delivery date'ini öne çek
        if delivery_dates_to_set:
            new_min_delivery = min(delivery_dates_to_set)
            current_transaction_date = getdate(so.transaction_date) if so.transaction_date else None
            if not current_transaction_date or current_transaction_date > new_min_delivery:
                so.db_set("transaction_date", new_min_delivery, update_modified=False)
                so.transaction_date = new_min_delivery
                so.db_set("delivery_date", new_min_delivery, update_modified=False)
                so.delivery_date = new_min_delivery

        # Tek seferde güncelleme
        if trans_items:
            try:
                update_child_qty_rate(
                    parent_doctype="Sales Order",
                    trans_items=json.dumps(trans_items),
                    parent_doctype_name=so.name,
                    child_docname="items",
                )
            except Exception as e:
                frappe.log_error("update_child_qty_rate failed", frappe.get_traceback())
                details.append({
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "order_no": so.po_no,
                    "error_message": _("Güncelleme hatası: {0}").format(cstr(e)[:100]),
                })
                errors += 1
                return {
                    "details": details,
                    "updated": 0,
                    "closed": 0,
                    "errors": errors,
                }

        # Sayımları hesapla
        for d in details:
            if d.get("action") == "Updated":
                updated += 1
            elif d.get("action") == "Closed":
                closed += 1

        # SO'yu yeniden yükle
        so.reload()

        # Tüm qty sıfırsa ve teslimat yoksa SO'yu sil
        if so.docstatus == 1:
            has_delivery_or_billing = any(
                flt(it.delivered_qty) > 0 or flt(getattr(it, "billed_amt", 0)) > 0
                for it in so.items
            )
            all_zero_qty = all(flt(it.qty) <= 0 for it in so.items)
            all_delivered = all(flt(it.qty) <= flt(it.delivered_qty or 0) for it in so.items)

            if all_zero_qty and not has_delivery_or_billing:
                so.cancel()
                frappe.delete_doc("Sales Order", so_name, force=1, ignore_permissions=True)
                
                details.append({
                    "action": "Closed",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "order_no": so.po_no,
                    "change_type": _("Tüm itemlar silindi, SO iptal edildi"),
                })
                closed += 1
            elif all_delivered:
                so.db_set("status", "Completed", update_modified=False)

        # Transaction / delivery date güncelleme
        # Eğer item delivery_date değiştiyse, SO.transaction_date ve delivery_date'i hizala
        if delivery_dates_to_set:
            # Tüm güncellenen delivery_date'lerin en küçüğünü seç
            new_transaction_date = min(delivery_dates_to_set)
            so.db_set("transaction_date", new_transaction_date, update_modified=False)
            so.db_set("delivery_date", new_transaction_date, update_modified=False)

        elapsed = time.perf_counter() - start_ts
        frappe.logger().debug(f"KTA SO Sync: SO {so_name} işlendi ({elapsed:.3f}s), {len(trans_items)} item")

        return {
            "details": details,
            "updated": updated,
            "closed": closed,
            "errors": errors,
        }

    except UOMMustBeIntegerError:
        raise
    except Exception as e:
        frappe.log_error("SO Update Critical", frappe.get_traceback())
        
        # Hata durumunda tüm değişiklikler için detay oluştur
        for change in changes:
            details.append({
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
                "error_message": _("Kritik hata: {0}").format(cstr(e)[:100]),
            })

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
