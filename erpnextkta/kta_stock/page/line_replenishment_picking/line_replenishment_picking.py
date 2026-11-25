# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from erpnextkta.kta_stock.line_replenishment_service import (
    _PICKING_ALLOWED_ROLES,
    _require_replenishment_picking_access,
)
from frappe import _
from frappe.utils import flt


def get_context(context):
    """Context and permission gate for Line Replenishment Mobile PDA Picking."""
    user = getattr(frappe.session, "user", None)
    if not user or user == "Guest":
        frappe.throw(
            _("Bu sayfaya erişim yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )

    user_roles = set(frappe.get_roles(user))
    if not (
        user_roles.intersection(_PICKING_ALLOWED_ROLES)
        or frappe.has_permission("Stock Entry", "read")
        or frappe.has_permission("KTA Line Replenishment Order", "read")
    ):
        frappe.throw(
            _("Bu sayfaya erişim yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def get_open_replenishment_orders() -> list[dict]:
    """Retrieve all open line replenishment orders for PDA picking."""
    _require_replenishment_picking_access()
    return frappe.get_all(
        "KTA Line Replenishment Order",
        filters={"status": ["in", ["Draft", "In Progress"]]},
        fields=[
            "name",
            "target_warehouse",
            "status",
            "total_deficit_qty",
            "creation",
        ],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_replenishment_order_details(order_name: str | None = None) -> dict | None:
    """Retrieve full line replenishment order details with item picking status."""
    _require_replenishment_picking_access()
    if not order_name:
        return None

    order = frappe.get_doc("KTA Line Replenishment Order", order_name)
    items_data = []
    for row in order.items:
        items_data.append(
            {
                "name": row.name,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "uom": row.uom,
                "deficit_qty": flt(row.deficit_qty),
                "picked_qty": flt(row.picked_qty) or flt(row.deficit_qty),
                "is_picked": int(row.is_picked or 0),
                "suggested_source_warehouse": row.suggested_source_warehouse,
                "suggested_batch_no": row.suggested_batch_no,
                "picked_source_warehouse": row.picked_source_warehouse,
                "picked_batch_no": row.picked_batch_no,
            }
        )

    return {
        "name": order.name,
        "target_warehouse": order.target_warehouse,
        "status": order.status,
        "company": order.company,
        "total_deficit_qty": flt(order.total_deficit_qty),
        "items": items_data,
    }


@frappe.whitelist()
def resolve_scanned_barcode(barcode: str | None = None) -> dict:
    """Resolve a scanned barcode string into item_code, batch_no, and quantity.

    Checks:
    1. Direct Item Code match
    2. KTA Stock Label (sut_barcode or document name)
    3. Batch record (name or batch_id)
    4. Item Barcode child table match
    """
    clean_code = (barcode or "").strip()
    _require_replenishment_picking_access()
    if not clean_code:
        return {"item_code": None, "batch_no": None, "qty": 0.0}

    # 1. Direct Item Code
    if frappe.db.exists("Item", clean_code):
        return {
            "item_code": clean_code,
            "batch_no": None,
            "qty": 0.0,
            "source": "Item",
        }

    # 2. KTA Stock Label lookup
    label = frappe.db.get_value(
        "KTA Stock Label",
        {"sut_barcode": clean_code},
        ["name", "item_code", "batch", "qty"],
        as_dict=True,
    )
    if not label:
        label = frappe.db.get_value(
            "KTA Stock Label",
            {"name": clean_code},
            ["name", "item_code", "batch", "qty"],
            as_dict=True,
        )

    if label:
        return {
            "item_code": label.item_code,
            "batch_no": label.batch,
            "qty": flt(label.qty),
            "label_name": label.name,
            "source": "KTA Stock Label",
        }

    # 3. Batch lookup
    batch = frappe.db.get_value(
        "Batch",
        clean_code,
        ["name", "item"],
        as_dict=True,
    )
    if not batch:
        batch = frappe.db.get_value(
            "Batch",
            {"batch_id": clean_code},
            ["name", "item"],
            as_dict=True,
        )

    if batch:
        return {
            "item_code": batch.item,
            "batch_no": batch.name,
            "qty": 0.0,
            "source": "Batch",
        }

    # 4. Item Barcode lookup
    item_barcode = frappe.db.get_value(
        "Item Barcode",
        {"barcode": clean_code},
        ["parent"],
        as_dict=True,
    )
    if item_barcode:
        return {
            "item_code": item_barcode.parent,
            "batch_no": None,
            "qty": 0.0,
            "source": "Item Barcode",
        }

    return {"item_code": None, "batch_no": None, "qty": 0.0}
