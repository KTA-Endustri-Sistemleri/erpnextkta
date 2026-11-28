# Copyright (c) 2026, KTA and Contributors
# See license.txt

import re

import frappe
from erpnextkta.kta_stock.line_replenishment_service import (
    _PICKING_ALLOWED_ROLES,
    _SKIP_ALLOWED_ROLES,
    _require_replenishment_picking_access,
)
from erpnextkta.kta_stock.services.relabeling_service import get_batch_ledger_balances
from frappe import _
from frappe.utils import cint, flt

_BALANCE_EPSILON = 1e-6


def _natural_shelf_sort_key(row: dict) -> tuple:
    """Sort picking rows by natural alphanumeric shelf name, keeping empty shelves last."""
    wh = (row.get("suggested_source_warehouse") or "").strip()
    if wh:
        parts = tuple(
            (0, int(part)) if part.isdigit() else (1, part.lower())
            for part in re.split(r"(\d+)", wh)
            if part
        )
        shelf_key = (0, parts)
    else:
        shelf_key = (1, ())
    return (
        shelf_key,
        row.get("item_code") or "",
        row.get("suggested_batch_no") or "",
        row.get("_orig_idx", 0),
    )


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
    """Retrieve full line replenishment order details with walk-order sorting and role flags."""
    _require_replenishment_picking_access()
    if not order_name:
        return None

    order = frappe.get_doc("KTA Line Replenishment Order", order_name)
    user_roles = set(frappe.get_roles(frappe.session.user))
    can_skip_items = bool(user_roles.intersection(_SKIP_ALLOWED_ROLES))

    item_codes = list({row.item_code for row in order.items if row.item_code})
    item_batch_map: dict[str, int] = {}
    if item_codes:
        item_batch_map = {
            d.name: cint(d.has_batch_no)
            for d in frappe.get_all(
                "Item",
                filters={"name": ["in", item_codes]},
                fields=["name", "has_batch_no"],
            )
        }

    items_data = []
    for idx, row in enumerate(order.items):
        is_skipped = cint(row.get("is_skipped"))
        picked_qty = (
            0.0 if is_skipped else (flt(row.picked_qty) or flt(row.deficit_qty))
        )
        items_data.append(
            {
                "name": row.name,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "uom": row.uom,
                "deficit_qty": flt(row.deficit_qty),
                "picked_qty": picked_qty,
                "is_picked": int(row.is_picked or 0),
                "is_skipped": is_skipped,
                "skipped_by": row.get("skipped_by"),
                "is_fifo_override": cint(row.get("is_fifo_override")),
                "has_batch_no": item_batch_map.get(row.item_code, 0),
                "suggested_source_warehouse": row.suggested_source_warehouse,
                "suggested_batch_no": row.suggested_batch_no,
                "picked_source_warehouse": row.picked_source_warehouse,
                "picked_batch_no": row.picked_batch_no,
                "_orig_idx": idx,
            }
        )

    items_data.sort(key=_natural_shelf_sort_key)
    for item in items_data:
        item.pop("_orig_idx", None)

    return {
        "name": order.name,
        "target_warehouse": order.target_warehouse,
        "status": order.status,
        "company": order.company,
        "total_deficit_qty": flt(order.total_deficit_qty),
        "can_skip_items": can_skip_items,
        "items": items_data,
    }


