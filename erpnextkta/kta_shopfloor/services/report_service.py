# Copyright (c) 2026, KTA and Contributors
# See license.txt

import datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

VALID_STATUS_FILTERS = ("completed", "partial", "unconfirmed", "all")
VALID_SHORTAGE_FILTERS = (
    "all",
    "active_shortage",
    "critical",
    "transfer_required",
    "resolved",
)
_ITEM_SEVERITY_ORDER = {
    "critical_shortage": 0,
    "transfer_required": 1,
    "available": 2,
}


def get_operation_completion_report(
    status_filter: str = "completed",
    operation: str | None = None,
    workstation: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    search: str | None = None,
    company: str | None = None,
    only_shortage: int | bool | None = 0,
) -> dict:
    """Return operation completion summary across active submitted Work Orders."""
    frappe.has_permission("Work Order", "read", throw=True)
    frappe.has_permission("KTA Production Confirmation", "read", throw=True)

    if status_filter not in VALID_STATUS_FILTERS:
        frappe.throw(
            _("Geçersiz durum filtresi: {0}").format(status_filter),
            frappe.ValidationError,
        )

    target_company, active_companies = _resolve_report_company(company)
    op_rows = _fetch_active_wo_operations(target_company, active_companies)

    filter_options = {
        "operations": sorted({r.operation for r in op_rows if r.get("operation")}),
        "workstations": sorted(
            {r.workstation for r in op_rows if r.get("workstation")}
        ),
    }

    if not op_rows:
        return {
            "rows": [],
            "summary": {
                "completed_operations": 0,
                "partial_operations": 0,
                "unconfirmed_operations": 0,
                "shortage_operations": 0,
                "unique_work_orders": 0,
                "total_confirmed_qty": 0.0,
            },
            "counts": {
                "completed": 0,
                "partial": 0,
                "unconfirmed": 0,
                "shortage": 0,
                "all": 0,
            },
            "filter_options": filter_options,
        }

    wo_names = tuple(sorted({r.work_order for r in op_rows}))
    conf_agg_map = _fetch_confirmation_aggregates(wo_names)
    legacy_agg_map = _fetch_legacy_manufacture_aggregates(wo_names)

    all_rows = [
        _build_report_row(
            op_row,
            conf_agg_map.get((op_row.work_order, op_row.operation)),
            legacy_agg_map.get(op_row.work_order),
        )
        for op_row in op_rows
    ]

    filtered_base = _apply_report_filters(
        all_rows,
        operation=operation,
        workstation=workstation,
        from_date=from_date,
        to_date=to_date,
        search=search,
    )

    shortage_count = sum(
        1
        for r in filtered_base
        if cint(r.get("custom_released_with_shortage") or 0) == 1
    )
    if cint(only_shortage or 0) == 1:
        filtered_pre_status = [
            r
            for r in filtered_base
            if cint(r.get("custom_released_with_shortage") or 0) == 1
        ]
    else:
        filtered_pre_status = filtered_base

    completed_count = sum(1 for r in filtered_pre_status if r["status"] == "completed")
    partial_count = sum(1 for r in filtered_pre_status if r["status"] == "partial")
    unconfirmed_count = sum(
        1 for r in filtered_pre_status if r["status"] == "unconfirmed"
    )
    all_count = len(filtered_pre_status)

    if status_filter == "completed":
        rows = [r for r in filtered_pre_status if r["status"] == "completed"]
    elif status_filter == "partial":
        rows = [r for r in filtered_pre_status if r["status"] == "partial"]
    elif status_filter == "unconfirmed":
        rows = [r for r in filtered_pre_status if r["status"] == "unconfirmed"]
    else:
        rows = list(filtered_pre_status)

    rows.sort(key=lambda r: cint(r.get("sequence_id") or 0))
    rows.sort(
        key=lambda r: (
            r.get("wo_creation") or "",
            r.get("work_order") or "",
        ),
        reverse=True,
    )

    return {
        "rows": rows,
        "summary": {
            "completed_operations": completed_count,
            "partial_operations": partial_count,
            "unconfirmed_operations": unconfirmed_count,
            "shortage_operations": shortage_count,
            "unique_work_orders": len({r["work_order"] for r in rows}),
            "total_confirmed_qty": flt(sum(flt(r["confirmed_qty"]) for r in rows), 4),
        },
        "counts": {
            "completed": completed_count,
            "partial": partial_count,
            "unconfirmed": unconfirmed_count,
            "shortage": shortage_count,
            "all": all_count,
        },
        "filter_options": filter_options,
    }


