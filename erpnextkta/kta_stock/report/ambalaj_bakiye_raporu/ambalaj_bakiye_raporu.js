// Copyright (c) 2026, KTA Endustri Sistemleri Ltd.Sti. and contributors
// For license information, please see license.txt

frappe.query_reports["Ambalaj Bakiye Raporu"] = {
	filters: [
		{ fieldname: "supplier", label: __("Tedarikçi"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "from_date", label: __("Başlangıç Tarihi"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("Bitiş Tarihi"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "hide_zero", label: __("Sıfır Bakiyeleri Gizle"), fieldtype: "Check", default: 1 },
	],
};
