import frappe

def execute():
    mappings = {
        "OP10-0001": {"sanal_yarimamul_davranisi": "Temel Kablo Oluşturur", "davranis_alt_parametresi": None},
        "OP10-0002": {"sanal_yarimamul_davranisi": "Temel Kablo Oluşturur", "davranis_alt_parametresi": None},
        "OP10-0003": {"sanal_yarimamul_davranisi": "Temel Kablo Oluşturur", "davranis_alt_parametresi": None},
        "OP10-0004": {"sanal_yarimamul_davranisi": "Temel Kablo Oluşturur", "davranis_alt_parametresi": None},
        "OP11-0001": {"sanal_yarimamul_davranisi": "Düğümleri Birleştirir", "davranis_alt_parametresi": "Terminal"},
        "OP11-0002": {"sanal_yarimamul_davranisi": "Uca / Düğüme Bileşen Ekler", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP11-0003": {"sanal_yarimamul_davranisi": "Uca / Düğüme Bileşen Ekler", "davranis_alt_parametresi": "Kapatır"},
        "OP11-0004": {"sanal_yarimamul_davranisi": "Temel Kablo Oluşturur", "davranis_alt_parametresi": None},
        "OP11-0005": {"sanal_yarimamul_davranisi": "Temel Kablo Oluşturur", "davranis_alt_parametresi": None},
        "OP20-0001": {"sanal_yarimamul_davranisi": "Uca / Düğüme Bileşen Ekler", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP20-0002": {"sanal_yarimamul_davranisi": "Uca / Düğüme Bileşen Ekler", "davranis_alt_parametresi": "Kapalı Düğüme Ekler"},
        "OP20-0003": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP20-0004": {"sanal_yarimamul_davranisi": "Doğrulama / Test", "davranis_alt_parametresi": None},
        "OP20-0005": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP20-0006": {"sanal_yarimamul_davranisi": "Uca / Düğüme Bileşen Ekler", "davranis_alt_parametresi": "Beklemede"},
        "OP20-0007": {"sanal_yarimamul_davranisi": "Düğümleri Birleştirir", "davranis_alt_parametresi": "Lehim"},
        "OP20-0008": {"sanal_yarimamul_davranisi": "Düğümleri Birleştirir", "davranis_alt_parametresi": "Perçin"},
        "OP20-0009": {"sanal_yarimamul_davranisi": "Alt Montaj (Sub-Assembly)", "davranis_alt_parametresi": "Yeni WIP"},
        "OP20-0010": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP20-0011": {"sanal_yarimamul_davranisi": "Bileşeni Aktifleştirir", "davranis_alt_parametresi": "Hayır"},
        "OP20-0012": {"sanal_yarimamul_davranisi": "Uca / Düğüme Bileşen Ekler", "davranis_alt_parametresi": "Kapatır"},
        "OP20-0013": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP20-0014": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP20-0015": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP20-0016": {"sanal_yarimamul_davranisi": "Düğümleri Birleştirir", "davranis_alt_parametresi": "Terminal"},
        "OP20-0017": {"sanal_yarimamul_davranisi": "Ucu Böler", "davranis_alt_parametresi": None},
        "OP30-0001": {"sanal_yarimamul_davranisi": "Soketler", "davranis_alt_parametresi": None},
        "OP30-0002": {"sanal_yarimamul_davranisi": "Soketler", "davranis_alt_parametresi": None},
        "OP30-0003": {"sanal_yarimamul_davranisi": "Soketler", "davranis_alt_parametresi": None},
        "OP30-0004": {"sanal_yarimamul_davranisi": "Uca / Düğüme Bileşen Ekler", "davranis_alt_parametresi": "Kapalı Düğüme Ekler"},
        "OP40-0001": {"sanal_yarimamul_davranisi": "Enjeksiyon", "davranis_alt_parametresi": None},
        "OP50-0001": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP50-0002": {"sanal_yarimamul_davranisi": "Doğrulama / Test", "davranis_alt_parametresi": None},
        "OP50-0003": {"sanal_yarimamul_davranisi": "Doğrulama / Test", "davranis_alt_parametresi": None},
        "OP50-0004": {"sanal_yarimamul_davranisi": "Doğrulama / Test", "davranis_alt_parametresi": None},
        "OP60-0001": {"sanal_yarimamul_davranisi": "Doğrulama / Test", "davranis_alt_parametresi": None},
        "OP60-0002": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"},
        "OP60-0003": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Tamamlandı Kapatır"},
        "OP60-0004": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Tamamlandı Kapatır"},
        "OP60-0005": {"sanal_yarimamul_davranisi": "Yapısal Değişikliksiz İşlem", "davranis_alt_parametresi": "Açık Bırakır"}
    }

    count = 0
    for op_name, config in mappings.items():
        if frappe.db.exists("KTA Calisma Karti Alt Operasyonlari", op_name):
            try:
                frappe.db.set_value(
                    "KTA Calisma Karti Alt Operasyonlari", 
                    op_name, 
                    "sanal_yarimamul_davranisi", 
                    config.get("sanal_yarimamul_davranisi")
                )
                
                frappe.db.set_value(
                    "KTA Calisma Karti Alt Operasyonlari", 
                    op_name, 
                    "davranis_alt_parametresi", 
                    config.get("davranis_alt_parametresi")
                )
                print(f"Başarılı: {op_name} güncellendi.")
                count += 1
            except Exception as e:
                print(f"Hata ({op_name}): {str(e)}")

    frappe.db.commit()
    print(f"İşlem tamamlandı! Toplam {count} adet kayıt başarıyla güncellendi.")
