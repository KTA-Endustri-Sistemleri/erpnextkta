import frappe

@frappe.whitelist()
def get_calisan_kart_sayisi(filters=None):
    count = frappe.db.count("Calisma Karti", {
        "docstatus": 1,
        "durum": "Çalışıyor"
    })

    return {
        "value": count or 0,
        "fieldtype": "Int",
        "route_options": {
            "durum": "Çalışıyor",
            "docstatus": 1
        },
        "route": ["List", "Calisma Karti"]
    }
