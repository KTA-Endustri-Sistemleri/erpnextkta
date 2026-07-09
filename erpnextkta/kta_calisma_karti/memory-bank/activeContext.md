# Active Context — kta_calisma_karti

> Son güncelleme: 2026-07-06 (Job Card Senkronizasyonu, UI Yenilemesi, Çoklu Hammadde, Enjeksiyon & Krimp Formları, Raporlama)

Bu dönemde yapılan geliştirmeler: Çalışma Kartı arayüzü ve yaşam döngüsü baştan aşağı yenilendi (Overhaul). Job Card senkronizasyonu tamamlandı (miktar dağıtımı ve sequence doğrulama bypass mekanizmaları eklendi). Alt operasyonlarda çoklu hammadde desteği, dinamik formlar ve otomatik UOM (Birim) çekme özellikleri getirildi. Krimp Ölçüm Formu ve Enjeksiyon Proses Formu eklendi. Ayrıca İş Emri Hammadde Tüketim Raporu ve Job Card üzerinden toplu protokol yazdırma özelliği eklendi. `tamamlanan_miktar` zorunluluğu kaldırılarak, üretim girişleri `alt_operasyon` üzerinden zorunlu hale getirildi.

- [x] **Job Card Senkronizasyonu**: Çalışma kartı üzerinden Job Card'a completed quantities dağıtımı, sequence validasyonu ve kapasite limiti bypass mekanizmaları eklendi (2026-07-06).
- [x] **UI ve Yaşam Döngüsü Overhaul**: Arayüz modernizasyonu, lifecycle güncellemeleri ve otomatik etiketleme entegrasyonu (2026-07-06).
- [x] **Çoklu Hammadde & UOM Takibi**: Alt operasyonlara çoklu hammadde desteği geldi. Item UOM (Birim) otomatik olarak arka planda permission error olmadan çekilip takip ediliyor (2026-07-06).
- [x] **Formlar & Raporlar**: Enjeksiyon Proses Formu, Krimp Ölçüm Formu ve İş Emri Hammadde Tüketim Raporu eklendi. Toplu Krimp Protokolü Yazdırma aktifleştirildi (2026-07-06).
- [x] **Kalite & Güvenlik Fixleri**: QI sync race condition düzeltildi. Operatörler için standart döküman permission hataları bypass edildi (2026-07-06).
- [x] **Modüler Kalite (Alt Operasyon Bazlı Kalite Onayı)**: Bütüncül çalışma kartı kalitesinden alt operasyon satır bazlı kalite onayına geçiş sağlandı. Kart liste görünümüne (CkCard.vue) çoklu statüler için dinamik parçalı/degrade renk blokları eklendi (2026-07-06).
- [x] **Krimp Formu Çift Taraf & Akıllı Autofill**: Alt operasyon onayında açılan krimp formunda, alt operasyon ismi "Çift Taraf" içeriyorsa form dinamik genişleyerek 2. yön alanlarını açar. Ayrıca hedeflenen yükseklikler ve kablo/kontak kodları form ekranına otomatik (`autofill`) doldurulur (2026-07-06).
- [x] **Üretim Miktarı Mantığı**: `tamamlanan_miktar` alanı zorunluluktan çıkarılıp, verinin `alt_operasyon`lar üzerinden girilmesi zorunlu kılındı (2026-07-06).
- [x] **Alt Operasyon Dinamik Formu**: "Küt", "Tek Taraf", "Çift Taraf" isimli alt operasyonlarda Terminal adet ve boyut alanları arayüzden gizlenip, otomatik olarak Kablo adetine (Hammadde 2) eşitlenerek veritabanına yazılması sağlandı (2026-07-04).
- [x] **Günlük Hata Raporu**: Hedef çalışma süresinin altında kalan (5 saat altı) operatörleri tespit edip amirlere günlük e-posta raporu gönderen cron job eklendi (2026-06-25).
- [x] **Krimp Ölçüm Modülü**: `Calisma Karti Krimp Olcumleri` DocType, backend CRUD API, `KrimpSection.vue` bileşeni ve `MeasureGauge.vue` tolerans göstergesi tamamlandı.
- [ ] **Test Masası Entegrasyonu**: Arayüz tarafındaki eksiklerin giderilmesi (Planlanıyor).

