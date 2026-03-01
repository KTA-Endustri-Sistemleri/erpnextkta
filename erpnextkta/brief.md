# erpnextkta — Uygulama Teknik Brief

> Son güncelleme: 2026-03-02
> Hedef sistem: ERPNext (Frappe Framework üzerinde) / Çerkezköy, Türkiye

---

## 1. Kimlik ve Amaç

| Özellik | Değer |
|---------|-------|
| App adı | `erpnextkta` |
| Başlık | KTA Endüstri Özelleştirmeleri |
| Yayıncı | Framras AS |
| Lisans | MIT |
| Frappe hook entry | `after_migrate = ["erpnextkta.overrides.apply"]` |
| Scheduler | Haftalık: `erpnextkta.tasks.weekly` |

**Temel misyon:** KTA Endüstri Sistemleri'nin ERPNext kurulumuna özgü iş kurallarını, üretim takibini, kalite kontrolünü, satış senkronizasyonunu ve stok yönetimini kapsar. Standart ERPNext doktipleri override edilerek genişletilmiş, yeni modüller ve Vue 3 SPA'ları ile zenginleştirilmiştir.

---

## 2. Modüller

```
modules.txt:
  erpnextkta          ← Core / genel amaçlı
  kta_mrp             ← MRP raporlaması
  kta_calisma_karti   ← Üretim takip + QC
  kta_sales           ← Satış siparişi senkronizasyonu
  kta_stock           ← Stok mutabakat dashboard
```

---

## 3. Dizin Yapısı (Genel)

```
erpnextkta/
├── api.py                  ← Ana whitelist API (1306 satır): Zebra, batch split, stok, satış
├── hooks.py                ← Override tanımları, doc_events, fixtures
├── modules.txt             ← Modül listesi
├── tasks.py                ← Scheduler görevleri
├── patches.txt             ← Migration patch'leri
│
├── erpnextkta/             ← Core modül (DocType tanımları: Zebra, depo etiketleri vb.)
├── kta_calisma_karti/      ← Üretim çalışma kartı modülü
├── kta_mrp/                ← MRP modülü
├── kta_sales/              ← Satış senkronizasyon modülü
├── kta_stock/              ← Stok dashboard modülü
│
├── overrides/              ← Standard ERPNext DocType override'ları
├── public/                 ← Frontend SPA'ları (Vue 3 Bundles)
├── rest-api/               ← REST endpoint yardımcıları
├── fixtures/               ← Export edilmiş fixture veriler
└── templates/              ← Jinja şablonları
```

---

## 4. Core `api.py` — Ana API

`erpnextkta/api.py` uygulamanın en büyük dosyasıdır (1306 satır). Beyaz listeye alınmış Frappe API fonksiyonlarının yanı sıra iç yardımcı fonksiyonlar barındırır.

### 4.1 Zebra Etiket Sistemi

Fabrika içi **Zebra termal yazıcılar** üzerinden ZPL formatında etiket baskısı.

| Fonksiyon | Açıklama |
|-----------|----------|
| `print_kta_pr_labels(gr_number, label, q_ref)` | Satın alma girişi etiketleri (split edilmemiş) |
| `print_split_kta_pr_labels(label)` | Split edilmiş batch etiketleri |
| `print_kta_wo_labels(work_order)` | İş emri üretim etiketleri |
| `print_kta_wo_labels_of_stock_entry(stock_entry)` | Stok girişi bazında üretim etiketi |
| `send_data_to_zebra(data, ip, port)` | TCP socket ile ZPL gönderimi |
| `zebra_formatter(doctype_name, data)` | `KTA Zebra Templates`'den şablon alır |
| `get_zebra_printer_for_user()` | Oturum kullanıcısının yazıcısını döner |
| `format_kta_label_qty(qty)` | Türkçe locale ile miktar formatlama |

**Bağlı Doctypes:** `KTA Zebra Templates`, `KTA Zebra Printers`, `KTA User Zebra Printers`, `KTA Depo Etiketleri`, `KTA Is Emri Etiketleri`

### 4.2 Batch Splitting Sistemi

