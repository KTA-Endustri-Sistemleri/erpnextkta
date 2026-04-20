frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Operator Net Sure"] = {
    method: "erpnextkta.kta_calisma_karti.dashboard_chart_source.operator_net_sure.operator_net_sure.get_data",
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
        {
            fieldname: "top_n",
            label: __("Gösterilecek Operatör Sayısı"),
            fieldtype: "Select",
            options: [
                { value: 5, label: "Top 5" },
                { value: 10, label: "Top 10" },
                { value: 15, label: "Top 15" },
                { value: 20, label: "Top 20" },
            ],
            default: 15,
        },
    ],
};
