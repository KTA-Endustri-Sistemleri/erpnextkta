import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice as original_make_purchase_invoice

@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, *args, **kwargs):
    doc = original_make_purchase_invoice(source_name, target_doc, *args, **kwargs)
    
    # Custom Logic: Map irsaliye_tarihi to bill_date
    try:
        if isinstance(source_name, str): # Verify source_name is a string before fetching
             # Optimization: Avoid full get_doc if possible, but for custom field we might need it.
             # Or simpler via get_value
             irsaliye_tarihi = frappe.db.get_value("Purchase Receipt", source_name, "irsaliye_tarihi")
             
             if irsaliye_tarihi:
                 doc.bill_date = irsaliye_tarihi
                 
    except Exception as e:
        frappe.log_error(f"Error in custom make_purchase_invoice: {e}")

    return doc
