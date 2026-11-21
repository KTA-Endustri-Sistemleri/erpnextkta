---
layout: default
title: "Shopfloor Hub (Çoklu Görünüm) Üretim ve Teyit Motoru Geliştirici Kılavuzu"
---

<main class="container" markdown="1">

# ⚡ Shopfloor Hub (Çoklu Görünüm Üretim ve Teyit Motoru)

**`kta_shopfloor`**, ERPNext üretim akışlarında iş emri açma / stok uygunluk kontrolü / serbest bırakma (`[ ⚡ Work Orders ]`), SAP CO11N tek ekran operasyon teyidi (`[ 📋 Operations ]`), çalışma kartı ve alt operasyon analitiği (`[ ⏱️ Work Cards ]`) ile üretim hatları arası tek adımlı stok transferini (`[ 🔄 Line Transfers ]`) bir araya getiren bağımsız, modüler ve yüksek performanslı üretim kokpitidir.

---

## 🎯 1. Mimari Tasarım ve Ayrım

Bu modül, atölye sürelerini ve duruşlarını toplayan `kta_calisma_karti` modülünden ve ana hammadde ambarından (`110 HAMMADDE`) çekme ikmali yöneten `Line Replenishment Hub` akışından açık sorumluluk sınırlarıyla izole edilmiştir:

- **`kta_calisma_karti`**: Sahadaki operatör sürelerini, duruşları ve krimp/kalite testlerini toplar. `Job Card` açık ve pasif bir süre sepeti (`Job Card Time Log`) olarak çalışır.
- **`kta_shopfloor` (`Shopfloor Hub SPA` — `/app/shopfloor_hub`)**:
  - **`[ ⚡ Work Orders ]` Görünümü**: Hızlı taslak iş emri oluşturma (`CreateWorkOrderModal`), $T_{\text{prod}}$ termin hesaplama, `Bin.actual_qty` ve rezervasyon bazlı hammadde uygunluk matrisi (`WorkOrderReleasePanel`), onaylı muadil değişimi (`ItemAlternativesModal`), kardeş hat transfer kısayolu (`🔄 Hat Transferi`) ve eksik parça uyarılı serbest bırakma (*Shortage-Allowed Release*) süreçlerini yönetir.
  - **`[ 📋 Operations ]` Görünümü**: Yetkili üretim yöneticisi veya vardiya amiri tarafından yapılan fiziki sayımları onaylar; orantısal hammadde sarfiyatı (261 Backflush), mamul girişi (101 GR), teyit öncesi *Hatlar Arası Hızlı Transfer* (`MaterialStagingModal`) ve SAP CORS ters kayıt işlemlerini gerçekleştirir.
  - **`[ ⏱️ Work Cards ]` Görünümü**: İş emri ve operasyon hiyerarşisinde canlı çalışma kartlarını (`WorkCardAnalyticsPanel`), alt operasyon rota kontrol listesini (`WorkCardSubOperationCard`) ve BOM vs. fiili tüketim/hurda mutabakatını (`WorkCardMaterialReconciliation`) sunar.
  - **`[ 🔄 Line Transfers ]` (`Hatlar Arası Transfer`) Görünümü**: Yalnızca `150 ÜRETİM` yaprak hat depoları arasında (`150x ↔ 150x`) **Açık Karşılama**, **Atıl Hat Stoğu** ve **+ Manuel Transfer** modlarıyla arka plan **LIFO** parti seçimi ve rezerve stok koruması altında tek adımda `Stock Entry (Material Transfer)` oluşturur.
- **`Line Replenishment Hub & PDA` (`110 HAMMADDE → 150x`)**: Ana hammadde ambarından hatlara yapılan planlı FIFO tam koli/makara ikmalleri için [Hat İkmal Geliştirici Kılavuzu](developer_guides/line_replenishment_guide.md) kullanılır.

