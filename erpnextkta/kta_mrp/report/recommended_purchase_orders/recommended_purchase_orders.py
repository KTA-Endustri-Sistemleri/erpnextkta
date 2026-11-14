from collections import defaultdict
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate

from erpnextkta.kta_mrp.mrp_engine.service import get_material_requirements
from erpnextkta.kta_mrp.mrp_engine.weeks import (
    parse_week_key,
    sort_weeks,
    week_key,
    week_label,
    week_start,
)


def execute(filters=None):
    filters = dict(filters or {})
    if not filters.get("from_date"):
        from erpnextkta.kta_mrp.mrp_engine.capacity import get_monday_of_current_week

        filters["from_date"] = str(get_monday_of_current_week())
    demand_filters = {
        key: filters.get(key)
        for key in ("from_date", "to_date", "item_group")
        if filters.get(key)
    }
    result = get_material_requirements(demand_filters, include_po=True)

    if filters.get("from_date"):
        first_valid_week = week_key(getdate(filters["from_date"]))
    elif result and result.weeks:
        first_valid_week = result.weeks[0]
    else:
        first_valid_week = week_key(getdate())

    raw_rows = build_order_rows(result.materials.values(), first_valid_week)
    all_weeks = sort_weeks(w for r in raw_rows for w in r["order_weeks"])

    data = [get_row(r, all_weeks) for r in raw_rows]
    grand_total = sum(row["row_total"] for row in data)
    data.append(get_total_row(data, all_weeks, grand_total))

    report_summary = [
        {
            "value": max(0, len(data) - 1),
            "label": _("Önerilen PO Sayısı"),
            "indicator": "Blue",
        },
        {
            "value": frappe.format(grand_total, "Float"),
            "label": _("Toplam Önerilen Miktar"),
            "indicator": "Green",
        },
    ]
    return get_columns(all_weeks), data, None, None, report_summary


def shift_by_lead_time(
    planned_orders_or_material, lead_time_days=None, first_valid_week=None
):
    """Önerilen siparişleri (MOQ/paket MR'da uygulanmış) lead time kadar öne alır.

    first_valid_week belirtilmişse, o haftadan önceye düşen siparişler ilk geçerli haftaya çekilir
    ve is_past_due=True bayrağı döner.
    """
    if hasattr(planned_orders_or_material, "netting"):
        planned_orders = planned_orders_or_material.netting.planned_orders
        if lead_time_days is None:
            lead_time_days = planned_orders_or_material.lead_time_days
    else:
        planned_orders = planned_orders_or_material or {}

    order_weeks = defaultdict(float)
    is_past_due = False
    for week, qty in planned_orders.items():
        if qty > 0:
            order_date = week_start(week) - timedelta(days=lead_time_days or 0)
            raw_week = week_key(order_date)
            if first_valid_week and parse_week_key(raw_week) < parse_week_key(
                first_valid_week
            ):
                target_week = first_valid_week
                is_past_due = True
            else:
                target_week = raw_week
            order_weeks[target_week] += qty
    return order_weeks, is_past_due


