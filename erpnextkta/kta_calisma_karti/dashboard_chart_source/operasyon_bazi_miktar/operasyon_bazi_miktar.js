frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Operasyon Bazi Miktar"] = {
    method: "erpnextkta.kta_calisma_karti.dashboard_chart_source.operasyon_bazi_miktar.operasyon_bazi_miktar.get_data",
    filters: [
        {
            fieldname: "date_range",
            label: __("Tarih Aralığı"),
            fieldtype: "DateRange",
            default: [
                frappe.datetime.add_days(frappe.datetime.get_today(), -29),
                frappe.datetime.get_today(),
            ],
        },
        {
            fieldname: "is_istasyonu",
            label: __("İş İstasyonu"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Workstation", txt);
            },
        },
    ],
};