```
+-------------------------------------------------------------+
|                      Work Order                             |
+------------------------------+------------------------------+
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
+-----------------------+             +----------------------------------------+
|  kta_calisma_karti    |             |             kta_shopfloor              |
|  (Atölye Süre/Duruş)  |             |          (Shopfloor Hub SPA)           |
|                       |             |                                        |
| - Çalışma Kartı       |             | - Work Orders / Ops / Work Cards       |
| - Süre Sayaçları      |             | - Line Transfers (150x <-> 150x)       |
| - Krimp & QC          |             | - WorkOrderService & LineTransferSvc   |
| - Job Card Time Log   |             | - ConfirmationService & BackflushSvc   |
+-----------------------+             | - ReversalService                      |
                                      +-------------------+--------------------+
                                                          |
                                                          v
                                      +----------------------------------------+
                                      |              Stock Entry               |
                                      | - 261 Backflush (Consumption)          |
                                      | - 101 Manufacture (Finished Goods)     |
                                      | - Material Transfer (Line LIFO)        |
                                      +----------------------------------------+
```

---

## 🧱 2. Servis Mimarisi

Tüm iş mantığı servis katmanında toplanmış olup tek sorumluluk prensibine (SRP) uygun yapılandırılmıştır:

### 2.1 ConfirmationService (`services/confirmation_service.py`)
Teyit sürecini koordine eden ana orkestratördür:
- Girdi verilerini (`work_order`, `operation`, `yield_qty`, `is_final_confirmation`) doğrular.
- Submittable `KTA Production Confirmation` dokümanını oluşturur ve submit eder.
- Son operasyonda (`is_milestone`) önceki ara operasyonları `_auto_catchup_preceding_operations` ile senkronize eder.
- `BackflushService` üzerinden ilgili stok hareketini tetikler ve oluşan `Stock Entry` numarasını teyit dokümanına bağlar.
- Operasyon satırının `completed_qty` değerini ve `Job Card`'ın `total_completed_qty` değerini günceller (`docstatus = 0` korunur).
- Tüm adımları veritabanı `savepoint` koruması altında yürütür; olası bir hatada atomik rollback yapar.

### 2.2 BackflushService (`services/backflush_service.py`)
BOM reçetesine dayalı orantısal hammadde sarfiyatı ve mamul girişini hesaplar:
- **Orantısal Sarfiyat:**
  $$\text{Tüketim Miktarı} = \left( \frac{\text{Sağlam Miktar}}{\text{İş Emri Miktarı}} \right) \times \text{BOM İhtiyaç Miktarı}$$
- **Ara Operasyon:** Reçetede yalnızca o operasyona atanmış kalemler için `Material Consumption for Manufacture` stok fişi oluşturur.
- **Son Operasyon (Milestone):** Operasyonsuz genel sarfları düşer, önceki operasyon eksiklerini (*Auto-Catchup Backflush*) tamamlar, maliyetleri mamule yansıtır (WIP Rollup) ve `Manufacture` stok fişi ile ürünü `fg_warehouse` ambarına teslim alır.
- **Son Teyit (Kalanı Kapat):** `is_final=True` bayrağında küsurat yuvarlamaları engellenerek kalan tüm bakiye farkı doğrudan sarfiyata yazılır.
- **Onaylı Muadil Desteği:** `custom_original_item` ve `Item Alternative` bağlamıyla fiilen seçilen alternatif kod üzerinden tüketim yapılır.

### 2.3 ReversalService (`services/reversal_service.py`)
SAP CORS (Cancel Confirmation) modelinde hatalı teyitlerin iptal edilmesini sağlar:
- Kullanıcının yetkili rollere (`System Manager`, `Manufacturing Manager`, `KTA Çalışma Kartı Yöneticisi`) sahip olduğunu doğrular.
- Teyide ve varsa catchup teyitlerine bağlı `Stock Entry` fişlerini iptal (`cancel`) eder; stoklar ambara iade edilir.
- `Job Card` ve `Work Order` üzerindeki ilerleme miktarlarını eksiltir; `KTA Production Confirmation` dokümanını `docstatus = 2` durumuna alır.

### 2.4 WorkOrderService (`services/work_order_service.py`)
`Work Orders` görünümü için taslak iş emri oluşturma, termin hesaplama, stok uygunluk analizi, alternatif yönetimi ve serbest bırakma işlemlerini yönetir:
- **Dahili İmalat Süresi ($T_{\text{prod}}$) Çözümleme (`resolve_manufacturing_lead_days`):**
  1. `Item Customer Detail.custom_production_time_days` (müşteri belirtilmiş ve `> 0` ise)
  2. `Item.custom_manufacturing_lead_days` (`> 0` ise)
  3. Fallback: `14` gün (`DEFAULT_MANUFACTURING_LEAD_DAYS = 14`)
