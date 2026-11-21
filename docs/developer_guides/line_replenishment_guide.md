---
layout: default
title: "KTA Hat İkmal Yönetimi (Line Replenishment Engine) Geliştirici Kılavuzu"
---

# 🚛 KTA Hat İkmal Yönetimi (Line Replenishment Engine)

**`Line Replenishment Engine`**, ERPNext üretim sahalarında reaktif malzeme duruşlarını ortadan kaldırıp hedef üretim hattının iş emri rezervasyon açıklarını tarayan, **yalnızca ana hammadde ambarının (`110 HAMMADDE`) yaprak raflarından** bölünmeyen tam koli/makara FIFO parti tahsisi yapan ve mobil PDA terminaliyle tek adımda resmi `Stock Entry (Material Transfer)` fişi üreten **%100 Saf Ana Ambar Hat İkmal** sistemidir.

> **Mimari Ayrım (Hat İkmal vs. Hatlar Arası Transfer):**
> - **Ana Ambardan Hatlara İkmal (`110 HAMMADDE → 150x`):** Bu dokümanda açıklanan `Line Replenishment Hub` (`/app/line-replenishment-hub`) ve mobil PDA (`/app/line-replenishment-picking`) üzerinden depo ekibi tarafından FIFO tam koli disipliniyle yürütülür.
> - **Üretim Hatları Arası Transfer (`150x ↔ 150x`):** Kardeş üretim hatları arasındaki serbest stok aktarımı, açık karşılama ve öncelik kaydırmalı transferler ise [Shopfloor Hub Geliştirici Kılavuzu](../kta_shopfloor_hub_kilavuzu.md) kapsamında **Shopfloor Hub (`/app/shopfloor_hub`) → `🔄 Hatlar Arası Transfer`** sekmesinden (`line_transfer_service.py`, arka plan LIFO parti tahsisi) yürütülür.

---

## 🎯 1. Modül Ayrımı ve Mimari Tasarım

Sistem iki ana modül arasında açık sorumluluk ayrımı (Separation of Concerns) ile kurgulanmıştır:

- **`kta_shopfloor` (Analitik & Masaüstü Kokpit Katmanı):**
  - Hedef hat bazlı rezervasyon açıklarını tespit eder (`services/reservation_deficit_service.py`).
  - Açıkta bekleyen taslak (`Draft`) ikmal emirlerini düşerek net açığı hesaplar (`D_net = max(0, D_ham - Q_taslak)`).
  - Ana hammadde ambarını (`get_central_warehouse`, varsayılan `110 HAMMADDE - KTA`) çözümler ve `bulk_allocate_fifo_batches` üzerinden raf/parti tahsisini alır.
  - Masaüstü planlama kokpitini (`/app/line-replenishment-hub` — `erpnextkta/public/line-replenishment-hub/`) barındırır.
  - Açık tarama API'sini (`erpnextkta.kta_shopfloor.api.get_line_deficits`) sunar.

- **`kta_stock` (İkmal Siparişi, Parti Tahsisi & PDA Toplama Katmanı):**
  - İkmal emri DocType modellerini (`KTA Line Replenishment Order` & `KTA Line Replenishment Item`) yönetir.
  - Hiyerarşik yaprak ambar çözümlemesi (`get_leaf_warehouses`) ile grup ambarlarını eler.
  - FIFO çoklu parti ve fiziksel raf tahsis motorunu (`allocate_fifo_batches` / `bulk_allocate_fifo_batches`) işletir.
  - Tam koli / makara bölmeme ilkesiyle partileri tam miktarıyla yukarı yuvarlar.
  - Mobil PDA toplama arayüzünü (`/app/line-replenishment-picking` — `erpnextkta/public/line-replenishment-pda/`) sağlar.
  - Sıfır manuel girişli barkod okuma, tolerans denetimi (+%15 veya +1 birim alt sınırı: `max(deficit * 1.15, deficit + 1.0)`) ve atomik `Stock Entry (Material Transfer)` fişini yürütür.
  - İptal durumunda bağlı transfer fişini de ters kayıtla iptal eden rollback güvencesi sunar.