Gelen malı müşteri paketlemeleri bazında **otomatik sub-batch'lere** bölme.

**Batch numaralandırma kuralı:**
- Base batch: `XXXXXXX` (7 alfanumerik, ilk 7 karakter)
- Split batch: `XXXXXXX0001`, `XXXXXXX0002`, ... (4 haneli sıralı suffix)

| Fonksiyon | Rol |
|-----------|-----|
| `custom_split_kta_batches(row)` | Satın alma girişi satırı için ana split akışı |
| `_prepare_batch_allocations(row, ...)` | Allocation planı hazırlar (PR ve üretim için ortak) |
| `_create_split_batch_record(row, ...)` | Bireysel split Batch kaydı oluşturur |
| `_update_bundle_safely(row, allocations)` | Serial and Batch Bundle'ı flags+save ile günceller |
| `custom_create_packages(row, ...)` | `KTA Depo Etiketleri` kaydı oluşturur |
| `_get_last_batch_number_for_base(base)` | SQL ile son sequence numarasını bulur |
| `_get_customer_packaging_qty(item_code)` | `Item Customer Detail.custom_musteri_paketleme_miktari` |

> **Önemli:** `do_not_split=1` olan satırlar tek batch olarak kalır, sadece `XXXXXXX0000` bundle'ı oluşturulur.

### 4.3 Satış Senkronizasyonu API'si

`kta_sales` modülü doktiplerinden re-export edilen fonksiyonlar:

| Fonksiyon | Kaynak | Açıklama |
|-----------|--------|----------|
| `sync_sales_orders_from_comparison` | `kta_so_sync_log` | Comparison belgesininden satış sipariş senkronu |
| `sync_sales_orders_from_sales_order_update` | `kta_so_sync_log` | SO Update belgesininden senkron |
| `compare_sales_order_update_documents` | `kta_sales_order_update_comparison` | İki güncelleme belgesini karşılaştırır |

### 4.4 Diğer API Fonksiyonları

| Fonksiyon | Açıklama |
|-----------|----------|
| `get_customer_income_account(customer, company)` | Party Account'tan müşteri gelir hesabı |
| `get_base_batch_for_work_order(work_order)` | Work Order için base batch |
| `get_available_batches_for_stock_recon(...)` | Stok mutabakat için uygun batch'ler |
| ve daha fazlası... (stok, depo, mobil depo, irsaliye gibi çeşitli yardımcılar) |

---

## 5. Override Sınıfları

`hooks.py` içinde tanımlanan `override_doctype_class` ve `doc_events` aşağıdaki dokümanlara uygulanmaktadır.

### 5.1 `KTAPurchaseReceipt` (Purchase Receipt)

**Dosya:** `overrides/KTAPurchaseReceipt.py`

| Hook | Davranış |
|------|----------|
| `validate()` | `update_rates_logic()` → Döviz kuru + kalem fiyatları güncellenir |
| `validate_with_previous_doc()` | "Rate must be same as Purchase Order" hatasını yutarak bypass |
| `before_insert/before_save()` | `use_serial_batch_fields = 0` |
| `on_submit()` | `verify_batch()` → batch split → QC oluşturma (`custom_atlama_sayisi` mantığı ile atlama) → Zebra baskı |
| `update_stock_ledger()` | Stok defteri yazılmadan önce pending split'leri tetikler |

**Döviz kuru mantığı:**
- Normal ithalat: `gumruk_beyanname_tarihi` veya `irsaliye_tarihi`'nden "Selling" kur
- `custom_gumruksuz = 1`: `posting_date`'den "Buying" kur

**QC atlama kuralı:** `Item.custom_atlama_sayisi` > 0 ise her N. girişte QI oluşturulur, aralardaki satırlar direkt split'e gider.

---

### 5.2 `KTADeliveryNote` (Delivery Note)

**Dosya:** `overrides/delivery_note.py`

| Hook | Davranış |
|------|----------|
| `validate()` | `update_rates_logic()` → Döviz kuru + fiyat listesi güncellemesi |
| `validate_with_previous_doc()` | "Rate must be same as Sales Order" bypass |

