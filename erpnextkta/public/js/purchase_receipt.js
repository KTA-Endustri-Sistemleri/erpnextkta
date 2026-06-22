/**
 * KTA Purchase Receipt — posting_date override
 *
 * Standart ERPNext'te posting_date değiştiğinde şu zincir çalışır:
 *   posting_date() → currency() → get_exchange_rate(posting_date) → conversion_rate() → apply_price_list()
 *
 * Bu zincir tüm kalem rate'lerini posting_date tarihli kur ile yeniden hesaplar.
 * KTA'da kur/fiyat hesaplaması sunucu tarafında update_rates_logic() ile
 * rate_date (irsaliye_tarihi / gumruk_beyanname_tarihi) bazlı yapılır.
 *
 * frappe.ui.form.on() tek başına yetmez çünkü controller class method'u
 * (cur_frm.cscript.posting_date) bağımsız olarak çalışır.
 * Bu yüzden setup event'inde controller method'unu da override ediyoruz.
 */
frappe.ui.form.on("Purchase Receipt", {
    setup: function (frm) {
        // Controller class'ın posting_date() method'unu override et.
        // Bu method cur_frm.cscript üzerinden çağrılır ve
        // currency() → get_exchange_rate() → apply_price_list() zincirini tetikler.
        frm.cscript.posting_date = function () {
            if (frm.doc.posting_date) {
                frm.posting_date = frm.doc.posting_date;
            }
            // currency() tetiklemesini YAPMA.
            // Kur ve fiyat hesaplaması sunucu tarafında (update_rates_logic) yapılacak.
        };
    },

    posting_date: function (frm) {
        // frappe.ui.form.on handler'ı da override et (ek güvenlik).
        if (frm.doc.posting_date) {
            frm.posting_date = frm.doc.posting_date;
        }
        // currency() tetiklemesini YAPMA.
    },

    refresh: function (frm) {
        // Sadece onaylı (submitted) belgeler için etiket butonu göster
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Etiketleri Yeniden Bas"), function () {
                frappe.confirm(
                    __("Bu irsaliyeye ait tüm etiketleri tekrar yazıcıya göndermek istiyor musunuz?"),
                    function () {
                        frappe.call({
                            method: "erpnextkta.kta_stock.label_manager.print_kta_pr_labels",
                            args: { gr_number: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Etiketler yazıcıya gönderiliyor..."),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: __("Etiketler yazıcıya gönderildi."),
                                        indicator: "green"
                                    }, 5);
                                }
                            }
                        });
                    }
                );
            }, __("KTA"));
        }
    }
});
