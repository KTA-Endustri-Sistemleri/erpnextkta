# Active Context — kta_calisma_karti

> Son güncelleme: 2026-07-04 (Alt Operasyon Dinamik Mantığı, Hata Raporlama, Dashboard Grafik, Validasyonlar)

Bu dönemde yapılan geliştirmeler: Alt operasyon türüne (Küt Kesme, Tek Taraf, Çift Taraf) göre arayüzdeki boyut ve adet alanlarının dinamik olarak gizlenmesi ve arka planda otomatik eşitlenmesi sağlandı. Ayrıca Günlük Hata Raporu altyapısı, User Dashboard override entegrasyonu, "Operator Düşük Net Süre" dashboard grafiği ve duruş başlatma sürecinde "Diger" nedeni için açıklama zorunluluğu validasyonları eklendi.

- [x] **Alt Operasyon Dinamik Formu**: "Küt", "Tek Taraf", "Çift Taraf" isimli alt operasyonlarda Terminal adet ve boyut alanları arayüzden gizlenip, otomatik olarak Kablo adetine (Hammadde 2) eşitlenerek veritabanına yazılması sağlandı (2026-07-04).
- [x] **Günlük Hata Raporu**: Hedef çalışma süresinin altında kalan (5 saat altı) operatörleri tespit edip amirlere günlük e-posta raporu gönderen cron job eklendi (2026-06-25).
- [x] **User Dashboard Override**: `User` doctype dashboard'u genişletilerek kullanıcının Employee kartı ile ilişkili Çalışma Kartları listesi ve open count sayımı eklendi (2026-06-25).
- [x] **Operator Düşük Net Süre Grafiği**: Son N günde en az net çalışma süresine sahip operatörlerin net sürelerini dakika bazında görselleştiren custom dashboard chart bileşeni eklendi (2026-06-25).
- [x] **Duruş "Diğer" Validasyonu**: Duruş nedeni "Diger" seçildiğinde açıklama girmeyi hem form/SPA arayüzünde hem de backend `validate` aşamasında zorunlu kılan mekanizma eklendi (2026-06-25).
- [x] **Krimp Ölçüm Modülü**: `Calisma Karti Krimp Olcumleri` DocType, backend CRUD API, `KrimpSection.vue` bileşeni ve `MeasureGauge.vue` tolerans göstergesi tamamlandı (2026-05-13 – 2026-05-15).
- [x] **QC Reddetme Yaşam Döngüsü Düzeltmesi**: Red kararında QI belgesi anında submit ediliyor, `finalize_rejected_card()` ile Çalışma Kartı da otomatik gönderiliyor (2026-05-11).
- [x] **Alt Operasyon Submit İzinleri**: `kta_calisma_karti_alt_operasyonlari` ve `kta_calisma_karti_operasyonlari` DocType'larında eksik Submit rolleri `setup.py` ile düzeltildi (2026-05-15).
- [x] **Frontend Race Condition Guards**: `App.vue` üzerinde `loading` tabanlı atomik kilitler ve `withLoading` geciktirme mekanizması (2026-04-24).
- [x] **Robust Frontend Testing**: Vitest ile spamming ve asenkron yarış durumlarını kapsayan 113 testin başarıyla geçmesi (2026-04-24).
- [x] **Backend Submission Validation**: Bitiş saati olmayan kartların onaylanmasının engellenmesi (2026-04-24).
- [ ] **Krimp Protokolü Baskı Şablonu**: Print format henüz tasarlanmadı (Planlanıyor).
- [ ] **Test Masası Entegrasyonu**: Arayüz tarafındaki eksiklerin giderilmesi (Planlanıyor).
- [ ] Statü Senkronizasyonu: CK → Job Card statü akışının tasarımı (Beklemede).

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
