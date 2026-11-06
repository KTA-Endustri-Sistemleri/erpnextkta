frappe.query_reports["Production Pipeline Analysis"] = {
	onload: function (report) {
		if (window.kta && kta.report_utils && kta.report_utils.sync_mrp_date_filters) {
			kta.report_utils.sync_mrp_date_filters(report);
		}
	},
	"filters": [
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
			"fieldname": "customer",
			"label": __("Müşteri"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "item_group",
			"label": __("Ürün Grubu"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "warehouses",
			"label": __("Depolar (Bitmiş Ürün Depolarını Seçin)"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options("Warehouse", txt);
			}
		}
	],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        if (column.fieldname == "stage" && row && row.stage) {
            if (row.stage.includes("1.")) {
                value = `<span style="color: #e74c3c; font-weight: bold;">${value}</span>`;
            } else if (row.stage.includes("2.")) {
                value = `<span style="color: #3498db; font-weight: bold;">${value}</span>`;
            } else if (row.stage.includes("3.")) {
                value = `<span style="color: #f39c12; font-weight: bold;">${value}</span>`;
            } else if (row.stage.includes("4.")) {
                value = `<span style="color: #27ae60; font-weight: bold;">${value}</span>`;
            }
        }
        
        return value;
    }
};
