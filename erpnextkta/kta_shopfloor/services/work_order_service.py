# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, today

from erpnextkta.kta_shopfloor.services.line_transfer_service import (
    is_valid_production_warehouse,
)

DEFAULT_MANUFACTURING_LEAD_DAYS = 14


def resolve_manufacturing_lead_days(item_code: str, customer: str | None = None) -> int:
    """Resolve internal manufacturing lead time in days.

    Hierarchy:
    1. Item Customer Detail.custom_production_time_days (when customer provided)
    2. Item.custom_manufacturing_lead_days
    3. Fallback to 14 days
    """
    if not item_code:
        return DEFAULT_MANUFACTURING_LEAD_DAYS

    if customer and frappe.db.has_column(
        "Item Customer Detail", "custom_production_time_days"
    ):
        cust_days = frappe.db.get_value(
            "Item Customer Detail",
            {"parent": item_code, "customer_name": customer},
            "custom_production_time_days",
        )
        if cint(cust_days) > 0:
            return cint(cust_days)

    if frappe.db.has_column("Item", "custom_manufacturing_lead_days"):
        item_days = frappe.db.get_value(
            "Item", item_code, "custom_manufacturing_lead_days"
        )
        if cint(item_days) > 0:
            return cint(item_days)

    return DEFAULT_MANUFACTURING_LEAD_DAYS


def check_work_order_material_availability(work_order) -> dict:
    """Check Bin stock availability against Work Order required_items across line and company warehouses."""
    wo = _load_work_order(work_order)
    wo.check_permission("read")
    company = wo.get("company") or _resolve_company(None)
    items: list[dict] = []

    for d in wo.get("required_items") or []:
        warehouse = (
            d.get("source_warehouse")
            or wo.get("source_warehouse")
            or wo.get("wip_warehouse")
        )
        required_qty = flt(d.get("required_qty") or 0)
        line_actual_qty, line_reserved_qty = _get_bin_stock_levels(
            d.item_code, warehouse
        )
        line_available_qty = max(0.0, flt(line_actual_qty - line_reserved_qty))
        available_qty = line_available_qty

        shortage_qty = max(0.0, flt(required_qty - line_available_qty))
        coverage_percent = max(
            0.0,
            min(
                100.0,
                round(
                    (line_available_qty / required_qty * 100.0)
                    if required_qty > 0
                    else 100.0,
                    1,
                ),
            ),
        )

        other_warehouses_qty, other_warehouses = _get_other_warehouses_stock(
            d.item_code, company, warehouse
        )
        sibling_line_warehouses = [
            w
            for w in other_warehouses
            if is_valid_production_warehouse(w["warehouse"], warehouse)
        ]

        if line_available_qty >= required_qty:
            availability_status = "available"
        elif (line_available_qty + other_warehouses_qty) >= required_qty:
            availability_status = "transfer_required"
        else:
            availability_status = "critical_shortage"

        root_item = d.get("custom_original_item") or d.item_code
        has_alternatives = bool(
            len(
                get_item_alternatives(
                    root_item,
                    company=company,
                    warehouse=warehouse,
                )
            )
        )
        can_swap = (
            flt(d.get("consumed_qty") or 0) <= 0
            and flt(d.get("transferred_qty") or 0) <= 0
            and wo.docstatus == 0
        )

        items.append(
            {
                "row_name": d.name,
                "item_code": d.item_code,
                "custom_original_item": d.get("custom_original_item"),
                "is_alternative": bool(d.get("custom_original_item")),
                "has_alternatives": has_alternatives,
                "can_swap": can_swap,
                "item_name": d.get("item_name")
                or frappe.db.get_value("Item", d.item_code, "item_name")
                or d.item_code,
                "description": d.get("description") or "",
                "warehouse": warehouse,
                "source_warehouse": warehouse,
                "required_qty": required_qty,
                "line_actual_qty": line_actual_qty,
                "line_reserved_qty": line_reserved_qty,
                "line_available_qty": line_available_qty,
                "available_qty": available_qty,
                "shortage_qty": shortage_qty,
                "coverage_percent": coverage_percent,
                "is_available": shortage_qty <= 0,
                "availability_status": availability_status,
                "other_warehouses_qty": other_warehouses_qty,
                "other_warehouses": other_warehouses,
                "sibling_line_warehouses": sibling_line_warehouses,
                "has_sibling_line_stock": bool(sibling_line_warehouses),
                "stock_uom": d.get("stock_uom") or "",
            }
        )

    shortage_count = sum(1 for row in items if row["shortage_qty"] > 0)
    critical_shortage_count = sum(
        1 for row in items if row["availability_status"] == "critical_shortage"
    )
    transfer_required_count = sum(
        1 for row in items if row["availability_status"] == "transfer_required"
    )

    has_shortage = shortage_count > 0
    has_line_shortage = shortage_count > 0
    has_critical_shortage = critical_shortage_count > 0
    can_fulfill_via_transfer = has_line_shortage and not has_critical_shortage

    overall_readiness = (
        round(sum(row["coverage_percent"] for row in items) / len(items), 1)
        if items
        else 100.0
    )

    return {
        "work_order": wo.name,
        "overall_readiness_percent": overall_readiness,
        "has_shortage": has_shortage,
        "has_line_shortage": has_line_shortage,
        "has_critical_shortage": has_critical_shortage,
        "can_fulfill_via_transfer": can_fulfill_via_transfer,
        "shortage_count": shortage_count,
        "critical_shortage_count": critical_shortage_count,
        "transfer_required_count": transfer_required_count,
        "total_items": len(items),
        "items": items,
    }


