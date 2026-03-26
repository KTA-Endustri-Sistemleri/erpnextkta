/**
 * KTA Purchase Receipt — posting_date override
 *
 * Standart ERPNext'te posting_date değiştiğinde şu zincir çalışır:
 *   posting_date() → currency() → get_exchange_rate(posting_date) → conversion_rate() → apply_price_list()
 *
 * Bu zincir, tüm kalemlerin rate'lerini posting_date tarihli kur ile yeniden hesaplar.
 * Ancak KTA'da kur ve fiyat hesaplaması sunucu tarafında update_rates_logic() ile
 * rate_date (irsaliye_tarihi / gumruk_beyanname_tarihi) bazlı yapılır.
 *
 * Bu dosya, posting_date değişikliğinde frontend'in kur/fiyat zincirini tetiklemesini
 * engelleyerek yanlış tarihli kur hesaplamasının önüne geçer.
 */
frappe.ui.form.on("Purchase Receipt", {
    posting_date: function (frm) {
        // Standart handler'ın yaptığı tek faydalı şey: frm.posting_date'i güncellemek.
        if (frm.doc.posting_date) {
            frm.posting_date = frm.doc.posting_date;
        }
        // currency() tetiklemesini YAPMA.
        // Kur ve fiyat hesaplaması sunucu tarafında (update_rates_logic) yapılacak.
    }
});
