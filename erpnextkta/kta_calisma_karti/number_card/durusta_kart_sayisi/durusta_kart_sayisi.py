import frappe

@frappe.whitelist()
def get_durusta_kart_sayisi(filters=None):
    count = frappe.db.count("Calisma Karti", {
        "docstatus": 1,
        "durum": "Duruşta"
    })

    return {
        "value": count or 0,
        "fieldtype": "Int",
        "route_options": {
            "durum": "Duruşta",
            "docstatus": 1
        },
        "route": ["List", "Calisma Karti"]
    }
