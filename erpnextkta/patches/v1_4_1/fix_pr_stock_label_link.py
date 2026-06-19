import frappe

def execute():
    # Fix existing DocType Link to prevent DuplicateEntryError during sync_customizations
    if frappe.db.exists("DocType Link", "kta_pr_stock_label"):
        frappe.db.sql("""
            UPDATE `tabDocType Link`
            SET link_fieldname = 'reference_name'
            WHERE name = 'kta_pr_stock_label' AND link_fieldname = 'gr_number'
        """)