```
+-------------------------------------------------------------------------+
|        Line Replenishment Hub (/app/line-replenishment-hub)             |
|        (Tekil Hedef 150x Hat Seçimi — Saf Ana Ambar Odaklı)            |
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
|         kta_shopfloor.services.reservation_deficit_service              |
| - Net Rezervasyon Açığı: reserved_qty_for_production - actual_qty       |
| - Taslak İkmal Düşümü: D_net = max(0, D_ham - Q_taslak) (Mükerrer Engel) |
| - Kaynak: Yalnızca get_central_warehouse() -> 110 HAMMADDE - KTA        |
| - Sıfır Stok & Taslak Kilidi: selectable = False Bayrağı                |
| - bulk_allocate_fifo_batches Entegrasyonu ile Raf & Parti Görünürlüğü   |
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
|               kta_stock.line_replenishment_service                      |
| - get_leaf_warehouses(parent) -> NestedSet lft/rgt ile Yaprak Raflar    |
| - allocate_fifo_batches() -> Bölünmeyen Tam Parti & Raf Tahsisi (FIFO)  |
| - create_line_replenishment_order() -> Çoklu Parti Ayrıştırmalı Taslak  |
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
|      Line Replenishment Picking (/app/line-replenishment-picking)       |
| - Sıfır Manuel Giriş: Barkod Okutulduğunda Otomatik Tam Parti Onayı      |
| - Tolerans Kontrolü (max(deficit * 1.15, deficit + 1.0))                |
| - complete_line_replenishment_picking()                                 |
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
|              Stock Entry (Material Transfer - Submitted)                |
| - Kaynak: Fiziksel Yaprak Raf (W1A-01-01 vb. - Asla Grup Ambarı Değil)  |
| - Hedef: Tekil Hat Deposu (1501 KESMELER - KTA vb.)                     |
+-------------------------------------------------------------------------+
```

---

## 📐 2. Veri Şeması ve DocType Modelleri

> **Not:** Eski sürümlerde bulunan `sourcing_strategy` (Order), `sourcing_type` (Item) ve `free_stock_qty` (Item) alanları mimari ayrım kapsamında tamamen kaldırılmıştır.

### 2.1 Parent DocType: `KTA Line Replenishment Order`

Tekil bir hatta yapılacak ana ambar malzeme ikmal operasyonunu temsil eder (`naming_series`: `LRO-.YYYY.-.#####`):

| Alan Adı | Tip | Zorunlu | Açıklama |
|---|---|---|---|
| `naming_series` | Select | Evet | Otomatik belge serisi (`LRO-.YYYY.-.#####`) |
| `target_warehouse` | Link (`Warehouse`) | Evet | Hedef üretim/WIP ambarı (Grup ambarı olamaz) |
| `company` | Link (`Company`) | Evet | İlgili şirket |
| `posting_date` | Date | Evet | Sipariş oluşturma tarihi |
| `posting_time` | Time | Hayır | Sipariş oluşturma saati |
| `status` | Select | Evet | `Draft`, `In Progress`, `Completed`, `Cancelled` |
| `total_deficit_qty` | Float | Hayır | Siparişteki toplam net açık miktarı (salt okunur) |
| `total_picked_qty` | Float | Hayır | Toplanan toplam fiili miktar (salt okunur) |
| `stock_entry` | Link (`Stock Entry`) | Hayır | Oluşturulan resmi transfer fişi referansı (salt okunur) |
| `items` | Table | Hayır | `KTA Line Replenishment Item` alt tablosu |
| `remarks` | Small Text | Hayır | Kullanıcı notları veya otomatik açıklamalar |

### 2.2 Child DocType: `KTA Line Replenishment Item`

İkmal siparişi altındaki parti ve raf bazlı malzeme kalemlerini içerir:

