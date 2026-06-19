import frappe

def execute():
    # Remove custom fields
    custom_fields = frappe.get_all("Custom Field", filters={"dt": "Calisma Karti"})
    for cf in custom_fields:
        frappe.delete_doc("Custom Field", cf.name, force=True)

    # Remove property setters
    property_setters = frappe.get_all("Property Setter", filters={"doc_type": "Calisma Karti"})
    for ps in property_setters:
        frappe.delete_doc("Property Setter", ps.name, force=True)
