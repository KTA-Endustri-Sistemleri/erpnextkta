"""
KTA Çalışma Kartı — Veri Temizleme Scripti
==========================================

⚠️  DİKKAT: Bu script tüm "Calisma Karti" belgelerini ve bağlı
    alt tablo kayıtlarını kalıcı olarak siler. GERI ALINAMAZ.

Kullanım (bench console):
    %run /opt/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_calisma_karti/scripts/clear_test_data.py

Veya bench execute ile:
    bench --site <site-adi> execute erpnextkta.kta_calisma_karti.scripts.clear_test_data.run

Ne siler:
    - Calisma Karti (ana doküman)
    - Operasyon Duruslari          (child table)
    - Calisma Karti Hurda          (child table)
    - Calisma Karti IDC Olcumleri  (child table)
    - Calisma Karti Barkod Kayitlari (child table)
    - Calisma Karti Alt Operasyon Kayitlari (child table)
    - Test Masasi Dogrulama Kaydi   (linked standalone)
    - Makine Gunluk Bakim Formu    (linked standalone)
"""

from __future__ import annotations

import frappe

# Child table'lar (parenttype ile silinir)
CHILD_TABLES = [
    "Operasyon Duruslari",
    "Calisma Karti Hurda",
    "Calisma Karti IDC Olcumleri",
    "Calisma Karti Barkod Kayitlari",
    "Calisma Karti Alt Operasyon Kayitlari",
]

# Calisma Karti'ye Link field ile bağlı standalone DocType'lar
# (doctype_adı, link_field_adı)
LINKED_DOCTYPES = [
    ("Test Masasi Dogrulama Kaydi", "calisma_karti_ref"),
    ("Makine Gunluk Bakim Formu", "calisma_karti_ref"),
]


def run():
    print("=" * 60)
    print("⚠️  KTA Çalışma Kartı — Veri Temizleme Başlıyor")
    print("=" * 60)

    total = frappe.db.count("Calisma Karti")
    if total == 0:
        print("ℹ️  Silinecek Calisma Karti kaydı yok. İşlem tamamlandı.")
        return

    print(f"   Toplam {total} Calisma Karti kaydı bulundu.")

    # Onay
    try:
        onay = input(f"\n   '{total}' kart ve tüm alt verileri SİLİNECEK. Devam? [evet/hayir]: ").strip().lower()
        if onay not in ("evet", "e", "yes", "y"):
            print("   İptal edildi.")
            return
    except EOFError:
        print("   (Otomatik mod) Devam ediliyor...")

    # 1) Linked standalone DocType'ları temizle
    print("\n   Bağlı dokümanlar temizleniyor...")
    for dt, field in LINKED_DOCTYPES:
        try:
            table_name = f"tab{dt}"
            cnt = frappe.db.sql(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field}` IS NOT NULL", as_list=True)[0][0]
            if cnt:
                frappe.db.sql(f"DELETE FROM `{table_name}` WHERE `{field}` IS NOT NULL")
                print(f"     ✓ {dt} — {cnt} kayıt silindi")
            else:
                print(f"     - {dt} — kayıt yok")
        except Exception as e:
            print(f"     ⚠ {dt} temizlenemedi: {e}")

    # 2) Child table'ları temizle
    print("\n   Child tablolar temizleniyor...")
    for child_dt in CHILD_TABLES:
        try:
            table_name = f"tab{child_dt}"
            frappe.db.sql(f"DELETE FROM `{table_name}` WHERE parenttype = 'Calisma Karti'")
            print(f"     ✓ {child_dt} temizlendi")
        except Exception as e:
            print(f"     ⚠ {child_dt} temizlenemedi: {e}")

    # 3) Frappe metadata tablolarını temizle (Comment, Version, Communication vb.)
    print("\n   Sistem kayıtları temizleniyor...")
    for meta_dt in ("Comment", "Version", "Communication", "Activity Log"):
        try:
            table_name = f"tab{meta_dt}"
            frappe.db.sql(f"DELETE FROM `{table_name}` WHERE reference_doctype = 'Calisma Karti'")
            print(f"     ✓ {meta_dt} temizlendi")
        except Exception as e:
            print(f"     ⚠ {meta_dt} temizlenemedi: {e}")

    # ToDo temizliği
    try:
        frappe.db.sql("DELETE FROM `tabToDo` WHERE reference_type = 'Calisma Karti'")
        print("     ✓ ToDo temizlendi")
    except Exception as e:
        print(f"     ⚠ ToDo temizlenemedi: {e}")

    # 4) Ana tabloyu doğrudan SQL ile sil
    print("\n   Ana kartlar siliniyor...")
    frappe.db.sql("DELETE FROM `tabCalisma Karti`")

    frappe.db.commit()

    print()
    print("=" * 60)
    print(f"✅ Temizlik tamamlandı: {total} kart ve tüm bağlı veriler silindi.")
    print("=" * 60)


if __name__ == "__main__":
    run()
