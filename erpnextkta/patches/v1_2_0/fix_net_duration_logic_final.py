"""
Patch: Mevcut tüm çalışma kartlarının net_calisma_suresi değerini
yeni mantığa göre günceller.
Formül: Net = min(Toplam Süre, Kalan Kapasite) - Duruşlar
Önce toplam süre vardiya kapasitesiyle (430 dk) sınırlanır, sonra duruşlar düşülür.
"""
import frappe

def execute():
    # Bitmiş tüm (Taslak veya Submitted) kartları getir
    affected_cards = frappe.get_all("Calisma Karti", 
        filters={
            "docstatus": ["!=", 2],
            "durum": "Bitmiş"
        },
        pluck="name"
    )

    updated_count = 0
    total_count = len(affected_cards)
    
    frappe.logger().info(f"fix_net_duration_logic_final: {total_count} kart taranıyor...")

    for i, name in enumerate(affected_cards):
        doc = frappe.get_doc("Calisma Karti", name)
        
        old_net = doc.net_calisma_suresi
        old_sure = doc.toplam_sure
        
        # Yeni mantığı hesaplat (calisma_karti.py içindeki yeni logic)
        doc.update_durum()
        
        if doc.net_calisma_suresi != old_net or doc.toplam_sure != old_sure:
            # Güncellenmesine izin ver (Submit edilmişse bile)
            if doc.docstatus == 1:
                doc.flags.ignore_validate_update_after_submit = True
            
            # Değerleri doğrudan DB'ye yaz (modified tarihini korumak için set_value kullanıyoruz)
            frappe.db.set_value("Calisma Karti", doc.name, {
                "net_calisma_suresi": doc.net_calisma_suresi,
                "toplam_sure": doc.toplam_sure,
                "toplam_durus": doc.toplam_durus,
                "durum": doc.durum
            }, update_modified=False)
            
            updated_count += 1

        # Her 100 kayıtta bir commit ve log
        if (i + 1) % 100 == 0:
            frappe.db.commit()
            frappe.logger().info(f"fix_net_duration_logic_final: {i + 1}/{total_count} kart işlendi...")

    frappe.db.commit()
    print(f"fix_net_duration_logic_final: {updated_count} cards updated out of {total_count} total scanned.")
