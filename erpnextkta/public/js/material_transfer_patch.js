frappe.ui.form.on('Stock Entry Detail', {
    item_code(frm, cdt, cdn) {
        frappe.flags.hide_serial_batch_dialog = true;
        frappe.flags.dialog_set = true;
    }
});
