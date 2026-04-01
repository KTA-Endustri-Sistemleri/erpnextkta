# Active Context — kta_calisma_karti

> Son güncelleme: 2026-03-31

Çalışma Kartı modülü Frappe-native document state mimarisine taşındı. "Draft-First" (Önce Taslak) yaratım akışı, iptal edilmiş belge desteği ve detaylı yetkilendirme güncellemeleri tamamlandı. Ayrıca toplu build işlemleriyle frontend-backend veri tutarlılığı sağlandı.

- [x] **Draft-First Lifecycle**: Yeni kartlar artık "Taslak" (docstatus=0) olarak açılıyor ve sadece "Bitir" anında otomatik submit ediliyor. (Tamamlandı)
- [x] **Native Document States**: Hazır, Çalışıyor, Duruşta, Bitmiş, Reddedildi durumları Frappe standart statüleri olarak sisteme işlendi. (Tamamlandı)
- [x] **Cancelled Status Display**: `docstatus=2` (İptal Edildi) olan kartların hem list-view hem de view-calisma-karti SPA'larında doğru (Gri) ve yüksek öncelikli gösterilmesi sağlandı. (Tamamlandı)
- [x] **Theme-Aware UI Sync**: "İptal Edildi" durumu için cam tasarımı (Glassmorphism) Açık/Koyu tema değişkenleri eklendi. (Tamamlandı)
- [x] **API Veri Tutarlılığı**: `get_calisma_karti_detail` ve `get_my_calisma_kartlari` API'lerine `docstatus` alanı eklenerek frontend belirsizliği giderildi. (Tamamlandı)
- [x] **Yetki Güncellemesi**: `Asset Maintenance Log` DocType'ı için standart operatör ve yönetici rollerine okuma yetkisi tanımlandı. (Tamamlandı)
- [ ] **Test Masası Entegrasyonu**: Arayüz tarafındaki eksiklerin giderilmesi (Planlanıyor).
- [ ] **Statü Senkronizasyonu**: CK → Job Card statü akışının tasarımı (Beklemede).

## Son Değişiklikler (2026-04-01) — Güvenlik ve Mantık Denetimi (Logic Audit) Tamamlandı
Çalışma Kartı modülünde tespit edilen asenkron sızıntılar, yarış durumları (race conditions) ve yetki/durum atlama (state bypass) zafiyetlerine karşı geniş çaplı bir güvenlik denetimi gerçekleştirildi. Zafiyetler başarıyla kapatıldı ve dinamik yetki yönetimi eklendi:

*   **Zafiyet 1 — Vue State Leakage (Kritik - Çözüldü)**: `App.vue` üzerindeki Kalite onayı (QC) gecikmesinde kart uyuşmazlığı yaşanması Reactivity Context Lock deseniyle engellendi. İstek esnasında kart isimleri `currentDocname` ile donduruldu.
*   **Zafiyet 2 — Race Conditions (Çözüldü)**: Kritik state değiştiren (`islem_yap`) ve child-table yazan backend API'lerine `for_update=True` pesimistik veritabanı kilidi uygulandı. Eş zamanlı isteklerin (Double Submit) birbirini ezmesi ve Miktar Kayıpları engellendi.
*   **Zafiyet 3 — State Bypass & Dinamik Otorizasyon (Çözüldü)**: 
    * Tüm arka uç API'leri `docstatus` ve `durum` kontrollerini giriş anında doğrulayacak şekilde katılaştırıldı. İptal edilmiş kartlara `System Manager` bile müdahale edemez.
    * Hardcoded yönetici rolleri yerine, `KTA Calisma Karti Settings` paneline **Admin Kontrol Rolleri (`admin_roles`)** ayarı eklendi. (Varsayılan: `System Manager, Quality Manager, Manufacturing Manager`)
    * Seçili `admin_roles` yetkisine sahip kişiler "Bitmiş" veya "Reddedilmiş" kartların içindeki verileri güncelleyebilirken, normal operatörler sadece aktif kartlarda çalışabilir.
