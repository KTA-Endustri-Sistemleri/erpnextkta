import frappe
from frappe.utils import now_datetime

@frappe.whitelist()
def get_tamamlanan_kart_sayisi(filters=None):
    """Returns the total number of work cards with status 'Bitmiş' that were completed today."""
    
    # Simple count for 'Bitmiş' cards with bitis_saati on current date
    result = frappe.db.sql("""
        SELECT count(*) 
        FROM `tabCalisma Karti` 
        WHERE durum = 'Bitmiş' AND DATE(bitis_saati) = CURDATE()
    """)
    
    val = result[0][0] if result else 0
    
    return {
        "value": val,
        "fieldtype": "Int",
        "route_options": {
            "durum": "Bitmiş",
            "bitis_saati": ["between", [frappe.utils.today() + " 00:00:00", frappe.utils.today() + " 23:59:59"]]
        },
    }
