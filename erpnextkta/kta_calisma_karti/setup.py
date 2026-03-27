import frappe

def setup_scrap_stock_entry_type():
    """Create 'Scrap for Manufacturing' Stock Entry Type if it doesn't exist."""
    if not frappe.db.exists("Stock Entry Type", "Scrap for Manufacturing"):
        doc = frappe.get_doc({
            "doctype": "Stock Entry Type",
            "name": "Scrap for Manufacturing",
            "stock_entry_type": "Scrap for Manufacturing",
            "purpose": "Material Issue"
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
