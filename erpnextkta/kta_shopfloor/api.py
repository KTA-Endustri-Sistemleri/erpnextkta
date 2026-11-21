# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from erpnextkta.kta_shopfloor.services.confirmation_service import (
    ConfirmationService,
    _resolve_job_card,
)
from erpnextkta.kta_shopfloor.services.line_transfer_service import (
    execute_line_transfer,
    execute_production_supply_return,
    get_line_idle_stock,
    get_line_transfer_deficits,
    get_production_warehouses,
    search_line_transfer_items,
)
from erpnextkta.kta_shopfloor.services.line_transfer_service import (
    get_raw_material_return_warehouses as _get_raw_material_return_warehouses,
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
    allow_reserved_override: int = 0,
) -> dict:
    """Create and submit a Material Transfer for Manufacture Stock Entry to replenish line stock."""
    return ConfirmationService.stage_confirmation_materials(
        work_order=work_order,
        transfers=transfers,
        allow_reserved_override=allow_reserved_override,
    )


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

    # Pre-fetch all Stock Entries related to this Work Order
    se_list = frappe.get_all(
        "Stock Entry",
        filters={"work_order": work_order},
        fields=["name", "purpose", "remarks"],
        order_by="creation asc",
    )

    for conf in confirmations:
        conf_name = conf["name"]
        linked_se = conf.get("stock_entry")

        matched_entries = []
        seen_se_names = set()

        for se in se_list:
            remarks = se.get("remarks") or ""
            is_match = (conf_name in remarks) or (
                bool(linked_se) and se["name"] == linked_se
            )
            if is_match and se["name"] not in seen_se_names:
                seen_se_names.add(se["name"])
                purpose = se.get("purpose")
                is_consumption = purpose == "Material Consumption for Manufacture"
                matched_entries.append(
                    {
                        "name": se["name"],
                        "purpose": purpose,
                        "type": "consumption" if is_consumption else "manufacture",
                        "label": _("Tüketim") if is_consumption else _("Üretim"),
                    }
                )

        if linked_se and linked_se not in seen_se_names:
            se_doc = frappe.db.get_value(
                "Stock Entry", linked_se, ["name", "purpose"], as_dict=True
            )
            if se_doc:
                seen_se_names.add(se_doc.name)
                purpose = se_doc.purpose
                is_consumption = purpose == "Material Consumption for Manufacture"
                matched_entries.append(
                    {
                        "name": se_doc.name,
                        "purpose": purpose,
                        "type": "consumption" if is_consumption else "manufacture",
                        "label": _("Tüketim") if is_consumption else _("Üretim"),
                    }
                )

        conf["yield_qty"] = flt(conf.get("yield_qty") or 0)
        conf["stock_entries"] = matched_entries

    return confirmations


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
def get_line_deficits(
    target_warehouse: str, sourcing_strategy: str | None = None
) -> list[dict]:
    """API endpoint to get central warehouse reservation deficits for a target WIP warehouse."""
    frappe.has_permission("Work Order", "read", throw=True)
    return get_line_reservation_deficits(target_warehouse)


@frappe.whitelist()
def get_shopfloor_production_warehouses(company: str | None = None) -> list[dict]:
    """API endpoint to list valid production line warehouses for line transfers."""
    frappe.has_permission("Work Order", "read", throw=True)
    return get_production_warehouses(company=company)


@frappe.whitelist()
def get_shopfloor_line_deficits(target_warehouse: str) -> list[dict]:
    """API endpoint to get target line deficits coverable from sibling production lines."""
    frappe.has_permission("Work Order", "read", throw=True)
    return get_line_transfer_deficits(target_warehouse)


@frappe.whitelist()
def get_shopfloor_idle_stock(source_warehouse: str) -> list[dict]:
    """API endpoint to get unreserved idle stock on a source production warehouse."""
    frappe.has_permission("Work Order", "read", throw=True)
    return get_line_idle_stock(source_warehouse)


@frappe.whitelist()
def search_shopfloor_transfer_items(
    source_warehouse: str,
    search: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """API endpoint to search stocked items inside a source production warehouse."""
    frappe.has_permission("Work Order", "read", throw=True)
    return search_line_transfer_items(
        source_warehouse=source_warehouse, search=search, limit=limit
    )


@frappe.whitelist()
def get_raw_material_return_warehouses(company: str | None = None) -> list[dict]:
    """API endpoint to list active 110 raw material return leaf shelves."""
    frappe.has_permission("Work Order", "read", throw=True)
    return _get_raw_material_return_warehouses(company=company)


@frappe.whitelist(methods=["POST"])
def execute_shopfloor_line_transfer(
    transfers: list[dict] | str,
    allow_reserved_override: int = 0,
    remarks: str | None = None,
    split_packages: int = 0,
) -> dict:
    """API endpoint to execute inter-line Material Transfer with LIFO batch resolution."""
    if not (
        frappe.has_permission("Stock Entry", "create")
        or frappe.has_permission("Work Order", "write")
    ):
        frappe.throw(
            _("Hat transferi oluşturma yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )
    return execute_line_transfer(
        transfers=transfers,
        allow_reserved_override=allow_reserved_override,
        remarks=remarks,
        split_packages=split_packages,
    )


@frappe.whitelist(methods=["POST"])
def execute_shopfloor_supply_return(
    items: list[dict] | str,
    target_warehouse: str,
    allow_reserved_override: int = 0,
    remarks: str | None = None,
) -> dict:
    """API endpoint to return idle line stock back to 110 raw material leaf shelves."""
    if not (
        frappe.has_permission("Stock Entry", "create")
        or frappe.has_permission("Work Order", "write")
    ):
        frappe.throw(
            _("Depo iadesi oluşturma yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )
    return execute_production_supply_return(
        items=items,
        target_warehouse=target_warehouse,
        allow_reserved_override=allow_reserved_override,
        remarks=remarks,
    )
