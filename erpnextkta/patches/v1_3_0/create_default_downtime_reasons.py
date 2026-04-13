# Copyright (c) 2026, KTA and contributors
# For license information, please see license.txt

"""
Patch: Varsayılan duruş sebeplerini KTA Durus Sebebi DocType'ına aktarır.

Mevcut Operasyon Duruslari tablosundaki tüm benzersiz durus_nedeni değerlerini
yeni DocType'a taşır ve Planlı/Plansız kategorizasyonu uygular.
"""

import frappe


# Varsayılan duruş sebepleri ve özellikleri
DEFAULT_REASONS = [
    {
        "reason": "Ariza",
        "durus_tipi": "Plansız",
        "is_system": 0,
        "exclude_from_charts": 0,
        "description": "Makine arızası kaynaklı duruş.",
    },
    {
        "reason": "Malzeme Bekleme",
        "durus_tipi": "Plansız",
        "is_system": 0,
        "exclude_from_charts": 0,
        "description": "Hammadde veya yarı mamul tedarik bekleme süresi.",
    },
    {
        "reason": "Kalite Kontrol",
        "durus_tipi": "Plansız",
        "is_system": 0,
        "exclude_from_charts": 0,
        "description": "Kalite kontrol işlemi için bekleme süresi.",
    },
    {
        "reason": "Mola",
        "durus_tipi": "Planlı",
        "is_system": 0,
        "exclude_from_charts": 0,
        "description": "Operatör mola süresi.",
    },
    {
        "reason": "Bakim",
        "durus_tipi": "Planlı",
        "is_system": 0,
        "exclude_from_charts": 0,
        "description": "Planlı bakım süresi.",
    },
    {
        "reason": "Diger",
        "durus_tipi": "Plansız",
        "is_system": 0,
        "exclude_from_charts": 0,
        "description": "Diğer nedenlerle oluşan duruş.",
    },
    {
        "reason": "Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı.",
        "durus_tipi": "Plansız",
        "is_system": 1,
        "exclude_from_charts": 1,
        "description": "Operatör farklı bir çalışma kartı başlattığında sistem tarafından otomatik oluşturulur.",
    },
    {
        "reason": "Zaman Aşımı",
        "durus_tipi": "Plansız",
        "is_system": 1,
        "exclude_from_charts": 1,
        "description": "Maksimum çalışma süresi aşıldığında sistem tarafından otomatik oluşturulur.",
    },
]


def execute():
    """Varsayılan duruş sebeplerini oluştur ve mevcut veritabanı değerlerini de ekle."""

    # 1. Varsayılan sebepleri oluştur
    for reason_data in DEFAULT_REASONS:
        if not frappe.db.exists("KTA Durus Sebebi", reason_data["reason"]):
            doc = frappe.new_doc("KTA Durus Sebebi")
            doc.update(reason_data)
            doc.insert(ignore_permissions=True)
            frappe.logger().info(f"[kta] KTA Durus Sebebi oluşturuldu: {reason_data['reason']}")

    # 2. Veritabanındaki mevcut benzersiz durus_nedeni değerlerini kontrol et
    #    (Kullanıcılar Select alanına manuel değer girmiş olabilir)
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
            frappe.logger().info(f"[kta] Mevcut veriden KTA Durus Sebebi oluşturuldu: {reason_name}")

    frappe.db.commit()
