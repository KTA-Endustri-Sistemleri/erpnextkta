# erpnextkta/stock_reco_api.py

import frappe
from frappe import _
from frappe.utils import cint, flt, today, nowtime

from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
    get_itemwise_batch,
    get_stock_balance,
    get_item_data,
    get_item_and_warehouses,
)


def get_items_for_stock_reco_static(warehouse: str, company: str):
    """
    Return all item/warehouse pairs that currently have non-zero stock.

    Behavior:
    - If `warehouse` is a group: scan its warehouse tree (including itself).
    - If `warehouse` is a leaf: scan only that warehouse.

    Rules:
    - We look at Bin.actual_qty (current stock).
    - Only stock items, no variants, not disabled.
    - If actual_qty becomes 0, the pair will no longer appear in future runs.
    """

    wh = frappe.get_cached_doc("Warehouse", warehouse)

    if cint(wh.is_group):
        # group -> tree query
        warehouse_condition = "w.lft >= %s and w.rgt <= %s"
        params = (wh.lft, wh.rgt)
    else:
        # leaf -> only itself
        warehouse_condition = "bin.warehouse = %s"
        params = (warehouse,)

    items = frappe.db.sql(
        f"""
        select
            i.name as item_code,
            i.item_name,
            bin.warehouse as warehouse,
            i.has_serial_no,
            i.has_batch_no
        from `tabBin` bin
        join `tabItem` i on i.name = bin.item_code
        join `tabWarehouse` w on w.name = bin.warehouse
        where
            {warehouse_condition}
            and w.is_group = 0
            and ifnull(bin.actual_qty, 0) != 0
            and ifnull(i.disabled, 0) = 0
            and i.is_stock_item = 1
            and i.has_variants = 0
        """,
        params,
        as_dict=True,
    )

    # ensure one row per (item_code, warehouse)
    seen = set()
    deduped = []
    for row in items:
        key = (row["item_code"], row["warehouse"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


@frappe.whitelist()
def get_items_static(
    warehouse: str,
    posting_date: str,
    posting_time: str,
    company: str,
    item_code: str | None = None,
    ignore_empty_stock: int | str = 0,
):
    """
    Drop-in replacement for core `get_items` used by Stock Reconciliation,
    but with a different source for the base item list.
    Optimized to fetch balances in bulk.
    """

    ignore_empty_stock = cint(ignore_empty_stock)

    if item_code and warehouse:
        items = get_item_and_warehouses(item_code, warehouse)
    else:
        items = get_items_for_stock_reco_static(warehouse, company)

    if not items:
        return []

    # Bulk fetch data to avoid N+1 queries
    itemwise_batch_data = get_itemwise_batch(warehouse, posting_date, company, item_code)
    balances = get_bulk_stock_balances(warehouse, posting_date, posting_time)
    
    # We only need serial nos if some items have them
    has_serial_items = any(d.get("has_serial_no") for d in items)
    serial_nos_map = get_bulk_serial_nos(warehouse) if has_serial_items else {}

    res = []
    for d in items:
        key = (d.item_code, d.warehouse)
        
        # Get balance from pre-fetched data
        qty, valuation_rate = balances.get(key, (0.0, 0.0))

        if key in itemwise_batch_data:
            # Batch items: valuation rate comes from item-warehouse balance (standard ERPNext behavior)
            for row in itemwise_batch_data.get(key):
                if ignore_empty_stock and not row.qty:
                    continue

                args = get_item_data(row, row.qty, valuation_rate)
                res.append(args)
        else:
            # Serialized or Normal items
            serial_no = serial_nos_map.get(key, "") if d.get("has_serial_no") else ""
            
            if ignore_empty_stock and not qty:
                continue

            args = get_item_data(d, qty, valuation_rate, serial_no)
            res.append(args)

    # stable ordering by item_code / warehouse / batch_no
    res.sort(key=lambda r: (r["item_code"], r["warehouse"], (r.get("batch_no") or "")))

    return res


def get_bulk_stock_balances(warehouse: str, posting_date: str, posting_time: str):
    """
    Fetches latest qty and valuation rate for all items in a warehouse (or group).
    """
    wh = frappe.get_cached_doc("Warehouse", warehouse)
    
    # Fast path for today's date: use Bin table
    if posting_date >= today():
        data = frappe.db.sql("""
            select 
                bin.item_code, bin.warehouse, bin.actual_qty, bin.valuation_rate
            from `tabBin` bin
            join `tabWarehouse` w on w.name = bin.warehouse
            where w.lft >= %s and w.rgt <= %s
        """, (wh.lft, wh.rgt), as_dict=True)
        
        return {(d.item_code, d.warehouse): (flt(d.actual_qty), flt(d.valuation_rate)) for d in data}

    # Robust path for past dates: use ROW_NUMBER over SLE
    # Note: Requires MariaDB 10.2+ or MySQL 8.0+
    try:
        data = frappe.db.sql(f"""
            select warehouse, item_code, qty_after_transaction, valuation_rate
            from (
                select 
                    warehouse, item_code, qty_after_transaction, valuation_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY item_code, warehouse 
                        ORDER BY posting_date DESC, posting_time DESC, creation DESC, name DESC
                    ) as rn
                from `tabStock Ledger Entry`
                where warehouse in (select name from tabWarehouse where lft >= %s and rgt <= %s)
                and posting_date <= %s
                and (posting_date < %s or posting_time <= %s)
                and is_cancelled = 0
            ) t
            where rn = 1
        """, (wh.lft, wh.rgt, posting_date, posting_date, posting_time), as_dict=True)
    except Exception:
        # Fallback for very old DBs (though unlikely) or complex cases
        return {}

    return {(d.item_code, d.warehouse): (flt(d.qty_after_transaction), flt(d.valuation_rate)) for d in data}


def get_bulk_serial_nos(warehouse: str):
    """
    Fetches all active serial numbers grouped by item and warehouse.
    """
    wh = frappe.get_cached_doc("Warehouse", warehouse)
    data = frappe.db.sql("""
        select item_code, warehouse, GROUP_CONCAT(name SEPARATOR '\n') as serial_nos
        from `tabSerial No`
        where warehouse in (select name from tabWarehouse where lft >= %s and rgt <= %s)
        and status = 'Active'
        group by item_code, warehouse
    """, (wh.lft, wh.rgt), as_dict=True)
    
    return {(d.item_code, d.warehouse): d.serial_nos for d in data}


# ----------------------------
# Bulk creation (Background Job)
# ----------------------------

@frappe.whitelist()
def create_stock_reco_docs_for_warehouse_group(
    warehouse_group: str,
    company: str,
    posting_date: str | None = None,
    posting_time: str | None = None,
    ignore_empty_stock: int | str = 0,
):
    """
    Enqueue bulk creation to avoid request timeouts.
    Returns immediately with a job id (if available).
    """

    if not warehouse_group:
        frappe.throw(_("Depo Grubu zorunludur"))
    if not company:
        frappe.throw(_("Şirket zorunludur"))

    posting_date = posting_date or today()
    posting_time = posting_time or nowtime()
    ignore_empty_stock = cint(ignore_empty_stock)

    requested_by = frappe.session.user

    job = frappe.enqueue(
        method="erpnextkta.rest-api.stock_reconciliation._job_create_stock_reco_docs_for_warehouse_group",
        queue="long",
        timeout=60 * 60,  # 1 hour
        job_name=f"Bulk Stock Reco: {warehouse_group} ({posting_date} {posting_time})",
        warehouse_group=warehouse_group,
        company=company,
        posting_date=posting_date,
        posting_time=posting_time,
        ignore_empty_stock=ignore_empty_stock,
        requested_by=requested_by,
    )

    return {
        "queued": True,
        "job_id": getattr(job, "id", None),
        "message": _("Arkaplan görevi sıraya alındı. Tamamlandığında bildirim alacaksınız."),
    }


def _job_create_stock_reco_docs_for_warehouse_group(
    warehouse_group: str,
    company: str,
    posting_date: str,
    posting_time: str,
    ignore_empty_stock: int,
    requested_by: str | None = None,
):
    """
    Worker job: create one Stock Reconciliation (DRAFT) per leaf warehouse under the group.
    Optimized: fetches all items for the group once and partitions them.
    """

    group = frappe.get_doc("Warehouse", warehouse_group)
    if not group.is_group:
        frappe.throw(_("Seçilen depo bir grup olmalıdır"))

    # Fetch ALL items for the entire group in one go
    all_rows = get_items_static(
        warehouse=warehouse_group,
        posting_date=posting_date,
        posting_time=posting_time,
        company=company,
        item_code=None,
        ignore_empty_stock=ignore_empty_stock,
    )

    if not all_rows:
        frappe.throw(_("Bu depo grubunda stoğu olan ürün bulunamadı"))

    # Partition by warehouse
    warehouse_partition = {}
    for row in all_rows:
        wh = row["warehouse"]
        if wh not in warehouse_partition:
            warehouse_partition[wh] = []
        warehouse_partition[wh].append(row)

    created = []
    skipped = []

    # Get leaf warehouses under this group (to identify empty ones)
    leaf_warehouses = frappe.get_all(
        "Warehouse",
        filters={
            "lft": (">", group.lft),
            "rgt": ("<", group.rgt),
            "is_group": 0,
        },
        pluck="name",
        order_by="name asc",
    )

    for wh in leaf_warehouses:
        rows = warehouse_partition.get(wh)

        if not rows:
            skipped.append(wh)
            continue

        doc = frappe.new_doc("Stock Reconciliation")
        doc.company = company
        doc.posting_date = posting_date
        doc.posting_time = posting_time
        doc.purpose = "Stock Reconciliation"

        if doc.meta.has_field("set_warehouse"):
            doc.set_warehouse = wh
        if doc.meta.has_field("warehouse"):
            doc.warehouse = wh

        doc.set("items", [])
        for row in rows:
            row["use_serial_batch_fields"] = 1
            doc.append("items", row)

        doc.insert()  # DRAFT

        created.append({"warehouse": wh, "name": doc.name, "item_count": len(rows)})

    if requested_by:
        _notify_bulk_stock_reco_result(
            user=requested_by,
            warehouse_group=warehouse_group,
            created=created,
            skipped=skipped,
        )

    return {
        "count": len(created),
        "documents": created,
        "skipped_count": len(skipped),
        "skipped_warehouses": skipped,
    }


def _notify_bulk_stock_reco_result(user: str, warehouse_group: str, created: list, skipped: list):
    """
    Notify user via Notification Log when the background job is done.
    """
    created_count = len(created)
    skipped_count = len(skipped)

    preview = "\n".join([f"- {d['name']} ({d['warehouse']})" for d in created[:20]])
    more = "" if created_count <= 20 else f"\n... (+{created_count - 20} more)"

    msg = (
        f"Warehouse Group: {warehouse_group}\n"
        f"Created: {created_count}\n"
        f"Skipped (no stock): {skipped_count}\n\n"
        f"Created docs:\n{preview}{more}"
    )

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "subject": _("Toplu Stok Uzlaştırması Tamamlandı"),
            "email_content": msg.replace("\n", "<br>"),
            "for_user": user,
            "type": "Alert",
        }
    ).insert(ignore_permissions=True)