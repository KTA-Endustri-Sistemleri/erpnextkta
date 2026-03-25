# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-25

Branş birleştirmesi (**Combined Enhancements Merge**) başarıyla tamamlandı. `calisma-karti-op-enhancements` ve `operation-jc-mapping` özellikleri tek bir stabil branşta toplandı. Bugün yapılan geliştirmeyle süre formatları `ss:dk:sn` olarak standartlaştırıldı, sihirbazdaki yönlendirme hatası giderildi ve otomatik kapatılan kartların kalite belgelerinin onaylanması sağlandı.

- [x] **Süre Formatı Standartlaştırması**: Tüm çalışma ve duruş süreleri `dk:sn` formatından `ss:dk:sn` formatına dönüştürüldü. (Tamamlandı)
- [x] **Bağlantı Hatası Düzeltmesi**: Yeni kart oluşturma sonrası "Çalışma Kartına Git" butonu artık doğru şekilde `view-calisma-karti` sayfasına yönlendiriyor. (Tamamlandı)
- [x] **Liste Görünümü & Skeleton Modernizasyonu**: `App.vue` içindeki skeleton yapısı modern shimmer animasyonu ile yenilendi ve asıl kart yapısına sadık hale getirildi. (Tamamlandı)
- [x] **Frontend Refactoring**: Dev boyutlu `App.vue` (~900 satır), `CkCard`, `CkFilters` ve `CkSkeleton` bileşenlerine ayrılarak modüler hale getirildi. (Tamamlandı)
- [x] **SPA Glassmorphism UI**: Uygulama arayüzü tam uyumlu Açık/Koyu tema değişkenleri ve akıcı tab animasyonları ile premium seviyeye çekildi. (Tamamlandı)
- [x] **Kalite Onay Kilitleme & Senkronizasyon**: Reddedilen kartların statü tutarlılığını korumak için QI bağımlı kontrol ve geri dönüş (restoration) mantığı eklendi. (Tamamlandı)
- [x] **Kart Geçiş Kısıtlaması (Veri Doğrulama)**: Operatörlerin veri girmeden açık kartlar arasında gezmesini önlemek için "Sıkı / Esnek" modlu geçiş onay sistemi eklendi. (Tamamlandı)
- [ ] **Test Masası Entegrasyonu**: Arayüz tarafındaki eksiklerin giderilmesi (Planlanıyor).
- [ ] **Statü Senkronizasyonu**: CK → Job Card statü akışının tasarımı (Beklemede).

## Son Değişiklikler (2026-03-25) — Süre Formatı Standartlaştırması
*   **Backend Mantığı**: `calisma_karti.py` içindeki `format_sure` fonksiyonu `HH:MM:SS` döndürecek şekilde, `_parse_minsec` ise hem eski (`M:SS`) hem yeni formatı tanıyacak şekilde güncellendi.
*   **Veri Göçü (Migration)**: Mevcut tüm `Calisma Karti` kayıtlarındaki süre alanları toplu bir patch ile `ss:dk:sn` formatına dönüştürüldü.
*   **DocType Etiketleri**: `Calisma Karti` ve `Operasyon Duruslari` DocType'larındaki süre alanlarının etiketleri `(ss:dk:sn)` olarak güncellendi.
*   **Frontend Görünümü**: `formatDuration` yardımcı fonksiyonu eklenerek durations SPA arayüzünde (DurusView vb.) ve standart form dashboard'unda (Indicators) yeni formatta gösterilmesi sağlandı.

## Son Değişiklikler (2026-03-25) — Bağlantı Hatası Düzeltmesi & Scheduler QI Onayı
*   **Yönlendirme Mantığı**: `create-calisma-karti` sihirbazındaki `goToCreatedDoc` fonksiyonu, standart form yerine özel `view-calisma-karti` sayfasına yönlendirme yapacak şekilde (`frappe.set_route`) güncellendi.
*   **Otomatik QI Onayı**: `tasks.py` içindeki `auto_close_timed_out_cards` fonksiyonu, kart kapatılırken bağlı olan taslak (Draft) durumundaki `Quality Inspection` belgelerini otomatik olarak onaylayacak (Submit) şekilde güçlendirildi.

## Son Değişiklikler (2026-03-23) — Glassmorphism SPA Arayüz Modernizasyonu
*   **Arayüz Paradigması**: Uygulama görünümü tamamen modern "Glassmorphism" (Cam efekti) tarzına dönüştürüldü. Arkaplan görselleri olmadan, derinlik ve gölge algısıyla (Soft UI) premium bir endüstriyel arayüz tasarlandı.
*   **Dinamik Tema Kontrastı**: Açık (Light) ve Koyu (Dark) temalar için fiziksel ışık kuralları (`--ck-glass-highlight`, `--ck-glass-bottom-edge`) katı kurallara bağlandı. Her iki temada yüksek okunanabilirlik sağlandı.
*   **Performanslı Geçişler (SPA)**: Alt sekmeler (Info, Operasyon, Kalite vb.) arasında sayfa yenilemesiz, Vue `<Transition mode="out-in">` ile donanım hızlandırmalı pürüzsüz animasyonlar eklendi.
*   **Dinamik Bileşenler**: `KaliteView` içerisindeki Kalite Belgesi linkleri, Frappe'nin lokalizasyon stringlerine ("Onaylandı", "Reddedildi") duyarlı hale getirilerek anında yeşil/kırmızı temaya bürünecek şekilde akıllandırıldı.

