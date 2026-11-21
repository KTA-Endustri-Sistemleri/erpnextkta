# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate, nowtime

from erpnextkta.kta_shopfloor.services.backflush_service import BackflushService
from erpnextkta.kta_shopfloor.services.line_transfer_service import (
    execute_line_transfer,
    get_sibling_production_sources,
    is_valid_production_warehouse,
)


class ConfirmationService:
    """Core coordinator service for CO11N production confirmations."""

    @staticmethod
    def get_operation_quantities(wo_or_name, operation: str) -> dict:
        """Calculate normalized operation quantities using single source of truth.

        completed_qty = min(wo_qty, legacy_manufacture_qty + co11n_qty)
        pending_qty = max(0.0, wo_qty - completed_qty)
        """
        if isinstance(wo_or_name, str):
            wo_name = wo_or_name
            wo_qty = flt(frappe.db.get_value("Work Order", wo_name, "qty") or 0)
        elif hasattr(wo_or_name, "name"):
            wo_name = wo_or_name.name
            wo_qty = flt(getattr(wo_or_name, "qty", 0) or 0)
        elif isinstance(wo_or_name, dict):
            wo_name = wo_or_name.get("name")
            wo_qty = flt(wo_or_name.get("qty") or 0)
        else:
            wo_name = str(wo_or_name)
            wo_qty = flt(frappe.db.get_value("Work Order", wo_name, "qty") or 0)

        # 1. Confirmed CO11N confirmations for this WO and operation
        co11n_res = frappe.db.sql(
            """
            SELECT COALESCE(SUM(yield_qty), 0)
            FROM `tabKTA Production Confirmation`
            WHERE work_order = %s
              AND operation = %s
              AND docstatus = 1
            """,
            (wo_name, operation),
        )
        co11n_qty = flt(co11n_res[0][0]) if co11n_res else 0.0

        # 2. Confirmed standard Manufacture Stock Entries not generated via
        # KTA Production Confirmation
        legacy_res = frappe.db.sql(
            """
            SELECT COALESCE(SUM(fg_completed_qty), 0)
            FROM `tabStock Entry`
            WHERE work_order = %s
              AND purpose = 'Manufacture'
              AND docstatus = 1
              AND name NOT IN (
                  SELECT COALESCE(stock_entry, '')
                  FROM `tabKTA Production Confirmation`
                  WHERE work_order = %s
                    AND docstatus = 1
                    AND stock_entry IS NOT NULL
                    AND stock_entry != ''
              )
            """,
            (wo_name, wo_name),
        )
        legacy_manufacture_qty = flt(legacy_res[0][0]) if legacy_res else 0.0

        total_completed = legacy_manufacture_qty + co11n_qty
        completed_qty = min(wo_qty, total_completed) if wo_qty > 0 else total_completed
        pending_qty = max(0.0, wo_qty - completed_qty)

        if wo_qty > 0:
            if pending_qty <= 0:
                status = "Completed"
            elif completed_qty > 0:
                status = "Work In Progress"
            else:
                status = "Pending"
        else:
            status = "Completed" if completed_qty > 0 else "Pending"

        return {
            "completed_qty": completed_qty,
            "pending_qty": pending_qty,
            "status": status,
            "co11n_qty": co11n_qty,
            "legacy_manufacture_qty": legacy_manufacture_qty,
        }

    @staticmethod
    def confirm_operation(payload: dict | str | None = None, **kwargs) -> dict:
        data = _normalize_payload(payload, kwargs)
        _validate_payload(data)

        wo_name = data["work_order"]
        operation = data["operation"]
        yield_qty = flt(data["yield_qty"])
        is_final = bool(data.get("is_final_confirmation"))
        posting_date = data.get("posting_date") or nowdate()
        posting_time = data.get("posting_time") or nowtime()
        confirmed_by = (
            data.get("confirmed_by") or frappe.session.user or "Administrator"
        )

        wo = frappe.get_doc("Work Order", wo_name)
        job_card = data.get("job_card") or _resolve_job_card(wo_name, operation)

        ops = wo.get("operations") or []
        sorted_ops = sorted(
            ops,
            key=lambda d: (
                getattr(d, "sequence_id", None) or d.get("sequence_id") or 0,
                getattr(d, "idx", None) or d.get("idx") or 0,
            ),
        )
        is_last_op = bool(
            sorted_ops
            and (
                getattr(sorted_ops[-1], "operation", None)
                or sorted_ops[-1].get("operation")
            )
            == operation
        )
        is_milestone = is_last_op or not ops

        wo_produced_before = flt(
            frappe.db.get_value("Work Order", wo_name, "produced_qty")
        )
        savepoint_name = f"co11n_{frappe.generate_hash(length=10)}"

        try:
            frappe.db.savepoint(savepoint_name)

            target_op_qty = None
            catchup_confs = []
            if is_milestone:
                target_op_qty, catchup_confs = _auto_catchup_preceding_operations(
                    wo=wo,
                    sorted_ops=sorted_ops,
                    current_op_name=operation,
                    yield_qty=yield_qty,
                    is_final=is_final,
                    posting_date=posting_date,
                    posting_time=posting_time,
                    confirmed_by=confirmed_by,
                )

            conf_doc = _create_confirmation_doc(
                wo_name=wo_name,
                operation=operation,
                job_card=job_card,
                yield_qty=yield_qty,
                is_final=is_final,
                posting_date=posting_date,
                posting_time=posting_time,
                confirmed_by=confirmed_by,
            )
            conf_doc.flags.ignore_permissions = True
            conf_doc.flags.ignore_links = True
            conf_doc.submit()

            _update_operation_progress(wo, operation, yield_qty, is_final)
            _update_job_card_progress(job_card, yield_qty, is_final)

            if catchup_confs and frappe.db.has_column(
                "KTA Production Confirmation", "milestone_confirmation"
            ):
                for c_doc in catchup_confs:
                    c_doc.db_set("milestone_confirmation", conf_doc.name)
                    c_doc.milestone_confirmation = conf_doc.name

            consumption_se, fg_se, stock_entries = _trigger_backflush(
                wo=wo,
                operation=operation,
                yield_qty=yield_qty,
                is_final=is_final,
                is_milestone=is_milestone,
                conf_name=conf_doc.name,
                target_op_qty=target_op_qty,
            )

            stock_entry_name = fg_se or consumption_se
            if stock_entry_name:
                conf_doc.db_set("stock_entry", stock_entry_name)
                conf_doc.stock_entry = stock_entry_name

            if consumption_se and catchup_confs:
                for c_doc in catchup_confs:
                    c_doc.db_set("stock_entry", consumption_se)
                    c_doc.stock_entry = consumption_se

            _update_work_order_progress(
                wo, is_milestone, is_final, yield_qty, wo_produced_before
            )

            frappe.db.release_savepoint(savepoint_name)

            return {
                "success": True,
                "confirmation": conf_doc.name,
                "stock_entry": stock_entry_name,
                "consumption_stock_entry": consumption_se,
                "stock_entries": stock_entries,
                "catchup_confirmations": [c.name for c in catchup_confs],
                "is_final": is_final,
            }

        except Exception:
            frappe.db.rollback(save_point=savepoint_name)
            raise

    @staticmethod
    def check_confirmation_materials(
        work_order: str,
        operation: str,
        yield_qty: float,
        is_final_confirmation: int | bool = 0,
    ) -> dict:
        """Check line stock availability for raw materials to be consumed in this confirmation.

        Returns shortage status and available replenishment sources across other company warehouses.
        """
        if not work_order or not frappe.db.exists("Work Order", work_order):
            frappe.throw(
                _("Geçerli bir İş Emri zorunludur: {0}").format(work_order),
                frappe.ValidationError,
            )

        wo = frappe.get_doc("Work Order", work_order)
        wo.check_permission("read")

        yield_val = flt(yield_qty)
        is_final = bool(cint(is_final_confirmation))

        if yield_val <= 0:
            return {"has_shortage": False, "shortages": []}

        raw_materials = BackflushService.calculate_operation_raw_materials(
            wo, operation, yield_val, is_final=is_final
        )
        if not raw_materials:
            return {"has_shortage": False, "shortages": []}

        # Aggregate required quantities per (item_code, target_warehouse)
        aggregated: dict[tuple[str, str], dict] = {}
        for item in raw_materials:
            item_code = item.get("item_code")
            if not item_code:
                continue
            target_wh = (
                item.get("source_warehouse")
                or wo.get("source_warehouse")
                or wo.get("wip_warehouse")
            )
            if not target_wh:
                continue

            key = (item_code, target_wh)
            if key not in aggregated:
                aggregated[key] = {
                    "item_code": item_code,
                    "item_name": item.get("item_name") or item_code,
                    "target_warehouse": target_wh,
                    "required_qty": 0.0,
                    "stock_uom": item.get("stock_uom") or item.get("uom") or "Nos",
                }
            aggregated[key]["required_qty"] += flt(item.get("qty") or 0.0)

        shortages: list[dict] = []
        for (item_code, target_wh), data in aggregated.items():
            req_qty = flt(data["required_qty"], 4)
            actual_qty = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": item_code, "warehouse": target_wh},
                    "actual_qty",
                )
                or 0.0
            )

            if actual_qty < req_qty:
                shortage_qty = flt(req_qty - max(0.0, actual_qty), 4)
                prod_warehouses = get_sibling_production_sources(
                    item_code, wo.company, target_wh
                )

                best_source = prod_warehouses[0] if prod_warehouses else None
                suggested_source = best_source["warehouse"] if best_source else None
                suggested_avail = (
                    flt(best_source["free_qty"], 4) if best_source else 0.0
                )
                suggested_actual = (
                    flt(best_source["actual_qty"], 4) if best_source else 0.0
                )

                available_sources = [
                    {
                        "warehouse": w["warehouse"],
                        "actual_qty": flt(w["actual_qty"], 4),
                        "reserved_qty": flt(w["reserved_qty"], 4),
                        "free_qty": flt(w["free_qty"], 4),
                        "available_qty": flt(w["free_qty"], 4),
                    }
                    for w in prod_warehouses
                ]

                shortages.append(
                    {
                        "item_code": item_code,
                        "item_name": data["item_name"],
                        "required_qty": req_qty,
                        "line_actual_qty": flt(actual_qty, 4),
                        "shortage_qty": shortage_qty,
                        "target_warehouse": target_wh,
                        "source_warehouse": suggested_source,
                        "source_available_qty": suggested_avail,
                        "source_actual_qty": suggested_actual,
                        "available_sources": available_sources,
                        "stock_uom": data["stock_uom"],
                    }
                )

        return {
            "has_shortage": len(shortages) > 0,
            "shortages": shortages,
        }

    @staticmethod
    def stage_confirmation_materials(
        work_order: str,
        transfers: list[dict] | str,
        allow_reserved_override: int | bool = 0,
    ) -> dict:
        """Create and submit a Material Transfer for Manufacture Stock Entry to replenish line stock."""
        if not work_order or not frappe.db.exists("Work Order", work_order):
            frappe.throw(
                _("Geçerli bir İş Emri zorunludur: {0}").format(work_order),
                frappe.ValidationError,
            )

        wo = frappe.get_doc("Work Order", work_order)
        wo.check_permission("write")

        return execute_line_transfer(
            transfers=transfers,
            allow_reserved_override=allow_reserved_override,
            work_order=wo.name,
        )


