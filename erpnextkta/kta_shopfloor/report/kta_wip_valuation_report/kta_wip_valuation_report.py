# Copyright (c) 2026, KTA and Contributors
# For license information, please see license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from erpnextkta.overrides.company_wip_validation import (
    get_validated_wip_consumption_account,
)

OPEN_WIP_THRESHOLD = 0.01
_CONFIRMATION_REMARKS_RE = re.compile(r"KTA Production Confirmation:\s*([^\r\n]+)")


def execute(filters=None):
    """Return read-only GL-exact Work Order WIP valuation report data and summary."""
    filters = frappe._dict(filters or {})
    view_mode = (filters.get("view_mode") or "Tree View").strip()
    is_flat_2d = view_mode == "Flat 2D (Pivot)"

    company = _resolve_company(filters)
    if not company:
        cols = get_flat_2d_columns() if is_flat_2d else get_columns()
        return cols, [], None, None, [], True

    company_currency = (
        frappe.get_cached_value("Company", company, "default_currency") or "TRY"
    )
    as_of_date = filters.get("as_of_date") or today()
    only_open_wip = (
        cint(filters.get("only_open_wip"))
        if filters.get("only_open_wip") is not None
        else 1
    )
    show_consumption_details = (
        cint(filters.get("show_consumption_details"))
        if filters.get("show_consumption_details") is not None
        else 1
    )
    include_classic_manufacture = (
        cint(filters.get("include_classic_manufacture"))
        if filters.get("include_classic_manufacture") is not None
        else 1
    )
    effective_show_details = bool(show_consumption_details) or is_flat_2d

    wip_account = get_validated_wip_consumption_account(company) or ""
    adjustment_account = (
        frappe.db.get_value("Company", company, "stock_adjustment_account") or ""
    )

    raw_rows = _fetch_wip_gl_rows(
        company=company,
        as_of_date=as_of_date,
        wip_account=wip_account,
        adjustment_account=adjustment_account,
        work_order=filters.get("work_order"),
        wo_status=filters.get("wo_status"),
    )

    level_0_rows = _build_level_0_rows(
        raw_rows=raw_rows,
        company_currency=company_currency,
        only_open_wip=only_open_wip,
    )

    classic_by_wo: dict[str, dict] = {}
    if include_classic_manufacture and level_0_rows:
        wo_tuple = tuple(dict.fromkeys(row["work_order"] for row in level_0_rows))
        classic_by_wo = _fetch_classic_manufacture_summary(
            company=company,
            as_of_date=as_of_date,
            work_orders=wo_tuple,
        )
        _apply_classic_manufacture_to_level_0(level_0_rows, classic_by_wo)

    classic_fg_qty_by_wo = {
        wo: flt(info.get("classic_fg_qty")) for wo, info in classic_by_wo.items()
    }

    breakdown_by_wo = {}
    if effective_show_details and level_0_rows:
        work_orders = [row["work_order"] for row in level_0_rows]
        wo_qty_by_wo = {row["work_order"]: flt(row.get("qty")) for row in level_0_rows}
        breakdown_by_wo = _fetch_consumption_breakdown(
            company=company,
            as_of_date=as_of_date,
            work_orders=work_orders,
            include_classic_manufacture=bool(include_classic_manufacture),
            classic_fg_qty_by_wo=classic_fg_qty_by_wo,
            wo_qty_by_wo=wo_qty_by_wo,
        )

    if is_flat_2d:
        columns = get_flat_2d_columns()
        data = _build_flat_2d_rows(
            level_0_rows=level_0_rows,
            company_currency=company_currency,
            breakdown_by_wo=breakdown_by_wo,
            classic_by_wo=classic_by_wo,
        )
    else:
        columns = get_columns(sortable=not bool(show_consumption_details))
        data = _build_report_rows(
            level_0_rows=level_0_rows,
            company_currency=company_currency,
            breakdown_by_wo=breakdown_by_wo,
        )
        if level_0_rows:
            data.append(_build_tree_total_row(level_0_rows, company_currency))

    summary = _build_report_summary(level_0_rows, company_currency)
    return columns, data, None, None, summary, True


def _resolve_company(filters: dict) -> str | None:
    """Resolve company from filters or user/global defaults."""
    return (
        filters.get("company")
        or frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )


def get_columns(sortable: bool = True) -> list[dict]:
    """Return column definitions for KTA WIP Valuation Report."""
    columns = [
        {
            "label": _("Work Order / Operation / Material"),
            "fieldname": "work_order",
            "fieldtype": "Data",
            "width": 240,
        },
        {
            "label": _("Item / Material"),
            "fieldname": "production_item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 145,
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Work Order Status"),
            "fieldname": "wo_status",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Qty To Manufacture"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": _("Produced / Confirmed Qty"),
            "fieldname": "produced_qty",
            "fieldtype": "Float",
            "width": 155,
        },
        {
            "label": _("Required Qty"),
            "fieldname": "required_qty",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": _("Consumed Qty"),
            "fieldname": "consumed_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": _("Remaining Qty"),
            "fieldname": "remaining_qty",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": _("In-WIP Qty"),
            "fieldname": "wip_qty",
            "fieldtype": "Float",
            "width": 125,
        },
        {
            "label": _("UOM"),
            "fieldname": "uom",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": _("Unit Rate"),
            "fieldname": "unit_rate",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": _("Consumed Value"),
            "fieldname": "consumed_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": _("FG Transferred Value"),
            "fieldname": "fg_transferred_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 160,
        },
        {
            "label": _("WIP Return / Adjustment"),
            "fieldname": "wip_adjustment_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 155,
        },
        {
            "label": _("WIP Balance"),
            "fieldname": "wip_balance",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": _("WIP Account (151)"),
            "fieldname": "wip_in_wip_account",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": _("Adjustment Account (710.20)"),
            "fieldname": "wip_in_adjustment_account",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 180,
        },
        {
            "label": _("Last Posting Date"),
            "fieldname": "last_posting_date",
            "fieldtype": "Date",
            "width": 130,
        },
    ]
    return [{**col, "sortable": sortable} for col in columns]


