# Active Context — kta_calisma_karti

> Son güncelleme: 2026-04-24 (Frontend Race Condition & Testing)

Frontend tarafında mükerrer kayıt oluşumunu (Enter-spam, double-click) engelleyen atomik korumalar ve bu durumu 113 farklı senaryoda doğrulayan Vitest test süiti tamamlandı. Backend tarafında ise bitmemiş kartların submit edilmesi engellendi.

- [x] **Frontend Race Condition Guards**: `App.vue` üzerinde `loading` tabanlı atomik kilitler ve `withLoading` geciktirme mekanizması (2026-04-24).
- [x] **Robust Frontend Testing**: Vitest ile spamming ve asenkron yarış durumlarını kapsayan 113 testin başarıyla geçmesi (2026-04-24).
- [x] **Backend Submission Validation**: Bitiş saati olmayan kartların onaylanmasının engellenmesi (2026-04-24).
- [x] **Manufacturing Permissions**: Üretim rollerinin dashboard ve rapor yetkilerinin düzenlenmesi (2026-04-24).
- [ ] **Test Masası Entegrasyonu**: Arayüz tarafındaki eksiklerin giderilmesi (Planlanıyor).
- [ ] **Statü Senkronizasyonu**: CK → Job Card statü akışının tasarımı (Beklemede).

## Son Değişiklikler (2026-04-24) — Frontend Güvenliği ve Vitest Suite
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