- **Hızlı Taslak İş Emri (`create_draft_work_order`):** Varsayılan aktif `BOM` ve şirket depolarını çözer, `auto_normalize_work_order_operations` uygular ve `Draft` iş emri açar.
- **Hedef Miktar Ölçekleme (`update_work_order_qty`):** Yalnızca `Draft` iş emirlerinde `qty`, `required_items` ve operasyon sürelerini orantısal ölçekler; atanmış alternatif hammadde seçimlerini (`custom_original_item`) korur.
- **Onaylı Muadil Yönetimi (`get_item_alternatives`, `get_work_order_item_alternatives`, `set_work_order_item_alternative`, `restore_work_order_item_original`):** Yalnızca `Draft` iş emrinde ve `consumed_qty == 0`, `transferred_qty == 0` satırlarda onaylı `Item Alternative` kodları arasında değişim veya orijinale dönüş sağlar.
- **3 Katmanlı Hammadde Stok Matrisi & Kardeş Hat Görünürlüğü (`check_work_order_material_availability`):**
  - Hattaki net kullanılabilir stok: $\text{line\_available\_qty} = \max(0, \text{Bin.actual\_qty} - \text{Bin.reserved\_qty\_for\_production})$.
  - Fabrika geneli tarama (`other_warehouses_qty`) ile kalemleri `available`, `transfer_required`, `critical_shortage` olarak sınıflar.
  - Her kalem için `is_valid_production_warehouse` filtresiyle kardeş üretim hatlarındaki stokları ayrıca işaretler: `sibling_line_warehouses` ve `has_sibling_line_stock` (`bool`) alanlarını döner.
- **Serbest Bırakma & Rezervasyon (`release_work_order_service`):** Stok tam veya `allow_shortage=1` ise `wo.submit()` ile iş emrini serbest bırakır ve eksik varsa `custom_released_with_shortage = 1` işaretler.

### 2.5 Confirmation Pre-Flight Kontrolü ve Hatlar Arası Hızlı Transfer (`services/confirmation_service.py`)
- **Teyit Öncesi Pre-Flight Kontrolü (`check_confirmation_materials`):** Teyit edilecek operasyonda tüketilecek hammaddelerin hat deposundaki fiili stoklarını denetler. Eksik varsa `get_sibling_production_sources` üzerinden yalnızca geçerli üretim/WIP depolarındaki `actual_qty`, `reserved_qty`, `free_qty` ve `available_qty` bilgilerini döner.
- **Tek Tıkla Hatlar Arası Hızlı Transfer (`stage_confirmation_materials`):** `work_order`, `transfers` ve `allow_reserved_override=0` parametrelerini alır, yazma yetkisini doğrular ve ortak `execute_line_transfer(..., work_order=wo.name)` servisini çağırarak otomatik **LIFO** parti seçimiyle `Material Transfer for Manufacture` stok fişi oluşturup submit eder.

### 2.6 LineTransferService (`services/line_transfer_service.py`)
Üretim hatları arası (`150x ↔ 150x`) tek adımlı stok transferlerinin çekirdek servis katmanıdır:

- **Çift Yönlü Üretim Deposu Güvenlik Kilidi (`is_valid_production_warehouse`):**
  - `is_group = 1` (grup depoları) ve `disabled = 1` (pasif depolar) kesinlikle reddedilir.
  - `FORBIDDEN_WAREHOUSE_KEYWORDS` (`hammadde`, `raw material`, `tesellum`, `tesellüm`, `giriş`, `giris`, `ana depo`, `central`, `stores`) depo adında, üst deposunda veya herhangi bir NestedSet atasında (`_has_forbidden_ancestor`) geçiyorsa reddedilir (`110 HAMMADDE` ve tüm alt rafları engellenir).
  - Depo `150 ÜRETİM` NestedSet ağacı altındaysa (`_is_under_150_production_tree`), `ALLOWED_PRODUCTION_KEYWORDS` (`üretim`, `uretim`, `production`, `wip`, `work in progress`) içeriyorsa veya `peer_warehouse` ile aynı kök olmayan üst gruba bağlıysa geçerli üretim hattı kabul edilir.
