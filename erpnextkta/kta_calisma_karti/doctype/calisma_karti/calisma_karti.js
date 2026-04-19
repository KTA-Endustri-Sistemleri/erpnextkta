frappe.ui.form.on('Calisma Karti', {
  // --- 1) Link sorgu filtreleri ---
  setup(frm) {
    // Açık İş Emri filtresi (custom field)
    frm.set_query('custom_work_order', () => {
      return {
        filters: {
          status: ['in', ['Not Started', 'In Process']],
          docstatus: 1
        }
      };
    });

    // Seçilen İş Emri altındaki açık Job Card filtresi
    frm.set_query('is_karti', () => {
      const wo = frm.doc.custom_work_order || '';
      return {
        filters: {
          work_order: wo
        }
      };
    });
  },

  // --- 2) İş Emri değişince bağımlı alanları sıfırla ---
  custom_work_order(frm) {
    frm.set_value({
      is_karti: null,
      urun_kodu: null,
      uretilecek_miktar: null,
      is_istasyonu: null
    });
  },

  // --- 3) (İsteğe bağlı) Job Card seçilince alanları doldur ---
  is_karti(frm) {
    if (frm.doc.is_karti) {
      if (frm.doc.custom_work_order) {
        frappe.db.get_value('Job Card', frm.doc.is_karti, ['work_order', 'production_item', 'for_quantity', 'workstation'])
          .then(r => {
            const jc = r && r.message ? r.message : null;
            if (!jc) return;

            if (jc.work_order && frm.doc.custom_work_order && jc.work_order !== frm.doc.custom_work_order) {
              frappe.msgprint({
                title: __('Uyarı'),
                message: __('Seçilen İş Kartı, seçtiğiniz İş Emri\'ne ait değil. Lütfen doğru kartı seçin.'),
                indicator: 'orange'
              });
              frm.set_value({
                is_karti: null,
                urun_kodu: null,
                uretilecek_miktar: null,
                is_istasyonu: null
              });
              return;
            }

            frm.set_value('urun_kodu', jc.production_item || null);
            frm.set_value('uretilecek_miktar', jc.for_quantity || null);
            frm.set_value('is_istasyonu', jc.workstation || null);
          });
      } else {
        frappe.msgprint(__('Önce bir İş Emri seçin.'));
        frm.set_value('is_karti', null);
      }
    }
  },

  // --- 4) Mevcut akış ve butonlar ---
  refresh(frm) {
    frm.clear_custom_buttons();
    if (frm.doc.__islocal) return;

    const getDurum = () => {
      if (frm.doc.kalite_kontrol === 'Reddedildi' || frm.doc.durum === 'Reddedildi') return 'reddedildi';
      const aktifDurusVarMi = (frm.doc.duruslar || []).some(row => row && row.durus_baslangic && !row.durus_bitis);
      if (frm.doc.bitis_saati) return 'bitmis';
      if (!frm.doc.baslangic_saati) return 'hazir';
      if (aktifDurusVarMi) return 'durusta';
      return 'calisiyor';
    };

    const durum = getDurum();
    const durumRenkleri = { 'hazir': 'gray', 'calisiyor': 'green', 'durusta': 'orange', 'bitmis': 'blue', 'reddedildi': 'red' };
    const durumMetinleri = { 'hazir': 'Hazır', 'calisiyor': 'Çalışıyor', 'durusta': 'Duruşta', 'bitmis': 'Bitmiş', 'reddedildi': 'Reddedildi' };
    frm.dashboard.add_indicator(__('Durum: {0}', [durumMetinleri[durum]]), durumRenkleri[durum]);

    switch (durum) {
      case 'hazir': addBaslatButton(frm, false, 'İşlemi başlat'); break;
      case 'calisiyor': addDurusButton(frm); addBitisButton(frm); break;
      case 'durusta': addBaslatButton(frm, true, 'Duruştan devam et'); addBitisButton(frm); break;
      case 'reddedildi': break; // No action buttons for rejected cards
    }

    if (frm.doc.baslangic_saati) {
      frm.dashboard.add_indicator(__('Başlangıç: {0}', [
        frappe.datetime.get_datetime_as_string(frm.doc.baslangic_saati)
      ]), 'blue');
    }

    if (frm.doc.net_calisma_suresi) {
      frm.dashboard.add_indicator(__('Net Süre: {0}', [frm.doc.net_calisma_suresi]), 'cyan');
    }

    if (frm.doc.toplam_durus && frm.doc.toplam_durus !== "00:00:00") {
      frm.dashboard.add_indicator(__('Toplam Duruş: {0}', [frm.doc.toplam_durus]), 'orange');
    }

    // Makine Günlük Bakım Butonu
    frm.add_custom_button(__('Günlük Bakım Onayı'), () => {
      showMaintenanceDialog(frm);
    }, __("Özel Belgeler")).addClass('btn-primary btn-sm');
  },

  validate(frm) {
    if (!frm.doc.is_istasyonu) { frappe.msgprint(__('İş İstasyonu zorunludur')); frappe.validated = false; return; }
    if (!frm.doc.custom_work_order) { frappe.msgprint(__('İş Emri zorunludur')); frappe.validated = false; return; }
    if (!frm.doc.is_karti) { frappe.msgprint(__('İş Kartı zorunludur')); frappe.validated = false; return; }
    if (!frm.doc.operasyon) { frappe.msgprint(__('Operasyon zorunludur')); frappe.validated = false; return; }
  }
});

