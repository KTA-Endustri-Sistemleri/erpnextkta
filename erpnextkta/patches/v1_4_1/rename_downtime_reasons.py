import frappe

def execute():
    # Mapping of old name -> dict with new_name and durus_tipi
    renames = {
        "Kalıp Bağlama / Makine Ayarı": {
            "new_name": "Makine Hazırlık / Ayar",
            "durus_tipi": "Ürün Geçişi / Hazırlık"
        },
        "Board Kurma Hazırlık": {
            "new_name": "Test Board Değişimi",
            "durus_tipi": "Ürün Geçişi / Hazırlık"
        },
        "Bakım": {
            "new_name": "Planlı Bakım / Kalibrasyon",
            "durus_tipi": "Planlı",
            "is_system": 0
        },
        "Arıza": {
            "new_name": "Arıza",
            "durus_tipi": "Sistem",
            "is_system": 1
        }
    }

    for old_name, config in renames.items():
        new_name = config["new_name"]
        durus_tipi = config["durus_tipi"]
        is_system = config.get("is_system", 0)
        
        if frappe.db.exists("KTA Durus Sebebi", old_name):
            if old_name != new_name:
                # If the new name somehow already exists, merge it
                if frappe.db.exists("KTA Durus Sebebi", new_name):
                    frappe.rename_doc("KTA Durus Sebebi", old_name, new_name, force=True, merge=True)
                else:
                    frappe.rename_doc("KTA Durus Sebebi", old_name, new_name, force=True)
            
            # Update the downtime type and system flag to the new ones
            frappe.db.set_value("KTA Durus Sebebi", new_name, {
                "durus_tipi": durus_tipi,
                "is_system": is_system
            }, update_modified=False)

    frappe.db.commit()