- **Arka Plan Otomatik LIFO Parti Çözümleme (`resolve_lifo_batches`):**
  - Parti takipli olmayan kalemlerde (`has_batch_no = 0`) doğrudan `[{"batch_no": None, "qty": req_qty}]` döner.
  - Parti takipli kalemlerde (`has_batch_no = 1`):
    1. `_query_warehouse_batch_balances` ile `tabStock Ledger Entry` ve `tabSerial and Batch Entry` üzerinden kaynak depodaki pozitif parti bakiyelerini, son giriş tarihini (`last_inward_posting_datetime`) ve kayıt zamanını (`last_inward_creation`) çeker (boşsa `_fallback_get_batch_qty` kullanır).
    2. `_filter_and_sort_lifo_candidates` ile `disabled = 0` ve süresi geçmemiş (`expiry_date >= today()` veya boş) partileri `_prior_consumed` bakiyesini düşerek **LIFO (en yeni giriş önce)** sırasına dizer:
       `(last_inward_posting_datetime DESC, last_inward_creation DESC, batch_creation DESC, batch_no DESC)`.
    3. `_allocate_lifo_from_candidates` ile makara/koli bölmeme kısıtı olmaksızın tam ihtiyaç kadar (`min(avail_qty, remaining)`) bölerek tahsis eder; böylece kaynak hattın tezgahta FIFO ile tükettiği aktif açık parti korunur.
- **3 Operasyonel Mod & Yardımcı Fonksiyonlar:**
  - `get_production_warehouses(company=None)`: Şirkete ait tüm aktif yaprak üretim hat depolarını temiz etiketlerle döner.
  - `get_line_transfer_deficits(target_warehouse)` (**Açık Karşılama / `deficit_pull`**): Hedef hattın `reserved_qty_for_production > actual_qty` açıklarını tarar, `_fetch_sibling_bins_by_item` ile yalnızca kardeş hatlarda fiili stoğu (`actual_qty > 0`) olanları `free_qty DESC, actual_qty DESC` sırasıyla listeler; serbest stoğu olanlarda `default_selected = True`, yalnız rezerve stoğu olanlarda `uses_reserved_stock = True` ve `default_selected = False` döner.
  - `get_line_idle_stock(source_warehouse)` (**Atıl Hat Stoğu / `idle_push`**): Kaynak hatta `actual_qty - reserved_qty_for_production > 0` boşta bekleyen stokları listeler; `_fetch_sibling_deficits_by_item` ile aynı malzeme için açığı bulunan en yüksek açık sahibi kardeş hattı (`suggested_target_warehouse`, `target_deficit_qty`) önerir.
  - `search_line_transfer_items(source_warehouse, search=None, limit=30)`: Manuel hat transferi modalı için kaynak depoda fiili stoğu bulunan kalemleri `actual_qty`, `reserved_qty` ve `free_qty` değerleriyle arar.
- **Tek Adımda Transfer Yürütme (`execute_line_transfer(..., split_packages=0)`):**
  - `_validate_transfer_rows`: Kaynak/hedef farklılığını, her iki deponun `is_valid_production_warehouse` kuralını ve aynı şirkete ait olduklarını doğrular.
  - `_validate_bin_and_reservation_limits`: Aynı `(item_code, source_warehouse)` çiftine denk gelen satırları toplulaştırarak `req_qty > actual_qty` ise kesin hata fırlatır; `req_qty > free_qty` durumunda `allow_reserved_override` onaylanmamışsa (`0`) `ValidationError` ile durdurur.
  - `_build_stock_entry_items_with_lifo`: Çoklu satırda aynı parti bakiyesini çift tahsis etmemek için `consumed_by_key` izleyerek `resolve_lifo_batches` ile satırları hazırlar.
  - **Varsayılan Sessiz Transfer (`split_packages = 0`):** Resmi `Stock Entry` (`work_order` varsa `"Material Transfer for Manufacture"`, yoksa `"Material Transfer"`) belgesini insert ve submit ederek tek adımda stok defterini günceller (ekstra `Repack` açmaz ve ZPL basmaz).
  - **İsteğe Bağlı Koli Bölme & Etiketleme (`split_packages = 1` → `_execute_split_line_transfer`):** `Atıl Hat Stoğu` veya `Manuel Hat Transferi` modalında kullanıcı *"Yeni Koliye Böl ve Etiket Bas"* kutucuğunu işaretlediğinde çalışır. Kısmi ayrılan veya `LEGACY` tahsisler için `relabeling_service.create_package_split_repack` (`Package Split` / `Repack`) keser ve yeni `000x` kutulara otomatik `Depo Giriş Etiketi` basar; tam kalan standart kutuları ise `Material Transfer` + `upsert_box_label` + `enqueue_print_labels_by_names` ile taşıyıp etiketler.
