# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from erpnextkta.kta_shopfloor.services.confirmation_service import (
    ConfirmationService,
    _resolve_job_card,
)
from erpnextkta.kta_shopfloor.services.report_service import (
    get_material_shortage_report as get_material_shortage_report_service,
)
from erpnextkta.kta_shopfloor.services.report_service import (
    get_operation_completion_report as get_operation_completion_report_service,
)
from erpnextkta.kta_shopfloor.services.reservation_deficit_service import (
    get_line_reservation_deficits,
)
from erpnextkta.kta_shopfloor.services.reversal_service import ReversalService
from erpnextkta.kta_shopfloor.services.work_order_service import (
    check_work_order_material_availability,
    create_draft_work_order,
    get_item_alternatives,
    get_work_order_item_alternatives,
    release_work_order_service,
    resolve_manufacturing_lead_days,
    restore_work_order_item_original,
    set_work_order_item_alternative,
    update_work_order_qty,
)
from erpnextkta.kta_shopfloor.services.work_order_service import (
    get_work_order_print_options as get_work_order_print_options_service,
)


@frappe.whitelist()
def get_shopfloor_hub_context(barcode: str | None = None) -> dict:
    """Resolve Work Order context and operations list from a barcode, WO name, or JC name.

    Returns dict containing Work Order header data, operation list, and default selections.
    """
    if not barcode:
        frappe.throw(
            _("Barkod veya İş Emri / İş Kartı boş olamaz."), frappe.ValidationError
        )

    code = str(barcode).strip()
    if not code:
        frappe.throw(
            _("Barkod veya İş Emri / İş Kartı boş olamaz."), frappe.ValidationError
        )

    wo_name = None
    selected_job_card = None
    selected_operation = None

    # 1. Direct Work Order match
    if frappe.db.exists("Work Order", code):
        wo_name = code

    # 2. Direct Job Card match
    elif frappe.db.exists("Job Card", code):
        jc_data = frappe.db.get_value(
            "Job Card", code, ["name", "work_order", "operation"], as_dict=True
        )
        if jc_data:
            selected_job_card = jc_data.name
            wo_name = jc_data.work_order
            selected_operation = jc_data.operation

    # 3. Barcode field on Job Card (if column exists)
    if not wo_name and frappe.db.has_column("Job Card", "barcode"):
        jc_data = frappe.db.get_value(
            "Job Card",
            {"barcode": code},
            ["name", "work_order", "operation"],
            as_dict=True,
        )
        if jc_data:
            selected_job_card = jc_data.name
            wo_name = jc_data.work_order
            selected_operation = jc_data.operation

    # 4. Barcode field on Work Order (if column exists)
    if not wo_name and frappe.db.has_column("Work Order", "barcode"):
        wo_name = frappe.db.get_value("Work Order", {"barcode": code}, "name")

    if not wo_name or not frappe.db.exists("Work Order", wo_name):
        frappe.throw(
            _("Barkod ile eşleşen İş Emri veya İş Kartı bulunamadı: {0}").format(code),
            frappe.ValidationError,
        )

    wo = frappe.get_doc("Work Order", wo_name)
    if not wo.has_permission("read"):
        frappe.throw(_("Bu İş Emri için okuma yetkiniz yok."), frappe.PermissionError)

    wo_qty = flt(wo.qty)
    ops = wo.get("operations") or []
    operations = []

    if ops:
        sorted_ops = sorted(
            ops,
            key=lambda d: (
                getattr(d, "sequence_id", None) or d.get("sequence_id") or 0,
                getattr(d, "idx", None) or d.get("idx") or 0,
            ),
        )
        num_ops = len(sorted_ops)
        for idx, op in enumerate(sorted_ops):
            is_last = idx == num_ops - 1
            op_qtys = ConfirmationService.get_operation_quantities(wo, op.operation)
            completed = op_qtys["completed_qty"]
            pending = op_qtys["pending_qty"]
            status = op_qtys["status"]

            # Self-healing synchronization for Work Order Operation row
            if flt(op.completed_qty or 0) != completed or (op.status or "") != status:
                frappe.db.set_value(
                    "Work Order Operation",
                    op.name,
                    {
                        "completed_qty": completed,
                        "status": status,
                    },
                )
                op.completed_qty = completed
                op.status = status

            jc_name = _resolve_job_card(wo.name, op.operation)
            op_data = {
                "operation": op.operation,
                "sequence_id": op.sequence_id or op.idx or (idx + 1),
                "workstation": op.workstation,
                "completed_qty": completed,
                "pending_qty": pending,
                "status": status,
                "is_last_op": is_last,
                "job_card": jc_name,
            }
            operations.append(op_data)
            if not selected_operation and idx == 0:
                selected_operation = op.operation
    else:
        default_op_name = _("Üretim")
        op_qtys = ConfirmationService.get_operation_quantities(wo, default_op_name)
        completed = op_qtys["completed_qty"]
        pending = op_qtys["pending_qty"]
        status = op_qtys["status"]
        operations.append(
            {
                "operation": default_op_name,
                "sequence_id": 1,
                "workstation": None,
                "completed_qty": completed,
                "pending_qty": pending,
                "status": status,
                "is_last_op": True,
                "job_card": None,
            }
        )
        selected_operation = default_op_name

    source_wh = getattr(wo, "source_warehouse", None) or getattr(
        wo, "wip_warehouse", None
    )

    return {
        "work_order": wo.name,
        "item_code": wo.production_item,
        "item_name": wo.item_name or wo.production_item,
        "stock_uom": wo.stock_uom,
        "qty": wo_qty,
        "produced_qty": flt(wo.produced_qty or 0),
        "docstatus": cint(wo.docstatus),
        "status": wo.status,
        "custom_released_with_shortage": cint(
            wo.get("custom_released_with_shortage") or 0
        ),
        "source_warehouse": source_wh,
        "fg_warehouse": getattr(wo, "fg_warehouse", None),
        "company": wo.company,
        "selected_operation": selected_operation,
        "selected_job_card": selected_job_card,
        "operations": operations,
        "can_cancel_confirmations": ReversalService.can_cancel_confirmations(
            frappe.session.user
        ),
    }


