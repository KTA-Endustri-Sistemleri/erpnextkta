import frappe

def setup():
    setup_scrap_stock_entry_type()
    create_kta_roles()
    setup_permissions()
    setup_system_downtime_reasons()

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

def create_kta_roles():
    """Create 'KTA Çalışma Kartı Kullanıcısı' and 'KTA Çalışma Kartı Yöneticisi' roles if they don't exist."""
    roles = ['KTA Çalışma Kartı Kullanıcısı', 'KTA Çalışma Kartı Yöneticisi']
    for role_name in roles:
        if not frappe.db.exists("Role", role_name):
            doc = frappe.get_doc({
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1
            })
            doc.insert(ignore_permissions=True)
    frappe.db.commit()

def setup_permissions():
    """Reset permissions to the exact state provided by the user in the image."""
    roles = ['KTA Çalışma Kartı Kullanıcısı', 'KTA Çalışma Kartı Yöneticisi']
    
    # Accurate transcription from the provided image
    permissions_data = [
        # Calisma Karti
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 0, "delete": 0, "submit": 1, "cancel": 0, "amend": 0},
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
        # Stock Entry
        {"parent": "Stock Entry", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 0, "cancel": 0, "amend": 0, "if_owner": 1},
        {"parent": "Stock Entry", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Asset
        {"parent": "Asset", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Asset", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Asset Maintenance
        {"parent": "Asset Maintenance", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Asset Maintenance", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Asset Maintenance Log
        {"parent": "Asset Maintenance Log", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Asset Maintenance Log", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Alt Operasyonlar
        {"parent": "KTA Calisma Karti Alt Operasyonlari", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "KTA Calisma Karti Alt Operasyonlari", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Operasyonlar
        {"parent": "KTA Calisma Karti Operasyonlari", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "KTA Calisma Karti Operasyonlari", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Stock Entry Type
        {"parent": "Stock Entry Type", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Stock Entry Type", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Stock Settings
        {"parent": "Stock Settings", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Stock Settings", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Warehouse
        {"parent": "Warehouse", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Warehouse", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Page
        {"parent": "Page", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Page", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Work Order
        {"parent": "Work Order", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Work Order", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Job Card
        {"parent": "Job Card", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Job Card", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Quality Inspection
        {"parent": "Quality Inspection", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "Quality Inspection", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # Quality Inspection
        {"parent": "UOM", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "UOM", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # KTA Calisma Karti Settings
        {"parent": "KTA Calisma Karti Settings", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "KTA Calisma Karti Settings", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0}
    ]

    for role in roles:
        # Clear existing to ensure clean state
        frappe.db.delete("Custom DocPerm", {"role": role})
        
    for p in permissions_data:
        p_copy = p.copy()
        p_copy.update({
            "doctype": "Custom DocPerm",
            "permlevel": 0
        })
        frappe.get_doc(p_copy).insert(ignore_permissions=True)
    
    frappe.db.commit()


def setup_system_downtime_reasons():
    """Create system downtime reasons in 'KTA Durus Sebebi' if they don't exist."""
    reasons = [
        {
            "reason": "Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı.",
            "durus_tipi": "Sistem",
            "is_system": 1,
            "exclude_from_charts": 1,
            "description": "Aynı operatör başka bir çalışma kartını başlattığında sistem tarafından otomatik olarak eklenen duruş."
        },
        {
            "reason": "Zaman Aşımı",
            "durus_tipi": "Sistem",
            "is_system": 1,
            "exclude_from_charts": 1,
            "description": "Vardiya sonunda veya uzun süre işlem yapılmadığında sistem tarafından otomatik kapatılan kartlar için kullanılır."
        },
        {
            "reason": "Kalıp Bağlama / Makine Ayarı",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "İş değişimi sırasında kalıp bağlama ve makine ayarları için yapılan duruş."
        },
        {
            "reason": "Board Kurma Hazırlık",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Üretime başlamadan önceki board kurma ve hazırlık süreci."
        },
        {
            "reason": "Malzeme Taşıma",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Ürün, Yarımamul vb. malzemelerin taşınması süreci."
        },
        {
            "reason": "Depo / Hammadde Yerleştirme",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Depodan gelen hammaddelerin operatör tarafından yerleştirilmesi ve düzenlenmesi süreci."
        },
        {
            "reason": "Arıza",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Makine veya ekipman kaynaklı teknik arızalar."
        },
        {
            "reason": "Bakım",
            "durus_tipi": "Planlı",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Planlı makine bakımları."
        },
        {
            "reason": "Mola",
            "durus_tipi": "Planlı",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Standart personel molaları."
        },
        {
            "reason": "Kalite Kontrol",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Kalite kontrol onayı beklerken geçen süre."
        },
        {
            "reason": "Malzeme Bekleme",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Hammadde veya yarı mamul eksikliği nedeniyle bekleme."
        },
        {
            "reason": "Diğer",
            "durus_tipi": "Plansız",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Tanımlananlar dışındaki genel nedenler."
        }
    ]

    for data in reasons:
        if not frappe.db.exists("KTA Durus Sebebi", data["reason"]):
            doc = frappe.get_doc({
                "doctype": "KTA Durus Sebebi",
                **data
            })
            doc.insert(ignore_permissions=True)
        else:
            # Update existing system records to ensure is_system=1
            frappe.db.set_value("KTA Durus Sebebi", data["reason"], {
                "is_system": 1,
                "durus_tipi": data["durus_tipi"],
                "exclude_from_charts": data["exclude_from_charts"]
            }, update_modified=False)

    # Link these reasons to KTA Calisma Karti Settings automatically
    settings = frappe.get_doc("KTA Calisma Karti Settings")
    settings.auto_pause_durus_nedeni = "Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı."
    settings.timeout_durus_nedeni = "Zaman Aşımı"
    settings.save(ignore_permissions=True)

    frappe.db.commit()
