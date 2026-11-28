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
    """Return read-only GL-exact Work Order WIP valuation tree report data and summary."""
    filters = frappe._dict(filters or {})
    company = _resolve_company(filters)
    if not company:
        return get_columns(), [], None, None, []

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

    breakdown_by_wo = {}
    if show_consumption_details and level_0_rows:
        work_orders = [row["work_order"] for row in level_0_rows]
        breakdown_by_wo = _fetch_consumption_breakdown(
            company=company,
            as_of_date=as_of_date,
            work_orders=work_orders,
        )

    data = _build_report_rows(
        level_0_rows=level_0_rows,
        company_currency=company_currency,
        breakdown_by_wo=breakdown_by_wo,
    )
    summary = _build_report_summary(data, company_currency)
    return (
        get_columns(sortable=not bool(show_consumption_details)),
        data,
        None,
        None,
        summary,
    )


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
            "label": _("Produced Qty"),
            "fieldname": "produced_qty",
            "fieldtype": "Float",
            "width": 115,
        },
        {
            "label": _("Consumed Qty"),
            "fieldname": "consumed_qty",
            "fieldtype": "Float",
            "width": 120,
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
            "consumed_qty": None,
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


def _fetch_consumption_sed_rows(
    company: str,
    as_of_date: str,
    work_orders: tuple[str, ...],
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

    return frappe.db.sql(
        f"""
        SELECT
            se.name AS se_name,
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
                voucher_detail_no,
                SUM(-actual_qty) AS sle_qty,
                SUM(-stock_value_difference) AS sle_val
            FROM `tabStock Ledger Entry`
            WHERE is_cancelled = 0
              AND voucher_type = 'Stock Entry'
              AND company = %(company)s
              AND posting_date <= %(as_of_date)s
            GROUP BY voucher_detail_no
        ) sle_agg
            ON sle_agg.voucher_detail_no = sed.name
        WHERE se.docstatus = 1
          AND se.purpose = 'Material Consumption for Manufacture'
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


def _fetch_consumption_breakdown(
    company: str,
    as_of_date: str,
    work_orders: list[str],
) -> dict[str, list[dict]]:
    """Fetch and group SLE-exact consumption breakdown by Work Order -> Operation -> Material."""
    if not work_orders:
        return {}

    wo_tuple = tuple(dict.fromkeys(work_orders))
    sed_rows = _fetch_consumption_sed_rows(company, as_of_date, wo_tuple)
    if not sed_rows:
        return {}

    op_order = _fetch_wo_operation_order(wo_tuple)
    wo_item_ops = _fetch_wo_item_operations(wo_tuple)
    se_to_op, conf_to_op = _fetch_confirmation_operations(wo_tuple)

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
                "last_posting_date": None,
            }
            mat_agg[key] = entry

        entry["raw_consumed_qty"] += flt(row.get("consumed_qty"))
        entry["raw_consumed_value"] += flt(row.get("consumed_value"))
        entry["last_posting_date"] = _later_date(
            entry["last_posting_date"], row.get("posting_date")
        )

    ops_by_wo: dict[str, dict[str, dict]] = {}
    for entry in mat_agg.values():
        wo_name = entry["work_order"]
        op_name = entry["operation"]
        qty = flt(entry["raw_consumed_qty"])
        val = flt(entry["raw_consumed_value"], 2)
        material_data = {
            "item_code": entry["item_code"],
            "item_name": entry["item_name"],
            "uom": entry["uom"],
            "consumed_qty": qty,
            "consumed_value": val,
            "unit_rate": flt(val / qty, 4) if qty else 0.0,
            "last_posting_date": entry["last_posting_date"],
        }

        wo_ops = ops_by_wo.setdefault(wo_name, {})
        op_bucket = wo_ops.setdefault(
            op_name,
            {
                "operation": op_name,
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

    breakdown: dict[str, list[dict]] = {}
    for wo_name, wo_ops in ops_by_wo.items():
        sorted_ops = sorted(
            wo_ops.values(),
            key=lambda bucket: (
                op_order.get((wo_name, bucket["operation"]), 999999),
                bucket["operation"],
            ),
        )
        for bucket in sorted_ops:
            bucket["consumed_value"] = flt(bucket["raw_consumed_value"], 2)
            bucket["materials"].sort(
                key=lambda m: (-flt(m["consumed_value"]), m["item_code"])
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
        "produced_qty": None,
        "consumed_qty": None,
        "uom": "",
        "unit_rate": None,
        "consumed_value": flt(op_entry.get("consumed_value"), 2),
        "fg_transferred_value": None,
        "wip_adjustment_value": None,
        "wip_balance": None,
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
        "consumed_qty": flt(mat_entry.get("consumed_qty")),
        "uom": uom,
        "unit_rate": flt(mat_entry.get("unit_rate"), 4),
        "consumed_value": flt(mat_entry.get("consumed_value"), 2),
        "fg_transferred_value": None,
        "wip_adjustment_value": None,
        "wip_balance": None,
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


def _build_report_summary(data: list[dict], company_currency: str) -> list[dict]:
    """Build summary KPI cards strictly from Level-0 Work Order rows."""
    level_0_rows = [d for d in data if cint(d.get("indent", 0)) == 0]
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