def create_draft_work_order(
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
    """Create a Draft Work Order with resolved BOM, warehouses, and lead-time end date."""
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(
            _("Geçerli bir mamul kodu (item_code) zorunludur."),
            frappe.ValidationError,
        )

    qty_val = flt(qty)
    if qty_val <= 0:
        frappe.throw(
            _("Üretim miktarı sıfırdan büyük olmalıdır."),
            frappe.ValidationError,
        )

    target_company = _resolve_company(company)
    target_bom = bom_no or _resolve_default_bom(item_code)
    start_date = planned_start_date or today()
    lead_days = resolve_manufacturing_lead_days(item_code, customer=customer)
    end_date = planned_end_date or add_days(start_date, lead_days)

    resolved_fg_wh = fg_warehouse or _resolve_default_warehouse(
        target_company, "default_fg_warehouse", item_code
    )
    resolved_wip_wh = wip_warehouse or _resolve_default_warehouse(
        target_company, "default_wip_warehouse"
    )

    wo = frappe.new_doc("Work Order")
    wo.production_item = item_code
    wo.qty = qty_val
    wo.bom_no = target_bom
    wo.company = target_company
    wo.planned_start_date = start_date
    wo.planned_end_date = end_date
    if source_warehouse:
        wo.source_warehouse = source_warehouse
    if resolved_wip_wh:
        wo.wip_warehouse = resolved_wip_wh
    if resolved_fg_wh:
        wo.fg_warehouse = resolved_fg_wh

    wo.set_work_order_operations()
    auto_normalize_work_order_operations(wo)
    wo.insert()

    return {
        "name": wo.name,
        "status": wo.status or "Draft",
        "docstatus": wo.docstatus,
        "production_item": wo.production_item,
        "qty": flt(wo.qty),
        "bom_no": wo.bom_no,
        "planned_start_date": str(wo.planned_start_date),
        "planned_end_date": str(wo.planned_end_date),
        "lead_days": lead_days,
    }


def release_work_order_service(work_order: str, allow_shortage: int = 0) -> dict:
    """Validate material availability and submit (release) a Draft Work Order."""
    wo = _load_work_order(work_order)
    wo.check_permission("submit")

    if wo.docstatus != 0:
        frappe.throw(
            _(
                "Yalnızca taslak durumundaki İş Emirleri serbest bırakılabilir: {0}"
            ).format(wo.name),
            frappe.ValidationError,
        )

    availability = check_work_order_material_availability(wo)
    has_shortage = bool(availability.get("has_shortage"))
    allow = bool(cint(allow_shortage))

    if has_shortage and not allow:
        shortage_items = [
            f"{d['item_code']} ({d['shortage_qty']})"
            for d in availability["items"]
            if d["shortage_qty"] > 0
        ]
        frappe.throw(
            _("Eksik hammadde mevcut: {0}").format(", ".join(shortage_items)),
            frappe.ValidationError,
        )

    released_with_shortage = has_shortage and allow
    if released_with_shortage:
        wo.custom_released_with_shortage = 1

    wo.submit()

    if released_with_shortage:
        if frappe.db.has_column("Work Order", "custom_released_with_shortage"):
            wo.db_set("custom_released_with_shortage", 1)

        shortage_details = ", ".join(
            f"{d['item_code']}: {d['shortage_qty']} {d.get('stock_uom') or ''}".strip()
            for d in availability["items"]
            if d["shortage_qty"] > 0
        )
        wo.add_comment(
            "Comment",
            _("İş Emri eksik hammadde ile serbest bırakıldı: {0}").format(
                shortage_details
            ),
        )

    return {
        "name": wo.name,
        "status": wo.status,
        "docstatus": wo.docstatus,
        "released_with_shortage": released_with_shortage,
        "availability": availability,
    }


def auto_normalize_work_order_operations(wo) -> None:
    """Normalize operation sequence_id values to 1-based sequential steps (preserving parallels)."""
    operations = wo.get("operations") or []
    if not operations:
        return

    sorted_ops = sorted(operations, key=lambda op: cint(op.get("idx") or 0))
    current_seq = 1
    prev_orig_seq = cint(sorted_ops[0].get("sequence_id"))
    sorted_ops[0].sequence_id = 1

    for op in sorted_ops[1:]:
        orig_seq = cint(op.get("sequence_id"))
        if orig_seq == prev_orig_seq and orig_seq not in (0, None):
            op.sequence_id = current_seq
        else:
            current_seq += 1
            op.sequence_id = current_seq
        prev_orig_seq = orig_seq


@frappe.whitelist()
def get_item_alternatives(
    item_code: str,
    company: str | None = None,
    warehouse: str | None = None,
) -> list[dict]:
    """Retrieve all approved item alternatives (one-way and two-way) with stock availability."""
    if not item_code:
        return []

    rows = frappe.db.sql(
        """
        SELECT item_code, alternative_item_code, two_way
        FROM `tabItem Alternative`
        WHERE (item_code = %(item_code)s)
           OR (alternative_item_code = %(item_code)s AND two_way = 1)
        ORDER BY idx ASC, creation ASC
        """,
        {"item_code": item_code},
        as_dict=True,
    )

    if not rows:
        return []

    unique_alts: dict[str, bool] = {}
    for r in rows:
        if r.item_code == item_code:
            alt_code = r.alternative_item_code
            is_two_way = bool(cint(r.two_way))
        else:
            alt_code = r.item_code
            is_two_way = True

        if not alt_code or alt_code == item_code:
            continue

        if alt_code in unique_alts:
            unique_alts[alt_code] = unique_alts[alt_code] or is_two_way
        else:
            unique_alts[alt_code] = is_two_way

    target_company = company
    if not target_company:
        try:
            target_company = _resolve_company(None)
        except frappe.ValidationError:
            target_company = None

    alternatives: list[dict] = []
    for alt_code, is_two_way in unique_alts.items():
        item_vals = (
            frappe.db.get_value(
                "Item",
                alt_code,
                ["item_name", "stock_uom", "description"],
                as_dict=True,
            )
            or {}
        )

        if warehouse:
            line_actual_qty, line_reserved_qty = _get_bin_stock_levels(
                alt_code, warehouse
            )
            line_available_qty = max(0.0, flt(line_actual_qty - line_reserved_qty))
        else:
            line_available_qty = 0.0

        if target_company:
            other_warehouses_qty, _ = _get_other_warehouses_stock(
                alt_code, target_company, warehouse
            )
        else:
            other_warehouses_qty = 0.0

        alternatives.append(
            {
                "item_code": alt_code,
                "item_name": item_vals.get("item_name") or alt_code,
                "stock_uom": item_vals.get("stock_uom") or "",
                "description": item_vals.get("description") or "",
                "line_available_qty": line_available_qty,
                "other_warehouses_qty": other_warehouses_qty,
                "two_way": is_two_way,
            }
        )

    return alternatives


@frappe.whitelist()
def get_work_order_item_alternatives(work_order: str, row_name: str) -> dict:
    """Retrieve approved alternatives for a specific Work Order item row with swapping eligibility."""
    wo = _load_work_order(work_order)
    wo.check_permission("read")

    target_row = None
    for d in wo.get("required_items") or []:
        if d.name == row_name or d.item_code == row_name:
            target_row = d
            break

    if not target_row:
        frappe.throw(
            _("İş Emri satırı bulunamadı: {0}").format(row_name),
            frappe.ValidationError,
        )

    root_item = target_row.get("custom_original_item") or target_row.item_code
    warehouse = (
        target_row.get("source_warehouse")
        or wo.get("source_warehouse")
        or wo.get("wip_warehouse")
    )
    alternatives = get_item_alternatives(
        root_item,
        company=wo.get("company"),
        warehouse=warehouse,
    )

    can_swap = (
        flt(target_row.get("consumed_qty") or 0) <= 0
        and flt(target_row.get("transferred_qty") or 0) <= 0
        and wo.docstatus == 0
    )

    return {
        "work_order": wo.name,
        "row_name": target_row.name,
        "current_item_code": target_row.item_code,
        "root_item_code": root_item,
        "is_alternative": bool(target_row.get("custom_original_item")),
        "can_swap": can_swap,
        "alternatives": alternatives,
    }


@frappe.whitelist()
def set_work_order_item_alternative(
    work_order: str, row_name: str, alternative_item_code: str
) -> dict:
    """Substitute an approved alternative item on a Draft Work Order required item line."""
    wo = _load_work_order(work_order)
    wo.check_permission("write")

    if wo.docstatus != 0:
        frappe.throw(
            _("Yalnızca taslak iş emirlerinde hammadde alternatifi değiştirilebilir."),
            frappe.ValidationError,
        )

    target_row = None
    for d in wo.get("required_items") or []:
        if d.name == row_name or d.item_code == row_name:
            target_row = d
            break

    if not target_row:
        frappe.throw(
            _("İş Emri satırı bulunamadı: {0}").format(row_name),
            frappe.ValidationError,
        )

    if (
        flt(target_row.get("consumed_qty") or 0) > 0
        or flt(target_row.get("transferred_qty") or 0) > 0
    ):
        frappe.throw(
            _("Tüketim veya transfer yapılmış satır değiştirilemez."),
            frappe.ValidationError,
        )

    root_item = target_row.get("custom_original_item") or target_row.item_code
    warehouse = (
        target_row.get("source_warehouse")
        or wo.get("source_warehouse")
        or wo.get("wip_warehouse")
    )
    approved_alts = get_item_alternatives(
        root_item,
        company=wo.get("company"),
        warehouse=warehouse,
    )
    approved_codes = {alt["item_code"] for alt in approved_alts}

    if alternative_item_code not in approved_codes:
        frappe.throw(
            _("'{0}' kalemi '{1}' için onaylı bir alternatif değildir.").format(
                alternative_item_code, root_item
            ),
            frappe.ValidationError,
        )

    target_row.custom_original_item = root_item
    target_row.item_code = alternative_item_code

    item_details = (
        frappe.db.get_value(
            "Item",
            alternative_item_code,
            ["item_name", "description", "stock_uom"],
            as_dict=True,
        )
        or {}
    )
    target_row.item_name = item_details.get("item_name") or alternative_item_code
    target_row.description = item_details.get("description") or ""
    if item_details.get("stock_uom"):
        target_row.stock_uom = item_details.get("stock_uom")

    wo.flags.ignore_validate_update_after_submit = True
    wo.save()

    wo.add_comment(
        "Comment",
        _("Satır #{0}: '{1}' hammaddesi yerine alternatif '{2}' atandı.").format(
            target_row.idx or 1, root_item, alternative_item_code
        ),
    )

    return check_work_order_material_availability(wo)


@frappe.whitelist()
def restore_work_order_item_original(work_order: str, row_name: str) -> dict:
    """Restore the original item on a Work Order row previously substituted with an alternative."""
    wo = _load_work_order(work_order)
    wo.check_permission("write")

    if wo.docstatus != 0:
        frappe.throw(
            _("Yalnızca taslak iş emirlerinde orijinal kalem geri yüklenebilir."),
            frappe.ValidationError,
        )

    target_row = None
    for d in wo.get("required_items") or []:
        if d.name == row_name or d.item_code == row_name:
            target_row = d
            break

    if not target_row:
        frappe.throw(
            _("İş Emri satırı bulunamadı: {0}").format(row_name),
            frappe.ValidationError,
        )

    if (
        flt(target_row.get("consumed_qty") or 0) > 0
        or flt(target_row.get("transferred_qty") or 0) > 0
    ):
        frappe.throw(
            _("Tüketim veya transfer yapılmış satır geri yüklenemez."),
            frappe.ValidationError,
        )

    if not target_row.get("custom_original_item"):
        frappe.throw(
            _("Satırda kayıtlı orijinal hammadde bulunamadı."),
            frappe.ValidationError,
        )

    orig = target_row.custom_original_item
    prev_alt = target_row.item_code
    target_row.item_code = orig
    target_row.custom_original_item = None

    item_details = (
        frappe.db.get_value(
            "Item",
            orig,
            ["item_name", "description", "stock_uom"],
            as_dict=True,
        )
        or {}
    )
    target_row.item_name = item_details.get("item_name") or orig
    target_row.description = item_details.get("description") or ""
    if item_details.get("stock_uom"):
        target_row.stock_uom = item_details.get("stock_uom")

    wo.flags.ignore_validate_update_after_submit = True
    wo.save()

    wo.add_comment(
        "Comment",
        _(
            "Satır #{0}: Alternatif '{1}' iptal edilerek orijinal '{2}' geri yüklendi."
        ).format(target_row.idx or 1, prev_alt, orig),
    )

    return check_work_order_material_availability(wo)


def update_work_order_qty(work_order: str, qty: float) -> dict:
    """Proportionally scale production target quantity, required items, and operation timings on a Draft Work Order."""
    wo = _load_work_order(work_order)
    wo.check_permission("write")

    if wo.docstatus != 0:
        frappe.throw(
            _(
                "Yalnızca taslak durumundaki İş Emirlerinin miktarı değiştirilebilir: {0}"
            ).format(wo.name),
            frappe.ValidationError,
        )

    new_qty = flt(qty)
    if new_qty <= 0:
        frappe.throw(
            _("Üretim miktarı sıfırdan büyük olmalıdır."),
            frappe.ValidationError,
        )

    old_qty = flt(wo.qty)
    if old_qty == new_qty:
        res = check_work_order_material_availability(wo)
        res["qty"] = new_qty
        res["old_qty"] = old_qty
        return res

    ratio = new_qty / old_qty if old_qty > 0 else 1.0

    wo.qty = new_qty
    for d in wo.get("required_items") or []:
        d.required_qty = flt(flt(d.required_qty) * ratio, 4)
        d.amount = flt(flt(d.rate or 0) * d.required_qty, 2)

    for op in wo.get("operations") or []:
        op.qty = new_qty
        if op.get("time_in_mins"):
            op.time_in_mins = flt(flt(op.time_in_mins) * ratio, 2)

    auto_normalize_work_order_operations(wo)

    wo.flags.ignore_validate_update_after_submit = True
    wo.save()

    wo.add_comment(
        "Comment",
        _("İş Emri üretim hedef miktarı {0} -> {1} olarak güncellendi.").format(
            old_qty, new_qty
        ),
    )

    res = check_work_order_material_availability(wo)
    res["qty"] = new_qty
    res["old_qty"] = old_qty
    return res


def get_work_order_print_options(work_order: str | None = None) -> dict:
    """Return active Work Order Print Formats, Letter Heads, and print permissions."""
    with_letterhead = cint(
        frappe.db.get_single_value("Print Settings", "with_letterhead") or 0
    )
    allow_print_for_draft = cint(
        frappe.db.get_single_value("Print Settings", "allow_print_for_draft") or 0
    )
    allow_print_for_cancelled = cint(
        frappe.db.get_single_value("Print Settings", "allow_print_for_cancelled") or 0
    )

    if work_order:
        if not frappe.db.exists("Work Order", work_order):
            frappe.throw(
                _("İş Emri bulunamadı: {0}").format(work_order),
                frappe.ValidationError,
            )
        wo = frappe.get_doc("Work Order", work_order)
        wo.check_permission("read")
        has_print_perm = bool(wo.has_permission("print"))
        blocked_by_status = (wo.docstatus == 0 and not allow_print_for_draft) or (
            wo.docstatus == 2 and not allow_print_for_cancelled
        )
        can_print = has_print_perm and not blocked_by_status
    else:
        work_order = None
        frappe.has_permission("Work Order", "read", throw=True)
        can_print = bool(frappe.has_permission("Work Order", "print"))

    has_beta_col = frappe.db.has_column("Print Format", "print_format_builder_beta")
    pf_fields = [
        "name",
        "default_print_language",
        "raw_printing",
        "print_format_type",
    ]
    if has_beta_col:
        pf_fields.append("print_format_builder_beta")

    pf_rows = frappe.get_all(
        "Print Format",
        filters={"doc_type": "Work Order", "disabled": 0, "docstatus": ["<", 2]},
        fields=pf_fields,
        order_by="name asc",
    )
    default_print_format = (
        frappe.db.get_value(
            "Property Setter",
            {"doc_type": "Work Order", "property": "default_print_format"},
            "value",
        )
        or frappe.get_meta("Work Order").default_print_format
        or "Standard"
    )

    print_formats = [
        {
            "name": pf.name,
            "label": pf.name,
            "is_default": pf.name == default_print_format,
            "default_print_language": pf.get("default_print_language") or "",
            "raw_printing": cint(pf.get("raw_printing") or 0),
            "print_format_builder_beta": cint(pf.get("print_format_builder_beta") or 0),
        }
        for pf in pf_rows
    ]

    if not any(pf["name"] == "Standard" for pf in print_formats):
        print_formats.append(
            {
                "name": "Standard",
                "label": _("Standard"),
                "is_default": default_print_format == "Standard",
                "default_print_language": "",
                "raw_printing": 0,
                "print_format_builder_beta": 0,
            }
        )

    print_formats.sort(
        key=lambda x: (
            not x["is_default"],
            x["name"] == "Standard",
            x["name"].lower(),
        )
    )

    if print_formats and not any(pf["is_default"] for pf in print_formats):
        default_print_format = print_formats[0]["name"]
        print_formats[0]["is_default"] = True

    letter_heads = frappe.get_all(
        "Letter Head",
        filters={"disabled": 0},
        fields=["name", "is_default"],
        order_by="is_default desc, name asc",
    )
    default_letter_head = next(
        (lh["name"] for lh in letter_heads if cint(lh.get("is_default") or 0) == 1),
        "",
    )

    return {
        "doctype": "Work Order",
        "work_order": work_order,
        "can_print": can_print,
        "default_print_format": default_print_format,
        "print_formats": print_formats,
        "default_letter_head": default_letter_head,
        "letter_heads": [
            {"name": lh["name"], "is_default": cint(lh.get("is_default") or 0)}
            for lh in letter_heads
        ],
        "with_letterhead": with_letterhead,
        "allow_print_for_draft": allow_print_for_draft,
        "allow_print_for_cancelled": allow_print_for_cancelled,
    }


def _load_work_order(work_order):
    if not work_order:
        frappe.throw(
            _("İş Emri bulunamadı: {0}").format(work_order),
            frappe.ValidationError,
        )
    if isinstance(work_order, str):
        if not frappe.db.exists("Work Order", work_order):
            frappe.throw(
                _("İş Emri bulunamadı: {0}").format(work_order),
                frappe.ValidationError,
            )
        return frappe.get_doc("Work Order", work_order)
    return work_order


def _get_bin_stock_levels(item_code: str, warehouse: str | None) -> tuple[float, float]:
    """Return (actual_qty, reserved_qty_for_production) for a given item and warehouse."""
    if not item_code or not warehouse:
        return 0.0, 0.0
    vals = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        ["actual_qty", "reserved_qty_for_production"],
        as_dict=True,
    )
    if not vals:
        return 0.0, 0.0
    return (
        flt(vals.get("actual_qty") or 0.0),
        flt(vals.get("reserved_qty_for_production") or 0.0),
    )


