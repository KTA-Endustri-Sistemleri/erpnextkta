# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import flt


def get_central_warehouse(company: str | None = None) -> str:
    """Resolve default central raw material warehouse for replenishment."""
    if frappe.db.exists("Warehouse", "110 HAMMADDE - KTA"):
        return "110 HAMMADDE - KTA"

    if company:
        default_wh = frappe.db.get_value(
            "Company", company, "default_raw_material_warehouse"
        )
        if default_wh:
            return default_wh

        wh = frappe.db.get_value(
            "Warehouse",
            {
                "company": company,
                "warehouse_name": ["like", "%HAMMADDE%"],
                "is_group": 0,
            },
            "name",
        )
        if wh:
            return wh

    wh = frappe.db.get_value(
        "Warehouse",
        {"warehouse_name": ["like", "%HAMMADDE%"], "is_group": 0},
        "name",
    )
    if wh:
        return wh

    return "110 HAMMADDE - KTA"


def get_line_reservation_deficits(target_warehouse: str, **_kwargs) -> list[dict]:
    """Calculate net reservation deficits for a target WIP warehouse from central store.

    Scans tabBin records for target_warehouse where reserved_qty_for_production > actual_qty,
    deducts open draft replenishment order quantities, and allocates FIFO batches exclusively
    from the central raw material warehouse (110 HAMMADDE).
    """
    target_wh = _validate_target_warehouse(target_warehouse)
    deficit_rows = _get_deficit_bin_rows(target_wh)
    if not deficit_rows:
        return []

    company = frappe.db.get_value("Warehouse", target_wh, "company")
    central_wh = get_central_warehouse(company)
    drafts_by_item = _get_drafts_by_item(target_wh)
    item_codes = list({r["item_code"] for r in deficit_rows if r.get("item_code")})
    items_info = _get_items_info(item_codes)

    deficit_items_info, items_to_allocate = _prepare_deficit_allocations(
        deficit_rows=deficit_rows,
        drafts_by_item=drafts_by_item,
        items_info=items_info,
        central_wh=central_wh,
    )

    from erpnextkta.kta_stock.line_replenishment_service import (
        bulk_allocate_fifo_batches,
    )

    bulk_batches_map = bulk_allocate_fifo_batches(
        items_to_allocate=items_to_allocate,
        target_warehouse=target_wh,
    )

    return [
        _build_deficit_result_row(
            info=info,
            batches=bulk_batches_map.get(info["item_code"], []),
            central_wh=central_wh,
        )
        for info in deficit_items_info
    ]


def _validate_target_warehouse(target_warehouse: str) -> str:
    """Ensure target warehouse is provided and is not a group warehouse."""
    if not target_warehouse or not str(target_warehouse).strip():
        frappe.throw(
            _("Hedef WIP deposu seçimi zorunludur."),
            frappe.ValidationError,
        )

    target_wh = str(target_warehouse).strip()
    if frappe.db.exists("Warehouse", target_wh) and frappe.db.get_value(
        "Warehouse", target_wh, "is_group"
    ):
        frappe.throw(
            _("Grup ambarı hedef WIP deposu olarak seçilemez: {0}").format(target_wh),
            frappe.ValidationError,
        )
    return target_wh


def _get_deficit_bin_rows(target_wh: str) -> list[dict]:
    """Query tabBin rows in target_wh with positive production reservation deficits."""
    return frappe.db.sql(
        """
        SELECT
            item_code,
            stock_uom,
            actual_qty,
            reserved_qty_for_production
        FROM `tabBin`
        WHERE warehouse = %s
          AND reserved_qty_for_production > actual_qty
        ORDER BY item_code
        """,
        (target_wh,),
        as_dict=True,
    )


def _get_drafts_by_item(target_wh: str) -> dict[str, list]:
    """Fetch in-flight draft replenishment order items grouped by item_code."""
    rows = frappe.db.sql(
        """
        SELECT parent, item_code, suggested_batch_no, deficit_qty
        FROM `tabKTA Line Replenishment Item`
        WHERE docstatus = 0
          AND parent IN (
            SELECT name FROM `tabKTA Line Replenishment Order`
            WHERE target_warehouse = %s
              AND docstatus = 0
              AND status = 'Draft'
          )
        """,
        (target_wh,),
        as_dict=True,
    )
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["item_code"], []).append(row)
    return grouped