## Son Değişiklikler (2026-07-04) — Alt Operasyon Dinamik Arayüzü
Kullanıcının işini kolaylaştırmak ve hatalı veri girişini önlemek için:
*   **İsime Dayalı Akıllı Form**: `AltOperasyonView.vue` ve `prompts.ts` içerisinde, seçilen alt operasyonun isminde geçen "Küt", "Tek Taraf" ve "Çift Taraf" anahtar kelimelerine göre arayüz tepkisi dinamikleştirildi.
*   **Otomatik Adet Eşitleme**: Tek ve Çift Taraf işlemlerinde Terminal (Hammadde 1 ve 3) alanlarının Boyut ve Adet kutuları formdan (`depends_on` kullanılarak) gizlendi. Kullanıcı formda sadece Kablo (Hammadde 2) adedini girdiğinde, frontend aşamasında `islem_adedi_1` ve `islem_adedi_3` bu kablo adedine eşitlenip (override edilip) arka plana gönderiliyor.

## Önceki Geliştirmeler (2026-06-25) — Raporlama, Dashboard ve Validasyon Güncellemeleri
Kullanıcı deneyimini, yönetimsel takibi ve veri kalitesini artırmak amacıyla yapılan son eklemeler:
*   **Daily Operator Error Report**: Günlük hedef çalışma süresini (7 saat 10 dk) dolduramayan ve 5 saatin altında kalan operatörlerin listesini amirlere otomatik olarak e-posta ile raporlayan zamanlanmış bir cron görevi (`tasks.py` -> `send_daily_calisma_karti_error_report`) eklendi.
*   **User Dashboard Override**: `User` DocType dashboard'u `hooks.py` üzerindeki `override_doctype_dashboards` ile ezildi. Kullanıcı profili içinde, kullanıcının `Employee` kartı ile eşleşen tüm aktif/açık `Calisma Karti` kayıtlarının sayısı ve listesi "Aktivite" kartı olarak eklendi (`overrides/user_dashboard.py`).
*   **Operator Düşük Net Süre Grafiği**: Belirlenen gün aralığında net çalışma süresi en düşük olan operatörleri ve bunların toplam sürelerini dakika bazında listeleyen yeni bir Dashboard Grafiği (`operator_dusuk_net_sure`) eklendi.
*   **Duruş "Diğer" Validasyonu**: Duruş nedeni "Diger" olarak seçildiğinde, kullanıcının bir açıklama metni girmesi frontend (dialog prompt) ve backend (`calisma_karti.py` -> `validate` hook'u) katmanlarında zorunlu kılındı.

## Önceki Geliştirmeler (2026-04-24) — Frontend Güvenliği ve Vitest Suite
Kullanıcıların "ardışık Enter" veya "hızlı tıklama" hatalarından kaynaklı mükerrer kart oluşturma riskini %100 engellemek için:
*   **Atomic Guards**: `submitWorkCard`, `fetchWorkOrderByBarcode` ve `fetchJobCardByBarcode` fonksiyonlarına senkron `loading` kontrolleri eklendi.
*   **withLoading (minMs=900)**: Asenkron işlemlerin en az 900ms sürmesi garanti edilerek UI'ın kararsız kalması (flickering) ve mükerrer tetiklemeler engellendi.
*   **Vitest Suite**: `App.race.test.js` altında "barkod spam", "hızlı Enter" ve "ağ gecikmesi sırasında tıklama" gibi 15 yeni senaryo test edildi. Toplam test sayısı 113'e çıkarıldı.

## Önceki Geliştirmeler (2026-04-19) — Dynamic Downtime & Visibility Fix
Duruş yönetimi tamamen dinamik hale getirildi. `KTA Calisma Karti Settings` üzerinden yönetilen otomatik duruşlar, "Sistem" kategorisi ve `is_system` tabanlı UI filtreleme mantığı devreye alındı.

*   **Dynamic Downtime Settings**: Otomatik duruş metinleri koddan arındırılarak Ayarlar tablosuna bağlandı.
*   **"Sistem" Category**: Otomatik duruşlar "Sistem" tipi ile Manuel duruşlardan (Arıza, Mola vb.) ayrıldı.
*   **Visibility Logic Fix**: `is_system=0` olanların kullanıcıya görünmesi, `1` olanların ise sadece API/Sistem için gizli kalması sağlandı.
*   **Downtime Reason Standardization**: "Diğer" kayıtları analiz edilerek 6 yeni standart manuel neden (Arıza, Kalıp vb.) eklendi.

## Önceki Geliştirmeler (2026-04-14) — API Test Kapsamı ve Stabilizasyon
Kritik iş akışlarını korumak için `tests/test_api.py` altında kapsamlı bir API test süiti oluşturuldu:

*   **Kritik API Testleri**:
    *   `test_islem_yap_workflow`: Başlat, Duruş, Devam, Bitiş flow'u.
    *   `test_qc_submission_via_api`: QC Belgesi oluşturma ve kart restorasyonu.
    *   `test_scrap_synchronization_via_api`: Hurda/Stok Girişi senkronizasyonu.
    *   `test_alt_operasyon_crud_via_api`: Alt operasyon CRUD işlemleri.
*   **Stabilizasyon Teknikleri**:
    *   **Employee Seeding**: Her test için benzersiz email ile operatör oluşturulup "Anti-Double-Click" koruması bypass edildi.
    *   **Monkeypatching**: Masraf Merkezi (Cost Center) hiyerarşisi ve BOM hammadde validasyonları çalışma zamanında (runtime) yamalanarak test ortamı izole edildi.

## Önemli Teknik Gelişmeler
### Race Condition (Pessimistic Locking)
*   **Pessimistic Locking (FOR UPDATE)**: 
    *   **Kalite Belgesi Kilidi**: `check_duplicate_quality_docs` içerisinde ilgili `Quality Inspection` belgesi üzerinde veritabanı düzeyinde kilit uygulanarak aynı belgenin aynı anda iki karta bağlanması engellendi.
    *   **Vardiya Kapasite Kilidi**: Operatörün vardiya süresi hesaplanırken o vardiyadaki aktif kartları kilitlenerek 430 dakikalık limitin yarış durumlarında aşılması önlendi.

### Süre Hesaplama Devrimi
*   **Süre Hesaplama Devrimi (Logic Overhaul)**: Net çalışma süresi artık `Elapsed - Pauses` değil, **Shift Capacity (430 dk) - Pauses** formülüyle hesaplanıyor.

### Smart Shift-End
*   **Vardiya Sonu Akıllı Kapatma**: Duruşta olanlar `durus_baslangic` zamanında, çalışıyor olanlar vardiya sonunda (`16:00` / `00:00`) kapatılır.

## Recent Changes
- **Modular QC Parent State Bugfix:** Corrected the behavior of modular QC where `_update_parent_qc_status_from_alt_ops` was erroneously setting the `quality_inspection` (document link) field on the parent `Calisma Karti` when all sub-operations were approved. Now, it only updates the `kalite_kontrol` status field to 'Onaylandı' or 'Onay Bekliyor', while explicitly clearing `quality_inspection` to prevent the UI from acting like a classical (card-based) QC process.
- **Authorization Documentation:** Updated the user guides to explicitly explain the behavior of `qc_allowed_roles` (Quality Roles) and `admin_roles` (Admin Roles) configuration in 'KTA Calisma Karti Settings', documenting that ordinary operators cannot delete/modify QC-approved sub-operations, but Quality Roles can bypass this lock, while Admin Roles can modify entirely finished (submitted) cards.
