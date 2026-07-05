# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    if not filters or (not filters.get("work_order") and not filters.get("operator") and not filters.get("item_code")):
        frappe.msgprint(_("Lütfen İş Emri, Operatör veya Hammadde seçiniz."))
        return [], []

    columns, data = _get_pivot_data(filters.get("work_order"), filters.get("operator"), filters.get("item_code"))
    return columns, data


def _get_pivot_data(work_order_filter: str = None, operator_filter: str = None, item_filter: str = None):
    """Fetch consumption data and pivot it as Operator x Items."""
    material_slots = [
        ("hammadde", "adet", "uom"),
        ("hammadde_2", "adet_2", "uom_2"),
        ("hammadde_3", "adet_3", "uom_3"),
    ]

    conditions = []
    query_params = []

    if work_order_filter:
        conditions.append("ck.custom_work_order = %s")
        query_params.append(work_order_filter)

    if operator_filter:
        conditions.append("ck.operator = %s")
        query_params.append(operator_filter)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    rows = frappe.db.sql(
        f"""
        SELECT
            ck.operator,
            aok.hammadde,   aok.adet,   aok.uom,
            aok.hammadde_2, aok.adet_2, aok.uom_2,
            aok.hammadde_3, aok.adet_3, aok.uom_3
        FROM `tabCalisma Karti Alt Operasyon Kayitlari` aok
        JOIN `tabCalisma Karti` ck ON ck.name = aok.parent
        WHERE {where_clause}
        """,
        tuple(query_params),
        as_dict=True,
    )

    operator_data = {}
    item_names = {}
    item_uoms = {}
    employee_names = {}

    for r in rows:
        for h_field, a_field, u_field in material_slots:
            item_code = r.get(h_field)
            qty = flt(r.get(a_field))
            uom = r.get(u_field)

            if not item_code or qty == 0:
                continue

            if item_filter and item_code != item_filter:
                continue

            operator = r.operator
            if operator and operator not in employee_names:
                employee_names[operator] = frappe.db.get_value("Employee", operator, "employee_name") or operator

            if item_code not in item_names:
                item_names[item_code] = frappe.db.get_value("Item", item_code, "item_name") or item_code
                item_uoms[item_code] = uom

            if operator not in operator_data:
                operator_data[operator] = {
                    "operator": operator,
                    "operator_name": employee_names.get(operator, ""),
                }

            if item_code not in operator_data[operator]:
                operator_data[operator][item_code] = 0.0

            operator_data[operator][item_code] += qty

    # Build dynamic columns
    columns = [
        {
            "label": _("Operatör"),
            "fieldname": "operator",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 140,
        },
        {
            "label": _("Operatör Adı"),
            "fieldname": "operator_name",
            "fieldtype": "Data",
            "width": 160,
        }
    ]

    unique_items = list(item_names.keys())
    unique_items.sort()

    for item_code in unique_items:
        # We put the UOM in the column header so it is completely clear!
        uom_str = item_uoms.get(item_code, "")
        columns.append({
            "label": f"{item_code} ({uom_str})",
            "fieldname": item_code,
            "fieldtype": "Float",
            "width": 150,
        })

    data = list(operator_data.values())

    # Add a final Grand Total row that safely sums the columns!
    if data:
        data.sort(key=lambda x: x.get("operator_name") or "")
        
        # Add a visual spacer (will be empty)
        data.append({"is_spacer": 1})
        
        total_row = {"operator": None, "operator_name": frappe.bold(_("GENEL TOPLAM")), "is_spacer": 1}
        for item_code in unique_items:
            total_row[item_code] = sum(flt(d.get(item_code)) for d in data if not d.get("is_spacer"))
        
        data.append(total_row)

    return columns, data
