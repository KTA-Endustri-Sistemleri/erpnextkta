# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

ROLE_REQUIRED = "Stock Reconciliation Manager"


def _require_role():
    """Allow only Stock Reconciliation Manager role to access API."""
    user = frappe.session.user
    roles = frappe.get_roles(user) or []
    if ROLE_REQUIRED not in roles:
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _has_column(doctype: str, fieldname: str) -> bool:
    """Return True if DB table for doctype has given column."""
    cols = frappe.db.get_table_columns(doctype) or []
    return fieldname in cols


def _diff_expr(alias: str = "sri") -> str:
    """
    Build a portable diff expression for Stock Reconciliation Item.

    Field variants observed across versions/customizations:
    - quantity_difference (your case)
    - difference_qty
    Fallback:
    - qty - current_qty
    """
    if _has_column("Stock Reconciliation Item", "quantity_difference"):
        return f"COALESCE({alias}.quantity_difference, 0)"

    if _has_column("Stock Reconciliation Item", "difference_qty"):
        return f"COALESCE({alias}.difference_qty, 0)"

    return f"(COALESCE({alias}.qty, 0) - COALESCE({alias}.current_qty, 0))"


@frappe.whitelist()
def get_years():
    """Return distinct years from Stock Reconciliation posting_date."""
    _require_role()

    rows = frappe.db.sql(
        """
        SELECT DISTINCT YEAR(posting_date) AS y
        FROM `tabStock Reconciliation`
        WHERE posting_date IS NOT NULL
        ORDER BY y DESC
        """
    )
    return [r[0] for r in rows if r and r[0]]


@frappe.whitelist()
def get_dashboard(year: int):
    """
    Aggregate draft Stock Reconciliation impact by item and warehouse (docstatus=0).

    Note: Uses portable diff field logic via _diff_expr().
    """
    _require_role()

    try:
        year = int(year)
    except Exception:
        frappe.throw(_("Invalid year"))

    diff = _diff_expr("sri")

    rows = frappe.db.sql(
        f"""
        SELECT
            sri.item_code,
            it.item_name AS item_name,
            it.stock_uom AS uom,
            sri.warehouse,
            SUM({diff}) AS diff_qty,
            COUNT(DISTINCT sr.name) AS docs_count
        FROM `tabStock Reconciliation` sr
        INNER JOIN `tabStock Reconciliation Item` sri
            ON sri.parent = sr.name
        LEFT JOIN `tabItem` it
            ON it.name = sri.item_code
        WHERE
            sr.docstatus = 0
            AND sr.posting_date IS NOT NULL
            AND YEAR(sr.posting_date) = %(year)s
        GROUP BY sri.item_code, sri.warehouse
        HAVING ABS(diff_qty) > 0.0000001
        """,
        {"year": year},
        as_dict=True,
    )

    by_item: dict[str, dict] = {}

    for r in rows:
        code = r.get("item_code")
        if not code:
            continue

        if code not in by_item:
            by_item[code] = {
                "item_code": code,
                "item_name": r.get("item_name") or "",
                "uom": r.get("uom") or "",
                "net_diff": 0.0,
                "warehouses": [],
                "docs_count": int(r.get("docs_count") or 0),
            }

        diff_val = float(r.get("diff_qty") or 0)
        by_item[code]["net_diff"] += diff_val
        by_item[code]["warehouses"].append(
            {"warehouse": r.get("warehouse"), "diff": diff_val}
        )
        by_item[code]["docs_count"] = max(
            by_item[code]["docs_count"], int(r.get("docs_count") or 0)
        )

    items = list(by_item.values())
    items.sort(key=lambda x: abs(float(x.get("net_diff") or 0)), reverse=True)

    return {"year": year, "items": items}


@frappe.whitelist()
def get_item_details(item_code: str, year: int):
    """Drill-down per item: list draft docs and their contribution."""
    _require_role()

    if not item_code:
        frappe.throw(_("Item Code is required"))

    try:
        year = int(year)
    except Exception:
        frappe.throw(_("Invalid year"))

    diff = _diff_expr("sri")

    docs = frappe.db.sql(
        f"""
        SELECT
            sr.name,
            sr.posting_date,
            sr.set_warehouse,
            sri.warehouse,
            SUM({diff}) AS diff_qty
        FROM `tabStock Reconciliation` sr
        INNER JOIN `tabStock Reconciliation Item` sri
            ON sri.parent = sr.name
        WHERE
            sr.docstatus = 0
            AND sr.posting_date IS NOT NULL
            AND YEAR(sr.posting_date) = %(year)s
            AND sri.item_code = %(item_code)s
        GROUP BY sr.name, sri.warehouse
        HAVING ABS(diff_qty) > 0.0000001
        ORDER BY sr.posting_date DESC, sr.name DESC
        """,
        {"year": year, "item_code": item_code},
        as_dict=True,
    )

    return {"year": year, "item_code": item_code, "docs": docs}