def _get_bin_actual_qty(item_code: str, warehouse: str | None) -> float:
    actual_qty, _ = _get_bin_stock_levels(item_code, warehouse)
    return actual_qty


def _get_other_warehouses_stock(
    item_code: str, company: str | None, line_warehouse: str | None
) -> tuple[float, list[dict]]:
    """Query available stock in active non-group warehouses of the same company, excluding line_warehouse."""
    if not item_code or not company:
        return 0.0, []

    rows = frappe.db.sql(
        """
        SELECT b.warehouse, b.actual_qty, b.reserved_qty_for_production
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code = %s
          AND w.company = %s
          AND w.name != %s
          AND w.is_group = 0
          AND w.disabled = 0
          AND b.actual_qty > 0
        ORDER BY b.actual_qty DESC
        """,
        (item_code, company, line_warehouse or ""),
        as_dict=True,
    )

    other_warehouses: list[dict] = []
    other_warehouses_qty = 0.0
    for b in rows:
        wh_avail = max(0.0, flt(b.actual_qty) - flt(b.reserved_qty_for_production))
        if wh_avail > 0:
            other_warehouses.append(
                {
                    "warehouse": b.warehouse,
                    "actual_qty": flt(b.actual_qty),
                    "available_qty": wh_avail,
                }
            )
            other_warehouses_qty += wh_avail

    return other_warehouses_qty, other_warehouses


