# Progress — kta_calisma_karti

> Son güncelleme: 2026-03-02 (alt operasyon geliştirme)

## Çalışan Özellikler

### Backend ✅
- [x] `Calisma Karti` DocType (ana + 5 child table)
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

### Frontend ✅
- [x] `create-calisma-karti` wizard — WO modu (5 adım) + JC modu (3 adım)
- [x] `list-calisma-cards` — Realtime list, çok filtreli (durum, QC, customer group), paginasyon
- [x] `view-calisma-karti` — Tab'lı detay (Info, Alt Operasyon, Hurda, Duruş, Kalite)
- [x] `AltOperasyonView.vue` — `sortedRows` computed (sequence sırası), `alt_operasyon_title` fallback gösterimi

## Eksik / Belirsiz

### Bilinmeyenler 🔍
- [x] ~~`callIslem` backend metodu~~ → `calisma_karti.islem_yap` whitelisted fonksiyonu (`calisma_karti.py`'de)
- [x] ~~`calisma_karti.py` controller~~ → `STATU_HARITASI`, `get_durum()`, `hesapla_*` metodları, `islem_yap` okundu
- [x] ~~`tamamlanan_miktar`~~ → `islem_yap` içinde `doc.tamamlanan_miktar` olarak kullanılıyor (Custom Field)
- [ ] CK → Job Card status senkronizasyonu — `on_update` hook Job Card'ı güncellemiyor; sadece `doc_events → Job Card → update_work_order_status` var
- [ ] `rest-api/` klasörü — Tam içerik incelenmedi

### Potansiyel İyileştirmeler
- [ ] **Alt operasyon — `hammadde` için BOM kısıtı** (henüz tasarlanmadı)
  - Hurda gibi BOM + operasyon bazlı `Item` whitelist olmalı, ama hangi BOM'dan ve hangi filtre ile alınacağı netleştirilmeli
  - Şu an serbest `Item` seçimi var
- [ ] `rest-api/` klasörü — Tam içerik incelenmedi

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