def get_flat_2d_columns() -> list[dict]:
    """Return pivot-ready denormalized column definitions for Flat 2D (Pivot) mode."""
    columns = [
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 115,
        },
        {
            "label": _("Work Order"),
            "fieldname": "work_order",
            "fieldtype": "Link",
            "options": "Work Order",
            "width": 170,
        },
        {
            "label": _("Work Order Status"),
            "fieldname": "wo_status",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("FG Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 145,
        },
        {
            "label": _("FG Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Planned Qty"),
            "fieldname": "planned_qty",
            "fieldtype": "Float",
            "width": 115,
        },
        {
            "label": _("FG Produced / Confirmed Qty"),
            "fieldname": "wo_confirmed_qty",
            "fieldtype": "Float",
            "width": 165,
        },
        {
            "label": _("WO Consumed Value"),
            "fieldname": "wo_consumed_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": _("WO FG / Output Value"),
            "fieldname": "wo_fg_output_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 160,
        },
        {
            "label": _("WO Classic FG / Output Value"),
            "fieldname": "wo_classic_fg_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 185,
        },
        {
            "label": _("WO Scrap Value"),
            "fieldname": "wo_scrap_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": _("WO WIP Balance"),
            "fieldname": "wo_wip_balance",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 145,
        },
        {
            "label": _("Operation"),
            "fieldname": "operation",
            "fieldtype": "Data",
            "width": 165,
        },
        {
            "label": _("Op Sequence"),
            "fieldname": "op_sequence",
            "fieldtype": "Int",
            "width": 105,
        },
        {
            "label": _("Op Confirmed Qty"),
            "fieldname": "op_confirmed_qty",
            "fieldtype": "Float",
            "width": 135,
        },
        {
            "label": _("Op WIP Qty"),
            "fieldname": "op_wip_qty",
            "fieldtype": "Float",
            "width": 125,
        },
        {
            "label": _("Raw Material Code"),
            "fieldname": "raw_material_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150,
        },
        {
            "label": _("Raw Material Name"),
            "fieldname": "raw_material_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Required Qty"),
            "fieldname": "required_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": _("Consumed Qty"),
            "fieldname": "consumed_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": _("Remaining Qty"),
            "fieldname": "remaining_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": _("In-WIP Qty"),
            "fieldname": "wip_qty",
            "fieldtype": "Float",
            "width": 125,
        },
        {
            "label": _("UOM"),
            "fieldname": "stock_uom",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": _("Raw Material Value"),
            "fieldname": "raw_material_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": _("Raw Material WIP Value"),
            "fieldname": "raw_material_wip_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 165,
        },
        {
            "label": _("Consumption Source"),
            "fieldname": "consumption_source",
            "fieldtype": "Data",
            "width": 175,
        },
    ]
    return [{**col, "sortable": True} for col in columns]


def _fetch_se_wip_gl_rows(
    company: str,
    as_of_date: str,
    wip_account: str,
    adjustment_account: str,
    work_order: str | None = None,
    wo_status: str | None = None,
) -> list[dict]:
    """Aggregate GL-exact WIP consumption, FG transfer, and WIP return values from Stock Entries."""
    conditions = [
        "gle.is_cancelled = 0",
        "gle.company = %(company)s",
        "gle.posting_date <= %(as_of_date)s",
        "se.docstatus = 1",
        "IFNULL(se.work_order, '') != ''",
        """(
            se.purpose = 'Material Consumption for Manufacture'
            OR (
                se.purpose = 'Manufacture'
                AND NOT EXISTS (
                    SELECT 1
                    FROM `tabStock Entry Detail` sed_src
                    WHERE sed_src.parent = se.name
                      AND IFNULL(sed_src.s_warehouse, '') != ''
                )
            )
            OR (
                se.purpose = 'Material Receipt'
                AND NOT EXISTS (
                    SELECT 1
                    FROM `tabStock Entry Detail` sed_src
                    WHERE sed_src.parent = se.name
                      AND IFNULL(sed_src.s_warehouse, '') != ''
                )
                AND %(wip_account)s != ''
                AND EXISTS (
                    SELECT 1
                    FROM `tabStock Entry Detail` sed_wip
                    WHERE sed_wip.parent = se.name
                      AND sed_wip.expense_account = %(wip_account)s
                )
            )
        )""",
    ]
    params: dict = {
        "company": company,
        "as_of_date": as_of_date,
        "wip_account": wip_account or "",
        "adj_account": adjustment_account or "",
    }

    if work_order:
        conditions.append("se.work_order = %(work_order)s")
        params["work_order"] = work_order

    if wo_status:
        conditions.append("wo.status = %(wo_status)s")
        params["wo_status"] = wo_status

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            se.work_order,
            wo.production_item,
            COALESCE(NULLIF(wo.item_name, ''), item.item_name, wo.production_item) AS item_name,
            wo.status AS wo_status,
            wo.qty,
            wo.produced_qty,
            MAX(gle.posting_date) AS last_posting_date,
            SUM(
                CASE
                    WHEN se.purpose = 'Material Consumption for Manufacture'
                     AND COALESCE(acc.account_type, '') != 'Stock'
                    THEN gle.debit - gle.credit
                    ELSE 0
                END
            ) AS consumed_value,
            SUM(
                CASE
                    WHEN se.purpose = 'Manufacture'
                     AND COALESCE(acc.account_type, '') != 'Stock'
                     AND (
                         (%(wip_account)s != '' AND gle.account = %(wip_account)s)
                         OR (%(adj_account)s != '' AND gle.account = %(adj_account)s)
                         OR EXISTS (
                             SELECT 1
                             FROM `tabStock Entry Detail` sed_exp
                             WHERE sed_exp.parent = se.name
                               AND sed_exp.expense_account = gle.account
                         )
                     )
                    THEN gle.credit - gle.debit
                    ELSE 0
                END
            ) AS fg_transferred_value,
            SUM(
                CASE
                    WHEN se.purpose = 'Material Receipt'
                     AND COALESCE(acc.account_type, '') != 'Stock'
                    THEN gle.debit - gle.credit
                    ELSE 0
                END
            ) AS wip_adjustment_value,
            SUM(
                CASE
                    WHEN %(wip_account)s != '' AND gle.account = %(wip_account)s
                    THEN gle.debit - gle.credit
                    ELSE 0
                END
            ) AS wip_in_wip_account,
            SUM(
                CASE
                    WHEN %(adj_account)s != ''
                     AND %(adj_account)s != %(wip_account)s
                     AND gle.account = %(adj_account)s
                    THEN gle.debit - gle.credit
                    ELSE 0
                END
            ) AS wip_in_adjustment_account
        FROM `tabGL Entry` gle
        INNER JOIN `tabStock Entry` se
            ON se.name = gle.voucher_no
           AND gle.voucher_type = 'Stock Entry'
        INNER JOIN `tabWork Order` wo
            ON wo.name = se.work_order
        LEFT JOIN `tabItem` item
            ON item.name = wo.production_item
        LEFT JOIN `tabAccount` acc
            ON acc.name = gle.account
        WHERE {where_clause}
        GROUP BY
            se.work_order,
            wo.production_item,
            COALESCE(NULLIF(wo.item_name, ''), item.item_name, wo.production_item),
            wo.status,
            wo.qty,
            wo.produced_qty
        ORDER BY se.work_order ASC
        """,
        params,
        as_dict=True,
    )


def _fetch_je_wip_gl_rows(
    company: str,
    as_of_date: str,
    wip_account: str,
    adjustment_account: str,
    work_order: str | None = None,
    wo_status: str | None = None,
) -> list[dict]:
    """Aggregate Work Order WIP adjustments from submitted Journal Entries."""
    if not frappe.db.has_column("Journal Entry Account", "custom_work_order"):
        return []
    if not (wip_account or adjustment_account):
        return []

    conditions = [
        "je.docstatus = 1",
        "je.company = %(company)s",
        "je.posting_date <= %(as_of_date)s",
        "IFNULL(jea.custom_work_order, '') != ''",
        """(
            (%(wip_account)s != '' AND jea.account = %(wip_account)s)
            OR (
                %(adj_account)s != ''
                AND %(adj_account)s != %(wip_account)s
                AND jea.account = %(adj_account)s
                AND NOT EXISTS (
                    SELECT 1
                    FROM `tabJournal Entry Account` jea_wip
                    WHERE jea_wip.parent = je.name
                      AND jea_wip.custom_work_order = jea.custom_work_order
                      AND jea_wip.account = %(wip_account)s
                )
            )
        )""",
    ]
    params: dict = {
        "company": company,
        "as_of_date": as_of_date,
        "wip_account": wip_account or "",
        "adj_account": adjustment_account or "",
    }

    if work_order:
        conditions.append("jea.custom_work_order = %(work_order)s")
        params["work_order"] = work_order

    if wo_status:
        conditions.append("wo.status = %(wo_status)s")
        params["wo_status"] = wo_status

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            jea.custom_work_order AS work_order,
            wo.production_item,
            COALESCE(NULLIF(wo.item_name, ''), item.item_name, wo.production_item) AS item_name,
            wo.status AS wo_status,
            wo.qty,
            wo.produced_qty,
            MAX(je.posting_date) AS last_posting_date,
            0.0 AS consumed_value,
            0.0 AS fg_transferred_value,
            SUM(jea.debit - jea.credit) AS wip_adjustment_value,
            SUM(
                CASE
                    WHEN %(wip_account)s != '' AND jea.account = %(wip_account)s
                    THEN jea.debit - jea.credit
                    ELSE 0
                END
            ) AS wip_in_wip_account,
            SUM(
                CASE
                    WHEN %(adj_account)s != ''
                     AND %(adj_account)s != %(wip_account)s
                     AND jea.account = %(adj_account)s
                    THEN jea.debit - jea.credit
                    ELSE 0
                END
            ) AS wip_in_adjustment_account
        FROM `tabJournal Entry` je
        INNER JOIN `tabJournal Entry Account` jea
            ON jea.parent = je.name
        INNER JOIN `tabWork Order` wo
            ON wo.name = jea.custom_work_order
        LEFT JOIN `tabItem` item
            ON item.name = wo.production_item
        WHERE {where_clause}
        GROUP BY
            jea.custom_work_order,
            wo.production_item,
            COALESCE(NULLIF(wo.item_name, ''), item.item_name, wo.production_item),
            wo.status,
            wo.qty,
            wo.produced_qty
        ORDER BY jea.custom_work_order ASC
        """,
        params,
        as_dict=True,
    )


