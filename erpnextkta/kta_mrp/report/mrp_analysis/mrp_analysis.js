frappe.query_reports["MRP Analysis"] = {
	onload: function (report) {
	},

	filters: [
		{
			"fieldname": "periyot",
			"label": __("Periyot"),
			"fieldtype": "Select",
			"options": ["Yıllık", "3 Aylık", "6 Aylık", "Süresiz", "Özel"],
			"default": "Yıllık",
			"on_change": function () {
				let report = frappe.query_report;
				let periyot = report.get_filter_value("periyot");
				let is_custom = periyot === "Özel";
				report.get_filter("from_date").toggle(is_custom);
				report.get_filter("to_date").toggle(is_custom);
			},
		},
		{
			"fieldname": "from_date",
			"label": __("Başlangıç Tarihi"),
			"fieldtype": "Date",
			"hidden": 1,
		},
		{
			"fieldname": "to_date",
			"label": __("Bitiş Tarihi"),
			"fieldtype": "Date",
			"hidden": 1,
		},
		{
			"fieldname": "item_group",
			"label": __("Ürün Grubu"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "musteri_grubu",
			"label": __("Müşteri Grubu"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options('KTA Customer Group', txt);
			}
		},
		{
			"fieldname": "sifir_tuketimi_goster",
			"label": __("Sıfır Tüketimi Göster"),
			"fieldtype": "Check",
			"default": 0,
		},
		{
			"fieldname": "fiyat_varsayilan_tedarikci",
			"label": __("Fiyatı Varsayılan Tedarikçiden Al"),
			"fieldtype": "Check",
			"default": 0
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		if (window.kta && kta.report_utils && kta.report_utils.std_formatter) {
			return kta.report_utils.std_formatter(value, row, column, data, default_formatter);
		}
		return default_formatter(value, row, column, data);
	}
};