def build_order_rows(materials, first_valid_week):
    """Her hammadde ve (kotalı ise) her tedarikçi için sipariş satırı üretir."""
    raw_rows = []
    for material in sorted(materials, key=lambda m: m.item_code):
        if material.netting.planned_order_total <= 0:
            continue

        sup_quota_map = {s.get("supplier"): s for s in (material.suppliers_quota or [])}

        # Kotalı dağılım veya çoklu tedarikçi siparişleri varsa
        if material.planned_orders_by_supplier:
            has_any_sup_order = False
            for sup_name, wk_orders in material.planned_orders_by_supplier.items():
                if sum(wk_orders.values()) <= 0:
                    continue
                has_any_sup_order = True
                sup_info = sup_quota_map.get(sup_name) or {}
                lead_time = (
                    sup_info.get("lead_time_days")
                    if sup_info.get("lead_time_days") is not None
                    else material.lead_time_days
                )
                moq = (
                    sup_info.get("moq")
                    if sup_info.get("moq") is not None
                    else material.moq
                )
                pack = (
                    sup_info.get("pack")
                    if sup_info.get("pack") is not None
                    else material.pack
                )

                shifted_weeks, is_past_due = shift_by_lead_time(
                    wk_orders, lead_time, first_valid_week
                )
                raw_rows.append(
                    {
                        "hammadde": material.item_code,
                        "uom": material.uom,
                        "supplier": sup_name,
                        "lead_time_days": lead_time,
                        "moq": moq,
                        "paket": pack,
                        "is_past_due": 1 if is_past_due else 0,
                        "status": _("Acil / Gecikmiş") if is_past_due else _("Normal"),
                        "order_weeks": shifted_weeks,
                    }
                )
            if has_any_sup_order:
                continue

        # Tek tedarikçi (veya planned_orders_by_supplier boş)
        shifted_weeks, is_past_due = shift_by_lead_time(
            material.netting.planned_orders,
            material.lead_time_days,
            first_valid_week,
        )
        raw_rows.append(
            {
                "hammadde": material.item_code,
                "uom": material.uom,
                "supplier": material.supplier,
                "lead_time_days": material.lead_time_days,
                "moq": material.moq,
                "paket": material.pack,
                "is_past_due": 1 if is_past_due else 0,
                "status": _("Acil / Gecikmiş") if is_past_due else _("Normal"),
                "order_weeks": shifted_weeks,
            }
        )

    return raw_rows


def get_row(raw_row, all_weeks):
    row = {
        "hammadde": raw_row["hammadde"],
        "uom": raw_row["uom"],
        "supplier": raw_row["supplier"],
        "lead_time_days": raw_row["lead_time_days"],
        "moq": raw_row["moq"],
        "paket": raw_row["paket"],
        "status": raw_row.get("status") or _("Normal"),
        "is_past_due": raw_row.get("is_past_due", 0),
    }
    order_weeks = raw_row["order_weeks"]
    for week in all_weeks:
        row[week] = round(order_weeks.get(week, 0), 2)
    row["row_total"] = round(sum(order_weeks.values()), 2)
    return row


def get_total_row(data, all_weeks, grand_total):
    total_row = {
        "hammadde": "<b>TOPLAM</b>",
        "supplier": "",
        "uom": "",
        "lead_time_days": "",
        "moq": "",
        "paket": "",
        "status": "",
        "is_past_due": 0,
    }
    for week in all_weeks:
        total_row[week] = round(sum(row[week] for row in data), 2)
    total_row["row_total"] = round(grand_total, 2)
    return total_row


def get_columns(all_weeks):
    return (
        [
            {
                "label": _("Hammadde"),
                "fieldname": "hammadde",
                "fieldtype": "Link",
                "options": "Item",
                "width": 140,
            },
            {
                "label": _("Tedarikçi"),
                "fieldname": "supplier",
                "fieldtype": "Link",
                "options": "Supplier",
                "width": 140,
            },
            {"label": _("Birim"), "fieldname": "uom", "fieldtype": "Data", "width": 80},
            {
                "label": _("Lead Time (Gün)"),
                "fieldname": "lead_time_days",
                "fieldtype": "Int",
                "width": 100,
            },
            {"label": _("MOQ"), "fieldname": "moq", "fieldtype": "Float", "width": 80},
            {
                "label": _("Paket Miktarı"),
                "fieldname": "paket",
                "fieldtype": "Float",
                "width": 100,
            },
            {
                "label": _("Durum"),
                "fieldname": "status",
                "fieldtype": "Data",
                "width": 110,
            },
        ]
        + [
            {
                "label": week_label(week),
                "fieldname": week,
                "fieldtype": "Float",
                "width": 100,
            }
            for week in all_weeks
        ]
        + [
            {
                "label": _("Satır Toplamı"),
                "fieldname": "row_total",
                "fieldtype": "Float",
                "width": 120,
            }
        ]
    )