def _resolve_report_company(
    company: str | None = None,
) -> tuple[str | None, list[str]]:
    """Resolve target company matching get_active_work_orders in api.py."""
    target_company = company
    if not target_company:
        target_company = (
            frappe.defaults.get_user_default("Company")
            or frappe.defaults.get_user_default("company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
        )
        if not frappe.flags.in_test and (
            not target_company or str(target_company).startswith("_Test")
        ):
            real_company = frappe.db.get_value(
                "Company",
                {"name": ["not like", "_Test%"], "is_group": 0},
                "name",
            )
            if real_company:
                target_company = real_company

    if target_company:
        return target_company, []

    active_companies = frappe.get_all("Company", filters={"is_group": 0}, pluck="name")
    return None, active_companies


def _fetch_active_wo_operations(
    target_company: str | None, active_companies: list[str]
) -> list[dict]:
    """Fetch all operation rows for submitted active Work Orders."""
    company_clause, params = _build_company_clause(target_company, active_companies)

    has_shortage_col = frappe.db.has_column(
        "Work Order", "custom_released_with_shortage"
    )
    shortage_col_expr = (
        "COALESCE(wo.custom_released_with_shortage, 0) AS released_with_shortage"
        if has_shortage_col
        else "0 AS released_with_shortage"
    )

    return frappe.db.sql(
        f"""
        SELECT
            wo.name AS work_order,
            wo.creation AS wo_creation,
            wo.status AS wo_status,
            wo.production_item,
            wo.item_name,
            wo.stock_uom,
            COALESCE(wo.qty, 0) AS wo_qty,
            COALESCE(wo.produced_qty, 0) AS produced_qty,
            {shortage_col_expr},
            op.operation,
            op.workstation,
            COALESCE(op.sequence_id, op.idx, 0) AS sequence_id,
            COALESCE(op.completed_qty, 0) AS op_completed_qty,
            op.status AS op_status
        FROM `tabWork Order Operation` op
        INNER JOIN `tabWork Order` wo ON wo.name = op.parent
        WHERE wo.docstatus = 1
          AND wo.status IN ('Not Started', 'In Process')
          {company_clause}
        ORDER BY wo.creation DESC, wo.name DESC, COALESCE(op.sequence_id, op.idx, 0) ASC
        """,
        params,
        as_dict=True,
    )


def _fetch_confirmation_aggregates(
    wo_names: tuple[str, ...],
) -> dict[tuple[str, str], dict]:
    """Fetch and aggregate submitted KTA Production Confirmations per (work_order, operation)."""
    conf_rows = frappe.db.sql(
        """
        SELECT
            work_order,
            operation,
            name,
            COALESCE(yield_qty, 0) AS yield_qty,
            COALESCE(is_final_confirmation, 0) AS is_final_confirmation,
            posting_date,
            posting_time,
            confirmed_by,
            stock_entry
        FROM `tabKTA Production Confirmation`
        WHERE docstatus = 1
          AND work_order IN %(wo_names)s
        ORDER BY posting_date DESC, posting_time DESC, creation DESC, name DESC
        """,
        {"wo_names": wo_names},
        as_dict=True,
    )

    agg_map: dict[tuple[str, str], dict] = {}
    for row in conf_rows:
        key = (row.work_order, row.operation)
        if key not in agg_map:
            posting_date = str(row.posting_date)[:10] if row.posting_date else ""
            posting_time = _format_time_str(row.posting_time)
            last_at = f"{posting_date} {posting_time}".strip() if posting_date else ""
            agg_map[key] = {
                "confirmed_qty": 0.0,
                "confirmation_count": 0,
                "final_confirmation_count": 0,
                "last_confirmation": row.name,
                "last_posting_date": posting_date,
                "last_posting_time": posting_time,
                "last_confirmation_at": last_at,
                "last_confirmed_by": row.confirmed_by or "",
                "stock_entries": set(),
            }

        entry = agg_map[key]
        entry["confirmed_qty"] += flt(row.yield_qty or 0)
        entry["confirmation_count"] += 1
        if cint(row.is_final_confirmation or 0) == 1:
            entry["final_confirmation_count"] += 1
        if row.stock_entry:
            entry["stock_entries"].add(row.stock_entry)

    return agg_map


def _fetch_legacy_manufacture_aggregates(
    wo_names: tuple[str, ...],
) -> dict[str, dict]:
    """Fetch submitted standalone Manufacture Stock Entries not linked to CO11N confirmations."""
    legacy_rows = frappe.db.sql(
        """
        SELECT
            work_order,
            COALESCE(fg_completed_qty, 0) AS fg_completed_qty,
            posting_date,
            posting_time,
            owner
        FROM `tabStock Entry`
        WHERE docstatus = 1
          AND purpose = 'Manufacture'
          AND work_order IN %(wo_names)s
          AND name NOT IN (
              SELECT COALESCE(stock_entry, '')
              FROM `tabKTA Production Confirmation`
              WHERE work_order IN %(wo_names)s
                AND docstatus = 1
                AND stock_entry IS NOT NULL
                AND stock_entry != ''
          )
        ORDER BY posting_date DESC, posting_time DESC, creation DESC, name DESC
        """,
        {"wo_names": wo_names},
        as_dict=True,
    )

    agg_map: dict[str, dict] = {}
    for row in legacy_rows:
        wo = row.work_order
        if wo not in agg_map:
            posting_date = str(row.posting_date)[:10] if row.posting_date else ""
            posting_time = _format_time_str(row.posting_time)
            last_at = f"{posting_date} {posting_time}".strip() if posting_date else ""
            agg_map[wo] = {
                "legacy_manufacture_qty": 0.0,
                "last_posting_date": posting_date,
                "last_posting_time": posting_time,
                "last_confirmation_at": last_at,
                "last_confirmed_by": row.owner or "",
            }
        agg_map[wo]["legacy_manufacture_qty"] += flt(row.fg_completed_qty or 0)

    return agg_map


def _build_report_row(
    op_row: dict,
    conf_agg: dict | None,
    legacy_agg: dict | None,
) -> dict:
    """Build normalized operation completion row from WO operation and confirmation aggregates."""
    wo_qty = flt(op_row.get("wo_qty") or 0)
    completed_qty = flt(op_row.get("op_completed_qty") or 0)
    confirmed_qty = flt(conf_agg["confirmed_qty"]) if conf_agg else 0.0
    confirmation_count = cint(conf_agg["confirmation_count"]) if conf_agg else 0
    final_confirmation_count = (
        cint(conf_agg["final_confirmation_count"]) if conf_agg else 0
    )
    has_final = 1 if final_confirmation_count > 0 else 0
    legacy_qty = flt(legacy_agg["legacy_manufacture_qty"]) if legacy_agg else 0.0

    pending_qty = max(0.0, wo_qty - completed_qty) if wo_qty > 0 else 0.0
    is_completed = (wo_qty > 0 and completed_qty >= wo_qty) or has_final == 1
    is_unconfirmed = (not is_completed) and completed_qty <= 0 and confirmed_qty <= 0
    row_status = (
        "completed"
        if is_completed
        else ("unconfirmed" if is_unconfirmed else "partial")
    )
    if is_completed:
        completion_pct = 100.0
    elif wo_qty > 0:
        completion_pct = round(min(100.0, (completed_qty / wo_qty) * 100.0), 1)
    else:
        completion_pct = 0.0

    if is_unconfirmed:
        source_type = "none"
        last_confirmation = None
        last_posting_date = ""
        last_posting_time = ""
        last_confirmation_at = ""
        last_confirmed_by = ""
        stock_entry_count = 0
    else:
        if confirmed_qty > 0 and legacy_qty > 0:
            source_type = "mixed"
        elif confirmed_qty > 0:
            source_type = "co11n"
        else:
            source_type = "legacy"

        if conf_agg:
            last_confirmation = conf_agg["last_confirmation"]
            last_posting_date = conf_agg["last_posting_date"]
            last_posting_time = conf_agg["last_posting_time"]
            last_confirmation_at = conf_agg["last_confirmation_at"]
            last_confirmed_by = conf_agg["last_confirmed_by"]
            stock_entry_count = len(conf_agg["stock_entries"])
        elif legacy_agg:
            last_confirmation = None
            last_posting_date = legacy_agg["last_posting_date"]
            last_posting_time = legacy_agg["last_posting_time"]
            last_confirmation_at = legacy_agg["last_confirmation_at"]
            last_confirmed_by = legacy_agg["last_confirmed_by"]
            stock_entry_count = 0
        else:
            last_confirmation = None
            last_posting_date = ""
            last_posting_time = ""
            last_confirmation_at = ""
            last_confirmed_by = ""
            stock_entry_count = 0

    return {
        "work_order": op_row.work_order,
        "wo_creation": _format_datetime_str(op_row.get("wo_creation")),
        "wo_status": op_row.wo_status,
        "production_item": op_row.production_item,
        "item_name": op_row.item_name or op_row.production_item,
        "stock_uom": op_row.stock_uom or "",
        "wo_qty": wo_qty,
        "qty": wo_qty,
        "custom_released_with_shortage": cint(
            op_row.get("released_with_shortage") or 0
        ),
        "operation": op_row.operation,
        "sequence_id": cint(op_row.sequence_id or 0),
        "workstation": op_row.workstation or "",
        "op_status": op_row.op_status or "",
        "completed_qty": completed_qty,
        "co11n_qty": confirmed_qty,
        "confirmed_qty": confirmed_qty,
        "legacy_manufacture_qty": legacy_qty,
        "pending_qty": pending_qty,
        "completion_percent": completion_pct,
        "completion_pct": completion_pct,
        "is_completed": is_completed,
        "status": row_status,
        "has_final_confirmation": has_final,
        "final_confirmation_count": final_confirmation_count,
        "confirmation_count": confirmation_count,
        "stock_entry_count": stock_entry_count,
        "last_confirmation": last_confirmation,
        "last_posting_date": last_posting_date,
        "last_posting_time": last_posting_time,
        "last_confirmation_at": last_confirmation_at,
        "last_confirmed_by": last_confirmed_by,
        "source_type": source_type,
    }


def _apply_report_filters(
    rows: list[dict],
    operation: str | None = None,
    workstation: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Filter report rows by operation, workstation, date range, and free-text search."""
    op_filter = str(operation).strip() if operation else ""
    ws_filter = str(workstation).strip() if workstation else ""
    search_term = str(search).strip().lower() if search else ""
    parsed_from = _safe_parse_date(from_date)
    parsed_to = _safe_parse_date(to_date)

    result: list[dict] = []
    for row in rows:
        if op_filter and row["operation"] != op_filter:
            continue
        if ws_filter and row["workstation"] != ws_filter:
            continue

        if parsed_from or parsed_to:
            row_date = _safe_parse_date(row.get("last_posting_date"))
            if not row_date:
                continue
            if parsed_from and row_date < parsed_from:
                continue
            if parsed_to and row_date > parsed_to:
                continue

        if search_term:
            haystack = (
                row.get("work_order") or "",
                row.get("production_item") or "",
                row.get("item_name") or "",
                row.get("operation") or "",
                row.get("workstation") or "",
                row.get("last_confirmed_by") or "",
            )
            if not any(search_term in str(val).lower() for val in haystack):
                continue

        result.append(row)

    return result


def _safe_parse_date(value: str | datetime.date | None) -> datetime.date | None:
    if not value or not str(value).strip():
        return None
    try:
        return getdate(value)
    except (frappe.ValidationError, TypeError, ValueError, OverflowError):
        return None


def _format_time_str(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime.timedelta):
        total_seconds = int(value.total_seconds()) % 86400
        hours, rem = divmod(total_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    text = str(value).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    parts = text.split(":")
    if len(parts) == 3 and parts[0].isdigit():
        return f"{int(parts[0]):02d}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    return text


def _format_datetime_str(value) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text.split(".", 1)[0]


def get_material_shortage_report(
    shortage_filter: str = "all",
    warehouse: str | None = None,
    search: str | None = None,
    company: str | None = None,
) -> dict:
    """Return material shortage and readiness summary across active shortage-released Work Orders."""
    frappe.has_permission("Work Order", "read", throw=True)

    if shortage_filter not in VALID_SHORTAGE_FILTERS:
        frappe.throw(
            _("Geçersiz eksik malzeme filtresi: {0}").format(shortage_filter),
            frappe.ValidationError,
        )

    if not frappe.db.has_column("Work Order", "custom_released_with_shortage"):
        return _empty_material_shortage_report()

    target_company, active_companies = _resolve_report_company(company)
    wo_rows = _fetch_active_shortage_work_orders(target_company, active_companies)
    if not wo_rows:
        return _empty_material_shortage_report()

    wo_names = tuple(sorted({r.name for r in wo_rows}))
    items_by_wo = _fetch_work_order_items_bulk(wo_names)

    item_codes = tuple(
        sorted(
            {
                item.item_code
                for items in items_by_wo.values()
                for item in items
                if item.get("item_code")
            }
        )
    )
    wo_companies = tuple(sorted({r.company for r in wo_rows if r.get("company")}))
    line_qty_map, company_wh_qty_map = _fetch_bin_stock_maps(item_codes, wo_companies)

    all_wo_rows = [
        _build_material_shortage_wo_row(
            wo_row,
            items_by_wo.get(wo_row.name, []),
            line_qty_map,
            company_wh_qty_map,
        )
        for wo_row in wo_rows
    ]

    filter_options = {
        "warehouses": sorted(
            {
                item["source_warehouse"]
                for wo in all_wo_rows
                for item in wo["items"]
                if item.get("source_warehouse")
            }
        )
    }

    filtered_base = _apply_shortage_filters(
        all_wo_rows, warehouse=warehouse, search=search
    )

    critical_count = sum(1 for r in filtered_base if r["shortage_status"] == "critical")
    transfer_count = sum(
        1 for r in filtered_base if r["shortage_status"] == "transfer_required"
    )
    resolved_count = sum(1 for r in filtered_base if r["shortage_status"] == "resolved")
    counts = {
        "all": len(filtered_base),
        "active_shortage": critical_count + transfer_count,
        "critical": critical_count,
        "transfer_required": transfer_count,
        "resolved": resolved_count,
    }

    if shortage_filter == "active_shortage":
        rows = [
            r
            for r in filtered_base
            if r["shortage_status"] in ("critical", "transfer_required")
        ]
    elif shortage_filter in ("critical", "transfer_required", "resolved"):
        rows = [r for r in filtered_base if r["shortage_status"] == shortage_filter]
    else:
        rows = list(filtered_base)

    rows.sort(
        key=lambda r: (
            r.get("wo_creation") or "",
            r.get("work_order") or "",
        ),
        reverse=True,
    )

    return {
        "rows": rows,
        "summary": {
            "total_work_orders": counts["all"],
            "critical_work_orders": counts["critical"],
            "transfer_work_orders": counts["transfer_required"],
            "resolved_work_orders": counts["resolved"],
            "total_shortage_items": sum(r["shortage_items_count"] for r in rows),
        },
        "counts": counts,
        "filter_options": filter_options,
    }


def _empty_material_shortage_report() -> dict:
    return {
        "rows": [],
        "summary": {
            "total_work_orders": 0,
            "critical_work_orders": 0,
            "transfer_work_orders": 0,
            "resolved_work_orders": 0,
            "total_shortage_items": 0,
        },
        "counts": {
            "all": 0,
            "active_shortage": 0,
            "critical": 0,
            "transfer_required": 0,
            "resolved": 0,
        },
        "filter_options": {"warehouses": []},
    }


def _build_company_clause(
    target_company: str | None, active_companies: list[str]
) -> tuple[str, dict]:
    params: dict = {}
    if target_company:
        params["company"] = target_company
        return "AND wo.company = %(company)s", params
    if active_companies:
        params["companies"] = tuple(active_companies)
        return "AND wo.company IN %(companies)s", params
    return "", params


def _fetch_active_shortage_work_orders(
    target_company: str | None, active_companies: list[str]
) -> list[dict]:
    """Fetch active submitted Work Orders released with material shortage."""
    company_clause, params = _build_company_clause(target_company, active_companies)
    return frappe.db.sql(
        f"""
        SELECT
            wo.name,
            wo.creation,
            wo.company,
            wo.status,
            wo.production_item,
            wo.item_name,
            wo.stock_uom,
            COALESCE(wo.qty, 0) AS qty,
            COALESCE(wo.produced_qty, 0) AS produced_qty,
            wo.wip_warehouse,
            wo.source_warehouse,
            COALESCE(wo.skip_transfer, 0) AS skip_transfer,
            COALESCE(wo.from_wip_warehouse, 0) AS from_wip_warehouse,
            wo.planned_start_date,
            wo.expected_delivery_date,
            wo.modified
        FROM `tabWork Order` wo
        WHERE wo.docstatus = 1
          AND wo.status IN ('Not Started', 'In Process')
          AND COALESCE(wo.custom_released_with_shortage, 0) = 1
          {company_clause}
        ORDER BY wo.creation DESC, wo.name DESC
        """,
        params,
        as_dict=True,
    )


def _fetch_work_order_items_bulk(
    wo_names: tuple[str, ...],
) -> dict[str, list[dict]]:
    """Bulk-fetch Work Order Item rows keyed by parent Work Order name."""
    if not wo_names:
        return {}
    rows = frappe.db.sql(
        """
        SELECT
            parent,
            item_code,
            item_name,
            operation,
            source_warehouse,
            COALESCE(required_qty, 0) AS required_qty,
            COALESCE(transferred_qty, 0) AS transferred_qty,
            COALESCE(consumed_qty, 0) AS consumed_qty,
            stock_uom
        FROM `tabWork Order Item`
        WHERE parent IN %(wo_names)s
        ORDER BY parent ASC, idx ASC
        """,
        {"wo_names": wo_names},
        as_dict=True,
    )
    by_wo: dict[str, list[dict]] = {}
    for row in rows:
        by_wo.setdefault(row.parent, []).append(row)
    return by_wo


def _fetch_bin_stock_maps(
    item_codes: tuple[str, ...],
    companies: tuple[str, ...],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], dict[str, float]]]:
    """Bulk-fetch Bin actual quantities across active non-group company warehouses."""
    if not item_codes:
        return {}, {}

    params: dict = {"item_codes": item_codes}
    company_clause = ""
    if companies:
        company_clause = "AND w.company IN %(companies)s"
        params["companies"] = companies

    bin_rows = frappe.db.sql(
        f"""
        SELECT
            b.item_code,
            b.warehouse,
            w.company,
            COALESCE(b.actual_qty, 0) AS actual_qty
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code IN %(item_codes)s
          AND w.is_group = 0
          AND w.disabled = 0
          {company_clause}
        """,
        params,
        as_dict=True,
    )

    line_qty_map: dict[tuple[str, str], float] = {}
    company_wh_qty_map: dict[tuple[str, str], dict[str, float]] = {}
    for row in bin_rows:
        qty = max(0.0, flt(row.actual_qty or 0))
        line_qty_map[(row.item_code, row.warehouse)] = qty
        if row.company:
            company_wh_qty_map.setdefault((row.item_code, row.company), {})[
                row.warehouse
            ] = qty

    return line_qty_map, company_wh_qty_map


def _build_material_shortage_wo_row(
    wo_row: dict,
    raw_items: list[dict],
    line_qty_map: dict[tuple[str, str], float],
    company_wh_qty_map: dict[tuple[str, str], dict[str, float]],
) -> dict:
    """Build normalized shortage status row and item breakdown for a Work Order."""
    wo_company = wo_row.get("company") or ""
    built_items: list[dict] = []

    for item_row in raw_items:
        item_code = item_row.get("item_code") or ""
        source_wh = (
            item_row.get("source_warehouse")
            or wo_row.get("source_warehouse")
            or wo_row.get("wip_warehouse")
            or ""
        )
        required_qty = flt(item_row.get("required_qty") or 0)
        consumed_qty = flt(item_row.get("consumed_qty") or 0)
        transferred_qty = flt(item_row.get("transferred_qty") or 0)
        remaining_required_qty = max(0.0, flt(required_qty - consumed_qty))

        line_actual_qty = (
            flt(line_qty_map.get((item_code, source_wh), 0.0)) if source_wh else 0.0
        )
        wh_qtys = company_wh_qty_map.get((item_code, wo_company), {})
        other_warehouses_qty = flt(
            sum(qty for wh, qty in wh_qtys.items() if wh != source_wh)
        )

        shortage_qty = max(0.0, flt(remaining_required_qty - line_actual_qty))
        coverage_pct = (
            100.0
            if remaining_required_qty <= 0
            else round(
                min(100.0, (line_actual_qty / remaining_required_qty) * 100.0), 1
            )
        )

        if shortage_qty <= 0:
            availability_status = "available"
        elif (line_actual_qty + other_warehouses_qty) >= remaining_required_qty:
            availability_status = "transfer_required"
        else:
            availability_status = "critical_shortage"

        built_items.append(
            {
                "item_code": item_code,
                "item_name": item_row.get("item_name") or item_code,
                "operation": item_row.get("operation") or "",
                "source_warehouse": source_wh,
                "stock_uom": item_row.get("stock_uom") or "",
                "required_qty": required_qty,
                "consumed_qty": consumed_qty,
                "transferred_qty": transferred_qty,
                "remaining_required_qty": remaining_required_qty,
                "line_actual_qty": line_actual_qty,
                "other_warehouses_qty": other_warehouses_qty,
                "shortage_qty": shortage_qty,
                "coverage_pct": coverage_pct,
                "availability_status": availability_status,
            }
        )

    built_items.sort(
        key=lambda item: (
            _ITEM_SEVERITY_ORDER[item["availability_status"]],
            -flt(item["shortage_qty"]),
            item["item_code"] or "",
        )
    )

    critical_shortage_count = sum(
        1 for item in built_items if item["availability_status"] == "critical_shortage"
    )
    transfer_required_count = sum(
        1 for item in built_items if item["availability_status"] == "transfer_required"
    )
    shortage_items_count = sum(1 for item in built_items if item["shortage_qty"] > 0)
    readiness_pct = (
        round(sum(item["coverage_pct"] for item in built_items) / len(built_items), 1)
        if built_items
        else 100.0
    )

    if critical_shortage_count > 0:
        shortage_status = "critical"
    elif shortage_items_count > 0:
        shortage_status = "transfer_required"
    else:
        shortage_status = "resolved"

    planned_start = wo_row.get("planned_start_date")
    expected_delivery = wo_row.get("expected_delivery_date")

    return {
        "work_order": wo_row.name,
        "wo_creation": _format_datetime_str(wo_row.get("creation")),
        "wo_status": wo_row.status,
        "production_item": wo_row.production_item,
        "item_name": wo_row.item_name or wo_row.production_item,
        "stock_uom": wo_row.stock_uom or "",
        "qty": flt(wo_row.get("qty") or 0),
        "produced_qty": flt(wo_row.get("produced_qty") or 0),
        "planned_start_date": str(planned_start)[:10] if planned_start else "",
        "expected_delivery_date": (
            str(expected_delivery)[:10] if expected_delivery else ""
        ),
        "items": built_items,
        "total_items": len(built_items),
        "shortage_items_count": shortage_items_count,
        "critical_shortage_count": critical_shortage_count,
        "transfer_required_count": transfer_required_count,
        "readiness_pct": readiness_pct,
        "shortage_status": shortage_status,
    }


def _apply_shortage_filters(
    rows: list[dict],
    warehouse: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Filter shortage Work Order rows by item source warehouse and free-text search."""
    wh_filter = str(warehouse).strip() if warehouse else ""
    search_term = str(search).strip().lower() if search else ""

    if not wh_filter and not search_term:
        return list(rows)

    result: list[dict] = []
    for row in rows:
        items = row.get("items") or []
        if wh_filter and not any(
            item.get("source_warehouse") == wh_filter for item in items
        ):
            continue

        if search_term:
            haystack: list[str] = [
                row.get("work_order") or "",
                row.get("production_item") or "",
                row.get("item_name") or "",
            ]
            for item in items:
                haystack.extend(
                    (
                        item.get("item_code") or "",
                        item.get("item_name") or "",
                        item.get("operation") or "",
                        item.get("source_warehouse") or "",
                    )
                )
            if not any(search_term in str(val).lower() for val in haystack):
                continue

        result.append(row)

    return result
