import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """Add custom_calisma_karti field to Quality Inspection to ensure unambiguous linkage."""
    custom_fields = {
        "Quality Inspection": [
            {
                "fieldname": "custom_calisma_karti",
                "label": "Çalışma Kartı",
                "fieldtype": "Link",
                "options": "Calisma Karti",
                "insert_after": "reference_name",
                "read_only": 1,
                "description": "Bu kalite belgesini oluşturan spesifik çalışma kartı."
            }
        ]
    }
    create_custom_fields(custom_fields, ignore_validate=True)
