frappe.provide("kta.report_utils");

kta.report_utils = {
    load_filters: function(report, report_name) {
        frappe.call({
            method: "erpnextkta.kta_mrp.report_utils.get_report_filters",
            args: { report_name: report_name },
            callback: function(r) {
                if (r.message) {
                    // Set page title
                    if (report.page) {
                        report.page.set_title(__(report_name));
                    }

                    // Set filters
                    report.filters = r.message.map(f => {
                        if (!f.onchange) {
                            f.onchange = () => report.refresh();
                        }
                        
                        if (f.fieldtype === "MultiSelectList" && typeof f.get_data === "string") {
                            const method_name = f.get_data;
                            f.get_data = function(txt) {
                                return frappe.db.get_link_options(method_name.match(/'([^']+)'/)[1], txt);
                            };
                        }
                        return f;
                    });

                    // Re-render filter area
                    if (report.make_filter_area) {
                        report.make_filter_area();
                    }
                    
                    if (report.refresh) {
                        report.refresh();
                    }
                } else if (r.exc) {
                    console.error("Filter loading failed:", r.exc);
                    frappe.msgprint(__("Filtreler yüklenirken bir hata oluştu."));
                }
            }
        });
    },

    std_formatter: function(value, row, column, data, default_formatter) {
        if (column.fieldtype === "Float") {
            if (!value || value === 0) {
                return "";
            }

            let formatted_value = parseFloat(value).toLocaleString("tr-TR", {
                minimumFractionDigits: value % 1 === 0 ? 0 : 2,
                maximumFractionDigits: 6,
            });

            // Negatif değerler için kırmızı vurgu
            if (value < 0) {
                return `<span style="color: #e74c3c; font-weight: bold;">${formatted_value}</span>`;
            }
            
            return formatted_value;
        }

        if (column.fieldtype === "Percent") {
            if (!value || value === 0) {
                return "";
            }

            return (
                parseFloat(value).toLocaleString("tr-TR", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 4,
                }) + "%"
            );
        }
        
        // Link alanları için özel badge stili (isteğe bağlı)
        if (column.fieldtype === "Link" && value) {
            if (column.options === "Item" || column.options === "Supplier") {
                 // Standart link kalsın ama belki bir ikon eklenebilir
            }
        }

        return default_formatter(value, row, column, data);
    },
    
    inject_report_styles: function() {
        const css = `
            .grid-static .slick-cell {
                border-right: 1px solid #f0f0f0 !important;
                border-bottom: 1px solid #f0f0f0 !important;
            }
            .report-summary {
                background: #f8f9fa;
                border-bottom: 1px solid #d1d8dd;
                padding: 15px;
                margin-bottom: 10px;
                border-radius: 8px;
            }
            .report-summary .summary-item {
                border-right: 1px solid #d1d8dd;
            }
            .report-summary .summary-item:last-child {
                border-right: none;
            }
            .report-summary .summary-value {
                font-size: 1.4em;
                font-weight: 700;
                color: var(--primary-color);
            }
            .report-summary .summary-label {
                font-size: 0.85em;
                color: #6c757d;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
        `;
        frappe.dom.set_style(css, "kta-report-styles");
    }
};

// Sayfa yüklendiğinde stilleri enjekte et
$(document).on("page-change", function() {
    if (frappe.get_route()[0] === "query-report") {
        kta.report_utils.inject_report_styles();
    }
});
