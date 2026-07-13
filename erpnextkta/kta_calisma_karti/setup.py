import frappe

def setup():
    setup_scrap_stock_entry_type()
    create_kta_roles()
    setup_permissions()
    cleanup_duplicate_custom_fields()
    setup_system_downtime_reasons()
    add_custom_fields()

def add_custom_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    
    # Bypass "Fieldtype cannot be changed from Link to Data" on test_site
    try:
        fields_to_check = ['custom_operasyon', 'custom_alt_operasyon', 'custom_alt_operasyon_kaydi']
        for f in fields_to_check:
            frappe.db.sql("DELETE FROM `tabCustom Field` WHERE fieldname = %s AND fieldtype = 'Link'", (f,))
        frappe.db.commit()
    except Exception:
        pass

    create_custom_fields(get_custom_fields())

def get_custom_fields():
    return {
        "Job Card Time Log": [
            {
                "fieldname": "custom_calisma_karti",
                "fieldtype": "Link",
                "options": "Calisma Karti",
                "label": "Çalışma Kartı",
                "insert_after": "operation",
                "no_copy": 1,
                "read_only": 1,
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_operasyon",
                "fieldtype": "Data",
                "label": "KTA Operasyon",
                "insert_after": "custom_calisma_karti",
                "no_copy": 1,
                "read_only": 1,
                "in_list_view": 0,
            },
            {
                "fieldname": "custom_alt_operasyon",
                "fieldtype": "Data",
                "label": "KTA Alt Operasyon",
                "insert_after": "custom_operasyon",
                "no_copy": 1,
                "read_only": 1,
                "in_list_view": 0,
            }
        ],
        "Quality Inspection": [
            {
                "fieldname": "custom_calisma_karti",
                "fieldtype": "Link",
                "options": "Calisma Karti",
                "label": "Çalışma Kartı",
                "insert_after": "reference_name",
                "description": "Bu kalite belgesini oluşturan spesifik çalışma kartı.",
                "read_only": 0,
                "unique": 0,
                "no_copy": 1
            },
            {
                "fieldname": "custom_alt_operasyon_kaydi",
                "fieldtype": "Data",
                "label": "Alt Operasyon Kaydı",
                "insert_after": "custom_calisma_karti",
                "description": "Modüler kalite sürecinde belgenin bağlandığı alt operasyon satırı."
            }
        ]
    }

