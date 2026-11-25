# Faz 2 Tasarım Dokümanı: İki Sekmeli Vue 3 + TypeScript Sayım Merkezi (`stock-reco-dashboard`)

**Tarih:** 2026-11-21  
**Durum:** Implemented — Kalite Kapısı Doğrulandı (`stock-reco-dashboard` & `stock_reconciliation_service`)  
**Faz:** 2 / 3  
**Önkoşul:** Faz 1 ([Faz 1 Spec](./2026-11-21-faz1-kta-stock-relabeling-core-design.md)) tamamlanmış olmalı (`kta_stock/services/` ve `relabeling_service.py`).  
**Kapsam:** `erpnextkta/kta_stock/services/stock_reconciliation_service.py`, `erpnextkta/kta_stock/page/stock_reco_dashboard/**`, `erpnextkta/public/stock-reco-dashboard/**`, `erpnextkta/public/js/stock_reconciliation.js`

---

## 3 Fazlı Program Yol Haritası

| Faz | Konu | Spec | Plan |
|---|---|---|---|
| **Faz 1** | `kta_stock` Çekirdek Etiket/Parti Motoru & `rest-api` Taşıması | [Faz 1 Spec](./2026-11-21-faz1-kta-stock-relabeling-core-design.md) | [Faz 1 Plan](../plans/2026-11-21-faz1-kta-stock-relabeling-core.md) |
| **Faz 2 (Bu Doküman)** | İki Sekmeli Vue 3 + TypeScript Sayım Merkezi (`stock-reco-dashboard`) | `2026-11-21-faz2-stock-reco-hub-vue-ts-design.md` | [Faz 2 Plan](../plans/2026-11-21-faz2-stock-reco-hub-vue-ts.md) |
| **Faz 3** | `Shopfloor Hub` Üretim Tedarik Alanından İade & İsteğe Bağlı Koli Bölme + Dokümantasyon | [Faz 3 Spec](./2026-11-21-faz3-shopfloor-supply-return-and-split-design.md) | [Faz 3 Plan](../plans/2026-11-21-faz3-shopfloor-supply-return-and-split.md) |

---

## 1. Amaç ve Kapsam

### Neden İki Sekmeli Tek Sayfa?
1. Mevcut `stock-reco-dashboard` ([App.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/stock-reco-dashboard/App.vue)) 1.266 satırlık tek bir tiplenmemiş JS bileşenidir ve yalnızca sayım sonrası fark/anomali izleme yapar; depo ekibinin sayım fişi açıp raftaki kutulara göre yeniden etiketleme (`Mod 1 / Mod 2`), kutu bölme (`5.000 + 2.750`) ve `LEGACY` standartlaştırması yapabileceği bir operasyon ekranı yoktur.
2. Tüm sayım operasyonlarını (toplu sayım oluşturma + sayım fişi üzerinden yeniden etiketleme + fark ve anomali analizi) `shopfloor-hub` mimarisiyle uyumlu **modüler Vue 3 + TypeScript** bir merkezde toplamak, masaüstü form kalabalığını önler ve depo ekibine tek ekran sunar.

### Hedefler, Hedef Dışı ve Anti-Hedefler
- **Hedefler:**
  - Sayım gününde kullanılabilecek **Mod 1 (Fiziksel Kutu Esas — Sadece Eksik / Değişen / `LEGACY`)** ve **Mod 2 (Sistem Partisi Esas — Tüm Pozitif Stoklar)** seçeneklerini sunmak.
  - Eski `LEGACY-...` veya partisiz satırları `7 hane Lot + 0001..N` KTA kutu yapısına dönüştürüp hem ERPNext stokunu hem `KTA Stock Label` kayıtlarını temizlemek.
  - Mevcut canlı Socket.IO Fark & Anomali Analizi sekmesinin tüm özelliklerini kayıpsız korumak, Açık/Koyu tema (`[data-theme="dark"]`) ve TR/EN/DE çeviri desteği kazandırmak.
- **Anti-Hedefler:**
  - Taslak (`Draft`) bir sayım fişinde belge onaylanmadan (submit öncesi) rafta var olup olmadığı kesinleşmemiş etiketleri basmak (Taslak fişte yalnızca **Onayla ve Etiketleri Bas** akışıyla baskı alınır).
  - Sayım kilidi (`stock_reconciliation_lock`) yüzünden onaylı sayım fişi üzerinde sistem tarafından başlatılan `Package Split` düzeltmesinin kendi kendini kilitlemesi.
  - 500 satırı aşan monolitik Vue dosyaları bırakmak.

---

## 2. Mimari ve İş Akışları

### 2.1 İki Sekmeli Sayfa Yapısı (`stock-reco-dashboard`)

```
+-------------------------------------------------------------------------+
| KTA Sayım ve Etiket Merkezi                       [+ Toplu Sayım Aç]   |
| [ 📦 Sayım Operasyonları & Etiketleme ]  [ 📊 Fark & Anomali Analizi ]  |
+-------------------------------------------------------------------------+
```