def _fetch_wip_gl_rows(
    company: str,
    as_of_date: str,
    wip_account: str,
    adjustment_account: str,
    work_order: str | None = None,
    wo_status: str | None = None,
) -> list[dict]:
    """Merge GL-exact WIP rows from Stock Entries and Journal Entries by Work Order."""
    se_rows = _fetch_se_wip_gl_rows(
        company=company,
        as_of_date=as_of_date,
        wip_account=wip_account,
        adjustment_account=adjustment_account,
        work_order=work_order,
        wo_status=wo_status,
    )
    je_rows = _fetch_je_wip_gl_rows(
        company=company,
        as_of_date=as_of_date,
        wip_account=wip_account,
        adjustment_account=adjustment_account,
        work_order=work_order,
        wo_status=wo_status,
    )

    numeric_fields = (
        "consumed_value",
        "fg_transferred_value",
        "wip_adjustment_value",
        "wip_in_wip_account",
        "wip_in_adjustment_account",
    )
    merged: dict[str, dict] = {}
    for row in (*se_rows, *je_rows):
        wo_name = row["work_order"]
        existing = merged.get(wo_name)
        if not existing:
            merged[wo_name] = {
                **row,
                **{field: flt(row.get(field)) for field in numeric_fields},
            }
            continue

        for field in numeric_fields:
            existing[field] = flt(existing.get(field)) + flt(row.get(field))
        existing["last_posting_date"] = _later_date(
            existing.get("last_posting_date"), row.get("last_posting_date")
        )

    return sorted(merged.values(), key=lambda r: r["work_order"])


def _is_open_wip(row: dict) -> bool:
    """Return True if any WIP or difference balance exceeds the rounding threshold."""
    return (
        abs(flt(row.get("wip_balance"), 2)) > OPEN_WIP_THRESHOLD
        or abs(flt(row.get("wip_in_wip_account"), 2)) > OPEN_WIP_THRESHOLD
        or abs(flt(row.get("wip_in_adjustment_account"), 2)) > OPEN_WIP_THRESHOLD
    )


def _later_date(d1, d2):
    """Return the later of two date values, handling None safely."""
    if not d1:
        return d2
    if not d2:
        return d1
    return d1 if getdate(d1) >= getdate(d2) else d2


def _extract_confirmation_from_remarks(remarks: str | None) -> str | None:
    """Parse confirmation document name from Stock Entry remarks."""
    if not remarks:
        return None
    match = _CONFIRMATION_REMARKS_RE.search(remarks)
    return match.group(1).strip() if match else None


def _build_level_0_rows(
    raw_rows: list[dict],
    company_currency: str,
    only_open_wip: int,
) -> list[dict]:
    """Normalize Level-0 Work Order rows, compute wip_balance, and filter open WIP."""
    rows: list[dict] = []
    for raw in raw_rows:
        wo_name = raw.get("work_order")
        consumed_value = flt(raw.get("consumed_value"), 2)
        fg_transferred_value = flt(raw.get("fg_transferred_value"), 2)
        wip_adjustment_value = flt(raw.get("wip_adjustment_value"), 2)
        wip_balance = flt(
            consumed_value - fg_transferred_value + wip_adjustment_value, 2
        )

        row = {
            "work_order": wo_name,
            "production_item": raw.get("production_item"),
            "item_name": raw.get("item_name"),
            "wo_status": raw.get("wo_status"),
            "qty": flt(raw.get("qty")),
            "produced_qty": flt(raw.get("produced_qty")),
            "required_qty": None,
            "consumed_qty": None,
            "remaining_qty": None,
            "wip_qty": None,
            "uom": "",
            "unit_rate": None,
            "consumed_value": consumed_value,
            "fg_transferred_value": fg_transferred_value,
            "wip_adjustment_value": wip_adjustment_value,
            "wip_balance": wip_balance,
            "wip_in_wip_account": flt(raw.get("wip_in_wip_account"), 2),
            "wip_in_adjustment_account": flt(raw.get("wip_in_adjustment_account"), 2),
            "last_posting_date": raw.get("last_posting_date"),
            "currency": company_currency,
            "indent": 0,
            "tree_node": wo_name,
            "parent_node": "",
            "row_type": "work_order",
            "work_order_ref": wo_name,
        }

        if only_open_wip and not _is_open_wip(row):
            continue

        rows.append(row)

    return rows


