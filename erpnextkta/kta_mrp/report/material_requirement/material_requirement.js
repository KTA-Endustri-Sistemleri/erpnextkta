frappe.query_reports["Material Requirement"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("Başlangıç Tarihi"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("Bitiş Tarihi"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), 90),
            reqd: 1
        },
        {
            fieldname: "stage",
            label: __("Aşama"),
            fieldtype: "Select",
            options: [
                "1 - Temel Hammadde İhtiyacı",
                "2 - Stokları Düş",
                "3 - PO Teslimatlarını Düş"
            ],
            default: "1 - Temel Hammadde İhtiyacı",
            onchange: function () {
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "group_by",
            label: __("Gruplama Şekli"),
            fieldtype: "Select",
            options: [
                "Bitmiş Ürün + Hammadde",
                "Sadece Hammadde"
            ],
            default: "Bitmiş Ürün + Hammadde",
            onchange: function () {
                frappe.query_report.refresh();
            }
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        if (column.fieldtype === "Float") {
            if (!value || value === 0) {
                return "";
            }

            // Ondalık .00 gösterimini kaldır, sadece gerektiği kadar basamak
            return parseFloat(value).toLocaleString("tr-TR", {
                minimumFractionDigits: (value % 1 === 0) ? 0 : 2,
                maximumFractionDigits: 6
            });
        }

        return default_formatter(value, row, column, data);
    }
};