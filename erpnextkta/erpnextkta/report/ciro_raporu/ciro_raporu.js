frappe.query_reports["İrsaliye Bazlı Satış Özeti"] = {
    filters: [
        {
            fieldname: "customer",
            label: "Müşteri",
            fieldtype: "Link",
            options: "Customer"
        }
    ]
}
