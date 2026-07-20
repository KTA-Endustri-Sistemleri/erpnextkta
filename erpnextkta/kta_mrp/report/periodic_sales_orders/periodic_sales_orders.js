frappe.query_reports["Periodic Sales Orders"] = {
	onload: function (report) {
	},

	filters: [
		{
			"fieldname": "from_date",
			"label": __("Başlangıç Tarihi"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("Bitiş Tarihi"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "range",
			"label": __("Dönem Aralığı"),
			"fieldtype": "Select",
			"options": ["Weekly", "Monthly", "Quarterly", "Yearly"],
			"default": "Weekly"
		},
		{
			"fieldname": "value_quantity",
			"label": __("Değer Türü"),
			"fieldtype": "Select",
			"options": [
				{ "label": "Tutar", "value": "Value" },
				{ "label": "Miktar", "value": "Quantity" }
			],
			"default": "Quantity"
		},
		{
			"fieldname": "target_currency",
			"label": __("Hedef Döviz"),
			"fieldtype": "Link",
			"options": "Currency"
		},
		{
			"fieldname": "tree_type",
			"label": __("Sınıflandırma"),
			"fieldtype": "Select",
			"options": [
				{ "label": "Müşteri", "value": "Müşteri" },
				{ "label": "Müşteri Grubu", "value": "Müşteri Grubu" }
			],
			"default": "Müşteri"
		},
		{
			"fieldname": "tree_key",
			"label": __("Filtre Değeri"),
			"fieldtype": "Link",
			"get_query": function() {
				var tree_type = frappe.query_report.get_filter_value('tree_type');
				if (tree_type == 'Müşteri') {
					return { "doctype": "Customer" };
				} else {
					return { "doctype": "Customer Group" };
				}
			}
		},
		{
			"fieldname": "show_pending_only",
			"label": __("Sadece Teslim Edilmemişler"),
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname": "convert_pending_to_eur",
			"label": __("Bekleyenleri EUR'ya Çevir"),
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