## Son Değişiklikler (2026-03-23) — Kart Geçiş Kısıtlaması
*   **Modüler Ayar**: `KTA Calisma Karti Settings`'e `kart_gecis_modu` eklendi (Sıkı/Esnek).
*   **Backend Validasyonu**: `check_active_card_data` API'si eklendi; `miktar_zorunlu_mu=1` ise `tamamlanan_miktar > 0`, `0` ise `alt_operasyon_kayitlari ≥ 1` kontrolü yapıyor.
*   **Çift Katmanlı Koruma**: Hem Vue SPA arayüzünde (Modal Dialog/Engel) hem de backend hook'larında (`_handle_baslat`, `_handle_devam_et`) aktif kartların durumu denetleniyor.
*   **Akıllı UI**: Veri eksiği durumunda operatöre doğrudan eksik olan alanları listeleyip "Eski Karta Git" yönlendirmesi sağlayan dialog eklendi.

## Son Değişiklikler (2026-03-19) — Liste Görünümü & Refactoring
*   **Skeleton Yenileme**: Statik yükleme ekranı yerine, asıl kart yapısıyla (pill + grid) uyumlu, shimmer efektli modern bir skeleton yapısı (`CkSkeleton.vue`) getirildi.
*   **Bileşen Ayrıştırma**: `App.vue` dosyasındaki karmaşıklığı azaltmak için liste kartları (`CkCard.vue`) ve filtreleme/arama alanı (`CkFilters.vue`) ayrı bileşenlere taşındı. Dosya boyutu %50'den fazla azaltıldı.
*   **Görsel Hata Giderimi**: Badge kenarlarındaki zigzag maskesinin rendering hataları (1px'lik beyaz çizgiler) border temizliği ve overlap optimizasyonu ile giderildi.

## Son Değişiklikler (2026-03-15) — Kalite Statü Kilidi ve Senkronizasyonu
*   **Statü Restorasyonu**: QI belgesi "Rejected" -> "Accepted" olduğunda, kartın statüsü sadece onaylanmakla kalmaz, zaman kayıtlarına bakılarak (Çalışıyor/Hazır vb.) otomatik restore edilir.
*   **Source of Truth**: QI bağlandığı anda CK üzerindeki kalite butonları kilitlenir; statü sadece QI üzerinden yönetilir.
*   **Backend Koruması**: `qc.py` içinde QI linki olan kartlarda manuel statü güncellemesi frappe.throw ile engellendi.

## Son Değişiklikler (2026-03-14) — Alt Operasyon Başlık Seçimi
*   **Backend API**: `get_alt_operasyon_options` fonksiyonu ile sub-op'ların Title ve ID'leri çekiliyor.
*   **Prompt Güncellemesi**: `prompts.ts` içindeki alt operasyon alanı `Select` tipine çevrildi, başlık gösterimi sağlandı.
*   **Vue Entegrasyonu**: `AltOperasyonView.vue` bileşeni API ile beslenerek kullanıcı deneyimi iyileştirildi.

## Son Değişiklikler (2026-03-13) — Akıllı Vardiya Sonu Kapatma & Scheduler Düzeltmesi

Otomatik kart kapatma mantığı kullanıcı geri bildirimleri doğrultusunda revize edildi ve scheduler yapılandırması düzeltildi:

*   **Scheduler Cron Birleştirmesi**: `hooks.py` içinde ayrı satırlarda olan `16:15` ve `00:15` cron tanımları, Frappe'nin çakışma nedeniyle sadece birini çalıştırmasından dolayı `15 0,16 * * *` şeklinde tek satırda birleştirildi.
*   **Akıllı Bitiş Mantığı (Smart Shift-End)**: 
    *   **Duruşta Olan Kartlar**: Bitiş saati, kartın duruşa alındığı gerçek zaman (`durus_baslangic`) olarak set edilir.
    *   **Çalışıyor Olan Kartlar**: Bitiş saati, vardiyanın resmi bitiş saati (`16:00` veya `00:00`) olarak set edilir.
*   **Kümülatif Süre Sınırı**: 430 dakikalık net çalışma süresi sınırı, kart kapatıldıktan sonra `doc.update_durum()` üzerinden operatörün o vardiyadaki tüm işleri baz alınarak otomatik hesaplanmaya devam eder.
*   **Hata Giderme**: `TEST-KULLANICISI` üzerinden yapılan simülasyonlarla yeni mantık doğrulandı ve manuel tetikleme ile ucu açık kalan kayıtlar temizlendi.

## Son Değişiklikler (2026-03-11) — Kalite Kontrol (QI) Geliştirmeleri & Draft Akışı

Kalite kontrol süreci daha esnek ve güvenli bir yapıya kavuşturuldu:

*   **Numune Sayısı (sample_size)**: Kullanıcı artık şablondaki numune sayısını modal üzerinden belirleyebiliyor.
*   **Reddedildi QI Kaydı**: "Reddedildi" (Reject) işlemi yapıldığında da arka planda bir QI belgesi oluşturulması sağlandı. Bu sayede ret kararları da dökümante ediliyor.
*   **Draft & Auto-Submit**: QI belgeleri artık ilk aşamada **Draft** (docstatus=0) olarak kaydediliyor. Çalışma Kartı "Bitir" (Bitis) işlemine alındığında bağlı olan draft QI belgesi otomatik olarak **Submit** ediliyor (`cards.py:_handle_bitis` üzerinden).
*   **Manual Inspection Flag**: ERPNext'in otomatik durum hesaplamasının kullanıcı girdisini (Accepted/Rejected) ezmesini önlemek için `manual_inspection: 1` flag'i her reading satırı için zorunlu kılındı.
*   **Reading Alanları**: Numerik veriler için `reading_1`, metin veriler için `reading_value` ayrımı kesinleştirildi.
*   **QI Link Görünümü**: Kalite sekmesinde `quality_inspection` alanı doluysa doğrudan link ve "Görüntüle" butonu eklendi.

## Son Değişiklikler (2026-03-05) — Operasyon → Job Card Eşleştirme Sistemi

#### Yeni Child DocType: `KTA Operation ERPNext Mappings`
- `erpnext_operation` (Link → ERPNext Operation, zorunlu)
- `production_item` (Link → Item, isteğe bağlı) — dolu ise yalnızca o ürünün BOM'unda geçerlidir
- `KTA Calisma Karti Operasyonlari`'na parent olarak bağlı

#### KTA Calisma Karti Operasyonlari — Yeni Alan ve Autoname
- **`erpnext_operations` Table alanı** eklendi (`KTA Operation ERPNext Mappings` child tablosunu bağlar)
- **Koşullu `autoname()`:** `customer_group` doluysa `"Kablo Kesme-BOSCH"`, boşsa yalnızca `"Kablo Kesme"` ID’si üretir
- `autoname: "Prompt"`, `naming_rule: "Set by user"` Şklinde güncellendi

## Önemli Teknik Gelişmeler

### Vardiya Penceresi + Operatör Net Süre Limiti
- Aynı vardiyada birden fazla kart açan operatörlerin toplam süresini kontrol eden `hesapla_toplam_sure()` güncellemesi.
- `auto_close_timed_out_cards` ve `delete_old_unstarted_cards` cron job iyileştirmeleri.

### Hammadde Filtreleme — item-group Tabanlı Mimari
- BOM/Job Card bağımsızlığı: WO `required_items` ∩ operasyon `allowed_material_groups`.
- Alt operasyon bazlı hammadde kısıtları.

### Hurda Filtreleme Kapsamı Genişletildi
- Operatörün o anki operasyon sırasına (sequence) göre önceki tüm operasyonların malzemelerini görebilmesi.

### Makine Günlük Bakım Sistemi
- **Bakım Talimatı**: `Bakim Talimati` DocType'ı ile tanımlanan (örn: `PTR.BT.049`) standart talimatların operatöre gösterilmesi.
- **Bakım Onayı**: Operatörün kart üzerinde çalışırken ilgili makineyi (Asset) seçip talimata göre onay vermesi.
- **Bakım Formu**: `Makine Gunluk Bakim Formu` ile back-end tarafında submit edilen resmi kayıtlar oluşturulması.
- **UI Entegrasyonu**: `BakimView.vue` bileşeni ile kart detaylarında "Bakım" sekmesi.

### Test Masası Doğrulama Sistemi (Altyapı)
- **DocType**: `Test Masasi Dogrulama Kaydi` (PTR 07/005).
- **Mantık**: KTA Operasyonu üzerinde `board_dogrulamasi_gerektirir` işaretli ise, karta bir doğrulama kaydı (Bağlantı noktaları, kriterler vb.) bağlanması gerekir.
- **Durum**: Şu an için back-end tarafında referans bağı (`on_submit` / `after_insert`) aktiftir, ancak Vue SPA arayüzüne entegrasyonu (buton/sekme) henüz yapılmamıştır.

## Proje İçgörüleri
- `api.py` stable facade mantığı korunuyor.
- Realtime events (Socket.io) tüm CRUD işlemlerini kapsıyor.
- `view-calisma-karti` TypeScript + Composable mimarisiyle en modern bileşen.
