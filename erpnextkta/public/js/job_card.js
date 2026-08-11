frappe.ui.form.on("Job Card", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Toplu Protokol Yazdır"), () => {
                frappe.call({
                    method: "erpnextkta.kta_calisma_karti.api.get_job_card_protocols_html",
                    args: { job_card: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Protokoller hazırlanıyor..."),
                    callback: (r) => {
                        if (r.message && r.message.html) {
                            const w = window.open("", "_blank", "width=1100,height=700");
                            if (w) {
                                w.document.write(r.message.html);
                                w.document.close();
                            }
                        } else {
                            frappe.msgprint(__("Bu iş kartına bağlı yazdırılacak protokol bulunamadı."));
                        }
                    }
                });
            }, __("Kalite"));
        }
        
        // Kısmi Üretim Bildirimi Butonu
        if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.time_logs && frm.doc.time_logs.length > 0) {
            frm.add_custom_button(__("Kısmi Üretim Bildir"), () => {
                frappe.prompt({
                    label: __("Tamamlanan Miktar"),
                    fieldname: "qty",
                    fieldtype: "Float",
                    reqd: 1,
                    description: __("Bu operasyonda üretilen toplam adet")
                }, (values) => {
                    frm.call("peel_off_partial_production", { qty: values.qty })
                        .then(r => {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __("Kısmi üretim {0} olarak oluşturuldu", [r.message]),
                                    indicator: "green"
                                });
                                frm.reload_doc();
                            }
                        });
                }, __("Kısmi Üretim Bildirimi"), __("Onayla"));
            }, __("İşlemler"));
        }
    }
});
