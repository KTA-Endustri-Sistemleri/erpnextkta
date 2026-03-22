# Progress — kta_calisma_karti

> Son güncelleme: 2026-03-19 (Liste Görünümü Modernizasyonu & Refactoring)

### Frontend Modernizasyon & Refactoring (2026-03-19 - Tamamlandı)
- [x] **Skeleton Güzelleştirme**: `CkSkeleton.vue` ile shimmer özellikli, kart yapısına uygun dinamik yükleme ekranı.
- [x] **App.vue Refactoring**: Liste sayfasının bileşenlere (`CkCard`, `CkFilters`, `CkSkeleton`) ayrıştırılması.
- [x] **Görsel Fix**: Badge zigzag maskesi rendering hatasının giderilmesi.
- [x] **Kod Temizliği**: Kullanılmayan stillerin ve mükerrer mantığın temizlenmesi.

### Notification / Bildirim Yapılandırması (Yeni - Tamamlandı)
- [x] `çalışma_kartı_oluşturuldu` sistem bildirimi aktifleştirildi.
- [x] Bildirimin alıcısı `operator` alanı üzerinden yapılandırıldı.
- [x] Bildirim başlığı ve içeriği daha açıklayıcı bir formata dönüştürüldü.
- [x] In-app system alert (Sistem Bildirimi) özelliği aktif edildi.

### Dashboard Charts (Tamamlandı)
- [x] Basic dashboard (Günlük durum ve Net Süre) - JSON & Source Script
- [x] `dashboard_chart_source` için 4 yeni metric geliştirilmesi
  - [x] Operasyon Başına Tamamlanan Miktar (Bar)
  - [x] Duruş Nedeni Dağılımı (Donut)
  - [x] Kalite Kontrol Dağılımı (Donut)
  - [x] Departman Bazlı Net Çalışma Süresi (Bar)
- [x] 6 Grafik için rol yetkileri eklendi (System, Dashboard, Manufacturing, Quality Manager)
- [x] "Çalışan Kart Sayısı" ve "Duruşta Olan Kartlar" isminde iki Number Card ve custom backend methodları sisteme eklendi
- [x] Workspace ve Dashboard entegrasyonları tamamlandı (Çalışma Kartı menüsünde listelenmesi sağlandı)

- [x] **Kalite Statü Kilidi ve Senkronizasyonu**: QI belgesi üzerinden statü kilidi, "Reddedildi" durumundan otomatik restorasyon (get_durum), backend linkage koruması ve UI kilitleri uygulandı. (Commit: `8d89a2b`)
- [x] **Kalite Kontrol (QI) Geliştirmeleri**: `sample_size` desteği, reddedilen kartlar için otomatik QI kaydı, numerik/metin ayrımı (`reading_1`/`reading_value`) ve `manual_inspection` senkronizasyonu. (Commit: `405746f`)
- [x] **QI Draft & Auto-Submit**: QI belgelerinin taslak olarak kaydedilmesi ve kart bitirildiğinde otomatik onaylanması. (Commit: `388719e`)
- [x] **QI UI İyileştirmeleri**: Kalite sekmesinde bağlı QI belgesine link ve route düzeltmeleri. (Commit: `cb904d7`)

### 🚀 Combined Enhancements Merge (Tamamlandı)
- [x] `calisma-karti-op-enhancements` ve `operation-jc-mapping` branşları `combined-op-jc-enhancements` altında birleştirildi.
- [x] **Makine Günlük Bakım**: `Bakim Talimati` ve `Makine Gunluk Bakim Formu` sistemi devreye alındı. (Alpkan tarafından geliştirildi)
- [x] Birleştirme sonrası `bench build` ve `bench migrate` hataları (JSON/CSS syntax errors) giderildi.
- [x] **QI Onay & Miktar Esnekliği (Bugfix)**: Operatör yetki sorunu (`set_user` ile) ve operasyon bazlı miktar sorgusu mantığı eklendi. (Commit: `-`)
- [x] **Arayüz İyileştirmeleri**: Alt operasyon seçiminin iyileştirilmesi (Tamamlandı).

