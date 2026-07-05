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
    }
});