#### Sekme 1 — Sayım Operasyonları ve Etiketleme
1. **Toplu Sayım Fişi Oluştur (`BulkCreateRecoModal.vue`):**
   - Depo grubu (`is_group = 1`), tarih/saat ve `Boş Stokları Yoksay` seçimi ile `create_stock_reco_docs_for_warehouse_group` arka plan görevini tetikler (önceden `stock_reconciliation.js` içinde olan diyalog bu modala taşınır).
2. **Sayım Belgeleri Listesi (`RecoDocumentsList.vue`):**
   - Durum filtresi (`Tümü / Taslak / Onaylı`), depo/belge arama ve tarih filtresi.
   - Her satırda belge no, `set_warehouse`, durum rozeti (`Taslak / Onaylı`), etiket sağlık özeti (`Örn. 14/20 Uyumlu • 3 Eksik • 2 Değişen • 1 LEGACY`) gösterilir.
3. **Belge Etiketleme ve Koli Standartlaştırma Çalışma Alanı (`RecoLabelingWorkspace.vue`):**
   - Seçilen `Stock Reconciliation` belgesinin satırlarını v15 uyumlu şekilde okur (**Taslak:** `row.batch_no` / bundle, **Onaylı:** `row.serial_and_batch_bundle` → `Serial and Batch Entry` içindeki her parti satırı).
   - Her satır için etiket durumu hesaplanır:
     - `valid`: Aktif `Depo Giriş Etiketi` var, standart `7+4` yapısında ve `label.qty == row.qty`.
     - `qty_changed`: Etiket var ama `label.qty != row.qty` *(açık kutu/makara)*.
     - `missing_label`: Standart `7+4` partinin `KTA Stock Label` kaydı yok *(etiketi yıpranmış veya sayım fazlası)*.
     - `legacy_batch`: Parti `LEGACY-...` formatında veya boş (`None`).
   - **İki Hazır Seçim Modu (Tek Tıkla Geçiş):**
     - **Mod 1 — Fiziksel Kutu Esas (Eksik / Değişen / LEGACY):** Yalnızca `qty > 0` olan `qty_changed`, `missing_label`, `legacy_batch` satırlarını otomatik seçer; etiketi sağlam kapalı kutuları (`valid`) atlar.
     - **Mod 2 — Sistem Partisi Esas (Tüm Pozitif Stoklar):** Belgedeki `qty > 0` olan tüm satırları seçer; rafın tamamı yeni etiketlenir.
   - **Satır İçi Kutu Kırılımı (`box_splits`):**
     - Kullanıcı seçtiği bir satırı raftaki fiziksel duruma göre bölebilir (ör. tek satırdaki `7.750` miktarı `5.000 + 2.750` şeklinde iki kutuya ayırma).
     - `Toplam == row.qty` kontrolü anlık doğrulanır; eşit değilse işlem butonu kilitlenir.
   - **Duruma Göre İki Temiz Uygulama Yolu:**
     - **Belge `Taslak (docstatus = 0)` ise — Buton: `Onayla ve Etiketleri Bas` (`submit_and_print_stock_reconciliation`):**
       1. Satır genişletme kuralı (ERPNext v15 batch uzlaştırması eski partiyi çiftlememesi için kritik):
          - **`LEGACY` veya partisiz dönüşüm (`convert_legacy = 1`):** Eğer eski `source_batch` üzerinde sistemde bakiye (`current_qty > 0`) varsa, eski partiyi sıfırlamak için fiş içinde explicit sıfırlama satırı (`batch_no = source_batch, qty = 0, use_serial_batch_fields = 1`) korunur; ardından yeni 7 haneli lot (`generate_new_base_lot`) ve `allocate_next_box_batches` ile üretilen `{base_lot}0001..N` satırları kaynak satırın `valuation_rate` değeri (boşsa `current_valuation_rate`) kopyalanarak eklenir. (`source_batch` yoksa doğrudan yeni `{base_lot}0001..N` satırları yazılır.)
          - **Zaten standart `7+4` olan kutuda çoklu kırılım (`len(box_splits) >= 2`, ör. `[5000, 2750]`):** Mevcut `source_batch` satırı ilk kutu (`box_splits[0] = 5000`) ile yerinde bırakılır; kalan kutular (`box_splits[1:] = [2750]`) için aynı 7 haneli lottan sıradaki `allocate_next_box_batches` (`{base_lot}{seq:04d}`) satırları `valuation_rate` kopyalanarak eklenir.
       2. Sayım fişi onaylanır (`doc.submit()`).
       3. Seçilen satırların `KTA Stock Label` kayıtları `upsert_box_label` ile oluşturulur/güncellenir, sıfırlanan `LEGACY` partilerin eski etiketleri `clear_empty_labels` ile silinir ve seçilen etiketler Zebra'ya toplu (`send_batch`) gönderilir.
     - **Belge `Onaylı (docstatus = 1)` ise — Buton: `Etiketleri Güncelle ve Bas` (`relabel_submitted_stock_reconciliation`):**
       1. Bölünme gerektirmeyen standart `7+4` satırların etiketleri doğrudan `upsert_box_label` ile güncellenir.
       2. `box_splits > 1` veya `LEGACY` dönüştürülecek satırlar için Faz 1 `create_package_split_repack(..., source_warehouse=wh, target_warehouse=wh, ignore_reco_lock=...)` çağrılarak kalem bazlı `Package Split` (`Repack`) fişleri kesilir.
       3. Oluşan yeni kutu etiketleri Zebra yazıcıya toplu gönderilir; `0` bakiye eski etiketler temizlenir.

