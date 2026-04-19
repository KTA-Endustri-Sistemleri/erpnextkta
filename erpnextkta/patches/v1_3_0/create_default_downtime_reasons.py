# Copyright (c) 2026, KTA and contributors
# For license information, please see license.txt

"""
Patch: Varsayılan duruş sebeplerini KTA Durus Sebebi DocType'ına aktarır.
Artık Türkçe karakterli ve sistem bayrakları (is_system vb.) doğru set edilmiş durumdadır.
"""

import frappe

# Varsayılan duruş sebepleri ve özellikleri
DEFAULT_REASONS = [
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

def execute():
    """Varsayılan duruş sebeplerini oluştur ve mevcut veritabanı değerlerini aktar."""

    # 1. Varsayılan sebepleri oluştur veya güncelle
    for data in DEFAULT_REASONS:
        if not frappe.db.exists("KTA Durus Sebebi", data["reason"]):
            doc = frappe.get_doc({
                "doctype": "KTA Durus Sebebi",
                **data
            })
            doc.insert(ignore_permissions=True)
            frappe.logger().info(f"[kta] KTA Durus Sebebi oluşturuldu: {data['reason']}")
        else:
            # Mevcut kayıtları yeni bayraklarla güncelle (idempotent)
            frappe.db.set_value("KTA Durus Sebebi", data["reason"], {
                "is_system": data["is_system"],
                "durus_tipi": data["durus_tipi"],
                "exclude_from_charts": data["exclude_from_charts"],
                "description": data["description"]
            }, update_modified=False)

    # 2. Ayarları otomatik bağla
    settings = frappe.get_doc("KTA Calisma Karti Settings")
    settings.auto_pause_durus_nedeni = "Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı."
    settings.timeout_durus_nedeni = "Zaman Aşımı"
    settings.save(ignore_permissions=True)

    # 3. Eski veriden aktarım (Opsiyonel/Ekstra güvenlik)
    existing_values = frappe.db.sql("""
        SELECT DISTINCT durus_nedeni
        FROM `tabOperasyon Duruslari`
        WHERE durus_nedeni IS NOT NULL AND durus_nedeni != ''
    """, as_dict=True)

    for row in existing_values:
        reason_name = row.get("durus_nedeni", "").strip()
        if reason_name and not frappe.db.exists("KTA Durus Sebebi", reason_name):
            doc = frappe.new_doc("KTA Durus Sebebi")
            doc.reason = reason_name
            doc.durus_tipi = "Plansız"
            doc.is_system = 0
            doc.exclude_from_charts = 0
            doc.description = "Mevcut veriden otomatik aktarıldı."
            doc.insert(ignore_permissions=True)

    frappe.db.commit()
