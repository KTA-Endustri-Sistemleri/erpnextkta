import frappe

def execute():
    frappe.delete_doc('Custom Field', 'Stock Entry-custom_kta', ignore_missing=True)
    frappe.delete_doc('Custom Field', 'Stock Entry-custom_etiket_bas', ignore_missing=True)
    frappe.db.commit()
