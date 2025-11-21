frappe.query_reports["Recommended Purchase Orders"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("Başlangıç Tarihi"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7)
        },
        {
            fieldname: "to_date",
            label: __("Bitiş Tarihi"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), 35)
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        if (column.fieldtype === "Float") {
            if (!value || value === 0) {
                return "";
            }

            return parseFloat(value).toLocaleString("tr-TR", {
                minimumFractionDigits: (value % 1 === 0) ? 0 : 2,
                maximumFractionDigits: 6
            });
        }

        return default_formatter(value, row, column, data);
    }
};
