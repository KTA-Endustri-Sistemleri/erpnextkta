frappe.query_reports["Shipment Week"] = {
    "filters": [
        {
            fieldname: "from_date",
            label: __("Başlangıç Tarihi"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("Bitiş Tarihi"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), 2),
            reqd: 1
        },
        {
            fieldname: "tree_key",
            label: __("Müşteri"),
            fieldtype: "Link",
            options: "Customer",
            reqd: 0
        }
    ]
}