@frappe.whitelist()
def get_co11n_context(barcode: str | None = None) -> dict:
    """Legacy alias for get_shopfloor_hub_context."""
    return get_shopfloor_hub_context(barcode=barcode)


@frappe.whitelist()
def submit_production_confirmation(payload: dict | str | None = None, **kwargs) -> dict:
    """Submit a shopfloor production confirmation."""
    return ConfirmationService.confirm_operation(payload=payload, **kwargs)


@frappe.whitelist()
def submit_co11n_confirmation(payload: dict | str | None = None, **kwargs) -> dict:
    """Legacy alias for submit_production_confirmation."""
    return submit_production_confirmation(payload=payload, **kwargs)


@frappe.whitelist()
def cancel_production_confirmation(confirmation_name: str) -> dict:
    """Cancel a shopfloor production confirmation using Shopfloor CORS pattern."""
    return ReversalService.cancel_confirmation(
        confirmation_name=confirmation_name,
        user=frappe.session.user,
    )


@frappe.whitelist()
def cancel_co11n_confirmation(confirmation_name: str) -> dict:
    """Legacy alias for cancel_production_confirmation."""
    return cancel_production_confirmation(confirmation_name=confirmation_name)


@frappe.whitelist(methods=["POST"])
def bulk_cancel_production_confirmations(confirmation_names: list[str] | str) -> dict:
    """Bulk cancel shopfloor production confirmations using Shopfloor CORS pattern."""
    return ReversalService.bulk_cancel_confirmations(
        confirmation_names=confirmation_names,
        user=frappe.session.user,
    )