**Fiyatlandırma kuralları:**
- `custom_ara_malzeme_grubu != "ÜRÜN"` olan kalemler atlanır
- Numune SO (`custom_numune_mi = 1`) olan kalemler atlanır
- **BOSCH** müşterisine özel: Selling kur kullanılır (diğerlerine Buying kur)
- Müşteriye özgü `Item Price` (valid_from–valid_upto bazlı) öncelikli uygulanır

---

### 5.3 `KTASalesInvoice` (Sales Invoice)

**Dosya:** `overrides/sales_invoice.py`

Delivery Note ile aynı kurallar uygulanır. Validate aşamasında döviz kuru + müşteri bazlı fiyat listesi güncellemesi yapılır.

---

### 5.4 `SerialandBatchBundle` (Serial and Batch Bundle)

**Dosya:** `overrides/serial_batch_bundle_doc.py`

| Hook | Davranış |
|------|----------|
| `autoname()` | Purchase Receipt bundle'larına base batch ilk 7 karakteri verilir |
| `validate()` | Split batch uyumluluk kontrolü; üretim giriş bundle'larında ek doğrulama |
| `validate_serial_and_batch_no_for_returned()` | İade senaryolarında split batch'leri base batch ile eşleştirir |

**Split batch tespiti:** Son 4 karakter rakam mı? → Split batch.

---

### 5.5 Diğer Override'lar

| Dosya | Override Nesnesi | Ana Davranış |
|-------|-----------------|-------------|
| `KTAStockEntry.py` | Stock Entry | Küçük özelleştirmeler |
| `KTAPurchaseOrder.py` | Purchase Order | Özelleştirmeler |
| `KTAQualityInspection.py` | Quality Inspection | Özelleştirmeler |
| `KTAbom.py` | BOM | Küçük özelleştirme |
| `stock_reconciliation.py` | Stock Reconciliation | Wrapper |
| `purchase_invoice.py` | Purchase Invoice | `validate` – kontroller |
| `purchase_receipt_rates.py` | Purchase Receipt | Kur güncelleme yardımcısı |
| `make_purchase_invoice.py` | PR→PI dönüşüm | `override_whitelisted_methods` ile override |
| `print_settings.py` | Print Settings | Barkod baskı özelleştirmeleri |
| `serial_batch_utils.py` | — | Yardımcı fonksiyonlar |

### 5.6 `doc_events` Hook'ları

| Doctype | Event | Hedef |
|---------|-------|-------|
| `Kalite Kontrol` | `on_submit` | CK QC akışını tetikler |
| `Job Card` | `on_update` | Work Order'ı "In Process" yapar (eğer time log başladıysa) |
| `Stock Reconciliation` | `on_update/cancel/trash` | `kta_stock` realtime event |
| `Stock Reconciliation` | `validate` | Warehouse başına tek draft kısıtı |
| `Stock Entry` | `validate` | Locked warehouse kontrolü |
| `Purchase Invoice` | `validate` | Özel doğrulamalar |
| `Purchase Receipt` | `validate` | Kur güncelleme yardımcısı |

### 5.7 `doctype_js` Hooks

| Doctype | JS Dosyası | Açıklama |
|---------|-----------|----------|
| `Calisma Karti` | `kta_calisma_karti/doctype/calisma_karti/calisma_karti.js` | CK form scripts |
| `Stock Reconciliation` | `public/js/stock_reconciliation.js` | Ek kontroller |
| `Stock Entry` | `public/js/stock_entry_get_items_from_calisma_karti.js` | CK'dan kalem çekme |

---

## 6. Modül: `kta_calisma_karti` — Üretim Çalışma Kartı

> 📋 **Detaylı teknik brief için:** [`kta_calisma_karti/TECHNICAL_BRIEF.md`](kta_calisma_karti/TECHNICAL_BRIEF.md)

### Özet

Üretim operatörlerinin **Job Card + Work Order** akışını takip ettiği, kalite kontrolünü (IDC ölçümü, barkod kaydı, QC onayı) ve hurda yönetimini yaptığı ana modül. Vue 3 SPA'ları ile mobil/fabrika zeminine yönelik bir operatör arayüzü sunar.