| Alan Adı | Tip | Açıklama |
|---|---|---|
| `item_code` | Link (`Item`) | İkmal edilecek hammadde kodu (Zorunlu) |
| `item_name` | Data | Malzemenin adı (salt okunur) |
| `uom` | Link (`UOM`) | Temel stok ölçü birimi (Zorunlu) |
| `reserved_qty` | Float | Hatta planlanan iş emirleri rezervasyon toplamı (salt okunur) |
| `line_actual_qty` | Float | Hedef hattın mevcut fiziki stok miktarı (salt okunur) |
| `deficit_qty` | Float | Hesaplanan net açık / parti tahsis miktarı (salt okunur) |
| `suggested_source_warehouse` | Link (`Warehouse`) | FIFO motorunun önerdiği fiziksel yaprak raf |
| `suggested_batch_no` | Link (`Batch`) | FIFO motorunun belirlediği parti numarası |
| `picked_qty` | Float | PDA ile toplanan gerçekleşen miktar |
| `picked_source_warehouse` | Link (`Warehouse`) | Fiilen çekilen kaynak yaprak raf |
| `picked_batch_no` | Link (`Batch`) | Fiilen taranan parti numarası |
| `is_picked` | Check | Toplama tamamlandı onay işareti |

---

## 🔌 3. API Uç Noktaları (White-Listed Endpoints)

### 3.1 `erpnextkta.kta_shopfloor.api.get_line_deficits`
Hedef WIP deposundaki net açıkları tarar, açıkta bekleyen taslak ikmal siparişlerini düşer ve yalnızca `110 HAMMADDE` yaprak raflarından FIFO parti önerilerini döner.

- **Girdi Parametreleri:**
  - `target_warehouse` (str, zorunlu): Hedef üretim/hat deposu.
  - `sourcing_strategy` (str, opsiyonel, kullanılmıyor): Geriye dönük API uyumluluğu için tutulur; dahili olarak `get_line_reservation_deficits(target_warehouse, **_kwargs)` imzasına aktarılır ve yok sayılır.
- **Doğrulama:**
  - `target_warehouse` boş veya `is_group == 1` ise `frappe.ValidationError` fırlatır.
- **Açıkta Bekleyen Taslak İkmal Düşümü (Mükerrer Sipariş Engeli):**
  - Servis, hedef hatta ait tüm açık `Draft` (`docstatus = 0, status = 'Draft'`) ikmal siparişlerini sorgular:
    `SELECT parent, item_code, suggested_batch_no, deficit_qty FROM tabKTA Line Replenishment Item WHERE docstatus = 0 AND parent IN (...)`
  - Her hammadde için $Q_{\text{taslak}} = \sum \text{deficit\_qty}$ toplanır.
  - Net açık miktarı $D_{\text{net}} = \max(0, D_{\text{ham}} - Q_{\text{taslak}})$ formülüyle indirgenir.
  - **Tam Kapsanan Kalemler:** $D_{\text{ham}} > 0$ ve $D_{\text{net}} == 0$ ise `covered_by_draft = True`, `selectable = False` olarak döner; `draft_orders` listesi ve `draft_covered_qty` iletilir.
  - **Kısmi Kapsanan Kalemler:** $D_{\text{net}} > 0$ ise yalnızca kalan delta miktar ($D_{\text{net}}$) `bulk_allocate_fifo_batches` motoruna gönderilir.
- **Sıfır Stok Koruması:**
  - Kalemin ana ambar yaprak raflarında stoğu yoksa (`has_stock == False`), `selectable = False` olarak işaretlenir ve arayüzde kilitlenir.
- **Dönüş Değeri (`list[dict]`):**
  - Her satırda: `item_code`, `item_name`, `uom`, `reserved_qty`, `line_actual_qty`, `deficit_qty`, `suggested_source_warehouse`, `suggested_batch_no`, `allocated_batches`, `has_stock`, `available_stock`, `covered_by_draft`, `draft_covered_qty`, `draft_orders`, `selectable`.

### 3.2 `erpnextkta.kta_stock.line_replenishment_service.get_leaf_warehouses`
Grup ambarı hiyerarşisi altındaki tüm fiziksel yaprak rafları (`is_group = 0`) çözümler.