@frappe.whitelist()
def check_confirmation_materials(
    work_order: str,
    operation: str,
    yield_qty: float,
    is_final_confirmation: int = 0,
) -> dict:
    """Check line stock availability for raw materials to be consumed in a confirmation."""
    return ConfirmationService.check_confirmation_materials(
        work_order=work_order,
        operation=operation,
        yield_qty=yield_qty,
        is_final_confirmation=is_final_confirmation,
    )


@frappe.whitelist(methods=["POST"])
def stage_confirmation_materials(
    work_order: str,
    transfers: list[dict] | str,
) -> dict:
    """Create and submit a Material Transfer for Manufacture Stock Entry to replenish line stock."""
    return ConfirmationService.stage_confirmation_materials(
        work_order=work_order,
        transfers=transfers,
    )


def _resolve_target_company(company: str | None = None) -> str | None:
    """Resolve target company from explicit value, user defaults, or active companies."""
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
    return target_company


@frappe.whitelist()
def get_active_work_orders(
    search: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    company: str | None = None,
    status_filter: str | None = None,
    include_drafts: int = 0,
    fiscal_year: str | None = None,
    order_by: str | None = None,
) -> list[dict]:
    """Retrieve Work Orders for Shopfloor Hub drawers (Operations & Work Orders views).

    Filters:
    - company: Specified company, or user's default company / active companies.
    - status_filter / status: Optional status filter ('Draft', 'Released', 'Not Started',
      'In Process', 'Completed').
    - include_drafts: When 1 and no status filter is given, includes active Work Orders (Draft,
      Not Started, In Process). When 0 (default, Operations view) and no status filter is given,
      restricts to docstatus=1 and status in ('Not Started', 'In Process').
    - search: If provided, filters by name, production_item, or item_name (LIKE %search%).
    - fiscal_year: Optional Fiscal Year to restrict creation date range. Defaults to current
      fiscal year when status is 'Completed'.
    - order_by: Custom order by clause. Defaults to 'name desc' when status is 'Completed',
      otherwise defaults to 'name asc'.
    - limit: Limit record count if > 0. If None, 0, or omitted, returns all matching records.
    """
    filters: dict[str, object] = {}

    target_company = _resolve_target_company(company)

    if target_company:
        filters["company"] = target_company
    else:
        active_companies = frappe.get_all(
            "Company", filters={"is_group": 0}, pluck="name"
        )
        if active_companies:
            filters["company"] = ["in", active_companies]

    effective_status = status_filter or status
    if effective_status == "All":
        effective_status = None

    if effective_status == "Draft":
        filters["docstatus"] = 0
        filters["status"] = "Draft"
    elif effective_status == "Released":
        filters["docstatus"] = 1
        filters["status"] = ["in", ["Not Started", "In Process"]]
    elif effective_status:
        filters["docstatus"] = 1
        filters["status"] = effective_status
    elif cint(include_drafts) == 1:
        filters["docstatus"] = ["in", [0, 1]]
        filters["status"] = ["in", ["Draft", "Not Started", "In Process"]]
    else:
        filters["docstatus"] = 1
        filters["status"] = ["in", ["Not Started", "In Process"]]

    if effective_status == "Completed" or fiscal_year:
        start_date = None
        end_date = None
        if fiscal_year:
            fy_dates = frappe.db.get_value(
                "Fiscal Year",
                fiscal_year,
                ["year_start_date", "year_end_date"],
                as_dict=True,
            )
            if fy_dates:
                start_date = fy_dates.get("year_start_date")
                end_date = fy_dates.get("year_end_date")
            elif (
                len(str(fiscal_year).strip()) == 4
                and str(fiscal_year).strip().isdigit()
            ):
                start_date = f"{str(fiscal_year).strip()}-01-01"
                end_date = f"{str(fiscal_year).strip()}-12-31"
        elif effective_status == "Completed":
            try:
                import erpnext.accounts.utils

                fy_info = erpnext.accounts.utils.get_fiscal_year(date=nowdate())
                if isinstance(fy_info, (list, tuple)) and len(fy_info) >= 3:
                    start_date = fy_info[1]
                    end_date = fy_info[2]
                elif isinstance(fy_info, dict):
                    start_date = fy_info.get("year_start_date")
                    end_date = fy_info.get("year_end_date")
            except Exception as err:  # noqa: BLE001
                frappe.logger().debug(f"Unable to resolve fiscal year: {err}")

            if not start_date or not end_date:
                cur_year = nowdate()[:4]
                start_date = f"{cur_year}-01-01"
                end_date = f"{cur_year}-12-31"

        if start_date and end_date:
            filters["creation"] = [
                "between",
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"],
            ]

    or_filters = None
    if search and str(search).strip():
        term = f"%{str(search).strip()}%"
        or_filters = [
            ["Work Order", "name", "like", term],
            ["Work Order", "production_item", "like", term],
            ["Work Order", "item_name", "like", term],
        ]

    fields = [
        "name",
        "production_item",
        "item_name",
        "qty",
        "produced_qty",
        "docstatus",
        "status",
        "planned_start_date",
        "planned_end_date",
        "modified",
    ]

    limit_records = cint(limit) if (limit is not None and cint(limit) > 0) else None

    if order_by and str(order_by).strip():
        resolved_order_by = str(order_by).strip()
    elif effective_status == "Completed":
        resolved_order_by = "name desc"
    else:
        resolved_order_by = "name asc"

    records = frappe.get_all(
        "Work Order",
        filters=filters,
        or_filters=or_filters,
        fields=fields,
        order_by=resolved_order_by,
        limit=limit_records,
    )

    for row in records:
        row["qty"] = flt(row.get("qty") or 0)
        row["produced_qty"] = flt(row.get("produced_qty") or 0)
        row["docstatus"] = cint(row.get("docstatus") or 0)

    return records


