// Copyright (c) 2026, kta and contributors
// For license information, please see license.txt

frappe.query_reports["Aylik Hammadde Stok Analizi"] = {
    "filters": [
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "reqd": 0
        },
        {
            "fieldname": "item_code",
            "label": __("Item"),
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 0
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -6),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        if (column.fieldname === "fire_orani" && value !== null && value !== undefined) {
            return parseFloat(value).toFixed(2) + "%";
        }
        return default_formatter(value, row, column, data);
    }
};