// ====== Mevcut akış butonları ======
function addBaslatButton(frm, isDurusDevami = false, customText = null) {
  const buttonText = customText || (isDurusDevami ? __('Devam Et') : __('Başlat'));
  const confirmText = isDurusDevami
    ? 'Duruş sonlandırılıp işleme devam edilecek.'
    : 'İşlem başlatılacak.';

  frm.add_custom_button(buttonText, () => {
    frappe.confirm(confirmText, () => {
      callIslemYap(frm, "Baslat", null, null, () => {
        if (!isDurusDevami) {
          frappe.msgprint({ title: __("İşlem Başarılı"), message: 'İşlem başlatıldı.', indicator: "green" });
        }
      });
    });
  }, __("İşlemler")).addClass('btn-success');
}

function addDurusButton(frm) {
  frm.add_custom_button(__('Duruş'), () => {
    frappe.prompt([
      { fieldtype: 'Link', label: __('Duruş Nedeni'), fieldname: 'durus_nedeni', reqd: 1,
        options: 'KTA Durus Sebebi',
        get_query: () => ({ filters: { is_system: 0 } })
      },
      { fieldtype: 'Small Text', label: __('Açıklama'), fieldname: 'aciklama' }
    ], (values) => {
      callIslemYap(frm, "Durus", values.durus_nedeni, values.aciklama, () => {
        frappe.msgprint({
          title: __("Duruş Kaydedildi"),
          message: __("Duruş başlatıldı: {0}", [values.durus_nedeni]),
          indicator: "orange"
        });
      });
    }, __('Duruş Bilgisi'), __('Duruş Başlat'));
  }, __("İşlemler")).addClass('btn-warning');
}

function addBitisButton(frm) {
  frm.add_custom_button(__('Bitir'), () => {
    frappe.confirm(__('İşlem bitirilecek. Devam etmek istediğinizden emin misiniz?'), () => {
      callIslemYap(frm, "Bitis", null, null, () => {
        frappe.msgprint({
          title: __("İşlem Tamamlandı"),
          message: __("İşlem başarıyla bitirildi."),
          indicator: "blue"
        });
      });
    });
  }, __("İşlemler")).addClass('btn-danger');
}

