import frappe
from frappe import scrub
from frappe.utils import getdate
from datetime import date

from erpnextkta.kta_mrp.mrp_engine.psw import calculate_psw_demand
from erpnextkta.kta_mrp.report.report_utils import get_modern_summary_html


class ProductionStartWeekReport:
	def __init__(self, filters):
		self.filters = frappe._dict(filters or {})
		today = date.today()

		self.filters.from_date = self.filters.get("from_date") or date(today.year, 1, 1)
		self.filters.to_date = self.filters.get("to_date") or date(today.year, 12, 31)
		self.filters.range = self.filters.get("range", "Weekly")
		self.filters.tree_type = self.filters.get("tree_type", "Müşteri")
		self.filters.group_by_item_only = int(self.filters.get("group_by_item_only", 0))
		self.filters.doc_type = "Sales Order"

		self.columns = []
		self.data = []
		self.periodic_ranges = []

	def run(self):
		psw_result = calculate_psw_demand(self.filters)
		self.periodic_ranges = psw_result.periodic_ranges
		self.build_columns()
		self.data = psw_result.rows

		chart = self.get_chart()
		summary = self.get_summary()
		html_summary = get_modern_summary_html(summary)

		return self.columns, self.data, html_summary, chart, None

	def build_columns(self):
		tree_doctype = {"Müşteri": "Customer", "Müşteri Grubu": "Customer Group"}.get(self.filters.tree_type, "Customer")
		self.columns = [
			{"label": "Ürün Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 120},
			{"label": "Ürün Kodu", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
			{"label": "Ürün Adı", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		]
		if not self.filters.group_by_item_only:
			self.columns.insert(1, {"label": self.filters.tree_type, "fieldname": "tree_key", "fieldtype": "Link", "options": tree_doctype, "width": 150})
		for _, end in self.periodic_ranges:
			label = self.get_period_label(end)
			self.columns.append({"label": label, "fieldname": scrub(label), "fieldtype": "Int", "width": 120})
		self.columns += [
			{"label": "Stok Karşılanan", "fieldname": "stock_covered", "fieldtype": "Int", "width": 100},
			{"label": "İş Emrinde Olan", "fieldname": "wip_covered", "fieldtype": "Int", "width": 100},
			{"label": "Üretilecek", "fieldname": "to_produce", "fieldtype": "Int", "width": 100},
			{"label": "Satış Siparişi Talebi", "fieldname": "sales_order_demand", "fieldtype": "Int", "width": 140},
			{"label": "Dahili Üretim Talebi", "fieldname": "internal_demand", "fieldtype": "Int", "width": 140},
			{"label": "Toplam", "fieldname": "total", "fieldtype": "Int", "width": 120},
			{"label": "Birim", "fieldname": "unit", "fieldtype": "Data", "width": 80},
		]

	def get_chart(self):
		labels = [self.get_period_label(end) for _, end in self.periodic_ranges]
		prod_totals = {l: 0 for l in labels}
		for row in self.data:
			for l in labels:
				prod_totals[l] += row.get(scrub(l), 0)

		return {
			"data": {"labels": labels, "datasets": [{"name": "Üretilecek", "values": [prod_totals[l] for l in labels]}]},
			"type": "bar",
			"colors": ["#e67e22"],
		}

	def get_summary(self):
		total_prod = sum(row.get("to_produce", 0) for row in self.data)
		total_stock = sum(row.get("stock_covered", 0) for row in self.data)
		total_wip = sum(row.get("wip_covered", 0) for row in self.data)
		return [
			{"value": total_prod, "label": "Toplam Üretilecek", "indicator": "Orange"},
			{"value": total_wip, "label": "İş Emrinde Olan", "indicator": "Blue"},
			{"value": total_stock, "label": "Stoktan Karşılanan", "indicator": "Green"},
		]

	def get_period_label(self, date_obj):
		if not date_obj:
			return None
		date_obj = getdate(date_obj)
		iso_year, iso_week, _ = date_obj.isocalendar()
		return f"{iso_year}-W{iso_week:02d}"


def execute(filters=None):
	return ProductionStartWeekReport(filters).run()