def _enrich_barcode_with_live_balances(
    result: dict,
    order_name: str | None = None,
) -> dict:
    """Attach has_batch_no, batch_disabled, already_in_target, and live shelf balances."""
    item_code = result.get("item_code")
    if not item_code:
        return result

    has_batch = cint(frappe.db.get_value("Item", item_code, "has_batch_no") or 0)
    result["has_batch_no"] = has_batch

    batch_no = result.get("batch_no")
    if not batch_no:
        result.setdefault("warehouse", None)
        result.setdefault("available_balances", [])
        result.setdefault("already_in_target", False)
        result.setdefault("batch_disabled", False)
        return result

    batch_disabled = cint(frappe.db.get_value("Batch", batch_no, "disabled") or 0)
    if batch_disabled == 1:
        return {
            **result,
            "warehouse": None,
            "qty": 0.0,
            "available_balances": [],
            "already_in_target": False,
            "batch_disabled": True,
            "has_batch_no": has_batch,
        }

    balances = get_batch_ledger_balances(item_code, batch_no)
    pos_balances = [b for b in balances if flt(b.get("qty")) > _BALANCE_EPSILON]

    target_wh = None
    order_company = None
    exact_suggested_whs: set[str] = set()
    item_suggested_whs: set[str] = set()
    if order_name and frappe.db.exists("KTA Line Replenishment Order", order_name):
        order = frappe.get_doc("KTA Line Replenishment Order", order_name)
        target_wh = order.target_warehouse
        order_company = order.company
        for r in order.items:
            if r.item_code == item_code and r.suggested_source_warehouse:
                item_suggested_whs.add(r.suggested_source_warehouse)
                if r.suggested_batch_no == batch_no:
                    exact_suggested_whs.add(r.suggested_source_warehouse)

    pos_whs = [b["warehouse"] for b in pos_balances if b.get("warehouse")]
    wh_meta = (
        {
            w.name: w
            for w in frappe.get_all(
                "Warehouse",
                filters={"name": ["in", pos_whs]},
                fields=[
                    "name",
                    "is_group",
                    "disabled",
                    "is_rejected_warehouse",
                    "company",
                ],
            )
        }
        if pos_whs
        else {}
    )

    in_target = False
    eligible: list[dict] = []
    for b in pos_balances:
        wh = b["warehouse"]
        qty = flt(b["qty"])
        meta = wh_meta.get(wh)
        if not meta:
            continue
        if (
            cint(meta.is_group)
            or cint(meta.disabled)
            or cint(meta.is_rejected_warehouse)
        ):
            continue
        if order_company and meta.company and meta.company != order_company:
            continue
        if target_wh and wh == target_wh:
            in_target = True
            continue
        eligible.append({"warehouse": wh, "qty": qty})

    if not eligible:
        return {
            **result,
            "warehouse": None,
            "qty": 0.0,
            "available_balances": [],
            "already_in_target": bool(in_target),
            "batch_disabled": False,
            "has_batch_no": has_batch,
        }

    eligible.sort(
        key=lambda b: (
            0 if b["warehouse"] in exact_suggested_whs else 1,
            0 if b["warehouse"] in item_suggested_whs else 1,
            -flt(b["qty"]),
            _natural_shelf_sort_key({"suggested_source_warehouse": b["warehouse"]}),
        )
    )
    primary = eligible[0]
    return {
        **result,
        "warehouse": primary["warehouse"],
        "qty": flt(primary["qty"]),
        "available_balances": eligible,
        "already_in_target": False,
        "batch_disabled": False,
        "has_batch_no": has_batch,
    }


@frappe.whitelist()
def resolve_scanned_barcode(
    barcode: str | None = None,
    order_name: str | None = None,
) -> dict:
    """Resolve a scanned barcode string into item_code, batch_no, live shelf, and quantity.

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
        return _enrich_barcode_with_live_balances(
            {
                "item_code": clean_code,
                "batch_no": None,
                "qty": 0.0,
                "source": "Item",
            },
            order_name=order_name,
        )

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
        return _enrich_barcode_with_live_balances(
            {
                "item_code": label.item_code,
                "batch_no": label.batch,
                "qty": flt(label.qty),
                "label_name": label.name,
                "source": "KTA Stock Label",
            },
            order_name=order_name,
        )

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
        return _enrich_barcode_with_live_balances(
            {
                "item_code": batch.item,
                "batch_no": batch.name,
                "qty": 0.0,
                "source": "Batch",
            },
            order_name=order_name,
        )

    # 4. Item Barcode lookup
    item_barcode = frappe.db.get_value(
        "Item Barcode",
        {"barcode": clean_code},
        ["parent"],
        as_dict=True,
    )
    if item_barcode:
        return _enrich_barcode_with_live_balances(
            {
                "item_code": item_barcode.parent,
                "batch_no": None,
                "qty": 0.0,
                "source": "Item Barcode",
            },
            order_name=order_name,
        )

    return {"item_code": None, "batch_no": None, "qty": 0.0}