- **Üretim Tedarik Alanından Depoya İade (`150x → 110 HAMMADDE`):**
  - `get_raw_material_return_warehouses(company=None)` & `is_valid_raw_material_return_warehouse(warehouse, company=None)`: Şirket içi `KTA MRP Settings` (`central_warehouse` / `raw_material_warehouse` / `default_raw_material_warehouse`) veya NestedSet `"110 hammadde"` / `"110 raw material"` grubu altındaki aktif, grup-olmayan ve hurda/red olmayan (`is_rejected_warehouse = 0`) yaprak rafları çözer (`150x` üretim hatları reddedilir).
  - `execute_production_supply_return(items, target_warehouse, allow_reserved_override=0, remarks=None)`:
    - Seçili kaynak hat için `Bin` rezervasyon korumasını uygular (`allow_reserved_override = 1` onayı olmadan serbest stok aşılamaz; `actual_qty` hiçbir zaman aşılamaz).
    - Satırda açık `batch_no` verilmişse `_resolve_explicit_batch_allocation` ile, verilmemişse `resolve_lifo_batches` ile parti çözer.
    - **Depo Kapısında Sıfır Taviz Yönlendirmesi (`_is_full_remaining_standard_box`):**
      1. Standart `7+4` KTA kutusunun kaynak hattaki tam kalan bakiyesi dönüyorsa ve başka hiçbir depoda aynı partiden açık bakiye kalmıyorsa → `stock_entry_type = "Return from Production Supply"` (`purpose = "Material Transfer"`, `set_stock_entry_type()` çağrılmadan) belgesi kesilir; mevcut etiket miktar/depo ile güncellenir ve basılır.
      2. Kısmi bölünme, başka depoda bakiye kalması veya `LEGACY`/standart dışı parti durumlarında → `create_package_split_repack` ile otomatik `Package Split` (`Repack`) kesilir ve yeni `000x` / `7+4` kutu etiketlenir.
    - Tüm oluşturulan belgeleri ve basılan etiket adedini tek yanıtta (`stock_entries`, `return_stock_entry`, `split_stock_entries`, `printed_labels`, `returned_items`, `used_reserved_stock`) döner.

---

## 🔌 3. Whitelisted API Uç Noktaları (`api.py`)