def _fetch_classic_manufacture_summary(
    company: str,
    as_of_date: str,
    work_orders: tuple[str, ...],
) -> dict[str, dict]:
    """Fetch classic mixed Manufacture FG qty and raw-material SLE value for hybrid Work Orders."""
    if not work_orders:
        return {}

    params = {
        "company": company,
        "as_of_date": as_of_date,
        "work_orders": work_orders,
    }
    header_rows = frappe.db.sql(
        """
        SELECT
            se.work_order,
            SUM(COALESCE(se.fg_completed_qty, 0)) AS classic_fg_qty,
            MAX(se.posting_date) AS last_posting_date
        FROM `tabStock Entry` se
        WHERE se.docstatus = 1
          AND se.purpose = 'Manufacture'
          AND se.company = %(company)s
          AND se.posting_date <= %(as_of_date)s
          AND se.work_order IN %(work_orders)s
          AND EXISTS (
              SELECT 1
              FROM `tabStock Entry Detail` sed_src
              WHERE sed_src.parent = se.name
                AND IFNULL(sed_src.s_warehouse, '') != ''
          )
        GROUP BY se.work_order
        """,
        params,
        as_dict=True,
    )
    if not header_rows:
        return {}

    rm_rows = frappe.db.sql(
        """
        SELECT
            se.work_order,
            SUM(COALESCE(sle_agg.sle_val, sed.amount)) AS classic_consumed_value
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se
            ON se.name = sed.parent
        LEFT JOIN (
            SELECT
                sle.voucher_detail_no,
                SUM(-sle.stock_value_difference) AS sle_val
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabStock Entry` se_sle
                ON se_sle.name = sle.voucher_no
            WHERE sle.is_cancelled = 0
              AND sle.voucher_type = 'Stock Entry'
              AND sle.company = %(company)s
              AND sle.posting_date <= %(as_of_date)s
              AND se_sle.work_order IN %(work_orders)s
            GROUP BY sle.voucher_detail_no
        ) sle_agg
            ON sle_agg.voucher_detail_no = sed.name
        WHERE se.docstatus = 1
          AND se.purpose = 'Manufacture'
          AND se.company = %(company)s
          AND se.posting_date <= %(as_of_date)s
          AND se.work_order IN %(work_orders)s
          AND IFNULL(sed.s_warehouse, '') != ''
        GROUP BY se.work_order
        """,
        params,
        as_dict=True,
    )
    rm_val_by_wo = {
        row["work_order"]: flt(row.get("classic_consumed_value")) for row in rm_rows
    }

    return {
        row["work_order"]: {
            "classic_fg_qty": flt(row.get("classic_fg_qty")),
            "classic_consumed_value": rm_val_by_wo.get(row["work_order"], 0.0),
            "last_posting_date": row.get("last_posting_date"),
        }
        for row in header_rows
    }


def _apply_classic_manufacture_to_level_0(
    level_0_rows: list[dict],
    classic_by_wo: dict[str, dict],
) -> None:
    """Add classic mixed Manufacture RM/FG value symmetrically to Level-0 rows without altering WIP."""
    for row in level_0_rows:
        info = classic_by_wo.get(row["work_order"])
        if not info:
            continue
        classic_val = flt(info.get("classic_consumed_value"), 2)
        row["consumed_value"] = flt(flt(row.get("consumed_value")) + classic_val, 2)
        row["fg_transferred_value"] = flt(
            flt(row.get("fg_transferred_value")) + classic_val, 2
        )
        row["last_posting_date"] = _later_date(
            row.get("last_posting_date"), info.get("last_posting_date")
        )


def _fetch_consumption_sed_rows(
    company: str,
    as_of_date: str,
    work_orders: tuple[str, ...],
    include_classic_manufacture: bool = False,
) -> list[dict]:
    """Fetch submitted consumption Stock Entry Detail rows joined with aggregated SLE values."""
    has_custom_orig = frappe.db.has_column("Stock Entry Detail", "custom_original_item")
    has_orig = frappe.db.has_column("Stock Entry Detail", "original_item")
    has_custom_conf = frappe.db.has_column("Stock Entry", "custom_confirmation")

    custom_orig_col = (
        "sed.custom_original_item" if has_custom_orig else "'' AS custom_original_item"
    )
    orig_col = "sed.original_item" if has_orig else "'' AS original_item"
    custom_conf_col = (
        "se.custom_confirmation" if has_custom_conf else "'' AS custom_confirmation"
    )
    purpose_condition = (
        "se.purpose IN ('Material Consumption for Manufacture', 'Manufacture')"
        if include_classic_manufacture
        else "se.purpose = 'Material Consumption for Manufacture'"
    )

    return frappe.db.sql(
        f"""
        SELECT
            se.name AS se_name,
            se.purpose,
            se.work_order,
            se.posting_date,
            se.remarks,
            {custom_conf_col},
            sed.item_code,
            {orig_col},
            {custom_orig_col},
            COALESCE(NULLIF(sed.item_name, ''), item.item_name, sed.item_code) AS item_name,
            COALESCE(sle_agg.sle_qty, NULLIF(sed.transfer_qty, 0), sed.qty) AS consumed_qty,
            COALESCE(sle_agg.sle_val, sed.amount) AS consumed_value,
            COALESCE(NULLIF(sed.stock_uom, ''), NULLIF(sed.uom, ''), item.stock_uom, '') AS uom
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se
            ON se.name = sed.parent
        LEFT JOIN `tabItem` item
            ON item.name = sed.item_code
        LEFT JOIN (
            SELECT
                sle.voucher_detail_no,
                SUM(-sle.actual_qty) AS sle_qty,
                SUM(-sle.stock_value_difference) AS sle_val
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabStock Entry` se_sle
                ON se_sle.name = sle.voucher_no
            WHERE sle.is_cancelled = 0
              AND sle.voucher_type = 'Stock Entry'
              AND sle.company = %(company)s
              AND sle.posting_date <= %(as_of_date)s
              AND se_sle.work_order IN %(work_orders)s
            GROUP BY sle.voucher_detail_no
        ) sle_agg
            ON sle_agg.voucher_detail_no = sed.name
        WHERE se.docstatus = 1
          AND {purpose_condition}
          AND se.company = %(company)s
          AND se.posting_date <= %(as_of_date)s
          AND se.work_order IN %(work_orders)s
          AND IFNULL(sed.s_warehouse, '') != ''
        """,
        {
            "company": company,
            "as_of_date": as_of_date,
            "work_orders": work_orders,
        },
        as_dict=True,
    )


def _fetch_wo_operation_order(
    work_orders: tuple[str, ...],
) -> dict[tuple[str, str], int]:
    """Map (work_order, operation) -> idx from Work Order Operation."""
    rows = frappe.get_all(
        "Work Order Operation",
        filters={"parent": ["in", list(work_orders)]},
        fields=["parent", "operation", "idx"],
        order_by="idx asc",
    )
    op_order: dict[tuple[str, str], int] = {}
    for row in rows:
        if row.get("operation"):
            op_order.setdefault((row["parent"], row["operation"]), cint(row.get("idx")))
    return op_order


def _fetch_wo_item_operations(
    work_orders: tuple[str, ...],
) -> dict[tuple[str, str], list[str]]:
    """Map (work_order, item_code) -> ordered distinct operations from Work Order Item."""
    fields = ["parent", "item_code", "operation", "idx"]
    has_custom_orig = frappe.db.has_column("Work Order Item", "custom_original_item")
    if has_custom_orig:
        fields.append("custom_original_item")

    rows = frappe.get_all(
        "Work Order Item",
        filters={"parent": ["in", list(work_orders)]},
        fields=fields,
        order_by="idx asc",
    )
    wo_item_ops: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        op = row.get("operation")
        if not op:
            continue
        for candidate in (row.get("item_code"), row.get("custom_original_item")):
            if not candidate:
                continue
            ops = wo_item_ops.setdefault((row["parent"], candidate), [])
            if op not in ops:
                ops.append(op)
    return wo_item_ops


