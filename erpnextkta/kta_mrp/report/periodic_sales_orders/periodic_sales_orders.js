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
				{ "label": "Müşteri Grubu", "value": "Müşteri Grubu" },
				{ "label": "Ürün Grubu", "value": "Ürün Grubu" }
			],
			"default": "Müşteri",
			"on_change": function() {
				var tree_type = frappe.query_report.get_filter_value('tree_type');
				var filter = frappe.query_report.get_filter('tree_key');
				if (filter) {
					if (tree_type == 'Müşteri') {
						filter.df.options = 'Customer';
					} else if (tree_type == 'Müşteri Grubu') {
						filter.df.options = 'Customer Group';
					} else if (tree_type == 'Ürün Grubu') {
						filter.df.options = 'Item Group';
					}
					filter.refresh();
					frappe.query_report.set_filter_value('tree_key', '');
				}
			}
		},
		{
			"fieldname": "tree_key",
			"label": __("Filtre Değeri"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "show_pending_only",
			"label": __("Sadece Teslim Edilmemişler"),
			"fieldtype": "Check",
			"default": 1
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		if (window.kta && kta.report_utils && kta.report_utils.std_formatter) {
			return kta.report_utils.std_formatter(value, row, column, data, default_formatter);
		}
		return default_formatter(value, row, column, data);
	}
,
	after_datatable_render: function(datatable_obj) {
		if (window.kta && kta.report_utils && kta.report_utils.inject_summary) {
			kta.report_utils.inject_summary(frappe.query_report);
		}
	}
};