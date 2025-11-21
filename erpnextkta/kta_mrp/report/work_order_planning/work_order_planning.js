frappe.query_reports["Work Order Planning"] = {
    "filters": [
        {
            fieldname: "from_date",
            label: __("Başlangıç Tarihi"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "to_date",
            label: __("Bitiş Tarihi"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.get_today(), 3)
        },
        {
            fieldname: "item_group",
            label: __("Ürün Grubu"),
            fieldtype: "Select",
            options: []
        }
    ],

    onload: function (report) {
        frappe.call({
            method: "erpnextkta.kta_mrp.report.work_order_planning.work_order_planning.get_available_item_groups",
            args: {
                filters: frappe.query_report.get_filter_values()
            },
            callback: function (r) {
                const field = report.get_filter('item_group');
                const groups = (r.message || []);
                groups.unshift("");  // "Tümü" seçeneği
                field.df.options = groups;
                field.refresh();
            }
        });
    }
};