| Metot | Parametreler | Açıklama |
|---|---|---|
| `get_shopfloor_hub_context` *(legacy: `get_co11n_context`)* | `barcode` (str) | Barkod, İş Emri ID veya Job Card ID üzerinden iş emri başlık bilgilerini, operasyon listesini ve kalan miktarları döner. |
| `get_active_work_orders` | `search`, `status`, `limit`, `company`, `status_filter`, `include_drafts`, `fiscal_year`, `order_by` | Kenar çubuğu için iş emirlerini filtreler (`Work Orders` görünümünde `include_drafts=1`, `Operations` görünümünde taslaklar hariç; `Work Cards` `Completed` filtresinde cari Mali Yıl + `name desc`). |
| `get_item_default_bom` | `item_code` (str), `customer` (str) | Mamulün varsayılan aktif BOM'unu, `stock_uom` bilgisini ve çözümlenen `manufacturing_lead_days` ($T_{\text{prod}}$) süresini döner. |
| `create_work_order` | `item_code`, `qty`, `bom_no`, `source_warehouse`, `wip_warehouse`, `fg_warehouse`, `planned_start_date`, `planned_end_date`, `company`, `customer` | Varsayılan BOM, depo ve $T_{\text{prod}}$ termin hesabıyla `Draft` statüsünde yeni iş emri oluşturur. |
| `check_material_availability` | `work_order` (str) | İş emri bileşenleri için `Bin` bazlı 3 katmanlı stok uygunluk matrisini, alternatif bayraklarını ve `has_sibling_line_stock` / `sibling_line_warehouses` verilerini döner. |
| `update_work_order_quantity` | `work_order` (str), `qty` (float) | `Draft` iş emrinin hedef miktarını, reçete ihtiyaçlarını ve operasyon sürelerini orantısal ölçekler (`POST`). |
| `get_alternatives` / `get_work_order_alternatives` | `item_code` / `work_order`, `row_name` | Onaylı `Item Alternative` listesini hat/diğer depo stoklarıyla birlikte döner. |
| `set_work_order_alternative` / `restore_work_order_original` | `work_order`, `row_name`, `alternative_item_code` | `Draft` iş emri satırında onaylı muadil atar veya orijinal BOM kalemine geri döner. |
| `release_work_order` | `work_order` (str), `allow_shortage` (int) | Stok uygunluğunu kontrol eder; eksik yoksa veya `allow_shortage=1` ise iş emrini submit ederek serbest bırakır. |
| `check_confirmation_materials` | `work_order` (str), `operation` (str), `yield_qty` (float), `is_final_confirmation` (int) | Teyit öncesi hat deposu malzeme uygunluğunu denetler, eksik varsa kardeş üretim (150x/WIP) depolarındaki `free_qty` / `actual_qty` kaynaklarını döner. |
| `stage_confirmation_materials` | `work_order` (str), `transfers` (list/json), `allow_reserved_override` (int) | `execute_line_transfer` üzerinden otomatik LIFO parti seçimiyle `Material Transfer for Manufacture` stok fişi oluşturup submit eder (`POST`). |
| `submit_production_confirmation` *(legacy: `submit_co11n_confirmation`)* | `payload` (dict/json) | CO11N üretim teyidini işler ve 261/101 stok hareketlerini oluşturur. |
| `cancel_production_confirmation` *(legacy: `cancel_co11n_confirmation`)* | `confirmation_name` (str) | CORS iptal mekanizmasını çalıştırır. |
| `get_production_confirmations` *(legacy: `get_co11n_confirmations`)* | `work_order` (str) | İş emrine ait tüm üretim teyitlerini ve ilişkili tüketim/mamul `Stock Entry` fişlerini döner. |
| `get_shopfloor_production_warehouses` | `company` (str, opsiyonel) | Hatlar Arası Transfer sekmesi için aktif yaprak `150x` üretim depolarını listeler. |
| `get_shopfloor_line_deficits` | `target_warehouse` (str) | Seçili hedef hattın kardeş hatlardan karşılanabilecek rezervasyon açıklarını (`deficit_pull`) döner. |
| `get_shopfloor_idle_stock` | `source_warehouse` (str) | Seçili kaynak hattaki boşta bekleyen (serbest) stokları ve önerilen açık sahibi hedef hatları (`idle_push`) döner. |
| `search_shopfloor_transfer_items` | `source_warehouse` (str), `search` (str), `limit` (int) | Manuel Hat Transferi modalında kaynak depoda stoklu malzemeleri serbest/fiziksel bakiyelerle arar. |
| `execute_shopfloor_line_transfer` | `transfers` (list/json), `allow_reserved_override` (int), `remarks` (str), `split_packages` (int) | `Stock Entry` (create) veya `Work Order` (write) yetkisini doğrulayıp LIFO parti tahsisiyle `Material Transfer` (varsayılan `split_packages=0`) ya da `Package Split` + etiket baskısı (`split_packages=1`) çalıştırır (`POST`). |
| `get_raw_material_return_warehouses` | `company` (str, opsiyonel) | `110 HAMMADDE` altındaki aktif, grup-olmayan ve `is_rejected_warehouse=0` yaprak iade raflarını döner (`Work Order` read). |
| `execute_shopfloor_supply_return` | `items` (list/json), `target_warehouse` (str), `allow_reserved_override` (int), `remarks` (str) | `150x → 110` iadelerinde tam standart kutular için `Return from Production Supply`, kısmi/`LEGACY` kutular için `Package Split` oluşturur ve Zebra etiketlerini günceller/basar (`POST`). |

---

## 🖥️ 4. Kullanıcı Arayüzü (Vue 3 SPA)

