frappe.query_reports["Shipment Week"] = {
	onload: function (report) {
		if (window.kta && kta.report_utils && kta.report_utils.sync_mrp_date_filters) {
			kta.report_utils.sync_mrp_date_filters(report);
		}
	},

	filters: [
		{
			"fieldname": "from_date",
			"label": __("Başlangıç Tarihi"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("Bitiş Tarihi"),
			"fieldtype": "Date",
			"default": (window.kta && kta.report_utils && kta.report_utils.get_default_to_date)
				? kta.report_utils.get_default_to_date()
				: frappe.datetime.add_days(frappe.datetime.get_today(), 90),
			"reqd": 1
		},
		{
			"fieldname": "tree_key",
			"label": __("Müşteri"),
			"fieldtype": "Link",
			"options": "Customer"
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