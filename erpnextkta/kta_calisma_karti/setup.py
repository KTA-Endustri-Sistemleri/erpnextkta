import frappe

def setup():
    setup_scrap_stock_entry_type()
    create_kta_roles()
    setup_permissions()

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
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 0, "delete": 0, "submit": 1, "cancel": 0, "amend": 0, "if_owner": 1},
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
