frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Kalite Kontrol Dagilimi"] = {
    method:
        "erpnextkta.kta_calisma_karti.dashboard_chart_source.kalite_kontrol_dagilimi.kalite_kontrol_dagilimi.get_data",
    filters: [
        {
            fieldname: "days",
            label: __("Gün Sayısı"),
            fieldtype: "Select",
            options: [
                { value: 7, label: __("Son 7 Gün") },
                { value: 14, label: __("Son 14 Gün") },
                { value: 30, label: __("Son 30 Gün") },
                { value: 60, label: __("Son 60 Gün") },
                { value: 90, label: __("Son 90 Gün") },
            ],
            default: 30,
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
