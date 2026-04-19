// Copyright (c) 2026, KTA and contributors
// For license information, please see license.txt

frappe.ui.form.on('KTA Krimp Book', {
    setup: function(frm) {
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'KTA Quality Settings',
                name: 'KTA Quality Settings'
            },
            callback: function(r) {
                let allowed_groups = [];
                if (r.message && r.message.gecerli_terminal_gruplari) {
                    allowed_groups = r.message.gecerli_terminal_gruplari.map(row => row.item_group);
                }
                
                // Eğer liste boşsa veya ayarlanmamışsa, default olarak istenen 150-Terminals kullanılsın.
                if (allowed_groups.length === 0) {
                    allowed_groups = ['150-Terminals'];
                }

                frm.set_query('kontak_no', function() {
                    return {
                        filters: {
                            'item_group': ['in', allowed_groups]
                        }
                    };
                });
            }
        });
    }
});
