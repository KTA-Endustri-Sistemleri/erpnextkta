// Copyright (c) 2024, KTA
// For license information, please see license.txt

frappe.ui.form.on("KTA Stock Label", {
    refresh(frm) {
        // Yeniden Bas butonu - her zaman göster
        frm.add_custom_button(__("Yeniden Bas"), function () {
            frappe.confirm(
                __("Bu etiketi tekrar yazıcıya göndermek istediğinize emin misiniz?"),
                function () {
                    frappe.call({
                        method: "erpnextkta.kta_stock.label_manager.reprint_depo_label",
                        args: { label_name: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Yazıcıya gönderiliyor..."),
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.show_alert({
                                    message: __("Etiket kuyruğa alındı. Kısa süre içinde yazıcıdan çıkacaktır."),
                                    indicator: "green"
                                }, 5);
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }, __("Etiket"));

        // İlk kez basılmamışsa uyarı göster
        if (!frm.doc.print_count || frm.doc.print_count === 0) {
            frm.dashboard.add_comment(
                __("Bu etiket henüz yazıcıya gönderilmemiş."),
                "orange",
                true
            );
        }
    }
});
