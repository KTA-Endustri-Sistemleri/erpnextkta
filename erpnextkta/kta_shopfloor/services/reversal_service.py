# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnextkta.kta_shopfloor.services.confirmation_service import ConfirmationService

ALLOWED_REVERSAL_ROLES = {
    "System Manager",
    "KTA Çalışma Kartı Yöneticisi",
    "Manufacturing Manager",
}


class ReversalService:
    """Service handling Shopfloor CORS (Cancel Confirmation) reversal logic.

    Cancels linked Stock Entries, rolls back Job Card and Work Order quantities,
    and marks KTA Production Confirmation document as cancelled.
    """

    @staticmethod
    def cancel_confirmation(confirmation_name: str, user: str | None = None) -> dict:
        _check_permission(user)

        if not confirmation_name or not frappe.db.exists(
            "KTA Production Confirmation", confirmation_name
        ):
            frappe.throw(
                _("Üretim teyidi bulunamadı: {0}").format(confirmation_name),
                frappe.ValidationError,
            )

        conf_doc = frappe.get_doc("KTA Production Confirmation", confirmation_name)

        if conf_doc.docstatus == 2:
            frappe.throw(
                _("Üretim teyidi zaten iptal edilmiş: {0}").format(confirmation_name),
                frappe.ValidationError,
            )

        if conf_doc.docstatus != 1:
            frappe.throw(
                _(
                    "Yalnızca onaylanmış (teslim edilmiş) teyitler iptal edilebilir: {0}"
                ).format(confirmation_name),
                frappe.ValidationError,
            )

        savepoint_name = f"cors_{frappe.generate_hash(length=10)}"

        try:
            frappe.db.savepoint(savepoint_name)

            yield_qty = flt(conf_doc.yield_qty)
            wo_name = conf_doc.work_order
            operation = conf_doc.operation
            job_card_name = conf_doc.job_card

            wo_produced_before = (
                flt(frappe.db.get_value("Work Order", wo_name, "produced_qty"))
                if wo_name
                else 0.0
            )

            # 1. Cancel linked Stock Entries
            cancelled_stock_entries = _cancel_linked_stock_entries(conf_doc)

            # 2. Cancel KTA Production Confirmation document (marks docstatus=2 so get_operation_quantities reflects cancellation)
            conf_doc.flags.ignore_permissions = True
            conf_doc.flags.ignore_links = True
            conf_doc.cancel()

            # 2b. Cancel associated catchup confirmations for preceding operations
            cancelled_catchups = _cancel_catchup_confirmations(
                conf_doc, cancelled_stock_entries
            )

            # 3. Rollback Job Card completed quantity & status
            _rollback_job_card(job_card_name, wo_name, operation, yield_qty)
            for c_doc in cancelled_catchups:
                _rollback_job_card(
                    c_doc.job_card,
                    c_doc.work_order,
                    c_doc.operation,
                    flt(c_doc.yield_qty),
                )

            # 4. Rollback Work Order Operation & Work Order produced quantity / status
            if wo_name and frappe.db.exists("Work Order", wo_name):
                wo = frappe.get_doc("Work Order", wo_name)
                for c_doc in cancelled_catchups:
                    _rollback_work_order_progress(
                        wo, c_doc.operation, flt(c_doc.yield_qty), wo_produced_before
                    )
                _rollback_work_order_progress(
                    wo, operation, yield_qty, wo_produced_before
                )

            frappe.db.release_savepoint(savepoint_name)

            primary_se = conf_doc.stock_entry or (
                cancelled_stock_entries[0] if cancelled_stock_entries else None
            )

            return {
                "success": True,
                "confirmation": confirmation_name,
                "cancelled_stock_entry": primary_se,
                "cancelled_stock_entries": cancelled_stock_entries,
                "cancelled_catchup_confirmations": [c.name for c in cancelled_catchups],
            }

        except Exception:
            frappe.db.rollback(save_point=savepoint_name)
            raise


@frappe.whitelist()
def cancel_confirmation(confirmation_name: str, user: str | None = None) -> dict:
    """Whitelisted endpoint and function alias for CORS production confirmation cancellation."""
    return ReversalService.cancel_confirmation(
        confirmation_name=confirmation_name, user=user
    )


