# İlerleme: KTA MRP Optimizasyonu

> Son güncelleme: 2026-05-16 (Raporlar Modülerleştirildi & BOM Stock Override)

## Neler Çalışıyor?
- [x] **Merkezi Rapor Altyapısı**: `report_utils.py` (Python) + `kta_report_utils.js` (JS) — tüm MRP raporları bu altyapıyı kullanıyor.
- [x] **BOM Stock Report Override**: `kta_report_overrides.js` ile "Sadece Varsayılan Reçeteler" filtresi core değiştirilmeden enjekte ediliyor.
- [x] **Production Pipeline Analysis**: Stock Evolution + WIP entegrasyonu ile haftalık üretim bandı raporu.
- [x] **Kapasite Planlama**: Paylaşımlı grup kapasitesi, hibrit FIFO+Kritiklik dengeleme, lineer ramp-up, `warehouses` filtresi, ISO hafta hataları düzeltildi.
- [x] **Material Requirement**: MOQ + paketleme yuvarlaması (`Item Price` tablosundan), tuple unpack hatası düzeltildi, dengeleme/ramp-up filtreleri eklendi.
- [x] **Üretim Komuta Merkezi**: Stok evrimini (Stock Evolution) gösteren ana strateji raporu.
- [x] **Dinamik Kapasite**: Tanımlı veya geçmişe dayalı otomatik kapasite tespiti.
- [x] **Hibrit Dengeleme**: FIFO + Oransal dağılım mantığı.
- [x] **Geriye Dönük Yumuşatma (Ramp-up)**: Gelecekteki yük patlamalarını önden hazırlama.
- [x] **Açık İş Emri Entegrasyonu**: WIP verisinin kapasite ve stok hesaplarına dahil edilmesi.
- [x] **Koli Bazlı Yuvarlama**: Sahadaki koli birimleriyle tam uyumlu üretim rakamları.

## Mevcut Durum
Tüm temel optimizasyon gereksinimleri uygulandı. Raporlar artık ortak `report_utils.py` ve `kta_report_utils.js` üzerinden filtre ve formatlama yapıyor; tekrar eden kod ortadan kalktı.

## Eksikler / Yapılacaklar
- [ ] **Çoklu Tedarikçi Desteği**: MOQ hesaplarında şu an sadece varsayılan tedarikçi baz alınıyor.
- [ ] **Emniyet Stoğu**: Malzeme raporunda otomatik "Emniyet Stoğu" tetikleyicisi eklenmesi.
- [ ] **Geri Bildirim**: 3 haftalık varsayılan ramp-up süresinin saha performansı için yeterliliğinin izlenmesi.
- [ ] **Krimp Protokolü Baskı Şablonu**: Ayrı ticket gerekiyor.

## Bilinen Sorunlar
- **Hız**: Çok geniş tarih aralıklarında Malzeme İhtiyaç raporu, üçlü rapor çağırma yapısı nedeniyle yavaş çalışabiliyor (Kapasite → BOM Patlatma → Stok/PO Kontrolü).