@frappe.whitelist()
def confirm_operation(payload: dict | str | None = None, **kwargs) -> dict:
    """Whitelisted endpoint and function alias for CO11N production confirmation."""
    return ConfirmationService.confirm_operation(payload=payload, **kwargs)


@frappe.whitelist()
def check_confirmation_materials(
    work_order: str,
    operation: str,
    yield_qty: float,
    is_final_confirmation: int | bool = 0,
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
    allow_reserved_override: int | bool = 0,
) -> dict:
    """Create and submit a Material Transfer for Manufacture Stock Entry to replenish line stock."""
    return ConfirmationService.stage_confirmation_materials(
        work_order=work_order,
        transfers=transfers,
        allow_reserved_override=allow_reserved_override,
    )


def _normalize_payload(payload: dict | str | None, kwargs: dict) -> dict:
    if payload is None:
        data = dict(kwargs)
    elif isinstance(payload, str):
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            data = frappe.parse_json(payload) or {}
    elif isinstance(payload, dict):
        data = dict(payload)
    else:
        data = {}

    if kwargs:
        data.update(kwargs)
    return data


def _validate_payload(data: dict) -> None:
    if not data.get("work_order"):
        frappe.throw(
            _("İş Emri (work_order) zorunludur."),
            frappe.ValidationError,
        )

    if not frappe.db.exists("Work Order", data.get("work_order")):
        frappe.throw(
            _("İş Emri bulunamadı: {0}").format(data.get("work_order")),
            frappe.ValidationError,
        )

    if not data.get("operation"):
        frappe.throw(
            _("Operasyon (operation) zorunludur."),
            frappe.ValidationError,
        )

    if flt(data.get("yield_qty")) <= 0:
        frappe.throw(
            _("Sağlam Miktar (yield_qty) sıfırdan büyük olmalıdır."),
            frappe.ValidationError,
        )