def cleanup_duplicate_custom_fields():
    """Remove duplicate Custom Field records for fields already defined in custom DocTypes JSON."""
    import json
    import os

    # Read fieldnames from Calisma Karti JSON
    setup_dir = os.path.dirname(__file__)
    json_path = os.path.join(setup_dir, "doctype", "calisma_karti", "calisma_karti.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            json_fields = [field.get("fieldname") for field in meta.get("fields", []) if field.get("fieldname")]
        
        # Delete custom fields from DB that overlap with JSON fields
        for fieldname in json_fields:
            if frappe.db.exists("Custom Field", {"dt": "Calisma Karti", "fieldname": fieldname}):
                frappe.db.delete("Custom Field", {"dt": "Calisma Karti", "fieldname": fieldname})
        frappe.db.commit()


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
    roles = [
        'KTA Çalışma Kartı Kullanıcısı', 
        'KTA Çalışma Kartı Yöneticisi',
        'KTA Kalite Kullanıcısı',
        'KTA Kalite Yöneticisi'
    ]
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
    roles = ['KTA Çalışma Kartı Kullanıcısı', 'KTA Çalışma Kartı Yöneticisi', 'KTA Kalite Kullanıcısı']
    
    # Accurate transcription from the provided image
    permissions_data = [
        # Calisma Karti
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 1, "cancel": 0, "amend": 0, "permlevel": 0},
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "permlevel": 3},
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "permlevel": 0},
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "permlevel": 3},
        {"parent": "Calisma Karti", "role": "Manufacturing User", "read": 1, "write": 1, "create": 1, "submit": 1, "permlevel": 0},
        {"parent": "Calisma Karti", "role": "Manufacturing User", "read": 1, "write": 1, "permlevel": 3},
        {"parent": "Calisma Karti", "role": "Manufacturing Manager", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "permlevel": 0},
        {"parent": "Calisma Karti", "role": "Manufacturing Manager", "read": 1, "write": 1, "permlevel": 3},
        {"parent": "Calisma Karti", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "permlevel": 0},
        {"parent": "Calisma Karti", "role": "System Manager", "read": 1, "write": 1, "permlevel": 3},
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "permlevel": 2},
        {"parent": "Calisma Karti", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "permlevel": 2},
        {"parent": "Calisma Karti", "role": "Manufacturing User", "read": 1, "write": 1, "permlevel": 2},
        {"parent": "Calisma Karti", "role": "Manufacturing Manager", "read": 1, "write": 1, "permlevel": 2},
        {"parent": "Calisma Karti", "role": "System Manager", "read": 1, "write": 1, "permlevel": 2},
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
        {"parent": "KTA Calisma Karti Alt Operasyonlari", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
        # Operasyonlar
        {"parent": "KTA Calisma Karti Operasyonlari", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "KTA Calisma Karti Operasyonlari", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "KTA Calisma Karti Operasyonlari", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1},
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
        # UOM
        {"parent": "UOM", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "UOM", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        # KTA Calisma Karti Settings
        {"parent": "KTA Calisma Karti Settings", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "KTA Calisma Karti Settings", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0},
        {"parent": "KTA Calisma Karti Settings", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 0, "cancel": 0, "amend": 0},
        # Child Tables - Ölçüm ve Kayıt Tabloları
        {"parent": "Calisma Karti Krimp Olcumleri", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Krimp Olcumleri", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "Calisma Karti IDC Olcumleri", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti IDC Olcumleri", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "Calisma Karti Enjeksiyon Olcumleri", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Enjeksiyon Olcumleri", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "Calisma Karti Barkod Kayitlari", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Barkod Kayitlari", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "Calisma Karti Hurda", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Hurda", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "Operasyon Duruslari", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Operasyon Duruslari", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "Calisma Karti Alt Operasyon Kayitlari", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Alt Operasyon Kayitlari", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        # Test Masası Doğrulama Kaydı (linked form - Kalite sekmesi)
        {"parent": "Test Masasi Dogrulama Kaydi", "role": "KTA Çalışma Kartı Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Test Masasi Dogrulama Kaydi", "role": "KTA Çalışma Kartı Yöneticisi", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "Test Masasi Dogrulama Kaydi", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        # KTA Kalite Kullanıcısı - Child Table erişimleri
        {"parent": "Calisma Karti Krimp Olcumleri", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti IDC Olcumleri", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Enjeksiyon Olcumleri", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Barkod Kayitlari", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 1, "create": 1, "delete": 0},
        {"parent": "Calisma Karti Hurda", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0},
        {"parent": "Operasyon Duruslari", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0},
        {"parent": "Calisma Karti Alt Operasyon Kayitlari", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 0, "create": 0, "delete": 0},
        {"parent": "Calisma Karti Alt Operasyon Kayitlari", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 1, "permlevel": 1},
        {"parent": "Calisma Karti Alt Operasyon Kayitlari", "role": "KTA Kalite Yöneticisi", "read": 1, "write": 1, "permlevel": 1},
        {"parent": "Calisma Karti Alt Operasyon Kayitlari", "role": "System Manager", "read": 1, "write": 1, "permlevel": 1},
        {"parent": "Calisma Karti", "role": "KTA Kalite Kullanıcısı", "read": 1, "write": 1, "permlevel": 1},
        {"parent": "Calisma Karti", "role": "KTA Kalite Yöneticisi", "read": 1, "write": 1, "permlevel": 1},
        {"parent": "Calisma Karti", "role": "System Manager", "read": 1, "write": 1, "permlevel": 1},
        # KTA Sanal Yarimamul
        {"parent": "KTA Sanal Yarimamul", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "KTA Sanal Yarimamul", "role": "Manufacturing User", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "KTA Sanal Yarimamul", "role": "Manufacturing Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "KTA Sanal Yarimamul", "role": "All", "read": 1, "write": 1, "create": 1, "delete": 1},
        {"parent": "KTA Sanal Yarimamul", "role": "Employee", "read": 1, "write": 1, "create": 1, "delete": 1},
    ]

    # KTA'ya özel olan ve tüm rollerini yönetmek istediğimiz DocType'lar
    kta_parents = ["Calisma Karti", "KTA Calisma Karti Operasyonlari", "KTA Calisma Karti Alt Operasyonlari", "KTA Calisma Karti Settings", "KTA Sanal Yarimamul"]

    cleared_pairs = set()

    for p in permissions_data:
        # Sadece şu durumlarda izinleri yönetiyoruz:
        # 1. Rol bizim özel KTA rolümüz ise (Her DocType'da yönetebiliriz)
        # 2. DocType bizim KTA DocType'ımız ise (Her rolü yönetebiliriz, örn: System Manager)
        if p["role"] in roles or p["parent"] in kta_parents:
            pair_key = (p["role"], p["parent"])

            # Önce temizle (duplicate oluşmaması için) ama her role/parent ikilisi için SADECE BİR KERE!
            # Aksi halde permlevel 3 eklenirken, az önce eklenen permlevel 0 silinir!
            if pair_key not in cleared_pairs:
                frappe.db.delete("Custom DocPerm", {"role": p["role"], "parent": p["parent"]})
                cleared_pairs.add(pair_key)
            
            # Yeni izni ekle
            p_copy = p.copy()
            if "permlevel" not in p_copy:
                p_copy["permlevel"] = 0
                
            p_copy.update({
                "doctype": "Custom DocPerm"
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
            "reason": "Makine Hazırlık / Ayar",
            "durus_tipi": "Ürün Geçişi / Hazırlık",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "İş değişimi sırasında kalıp bağlama ve makine ayarları için yapılan duruş."
        },
        {
            "reason": "Test Board Değişimi",
            "durus_tipi": "Ürün Geçişi / Hazırlık",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Üretime başlamadan önceki board kurma ve hazırlık süreci."
        },
        {
            "reason": "İlk Ürün / Numune Onayı",
            "durus_tipi": "Ürün Geçişi / Hazırlık",
            "is_system": 0,
            "exclude_from_charts": 0,
            "description": "Seri üretime geçmeden önceki ilk ürün veya numune onay süreci."
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
            "durus_tipi": "Sistem",
            "is_system": 1,
            "exclude_from_charts": 0,
            "description": "Makine veya ekipman kaynaklı teknik arızalar."
        },
        {
            "reason": "Arıza Sonrası Bekleme",
            "durus_tipi": "Sistem",
            "is_system": 1,
            "exclude_from_charts": 0,
            "description": "Arıza giderildikten sonra operatörün makine başına geçip üretime başlamasının beklendiği süre."
        },
        {
            "reason": "Planlı Bakım / Kalibrasyon",
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
            "description": "Üretim esnasında çıkan bir hata nedeniyle durma."
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
            # Update existing system records to ensure correct flags
            frappe.db.set_value("KTA Durus Sebebi", data["reason"], {
                "is_system": data.get("is_system", 0),
                "durus_tipi": data["durus_tipi"],
                "exclude_from_charts": data["exclude_from_charts"],
                "description": data.get("description", "")
            }, update_modified=False)

    # Link these reasons to KTA Calisma Karti Settings automatically
    settings = frappe.get_doc("KTA Calisma Karti Settings")
    settings.auto_pause_durus_nedeni = "Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı."
    settings.timeout_durus_nedeni = "Zaman Aşımı"
    settings.save(ignore_permissions=True)

    frappe.db.commit()