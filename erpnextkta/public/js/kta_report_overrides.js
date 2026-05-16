frappe.provide("kta.report_overrides");

/**
 * Bu dosya, standart ERPNext raporlarına yapılan dinamik müdahaleleri (overrides) içerir.
 * Yeni bir rapor özelleştirmesi eklendiğinde kta.report_overrides nesnesi altına 
 * rapor ismiyle bir fonksiyon eklenmelidir.
 */

kta.report_overrides = {
    "BOM Stock Report": function(report) {
        if (!report) return;

        // 1. Global konfigürasyonu güncelle (Filtre seçimi ve tooltip için)
        let config = frappe.query_reports["BOM Stock Report"];
        if (config && config.filters && !config.filters.find(f => f.fieldname === "only_default_boms")) {
            let bom_idx = config.filters.findIndex(f => f.fieldname === "bom");
            if (bom_idx !== -1) {
                // BOM filtresinin sorgusunu checkbox'a duyarlı hale getir
                config.filters[bom_idx].get_query = function() {
                    let only_default = frappe.query_report.get_filter_value("only_default_boms");
                    let filters = { is_active: 1 };
                    if (only_default) filters.is_default = 1;
                    return { filters: filters };
                };

                // Checkbox filtresini ekle
                config.filters.splice(bom_idx + 1, 0, {
                    fieldname: "only_default_boms",
                    label: __("Only Default BOMs"),
                    fieldtype: "Check",
                    default: 0,
                    description: __("Sadece ürün kartında varsayılan olarak tanımlanmış aktif reçeteleri listeler."),
                    on_change: function() {
                        frappe.query_report.set_filter_value("bom", "");
                    }
                });
                
                // Instance filtrelerini konfigürasyonla senkronize et
                report.filters = config.filters;
            }
        }

        // 2. Mevcut instance üzerindeki get_query'yi sağlama al
        let bom_filter = report.filters.find(f => (f.fieldname === "bom" || (f.df && f.df.fieldname === "bom")));
        if (bom_filter && bom_filter.df) {
            bom_filter.df.get_query = function() {
                let only_default = 0;
                if (report.page && report.page.fields_dict && report.page.fields_dict.only_default_boms) {
                    only_default = report.page.fields_dict.only_default_boms.get_value();
                } else if (report.get_filter_value) {
                    only_default = report.get_filter_value("only_default_boms");
                }
                
                let filters = { is_active: 1 };
                if (only_default) filters.is_default = 1;
                return { filters: filters };
            };
        }

        // 3. Filtre alanını yeniden oluştur
        const render_fn = report.make_filter_area || report.make_filters || report.setup_filters;
        if (render_fn) render_fn.call(report);
    }
};

// Sayfa değişimlerinde ilgili raporun override fonksiyonunu tetikle
$(document).on("page-change", function() {
    if (frappe.get_route()[0] === "query-report") {
        let report_name = frappe.get_route()[1];
        
        if (kta.report_overrides[report_name]) {
            console.log(`[KTA Override] ${report_name} için özelleştirmeler yükleniyor...`);
            
            let check_interval = setInterval(() => {
                let report = frappe.query_report;
                if (report && report.report_name === report_name && report.filters && report.filters.length > 0) {
                    clearInterval(check_interval);
                    kta.report_overrides[report_name](report);
                }
            }, 200);
            
            setTimeout(() => clearInterval(check_interval), 10000);
        }
    }
});