def _check_permission(user: str | None = None) -> None:
    target_user = user or frappe.session.user or "Administrator"
    user_roles = set(frappe.get_roles(target_user))

    if not (target_user == "Administrator" or (user_roles & ALLOWED_REVERSAL_ROLES)):
        frappe.throw(
            _("Üretim teyidini iptal etme yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )


def _cancel_linked_stock_entries(conf_doc) -> list[str]:
    stock_entries_to_cancel: list[str] = []

    # Direct reference on confirmation document
    if (
        conf_doc.stock_entry
        and frappe.db.exists("Stock Entry", conf_doc.stock_entry)
        and frappe.db.get_value("Stock Entry", conf_doc.stock_entry, "docstatus") == 1
    ):
        stock_entries_to_cancel.append(conf_doc.stock_entry)

    # Reference via custom_confirmation column if present
    if frappe.db.has_column("Stock Entry", "custom_confirmation"):
        custom_entries = frappe.get_all(
            "Stock Entry",
            filters={"custom_confirmation": conf_doc.name, "docstatus": 1},
            pluck="name",
        )
        for se_name in custom_entries:
            if se_name not in stock_entries_to_cancel:
                stock_entries_to_cancel.append(se_name)

    # Reference via remarks containing confirmation name
    remarks_entries = frappe.get_all(
        "Stock Entry",
        filters={"remarks": ["like", f"%{conf_doc.name}%"], "docstatus": 1},
        pluck="name",
    )
    for se_name in remarks_entries:
        if se_name not in stock_entries_to_cancel:
            stock_entries_to_cancel.append(se_name)

    cancelled: list[str] = []
    for se_name in stock_entries_to_cancel:
        se = frappe.get_doc("Stock Entry", se_name)
        if se.docstatus == 1:
            se.flags.ignore_permissions = True
            se.flags.ignore_links = True
            se.cancel()
            cancelled.append(se_name)

    return cancelled


def _cancel_catchup_confirmations(conf_doc, cancelled_stock_entries: list[str]) -> list:
    """Find and cancel any preceding operation catchup confirmations associated with this confirmation."""
    wo_name = conf_doc.work_order
    if not wo_name:
        return []

    catchup_names: set[str] = set()

    # 1. By milestone_confirmation link if column exists
    if frappe.db.has_column("KTA Production Confirmation", "milestone_confirmation"):
        linked = frappe.get_all(
            "KTA Production Confirmation",
            filters={
                "work_order": wo_name,
                "milestone_confirmation": conf_doc.name,
                "docstatus": 1,
            },
            pluck="name",
        )
        for name in linked:
            if name != conf_doc.name:
                catchup_names.add(name)

    # 2. By stock_entry in cancelled_stock_entries (e.g. shared consumption stock entry)
    if cancelled_stock_entries:
        se_linked = frappe.get_all(
            "KTA Production Confirmation",
            filters={
                "work_order": wo_name,
                "stock_entry": ["in", cancelled_stock_entries],
                "docstatus": 1,
            },
            pluck="name",
        )
        for name in se_linked:
            if name != conf_doc.name:
                catchup_names.add(name)

    cancelled_docs = []
    for c_name in catchup_names:
        c_doc = frappe.get_doc("KTA Production Confirmation", c_name)
        if c_doc.docstatus == 1:
            if (
                c_doc.stock_entry
                and frappe.db.exists("Stock Entry", c_doc.stock_entry)
                and frappe.db.get_value("Stock Entry", c_doc.stock_entry, "docstatus")
                == 1
            ):
                se = frappe.get_doc("Stock Entry", c_doc.stock_entry)
                se.flags.ignore_permissions = True
                se.flags.ignore_links = True
                se.cancel()
                if c_doc.stock_entry not in cancelled_stock_entries:
                    cancelled_stock_entries.append(c_doc.stock_entry)

            c_doc.flags.ignore_permissions = True
            c_doc.flags.ignore_links = True
            c_doc.cancel()
            cancelled_docs.append(c_doc)

    return cancelled_docs


def _rollback_job_card(
    job_card_name: str | None,
    wo_name: str,
    operation: str,
    yield_qty: float,
) -> None:
    if not job_card_name and wo_name and operation:
        job_card_name = frappe.db.get_value(
            "Job Card",
            {"work_order": wo_name, "operation": operation},
            "name",
        )

    if not job_card_name or not frappe.db.exists("Job Card", job_card_name):
        return

    jc_docstatus = frappe.db.get_value("Job Card", job_card_name, "docstatus")
    if jc_docstatus != 0:
        return

    current_qty = flt(
        frappe.db.get_value("Job Card", job_card_name, "total_completed_qty")
    )
    for_qty = flt(frappe.db.get_value("Job Card", job_card_name, "for_quantity"))
    current_status = frappe.db.get_value("Job Card", job_card_name, "status")

    new_qty = max(0.0, current_qty - yield_qty)
    vals = {"total_completed_qty": new_qty}

    if current_status == "Completed" and (not for_qty or new_qty < for_qty):
        vals["status"] = "Work In Progress" if new_qty > 0 else "Open"
    elif new_qty == 0.0 and current_status == "Work In Progress":
        vals["status"] = "Open"

    frappe.db.set_value("Job Card", job_card_name, vals)


def _rollback_work_order_progress(
    wo, operation: str, yield_qty: float, wo_produced_before: float
) -> None:
    wo_qty = flt(wo.qty)

    # 1. Rollback operation completed quantity and status using single source of truth
    op_qtys = ConfirmationService.get_operation_quantities(wo, operation)
    for op in wo.get("operations") or []:
        if op.operation == operation:
            op_vals = {
                "completed_qty": op_qtys["completed_qty"],
                "status": op_qtys["status"],
            }
            frappe.db.set_value("Work Order Operation", op.name, op_vals)
            op.completed_qty = op_qtys["completed_qty"]
            op.status = op_qtys["status"]
            break

    # 2. Rollback milestone / finished goods progress
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

    if is_milestone:
        wo_produced_after = flt(
            frappe.db.get_value("Work Order", wo.name, "produced_qty")
        )
        if wo_produced_after == wo_produced_before:
            # Stock Entry cancellation did not decrement produced_qty directly
            new_produced = max(0.0, wo_produced_before - yield_qty)
            frappe.db.set_value("Work Order", wo.name, "produced_qty", new_produced)
        else:
            new_produced = wo_produced_after

        wo_status = frappe.db.get_value("Work Order", wo.name, "status")
        if wo_status == "Completed" and (not wo_qty or new_produced < wo_qty):
            frappe.db.set_value("Work Order", wo.name, "status", "In Process")