### Next Steps / Pendings
- [ ] CK → Job Card status senkronizasyonu — `on_update` hook veya bitiş anında Job Card'ın ERPNext standart statüsünü (Completed vb.) tetikleme. (Hala tasarım aşamasında)
- [ ] Test coverage (Pytest & Jest) artırılması.

## Çalışan Özellikler

### Dashboard ✅
- [x] **`Calisma Karti` Chart Source** (`dashboard_chart_source/calisma_karti/`)
  - Günlük durum dağılımı bar chart (5 durum × N gün)
  - Filtreler: `days` (7-90), `operasyon` (Link), `is_istasyonu` (Link)
  - `frappe.form_dict` üzerinden filtre okuma (typing wrapper bypass)
- [x] **`Operator Net Sure` Chart Source** (`dashboard_chart_source/operator_net_sure/`)
  - Operatör bazlı net çalışma süresi bar chart (M:SS → dakika)
  - Filtreler: `days`, `is_istasyonu` (Link), `top_n` (5-20)
- [x] **Dashboard Fixture** — `kta_calisma_karti_dashboard/calisma_karti.json` (Full width, iki chart)
- [x] Chart JSON fixture'larında `currency` alanı kaldırıldı (TRY format sorunu)

### Backend ✅
- [x] Concurrency (Anti-Double-Click) Koruması — `create_calisma_karti()` 30 saniye geciktirmeli blokaj
- [x] Monolith Refactoring — `islem_yap` metodu parçalandı ve `cards.py` modülüne aktarıldı
- [x] KTA Calisma Karti Settings (Single Doctype) — Sistem limit süreleri (430 dk vb.) dinamikleştirildi
- [x] `Calisma Karti` DocType (ana + 5 child table)
- [x] Ana Operasyon (`KTA Calisma Karti Operasyonlari`) doctype'ina `sequence` alanı eklendi (Sıralama için)
- [x] `create_calisma_karti()` — WO/JC doğrulama + insert + realtime + departman tag
- [x] `get_my_calisma_kartlari()` — Rol bazlı liste (paginasyon + customer_group enrichment)
- [x] `get_calisma_karti_detail()` — Detay payload (tüm child table'lar)
- [x] `get_job_card_by_barcode()` — JC barkod arama + WO status kontrolü
- [x] `get_work_order_by_barcode()` — WO barkod arama
- [x] Hurda CRUD — BOM/operasyon bazlı item kısıtı dahil
- [x] Kalite kontrol güncelleme — permlevel bypass + rol kapısı
- [x] IDC ölçüm CRUD — item_group (120-IDC ve 110-Connector) + BOM scope filtresi; operatörler de girebilir (QC kısıtı kaldırıldı)
- [x] `yukseklik_mm` ve `cekme_n` opsiyonel (default 0, `reqd: 1` kaldırıldı)
- [x] Barkod kaydı CRUD
- [x] Alt operasyon CRUD
- [x] Alt operasyon realtime event (`publish_calisma_karti_changed` add/update/delete sonrası)
- [x] Alt operasyon detail API'sinde `alt_operasyon_title` + `alt_operasyon_sequence` enrichment
- [x] Alt operasyon seçimi için başlık (Title) desteği
  - `get_alt_operasyon_options(parent_operation)` API'si ile `{label, value}` çiftleri dönülüyor
  - Prompt ekranında `Select` alanına geçilerek kullanıcıya başlık seçtiriliyor
- [x] Alt operasyon hammadde için 2 katmanlı material group kısıtı
  - `KTA Operation Allowed Material Groups` child doctype (ana op)
  - `KTA Sub Operation Allowed Material Groups` child doctype (alt op)
  - `_get_allowed_groups_for_alt_op()` — sub-op → parent op → kısıtsız öncelik
  - `_assert_hammadde_allowed()` — backend validasyon
  - `search_allowed_hammadde_items` — whitelist search endpoint
  - `prompts.ts` hammadde field’ına `get_query` eklendi
- [x] Socket.IO realtime events (list + doc) — alt operasyon write'ları da artık kapsıyor
- [x] Kart Zaman Aşımı & Otomatik Kapatma (Katman 1 & 2)
  - `MAX_NET_CALISMA_DK = 430` sabitiyle raporlama kırpılması
  - `auto_close_timed_out_cards` cron job (her gün 16:15 ve 00:15)
- [x] Başlatılmamış Kartların Temizliği (Katman 2.5)
  - `delete_old_unstarted_cards` cron job (her gece 04:00'te) >1 günlük başlatılmamış kartları siler
- [x] Tekil Çalışma Kartı (Otomatik Duruş / Katman 4)
  - Operatör yeni kart başlattığında, daha önce açık bıraktığı diğer kartlar otomatik 'Diger' açıklamasıyla 'Duruş'a alınır (`_auto_pause_other_active_cards`)
- [x] Proaktif Uyarılama Sistemi (Katman 3 / Backend)
  - `validate()` hook'unda kart çalışması > 400 dk ise `frappe.msgprint` popup
- [x] Üretim Miktarı Girişinin Esnetilmesi
  - Ana operasyona `miktar_zorunlu_mu` (varsayılan: 1) alanı eklendi
  - Tikli değilse miktar 0 ile bitirilebilir (fakat en az bir alt operasyon zorunlu)
  - UI Duruş ve Bitiş formu `tamamlanan_miktar` field'ı opsiyonel (`reqd: 0`) yapıldı
- [x] Hurda Filtreleme Kapsamının Genişletilmesi  
  - Filtreleme mekanizması, aktif operasyonun `KTA Calisma Karti Operasyonlari` tanımındaki `sequence` (sıra) değerini baz alacak şekilde güncellendi.
  - Sadece mevcut operasyon değil; bu sıraya eşit veya kendinden önceki (`sequence <= mevcut`) **tüm ana operasyonlar** ve bunlara bağlı **tüm alt operasyonların** materyalleri (Item Group'ları) serbest bırakıldı.
- [x] Hammadde Filtreleme — item-group Tabanlı Mimari (Commit: `dcd1b05` + `b769ea3`)
  - `get_allowed_items_with_groups(calisma_karti_name, alt_operasyon=None)` merkezi yardımcı fonksiyon `_helpers.py`'e eklendi
  - BOM/Job Card bağlantısından tamamen bağımsız: WO `required_items` ∩ operasyon `allowed_material_groups` ı filtreler
  - Alt-op kendi grubu tanımlıysa YALNIZCA o grup; boşsa sequence cözümlemesi ile önceki alt-op'lar + parent op birleştirilir
  - `hurda.py` tüm eski BOM SQL bloğunu bıraktı; `_assert_hurda_item_allowed_for_operation` + `search_allowed_hurda_items` yeni yardımcıyı kullanıyor
  - `alt_operasyon.py`: `_assert_hammadde_allowed` imzası `(calisma_karti, hammadde, alt_operasyon)` olarak güncellendi; `search_allowed_hammadde_items` `calisma_karti` filtresi eklendi
- [x] Zaman Aşımı Duruş Nedeni (Commit: `37848be`)
  - `operasyon_duruslari.json` dış sekmesine `"Zaman Aşımı"` sekmesi eklendi
  - Otomatik kapama cron'u bu nedeni kullanıyor (sıfır süreli bilgi kaydı olarak)
- [x] Vardiya Penceresi + Operatör Net Süre Limiti (Commit: `35bd322`)
  - `_shift_name_by_now`, `_shift_window`, `_parse_minsec`, `_other_cards_net_seconds_in_shift` `calisma_karti.py`'e eklendi
  - `hesapla_toplam_sure()` artık vardiya penceresindeki diğer kartların toplam süresini hesaba katan kapasiteye göre kırpar
- [x] **Smart Vardiya Sonu Kapatma & Scheduler Düzeltmesi (2026-03-13)**
  - `hooks.py`: Cron çakışması giderildi (`15 0,16 * * *` birleştirildi).
  - `tasks.py`: `auto_close_timed_out_cards` revize edildi. Duruşta olanlar "duruş anında", çalışıyor olanlar "vardiya sonunda" kapatılacak şekilde akıllandırıldı.
  - Testler `TEST-KULLANICISI` üzerinden doğrulandı.
- [x] `delete_old_unstarted_cards`: `docstatus=["!=", 2]` yapılarak draft/iptal ayrımı düzeltildi
- [x] Vardiya Net Süre Simülasyonu ve Düzeltmeler (Bugfix)
  - Tüm net süre hesaplamaları (`_other_cards_net_seconds_in_shift`, `auto_close_timed_out_cards`) `docstatus=1` yerine `["!=", 2]` (Draft kartları da kapsayacak) şekilde düzeltildi
  - DB'ye dokunmayan analiz scripti yazıldı (`vardiya_sim.py`)
  - Zamanaşımı kapatma scripti eklendi (`cleanup_timed_out.py`)
  - Eski aşırı değerli kartları düzeltme scripti yazıldı (`fix_closed_cards_net_time.py`)
- [x] Operasyon → Job Card Eşleştirme Sistemi
  - **Yeni child doctype** `KTA Operation ERPNext Mappings`: `erpnext_operation` (zorunlu) + `production_item` (isteğe bağlı)
  - `KTA Calisma Karti Operasyonlari`'na `erpnext_operations` Table alanı eklendi
  - Koşullu `autoname()`: `customer_group` doluysa `Op-CG`, boşsa yalnızca `Op` ID'şi
  - `get_operations_for_job_card(job_card)` — JC'nin `operation` + `production_item`'a göre üçlü öncelik filtresi
    - Prio-1: operation + product tam eşleşmesi (BOM-spec)
    - Prio-2: operation eşleşmesi + boş product (operation-generic)
    - Prio-3: hiç mapping yok (fully generic fallback)

### Frontend ✅
- [x] Server-Side Filtering & Initialization Fixes — `list-calisma-cards` sayfasındaki ağır Vue array filtrelemeleri SQL API'ye bağlandı.
- [x] Resolve "Onaylı" (docstatus=1) validation error.
- [x] Fix "Not allowed to change after submission" error (Allow on Submit metadata + Backend bypass flags).
- [x] Fix `net_calisma_suresi` calculation bug during active stops.
- [x] `create-calisma-karti` wizard — WO modu (5 adım) + JC modu (3 adım)
- [x] `list-calisma-cards` — Realtime list, çok filtreli (durum, QC, customer group), paginasyon
- [x] `view-calisma-karti` — Tab'lı detay (Info, Alt Operasyon, Hurda, Duruş, Kalite)
- [x] `AltOperasyonView.vue` ve `HurdaView.vue` — Kart "Hazır" veya "Bitmiş" durumdayken Ekle butonlarının iptali
- [x] `AltOperasyonView.vue` — `sortedRows` computed (sequence sırası), `alt_operasyon_title` fallback gösterimi
- [x] `App.vue` Timeout Banner (Katman 3 / UI) — İşlem uyarı süresini aşarsa tepeye kırmızı 🚨 alert banner açılır (**dinamik**: `kart_uyari_suresi_dk` KTA Settings'ten okunur)
- [x] `prompts.ts` `altOperasyonFields` — `calismaKartiName` + `getAltOpValue` callback eklendi; hammadde `get_query` `calisma_karti` filtresi gönderiyor
- [x] `AltOperasyonView.vue` dialog referansı (`let d`) — `getAltOpValue` callback'ine aktarılıyor
- [x] `create-calisma-karti` wizard operasyon adımı JC bazlıya geçirildi
  - `fetchOperations()` kaldırıldı; `fetchOperationsForJobCard(jcName)` yeni API'yi çağırıyor
  - JC ve WO modlarında JC seçimi/belirlenmesi sonrası operasyon listesi otomatik çekiliyor

## Eksik / Belirsiz

### Bilinmeyenler 🔍
- [x] ~~`callIslem` backend metodu~~ → `calisma_karti.islem_yap` whitelisted fonksiyonu (`calisma_karti.py`'de)
- [x] ~~`calisma_karti.py` controller~~ → `STATU_HARITASI`, `get_durum()`, `hesapla_*` metodları, `islem_yap` okundu
- [x] ~~`tamamlanan_miktar`~~ → `islem_yap` içinde `doc.tamamlanan_miktar` olarak kullanılıyor (Custom Field)
- [ ] CK → Job Card status senkronizasyonu — `on_update` hook Job Card'ı güncellemiyor; sadece `doc_events → Job Card → update_work_order_status` var

### Potansiyel İyileştirmeler
- [ ] Liste sayfasındaki filtreler server-side hale getirilebilir (şu an client-side)
- [ ] `customer_group` hesabı her listede `Item Customer Detail` join yapıyor — cache eklenebilir
- [ ] Test coverage yok
- [ ] **Test Masası Doğrulama Entegrasyonu**: `board_dogrulamasi_gerektirir` kontrolünün Vue SPA tarafında UI ve doğrulama olarak gerçeklenmesi (Faz 2).
### Karar Verilmiş / Gerekmiyor
- ✅ `create-calisma-karti` wizard'a alt operasyon adımı eklenMEyecek (operatör CK içinden kendi dolduruyor)
- ✅ `list-calisma-cards`'ta alt operasyon özeti gösterilMEyecek (şu an için gerek yok)
- ✅ Material group kısıtı ana operasyonda tanımlir; alt op isteðe bağlı daraltabilir

## Bilinen Sorunlar

Şu an rapor edilen aktif bir bug yok.

## Proje Kararlarının Evrimi

| Tarih | Karar | Gerekçe |
|-------|-------|---------|
| — | `api.py` stable facade | Frontend method string'leri kırılmasın diye |
| — | Hurda'ya BOM/operasyon kısıtı eklendi | Operatör yanlış malzeme giriyordu |
| — | `create-calisma-karti`'ye JC modu eklendi | WO bilinmediğinde JC barkodu ile kısayol |
| — | `view-calisma-karti` TypeScript'e geçirildi | type safety ve composable mimarisi |
| — | Customer group filtreleme eklendi | Farklı müşterilerin kartlarını ayırt etmek için |
| 2026-03-02 | Zaman aşımı kontrolü (`MAX_NET_CALISMA_DK=430`) sağlandı | Kartlar açık unutulduğunda raporların ve süre hesabının bozulmasını önlemek |
| 2026-03-02 | Cron job bazlı otomatik kart iptali / temizliği kodu yazıldı | Operatör hatalarını (unutulan/hiç başlatılmayan kartları) manuel yerine arka planda otonom onarmak |
| 2026-03-02–2026-03-04 | Hammadde filtreleme BOM/JC bağlantısından çıkarıldı; `get_allowed_items_with_groups` (WO + item-group) mantığına geçildi | BOM operasyon etiketleri tutarsız; item-group tabanlı konfigurasyon daha esnek |
| 2026-03-04 | Vardiya penceresi bazlı operatör net süre biçimlendi | Aynı vardiyada birden fazla kart açan operatörlerin toplam süresi kontrol altına alındı |
| 2026-03-04 | `kart_uyari_suresi_dk` ve `max_kart_suresi_dk` backend'den frontend'e aktarıldı | Sabit hard-code banner metninin yerini dinamik ayar aldı |