def _resolve_job_card(work_order: str, operation: str) -> str | None:
    jc = frappe.db.get_value(
        "Job Card",
        {"work_order": work_order, "operation": operation, "docstatus": 0},
        "name",
        order_by="creation desc",
    )
    if jc:
        return jc

    return frappe.db.get_value(
        "Job Card",
        {"work_order": work_order, "operation": operation, "docstatus": ("<", 2)},
        "name",
        order_by="creation desc",
    )


def _create_confirmation_doc(
    wo_name: str,
    operation: str,
    job_card: str | None,
    yield_qty: float,
    is_final: bool,
    posting_date: str,
    posting_time: str,
    confirmed_by: str,
    milestone_confirmation: str | None = None,
):
    doc_data = {
        "doctype": "KTA Production Confirmation",
        "work_order": wo_name,
        "operation": operation,
        "job_card": job_card,
        "yield_qty": yield_qty,
        "is_final_confirmation": 1 if is_final else 0,
        "posting_date": posting_date,
        "posting_time": posting_time,
        "confirmed_by": confirmed_by,
    }
    if milestone_confirmation and frappe.db.has_column(
        "KTA Production Confirmation", "milestone_confirmation"
    ):
        doc_data["milestone_confirmation"] = milestone_confirmation

    conf = frappe.get_doc(doc_data)
    conf.flags.ignore_permissions = True
    conf.insert(ignore_permissions=True)
    return conf


