frappe.ui.form.on('KTA Sales Order Update', {
    refresh(frm) {
        if (frm.is_new()) return;

        const referenceName = frm.doc.name;

        frm.add_custom_button(__('Önceki Verilerle Karşılaştır'), () => {
            frappe.call({
                method: 'erpnextkta.api.compare_sales_order_update_documents',
                args: { current_sales_order_update_name: referenceName },
                freeze: true,
                freeze_message: __('Karşılaştırma yapılıyor...'),
                callback: (r) => {
                    if (r.message) {
                        frappe.msgprint(__('Karşılaştırma tamamlandı.'));
                        frappe.set_route('Form', 'KTA Sales Order Update Comparison', r.message);
                    }
                },
            });
        }, __('Sales Order Update İşlemleri'));

        frm.add_custom_button(__('Sales Order\'ları Senkronize Et'), () => {
            frappe.call({
                method: 'erpnextkta.api.sync_sales_orders_from_sales_order_update',
                args: { sales_order_update_reference: referenceName },
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
        }, __('Sales Order Update İşlemleri'));

        frm.add_custom_button(__('Sales Order Update Listesi'), () => {
            frappe.set_route('List', 'KTA Sales Order Update');
        }, __('Kısayollar'));

        frm.add_custom_button(__('Dosyadan Yükle (Data Import)'), () => {
            frappe.new_doc('Data Import', {
                reference_doctype: 'KTA Sales Order Update Entry',
                import_type: 'Insert New Records',
            });
        }, __('Kısayollar'));
    },
});
