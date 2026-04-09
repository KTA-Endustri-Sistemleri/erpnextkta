"""
Patch: Mevcut çalışma kartlarının net_calisma_suresi değerini 
yeni mantığa (430 dk - Duruşlar) göre günceller.
"""
import frappe

def execute():
    # Bitmiş ve duruşu olan (Taslak veya Submitted) tüm kartları getir
    affected_cards = frappe.get_all("Calisma Karti", 
        filters={
            "docstatus": ["!=", 2],
            "durum": "Bitmiş",
            "toplam_durus": ["!=", "00:00:00"]
        },
        pluck="name"
    )

    updated_count = 0
    for name in affected_cards:
        doc = frappe.get_doc("Calisma Karti", name)
        
        old_net = doc.net_calisma_suresi
        
        # Yeni mantığı hesaplat (L205-L210 logic already in code)
        doc.update_durum()
        
        if doc.net_calisma_suresi != old_net:
            # Submitted kartın güncellenmesine izin ver
            doc.flags.ignore_validate_update_after_submit = True
            
            # Değerleri doğrudan DB'ye yaz (audit log/modified_by koruması istenirse)
            # Ama genelde doc.save() tercih edilir. 
            # Burada 'net_calisma_suresi' ve 'durum' gibi alanları güncellemek yeterli.
            frappe.db.set_value("Calisma Karti", doc.name, {
                "net_calisma_suresi": doc.net_calisma_suresi,
                "toplam_sure": doc.toplam_sure,
                "toplam_durus": doc.toplam_durus,
            }, update_modified=False)
            
            updated_count += 1

    if updated_count:
        frappe.db.commit()

    print(f"fix_calisma_karti_net_durations: {updated_count} cards updated.")