def _auto_catchup_preceding_operations(
    wo,
    sorted_ops: list,
    current_op_name: str,
    yield_qty: float,
    is_final: bool,
    posting_date: str | None = None,
    posting_time: str | None = None,
    confirmed_by: str | None = None,
    milestone_conf_name: str | None = None,
) -> tuple[float, list]:
    """For milestone operations, automatically advance any preceding intermediate operations

    whose completed_qty is less than the new milestone target_qty by creating and submitting
    KTA Production Confirmation confirmations. Returns (target_qty, catchup_confs).
    """
    current_op = None
    for op in sorted_ops:
        if (getattr(op, "operation", None) or op.get("operation")) == current_op_name:
            current_op = op
            break

    wo_qty = flt(getattr(wo, "qty", 0) or 0)
    current_completed = (
        flt(getattr(current_op, "completed_qty", 0) or 0) if current_op else 0.0
    )
    if is_final:
        target_qty = wo_qty if wo_qty > 0 else (current_completed + flt(yield_qty))
    else:
        new_completed = current_completed + flt(yield_qty)
        target_qty = min(wo_qty, new_completed) if wo_qty > 0 else new_completed

    if not current_op:
        return target_qty, []

    curr_idx = getattr(current_op, "idx", None) or current_op.get("idx") or 0
    curr_pos = sorted_ops.index(current_op) if current_op in sorted_ops else 0
    catchup_confs = []

    wo_name = getattr(wo, "name", None) or (
        wo.get("name") if isinstance(wo, dict) else str(wo)
    )

    for idx_pos, prev_op in enumerate(sorted_ops):
        prev_idx = getattr(prev_op, "idx", None) or prev_op.get("idx") or 0
        if idx_pos >= curr_pos and prev_idx >= curr_idx:
            continue

        prev_op_name = getattr(prev_op, "operation", None) or (
            prev_op.get("operation") if isinstance(prev_op, dict) else None
        )
        if not prev_op_name:
            continue

        op_qtys = ConfirmationService.get_operation_quantities(wo, prev_op_name)
        prev_completed = flt(op_qtys["completed_qty"])

        if prev_completed < target_qty:
            catchup_delta = target_qty - prev_completed
            prev_jc = _resolve_job_card(wo_name, prev_op_name) if wo_name else None

            # 1. Create and submit KTA Production Confirmation document for the catchup delta
            catchup_doc = _create_confirmation_doc(
                wo_name=wo_name,
                operation=prev_op_name,
                job_card=prev_jc,
                yield_qty=catchup_delta,
                is_final=is_final,
                posting_date=posting_date or nowdate(),
                posting_time=posting_time or nowtime(),
                confirmed_by=confirmed_by or frappe.session.user or "Administrator",
                milestone_confirmation=milestone_conf_name,
            )
            catchup_doc.flags.ignore_permissions = True
            catchup_doc.flags.ignore_links = True
            catchup_doc.submit()
            catchup_confs.append(catchup_doc)

            # 2. Update Work Order Operation row
            _update_operation_progress(wo, prev_op_name, catchup_delta, is_final)

            # 3. Update Job Card progress
            if prev_jc:
                _update_job_card_progress(prev_jc, catchup_delta, is_final)

            # 4. In-memory op sync
            prev_status = "Completed" if target_qty >= wo_qty else "Work In Progress"
            if hasattr(prev_op, "completed_qty"):
                prev_op.completed_qty = target_qty
                prev_op.status = prev_status
            elif isinstance(prev_op, dict):
                prev_op["completed_qty"] = target_qty
                prev_op["status"] = prev_status

    return target_qty, catchup_confs


