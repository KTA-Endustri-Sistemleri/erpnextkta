// Stock Entry – Get Items From → Çalışma Kartı (özel diyalog + direkt frappe.call)
frappe.ui.form.on('Stock Entry', {
  refresh(frm) {
    if (frm.doc.docstatus !== 0) return;                 // sadece taslakta

    frm.add_custom_button(__('Çalışma Kartı'), () => {
      open_calisma_karti_dialog(frm);
    }, __('Get Items From'));
  }
});

function open_calisma_karti_dialog(frm) {
  const d = new frappe.ui.Dialog({
    title: __('Çalışma Kartından Getir (Hurda)'),
    fields: [
      {
        fieldtype: 'Link',
        fieldname: 'calisma_karti',
        label: __('Çalışma Kartı'),
        options: 'Calisma Karti',
        reqd: 1
      },
      {
        fieldtype: 'Check',
        fieldname: 'clear',
        label: __('Mevcut kalemleri temizle')
      }
    ],
    primary_action_label: __('Getir'),
    primary_action(values) {
      if (!values.calisma_karti) return;

      frappe.call({
        method: 'erpnextkta.api.get_items_from_calisma_karti',
        args: { source_name: values.calisma_karti },
        freeze: true,
        freeze_message: __('Hurda kalemler getiriliyor...'),
        callback: (r) => {
          const rows = r.message || [];
          if (!Array.isArray(rows) || rows.length === 0) {
            frappe.msgprint(__('Aktarılacak kalem bulunamadı.'));
            return;
          }
          if (values.clear) {
            frm.clear_table('items');
          }
          rows.forEach(it => {
            let child = frm.add_child('items');
            Object.assign(child, it);
          });
          frm.refresh_field('items');
          d.hide();

          // s_warehouse kontrolü
          const missing = (frm.doc.items || []).some(i => !i.s_warehouse);
          if (missing) {
            frappe.msgprint(__('Bazı satırlarda Kaynak Depo (s_warehouse) boş. Lütfen doldurun.'));
          }
        },
        error: (err) => {
          console.error(err);
          frappe.msgprint(__('Hurda kalemleri çekerken bir hata oluştu. Konsolu kontrol edin.'));
        }
      });
    }
  });

  d.show();
}
