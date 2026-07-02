import frappe
from erpnextkta.kta_calisma_karti.api_impl.job_card_sync import sync_time_log_to_job_card

def execute():
    """
    Tüm geçerli (İptal edilmemiş ve Submit edilmiş) Çalışma Kartlarını bulur,
    her birini sırayla Job Card'larına senkronize eder.
    Bu sayede eski kayıtlara 'operasyon', 'alt_operasyon' gibi yeni alanlar eklenir,
    ve Job Card kaydedildiği için yeni Zaman Orantılı dağıtım algoritması tetiklenir.
    """
    frappe.logger().info("Geçmiş Çalışma Kartları Job Card senkronizasyonu başlatılıyor...")
    print("Geçmiş Çalışma Kartları Job Card senkronizasyonu başlatılıyor...")

    # İptal edilmemiş ve submit edilmiş tüm kartları çek
    calisma_kartlari = frappe.get_all(
        "Calisma Karti",
        filters={
            "docstatus": 1,
            "durum": ["!=", "İptal Edildi"]
        },
        pluck="name"
    )

    if not calisma_kartlari:
        print("Senkronize edilecek uygun Çalışma Kartı bulunamadı.")
        return

    toplam = len(calisma_kartlari)
    basarili = 0
    hatali = 0

    print(f"Toplam {toplam} adet Çalışma Kartı işlenecek.")

    for i, kart_name in enumerate(calisma_kartlari):
        try:
            doc = frappe.get_doc("Calisma Karti", kart_name)
            if doc.is_karti:
                sync_time_log_to_job_card(doc)
                basarili += 1
                
                if i % 10 == 0:
                    frappe.db.commit()
                    print(f"[{i+1}/{toplam}] İşleniyor...")
        except Exception as e:
            hatali += 1
            print(f"Hata! {kart_name} işlenirken bir sorun oluştu: {str(e)}")

    frappe.db.commit()
    print(f"\n--- İŞLEM TAMAMLANDI ---")
    print(f"Toplam İşlenen: {toplam}")
    print(f"Başarılı: {basarili}")
    print(f"Hatalı: {hatali}")
    frappe.logger().info(f"Senkronizasyon Bitti. Başarılı: {basarili}, Hatalı: {hatali}")
