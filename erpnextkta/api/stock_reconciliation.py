# erpnextkta/stock_reco_api.py

import frappe
from frappe.utils import cint

from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
    get_itemwise_batch,
    get_stock_balance,
    get_item_data,
    get_item_and_warehouses,
)


def get_items_for_stock_reco_static(warehouse: str, company: str):
    """
    Return all item/warehouse pairs that currently have non-zero stock
    in this warehouse tree.

    Rules:
    - We look at Bin.actual_qty (current stock).
    - Only warehouses under the selected warehouse (including itself).
    - Only stock items, no variants, not disabled.
    - If actual_qty becomes 0, the pair will no longer appear in future runs.
    """

    lft, rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])

    items = frappe.db.sql(
        """
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
            w.lft >= %s and w.rgt <= %s
            and w.is_group = 0
            and ifnull(bin.actual_qty, 0) != 0
            and ifnull(i.disabled, 0) = 0
            and i.is_stock_item = 1
            and i.has_variants = 0
        """,
        (lft, rgt),
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
    but with a different source for the base item list:

    - When item_code is given: reuse core `get_item_and_warehouses`.
    - When item_code is empty: use our `get_items_for_stock_reco_static`, which
      only returns items that currently have non-zero stock in this warehouse tree.

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