@frappe.whitelist()
def get_item_default_bom(item_code: str, customer: str | None = None) -> dict:
    """Fetch default active submitted BOM, item metadata, and manufacturing lead days."""
    frappe.has_permission("Item", "read", throw=True)
    item_info = (
        frappe.db.get_value(
            "Item",
            item_code,
            ["item_name", "stock_uom"],
            as_dict=True,
        )
        if item_code
        else None
    )

    default_bom = None
    if item_code:
        default_bom = frappe.db.get_value(
            "BOM",
            {"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
            "name",
        )
        if not default_bom:
            default_bom = frappe.db.get_value(
                "BOM",
                {"item": item_code, "is_active": 1, "docstatus": 1},
                "name",
                order_by="creation desc",
            )

    lead_days = resolve_manufacturing_lead_days(item_code, customer=customer)

    return {
        "item_code": item_code,
        "item_name": item_info.item_name if item_info else None,
        "bom": default_bom,
        "stock_uom": item_info.stock_uom if item_info else None,
        "manufacturing_lead_days": lead_days,
    }


@frappe.whitelist()
def create_work_order(
    item_code: str,
    qty: float,
    bom_no: str | None = None,
    source_warehouse: str | None = None,
    wip_warehouse: str | None = None,
    fg_warehouse: str | None = None,
    planned_start_date: str | None = None,
    planned_end_date: str | None = None,
    company: str | None = None,
    customer: str | None = None,
) -> dict:
    """Create a Draft Work Order with resolved BOM and manufacturing lead time."""
    return create_draft_work_order(
        item_code=item_code,
        qty=qty,
        bom_no=bom_no,
        source_warehouse=source_warehouse,
        wip_warehouse=wip_warehouse,
        fg_warehouse=fg_warehouse,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        company=company,
        customer=customer,
    )


@frappe.whitelist()
def check_material_availability(work_order: str) -> dict:
    """Check Bin stock availability for all required items of a Work Order."""
    return check_work_order_material_availability(work_order)


@frappe.whitelist()
def release_work_order(work_order: str, allow_shortage: int = 0) -> dict:
    """Release (submit) a Draft Work Order after validating material availability."""
    return release_work_order_service(work_order, allow_shortage=cint(allow_shortage))


def _format_stock_entry_ref(name: str, purpose: str | None) -> dict:
    """Format a Stock Entry reference dict for confirmation listings."""
    is_consumption = purpose == "Material Consumption for Manufacture"
    return {
        "name": name,
        "purpose": purpose,
        "type": "consumption" if is_consumption else "manufacture",
        "label": _("Tüketim") if is_consumption else _("Üretim"),
    }


def _attach_stock_entries_to_confirmations(
    confirmations: list[dict], work_orders: list[str] | None = None
) -> list[dict]:
    """Attach linked consumption and manufacture Stock Entries to confirmation dicts."""
    if not confirmations:
        return confirmations

    target_wos = (
        list(dict.fromkeys(wo for wo in work_orders if wo))
        if work_orders is not None
        else list(
            dict.fromkeys(
                conf.get("work_order")
                for conf in confirmations
                if conf.get("work_order")
            )
        )
    )

    se_list = (
        frappe.get_all(
            "Stock Entry",
            filters={"work_order": ["in", target_wos]},
            fields=["name", "work_order", "purpose", "remarks"],
            order_by="creation asc",
        )
        if target_wos
        else []
    )

    se_by_wo: dict[str, list[dict]] = {}
    known_se_names: set[str] = set()
    for se in se_list:
        known_se_names.add(se["name"])
        se_by_wo.setdefault(se.get("work_order") or "", []).append(se)

    missing_linked = list(
        dict.fromkeys(
            conf["stock_entry"]
            for conf in confirmations
            if conf.get("stock_entry") and conf["stock_entry"] not in known_se_names
        )
    )
    extra_se_map: dict[str, dict] = {}
    if missing_linked:
        for se_doc in frappe.get_all(
            "Stock Entry",
            filters={"name": ["in", missing_linked]},
            fields=["name", "purpose"],
        ):
            extra_se_map[se_doc["name"]] = se_doc

    for conf in confirmations:
        conf_name = conf["name"]
        linked_se = conf.get("stock_entry")
        wo_name = conf.get("work_order")
        candidates = (
            se_by_wo.get(wo_name, [])
            if wo_name
            else (se_by_wo.get(target_wos[0], []) if len(target_wos) == 1 else se_list)
        )

        matched_entries: list[dict] = []
        seen_se_names: set[str] = set()
        for se in candidates:
            remarks = se.get("remarks") or ""
            is_match = (conf_name in remarks) or (
                bool(linked_se) and se["name"] == linked_se
            )
            if is_match and se["name"] not in seen_se_names:
                seen_se_names.add(se["name"])
                matched_entries.append(
                    _format_stock_entry_ref(se["name"], se.get("purpose"))
                )

        if linked_se and linked_se not in seen_se_names and linked_se in extra_se_map:
            se_doc = extra_se_map[linked_se]
            seen_se_names.add(se_doc["name"])
            matched_entries.append(
                _format_stock_entry_ref(se_doc["name"], se_doc.get("purpose"))
            )

        conf["yield_qty"] = flt(conf.get("yield_qty") or 0)
        conf["stock_entries"] = matched_entries

    return confirmations


@frappe.whitelist()
def get_production_confirmations(work_order: str) -> list[dict]:
    """Retrieve production confirmations (KTA Production Confirmation) for a given Work Order,

    including all associated Stock Entry records (both consumption and finished goods).
    """
    if not work_order:
        return []

    confirmations = frappe.get_all(
        "KTA Production Confirmation",
        filters={"work_order": work_order},
        fields=[
            "name",
            "work_order",
            "operation",
            "yield_qty",
            "posting_date",
            "posting_time",
            "confirmed_by",
            "stock_entry",
            "docstatus",
            "is_final_confirmation",
            "creation",
        ],
        order_by="creation desc",
    )

    if not confirmations:
        return []

    return _attach_stock_entries_to_confirmations(
        confirmations, work_orders=[work_order]
    )


@frappe.whitelist()
def get_co11n_confirmations(work_order: str) -> list[dict]:
    """Legacy alias for get_production_confirmations."""
    return get_production_confirmations(work_order=work_order)


@frappe.whitelist()
def get_alternatives(
    item_code: str,
    company: str | None = None,
    warehouse: str | None = None,
) -> list[dict]:
    """API endpoint to get approved item alternatives with stock."""
    return get_item_alternatives(item_code, company=company, warehouse=warehouse)


@frappe.whitelist()
def get_work_order_alternatives(work_order: str, row_name: str) -> dict:
    """API endpoint to get alternatives and swap feasibility for a Work Order item."""
    return get_work_order_item_alternatives(work_order, row_name)


@frappe.whitelist()
def set_work_order_alternative(
    work_order: str, row_name: str, alternative_item_code: str
) -> dict:
    """API endpoint to substitute an approved alternative on a Draft Work Order."""
    return set_work_order_item_alternative(work_order, row_name, alternative_item_code)


@frappe.whitelist()
def restore_work_order_original(work_order: str, row_name: str) -> dict:
    """API endpoint to restore original item on a Draft Work Order."""
    return restore_work_order_item_original(work_order, row_name)


@frappe.whitelist(methods=["POST"])
def update_work_order_quantity(work_order: str, qty: float) -> dict:
    """API endpoint to proportionally scale target quantity on a Draft Work Order."""
    wo = frappe.get_doc("Work Order", work_order)
    wo.check_permission("write")
    return update_work_order_qty(work_order, qty)


@frappe.whitelist()
def get_work_order_print_options(work_order: str | None = None) -> dict:
    """Retrieve active Print Formats, letter heads, and print permissions for a Work Order."""
    return get_work_order_print_options_service(work_order=work_order)


@frappe.whitelist()
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
    """Retrieve operation completion summary across active submitted Work Orders."""
    return get_operation_completion_report_service(
        status_filter=status_filter,
        operation=operation,
        workstation=workstation,
        from_date=from_date,
        to_date=to_date,
        search=search,
        company=company,
        only_shortage=only_shortage,
    )


@frappe.whitelist()
def get_material_shortage_report(
    shortage_filter: str = "all",
    warehouse: str | None = None,
    search: str | None = None,
    company: str | None = None,
) -> dict:
    """Retrieve material shortage report across active shortage-released Work Orders."""
    return get_material_shortage_report_service(
        shortage_filter=shortage_filter,
        warehouse=warehouse,
        search=search,
        company=company,
    )


_MANAGEMENT_STATUS_FILTERS = ("active", "cancelled", "all")


def _build_management_base_conditions(
    company: str | None = None,
) -> tuple[list[str], list]:
    """Build company and submitted/cancelled base SQL conditions for confirmation queries."""
    conditions = ["conf.docstatus IN (1, 2)"]
    params: list = []

    target_company = _resolve_target_company(company)
    if target_company:
        conditions.append("wo.company = %s")
        params.append(target_company)
    else:
        active_companies = frappe.get_all(
            "Company", filters={"is_group": 0}, pluck="name"
        )
        if active_companies:
            placeholders = ", ".join(["%s"] * len(active_companies))
            conditions.append(f"wo.company IN ({placeholders})")
            params.extend(active_companies)

    return conditions, params


def _append_management_non_status_filters(
    conditions: list[str],
    params: list,
    search: str | None = None,
    operation: str | None = None,
    confirmed_by: str | None = None,
    work_order: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> None:
    """Append optional non-status SQL filter clauses and bound parameters."""
    if search and str(search).strip():
        term = f"%{str(search).strip()}%"
        conditions.append(
            "(conf.name LIKE %s OR conf.work_order LIKE %s "
            "OR wo.production_item LIKE %s OR wo.item_name LIKE %s)"
        )
        params.extend([term, term, term, term])

    if operation and str(operation).strip():
        conditions.append("conf.operation = %s")
        params.append(str(operation).strip())

    if confirmed_by and str(confirmed_by).strip():
        conditions.append("conf.confirmed_by = %s")
        params.append(str(confirmed_by).strip())

    if work_order and str(work_order).strip():
        conditions.append("conf.work_order = %s")
        params.append(str(work_order).strip())

    if from_date and str(from_date).strip():
        conditions.append("conf.posting_date >= %s")
        params.append(str(from_date).strip())

    if to_date and str(to_date).strip():
        conditions.append("conf.posting_date <= %s")
        params.append(str(to_date).strip())


def _fetch_management_counts(where_sql: str, params: list) -> dict:
    """Fetch active, cancelled, and all confirmation counts for non-status filters."""
    row = frappe.db.sql(
        f"""
        SELECT
            SUM(CASE WHEN conf.docstatus = 1 THEN 1 ELSE 0 END) AS active_count,
            SUM(CASE WHEN conf.docstatus = 2 THEN 1 ELSE 0 END) AS cancelled_count,
            COUNT(*) AS all_count
        FROM `tabKTA Production Confirmation` conf
        INNER JOIN `tabWork Order` wo ON wo.name = conf.work_order
        WHERE {where_sql}
        """,
        tuple(params),
        as_dict=True,
    )
    agg = row[0] if row else {}
    return {
        "active": cint(agg.get("active_count") or 0),
        "cancelled": cint(agg.get("cancelled_count") or 0),
        "all": cint(agg.get("all_count") or 0),
    }


def _fetch_management_summary(where_sql: str, params: list) -> dict:
    """Fetch aggregate summary metrics over all matching rows for current status filter."""
    row = frappe.db.sql(
        f"""
        SELECT
            SUM(CASE WHEN conf.docstatus = 1 THEN 1 ELSE 0 END) AS active_confirmations,
            COUNT(DISTINCT conf.work_order) AS unique_work_orders,
            COALESCE(SUM(conf.yield_qty), 0) AS total_yield_qty
        FROM `tabKTA Production Confirmation` conf
        INNER JOIN `tabWork Order` wo ON wo.name = conf.work_order
        WHERE {where_sql}
        """,
        tuple(params),
        as_dict=True,
    )
    agg = row[0] if row else {}
    return {
        "active_confirmations": cint(agg.get("active_confirmations") or 0),
        "unique_work_orders": cint(agg.get("unique_work_orders") or 0),
        "total_yield_qty": flt(agg.get("total_yield_qty") or 0),
    }


def _fetch_management_filter_options(base_where_sql: str, base_params: list) -> dict:
    """Fetch distinct operation and user filter options within company scope."""
    op_rows = frappe.db.sql(
        f"""
        SELECT DISTINCT conf.operation
        FROM `tabKTA Production Confirmation` conf
        INNER JOIN `tabWork Order` wo ON wo.name = conf.work_order
        WHERE {base_where_sql} AND COALESCE(conf.operation, '') != ''
        """,
        tuple(base_params),
        as_dict=True,
    )
    operations = sorted(r["operation"] for r in op_rows if r.get("operation"))

    user_rows = frappe.db.sql(
        f"""
        SELECT DISTINCT
            conf.confirmed_by,
            COALESCE(NULLIF(u.full_name, ''), conf.confirmed_by) AS full_name
        FROM `tabKTA Production Confirmation` conf
        INNER JOIN `tabWork Order` wo ON wo.name = conf.work_order
        LEFT JOIN `tabUser` u ON u.name = conf.confirmed_by
        WHERE {base_where_sql} AND COALESCE(conf.confirmed_by, '') != ''
        """,
        tuple(base_params),
        as_dict=True,
    )
    users = sorted(
        [
            {
                "value": r["confirmed_by"],
                "label": r.get("full_name") or r["confirmed_by"],
            }
            for r in user_rows
            if r.get("confirmed_by")
        ],
        key=lambda item: (item["label"] or "").lower(),
    )
    return {"operations": operations, "users": users}


def _fetch_management_rows(where_sql: str, params: list, limit: int) -> list[dict]:
    """Fetch paginated confirmation management rows and attach linked Stock Entries."""
    rows = frappe.db.sql(
        f"""
        SELECT
            conf.name,
            conf.work_order,
            wo.production_item,
            wo.item_name,
            wo.stock_uom,
            wo.status AS wo_status,
            conf.operation,
            conf.job_card,
            conf.yield_qty,
            conf.posting_date,
            conf.posting_time,
            conf.confirmed_by,
            COALESCE(NULLIF(u.full_name, ''), conf.confirmed_by) AS confirmed_by_name,
            conf.is_final_confirmation,
            conf.docstatus,
            conf.milestone_confirmation,
            conf.stock_entry,
            conf.creation
        FROM `tabKTA Production Confirmation` conf
        INNER JOIN `tabWork Order` wo ON wo.name = conf.work_order
        LEFT JOIN `tabUser` u ON u.name = conf.confirmed_by
        WHERE {where_sql}
        ORDER BY conf.creation DESC, conf.name DESC
        LIMIT %s
        """,
        (*params, limit),
        as_dict=True,
    )

    for row in rows:
        row["yield_qty"] = flt(row.get("yield_qty") or 0)
        row["posting_date"] = (
            str(row.get("posting_date")) if row.get("posting_date") else ""
        )
        row["posting_time"] = (
            str(row.get("posting_time")) if row.get("posting_time") else ""
        )
        row["confirmed_by_name"] = (
            row.get("confirmed_by_name") or row.get("confirmed_by") or ""
        )
        row["is_final_confirmation"] = cint(row.get("is_final_confirmation") or 0)
        row["docstatus"] = cint(row.get("docstatus") or 0)
        row["creation"] = str(row.get("creation")) if row.get("creation") else ""

    return _attach_stock_entries_to_confirmations(rows)


@frappe.whitelist()
def get_confirmations_for_management(
    status_filter: str = "active",
    search: str | None = None,
    operation: str | None = None,
    confirmed_by: str | None = None,
    work_order: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    company: str | None = None,
    limit: int = 200,
) -> dict:
    """Retrieve production confirmations for Shopfloor Hub management & bulk reversal."""
    frappe.has_permission("KTA Production Confirmation", "read", throw=True)
    frappe.has_permission("Work Order", "read", throw=True)

    if status_filter not in _MANAGEMENT_STATUS_FILTERS:
        frappe.throw(
            _("Geçersiz durum filtresi: {0}").format(status_filter),
            frappe.ValidationError,
        )

    base_conditions, base_params = _build_management_base_conditions(company=company)
    non_status_conditions = list(base_conditions)
    non_status_params = list(base_params)
    _append_management_non_status_filters(
        non_status_conditions,
        non_status_params,
        search=search,
        operation=operation,
        confirmed_by=confirmed_by,
        work_order=work_order,
        from_date=from_date,
        to_date=to_date,
    )

    non_status_where = " AND ".join(non_status_conditions)
    counts = _fetch_management_counts(non_status_where, non_status_params)

    full_conditions = list(non_status_conditions)
    if status_filter == "active":
        full_conditions.append("conf.docstatus = 1")
    elif status_filter == "cancelled":
        full_conditions.append("conf.docstatus = 2")
    full_where = " AND ".join(full_conditions)

    resolved_limit = max(1, min(cint(limit) or 200, 500))
    rows = _fetch_management_rows(full_where, non_status_params, resolved_limit)
    summary = _fetch_management_summary(full_where, non_status_params)
    filter_options = _fetch_management_filter_options(
        " AND ".join(base_conditions), base_params
    )

    return {
        "rows": rows,
        "counts": counts,
        "total_count": counts[status_filter],
        "summary": summary,
        "filter_options": filter_options,
        "can_cancel": ReversalService.can_cancel_confirmations(frappe.session.user),
    }


@frappe.whitelist()
def get_line_deficits(
    target_warehouse: str, sourcing_strategy: str | None = None
) -> list[dict]:
    """API endpoint to get central warehouse reservation deficits for a target WIP warehouse."""
    frappe.has_permission("Work Order", "read", throw=True)
    return get_line_reservation_deficits(target_warehouse)