*   **Frontend UI Gizliliği**: İptal veya bitmiş kartlarda yetkisi olmayan operatörler için veri düzenleme butonları (Ekle/Sil/Düzenle) `frappe.boot.kta_admin_roles` array'ini dinleyen `canEditData` state'i aracılığıyla SPA üzerinden de tamamen gizlendi.
*   **Zafiyet 4 — Operasyonel Üretim Fazlası Kısıtları**: Beklemede (Gelecek iterasyonda işlenecektir).

## Son Değişiklikler (2026-03-31) — Vardiya Sınır Değeri Hesaplama Hatası Düzeltmesi
*   **Bug Fix — `_shift_name_by_now` Boundary Condition**: `_shift_name_by_now()` fonksiyonundaki vardiya sınır koşulları `[start, end)` yerine `(start, end]` olarak değiştirildi. Sınır zamanları (16:00, 00:00, 08:00) artık **biten vardiyaya** aittir.
*   **Kök Neden**: `auto_close_timed_out_cards` cron job'ı kartları tam sınır saatinde (örn. `16:00:00`) kapattığında, eski mantık bu zamanı bir sonraki vardiyaya atıyordu. Bu durumda `_other_cards_net_seconds_in_shift` yanlış vardiya penceresine bakarak `other_net=0` döndürüyor ve 430 dk limiti uygulanmıyordu.
*   **Etki**: 12 vardiya aşımı, 10 operatör, 27 kart etkilenmiş. En büyük aşım: +45 dk (475→430).
*   **Migration Patch**: `erpnextkta.patches.v0_20.fix_shift_boundary_net_times` — `bench migrate` sırasında etkilenen kartları kronolojik sırayla `update_durum()` ile yeniden hesaplatır.
*   **Branch**: `fix/shift-boundary-net-time-calculation`

## Son Değişiklikler (2026-03-26) — Hurda Modülü Modernizasyonu & 1:1 Senkronizasyon
*   **Operatör Bazlı Mimari (1:1)**: Her `Calisma Karti`'nin kendine ait bir `Stock Entry` (Scrap for Manufacturing) belgesi olması sağlandı. İş Emri bazlı konsolidasyon yerine operatör/kart bazlı izlenebilirlik önceliklendirildi.
*   **Çift Yönlü Eşzamanlılık (Bidirectional)**:
    *   **SPA/Desk → SE**: Kart üzerinden (vue veya desk formu) yapılan ekleme, silme ve miktar güncellemeleri bağlı SE'ye anında yansıtılır.
    *   **SE → Kart**: Stok Belgesi üzerinden manuel satır silme veya düzenleme işlemleri karta geri yansıtılır. `syncing_hurda_from_se` flag'i ile döngü koruması sağlandı.
*   **Onay Sonrası Revizyon Desteği**: `on_update_after_submit` eklenerek, Çalışma Kartı onaylandığında dahi hurda değişikliklerinin senkronize kalması sağlandı.
*   **Veri Bütünlüğü Koruması**: ERPNext'in `validate()` sırasında `work_order` alanını temizlemesini önlemek için, her kayıt sonrası `frappe.db.set_value` ile İş Emri bilgisi doğrudan DB'ye zorla (force) yazılır.
*   **Arayüz İyileştirmeleri (CkHurdaModal)**:
    *   `frappe.prompt` yerine modern Vue bileşeni tasarlandı ve `Teleport` ile body'ye taşınarak katman (z-index) çakışmaları giderildi.
    *   **Pill (Chip) Seçimi**: Hurda nedeni seçimi için dropdown yerine interaktif tıklanabilir piller (chips) eklendi.
    *   **Dikey Sığma (Vertical Fit)**: Küçük ekranlarda modalın alt kısmının kesilmemesi için `max-height: 92vh` ve dahili `overflow-y: auto` (flex-body) yapısı kuruldu.
    *   **Silme Hatası Giderimi**: Son hurda silinirken oluşan "Document Modified" hatası, `on_stock_entry_trash` hook'unda `update_modified=False` kullanılarak ve redundant save'ler temizlenerek giderildi.
    *   İş Emri verileriyle (Depo, Birim) otomatik dolum mantığı korundu.

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
- **⚠️ Boundary Pattern**: `_shift_name_by_now()` (start, end] mantığı kullanır — sınır zamanı biten vardiyaya aittir. Kesinlikle `[start, end)` yapılmamalıdır.

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
