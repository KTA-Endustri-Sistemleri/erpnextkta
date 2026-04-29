frappe.query_reports["Material Requirement"] = {
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
			"fieldname": "dengeleme_yapilsin",
			"label": __("Kapasite Dengeleme Yapılsın mı?"),
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname": "ramp_up_aktif",
			"label": __("Ramp-up (Önden Üretim) Yapılsın mı?"),
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname": "ramp_up_weeks",
			"label": __("Ramp-up Süresi (Hafta)"),
			"fieldtype": "Int",
			"default": 3
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
		},
		{
			"fieldname": "stage",
			"label": __("Aşama"),
			"fieldtype": "Select",
			"options": [
				"1 - Temel Hammadde İhtiyacı",
				"2 - Stokları Düş",
				"3 - PO Teslimatlarını Düş"
			],
			"default": "1 - Temel Hammadde İhtiyacı"
		},
		{
			"fieldname": "group_by",
			"label": __("Gruplama Şekli"),
			"fieldtype": "Select",
			"options": ["Bitmiş Ürün + Hammadde", "Sadece Hammadde"],
			"default": "Bitmiş Ürün + Hammadde"
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		if (window.kta && kta.report_utils && kta.report_utils.std_formatter) {
			return kta.report_utils.std_formatter(value, row, column, data, default_formatter);
		}
		return default_formatter(value, row, column, data);
	}
};