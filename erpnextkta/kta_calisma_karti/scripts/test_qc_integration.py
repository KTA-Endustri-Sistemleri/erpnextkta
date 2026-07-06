import frappe
from erpnextkta.kta_calisma_karti.api_impl.qc import (
    get_qc_templates_for_ck,
    get_template_details,
    submit_kta_quality_inspection
)

def test_qc_integration():
    """
    Manual verification script for QC integration.
    Run via: bench --site [site] execute erpnextkta.kta_calisma_karti.scripts.test_qc_integration.test_qc_integration
    """
    print("QC Entegrasyon Testi Başlıyor...")
    
    # 1. Find a Calisma Karti that is linked to a Job Card
    ck_name = frappe.db.get_value("Calisma Karti", {"docstatus": 0, "is_karti": ["!=", ""]}, "name")
    
    if not ck_name:
        print("Hata: Test için Job Card bağlantılı aktif Çalışma Kartı bulunamadı.")
        return

    print(f"Şu Çalışma Kartı ile test ediliyor: {ck_name}")

    # 2. Test fetching templates
    templates_res = get_qc_templates_for_ck(ck_name)
    print(f"Mevcut Şablonlar: {len(templates_res['templates'])}")
    
    if not templates_res['templates']:
        print("Uyarı: Sistemde Kalite Kontrol Şablonu bulunamadı.")
        return
        
    template_name = templates_res['templates'][0]['name']
    print(f"Test için Seçilen Şablon: {template_name}")

    # 3. Test fetching details
    params = get_template_details(template_name)
    print(f"Şablondaki parametre sayısı: {len(params)}")

    # 4. Mock readings
    readings = []
    for p in params:
        readings.append({
            "specification": p["specification"],
            "parameter": p["parameter"],
            "reading_1": 10 if p["numeric"] else "OK",
            "status": "Accepted",
            "numeric": p["numeric"],
            "min_value": p["min_value"],
            "max_value": p["max_value"]
        })

    # 5. Test submission
    print("Kalite Kontrol gönderiliyor...")
    try:
        res = submit_kta_quality_inspection(ck_name, template_name, readings)
        print(f"Başarılı! MAT-QA oluşturuldu: {res['quality_inspection']}")
        
        # Verify CK state
        ck = frappe.get_doc("Calisma Karti", ck_name)
        print(f"CK Kalite Kontrol Durumu: {ck.kalite_kontrol}")
        print(f"CK Bağlı Kontrol: {ck.quality_inspection}")
        
        if ck.kalite_kontrol == "Onaylandı" and ck.quality_inspection == res['quality_inspection']:
            print("Doğrulama BAŞARILI!")
        else:
            print("Doğrulama BAŞARISIZ: Bağlantı veya durum uyuşmazlığı.")
            
    except Exception as e:
        print(f"Gönderim başarısız: {str(e)}")
        frappe.db.rollback()

if __name__ == "__main__":
    test_qc_integration()
