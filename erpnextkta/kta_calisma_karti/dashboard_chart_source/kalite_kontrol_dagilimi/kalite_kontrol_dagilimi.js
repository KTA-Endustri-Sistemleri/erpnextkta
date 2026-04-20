frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Kalite Kontrol Dagilimi"] = {
    method:
        "erpnextkta.kta_calisma_karti.dashboard_chart_source.kalite_kontrol_dagilimi.kalite_kontrol_dagilimi.get_data",
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
            fieldname: "operasyon",
            label: __("Operasyon"),
            fieldtype: "Link",
            options: "KTA Calisma Karti Operasyonlari",
        },
        {
            fieldname: "is_istasyonu",
            label: __("İş İstasyonu"),
            fieldtype: "Link",
            options: "Workstation",
        },
    ],
};
