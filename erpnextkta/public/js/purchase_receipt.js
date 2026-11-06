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

    refresh: function (frm) {
        toggle_eta_mandatory(frm);
    },

    posting_date: function (frm) {
        // frappe.ui.form.on handler'ı da override et (ek güvenlik).
        if (frm.doc.posting_date) {
            frm.posting_date = frm.doc.posting_date;
        }
        // currency() tetiklemesini YAPMA.
    },

    workflow_state: function (frm) {
        toggle_eta_mandatory(frm);
        set_clearance_start_date(frm);
    },

    is_import_purchase_receipt: function (frm) {
        toggle_eta_mandatory(frm);
    }
});

function toggle_eta_mandatory(frm) {
    const state = (frm.doc.workflow_state || "").toLowerCase();
    const is_yolda = state.includes("yol");
    frm.set_df_property("tahmini_varis_tarihi", "reqd", is_yolda ? 1 : 0);
}

function set_clearance_start_date(frm) {
    const state = (frm.doc.workflow_state || "").toLowerCase();
    if ((state.includes("gümrükleme") || state.includes("gumrukleme")) && !frm.doc.custom_gumruk_islem_baslama_tarihi) {
        // Gümrükleme başlatıldığında işlem başlama tarihini bugün yap
        frm.set_value("custom_gumruk_islem_baslama_tarihi", frappe.datetime.get_today());
    }
}
