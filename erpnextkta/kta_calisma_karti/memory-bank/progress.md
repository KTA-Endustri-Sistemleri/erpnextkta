# Progress — kta_calisma_karti

> Son güncelleme: 2026-03-02 (alt operasyon geliştirme)

## Çalışan Özellikler

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
- [x] IDC ölçüm CRUD — item_group + BOM scope filtresi; operatörler de girebilir (QC kısıtı kaldırıldı)
- [x] `yukseklik_mm` ve `cekme_n` opsiyonel (default 0, `reqd: 1` kaldırıldı)
- [x] Barkod kaydı CRUD
- [x] Alt operasyon CRUD
- [x] Alt operasyon realtime event (`publish_calisma_karti_changed` add/update/delete sonrası)
- [x] Alt operasyon detail API'sinde `alt_operasyon_title` + `alt_operasyon_sequence` enrichment
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
  - `hurda.py` içerisindeki filtreleme operatörün o an bulunduğu `BOM Operation`'ın `idx` (sıra) değerini baz alacak şekilde güncellendi
  - Sadece mevcut operasyon değil, kendinden önceki (idx <= mevcut idx) tüm operasyonların materyalleri serbest bırakıldı

### Frontend ✅
- [x] Server-Side Filtering & Initialization Fixes — `list-calisma-cards` sayfasındaki ağır Vue array filtrelemeleri SQL API'ye bağlandı. Reaktif değişken başlatma (TDZ) ve şablon hataları giderildi.
- [x] Resolve "Onaylı" (docstatus=1) validation error (Submittable DocType + doc.submit())
- [x] Fix "Not allowed to change after submission" error (Allow on Submit metadata)
- [x] `create-calisma-karti` wizard — WO modu (5 adım) + JC modu (3 adım)
- [x] `list-calisma-cards` — Realtime list, çok filtreli (durum, QC, customer group), paginasyon
- [x] `view-calisma-karti` — Tab'lı detay (Info, Alt Operasyon, Hurda, Duruş, Kalite)
- [x] `AltOperasyonView.vue` — `sortedRows` computed (sequence sırası), `alt_operasyon_title` fallback gösterimi
- [x] `App.vue` Timeout Banner (Katman 3 / UI) — İşlem 400 dk'yi aşarsa tepeye kırmızı 🚨 alert banner açılır

## Eksik / Belirsiz

### Bilinmeyenler 🔍
- [x] ~~`callIslem` backend metodu~~ → `calisma_karti.islem_yap` whitelisted fonksiyonu (`calisma_karti.py`'de)
- [x] ~~`calisma_karti.py` controller~~ → `STATU_HARITASI`, `get_durum()`, `hesapla_*` metodları, `islem_yap` okundu
- [x] ~~`tamamlanan_miktar`~~ → `islem_yap` içinde `doc.tamamlanan_miktar` olarak kullanılıyor (Custom Field)
- [ ] CK → Job Card status senkronizasyonu — `on_update` hook Job Card'ı güncellemiyor; sadece `doc_events → Job Card → update_work_order_status` var
- [ ] `rest-api/` klasörü — Tam içerik incelenmedi

### Potansiyel İyileştirmeler
- [ ] Liste sayfasındaki filtreler server-side hale getirilebilir (şu an client-side)
- [ ] `customer_group` hesabı her listede `Item Customer Detail` join yapıyor — cache eklenebilir
- [ ] Test coverage yok
### Karar Verilmiş / Gerekmiyor
- ✅ `create-calisma-karti` wizard'a alt operasyon adımı eklenMEyecek (operatör CK içinden kendi dolduruyor)
- ✅ `list-calisma-cards`'ta alt operasyon özeti gösterilMEyecek (şu an için gerek yok)
- ✅ Material group kısıtı ana operasyonda tanımlanır; alt op isteðe bağlı daraltabilir

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
