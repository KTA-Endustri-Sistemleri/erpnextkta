# erpnextkta/stock_reco_api.py

import frappe
from frappe import _
from frappe.utils import cint, today, nowtime

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

    Result is sorted by (item_code, warehouse, batch_no) for stable ordering.
    """

    ignore_empty_stock = cint(ignore_empty_stock)

    if item_code and warehouse:
        items = get_item_and_warehouses(item_code, warehouse)
    else:
        items = get_items_for_stock_reco_static(warehouse, company)

    res = []
    itemwise_batch_data = get_itemwise_batch(warehouse, posting_date, company, item_code)

    for d in items:
        key = (d.item_code, d.warehouse)
        if key in itemwise_batch_data:
            valuation_rate = get_stock_balance(
                d.item_code,
                d.warehouse,
                posting_date,
                posting_time,
                with_valuation_rate=True,
            )[1]

            for row in itemwise_batch_data.get(key):
                if ignore_empty_stock and not row.qty:
                    continue

                args = get_item_data(row, row.qty, valuation_rate)
                res.append(args)
        else:
            stock_bal = get_stock_balance(
                d.item_code,
                d.warehouse,
                posting_date,
                posting_time,
                with_valuation_rate=True,
                with_serial_no=cint(d.has_serial_no),
            )
            qty, valuation_rate, serial_no = (
                stock_bal[0],
                stock_bal[1],
                stock_bal[2] if cint(d.has_serial_no) else "",
            )

            if ignore_empty_stock and not stock_bal[0]:
                continue

            args = get_item_data(d, qty, valuation_rate, serial_no)
            res.append(args)

    # stable ordering by item_code / warehouse / batch_no
    res.sort(key=lambda r: (r["item_code"], r["warehouse"], (r.get("batch_no") or "")))

    return res


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
        frappe.throw(_("Warehouse Group is required"))
    if not company:
        frappe.throw(_("Company is required"))

    posting_date = posting_date or today()
    posting_time = posting_time or nowtime()
    ignore_empty_stock = cint(ignore_empty_stock)

    requested_by = frappe.session.user

    job = frappe.enqueue(
        method="erpnextkta.stock_reco_api._job_create_stock_reco_docs_for_warehouse_group",
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
        "message": _("Background job queued. You will be notified when it finishes."),
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
    Items are populated using `get_items_static()` so qty/valuation/batch/serial logic remains consistent.
    """

    group = frappe.get_doc("Warehouse", warehouse_group)
    if not group.is_group:
        frappe.throw(_("Selected warehouse must be a group"))

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

    if not leaf_warehouses:
        frappe.throw(_("No leaf warehouses found under this group"))

    created = []
    skipped = []

    for wh in leaf_warehouses:
        rows = get_items_static(
            warehouse=wh,
            posting_date=posting_date,
            posting_time=posting_time,
            company=company,
            item_code=None,
            ignore_empty_stock=ignore_empty_stock,
        )

        # ✅ items boşsa belge yaratma (MandatoryError önler)
        if not rows:
            skipped.append(wh)
            continue

        doc = frappe.new_doc("Stock Reconciliation")
        doc.company = company
        doc.posting_date = posting_date
        doc.posting_time = posting_time
        doc.purpose = "Stock Reconciliation"

        # Header default warehouse
        if doc.meta.has_field("set_warehouse"):
            doc.set_warehouse = wh
        if doc.meta.has_field("warehouse"):
            doc.warehouse = wh

        doc.set("items", [])
        for row in rows:
            # ✅ Bulk akışında da bundle istemesin (manuel fetch ile aynı davranış)
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
            "subject": _("Bulk Stock Reconciliation Completed"),
            "email_content": msg.replace("\n", "<br>"),
            "for_user": user,
            "type": "Alert",
        }
    ).insert(ignore_permissions=True)