def _trigger_backflush(
    wo,
    operation: str,
    yield_qty: float,
    is_final: bool,
    is_milestone: bool,
    conf_name: str,
    target_op_qty: float | None = None,
) -> tuple[str | None, str | None, list[dict]]:
    consumption_se = None
    fg_se = None
    stock_entries = []

    if is_milestone:
        consumption_se = BackflushService.create_consumption_entry(
            wo,
            operation,
            yield_qty,
            is_final=is_final,
            confirmation_name=conf_name,
            target_op_qty=target_op_qty,
        )
        fg_se = BackflushService.create_finished_goods_entry(
            wo, yield_qty, is_final=is_final, confirmation_name=conf_name
        )
    else:
        consumption_se = BackflushService.create_consumption_entry(
            wo,
            operation,
            yield_qty,
            is_final=is_final,
            confirmation_name=conf_name,
            target_op_qty=target_op_qty,
        )

    if consumption_se:
        stock_entries.append(
            {
                "name": consumption_se,
                "purpose": "Material Consumption for Manufacture",
                "type": "consumption",
                "label": _("Tüketim"),
            }
        )
    if fg_se:
        stock_entries.append(
            {
                "name": fg_se,
                "purpose": "Manufacture",
                "type": "manufacture",
                "label": _("Üretim"),
            }
        )

    return consumption_se, fg_se, stock_entries


def _update_operation_progress(
    wo, operation: str, yield_qty: float, is_final: bool
) -> None:
    op_qtys = ConfirmationService.get_operation_quantities(wo, operation)
    new_completed = op_qtys["completed_qty"]
    status = "Completed" if is_final else op_qtys["status"]

    for d in wo.get("operations") or []:
        if d.operation == operation:
            vals = {"completed_qty": new_completed, "status": status}
            frappe.db.set_value("Work Order Operation", d.name, vals)
            d.completed_qty = new_completed
            d.status = status
            break


def _update_job_card_progress(
    job_card: str | None, yield_qty: float, is_final: bool
) -> None:
    if not job_card or not frappe.db.exists("Job Card", job_card):
        return

    jc_docstatus = frappe.db.get_value("Job Card", job_card, "docstatus")
    if jc_docstatus != 0:
        return

    current_qty = flt(frappe.db.get_value("Job Card", job_card, "total_completed_qty"))
    for_qty = flt(frappe.db.get_value("Job Card", job_card, "for_quantity"))
    current_status = frappe.db.get_value("Job Card", job_card, "status")

    new_qty = current_qty + yield_qty
    vals = {"total_completed_qty": new_qty}

    if is_final or (for_qty and new_qty >= for_qty):
        vals["status"] = "Completed"
    elif current_status in ("Open", "Pending"):
        vals["status"] = "Work In Progress"

    # IMPORTANT: Keep docstatus = 0 (Draft container), DO NOT submit Job Card
    frappe.db.set_value("Job Card", job_card, vals)


def _update_work_order_progress(
    wo,
    is_milestone: bool,
    is_final: bool,
    yield_qty: float,
    wo_produced_before: float,
) -> None:
    if is_milestone:
        current_produced = flt(
            frappe.db.get_value("Work Order", wo.name, "produced_qty")
        )
        if current_produced == wo_produced_before:
            # When Manufacture Stock Entry didn't increment produced_qty (e.g. mocked SE)
            current_produced = wo_produced_before + yield_qty
            frappe.db.set_value("Work Order", wo.name, "produced_qty", current_produced)

        wo_vals = {}
        if is_final or current_produced >= flt(wo.qty):
            wo_vals["status"] = "Completed"
        elif wo.status == "Not Started":
            wo_vals["status"] = "In Process"

        if wo_vals:
            frappe.db.set_value("Work Order", wo.name, wo_vals)
    else:
        if wo.status == "Not Started":
            frappe.db.set_value("Work Order", wo.name, "status", "In Process")


def _is_production_warehouse(
    warehouse: str | None, target_warehouse: str | None = None
) -> bool:
    """Delegate production warehouse validation to line_transfer_service."""
    return is_valid_production_warehouse(warehouse, peer_warehouse=target_warehouse)
