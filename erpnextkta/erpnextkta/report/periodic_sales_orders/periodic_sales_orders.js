frappe.query_reports["Periodic Sales Orders"] = {
    "filters": [
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
            "label": __("Müşteri"),
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

    onload: function(report) {
        report.page.set_title(__("Periodic Sales Orders"));

        frappe.query_report.set_filter_value("tree_type", "Müşteri");

        frappe.query_report.get_filter("tree_type").$input.on("change", function () {
            const selected = frappe.query_report.get_filter_value("tree_type");
            const tree_key_filter = frappe.query_report.get_filter("tree_key");

            if (selected === "Müşteri") {
                tree_key_filter.df.options = "Customer";
                tree_key_filter.df.label = __("Müşteri");
            } else if (selected === "Müşteri Grubu") {
                tree_key_filter.df.options = "Customer Group";
                tree_key_filter.df.label = __("Müşteri Grubu");
            }

            tree_key_filter.refresh();
        });
    }
};