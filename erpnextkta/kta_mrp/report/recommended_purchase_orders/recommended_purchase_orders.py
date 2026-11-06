from collections import defaultdict
from datetime import timedelta

import frappe
from frappe import _

from erpnextkta.kta_mrp.mrp_engine.service import get_material_requirements
from erpnextkta.kta_mrp.mrp_engine.weeks import sort_weeks, week_key, week_label, week_start


def execute(filters=None):
	filters = dict(filters or {})
	if not filters.get("from_date"):
		from erpnextkta.kta_mrp.mrp_engine.capacity import get_monday_of_current_week
		filters["from_date"] = str(get_monday_of_current_week())
	demand_filters = {key: filters.get(key) for key in ("from_date", "to_date", "item_group") if filters.get(key)}
	result = get_material_requirements(demand_filters, include_po=True)
	orders = [m for m in result.materials.values() if m.netting.planned_order_total > 0]
	order_weeks = {m.item_code: shift_by_lead_time(m) for m in orders}
	all_weeks = sort_weeks(w for weeks in order_weeks.values() for w in weeks)

	data = [get_row(m, order_weeks[m.item_code], all_weeks) for m in sorted(orders, key=lambda m: m.item_code)]
	grand_total = sum(row["row_total"] for row in data)
	data.append(get_total_row(data, all_weeks, grand_total))

	report_summary = [
		{"value": len(data) - 1, "label": _("Önerilen PO Sayısı"), "indicator": "Blue"},
		{"value": frappe.format(grand_total, "Float"), "label": _("Toplam Önerilen Miktar"), "indicator": "Green"},
	]
	return get_columns(all_weeks), data, None, None, report_summary


def shift_by_lead_time(material):
	"""Önerilen siparişleri (MOQ/paket MR'da uygulanmış) lead time kadar öne alır."""
	order_weeks = defaultdict(float)
	for week, qty in material.netting.planned_orders.items():
		if qty > 0:
			order_date = week_start(week) - timedelta(days=material.lead_time_days or 0)
			order_weeks[week_key(order_date)] += qty
	return order_weeks


def get_row(material, order_weeks, all_weeks):
	row = {
		"hammadde": material.item_code,
		"uom": material.uom,
		"supplier": material.supplier,
		"lead_time_days": material.lead_time_days,
		"moq": material.moq,
		"paket": material.pack,
	}
	for week in all_weeks:
		row[week] = round(order_weeks.get(week, 0), 2)
	row["row_total"] = round(sum(order_weeks.values()), 2)
	return row


def get_total_row(data, all_weeks, grand_total):
	total_row = {"hammadde": "<b>TOPLAM</b>", "supplier": "", "uom": "", "lead_time_days": "", "moq": "", "paket": ""}
	for week in all_weeks:
		total_row[week] = round(sum(row[week] for row in data), 2)
	total_row["row_total"] = round(grand_total, 2)
	return total_row


def get_columns(all_weeks):
	return (
		[
			{"label": _("Hammadde"), "fieldname": "hammadde", "fieldtype": "Link", "options": "Item", "width": 140},
			{"label": _("Tedarikçi"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
			{"label": _("Birim"), "fieldname": "uom", "fieldtype": "Data", "width": 80},
			{"label": _("Lead Time (Gün)"), "fieldname": "lead_time_days", "fieldtype": "Int", "width": 100},
			{"label": _("MOQ"), "fieldname": "moq", "fieldtype": "Float", "width": 80},
			{"label": _("Paket Miktarı"), "fieldname": "paket", "fieldtype": "Float", "width": 100},
		]
		+ [{"label": week_label(week), "fieldname": week, "fieldtype": "Float", "width": 100} for week in all_weeks]
		+ [{"label": _("Satır Toplamı"), "fieldname": "row_total", "fieldtype": "Float", "width": 120}]
	)