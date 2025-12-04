frappe.ui.form.on('KTA Supply On', {
    refresh(frm) {
        if (frm.is_new()) return;

        if (!frm.doc.supply_on_head) {
            frm.dashboard.set_headline(__('Bu satır herhangi bir Supply On Head kayıtıyla ilişkilendirilmemiştir.'));
        }

        const referenceName = frm.doc.name;

        frm.add_custom_button(__('Veriyi İşle'), () => {
            frappe.call({
                method: 'erpnextkta.api.process_supply_on',
                args: { supply_on_reference: referenceName },
                freeze: true,
                freeze_message: __('Supply On verisi işleniyor...'),
                callback: () => {
                    frappe.show_alert({
                        message: __('Supply On verisi işlendi.'),
                        indicator: 'green',
                    });
                    frm.reload_doc();
                },
            });
        }, __('Supply On İşlemleri'));

        frm.add_custom_button(__('Önceki Verilerle Karşılaştır'), () => {
            frappe.call({
                method: 'erpnextkta.api.compare_supply_on_documents',
                args: { current_supply_on_name: referenceName },
                freeze: true,
                freeze_message: __('Karşılaştırma yapılıyor...'),
                callback: (r) => {
                    if (r.message) {
                        frappe.msgprint(__('Karşılaştırma tamamlandı.'));
                        frappe.set_route('Form', 'KTA Supply On Comparison', r.message);
                    }
                },
            });
        }, __('Supply On İşlemleri'));

        frm.add_custom_button(__('Sales Order\'ları Senkronize Et'), () => {
            frappe.call({
                method: 'erpnextkta.api.sync_sales_orders_from_supply_on',
                args: { supply_on_reference: referenceName },
                freeze: true,
                freeze_message: __('Sales Order\'lar güncelleniyor...'),
                callback: (r) => {
                    if (r.message) {
                        const result = r.message;
                        const msg = `
                            <b>${__('Senkronizasyon Tamamlandı')}</b><br><br>
                            <table class="table table-bordered">
                                <tr><td>${__('Oluşturulan SO')}</td><td><b>${result.created}</b></td></tr>
                                <tr><td>${__('Güncellenen SO')}</td><td><b>${result.updated}</b></td></tr>
                                <tr><td>${__('Kapatılan SO')}</td><td><b>${result.closed}</b></td></tr>
                                <tr><td>${__('Hatalar')}</td><td><b>${result.errors}</b></td></tr>
                            </table>
                        `;

                        frappe.msgprint({
                            title: __('Senkronizasyon Sonucu'),
                            message: msg,
                            indicator: result.errors > 0 ? 'orange' : 'green',
                        });

                        if (result.sync_log) {
                            frappe.set_route('Form', 'KTA SO Sync Log', result.sync_log);
                        }
                    }
                },
            });
        }, __('Supply On İşlemleri'));

        frm.add_custom_button(__('Supply On Listesi'), () => {
            frappe.set_route('List', 'KTA Supply On');
        }, __('Kısayollar'));

        frm.add_custom_button(__('Dosyadan Yükle (Data Import)'), () => {
            frappe.new_doc('Data Import', {
                reference_doctype: 'KTA Supply On',
                import_type: 'Insert New Records',
            });
        }, __('Kısayollar'));
    },
});
