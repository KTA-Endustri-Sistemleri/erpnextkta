import frappe


def execute():
	"""MRP Analysis ve Material Requirement raporlarını arka plan (prepared) rapor modundan çıkarır.

	Frappe, standart raporların JSON'undaki `prepared_report` alanını mevcut sitelere
	aktarmaz (import_file ignore_values), bu yüzden değer patch ile güncellenir.
	"""
	for report_name in ("MRP Analysis", "Material Requirement"):
		if frappe.db.exists("Report", report_name):
			frappe.db.set_value("Report", report_name, "prepared_report", 0, update_modified=False)
