"""Custom Manufacture auto-reorder logic and stale draft cleanup for KTA."""

from __future__ import annotations

import erpnext
import frappe
from frappe.utils import flt, nowdate


def calculate_kta_manufacture_reorder_qty(
    projected_qty, reorder_level, reorder_qty
) -> float | None:
    """Return KTA Manufacture reorder quantity using strict `<` level comparison."""
    projected_qty = flt(projected_qty)
    reorder_level = flt(reorder_level)
    reorder_qty = flt(reorder_qty)

    if not (reorder_level or reorder_qty):
        return None

    if projected_qty >= reorder_level:
        return None

    deficiency = reorder_level - projected_qty
    return max(reorder_qty, deficiency)


def get_kta_manufacture_projected_qty(item_codes) -> dict[str, dict[str, float]]:
    """Compute projected quantities per item and warehouse hierarchy excluding Sales Order reserves."""
    unique_codes = list(dict.fromkeys(c for c in (item_codes or []) if c))
    if not unique_codes:
        return {}

    warehouse_parent_map = frappe._dict(
        frappe.get_all("Warehouse", fields=["name", "parent_warehouse"], as_list=True)
    )

    placeholders = ", ".join(["%s"] * len(unique_codes))
    rows = frappe.db.sql(
        f"""
		SELECT
			bin.item_code,
			bin.warehouse,
			SUM(bin.actual_qty)
			+ SUM(bin.planned_qty)
			+ SUM(bin.indented_qty)
			+ SUM(bin.ordered_qty)
			- SUM(bin.reserved_qty_for_production)
			- SUM(bin.reserved_qty_for_sub_contract) AS custom_projected
		FROM `tabBin` bin
		INNER JOIN `tabWarehouse` w ON w.name = bin.warehouse
		WHERE bin.item_code IN ({placeholders})
			AND bin.warehouse IS NOT NULL
			AND bin.warehouse != ''
			AND w.is_rejected_warehouse = 0
		GROUP BY bin.item_code, bin.warehouse
		""",
        tuple(unique_codes),
        as_dict=True,
    )

    item_warehouse_projected_qty: dict[str, dict[str, float]] = {}
    for row in rows:
        item_code = row.item_code
        warehouse = row.warehouse
        projected_qty = flt(row.custom_projected)

        item_wh_map = item_warehouse_projected_qty.setdefault(item_code, {})
        item_wh_map[warehouse] = item_wh_map.get(warehouse, 0.0) + projected_qty

        visited = {warehouse}
        parent_warehouse = warehouse_parent_map.get(warehouse)
        while parent_warehouse and parent_warehouse not in visited:
            visited.add(parent_warehouse)
            item_wh_map[parent_warehouse] = (
                item_wh_map.get(parent_warehouse, 0.0) + projected_qty
            )
            parent_warehouse = warehouse_parent_map.get(parent_warehouse)

    return item_warehouse_projected_qty


def cleanup_stale_auto_reorder_drafts(before_date=None) -> list[str]:
    """Delete stale auto-generated Draft Manufacture Material Requests owned by Administrator."""
    cutoff_date = before_date or nowdate()
    stale_mrs = frappe.get_all(
        "Material Request",
        filters={
            "docstatus": 0,
            "material_request_type": "Manufacture",
            "owner": "Administrator",
            "transaction_date": ["<", cutoff_date],
        },
        pluck="name",
    )

    deleted = []
    for mr_name in stale_mrs:
        try:
            frappe.delete_doc("Material Request", mr_name, ignore_permissions=True)
            deleted.append(mr_name)
        except Exception:  # noqa: BLE001
            frappe.log_error(
                title="KTA Reorder Draft Cleanup Error",
                message=frappe.get_traceback(),
            )

    return deleted


def _split_items_by_request_type(items_to_consider):
    """Split reorder item map into Manufacture rows and all other request types."""
    manufacture_items = {}
    other_items = {}

    for item_code, rows in items_to_consider.items():
        for d in rows:
            target = (
                manufacture_items
                if d.material_request_type == "Manufacture"
                else other_items
            )
            target.setdefault(item_code, []).append(d)

    return manufacture_items, other_items


def _build_manufacture_item_entry(item_code, row, qty):
    """Build Material Request payload entry for a single Manufacture reorder row."""
    return {
        "item_code": item_code,
        "warehouse": row.warehouse,
        "reorder_qty": qty,
        "item_details": frappe._dict(
            {
                "item_code": item_code,
                "name": item_code,
                "item_name": row.item_name,
                "item_group": row.item_group,
                "brand": row.brand,
                "description": row.description,
                "stock_uom": row.stock_uom,
                "purchase_uom": row.purchase_uom,
                "lead_time_days": row.lead_time_days,
            }
        ),
    }


def process_kta_manufacture_reorder(manufacture_items) -> list:
    """Evaluate KTA Manufacture reorder rows and create Material Requests when below level."""
    from erpnext.stock import reorder_item

    warehouse_company = frappe._dict(
        frappe.get_all(
            "Warehouse",
            filters={"disabled": 0},
            fields=["name", "company"],
            as_list=True,
        )
    )
    default_company = erpnext.get_default_company() or frappe.db.get_value(
        "Company", {}, "name"
    )
    projected_map = get_kta_manufacture_projected_qty(list(manufacture_items.keys()))

    material_requests: dict[str, dict[str, list]] = {"Manufacture": {}}

    for item_code, reorder_levels in manufacture_items.items():
        for d in reorder_levels:
            if d.has_variants or d.warehouse not in warehouse_company:
                continue

            lookup_wh = d.warehouse_group or d.warehouse
            projected_qty = flt(projected_map.get(item_code, {}).get(lookup_wh))
            qty = calculate_kta_manufacture_reorder_qty(
                projected_qty,
                d.warehouse_reorder_level,
                d.warehouse_reorder_qty,
            )
            if qty is None:
                continue

            company = warehouse_company.get(d.warehouse) or default_company
            material_requests["Manufacture"].setdefault(company, []).append(
                _build_manufacture_item_entry(item_code, d, qty)
            )

    if material_requests["Manufacture"]:
        return reorder_item.create_material_request(material_requests) or []
    return []


def custom_reorder_item():
    """Run stale Manufacture draft cleanup, custom Manufacture reorder, and standard reorder."""
    from erpnext.stock import reorder_item

    cleanup_stale_auto_reorder_drafts()

    items_to_consider = reorder_item.get_items_for_reorder()
    if not items_to_consider:
        return []

    manufacture_items, other_items = _split_items_by_request_type(items_to_consider)
    mr_list = []

    if manufacture_items:
        mr_list.extend(process_kta_manufacture_reorder(manufacture_items))

    if other_items:
        original_get_items = reorder_item.get_items_for_reorder
        reorder_item.get_items_for_reorder = lambda: other_items
        try:
            other_mrs = reorder_item._original_reorder_item()
        finally:
            reorder_item.get_items_for_reorder = original_get_items
        if other_mrs:
            mr_list.extend(other_mrs)

    return mr_list


def apply_reorder_item_override():
    """Idempotently override ERPNext's internal _reorder_item entrypoint."""
    from erpnext.stock import reorder_item

    if not hasattr(reorder_item, "_original_reorder_item"):
        reorder_item._original_reorder_item = reorder_item._reorder_item
        reorder_item._reorder_item = custom_reorder_item
