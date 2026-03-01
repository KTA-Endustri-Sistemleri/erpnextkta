# Progress — kta_calisma_karti

> Son güncelleme: 2026-03-02

## Çalışan Özellikler

### Backend ✅
- [x] `Calisma Karti` DocType (ana + 5 child table)
- [x] `create_calisma_karti()` — WO/JC doğrulama + insert + realtime + departman tag
- [x] `get_my_calisma_kartlari()` — Rol bazlı liste (paginasyon + customer_group enrichment)
- [x] `get_calisma_karti_detail()` — Detay payload (tüm child table'lar)
- [x] `get_job_card_by_barcode()` — JC barkod arama + WO status kontrolü
- [x] `get_work_order_by_barcode()` — WO barkod arama
- [x] Hurda CRUD — BOM/operasyon bazlı item kısıtı dahil
- [x] QC güncelleme — permlevel bypass + rol kapısı
- [x] IDC ölçüm CRUD — item_group + BOM scope filtresi
- [x] Barkod kaydı CRUD
- [x] Alt operasyon CRUD
- [x] Socket.IO realtime events (list + doc)

### Frontend ✅
- [x] `create-calisma-karti` wizard — WO modu (5 adım) + JC modu (3 adım)
- [x] `list-calisma-cards` — Realtime list, çok filtreli (durum, QC, customer group), paginasyon
- [x] `view-calisma-karti` — Tab'lı detay (Info, Alt Operasyon, Hurda, Duruş, Kalite)

## Eksik / Belirsiz

### Bilinmeyenler 🔍
- [ ] `callIslem("Baslat" | "Durus" | "Bitis")` — `useCalismaKarti.ts` içindeki backend metodu tam okunmadı
- [ ] `calisma_karti.py` controller — `STATU_HARITASI`, `get_durum()`, `qc_on_submit` hook
- [ ] `tamamlanan_miktar` alanı — DocType JSON'da yok; Custom Field olabilir
- [ ] CK → Job Card status senkronizasyonu — `on_update/on_submit` hook var mı?
- [ ] `rest-api/` klasörü — Tam içerik incelenmedi

### Potansiyel İyileştirmeler
- [ ] Liste sayfasındaki filtreler server-side hale getirilebilir (şu an client-side)
- [ ] `customer_group` hesabı her listede `Item Customer Detail` join yapıyor — cache eklenebilir
- [ ] Test coverage yok

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
