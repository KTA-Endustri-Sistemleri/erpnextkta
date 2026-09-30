// Copyright (c) 2026, Framras AS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Iade Edilebilir Ambalaj Fisi", {
	setup: function(frm) {
		frm.set_query("purchase_receipt", function() {
			if (frm.doc.supplier) {
				return {
					filters: {
						supplier: frm.doc.supplier,
						docstatus: 1 // Sadece onaylanmış irsaliyeler
					}
				};
			} else {
				return {
					filters: {
						docstatus: 1
					}
				};
			}
		});
	},
    
    refresh: function(frm) {
        frm.trigger("type");
    },
    
    type: function(frm) {
        // Giriş yapılıyorsa Mal Alım İrsaliyesi seçmek zorunlu olsun
        frm.toggle_reqd("purchase_receipt", frm.doc.type === "Giriş");
    },
	
	purchase_receipt: function(frm) {
		if (frm.doc.purchase_receipt) {
            if (frm.doc.type !== "Giriş") {
                frm.set_value("type", "Giriş");
            }

			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "Purchase Receipt",
					name: frm.doc.purchase_receipt
				},
				callback: function(r) {
					if (r.message) {
                        // İrsaliye seçilince, henüz tedarikçi girilmediyse veya farklıysa otomatik doldur
                        if (r.message.supplier && (!frm.doc.supplier || frm.doc.supplier !== r.message.supplier)) {
                            frm.set_value("supplier", r.message.supplier);
                        }

						if (r.message.items) {
                            let total_makara = 0;
                            let hesaplama_detayi = "";
                            
                            r.message.items.forEach(item => {
                                let acc_qty = item.qty || 0;
                                let split_qty = item.custom_split_qty || 0;
                                
                                if (acc_qty > 0 && split_qty > 0) {
                                    let makara = Math.ceil(acc_qty / split_qty);
                                    total_makara += makara;
                                    hesaplama_detayi += `<li>${item.item_code}: ${acc_qty} / ${split_qty} = <b>${makara} ${__("Adet")}</b></li>`;
                                }
                            });
                            
                            if (total_makara > 0) {
                                frappe.msgprint({
                                    title: __('Tahmini Ambalaj Sayısı'),
                                    message: __('Seçilen irsaliyedeki kalemlere göre hesaplanan ambalaj/konipak sayısı: <b>{0}</b><br><ul>{1}</ul>Lütfen <b>Adet</b> alanına bu değeri veya fiziki sayım sonucunuzu girerek doğrulayın.', [total_makara, hesaplama_detayi]),
                                    indicator: 'blue'
                                });
                                
                                frm.set_value("calculated_qty", total_makara);
                            } else {
                                frm.set_value("calculated_qty", 0);
                            }
                        }
					}
				}
			});
		} else {
            frm.set_value("calculated_qty", 0);
        }
	}
});
