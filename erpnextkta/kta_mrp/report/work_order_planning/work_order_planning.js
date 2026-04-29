frappe.query_reports["Work Order Planning"] = {
	onload: function (report) {
	},

	filters: [
		{
			"fieldname": "from_date",
			"label": __("Başlangıç Tarihi"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("Bitiş Tarihi"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), 3),
			"reqd": 1
		},
		{
			"fieldname": "custom_musteri_grubu",
			"label": __("Müşteri Grubu"),
			"fieldtype": "Link",
			"options": "KTA Customer Group"
		},
		{
			"fieldname": "item_group",
			"label": __("Ürün Grubu"),
			"fieldtype": "Link",
			"options": "Item Group",
			"get_query": function() {
				const musteri_grubu = frappe.query_report.get_filter_value('custom_musteri_grubu');
				return {
					query: "erpnextkta.kta_mrp.report_utils.get_item_group_query",
					filters: {
						"custom_musteri_grubu": musteri_grubu
					}
				};
			}
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		if (window.kta && kta.report_utils && kta.report_utils.std_formatter) {
			return kta.report_utils.std_formatter(value, row, column, data, default_formatter);
		}
		return default_formatter(value, row, column, data);
	}
};