function callIslemYap(frm, islemTipi, durusNedeni, aciklama, successCallback) {
  frappe.call({
    method: 'erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.islem_yap',
    args: { docname: frm.doc.name, islem_tipi: islemTipi, durus_nedeni: durusNedeni, aciklama: aciklama },
    freeze: true,
    freeze_message: __('İşlem yapılıyor...'),
    callback: (r) => {
      if (r.message && r.message.status === 'success') {
        if (successCallback) successCallback();
        frm.reload_doc();
      }
    },
    error: () => {
      frappe.msgprint({ title: __("Hata"), message: __("İşlem sırasında bir hata oluştu."), indicator: "red" });
    }
  });
}

// ====== Makine Günlük Bakım Dialog ======
function showMaintenanceDialog(frm) {
  // First, fetch the instruction content
  frappe.call({
    method: 'frappe.client.get',
    args: {
      doctype: 'Bakim Talimati',
      name: 'PTR.BT.049'
    },
    callback: function(r) {
      if (!r.message) {
        frappe.msgprint(__('Bakım talimatı bulunamadı.'));
        return;
      }

      const instruction = r.message;
      let html = `
        <div style="padding: 20px; background-color: #f9f9f9; border-radius: 5px; max-height: 500px; overflow-y: auto;">
          <h3 style="color: #333; margin-top: 0;">${instruction.talimat_kodu} - ${instruction.talimat_adi}</h3>
      `;

      if (instruction.amac) {
        html += `<p><strong>AMAÇ:</strong> ${instruction.amac}</p>`;
      }

      if (instruction.kapsam) {
        html += `<p><strong>KAPSAM:</strong> ${instruction.kapsam}</p>`;
      }

      html += '<hr style="border: 0; border-top: 2px solid #ddd; margin: 15px 0;">';

      if (instruction.talimat_metni) {
        html += instruction.talimat_metni;
      }

      html += '</div>';

      // Create the dialog
      const dialog = new frappe.ui.Dialog({
        title: __('Günlük Bakım Onayı'),
        fields: [
          {
            fieldtype: 'Link',
            fieldname: 'makine',
            label: __('Makine No'),
            options: 'Asset',
            reqd: 1,
            description: __('Makine numarasını yazarak seçin (ör: M 1)')
          },
          {
            fieldtype: 'Section Break',
            label: __('Bakım Talimatı')
          },
          {
            fieldtype: 'HTML',
            fieldname: 'instruction_html',
            options: html
          },
          {
            fieldtype: 'Section Break',
            label: __('Onay')
          },
          {
            fieldtype: 'Check',
            fieldname: 'onay',
            label: __('Günlük bakımı talimata göre kontrol ettim ve sorun bulunmamıştır.'),
            reqd: 1
          },
          {
            fieldtype: 'Small Text',
            fieldname: 'notlar',
            label: __('Notlar (İsteğe Bağlı)')
          }
        ],
        primary_action_label: __('Onayla ve Kaydet'),
        primary_action: function(values) {
          if (!values.onay) {
            frappe.msgprint(__('Lütfen bakım kontrolünü onaylayın.'));
            return;
          }

          if (!values.makine) {
            frappe.msgprint(__('Lütfen makine seçin.'));
            return;
          }

          // Create the maintenance record
          frappe.call({
            method: 'frappe.client.insert',
            args: {
              doc: {
                doctype: 'Makine Gunluk Bakim Formu',
                calisma_karti_ref: frm.doc.name,
                operator: frm.doc.operator,
                makine: values.makine,
                tarih: frappe.datetime.get_today(),
                bakim_talimati: 'PTR.BT.049',
                notlar: values.notlar || '',
                onay: 1
              }
            },
            callback: function(r) {
              if (r.message) {
                // Submit the document
                frappe.call({
                  method: 'frappe.client.submit',
                  args: {
                    doc: r.message
                  },
                  callback: function(submit_r) {
                    dialog.hide();
                    frappe.msgprint({
                      title: __('Başarılı'),
                      message: __('Günlük bakım kaydı oluşturuldu ve onaylandı.'),
                      indicator: 'green'
                    });
                    frm.reload_doc();
                  }
                });
              }
            }
          });
        }
      });

      dialog.show();
      dialog.$wrapper.find('.modal-dialog').css("max-width", "800px");
    }
  });
}