def _get_items_info(item_codes: list[str]) -> dict[str, dict]:
    """Fetch item_name and stock_uom metadata for deficit item codes."""
    if not item_codes:
        return {}
    return {
        d.name: d
        for d in frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "stock_uom"],
        )
    }


def _prepare_deficit_allocations(
    deficit_rows: list[dict],
    drafts_by_item: dict[str, list],
    items_info: dict[str, dict],
    central_wh: str,
) -> tuple[list[dict], list[dict]]:
    """Compute net deficits after draft deduction and build central allocation requests."""
    deficit_items_info: list[dict] = []
    items_to_allocate: list[dict] = []

    for row in deficit_rows:
        reserved_qty = flt(row.get("reserved_qty_for_production") or 0)
        line_actual_qty = flt(row.get("actual_qty") or 0)
        raw_deficit = reserved_qty - line_actual_qty
        if raw_deficit <= 0:
            continue

        item_code = row.get("item_code")
        item_meta = items_info.get(item_code)
        item_name = item_meta.item_name if item_meta else item_code
        uom = row.get("stock_uom") or (item_meta.stock_uom if item_meta else "")

        item_drafts = drafts_by_item.get(item_code, [])
        q_taslak = sum(flt(d.get("deficit_qty") or 0) for d in item_drafts)
        draft_orders = list(
            dict.fromkeys(d["parent"] for d in item_drafts if d.get("parent"))
        )
        d_net = max(0.0, raw_deficit - q_taslak)

        deficit_items_info.append(
            {
                "item_code": item_code,
                "item_name": item_name,
                "uom": uom,
                "reserved_qty": reserved_qty,
                "line_actual_qty": line_actual_qty,
                "raw_deficit": raw_deficit,
                "d_net": d_net,
                "q_taslak": q_taslak,
                "draft_orders": draft_orders,
            }
        )

        if d_net > 0:
            items_to_allocate.append(
                {
                    "item_code": item_code,
                    "parent_warehouse": central_wh,
                    "required_qty": d_net,
                }
            )

    return deficit_items_info, items_to_allocate


def _build_deficit_result_row(
    info: dict,
    batches: list[dict],
    central_wh: str,
) -> dict:
    """Build normalized deficit output dictionary with central FIFO batch results."""
    raw_deficit = info["raw_deficit"]
    d_net = info["d_net"]
    q_taslak = info["q_taslak"]

    if raw_deficit > 0 and d_net == 0:
        covered_by_draft = True
        deficit_qty = 0.0
        suggested_source_wh = central_wh
        suggested_batch_no = None
        allocated_batches = []
        has_stock = False
        available_stock = 0.0
    else:
        covered_by_draft = False
        deficit_qty = d_net
        if batches:
            suggested_source_wh = batches[0].get("warehouse") or central_wh
            suggested_batch_no = batches[0].get("batch_no")
            allocated_batches = batches
            has_stock = True
            available_stock = sum(flt(b.get("allocated_qty") or 0) for b in batches)
        else:
            suggested_source_wh = central_wh
            suggested_batch_no = None
            allocated_batches = []
            has_stock = False
            available_stock = 0.0

    return {
        "item_code": info["item_code"],
        "item_name": info["item_name"],
        "uom": info["uom"],
        "reserved_qty": info["reserved_qty"],
        "line_actual_qty": info["line_actual_qty"],
        "deficit_qty": deficit_qty,
        "suggested_source_warehouse": suggested_source_wh,
        "suggested_batch_no": suggested_batch_no,
        "allocated_batches": allocated_batches,
        "has_stock": has_stock,
        "available_stock": available_stock,
        "covered_by_draft": covered_by_draft,
        "draft_covered_qty": q_taslak,
        "draft_orders": info["draft_orders"],
        "selectable": bool(has_stock),
    }