- **Mantık:** Frappe `Warehouse` NestedSet indeksleri (`lft >= parent_lft AND rgt <= parent_rgt`) üzerinden 924'ün üzerindeki raf ambarını (`W1A-01-01`, `W1B-04-01` vb.) tek sorguda listeler.
- **Grup Ambarı Yasağı:** ERPNext `Stock Entry` belgelerine asla grup ambarı yazılmamasını garanti eder.

### 3.3 `erpnextkta.kta_stock.line_replenishment_service.allocate_fifo_batches` *(ve `bulk_allocate_fifo_batches`)*
Hammadde açığı için ana ambar yaprak raflarından bölünmeyen tam partileri FIFO ile tahsis eder.

- **Girdi Parametreleri (`allocate_fifo_batches`):**
  - `item_code` (str, zorunlu): Hammadde kodu.
  - `parent_warehouse` (str, zorunlu): Kaynak ambar (Genellikle `110 HAMMADDE - KTA` veya tekil yaprak raf).
  - `required_qty` (float, zorunlu): Karşılanması gereken net açık miktarı.
  - `target_warehouse` (str, opsiyonel): Döngüsel ikmali önlemek için hariç tutulacak hedef hat deposu.
- **Parti ve Bakiye Çözümleme Katmanları:**
  1. Pozitif `tabBin` filtrelemesi ardından `tabStock Ledger Entry` + `tabSerial and Batch Entry` birleşik bakiye sorgusu.
  2. Fallback: ERPNext standart `get_batch_qty(item_code=item_code)` bakiye sorgusu.
  3. Partisiz kalemler (`has_batch_no == 0`) için: Yaprak ambar `tabBin` (ve fallback `tabStock Ledger Entry`) kayıtları.
- **FIFO Sıralama Kuralı:**
  `(expiry_date is None, expiry_date, creation, batch_no, warehouse)`
- **Bölmeme & Yukarı Yuvarlama Mantığı:**
  Aday partiler FIFO sırasıyla gezilir; koli/makara bölünmeden partinin tam miktarı (`cand["qty"]`) tahsis edilir ve `accumulated_qty >= required_qty` koşulu sağlandığında döngü sonlanır.
- **Dönüş Değeri:**
  `list[{"warehouse": str, "batch_no": str | None, "allocated_qty": float}]`

### 3.4 `erpnextkta.kta_stock.line_replenishment_service.create_line_replenishment_order`
Seçilen açık kalemleri için FIFO parti ve raf tahsisini tamamlayarak `KTA Line Replenishment Order` üretir.

- **Girdi Parametreleri:**
  - `target_warehouse` (str, zorunlu): Tekil hedef WIP ambarı (`is_group = 0`).
  - `items` (list[dict] | str, zorunlu): `deficit_qty > 0` olan kalem listesi.
  - `company` (str, opsiyonel): Belirtilmezse hedef depo/varsayılan şirket çözümlenir.
  - `**_kwargs`: Eski istemci çağrılarından gelebilecek `sourcing_strategy` gibi artık kullanılmayan parametreleri sessizce yok saymak için geriye dönük uyumluluk sağlar.
- **Çoklu Parti Ayrıştırması:** Net açık birden fazla parti gerektiriyorsa (Örn: 29m açık için 15m + 15m), tek bir malzeme satırı yerine her parti ve raf lokasyonu için bağımsız birer `KTA Line Replenishment Item` child satırı açılır.
- **Sıfır Stok Güvenlik Doğrulaması:**
  - Metot, gönderilen her kalemin yaprak raflardaki (`get_warehouse_leaf_stock`) stok durumunu denetler.
  - Stoğu 0 olan kalemler filtrelenir; eğer seçilen kalemlerin hiçbirinde stok yoksa işlem `frappe.ValidationError` ile engellenir (*"Seçilen hammaddelerin hiçbirinde depoda veya hatlarda mevcut stok bulunamadı."*).
- **Dönüş Değeri (`str`):**
  - Oluşturulan belgenin adı (örn. `"LRO-2026-00001"`).

### 3.5 `erpnextkta.kta_stock.line_replenishment_service.complete_line_replenishment_picking`
Mobil PDA üzerinden toplanan partileri doğrular, tolerans denetimi yapar ve resmi transfer fişini submit eder.