- **Desk Sayfası:** `erpnextkta/kta_shopfloor/page/shopfloor_hub/` (`/app/shopfloor_hub`)
- **Frontend Bileşenleri (`erpnextkta/public/shopfloor-hub/`):**
  - `App.vue`: 4 görünüm (`work_orders`, `operations`, `work_cards`, `line_transfers`) orkestrasyonu, modal/panel geçişleri, `@open-line-transfers` hedef hat yönlendirmesi ve teyit durumu yönetimi.
  - `components/ShopfloorNavbar.vue`: Üst navigasyon çubuğu (`[ ⚡ Work Orders ]`, `[ 📋 Operations ]`, `[ ⏱️ Work Cards ]`, `[ 🔄 Line Transfers ]`).
  - `components/WorkOrderSidebar.vue`: Bağlamsal sol iş emri kenar çubuğu (`line_transfers` görünümünde gizlenir; `Work Cards` görünümünde mali yıl filtreli `Completed` sekmesini içerir).
  - `components/CreateWorkOrderModal.vue`: Hızlı taslak iş emri açma penceresi, otomatik BOM/termin ($T_{\text{prod}}$) yükleme ve Gelişmiş Seçenekler akordeonu.
  - `components/WorkOrderReleasePanel.vue`: Hammadde Stok Uygunluk Matrisi, hedef miktar ölçekleme, onaylı muadil değişimi (`ItemAlternativesModal`), Eksik Hammadde Uyarısı (`Force Release`) modali, `Operasyon Teyidine Geç` aksiyonu ve `has_sibling_line_stock` varsa **🔄 Hat Transferi** (`Kardeş Hattan Transfer Yap`) kısayol butonu.
  - `components/ItemAlternativesModal.vue`: Onaylı tek/çift yönlü alternatif hammadde seçim ve geri yükleme modali.
  - `components/MaterialStagingModal.vue`: Operasyon teyidi öncesi hat deposu stok yetersizliğinde açılan **Hatlar Arası Hızlı Transfer** modali; kaynak hat seçiminde `Serbest` / `Fiziksel` gösterimi, rezerve aşımında `Kaynak hattın rezerve stoğundan öncelik kaydırarak kullanmayı onaylıyorum` onay kutusu ve tek tıkla LIFO transfer + otomatik teyit.
  - `components/WoStatsCard.vue`, `components/OperationsList.vue`, `components/ConfirmationPanel.vue`, `components/ConfirmationHistory.vue`: Operasyon teyidi KPI, istasyon seçimi, miktar girişi ve CORS iptal geçmişi bileşenleri.
  - `components/WorkCardAnalyticsPanel.vue`, `components/WorkCardSubOperationCard.vue`, `components/WorkCardMaterialReconciliation.vue`: Çalışma kartı, alt operasyon rota kontrolü ve malzeme/hurda mutabakat bileşenleri.
  - **Hatlar Arası Transfer (`line_transfers`) Bileşenleri (`<500` satır modüler yapı):**
    - `components/LineTransfersPanel.vue`: Ana panel orkestratörü; mod geçişi (`deficit_pull` / `idle_push`), depo yükleme, transfer/iade öncesi `findReservedOverages` kontrolü, `execute_shopfloor_line_transfer` / `execute_shopfloor_supply_return` çalıştırma, basılan etiket sayacı ve **Öncelik Kaydırma (Rezerve Stok Kullanımı) Onayı** modalı.
    - `components/LineTransferHeader.vue`: `📥 Açık Karşılama` / `📤 Atıl Hat Stoğu` segment kontrolü, `+ Manuel Transfer` ve `🔄 Yenile` aksiyonları, dinamik `150x` hat seçim pill'leri ve `🔍 Diğer Üretim Deposu...` diyaloğu.
    - `components/LineDeficitTransferTable.vue`: Seçilen hedef hattaki açıkları, kaynak `150x` hat seçicisini (`Serbest` / `Fiziksel`), `🟢 Serbestten Hazır` / `⚠️ Öncelik Kaydırma (Rezerve)` durum rozetlerini ve `⚡ Seçilenleri Hatta Aktar` aksiyon çubuğunu sunar.
    - `components/LineIdleStockTable.vue`: Seçilen kaynak hattaki `Fiziksel / Rezerve / Boşta (Serbest)` stok dağılımını, önerilen açık sahibi hedef hattı (`suggested_target_warehouse`), hedef `150x` hat seçicisini, `150x ↔ 150x` transferler için isteğe bağlı *"Yeni Koliye Böl ve Etiket Bas"* seçeneğini, **↩️ Depoya İade (110)** butonunu ve `⚡ Seçilenleri Gönder` aksiyon çubuğunu sunar.
    - `components/ProductionSupplyReturnModal.vue`: `<Teleport to="body">` modalı; `get_raw_material_return_warehouses` üzerinden yalnızca `110` yaprak rafları listeler, kaynak kutu/parti seçimi (`Otomatik (LIFO — Yeni Açılan İlk)` veya belirli `batch_no`), bakiye/rezerve uyarısı ve açıklama girişiyle `execute_shopfloor_supply_return` tetikler.
    - `components/ManualLineTransferModal.vue`: Kaynak ve hedef `150x` hat seçimi, 250ms debounced kaynak hat malzeme araması (`search_shopfloor_transfer_items`), sepete ekleme/çıkarma, satır bazlı rezerve/fiziksel stok doğrulaması, isteğe bağlı *"Yeni Koliye Böl ve Etiket Bas"* (`split_packages`) kutusu ve `⚡ Transferi Başlat` aksiyonu.