def _resolve_company(company: str | None) -> str:
    resolved = (
        company
        or frappe.defaults.get_user_default("Company")
        or frappe.defaults.get_user_default("company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if not resolved:
        companies = frappe.get_all(
            "Company", filters={"is_group": 0}, pluck="name", limit=1
        )
        resolved = companies[0] if companies else None

    if not resolved:
        frappe.throw(_("Şirket bilgisi çözümlenemedi."), frappe.ValidationError)
    return resolved


def _resolve_default_bom(item_code: str) -> str:
    bom = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
        "name",
    )
    if not bom:
        bom = frappe.db.get_value(
            "BOM",
            {"item": item_code, "is_active": 1, "docstatus": 1},
            "name",
            order_by="creation desc",
        )
    if not bom:
        frappe.throw(
            _("Ürün için aktif reçete (BOM) bulunamadı: {0}").format(item_code),
            frappe.ValidationError,
        )
    return bom


def _resolve_default_warehouse(
    company: str, settings_field: str, item_code: str | None = None
) -> str | None:
    wh = frappe.db.get_single_value("Manufacturing Settings", settings_field)
    if wh and frappe.db.get_value("Warehouse", wh, "company") == company:
        return wh

    if item_code:
        item_wh = frappe.db.get_value(
            "Item Default",
            {"parent": item_code, "company": company},
            "default_warehouse",
        )
        if item_wh:
            return item_wh

    return frappe.db.get_value(
        "Warehouse",
        {"company": company, "is_group": 0, "disabled": 0},
        "name",
    )
