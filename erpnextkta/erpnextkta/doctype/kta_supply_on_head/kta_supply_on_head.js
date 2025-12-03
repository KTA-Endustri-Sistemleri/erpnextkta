frappe.ui.form.on('KTA Supply On Head', {
    compare_with_previous: function(frm) {
        frappe.confirm(
            'Önceki verilerle karşılaştırma yapılacak. Devam etmek istiyor musunuz?',
            function() {
                frappe.call({
                    method: 'erpnextkta.api.compare_supply_on_documents',
                    args: {
                        current_supply_on_name: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Karşılaştırma yapılıyor...'),
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __('Karşılaştırma Tamamlandı'),
                                message: __('Karşılaştırma başarıyla oluşturuldu.'),
                                indicator: 'green'
                            });
                            
                            // Comparison dokümanını aç
                            frappe.set_route('Form', 'KTA Supply On Comparison', r.message);
                        }
                    }
                });
            }
        );
    },
    
    sync_to_sales_orders: function(frm) {
        frappe.confirm(
            'Sales Order\'lar güncellenecek. Bu işlem geri alınamaz. Devam etmek istiyor musunuz?',
            function() {
                frappe.call({
                    method: 'erpnextkta.api.sync_sales_orders_from_supply_on',
                    args: {
                        supply_on_head_name: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Sales Order\'lar senkronize ediliyor...'),
                    callback: function(r) {
                        if (r.message) {
                            let msg = `
                                <b>Senkronizasyon Tamamlandı</b><br><br>
                                <table class="table table-bordered">
                                    <tr>
                                        <td>✅ Oluşturulan SO:</td>
                                        <td><b>${r.message.created}</b></td>
                                    </tr>
                                    <tr>
                                        <td>🔄 Güncellenen SO:</td>
                                        <td><b>${r.message.updated}</b></td>
                                    </tr>
                                    <tr>
                                        <td>❌ Kapatılan SO:</td>
                                        <td><b>${r.message.closed}</b></td>
                                    </tr>
                                    <tr>
                                        <td>⚠️ Hatalar:</td>
                                        <td><b>${r.message.errors}</b></td>
                                    </tr>
                                </table>
                            `;
                            
                            frappe.msgprint({
                                title: __('Senkronizasyon Sonucu'),
                                message: msg,
                                indicator: r.message.errors > 0 ? 'orange' : 'green'
                            });
                            
                            // Sync log'u aç
                            frappe.set_route('Form', 'KTA SO Sync Log', r.message.sync_log);
                        }
                    }
                });
            }
        );
    },
    
    refresh: function(frm) {
        // Last comparison ve sync log'a hızlı erişim
        if (frm.doc.last_comparison_date) {
            frm.add_custom_button(__('Son Karşılaştırma'), function() {
                frappe.db.get_value('KTA Supply On Comparison', 
                    {
                        'current_supply_on': frm.doc.name,
                        'comparison_date': frm.doc.last_comparison_date
                    },
                    'name',
                    function(r) {
                        if (r && r.name) {
                            frappe.set_route('Form', 'KTA Supply On Comparison', r.name);
                        }
                    }
                );
            }, __('Görüntüle'));
        }
        
        if (frm.doc.last_sync_log) {
            frm.add_custom_button(__('Son Sync Log'), function() {
                frappe.set_route('Form', 'KTA SO Sync Log', frm.doc.last_sync_log);
            }, __('Görüntüle'));
        }
    }
});