#### Sekme 2 — Fark ve Anomali Analizi (`RecoAnalyticsTab.vue` + `RecoItemDrawer.vue`)
- Mevcut `App.vue` panosunun birebir TypeScript + `const __ = ...` + Açık/Koyu tema dönüşümü:
  - Yıl, tarih aralığı, eşik (`threshold`), yön (`Tümü / + / −`) ve metin arama filtreleri (`localStorage` tercihleri korunur).
  - 7 KPI kartı + Taslak/Onaylı ilerleme çubuğu.
  - Kural tabanlı Anomali motoru (`CONTRADICTION`, `CONCENTRATION`, `CHURN`, `OSCILLATION`, `DOC_SPIKE`, `DOC_OSCILLATION`) ve En Yüksek Riskler (`Top Risks`) listesi.
  - Sıralanabilir ürün tablosu, CSV dışa aktarma, sağdan açılan `RecoItemDrawer.vue` depo kırılımı & belge listesi.
  - Socket.IO `stock_reco_dashboard_update` canlı yenileme desteği.

---

### 2.2 Desk Form Entegrasyonu ve Yönlendirme
- `erpnextkta/public/js/stock_reconciliation.js`:
  - Form içi **`Depodan Ürünleri Getir`** (`get_items_static`) davranışı aynen korunur.
  - Eskiden toplu oluşturma prompt'u açan buton **`Sayım ve Etiket Merkezinde Aç`** butonu olarak güncellenir (`frappe.route_options = { doc: frm.doc.name, tab: "operations" }; frappe.set_route("stock-reco-dashboard");`).
- `erpnextkta/kta_stock/page/stock_reco_dashboard/stock_reco_dashboard.js`:
  - `on_page_load` ve özellikle **`on_page_show`** içinde `frappe.route_options` okunup CustomEvent veya Vue store üzerinden sayfanın ilk açılışından *sonra* bile belge/sekme seçiminin anında güncellenmesi sağlanır.
  - Sayfa tam genişlik / modern header düzeni (`shopfloor_hub.js` örüntüsü veya temiz `.page-head` entegrasyonu) uygulanır.

---

### 2.3 Frontend Dosya Ayrışımı (`< 500` Satır Standardı)

```
erpnextkta/public/stock-reco-dashboard/
├── stock-reco-dashboard.bundle.js
├── tsconfig.json
├── frappe.d.ts
├── types.ts
├── App.vue                         (Sekme yönetimi, URL/route_options senkronu, tema/hata kabuğu)
└── components/
    ├── BulkCreateRecoModal.vue     (Teleport modal: Depo grubundan toplu sayım fişi)
    ├── RecoDocumentsList.vue       (Sayım belgeleri tablosu & filtreleri)
    ├── RecoLabelingWorkspace.vue   (Mod 1 / Mod 2, kutu kırılımı, LEGACY dönüşüm & Zebra baskı)
    ├── RecoAnalyticsTab.vue        (Fark & Anomali Analizi sekmesi, KPI, anomali, tablo, CSV)
    └── RecoItemDrawer.vue          (Sağ detay çekmecesi: depo barları & belge listesi)
```

---

## 3. Faz 2 Backend API Sözleşmeleri

- **`erpnextkta/kta_stock/services/stock_reconciliation_service.py`:**
  - `list_stock_reconciliations(status_filter: str = "all", warehouse: str | None = None, search: str | None = None, limit: int = 50) -> list[dict]`
  - `get_stock_reconciliation_label_preview(stock_reconciliation: str) -> dict` *(belge üst bilgileri + her satır/parti için `status`, `is_legacy`, `existing_label_qty`, `suggested_mode1_selected`)*
  - `submit_and_print_stock_reconciliation(stock_reconciliation: str, selected_items: list[dict] | str, print_labels: int = 1) -> dict`
  - `relabel_submitted_stock_reconciliation(stock_reconciliation: str, selected_items: list[dict] | str, print_labels: int = 1) -> dict`
- **`selected_items` satır sözleşmesi:**
  - `{"row_name": str, "item_code": str, "warehouse": str, "source_batch": str | None, "qty": float, "convert_legacy": int, "box_splits": list[float]}`
- **Yetki Kuralı:**
  - Okuma uçları `frappe.has_permission("Stock Reconciliation", "read", throw=True)`.
  - Yazma/Onaylama uçları `frappe.has_permission("Stock Reconciliation", "write", throw=True)` + submit gerekiyorsa `"submit"` yetki kontrolü; `Stock Reconciliation Manager` kilidi kuralına tam uyum.
