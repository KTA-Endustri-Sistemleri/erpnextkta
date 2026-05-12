import frappe

def execute():
    doc = frappe.get_doc("Client Script", "KTA Hareketten Ürün Tanıtım Etiketi Bas")
    doc.script = """frappe.ui.form.on('Stock Entry', {
custom_etiket_bas: function(frm){
        frappe.call({
            method: "erpnextkta.api_resplit.check_packaging_quantity_mismatch",
            args: { stock_entry: frm.doc.name },
            callback: function(r) {
                if (r.message && r.message.mismatch) {
                    frappe.confirm(
                        __('Müşteri paketleme miktarı değişmiş. Mevcut paketler silinip güncel miktara göre yeniden paketleme yapılsın mı?'),
                        () => {
                            frappe.call({
                                method: "erpnextkta.api_resplit.resplit_and_print_kta_wo_labels",
                                args: { stock_entry: frm.doc.name },
                                freeze: true,
                                freeze_message: __('Yeniden paketleniyor ve etiketler basılıyor...')
                            });
                        },
                        () => {
                            frappe.call({
                                method: "erpnextkta.api.print_kta_wo_labels_of_stock_entry",
                                args: { stock_entry: frm.doc.name }
                            });
                        }
                    );
                } else {
                    frappe.call({
                        method: "erpnextkta.api.print_kta_wo_labels_of_stock_entry",
                        args: { stock_entry: frm.doc.name }
                    });
                }
            }
        });
    }
});"""
    doc.save()
    frappe.db.commit()