def _fetch_confirmation_operations(
    work_orders: tuple[str, ...],
) -> tuple[dict[str, str], dict[str, str]]:
    """Map stock_entry -> operation and confirmation name -> operation."""
    confs = frappe.get_all(
        "KTA Production Confirmation",
        filters={"docstatus": 1, "work_order": ["in", list(work_orders)]},
        fields=["name", "operation", "stock_entry"],
    )
    se_to_op: dict[str, str] = {}
    conf_to_op: dict[str, str] = {}
    for conf in confs:
        op = conf.get("operation")
        if not op:
            continue
        if conf.get("name"):
            conf_to_op[conf["name"]] = op
        if conf.get("stock_entry"):
            se_to_op[conf["stock_entry"]] = op
    return se_to_op, conf_to_op


def _resolve_row_operation(
    row: dict,
    se_to_op: dict[str, str],
    conf_to_op: dict[str, str],
    wo_item_ops: dict[tuple[str, str], list[str]],
) -> str:
    """Resolve the operation for a consumed raw-material Stock Entry Detail row."""
    se_op = se_to_op.get(row.get("se_name") or "")
    if not se_op and row.get("custom_confirmation"):
        se_op = conf_to_op.get(row["custom_confirmation"])
    if not se_op:
        conf_name = _extract_confirmation_from_remarks(row.get("remarks"))
        if conf_name:
            se_op = conf_to_op.get(conf_name)

    wo_name = row["work_order"]
    for candidate in (
        row.get("custom_original_item"),
        row.get("original_item"),
        row.get("item_code"),
    ):
        if not candidate:
            continue
        ops = wo_item_ops.get((wo_name, candidate))
        if ops:
            return se_op if (se_op and se_op in ops) else ops[0]

    return se_op or _("Unassigned Operation")