### Backend Yapısı

```
kta_calisma_karti/
├── api.py                      ← Stable facade (tüm frontend çağrıları buraya)
├── realtime.py                 ← Socket.IO publisher
├── api_impl/
│   ├── _helpers.py             ← Rol/employee yardımcıları
│   ├── cards.py                ← Liste + detay sorguları
│   ├── create.py               ← CK oluşturma
│   ├── hurda.py                ← Hurda CRUD + BOM filtresi
│   ├── qc.py                   ← QC + IDC + Barkod CRUD
│   ├── alt_operasyon.py        ← Alt operasyon CRUD
│   └── barcode.py              ← JC/WO barkod arama
└── doctype/
    ├── calisma_karti/          ← Ana doctype
    ├── calisma_karti_hurda/
    ├── calisma_karti_idc_olcumleri/
    ├── calisma_karti_barkod_kayitlari/
    ├── calisma_karti_alt_operasyon_kayitlari/
    ├── kta_calisma_karti_operasyonlari/
    ├── kta_calisma_karti_alt_operasyonlari/
    ├── kta_operasyon_grubu/
    └── operasyon_duruslari/
```

### Veri Modeli Özeti

**Ana Doctype: `Calisma Karti`**

| Alan | Tip |
|------|-----|
| `is_istasyonu` | Link → Workstation (Zorunlu) |
| `operator` | Link → Employee |
| `operasyon` | Link → KTA Calisma Karti Operasyonlari (Zorunlu) |
| `is_karti` | Link → Job Card (Zorunlu) |
| `custom_work_order` | Link → Work Order |
| `durum` | Select: Hazır/Çalışıyor/Duruşta/Bitmiş/Reddedildi |
| `kalite_kontrol` | Select (permlevel=1): Onay Bekliyor/Onaylandı/Reddedildi |
| `hurdalar` | Table → Calisma Karti Hurda |
| `duruslar` | Table → Operasyon Duruslari |
| `idc_olcumleri` | Table → Calisma Karti IDC Olcumleri |
| `barkod_kayitlari` | Table → Calisma Karti Barkod Kayitlari |
| `alt_operasyon_kayitlari` | Table → Calisma Karti Alt Operasyon Kayitlari |

### Realtime Events

```python
"kta_calisma_karti:list_changed"               # Tüm liste ekranları (broadcast)
f"kta_calisma_karti:doc_changed:{docname}"     # Belirli kart detayı
```

### Frontend SPA'ları

| Sayfa | Konum | Açıklama |
|-------|-------|----------|
| `create-calisma-karti` | `public/create-calisma-karti/` | Wizard (WO modu: 5 adım, JC modu: 3 adım) |
| `list-calisma-cards` | `public/list-calisma-cards/` | Liste (realtime, filtreler, pagination) |
| `view-calisma-karti` | `public/view-calisma-karti/` | Detay (TypeScript, tab yapısı, aksiyon butonları) |

### Roller

| Rol | Liste | Detay Okuma | Durum Değiştirme | Hurda | QC |
|-----|-------|------------|-----------------|-------|----|
| System Manager | Tümü | Tümü | ✅ | ✅ | ✅ |
| KTA Kalite Kullanıcısı | Tümü | Tümü | — | — | ✅ |
| Manufacturing User | Kendi | Kendi | ✅ | ✅ | — |

---

## 7. Modül: `kta_mrp` — MRP Raporlaması

### Amaç
Üretim planlama, kapasite ve satış verisi köprüleyen raporlar seti.

### Raporlar

| Rapor | Açıklama |
|-------|----------|
| `material_requirement` | Malzeme İhtiyaç Planlaması (MRP) |
| `production_start_week` | Haftalık üretim başlangıç planı |
| `shipment_week` | Haftalık sevkiyat planı |
| `work_order_planning` | İş emri planlama |
| `capacity_planning_report` | Kapasite planlama raporu |
| `periodic_sales_orders` | Periyodik satış sipariş özeti |
| `recommended_purchase_orders` | Önerilen satın alma emirleri |

