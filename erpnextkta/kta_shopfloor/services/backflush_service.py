# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe.utils import flt

from erpnextkta.overrides.company_wip_validation import (
    get_validated_wip_consumption_account,
)


def _row_get(row, fieldname: str):
    """Safely read a field from a Document or dict-like Stock Entry row."""
    if isinstance(row, dict):
        return row.get(fieldname)
    return getattr(row, fieldname, None)


def _row_set(row, fieldname: str, value) -> None:
    """Safely set a field on a Document or dict-like Stock Entry row."""
    if isinstance(row, dict):
        row[fieldname] = value
    else:
        setattr(row, fieldname, value)


def _apply_wip_account_to_fg_only_items(se, wip_account: str | None) -> None:
    """Set expense_account on incoming FG/scrap rows when Stock Entry is FG-only."""
    items = getattr(se, "items", None)
    if not wip_account or not items:
        return

    has_source = any(bool(_row_get(d, "s_warehouse")) for d in items)
    has_target = any(bool(_row_get(d, "t_warehouse")) for d in items)
    if has_source or not has_target:
        return

    for d in items:
        if _row_get(d, "t_warehouse"):
            _row_set(d, "expense_account", wip_account)


class BackflushService:
    """Service handling proportional BOM raw material backflushing, FIFO allocation

    and finished goods stock entry creation for production confirmations (CO11N).
    """

    @staticmethod
    def calculate_operation_raw_materials(
        work_order,
        operation: str,
        yield_qty: float,
        is_final: bool = False,
        target_op_qty: float | None = None,
    ) -> list[dict]:
        """Calculates raw material quantities to be consumed for a specific operation confirmation.

        Rules:
        1. Proportional formula: (yield_qty / wo.qty) * required_qty for raw materials assigned to operation.
        2. If is_final is True or this is the final milestone operation, also include BOM items
           where operation is null/empty (unassigned general consumables).
        3. If is_milestone is True, also auto-catchup raw materials of preceding intermediate operations
           where consumed_qty < target_consumed.
        4. If is_final is True, calculate remaining unconsumed balance so rounding differences
           are closed: remaining = flt(d.required_qty) - flt(d.consumed_qty).
        """
        if isinstance(work_order, str):
            wo = frappe.get_doc("Work Order", work_order)
        else:
            wo = work_order

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

        current_op = None
        for op in sorted_ops:
            if (getattr(op, "operation", None) or op.get("operation")) == operation:
                current_op = op
                break

        curr_idx = (
            (getattr(current_op, "idx", None) or current_op.get("idx") or 0)
            if current_op
            else 0
        )
        curr_pos = sorted_ops.index(current_op) if current_op in sorted_ops else -1

        preceding_op_names = set()
        if current_op and is_milestone:
            for idx_pos, op in enumerate(sorted_ops):
                op_idx = getattr(op, "idx", None) or op.get("idx") or 0
                if idx_pos < curr_pos or op_idx < curr_idx:
                    op_name = getattr(op, "operation", None) or op.get("operation")
                    if op_name:
                        preceding_op_names.add(op_name)

        wo_qty = flt(wo.get("qty")) or 1.0
        precision = frappe.get_precision("Stock Entry Detail", "qty") or 4
        fallback_wh = (
            wo.get("source_warehouse")
            if (wo.get("skip_transfer") and not wo.get("from_wip_warehouse"))
            else wo.get("wip_warehouse")
        )

        if target_op_qty is not None:
            target_cumulative_qty = flt(target_op_qty)
        elif is_final:
            target_cumulative_qty = wo_qty
        else:
            op_completed = (
                flt(
                    (
                        current_op.get("completed_qty")
                        if isinstance(current_op, dict)
                        else getattr(current_op, "completed_qty", 0)
                    )
                    or 0
                )
                if current_op
                else 0.0
            )
            target_cumulative_qty = op_completed + flt(yield_qty)

        target_cumulative_qty = min(wo_qty, target_cumulative_qty)

        result: list[dict] = []
        for d in wo.get("required_items") or []:
            item_op = d.get("operation")
            required_qty = flt(d.get("required_qty"))
            consumed_qty = flt(d.get("consumed_qty"))

            if item_op == operation or (not item_op and is_milestone):
                if is_final:
                    item_qty = required_qty - consumed_qty
                else:
                    item_qty = flt(
                        (flt(yield_qty) / wo_qty) * required_qty,
                        precision,
                    )
            elif is_milestone and item_op in preceding_op_names:
                already_consumed = consumed_qty
                if is_final:
                    item_qty = max(0.0, required_qty - already_consumed)
                else:
                    target_consumed = flt(
                        (target_cumulative_qty / wo_qty) * required_qty,
                        precision,
                    )
                    item_qty = max(0.0, target_consumed - already_consumed)
            else:
                continue

            if is_final:
                item_qty = flt(item_qty, max(precision, 4))
            else:
                item_qty = flt(item_qty, precision)
            if item_qty <= 0:
                continue

            src_wh = d.get("source_warehouse") or fallback_wh

            result.append(
                {
                    "item_code": d.get("item_code"),
                    "item_name": d.get("item_name") or d.get("item_code"),
                    "description": d.get("description") or "",
                    "qty": item_qty,
                    "required_qty": required_qty,
                    "consumed_qty": consumed_qty,
                    "stock_uom": d.get("stock_uom"),
                    "uom": d.get("uom") or d.get("stock_uom"),
                    "conversion_factor": 1.0,
                    "source_warehouse": src_wh,
                    "s_warehouse": src_wh,
                    "operation": item_op,
                    "original_item": d.get("custom_original_item"),
                    "custom_original_item": d.get("custom_original_item"),
                }
            )

        return result

    @staticmethod
    def create_consumption_entry(
        work_order,
        operation: str,
        yield_qty: float,
        is_final: bool = False,
        confirmation_name: str | None = None,
        target_op_qty: float | None = None,
    ) -> str | None:
        """Creates and submits a Material Consumption Stock Entry for an operation confirmation.

        Returns None if no raw materials are assigned/needed (e.g. pure inspection/test).
        """
        if isinstance(work_order, str):
            wo = frappe.get_doc("Work Order", work_order)
        else:
            wo = work_order

        raw_materials = BackflushService.calculate_operation_raw_materials(
            wo, operation, yield_qty, is_final=is_final, target_op_qty=target_op_qty
        )
        if not raw_materials:
            return None

        wo_name = wo.name if hasattr(wo, "name") else wo.get("name")
        company = wo.company if hasattr(wo, "company") else wo.get("company")
        bom_no = wo.bom_no if hasattr(wo, "bom_no") else wo.get("bom_no")
        use_multi_level_bom = (
            wo.use_multi_level_bom
            if hasattr(wo, "use_multi_level_bom")
            else wo.get("use_multi_level_bom")
        )
        fallback_wh = (
            wo.get("source_warehouse")
            if (wo.get("skip_transfer") and not wo.get("from_wip_warehouse"))
            else wo.get("wip_warehouse")
        )

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Consumption for Manufacture"
        se.stock_entry_type = "Material Consumption for Manufacture"
        se.work_order = wo_name
        se.company = company
        se.from_bom = 1
        se.bom_no = bom_no
        se.use_multi_level_bom = use_multi_level_bom
        se.fg_completed_qty = flt(yield_qty)
        se.from_warehouse = fallback_wh

        if confirmation_name:
            if hasattr(se, "meta") and se.meta.has_field("custom_confirmation"):
                se.custom_confirmation = confirmation_name
            se.remarks = f"KTA Production Confirmation: {confirmation_name}"

        wip_account = get_validated_wip_consumption_account(company)

        for rm in raw_materials:
            item_row = {
                "item_code": rm["item_code"],
                "item_name": rm.get("item_name"),
                "description": rm.get("description"),
                "qty": rm["qty"],
                "uom": rm.get("uom") or rm.get("stock_uom"),
                "stock_uom": rm.get("stock_uom"),
                "conversion_factor": rm.get("conversion_factor", 1.0),
                "s_warehouse": rm.get("s_warehouse") or rm.get("source_warehouse"),
                "t_warehouse": "",
                "original_item": rm.get("original_item"),
                "custom_original_item": rm.get("custom_original_item")
                or rm.get("original_item"),
            }
            if wip_account:
                item_row["expense_account"] = wip_account
            se.append("items", item_row)

        if hasattr(se, "set_stock_entry_type"):
            se.set_stock_entry_type()
        if hasattr(se, "calculate_rate_and_amount"):
            se.calculate_rate_and_amount(raise_error_if_no_rate=False)

        se.flags.ignore_permissions = True
        se.insert(ignore_permissions=True)
        se.submit()

        return se.name

    @staticmethod
    def create_finished_goods_entry(
        work_order,
        yield_qty: float,
        is_final: bool = False,
        confirmation_name: str | None = None,
    ) -> str:
        """Creates and submits a Manufacture Stock Entry to receive finished goods into fg_warehouse."""
        if isinstance(work_order, str):
            wo = frappe.get_doc("Work Order", work_order)
        else:
            wo = work_order

        wo_name = wo.name if hasattr(wo, "name") else wo.get("name")
        company = wo.company if hasattr(wo, "company") else wo.get("company")
        bom_no = wo.bom_no if hasattr(wo, "bom_no") else wo.get("bom_no")
        use_multi_level_bom = (
            wo.use_multi_level_bom
            if hasattr(wo, "use_multi_level_bom")
            else wo.get("use_multi_level_bom")
        )
        fg_warehouse = (
            wo.fg_warehouse if hasattr(wo, "fg_warehouse") else wo.get("fg_warehouse")
        )
        project = wo.project if hasattr(wo, "project") else wo.get("project")
        fallback_wh = (
            wo.get("source_warehouse")
            if (wo.get("skip_transfer") and not wo.get("from_wip_warehouse"))
            else wo.get("wip_warehouse")
        )

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Manufacture"
        se.stock_entry_type = "Manufacture"
        se.work_order = wo_name
        se.company = company
        se.from_bom = 1
        se.bom_no = bom_no
        se.use_multi_level_bom = use_multi_level_bom
        se.fg_completed_qty = flt(yield_qty)
        se.from_warehouse = fallback_wh
        se.to_warehouse = fg_warehouse
        se.project = project
        se.flags.kta_is_final_confirmation = bool(is_final)

        if confirmation_name:
            if hasattr(se, "meta") and se.meta.has_field("custom_confirmation"):
                se.custom_confirmation = confirmation_name
            se.remarks = f"KTA Production Confirmation: {confirmation_name}"

        if hasattr(se, "set_stock_entry_type"):
            se.set_stock_entry_type()
        if hasattr(se, "get_items"):
            se.get_items()

        # If raw materials were already consumed via consumption entries, retain only FG & scrap
        if getattr(se, "items", None):
            has_consumption = frappe.db.exists(
                "Stock Entry",
                {
                    "work_order": wo_name,
                    "purpose": "Material Consumption for Manufacture",
                    "docstatus": 1,
                },
            )
            if has_consumption:
                se.items = [
                    d
                    for d in se.items
                    if getattr(d, "is_finished_item", 0)
                    or getattr(d, "is_scrap_item", 0)
                ]

        # Ensure finished goods item exists if get_items didn't populate items (e.g. WO without BOM)
        if not getattr(se, "items", None):
            prod_item = (
                wo.production_item
                if hasattr(wo, "production_item")
                else wo.get("production_item")
            )
            item_doc = (
                frappe.get_cached_doc("Item", prod_item)
                if frappe.db.exists("Item", prod_item)
                else None
            )
            val_rate = (
                flt(getattr(item_doc, "valuation_rate", 0))
                or flt(frappe.db.get_value("Item", prod_item, "valuation_rate"))
                or 1.0
            )
            se.append(
                "items",
                {
                    "item_code": prod_item,
                    "item_name": getattr(item_doc, "item_name", None) or prod_item,
                    "description": getattr(item_doc, "description", None) or "",
                    "qty": flt(yield_qty),
                    "transfer_qty": flt(yield_qty),
                    "stock_uom": getattr(item_doc, "stock_uom", None) or "Nos",
                    "uom": getattr(item_doc, "stock_uom", None) or "Nos",
                    "conversion_factor": 1.0,
                    "t_warehouse": fg_warehouse,
                    "is_finished_item": 1,
                    "basic_rate": val_rate,
                    "allow_zero_valuation_rate": 1,
                },
            )

        wip_account = get_validated_wip_consumption_account(company)
        _apply_wip_account_to_fg_only_items(se, wip_account)

        if hasattr(se, "calculate_rate_and_amount"):
            se.calculate_rate_and_amount(raise_error_if_no_rate=False)

        se.flags.ignore_permissions = True
        se.insert(ignore_permissions=True)
        se.submit()

        return se.name

    @staticmethod
    def cancel_consumption_entries(
        work_order: str, confirmation_name: str | None = None
    ) -> list[str]:
        """Cancels Material Consumption Stock Entries linked to the given confirmation or work order."""
        filters = {
            "work_order": work_order,
            "purpose": "Material Consumption for Manufacture",
            "docstatus": 1,
        }
        if confirmation_name:
            has_conf_field = frappe.db.has_column("Stock Entry", "custom_confirmation")
            if has_conf_field:
                filters["custom_confirmation"] = confirmation_name
            else:
                filters["remarks"] = ["like", f"%{confirmation_name}%"]

        cancelled = []
        entries = frappe.get_all("Stock Entry", filters=filters, pluck="name")
        for se_name in entries:
            se = frappe.get_doc("Stock Entry", se_name)
            se.cancel()
            cancelled.append(se_name)

        return cancelled


# Convenient module-level aliases
calculate_operation_raw_materials = BackflushService.calculate_operation_raw_materials
create_consumption_entry = BackflushService.create_consumption_entry
create_finished_goods_entry = BackflushService.create_finished_goods_entry
cancel_consumption_entries = BackflushService.cancel_consumption_entries