def _fetch_operation_confirmed_qty(
    work_orders: tuple[str, ...],
    as_of_date: str,
) -> dict[tuple[str, str], dict]:
    """Aggregate submitted confirmation yield_qty and latest date per (work_order, operation)."""
    if not work_orders:
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            work_order,
            operation,
            SUM(COALESCE(yield_qty, 0)) AS confirmed_qty,
            MAX(posting_date) AS last_posting_date
        FROM `tabKTA Production Confirmation`
        WHERE docstatus = 1
          AND work_order IN %(work_orders)s
          AND posting_date <= %(as_of_date)s
          AND IFNULL(operation, '') != ''
        GROUP BY work_order, operation
        """,
        {"work_orders": work_orders, "as_of_date": as_of_date},
        as_dict=True,
    )
    return {
        (row["work_order"], row["operation"]): {
            "confirmed_qty": flt(row.get("confirmed_qty")),
            "last_posting_date": row.get("last_posting_date"),
        }
        for row in rows
    }


def _fetch_wo_required_items(work_orders: tuple[str, ...]) -> list[dict]:
    """Fetch and aggregate Work Order Item required quantities per (work_order, operation, item_code)."""
    if not work_orders:
        return []

    fields = [
        "parent",
        "operation",
        "item_code",
        "item_name",
        "required_qty",
        "stock_uom",
        "idx",
    ]
    has_custom_orig = frappe.db.has_column("Work Order Item", "custom_original_item")
    has_orig = frappe.db.has_column("Work Order Item", "original_item")
    if has_custom_orig:
        fields.append("custom_original_item")
    if has_orig:
        fields.append("original_item")

    rows = frappe.get_all(
        "Work Order Item",
        filters={"parent": ["in", list(work_orders)]},
        fields=fields,
        order_by="idx asc",
    )

    aggregated: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        wo_name = row.get("parent")
        item_code = row.get("item_code")
        if not wo_name or not item_code:
            continue
        op_name = (row.get("operation") or "").strip()
        key = (wo_name, op_name, item_code)
        bucket = aggregated.get(key)
        if not bucket:
            bucket = {
                "work_order": wo_name,
                "operation": op_name,
                "item_code": item_code,
                "custom_original_item": (row.get("custom_original_item") or "").strip(),
                "original_item": (row.get("original_item") or "").strip(),
                "item_name": row.get("item_name") or item_code,
                "required_qty": 0.0,
                "stock_uom": row.get("stock_uom") or "",
                "idx": cint(row.get("idx")) or 999999,
            }
            aggregated[key] = bucket

        bucket["required_qty"] += flt(row.get("required_qty"))
        if not bucket["custom_original_item"] and row.get("custom_original_item"):
            bucket["custom_original_item"] = row["custom_original_item"].strip()
        if not bucket["original_item"] and row.get("original_item"):
            bucket["original_item"] = row["original_item"].strip()

    return list(aggregated.values())


def _find_matching_consumed_material(
    req: dict,
    mat_agg: dict[tuple[str, str, str, str], dict],
) -> dict | None:
    """Match a Work Order Item requirement to an aggregated consumed material entry, including substitutes."""
    wo_name = req["work_order"]
    req_op = req["operation"]
    req_candidates = [
        c
        for c in (
            req.get("item_code"),
            req.get("custom_original_item"),
            req.get("original_item"),
        )
        if c
    ]

    def _matches_op(entry: dict) -> bool:
        return True if not req_op else entry["operation"] == req_op

    # 1. Match consumed entry by item_code against req item_code / original_item
    for candidate in req_candidates:
        for entry in mat_agg.values():
            if (
                entry["work_order"] == wo_name
                and _matches_op(entry)
                and entry["item_code"] == candidate
            ):
                return entry

    # 2. Match consumed substitute entry whose orig_candidates overlap req_candidates
    req_candidate_set = set(req_candidates)
    for entry in mat_agg.values():
        if (
            entry["work_order"] == wo_name
            and _matches_op(entry)
            and (entry.get("orig_candidates") or set()) & req_candidate_set
        ):
            return entry

    return None


def _format_consumption_source(sources: set[str], consumed_qty: float) -> str:
    """Format a translated Title Case consumption source label."""
    if not sources and flt(consumed_qty) == 0.0:
        return _("BOM Only (Unconsumed)")
    if sources == {"Shopfloor Confirmation"}:
        return _("Shopfloor Confirmation")
    if sources == {"Classic Manufacture"}:
        return _("Classic Manufacture")
    if len(sources) > 1:
        return _("Shopfloor + Classic")
    if sources:
        return _(next(iter(sources)))
    return _("BOM Only (Unconsumed)")


def _fetch_fg_produced_qty_as_of(
    company: str,
    as_of_date: str,
    work_orders: tuple[str, ...],
    include_classic_manufacture: bool = False,
) -> dict[str, float]:
    """Return finished-goods qty transferred to warehouse as of date per Work Order."""
    if not work_orders:
        return {}

    classic_filter = ""
    if not include_classic_manufacture:
        classic_filter = """
            AND NOT EXISTS (
                SELECT 1
                FROM `tabStock Entry Detail` s
                WHERE s.parent = se.name
                  AND COALESCE(s.s_warehouse, '') != ''
            )
        """

    rows = frappe.db.sql(
        f"""
        SELECT
            se.work_order,
            SUM(COALESCE(sed.transfer_qty, 0)) AS fg_qty
        FROM `tabStock Entry` se
        INNER JOIN `tabStock Entry Detail` sed
            ON sed.parent = se.name
        WHERE se.docstatus = 1
          AND se.company = %(company)s
          AND se.posting_date <= %(as_of_date)s
          AND se.purpose = 'Manufacture'
          AND se.work_order IN %(work_orders)s
          AND sed.is_finished_item = 1
          AND COALESCE(sed.t_warehouse, '') != ''
          {classic_filter}
        GROUP BY se.work_order
        """,
        {
            "company": company,
            "as_of_date": as_of_date,
            "work_orders": work_orders,
        },
        as_dict=True,
    )
    return {row["work_order"]: flt(row.get("fg_qty")) for row in rows}


def _fetch_consumption_breakdown(
    company: str,
    as_of_date: str,
    work_orders: list[str],
    include_classic_manufacture: bool = False,
    classic_fg_qty_by_wo: dict[str, float] | None = None,
    wo_qty_by_wo: dict[str, float] | None = None,
) -> dict[str, list[dict]]:
    """Fetch and group SLE-exact consumption, BOM requirements, and confirmed qty by WO -> Op -> Material."""
    if not work_orders:
        return {}

    wo_tuple = tuple(dict.fromkeys(work_orders))
    sed_rows = _fetch_consumption_sed_rows(
        company,
        as_of_date,
        wo_tuple,
        include_classic_manufacture=include_classic_manufacture,
    )
    op_confirmed = _fetch_operation_confirmed_qty(wo_tuple, as_of_date)
    req_items = _fetch_wo_required_items(wo_tuple)
    if not sed_rows and not op_confirmed and not req_items:
        return {}

    fg_qty_by_wo = _fetch_fg_produced_qty_as_of(
        company,
        as_of_date,
        wo_tuple,
        include_classic_manufacture=include_classic_manufacture,
    )
    op_order = _fetch_wo_operation_order(wo_tuple)
    wo_item_ops = _fetch_wo_item_operations(wo_tuple)
    se_to_op, conf_to_op = _fetch_confirmation_operations(wo_tuple)
    unassigned_label = _("Unassigned Operation")

    mat_agg: dict[tuple[str, str, str, str], dict] = {}
    for row in sed_rows:
        operation = _resolve_row_operation(row, se_to_op, conf_to_op, wo_item_ops)
        key = (row["work_order"], operation, row["item_code"], row.get("uom") or "")
        entry = mat_agg.get(key)
        if not entry:
            entry = {
                "work_order": row["work_order"],
                "operation": operation,
                "item_code": row["item_code"],
                "item_name": row.get("item_name") or row["item_code"],
                "uom": row.get("uom") or "",
                "raw_consumed_qty": 0.0,
                "raw_consumed_value": 0.0,
                "required_qty": 0.0,
                "bom_idx": 999999,
                "sources": set(),
                "orig_candidates": set(),
                "last_posting_date": None,
            }
            mat_agg[key] = entry

        entry["raw_consumed_qty"] += flt(row.get("consumed_qty"))
        entry["raw_consumed_value"] += flt(row.get("consumed_value"))
        if row.get("purpose") == "Manufacture":
            entry["sources"].add("Classic Manufacture")
        else:
            entry["sources"].add("Shopfloor Confirmation")
        for orig in (row.get("custom_original_item"), row.get("original_item")):
            if orig:
                entry["orig_candidates"].add(orig)
        entry["last_posting_date"] = _later_date(
            entry["last_posting_date"], row.get("posting_date")
        )

    for req in req_items:
        matched = _find_matching_consumed_material(req, mat_agg)
        if matched:
            matched["required_qty"] += flt(req.get("required_qty"))
            matched["bom_idx"] = min(matched["bom_idx"], cint(req.get("idx")) or 999999)
            continue

        op_name = req["operation"] or unassigned_label
        key = (
            req["work_order"],
            op_name,
            req["item_code"],
            req.get("stock_uom") or "",
        )
        entry = mat_agg.get(key)
        if not entry:
            entry = {
                "work_order": req["work_order"],
                "operation": op_name,
                "item_code": req["item_code"],
                "item_name": req.get("item_name") or req["item_code"],
                "uom": req.get("stock_uom") or "",
                "raw_consumed_qty": 0.0,
                "raw_consumed_value": 0.0,
                "required_qty": 0.0,
                "bom_idx": cint(req.get("idx")) or 999999,
                "sources": set(),
                "orig_candidates": set(),
                "last_posting_date": None,
            }
            mat_agg[key] = entry
        entry["required_qty"] += flt(req.get("required_qty"))
        entry["bom_idx"] = min(entry["bom_idx"], cint(req.get("idx")) or 999999)

    ops_by_wo: dict[str, dict[str, dict]] = {}
    wo_qty_by_wo = wo_qty_by_wo or {}
    for entry in mat_agg.values():
        wo_name = entry["work_order"]
        op_name = entry["operation"]
        qty = flt(entry["raw_consumed_qty"])
        req_qty = flt(entry["required_qty"])
        rem_qty = flt(req_qty - qty)
        val = flt(entry["raw_consumed_value"], 2)

        wo_qty = flt(wo_qty_by_wo.get(wo_name))
        fg_qty = flt(fg_qty_by_wo.get(wo_name))
        if qty <= 0:
            wip_qty = 0.0
            wip_value = 0.0
        else:
            if req_qty > 0 and wo_qty > 0:
                fg_absorbed_qty = fg_qty * (req_qty / wo_qty)
            elif wo_qty > 0:
                fg_absorbed_qty = qty * min(fg_qty / wo_qty, 1.0)
            else:
                fg_absorbed_qty = 0.0
            wip_qty = max(0.0, flt(qty - fg_absorbed_qty, 6))
            wip_value = flt(entry["raw_consumed_value"] * (wip_qty / qty), 2)

        material_data = {
            "item_code": entry["item_code"],
            "item_name": entry["item_name"],
            "uom": entry["uom"],
            "required_qty": req_qty,
            "consumed_qty": qty,
            "remaining_qty": rem_qty,
            "wip_qty": wip_qty,
            "wip_value": wip_value,
            "consumed_value": val,
            "unit_rate": flt(val / qty, 4) if qty else 0.0,
            "consumption_source": _format_consumption_source(entry["sources"], qty),
            "bom_idx": entry["bom_idx"],
            "last_posting_date": entry["last_posting_date"],
        }

        wo_ops = ops_by_wo.setdefault(wo_name, {})
        op_bucket = wo_ops.setdefault(
            op_name,
            {
                "operation": op_name,
                "op_sequence": op_order.get((wo_name, op_name)),
                "raw_consumed_value": 0.0,
                "last_posting_date": None,
                "materials": [],
            },
        )
        op_bucket["raw_consumed_value"] += entry["raw_consumed_value"]
        op_bucket["last_posting_date"] = _later_date(
            op_bucket["last_posting_date"], entry["last_posting_date"]
        )
        op_bucket["materials"].append(material_data)

    for (wo_name, op_name), conf_info in op_confirmed.items():
        wo_ops = ops_by_wo.setdefault(wo_name, {})
        if op_name not in wo_ops:
            wo_ops[op_name] = {
                "operation": op_name,
                "op_sequence": op_order.get((wo_name, op_name)),
                "raw_consumed_value": 0.0,
                "last_posting_date": conf_info.get("last_posting_date"),
                "materials": [],
            }

    classic_fg_qty_by_wo = classic_fg_qty_by_wo or {}
    breakdown: dict[str, list[dict]] = {}
    for wo_name, wo_ops in ops_by_wo.items():
        classic_qty = (
            flt(classic_fg_qty_by_wo.get(wo_name, 0.0))
            if include_classic_manufacture
            else 0.0
        )
        fg_qty = flt(fg_qty_by_wo.get(wo_name))
        for bucket in wo_ops.values():
            op_name = bucket["operation"]
            if op_name == unassigned_label:
                bucket["confirmed_qty"] = None
                bucket["wip_qty"] = None
            else:
                conf_info = op_confirmed.get((wo_name, op_name))
                shopfloor_confirmed = (
                    flt(conf_info.get("confirmed_qty")) if conf_info else 0.0
                )
                if conf_info:
                    bucket["last_posting_date"] = _later_date(
                        bucket["last_posting_date"], conf_info.get("last_posting_date")
                    )
                bucket["confirmed_qty"] = flt(shopfloor_confirmed + classic_qty)
                bucket["wip_qty"] = max(0.0, flt(bucket["confirmed_qty"] - fg_qty, 6))
            bucket["wip_value"] = flt(
                sum(flt(m.get("wip_value")) for m in bucket["materials"]), 2
            )

        sorted_ops = sorted(
            wo_ops.values(),
            key=lambda bucket: (
                1 if bucket["operation"] == unassigned_label else 0,
                op_order.get((wo_name, bucket["operation"]), 999999),
                bucket["operation"],
            ),
        )
        for bucket in sorted_ops:
            bucket["consumed_value"] = flt(bucket["raw_consumed_value"], 2)
            bucket["materials"].sort(
                key=lambda m: (m.get("bom_idx", 999999), m["item_code"])
            )
        breakdown[wo_name] = sorted_ops

    return breakdown


def _make_operation_row(wo_name: str, op_entry: dict, company_currency: str) -> dict:
    """Build a Level-1 Operation row dict with tree metadata."""
    op_name = op_entry["operation"]
    return {
        "work_order": op_name,
        "production_item": "",
        "item_name": "",
        "wo_status": "",
        "qty": None,
        "produced_qty": op_entry.get("confirmed_qty"),
        "required_qty": None,
        "consumed_qty": None,
        "remaining_qty": None,
        "wip_qty": op_entry.get("wip_qty"),
        "uom": "",
        "unit_rate": None,
        "consumed_value": flt(op_entry.get("consumed_value"), 2),
        "fg_transferred_value": None,
        "wip_adjustment_value": None,
        "wip_balance": flt(op_entry.get("wip_value"), 2),
        "wip_in_wip_account": None,
        "wip_in_adjustment_account": None,
        "last_posting_date": op_entry.get("last_posting_date"),
        "currency": company_currency,
        "indent": 1,
        "tree_node": f"{wo_name}::{op_name}",
        "parent_node": wo_name,
        "row_type": "operation",
        "work_order_ref": wo_name,
        "operation": op_name,
    }


def _make_material_row(
    wo_name: str,
    op_name: str,
    mat_entry: dict,
    company_currency: str,
) -> dict:
    """Build a Level-2 Raw Material row dict with tree metadata."""
    item_code = mat_entry["item_code"]
    uom = mat_entry.get("uom") or ""
    return {
        "work_order": item_code,
        "production_item": item_code,
        "item_name": mat_entry.get("item_name") or item_code,
        "wo_status": "",
        "qty": None,
        "produced_qty": None,
        "required_qty": flt(mat_entry.get("required_qty")),
        "consumed_qty": flt(mat_entry.get("consumed_qty")),
        "remaining_qty": flt(mat_entry.get("remaining_qty")),
        "wip_qty": flt(mat_entry.get("wip_qty")),
        "uom": uom,
        "unit_rate": flt(mat_entry.get("unit_rate"), 4),
        "consumed_value": flt(mat_entry.get("consumed_value"), 2),
        "fg_transferred_value": None,
        "wip_adjustment_value": None,
        "wip_balance": flt(mat_entry.get("wip_value"), 2),
        "wip_in_wip_account": None,
        "wip_in_adjustment_account": None,
        "last_posting_date": mat_entry.get("last_posting_date"),
        "currency": company_currency,
        "indent": 2,
        "tree_node": f"{wo_name}::{op_name}::{item_code}::{uom}",
        "parent_node": f"{wo_name}::{op_name}",
        "row_type": "material",
        "work_order_ref": wo_name,
        "operation": op_name,
        "material_item": item_code,
    }


def _build_flat_2d_row_base(
    wo_row: dict,
    company_currency: str,
    classic_fg_value: float,
) -> dict:
    """Build shared Work Order level fields for a Flat 2D (Pivot) row."""
    return {
        "posting_date": wo_row.get("last_posting_date"),
        "work_order": wo_row["work_order"],
        "wo_status": wo_row.get("wo_status") or "",
        "item_code": wo_row.get("production_item") or "",
        "item_name": wo_row.get("item_name") or "",
        "planned_qty": flt(wo_row.get("qty")),
        "wo_confirmed_qty": flt(wo_row.get("produced_qty")),
        "wo_consumed_value": flt(wo_row.get("consumed_value"), 2),
        "wo_fg_output_value": flt(wo_row.get("fg_transferred_value"), 2),
        "wo_classic_fg_value": flt(classic_fg_value, 2),
        "wo_scrap_value": 0.0,
        "wo_wip_balance": flt(wo_row.get("wip_balance"), 2),
        "currency": company_currency,
    }


def _build_flat_2d_rows(
    level_0_rows: list[dict],
    company_currency: str,
    breakdown_by_wo: dict[str, list[dict]] | None = None,
    classic_by_wo: dict[str, dict] | None = None,
) -> list[dict]:
    """Build denormalized 2D pivot rows without tree metadata keys."""
    breakdown_by_wo = breakdown_by_wo or {}
    classic_by_wo = classic_by_wo or {}
    rows: list[dict] = []

    for wo_row in level_0_rows:
        wo_name = wo_row["work_order"]
        classic_val = flt(
            classic_by_wo.get(wo_name, {}).get("classic_consumed_value"), 2
        )
        wo_base = _build_flat_2d_row_base(wo_row, company_currency, classic_val)
        ops = breakdown_by_wo.get(wo_name, [])

        if not ops:
            rows.append(
                {
                    **wo_base,
                    "operation": "",
                    "op_sequence": None,
                    "op_confirmed_qty": None,
                    "op_wip_qty": None,
                    "raw_material_code": "",
                    "raw_material_name": "",
                    "required_qty": 0.0,
                    "consumed_qty": 0.0,
                    "remaining_qty": 0.0,
                    "wip_qty": 0.0,
                    "stock_uom": "",
                    "raw_material_value": 0.0,
                    "raw_material_wip_value": 0.0,
                    "consumption_source": "",
                }
            )
            continue

        for op_entry in ops:
            op_base = {
                "operation": op_entry["operation"],
                "op_sequence": op_entry.get("op_sequence"),
                "op_confirmed_qty": op_entry.get("confirmed_qty"),
                "op_wip_qty": op_entry.get("wip_qty"),
            }
            materials = op_entry.get("materials") or []
            if not materials:
                rows.append(
                    {
                        **wo_base,
                        "posting_date": op_entry.get("last_posting_date")
                        or wo_base["posting_date"],
                        **op_base,
                        "raw_material_code": "",
                        "raw_material_name": "",
                        "required_qty": 0.0,
                        "consumed_qty": 0.0,
                        "remaining_qty": 0.0,
                        "wip_qty": 0.0,
                        "stock_uom": "",
                        "raw_material_value": 0.0,
                        "raw_material_wip_value": 0.0,
                        "consumption_source": "",
                    }
                )
                continue

            for mat_entry in materials:
                rows.append(
                    {
                        **wo_base,
                        "posting_date": mat_entry.get("last_posting_date")
                        or op_entry.get("last_posting_date")
                        or wo_base["posting_date"],
                        **op_base,
                        "raw_material_code": mat_entry["item_code"],
                        "raw_material_name": mat_entry.get("item_name")
                        or mat_entry["item_code"],
                        "required_qty": flt(mat_entry.get("required_qty")),
                        "consumed_qty": flt(mat_entry.get("consumed_qty")),
                        "remaining_qty": flt(mat_entry.get("remaining_qty")),
                        "wip_qty": flt(mat_entry.get("wip_qty")),
                        "stock_uom": mat_entry.get("uom") or "",
                        "raw_material_value": flt(mat_entry.get("consumed_value"), 2),
                        "raw_material_wip_value": flt(mat_entry.get("wip_value"), 2),
                        "consumption_source": mat_entry.get("consumption_source") or "",
                    }
                )

    return rows


def _build_tree_total_row(
    level_0_rows: list[dict],
    company_currency: str,
) -> dict:
    """Build a single Total row summing strictly Level-0 Work Order rows."""
    return {
        "work_order": _("Total"),
        "production_item": "",
        "item_name": "",
        "wo_status": "",
        "qty": flt(sum(flt(r.get("qty")) for r in level_0_rows), 6),
        "produced_qty": flt(sum(flt(r.get("produced_qty")) for r in level_0_rows), 6),
        "required_qty": None,
        "consumed_qty": None,
        "remaining_qty": None,
        "wip_qty": None,
        "uom": "",
        "unit_rate": None,
        "consumed_value": flt(
            sum(flt(r.get("consumed_value")) for r in level_0_rows), 2
        ),
        "fg_transferred_value": flt(
            sum(flt(r.get("fg_transferred_value")) for r in level_0_rows), 2
        ),
        "wip_adjustment_value": flt(
            sum(flt(r.get("wip_adjustment_value")) for r in level_0_rows), 2
        ),
        "wip_balance": flt(sum(flt(r.get("wip_balance")) for r in level_0_rows), 2),
        "wip_in_wip_account": flt(
            sum(flt(r.get("wip_in_wip_account")) for r in level_0_rows), 2
        ),
        "wip_in_adjustment_account": flt(
            sum(flt(r.get("wip_in_adjustment_account")) for r in level_0_rows), 2
        ),
        "last_posting_date": None,
        "currency": company_currency,
        "indent": 0,
        "tree_node": _("Total"),
        "parent_node": "",
        "row_type": "total",
    }


def _build_report_rows(
    level_0_rows: list[dict],
    company_currency: str,
    breakdown_by_wo: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Attach Level-1 operation and Level-2 material child rows to surviving Level-0 rows."""
    breakdown_by_wo = breakdown_by_wo or {}
    rows: list[dict] = []
    for wo_row in level_0_rows:
        rows.append(wo_row)
        wo_name = wo_row["work_order"]
        for op_entry in breakdown_by_wo.get(wo_name, []):
            rows.append(_make_operation_row(wo_name, op_entry, company_currency))
            op_name = op_entry["operation"]
            for mat_entry in op_entry.get("materials", []):
                rows.append(
                    _make_material_row(wo_name, op_name, mat_entry, company_currency)
                )
    return rows