- **Üretim Paketi:** `erpnextkta/public/dist/js/shopfloor-hub.bundle.*.js`

---

## 🧪 5. Test Kapsamı

Tüm servisler, şema alanları ve API uç noktaları için kapsamlı otomatik testler mevcuttur:
- `erpnextkta/kta_shopfloor/tests/test_work_order_service.py`
- `erpnextkta/kta_shopfloor/tests/test_line_transfer_service.py`
- `erpnextkta/kta_shopfloor/tests/test_reservation_deficit_service.py`
- `erpnextkta/kta_shopfloor/tests/test_line_replenishment_hub_page.py`
- `erpnextkta/kta_shopfloor/tests/test_schema.py`
- `erpnextkta/kta_shopfloor/tests/test_confirmation_service.py`
- `erpnextkta/kta_shopfloor/tests/test_backflush_service.py`
- `erpnextkta/kta_shopfloor/tests/test_reversal_service.py`
- `erpnextkta/kta_shopfloor/tests/test_api.py`
- `erpnextkta/kta_shopfloor/doctype/kta_uretim_teyidi/test_kta_uretim_teyidi.py`

---

## 🔄 6. Canlı Mimari Ayrımı: Ana Ambar İkmali vs. Hatlar Arası Transfer

Üretim sahasındaki iki temel malzeme akışı canlı sistemde net sorumluluk sınırlarıyla ayrılmıştır:

1. **Ana Ambardan Hatlara İkmal (`110 HAMMADDE → 150x`):**
   - **Araçlar:** `Line Replenishment Hub` (`/app/line-replenishment-hub`) & `PDA Toplama` (`/app/line-replenishment-picking`)
   - **Özellikler:** Yalnızca `110 HAMMADDE` yaprak raflarından (`W1A-01-01` vb.) kapalı koli/makara bölmeden **FIFO** tahsis, taslak ikmal düşümü ve barkodlu depo toplama.
   - **Kılavuz:** [Line Replenishment Geliştirici Kılavuzu](developer_guides/line_replenishment_guide.md)
2. **Üretim Hatları Arası Transfer (`150x ↔ 150x`):**
   - **Araçlar:** `Shopfloor Hub` (`/app/shopfloor_hub`) → **`🔄 Hatlar Arası Transfer`** sekmesi (ve `Operations` sekmesindeki *Hatlar Arası Hızlı Transfer* Pre-Flight modali)
   - **Özellikler:** Sipariş/PDA adımı olmadan tek adımda resmi `Stock Entry`, arka plan otomatik **LIFO** parti bölme (kaynak hattın aktif FIFO partisini korumak için) ve serbest stok sınırı + onaylı öncelik kaydırma (`allow_reserved_override`). İsteğe bağlı *"Yeni Koliye Böl ve Etiket Bas"* (`split_packages = 1`) ile kısmi/`LEGACY` koliler `Package Split` üzerinden etiketlenebilir.
3. **Üretim Tedarik Alanından Depoya İade (`150x → 110 HAMMADDE`):**
   - **Araçlar:** `Shopfloor Hub` → **`🔄 Hatlar Arası Transfer` → `Atıl Hat Stoğu` → `↩️ Depoya İade (110)`**
   - **Özellikler:** Yalnızca `110` hammadde yaprak raflarına iade; tam standart `7+4` kutularda `Return from Production Supply` (`Material Transfer`), kısmi/paylaşımlı/`LEGACY` kutularda otomatik `Package Split` (`Repack`) ve `Depo Giriş Etiketi` basımı. (Etiket/koli kuralları için [KTA Stok ve Lojistik Kılavuzu](kta_stok_lojistik_kilavuzu.md).)

</main>
