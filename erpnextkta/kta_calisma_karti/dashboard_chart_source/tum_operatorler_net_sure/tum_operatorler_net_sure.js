frappe.provide("frappe.dashboards.chart_sources");

if (typeof $ !== 'undefined' && !$("#tum-operatorler-net-sure-style").length) {
    $("<style id='tum-operatorler-net-sure-style'>")
        .html('[data-widget-name="Tum Operatorler Net Sure"] .axis.x .tick text { display: none !important; }')
        .appendTo("head");
}

frappe.dashboards.chart_sources["Tum Operatorler Net Sure"] = {
    method: "erpnextkta.kta_calisma_karti.dashboard_chart_source.tum_operatorler_net_sure.tum_operatorler_net_sure.get_data",
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
            fieldname: "department",
            label: __("Departman"),
            fieldtype: "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options("Department", txt, { parent_department: "Üretim" });
            },
        }
    ],
};