def _build_report_summary(
    level_0_rows: list[dict], company_currency: str
) -> list[dict]:
    """Build summary KPI cards strictly from Level-0 Work Order rows."""
    level_0_rows = [d for d in level_0_rows if cint(d.get("indent", 0)) == 0]
    total_open_wip = flt(sum(flt(d.get("wip_balance")) for d in level_0_rows), 2)
    total_wip_account = flt(
        sum(flt(d.get("wip_in_wip_account")) for d in level_0_rows), 2
    )
    total_adjustment_account = flt(
        sum(flt(d.get("wip_in_adjustment_account")) for d in level_0_rows), 2
    )

    stopped_open_rows = [
        d
        for d in level_0_rows
        if d.get("wo_status") == "Stopped"
        and abs(flt(d.get("wip_balance"), 2)) > OPEN_WIP_THRESHOLD
    ]
    stopped_count = len(stopped_open_rows)
    stopped_value = flt(sum(flt(d.get("wip_balance")) for d in stopped_open_rows), 2)

    return [
        {
            "value": total_open_wip,
            "label": _("Total Open WIP"),
            "datatype": "Currency",
            "currency": company_currency,
            "indicator": "Blue"
            if abs(total_open_wip) > OPEN_WIP_THRESHOLD
            else "Green",
        },
        {
            "value": total_wip_account,
            "label": _("WIP Account (151)"),
            "datatype": "Currency",
            "currency": company_currency,
            "indicator": "Blue"
            if abs(total_wip_account) > OPEN_WIP_THRESHOLD
            else "Green",
        },
        {
            "value": total_adjustment_account,
            "label": _("Adjustment Account (710.20)"),
            "datatype": "Currency",
            "currency": company_currency,
            "indicator": "Orange"
            if abs(total_adjustment_account) > OPEN_WIP_THRESHOLD
            else "Grey",
        },
        {
            "value": stopped_count,
            "label": _("Stopped WOs With Open WIP"),
            "datatype": "Int",
            "indicator": "Red" if stopped_count > 0 else "Green",
        },
        {
            "value": stopped_value,
            "label": _("Stopped WOs WIP Value"),
            "datatype": "Currency",
            "currency": company_currency,
            "indicator": "Red" if abs(stopped_value) > OPEN_WIP_THRESHOLD else "Green",
        },
    ]


