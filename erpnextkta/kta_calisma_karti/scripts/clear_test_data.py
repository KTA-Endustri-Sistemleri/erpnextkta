"""
KTA Çalışma Kartı — Veri Temizleme Scripti
==========================================

⚠️  DİKKAT: Bu script tüm "Calisma Karti" belgelerini ve bağlı
    alt tablo kayıtlarını kalıcı olarak siler. GERI ALINAMAZ.
    Yalnızca test ortamında kullanın.

Kullanım (bench console):
    %run /opt/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_calisma_karti/scripts/clear_test_data.py

Veya bench execute ile:
    bench --site <site-adi> execute erpnextkta.kta_calisma_karti.scripts.clear_test_data.run

Ne siler:
    - Calisma Karti (ana doküman — önce cancel, sonra delete)
    - Operasyon Duruslari          (child table)
    - Calisma Karti Hurda          (child table)
    - Calisma Karti IDC Olcumleri  (child table)
    - Calisma Karti Barkod Kayitlari (child table)
    - Calisma Karti Alt Operasyon Kayitlari (child table)
"""

from __future__ import annotations

import frappe

# Child table → parent field adı eşleşmeleri (doğrudan SQL ile temizlenir)
CHILD_TABLES = [
    "Operasyon Duruslari",
    "Calisma Karti Hurda",
    "Calisma Karti IDC Olcumleri",
    "Calisma Karti Barkod Kayitlari",
    "Calisma Karti Alt Operasyon Kayitlari",
]


def run():
    print("=" * 60)
    print("⚠️  KTA Çalışma Kartı — Veri Temizleme Başlıyor")
    print("=" * 60)

    # 1) Mevcut kart sayısını kontrol et
    total = frappe.db.count("Calisma Karti")
    if total == 0:
        print("ℹ️  Silinecek Calisma Karti kaydı yok. İşlem tamamlandı.")
        return

    print(f"   Toplam {total} Calisma Karti kaydı bulundu.")

    # 2) Onay (bench console'da çalışıyorsa interaktif onay iste)
    try:
        onay = input(f"\n   '{total}' kart ve tüm alt verileri SİLİNECEK. Devam? [evet/hayir]: ").strip().lower()
        if onay not in ("evet", "e", "yes", "y"):
            print("   İptal edildi.")
            return
    except EOFError:
        # bench execute komutuyla çalışırken stdin yok — otomatik devam
        print("   (Otomatik mod) Devam ediliyor...")

    # 3) Child table'ları doğrudan SQL ile temizle (en hızlı yol)
    print("\n   Child tablolar temizleniyor...")
    for child_dt in CHILD_TABLES:
        try:
            tablo = frappe.db.get_value("DocType", child_dt, "name")
            if not tablo:
                continue
            db_tablo = f"tab{child_dt}"
            frappe.db.sql(f"DELETE FROM `{db_tablo}` WHERE parenttype = 'Calisma Karti'")
            print(f"     ✓ {child_dt} temizlendi")
        except Exception as e:
            print(f"     ⚠ {child_dt} temizlenemedi: {e}")

    # 4) Ana dokümanları sil
    # Submit edilmiş (docstatus=1) olanları önce cancel et, sonra sil
    print("\n   Ana kartlar siliniyor...")
    
    all_names = frappe.get_all(
        "Calisma Karti",
        fields=["name", "docstatus"],
        limit_page_length=0,    # tümü
    )

    deleted  = 0
    errored  = 0

    for row in all_names:
        name = row["name"]
        try:
            if row["docstatus"] == 1:
                # Submit edilmiş → önce cancel
                frappe.db.set_value("Calisma Karti", name, "docstatus", 2, update_modified=False)

            frappe.delete_doc(
                "Calisma Karti",
                name,
                ignore_permissions=True,
                ignore_missing=True,
                force=True,        # docstatus=2 olanlarda bile çalışır
                delete_permanently=True,
            )
            deleted += 1
        except Exception as e:
            errored += 1
            print(f"     ⚠ Silinemedi [{name}]: {e}")

    frappe.db.commit()

    print()
    print("=" * 60)
    print(f"✅ Temizlik tamamlandı:")
    print(f"   Silinen  : {deleted}")
    print(f"   Hatalı   : {errored}")
    print("=" * 60)


if __name__ == "__main__":
    run()
