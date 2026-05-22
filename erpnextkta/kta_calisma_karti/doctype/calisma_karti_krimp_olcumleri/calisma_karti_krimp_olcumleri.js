frappe.ui.form.on('Calisma Karti Krimp Olcumleri', {
	krimp_olcumleri_add: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (frm.doc.operator) {
			frappe.model.set_value(cdt, cdn, 'operator', frm.doc.operator);
		}
		frappe.model.set_value(cdt, cdn, 'olcum_tarihi', frappe.datetime.now_datetime());
	}
});
