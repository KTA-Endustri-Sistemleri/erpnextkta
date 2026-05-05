frappe.query_reports["MRP Analysis"] = {
	onload: function (report) {
		// Ara Malzeme Grubu seçeneklerini dinamik doldur
		frappe.call({
			method:
				"erpnextkta.kta_mrp.report.mrp_analysis.mrp_analysis.get_ara_malzeme_gruplari",
			callback: function (r) {
				const field = report.get_filter("ara_malzeme_grubu");
				const options = r.message || [];
				field.df.options = ["", ...options];
				field.refresh();
			},
		});

		// Hammadde Grubu (Item Group) seçeneklerini dinamik doldur
		frappe.call({
			method:
				"erpnextkta.kta_mrp.report.mrp_analysis.mrp_analysis.get_item_groups",
			callback: function (r) {
				const field = report.get_filter("item_group");
				const options = r.message || [];
				field.df.options = ["", ...options];
				field.refresh();
			},
		});
	},

	filters: [
		{
			fieldname: "periyot",
			label: __("Periyot"),
			fieldtype: "Select",
			options: ["Yıllık", "3 Aylık", "6 Aylık", "Süresiz", "Özel"],
			default: "Yıllık",
			on_change: function () {
				let report = frappe.query_report;
				let periyot = report.get_filter_value("periyot");
				let is_custom = periyot === "Özel";
				report.get_filter("from_date").toggle(is_custom);
				report.get_filter("to_date").toggle(is_custom);
			},
		},
		{
			fieldname: "from_date",
			label: __("Başlangıç Tarihi"),
			fieldtype: "Date",
			hidden: 1,
		},
		{
			fieldname: "to_date",
			label: __("Bitiş Tarihi"),
			fieldtype: "Date",
			hidden: 1,
		},
		{
			fieldname: "ara_malzeme_grubu",
			label: __("Ara Malzeme Grubu"),
			fieldtype: "Select",
			options: [],
		},
		{
			fieldname: "musteri_grubu",
			label: __("Müşteri Grubu"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("KTA Customer Group", txt);
			},
		},
		{
			fieldname: "item_group",
			label: __("Hammadde Grubu"),
			fieldtype: "Select",
			options: [],
		},
		{
			fieldname: "varsayilan_tedarikci",
			label: __("Varsayılan Tedarikçi"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "sifir_tuketimi_goster",
			label: __("Sıfır Tüketimi Göster"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		if (column.fieldtype === "Float") {
			if (!value || value === 0) {
				return "";
			}

			return parseFloat(value).toLocaleString("tr-TR", {
				minimumFractionDigits: value % 1 === 0 ? 0 : 2,
				maximumFractionDigits: 6,
			});
		}

		if (column.fieldtype === "Percent") {
			if (!value || value === 0) {
				return "";
			}

			return (
				parseFloat(value).toLocaleString("tr-TR", {
					minimumFractionDigits: 2,
					maximumFractionDigits: 4,
				}) + "%"
			);
		}

		return default_formatter(value, row, column, data);
	},
};