- **Sıfır Manuel Giriş Denetimi:** Depocunun PDA'da barkod okuttuğu parti (`resolve_scanned_barcode`), sipariş satırındaki partiyle eşleştiği anda satır tam miktar üzerinden onaylanır.
- **Tolerans Kuralı:** Toplanan miktar `max(deficit_qty * 1.15, deficit_qty + 1.0)` sınırını aşıyorsa `frappe.ValidationError` fırlatılır.
- **Fiziksel Raf Çıkışı:** Üretilen `Stock Entry (Material Transfer)` belgesinde kaynak ambar olarak doğrudan fiziksel yaprak raflar (`W1A-01-01 - KTA`), hedef ambar olarak tekil WIP deposu yer alır.
- **Dönüş Değeri (`str`):** Oluşturulan ve submit edilen `Stock Entry` adı.

### 3.6 `erpnextkta.kta_stock.line_replenishment_service.cancel_line_replenishment_order`
İkmal siparişini ve varsa bağlı `Stock Entry` belgesini Frappe standartlarında iptal eder.

- **Girdi Parametreleri:** `order_name` (str, zorunlu)
- **Dönüş Değeri (`str`):** İptal edilen sipariş adı.

### 3.7 Diğer Yardımcı & PDA Uç Noktaları
- `erpnextkta.kta_stock.line_replenishment_service.override_item_source(order_name, item_code, new_source_warehouse, new_batch_no=None)`: Yalnızca `Draft` siparişte satırın kaynak rafını değiştirir ve yeni parti verilmemişse `allocate_fifo_batch` ile yeni FIFO partisini atar.
- `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_open_replenishment_orders()`: `Draft` / `In Progress` durumundaki açık ikmal emirlerini döner.
- `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_replenishment_order_details(order_name)`: Sipariş başlığı ve satır detaylarını döner.
- `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.resolve_scanned_barcode(barcode)`: `Item`, `KTA Stock Label` (`sut_barcode` / `name`), `Batch` (`name` / `batch_id`) ve `Item Barcode` üzerinden barkodu çözümler.

---

## 🧪 4. Test Suitleri ve Kapsam

Line Replenishment sistemi kapsamlı birim ve entegrasyon testleriyle doğrulanmıştır:

- `kta_stock/tests/test_line_replenishment_doctypes.py`:
  DocType şema doğrulaması (`sourcing_strategy`/`sourcing_type`/`free_stock_qty` temizliği dahil), tekil hedef kontrolü, toplamların hesaplanması.
- `kta_shopfloor/tests/test_reservation_deficit_service.py`:
  Netting formülü, saf `110 HAMMADDE` merkezi ambar çözümü, `**_kwargs` uyumluluğu, taslak ikmal düşümü ve mükerrer sipariş engeli (`test_draft_order_fully_covers_deficit_dedup`, `test_draft_order_partially_covers_deficit_delta`), sıfır stok kilidi.
- `kta_stock/tests/test_line_replenishment_service.py`:
  `get_leaf_warehouses` ağaç çözümlemesi, `allocate_fifo_batches` / `bulk_allocate_fifo_batches` FIFO çoklu parti tahsisi, tam koli bölmeme ve yukarı yuvarlama, `**_kwargs` geriye dönük uyumluluğu, sıfır stoklu kalemlerin sipariş oluşturmada engellenmesi.
- `kta_stock/tests/test_line_replenishment_transfer.py`:
  Fiziksel yaprak raflardan `Stock Entry` üretimi, tam parti miktarları, %15 tolerans, ters kayıt iptali.
- `kta_shopfloor/tests/test_line_replenishment_hub_page.py`:
  Masaüstü Kokpit Frappe Page yapılandırması (`/app/line-replenishment-hub`), bundle yükleme ve erişim yetkisi.
- `kta_stock/tests/test_line_replenishment_picking_page.py`:
  Mobil PDA Frappe Page arayüzü (`/app/line-replenishment-picking`), barkod çözümleme ve açık sipariş listesi.