### DocType
- `KTA Sevk Parametreleri` — Sevkiyat parametre tanımları

---

## 8. Modül: `kta_sales` — Satış Siparişi Senkronizasyonu

### Amaç
Müşterilerin (özellikle BOSCH gibi büyük OEM müşterileri) göndereceği **satış sipariş güncelleme dosyalarını** ERPNext'e senkronize etmek. Karşılaştırma, değişiklik takibi ve onay akışı içerir.

### DocType'lar

| DocType | Rol |
|---------|-----|
| `KTA Sales Order Update` | Müşteri tarafından gelen sipariş güncellemesi (ana kayıt) |
| `KTA Sales Order Update Entry` | Güncelleme kalemi (child table) |
| `KTA Sales Order Update Comparison` | İki güncelleme belgesi arasında karşılaştırma |
| `KTA Sales Order Update Change` | Tespit edilen değişiklikler (child) |
| `KTA SO Sync Log` | Senkronizasyon log belgesi |
| `KTA SO Sync Detail` | Senkronizasyon log detayı (child) |

### Temel API (api.py'den re-export)

```python
compare_sales_order_update_documents(doc1, doc2)
sync_sales_orders_from_comparison(comparison_doc)
sync_sales_orders_from_sales_order_update(update_doc)
```

---

## 9. Modül: `kta_stock` — Stok Mutabakat Dashboard

### Amaç
`Stock Reconciliation` dokümanlarının gerçek zamanlı durumunu izleyen bir dashboard sayfası. Realtime Socket.IO ile anlık güncelleme destekler.

### Yapı

```
kta_stock/
├── page/
│   └── stock_reco_dashboard/    ← Frappe Page tanımı (3 dosya)
└── realtime/
    └── stock_reco_dashboard.py  ← on_update/cancel/trash event yayıncısı
```

### Realtime Event

```python
# hooks.py → doc_events → Stock Reconciliation → on_update/cancel/trash
→ kta_stock.realtime.stock_reco_dashboard.on_update
```

Frontend sayfası: `public/stock-reco-dashboard/` SPA.

---

## 10. Core Modül: `erpnextkta` — Genel Doctypes

`erpnextkta/erpnextkta/` altındaki doctypes büyük ölçüde Zebra etiket sistemi, depo etiketleri ve ölçüm metodları ile ilgilidir.

### Başlıca DocType'lar (core)

| DocType | Amaç |
|---------|------|
| `KTA Zebra Templates` | Yazıcı şablonları (ZPL) |
| `KTA Zebra Printers` | Yazıcı IP/port tanımları |
| `KTA User Zebra Printers` | Kullanıcı → Yazıcı eşlemesi |
| `KTA Depo Etiketleri` | Satın alma girişi etiket kayıtları |
| `KTA Depo Etiketleri Bolme` | Etiket kırılımı (split için child table) |
| `KTA Is Emri Etiketleri` | Üretim çıkış etiketleri |
| `KTA Mobil Depo` | Mobil depo takibi |
| `KTA Mobil Depo Kalemi` | Mobil depo kalemi |
| `KTA Olcu Metodu` | Ölçüm metotları (fixture olarak export edilir) |
| `Calisma Karti` *(ayrıca kta_calisma_karti modülünde)* | — |

### Overrides içindeki `__init__.py`

`overrides/__init__.py` → `after_migrate` hook'u çağırır → Custom Field'ları ve gereken konfigürasyonları migrate sonrası uygular.

### Fixtures

```
fixtures = [
  "KTA Olcu Metodu",
  "Customs Tariff Number",
  Custom Field (Print Settings, Stock Settings, Buying Settings — barkod format alanları),
  Client Script (name like "KTA%"),
  Role Profile (name like "KTA%"),
]
```

---

## 11. Frontend Genel Bakış

Tüm SPA'lar **Vue 3 + Composition API** ile yazılmıştır. `*.bundle.js` dosyaları Frappe'nin asset build pipeline'ına giriş noktasıdır.

