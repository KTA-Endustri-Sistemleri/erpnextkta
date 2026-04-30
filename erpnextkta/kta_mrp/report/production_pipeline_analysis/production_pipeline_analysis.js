frappe.query_reports["Production Pipeline Analysis"] = {
	"filters": [
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
			"fieldname": "dengeleme_yapilsin",
			"label": __("Kapasite Dengeleme Yapılsın mı?"),
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname": "ramp_up_aktif",
			"label": __("Ramp-up (Önden Üretim) Yapılsın mı?"),
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname": "ramp_up_weeks",
			"label": __("Ramp-up Süresi (Hafta)"),
			"fieldtype": "Int",
			"default": 3
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
