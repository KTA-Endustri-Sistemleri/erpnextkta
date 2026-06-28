frappe.query_reports["İrsaliye Bazlı Satış Özeti"] = {
    filters: [
        {
            fieldname: "customer",
            label: __("Müşteri"),
            fieldtype: "Link",
            options: "Customer"
        }
    ]
}
