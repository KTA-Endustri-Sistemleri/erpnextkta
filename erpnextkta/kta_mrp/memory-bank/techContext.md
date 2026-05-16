# Teknik Bağlam: KTA MRP

## Teknolojiler
- **Çekirdek**: Frappe Framework (Python 3.x, MariaDB).
- **Önyüz**: Vanilla JS (Frappe Script Reports).
- **Kütüphaneler**: `math` (yuvarlama işlemleri için), `collections.defaultdict` (veri yapıları için).

## Geliştirme Yapısı
- **Özel Uygulama**: `kta_mrp`.
- **Ana Rapor Dosyaları**:
    - `production_pipeline_analysis.py/js` (Üretim Komuta Merkezi)
    - `capacity_planning_report.py/js` (Kapasite Planlama)
    - `work_order_planning.py/js` (İş Emri Planlama)
    - `material_requirement.py/js` (Malzeme İhtiyacı)
    - `report_utils.py` (Ortak yardımcı fonksiyonlar ve filtreler).

## Teknik Kısıtlar
- **Haftalık Çözünürlük**: Tüm planlama ISO hafta formatında (YYYY-Www) yapılır.
- **"ÜRÜN" Filtresi**: Ana üretim planında sadece `custom_ara_malzeme_grubu == "ÜRÜN"` olan kalemler dikkate alınır.
- **Performans**: Malzeme İhtiyacı raporu, tam bir kapasite yeniden hesaplamasını tetikler, bu nedenle tarih aralıkları filtrelerle sınırlandırılmalıdır.

## Bağımlılıklar
- Başlangıç talep verisi için `ProductionStartWeekReport` raporuna dayanır.
- Kapasite tanımları için `Item` ve `Item Group` özel alanlarına dayanır.
- Geçmiş performans verisi için `Work Order` kayıtlarına dayanır.
- MOQ ve Paketleme tanımları için `Item Price` tablosuna dayanır (`custom_minimum_order_quantity` ve `custom_minimum_paketleme_miktari`).
