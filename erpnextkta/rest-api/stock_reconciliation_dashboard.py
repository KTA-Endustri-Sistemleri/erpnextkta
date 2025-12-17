# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

from frappe.utils import getdate

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


def _parse_date(d: str | None) -> str | None:
    """Validate & normalize date string to YYYY-MM-DD (or return None)."""
    if not d:
        return None
    try:
        return str(getdate(d))
    except Exception:
        frappe.throw(_("Invalid date: {0}").format(d))


def _build_date_filter(year: int, from_date: str | None, to_date: str | None) -> tuple[str, dict]:
    """
    Build SQL WHERE fragment for posting_date filter.

    Rule:
    - If from_date/to_date provided => use BETWEEN (inclusive).
    - Else => filter by YEAR(posting_date) = year.
    """
    params: dict = {"year": year}

    fd = _parse_date(from_date)
    td = _parse_date(to_date)

    if fd and td:
        if fd > td:
            frappe.throw(_("Date From cannot be after Date To"))
        params.update({"from_date": fd, "to_date": td})
        return "sr.posting_date BETWEEN %(from_date)s AND %(to_date)s", params

    if fd and not td:
        params.update({"from_date": fd})
        return "sr.posting_date >= %(from_date)s", params

    if td and not fd:
        params.update({"to_date": td})
        return "sr.posting_date <= %(to_date)s", params

    # fallback: year filter
    return "YEAR(sr.posting_date) = %(year)s", params


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
def get_dashboard(year: int, from_date: str | None = None, to_date: str | None = None):
    """
    Aggregate Stock Reconciliation impact by item and warehouse for a given time window.

    - Includes BOTH Draft (docstatus=0) and Submitted (docstatus=1)
    - Excludes Cancelled (docstatus=2) implicitly
    - Returns progress meta: draft/submitted counts and percentages
    """
    _require_role()

    try:
        year = int(year)
    except Exception:
        frappe.throw(_("Invalid year"))

    diff = _diff_expr("sri")
    date_clause, params = _build_date_filter(year, from_date, to_date)

    # 1) Progress counts (docs in window)
    counts = frappe.db.sql(
        f"""
        SELECT
            SUM(CASE WHEN sr.docstatus = 0 THEN 1 ELSE 0 END) AS draft_count,
            SUM(CASE WHEN sr.docstatus = 1 THEN 1 ELSE 0 END) AS submitted_count
        FROM `tabStock Reconciliation` sr
        WHERE
            sr.posting_date IS NOT NULL
            AND sr.docstatus IN (0, 1)
            AND {date_clause}
        """,
        params,
        as_dict=True,
    )

    draft_count = int((counts and counts[0].get("draft_count")) or 0)
    submitted_count = int((counts and counts[0].get("submitted_count")) or 0)
    total = draft_count + submitted_count

    progress_pct = round((submitted_count / total) * 100, 2) if total else 0.0
    open_pct = round((draft_count / total) * 100, 2) if total else 0.0

    # 2) Item x Warehouse aggregation (impact)
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
            sr.posting_date IS NOT NULL
            AND sr.docstatus IN (0, 1)
            AND {date_clause}
        GROUP BY sri.item_code, sri.warehouse
        HAVING ABS(diff_qty) > 0.0000001
        """,
        params,
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

        # Keep maximum docs_count seen across grouped rows (cheap + consistent with your UI expectation)
        by_item[code]["docs_count"] = max(
            by_item[code]["docs_count"], int(r.get("docs_count") or 0)
        )

    items = list(by_item.values())
    items.sort(key=lambda x: abs(float(x.get("net_diff") or 0)), reverse=True)

    return {
        "year": year,
        "from_date": _parse_date(from_date),
        "to_date": _parse_date(to_date),
        "items": items,
        "meta": {
            "counts": {"draft": draft_count, "submitted": submitted_count},
            "progress_pct": progress_pct,  # submitted %
            "open_pct": open_pct,          # draft %
        },
    }


@frappe.whitelist()
def get_item_details(item_code: str, year: int, from_date: str | None = None, to_date: str | None = None):
    """
    Drill-down per item: list docs (Draft+Submitted) and their contribution.

    Returns docstatus for UI "Status" column.
    """
    _require_role()

    if not item_code:
        frappe.throw(_("Item Code is required"))

    try:
        year = int(year)
    except Exception:
        frappe.throw(_("Invalid year"))

    diff = _diff_expr("sri")
    date_clause, params = _build_date_filter(year, from_date, to_date)
    params.update({"item_code": item_code})

    docs = frappe.db.sql(
        f"""
        SELECT
            sr.name,
            sr.posting_date,
            sr.docstatus,
            sr.set_warehouse,
            sri.warehouse,
            SUM({diff}) AS diff_qty
        FROM `tabStock Reconciliation` sr
        INNER JOIN `tabStock Reconciliation Item` sri
            ON sri.parent = sr.name
        WHERE
            sr.posting_date IS NOT NULL
            AND sr.docstatus IN (0, 1)
            AND {date_clause}
            AND sri.item_code = %(item_code)s
        GROUP BY sr.name, sr.docstatus, sri.warehouse
        HAVING ABS(diff_qty) > 0.0000001
        ORDER BY sr.posting_date DESC, sr.name DESC
        """,
        params,
        as_dict=True,
    )

    return {
        "year": year,
        "from_date": _parse_date(from_date),
        "to_date": _parse_date(to_date),
        "item_code": item_code,
        "docs": docs,
    }