def _build_flat_2d_xlsx_payload(
    filters=None,
) -> tuple[list[list], list[int]]:
    """Build pivot-ready 2D XLSX matrix (headers + rows, no Total row) and column widths."""
    parsed = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    flat_filters = dict(parsed)
    flat_filters["view_mode"] = "Flat 2D (Pivot)"

    columns, rows, *_ = execute(flat_filters)
    headers = [col.get("label") or col.get("fieldname") for col in columns]
    fieldnames = [col.get("fieldname") for col in columns]
    column_widths = [max(12, cint(col.get("width", 120)) // 7) for col in columns]

    data_rows = []
    for row in rows:
        data_rows.append(
            [
                "" if row.get(fieldname) is None else row.get(fieldname)
                for fieldname in fieldnames
            ]
        )

    return [headers, *data_rows], column_widths


@frappe.whitelist()
def export_flat_2d_excel(filters=None):
    """Download pivot-ready Flat 2D (Pivot) XLSX export for KTA WIP Valuation Report."""
    if not frappe.get_doc("Report", "KTA WIP Valuation Report").is_permitted():
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    from frappe.desk.utils import provide_binary_file
    from frappe.utils.xlsxutils import make_xlsx

    xlsx_data, column_widths = _build_flat_2d_xlsx_payload(filters)
    xlsx_file = make_xlsx(
        xlsx_data,
        "KTA WIP Valuation 2D",
        column_widths=column_widths,
    )
    provide_binary_file(
        f"KTA WIP Valuation 2D - {today()}",
        "xlsx",
        xlsx_file.getvalue(),
    )
