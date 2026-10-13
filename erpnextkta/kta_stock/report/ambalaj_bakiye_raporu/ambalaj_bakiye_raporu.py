# Copyright (c) 2026, KTA Endustri Sistemleri Ltd.Sti. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

DOCTYPE = "Iade Edilebilir Ambalaj Fisi"


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Tedarikçi"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 220},
		{"label": _("Tedarikçi Adı"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 220},
		{"label": _("Toplam Giriş"), "fieldname": "total_in", "fieldtype": "Int", "width": 130},
		{"label": _("Toplam Çıkış"), "fieldname": "total_out", "fieldtype": "Int", "width": 130},
		{"label": _("Bakiye"), "fieldname": "balance", "fieldtype": "Int", "width": 120},
		{"label": _("Son İşlem Tarihi"), "fieldname": "last_posting_date", "fieldtype": "Date", "width": 130},
	]


def get_conditions(filters):
	conditions = {"docstatus": 1}
	if filters.get("supplier"):
		conditions["supplier"] = filters["supplier"]
	if filters.get("from_date") and filters.get("to_date"):
		conditions["posting_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("to_date"):
		conditions["posting_date"] = ["<=", filters["to_date"]]
	return conditions


def get_data(filters):
	rows = frappe.get_all(
		DOCTYPE,
		filters=get_conditions(filters),
		fields=["supplier", "type", "sum(qty) as total", "max(posting_date) as last_posting_date"],
		group_by="supplier, type",
	)
	summary = {}
	for d in rows:
		entry = summary.setdefault(d.supplier, {"supplier": d.supplier, "total_in": 0, "total_out": 0, "last_posting_date": None})
		entry["total_in" if d.type == "Giriş" else "total_out"] += flt(d.total)
		if not entry["last_posting_date"] or d.last_posting_date > entry["last_posting_date"]:
			entry["last_posting_date"] = d.last_posting_date
	return finalize_rows(summary.values(), filters)


def finalize_rows(entries, filters):
	names = dict(frappe.get_all("Supplier", fields=["name", "supplier_name"], as_list=True))
	data = []
	for d in entries:
		d["balance"] = d["total_in"] - d["total_out"]
		d["supplier_name"] = names.get(d["supplier"])
		if filters.get("hide_zero") and not d["balance"]:
			continue
		data.append(d)
	return sorted(data, key=lambda d: d["balance"], reverse=True)
