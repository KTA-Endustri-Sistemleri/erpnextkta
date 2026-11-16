frappe.provide("kta.report_utils");

kta.report_utils = {
    get_planning_horizon_days: function() {
        return (frappe.boot && frappe.boot.kta_mrp_settings && frappe.boot.kta_mrp_settings.planning_horizon_days) || 90;
    },

    get_monday_of_current_week: function() {
        if (window.moment) {
            return window.moment().startOf("isoWeek").format("YYYY-MM-DD");
        }
        let now = new Date();
        let day = now.getDay();
        let diff = now.getDate() - day + (day === 0 ? -6 : 1);
        let monday = new Date(now.setDate(diff));
        return monday.toISOString().split("T")[0];
    },

    get_default_to_date: function(from_date) {
        let monday = kta.report_utils.get_monday_of_current_week();
        let start = from_date || monday;
        let days = kta.report_utils.get_planning_horizon_days();
        return frappe.datetime.add_days(start, days);
    },

    sync_mrp_date_filters: function(report) {
        if (!report) return;
        frappe.db.get_single_value("KTA MRP Settings", "planning_horizon_days").then((days) => {
            if (!days) return;
            days = parseInt(days, 10);
            if (frappe.boot) {
                frappe.boot.kta_mrp_settings = frappe.boot.kta_mrp_settings || {};
                frappe.boot.kta_mrp_settings.planning_horizon_days = days;
            }
            let monday = kta.report_utils.get_monday_of_current_week();
            let from_filter = report.get_filter("from_date");
            if (from_filter && from_filter.get_value() !== monday) {
                from_filter.set_value(monday);
            }
            let to_filter = report.get_filter("to_date");
            if (to_filter) {
                let from_val = (from_filter && from_filter.get_value()) || monday;
                let target_to_date = frappe.datetime.add_days(from_val, days);
                let current_to_val = to_filter.get_value();
                if (current_to_val !== target_to_date) {
                    to_filter.set_value(target_to_date);
                }
            }
        });
    },

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
    },

    inject_summary: function(query_report) {
        if (!query_report || !query_report.raw_data || !query_report.raw_data.message) return;
        
        let msg = query_report.raw_data.message;
        if (typeof msg === "string" && msg.indexOf("mrp-summary-container") !== -1) {
            let $summary_container = query_report.page.main.find('.kta-custom-summary');
            if ($summary_container.length === 0) {
                $summary_container = $('<div class="kta-custom-summary"></div>');
                if (query_report.$chart && query_report.$chart.length) {
                    $summary_container.insertBefore(query_report.$chart);
                } else if (query_report.$report && query_report.$report.length) {
                    $summary_container.insertBefore(query_report.$report);
                } else {
                    query_report.page.main.append($summary_container);
                }
            }
            $summary_container.html(msg).show();
            
            // Eğer frappe varsayılan olarak bu message'i status bar'a yazdıysa temizle
            if (query_report.$status) {
                let status_html = query_report.$status.html();
                if (status_html && status_html.indexOf("mrp-summary-container") !== -1) {
                    query_report.$status.empty().hide();
                }
            }
        }
    }
};

// Sayfa yüklendiğinde stilleri enjekte et
$(document).on("page-change", function() {
    if (frappe.get_route()[0] === "query-report") {
        kta.report_utils.inject_report_styles();
    }
});
