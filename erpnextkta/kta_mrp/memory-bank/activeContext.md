# Aktif Bağlam: KTA MRP Optimizasyonu

> Son güncelleme: 2026-05-16 (Raporlar Modülerleştirildi & BOM Stock Override)

## Mevcut Odak Noktası
Tüm MRP ve planlama raporlarının ortak bir altyapıya taşınması tamamlandı. Yeni `Production Pipeline Analysis` raporu eklendi. Kapasite planlaması paylaşımlı grup kapasitesi, hibrit dengeleme ve ramp-up desteğiyle güçlendirildi.

## Son Değişiklikler
- **Rapor Modülerleştirilmesi**: Tüm MRP raporları (`mrp_analysis`, `material_requirement`, `capacity_planning_report`, `production_start_week`, `work_order_planning`, `shipment_week`, `periodic_sales_orders`, `recommended_purchase_orders`) merkezi `report_utils.py` + `kta_report_utils.js` altyapısına taşındı.
- **Production Pipeline Analysis (Komuta Merkezi)**: Stock Evolution + WIP entegrasyonu ile haftalık üretim bandı raporu.
- **BOM Stock Report Override**: `kta_report_overrides.js` ile core ERPNext dosyasına dokunmadan "Sadece Varsayılan Reçeteler" filtresi dinamik olarak enjekte ediliyor. `frappe.provide("kta.report_overrides")` altında genişletilebilir yapı kuruldu.
- **Kapasite Planlama İyileştirmeleri**: Paylaşımlı grup kapasitesi, hibrit dengeleme (FIFO + Kritiklik), lineer ramp-up ve `warehouses` multi-select filtresi.
- **MOQ & Ambalaj Entegrasyonu**: `Item Price` tablosundan `custom_minimum_order_quantity` ve `custom_minimum_paketleme_miktari` çekilerek `max(moq, ceil(eksik/paket)*paket)` formülüyle malzeme hesapları yuvarlama yapıyor.

## Gelecek Adımlar
- **Krimp Protokolü Baskı Şablonu**: Henüz tasarlanmadı; ayrı ticket gerekiyor.
- **Çoklu Tedarikçi Desteği**: MOQ hesaplarında şu an sadece varsayılan tedarikçi baz alınıyor.
- **Emniyet Stoğu**: Malzeme raporunda otomatik "Emniyet Stoğu" tetikleyicisi eklenmesi.
- **Hız**: Çok geniş tarih aralıklarında Malzeme İhtiyaç raporu üçlü rapor çağırma yapısı nedeniyle yavaş.

## Aktif Kararlar
- **Backlog Önceliği**: Tüm gecikmiş siparişler "1. Hafta" (Bugün) kolonunda toplanarak planın gerçek borçla başlaması kararlaştırıldı.
- **Kanıtlanmış Kapasite**: Ürün kartında kapasite tanımlı değilse, son 3 aylık İş Emri verilerinden hesaplanan ortalama haftalık hız baz alınır.
- **Report Override Yaklaşımı**: `page-change` event'ine bağlı dinamik injection ile core ERPNext dosyalarına dokunulmaz; `kta.report_overrides` namespace'i altında yeni raporlar eklenebilir.
