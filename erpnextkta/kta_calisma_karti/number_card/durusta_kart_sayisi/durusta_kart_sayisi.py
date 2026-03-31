import json
import frappe

@frappe.whitelist()
def get_durusta_kart_sayisi(filters=None):
    """Returns the total number of work cards with status 'Duruşta'."""
    
    # Simple count without workstation filters as per user request
    result = frappe.db.sql("""
        SELECT count(*) 
        FROM `tabCalisma Karti` 
        WHERE durum = 'Duruşta'
    """)
    
    val = result[0][0] if result else 0
    
    return {
        "value": val,
        "fieldtype": "Int",
        "route_options": {"durum": "Duruşta"},
        "route": ["List", "Calisma Karti"]
    }