| Bundle | Konum | Teknoloji | Açıklama |
|--------|-------|-----------|----------|
| `create-calisma-karti.bundle.js` | `public/create-calisma-karti/` | Vue 3 (JS) | CK oluşturma wizard |
| `list-calisma-cards.bundle.js` | `public/list-calisma-cards/` | Vue 3 (JS) | CK listesi |
| `view-calisma-karti.bundle.js` | `public/view-calisma-karti/` | Vue 3 + TypeScript | CK detay |
| `stock-reco-dashboard.bundle.js` | `public/stock-reco-dashboard/` | Vue 3 | Stok mutabakat dashboard |

**Ortak özellikler:**
- `frappe.call()` ile API iletişimi
- `frappe.realtime` (Socket.IO) ile canlı güncelleme
- Frappe CSS değişkenleri (`--card-bg`, `--text-color` vb.) ile tema uyumu
- `frappe.set_route()` ile Frappe router entegrasyonu

---

## 12. Güvenlik Mimarisi

```
Katman 1: Frappe @whitelist()        → HTTP erişim kontrolü
Katman 2: Rol kontrolü              → frappe.get_roles()
Katman 3: doc.check_permission()    → Frappe permission layer
Katman 4: Domain validation         → BOM, Cost Center, item_group whitelist
Katman 5: Azami ayrıcalık           → ignore_permissions SADECE rol kapısı geçildikten sonra
```

### Özel Roller

| Rol | Kullanıldığı Yer |
|-----|----------------|
| `System Manager` | Tüm modüllerde tam yetki |
| `KTA Kalite Kullanıcısı` | CK listesi (tümü), QC güncellemeleri, IDC/Barkod CRUD |
| `Manufacturing User` | CK oluşturma/okuma/yazma (sadece kendi kartları) |
| `Quality Manager` | QC güncelleme |

---

## 13. Bağımlı ERPNext/Frappe Doktipler

| Doctype | Kullanıldığı Modül(ler) |
|---------|------------------------|
| `Job Card` | kta_calisma_karti, kta_mrp |
| `Work Order` | kta_calisma_karti, api.py (Zebra) |
| `BOM / BOM Item` | kta_calisma_karti, api.py |
| `Purchase Receipt` | overrides, api.py (batch split, zebra) |
| `Serial and Batch Bundle/Entry` | overrides, api.py |
| `Batch` | api.py (batch split sistemi) |
| `Item / Item Price / Item Customer Detail` | overrides, kta_calisma_karti |
| `Currency Exchange` | override (KTAPurchaseReceipt, DeliveryNote, SalesInvoice) |
| `Delivery Note` | overrides |
| `Sales Invoice` | overrides |
| `Sales Order` | kta_sales, overrides |
| `Stock Reconciliation` | kta_stock, rest-api |
| `Stock Entry` | overrides, api.py |
| `Employee` | kta_calisma_karti |
| `Workstation` | kta_calisma_karti |
| `Cost Center` | kta_calisma_karti (hurda nedeni whitelist) |
| `Quality Inspection` | overrides |

---

## 14. Bilinen Açık Noktalar

1. **`callIslem` endpoint'i** (`view-calisma-karti` Başlat/Durdur/Bitir) → `useCalismaKarti.ts` composable içinde. Hangi backend yöntemine bağlandığı tam olarak saptanmamıştır.

2. **`tamamlanan_miktar` alanı** `Calisma Karti` JSON şemasında göünmüyor → Muhtemelen Custom Field veya migration ile eklenmiş.

3. **`STATU_HARITASI` + `get_durum()`** → `calisma_karti.py` DocType sınıfında yaşıyor; CK durum geçiş mantığı bu sınıfta.

4. **`kta_mrp` rapor içerikleri** bu brief'te detaylandırılmadı (7 ayrı rapor, her biri farklı planlama boyutu).

5. **`rest-api/` klasörü** → `stock_reconciliation_lock.py` (stok mutabakat kilitleme) içeriyor; tam inventeri çıkarılmadı.

6. **Batch splitting** hem PR hem üretim (Stock Entry) için çalışır; üretim tarafındaki `KTAStockEntry` hook'u ayrıca incelenebilir.

---
