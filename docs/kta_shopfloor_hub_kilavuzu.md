---
layout: default
title: "Shopfloor Hub (Çoklu Görünüm) Üretim ve Teyit Motoru Geliştirici Kılavuzu"
---

<main class="container" markdown="1">

# ⚡ Shopfloor Hub (Çoklu Görünüm Üretim ve Teyit Motoru)

**`kta_shopfloor`**, ERPNext üretim akışlarında iş emri açma / stok uygunluk kontrolü / serbest bırakma (`[ ⚡ Work Orders ]`), SAP CO11N tek ekran operasyon teyidi (`[ 📋 Operations ]`), çalışma kartı analitiği (`[ ⏱️ Work Cards ]`) ve genişletilebilir saha raporlarını (`[ 📊 Raporlar ]` / `Reports`) bir araya getiren bağımsız, modüler ve yüksek performanslı üretim kokpitidir.

---

## 🎯 1. Mimari Tasarım ve Ayrım

Bu modül, atölye sürelerini ve duruşlarını toplayan `kta_calisma_karti` modülünden tamamen izole edilmiştir:

- **`kta_calisma_karti`**: Sahadaki operatör sürelerini, duruşları ve krimp/kalite testlerini toplar. Job Card açık ve pasif bir süre sepeti (`Job Card Time Log`) olarak çalışır.
- **`kta_shopfloor`**:
  - **`[ ⚡ Work Orders ]` Görünümü**: Hızlı taslak iş emri oluşturma (`CreateWorkOrderModal`), $T_{\text{prod}}$ termin hesaplama, `Bin.actual_qty` bazlı hammadde uygunluk matrisi (`WorkOrderReleasePanel`) ve eksik parça uyarılı serbest bırakma (Shortage-Allowed Release) süreçlerini yönetir.
  - **`[ 📋 Operations ]` Görünümü**: Yetkili üretim yöneticisi veya vardiya amiri tarafından yapılan fiziki sayımları onaylar; orantısal hammadde sarfiyatı (261 Backflush), mamul girişi (101 GR), çoklu stok fişi takibi ve SAP CORS ters kayıt işlemlerini gerçekleştirir.
  - **`[ ⏱️ Work Cards ]` Görünümü**: İş emri ve operasyon hiyerarşisinde canlı çalışma kartlarını, alt operasyon kontrol listesini ve malzeme/hurda mutabakatını sunar.
  - **`[ 📊 Raporlar ]` (`Reports`) Görünümü**: `ReportsSidebar` üzerinden kategori bazlı deklaratif rapor kataloğunu (`reports/registry.ts`) sunar: *Üretim Teyitleri* altında `İş Emri Operasyon Tamamlanma Özeti` (aktif iş emirlerindeki tamamlanan, kısmi ve teyit almamış operasyonlar, iş emri bazlı akordeon gruplaması, iç içe CO11N detayları, `İş Emrine Git` ve düz operasyon bazlı CSV) ile *Malzeme ve Stok* altında `Eksik Malzeme ile Açılan İş Emirleri` (canlı `Bin` + `Warehouse` stok karşılama analizi, `critical` / `transfer_required` / `resolved` ayrımı, genişletilebilir hammadde tablosu ve düz `(İş Emri, Hammadde)` CSV) raporlarını (`ReportService`) yönetir.

```
+-------------------------------------------------------------+
|                      Work Order                             |
+------------------------------+------------------------------+
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
+-----------------------+             +--------------------------------+
|  kta_calisma_karti    |             |         kta_shopfloor          |
|  (Atölye Süre/Duruş)  |             |      (Shopfloor Hub SPA)       |
|                       |             |                                |
| - Çalışma Kartı       |             | - Work Orders / Ops / Cards    |
| - Süre Sayaçları      |             | - Reports (Catalog & Summary)  |
| - Krimp & QC          |             | - WorkOrderService & ReportSvc |
| - Job Card Time Log   |             | - ConfirmationService          |
+-----------------------+             | - BackflushService             |
                                      | - ReversalService              |
                                      +--------------------------------+
                                                      |
                                                      v
                                      +--------------------------------+
                                      |          Stock Entry           |
                                      | - 261 Backflush (SE)           |
                                      | - 101 Manufacture (SE)         |
                                      +--------------------------------+
```

---

## 🧱 2. Servis Mimarisi

Tüm iş mantığı servis katmanında toplanmış olup tek sorumluluk prensibine (SRP) uygun yapılandırılmıştır:

### 2.1 ConfirmationService (`services/confirmation_service.py`)
Teyit sürecini koordine eden ana orkestratördür:
- Girdi verilerini (`work_order`, `operation`, `yield_qty`, `is_final_confirmation`) doğrular.
- Submittable `KTA Production Confirmation` dokümanını oluşturur ve submit eder.
- `BackflushService` üzerinden ilgili stok hareketini tetikler ve oluşan `Stock Entry` numarasını teyit dokümanına bağlar.
- Operasyon satırının `completed_qty` değerini ve Job Card'ın `total_completed_qty` değerini günceller.
- Son operasyonda veya `is_final_confirmation` durumunda Job Card'ı ve Work Order'ı tamamlar (`Completed`).
- Tüm adımları veritabanı `savepoint` koruması altında yürütür; olası bir hatada atomik rollback yapar.

### 2.2 BackflushService (`services/backflush_service.py`)
BOM reçetesine dayalı orantısal hammadde sarfiyatı ve mamul girişini hesaplar:
- **Orantısal Sarfiyat:**
  $$\text{Tüketim Miktarı} = \left( \frac{\text{Sağlam Miktar}}{\text{İş Emri Miktarı}} \right) \times \text{BOM İhtiyaç Miktarı}$$
- **Ara Operasyon:** Reçetede yalnızca o operasyona atanmış kalemler için `Material Consumption for Manufacture` stok fişi oluşturur.
- **Son Operasyon (Milestone):** Operasyonsuz genel sarflar ile önceki ara operasyonların telafi sarflarını (`Auto-Catchup Backflush`) ayrı `Material Consumption for Manufacture` fişinden düşer; ardından `create_finished_goods_entry()` ile yalnızca mamul/hurda satırlarını içeren (`FG-Only`) `Manufacture` fişini oluşturarak ürünü `fg_warehouse` ambarına alır. Fiili maliyet dağıtımı `KTAStockEntry` tüketim havuzu motoru üzerinden yapılır.
- **Son Teyit (Kalanı Kapat):** `is_final=True` bayrağında küsurat yuvarlamaları engellenerek kalan hammadde miktar bakiye farkı doğrudan sarfiyata yazılır. Ayrıca `create_finished_goods_entry()`, final / kısa kapanış teyitlerinde `se.flags.kta_is_final_confirmation` bayrağını `Stock Entry` belgesine ileterek kalan tüketim maliyet havuzunun son partide sıfırlanmasını sağlar.
- **Otomatik FIFO:** `auto_create_serial_and_batch_bundle_for_outward = 1` ayarıyla parti/lot tahsisi ERPNext yerel motoru tarafından FIFO ile gerçekleştirilir.

### 2.3 ReversalService (`services/reversal_service.py`)
SAP CORS (Cancel Confirmation) modelinde hatalı teyitlerin iptal edilmesini sağlar:
- Kullanıcının yetkili rollere (`System Manager`, `Manufacturing Manager`, `KTA Çalışma Kartı Yöneticisi`) sahip olduğunu doğrular.
- Teyide bağlı `Stock Entry` fişlerini (`Material Consumption for Manufacture` ve `Manufacture`) iptal (`cancel` / `docstatus = 2`) eder; stoklar otomatik olarak ambara iade edilir. İptal edilen fişler `KTAStockEntry` maliyet havuzu sorgularının (`docstatus = 1`) dışında bırakıldığı için yeniden teyit verildiğinde maliyetler sıfırdan tutarlı hesaplanır.
- Job Card ve Work Order üzerindeki ilerleme miktarlarını eksiltir.
- `KTA Production Confirmation` dokümanını iptal durumuna (`docstatus = 2`) alır.

### 2.4 WorkOrderService (`services/work_order_service.py`)
`Work Orders` görünümü için taslak iş emri oluşturma, termin hesaplama, stok uygunluk analizi ve serbest bırakma işlemlerini yönetir:
- **Dahili İmalat Süresi ($T_{\text{prod}}$) Çözümleme (`resolve_manufacturing_lead_days`):**
  1. `Item Customer Detail.custom_production_time_days` (müşteri bilgisi sağlanmış ve `> 0` ise)
  2. `Item.custom_manufacturing_lead_days` (`> 0` ise; `kta_mrp/custom/item.json`)
  3. Fallback: `14` gün (`DEFAULT_MANUFACTURING_LEAD_DAYS = 14`)
- **Hızlı Taslak İş Emri (`create_draft_work_order`):** Varsayılan aktif `BOM` ve şirket depolarını (`Manufacturing Settings` / `Item Default` / aktif depo) çözer, `planned_end_date = planned_start_date + T_prod` hesabıyla `Draft` iş emri açar.
- **3 Katmanlı Hammadde Stok ve Hat Besleme Matrisi (`check_work_order_material_availability`):**
  - **Hattaki Net Kullanılabilir Stok:** $\text{line\_available\_qty} = \max(0, \text{Bin.actual\_qty} - \text{Bin.reserved\_qty\_for\_production})$. Açık üretim rezervasyonları düşülerek serbest stok hesaplanır.
  - **Fabrika Geneli Depo Taraması:** Şirketin diğer tüm aktif ve non-group depolarındaki serbest stoklar ($\max(0, \text{actual\_qty} - \text{reserved\_qty})$) taranır (`other_warehouses_qty`).
  - **3 Kademeli Durum Sınıflandırması:**
    1. `available` (Hatta Mevcut): `line_available_qty >= required_qty`.
    2. `transfer_required` (Transfer Edilebilir): Hattaki net stok yetersiz ancak fabrika genelinde karşılanabilir (`line_available_qty + other_warehouses_qty >= required_qty`).
    3. `critical_shortage` (Fabrikada Yok): Şirketin tüm depolarında dahi yetersiz (`line_available_qty + other_warehouses_qty < required_qty`).
  - Kalem bazlı `shortage_qty`, `coverage_percent`, `availability_status` ve genel `overall_readiness_percent` metriklerini döner.
- **Serbest Bırakma & Rezervasyon (`release_work_order_service`):**
  - Stok tam ise `wo.submit()` (`docstatus = 1`) ile iş emrini serbest bırakır.
  - Eksik hammadde varken `allow_shortage=0` gönderilirse `ValidationError` fırlatır; `allow_shortage=1` onayında `Work Order.custom_released_with_shortage = 1` işaretler, eksik listesini `Comment` olarak aktivite geçmişine ekler ve submit eder.
  - **Stok Rezervasyonu ve Tüketim Yaşam Döngüsü:** İş emri submit edildiğinde ERPNext standart motoru ilgili depodaki `Bin.reserved_qty_for_production` değerini artırarak hammadde rezervasyonu oluşturur. `Operations` sekmesinden backflush malzeme tüketimi (`Material Consumption for Manufacture`) yapıldığında `consumed_qty` artar ve rezervasyon otomatik olarak tüketilen miktar kadar azalır (`reserved_qty_for_production = required_qty - consumed_qty`). Teyit SAP CORS ile iptal edildiğinde rezervasyon otomatik olarak eski haline döner.
- **İş Emri Yazdırma Seçenekleri (`get_work_order_print_options`):** `Print Settings` (`allow_print_for_draft`, `allow_print_for_cancelled`, `with_letterhead`) ayarlarını, `Work Order` okuma/yazdırma yetkilerini ve taslak/iptal belge durumu engelini (`can_print`) denetler. Aktif `Work Order` `Print Format` kayıtlarını (varsayılan şablon en üstte, `"Standard"` her zaman dahil; `default_print_language`, `raw_printing`, `print_format_builder_beta` alanlarıyla) ve aktif `Letter Head` listesini (`default_letter_head` dahil) döner.

### 2.5 Confirmation Pre-Flight Kontrolü ve Hat İkmal Modali (`services/confirmation_service.py`)
- **Teyit Öncesi Pre-Flight Kontrolü (`check_confirmation_materials`):** Teyit verilmek istenen operasyonda tüketilecek reçete hammaddelerinin hat deposundaki (`wip_warehouse`) fiili serbest stoklarını hesaplar.
- **Kullanıcı Onaylı Hat İkmal Modali (User-Confirmed Staging):** Hat deposunda eksik hammadde tespit edildiğinde otomatik açılır (`MaterialStagingModal.vue`).
- **İş Kuralı (Yalnızca WIP Depolar Arası Transfer):** Hat ikmali transferleri **yalnızca üretim/WIP depoları** arasında yapılabilir (örn. `WIP Hat A` → `WIP Hat B`). Ana hammadde ve merkez depolardan operatör tarafından doğrudan çekim yapılması engellenmiştir. Diğer hatlarda da stok yoksa modal uyarı verir ve ambar biriminden resmi ikmal talep edilmesini ister.
- **Tek Tıkla Hat İkmali ve Otomatik Teyit (`stage_confirmation_materials`):** Kullanıcı kaynak üretim deposunu ve transfer miktarlarını onayladığında, sistem tek tıkla `Material Transfer for Manufacture` stok fişi oluşturup submit eder, ardından bekleyen operasyon teyidini otomatik olarak tamamlar.

### 2.6 KTAStockEntry Override — Çoklu / Kısmi `Manufacture` Stoklaştırma ve Fiili Tüketim Maliyetleme (`overrides/KTAStockEntry.py`)
`Manufacturing Settings` altında `material_consumption = 1` ve `get_rm_cost_from_consumption_entry = 1` etkinken çoklu ve kısmi `Manufacture` fişlerinin gerçek fiili tüketim maliyetleriyle stoklanmasını sağlar:

- **Standart Sınırlamanın Aşılması ve Korumanın Sürdürülmesi:**
  - ERPNext çekirdeğinin `"Only one Manufacture entry can be created against the Work Order"` engeli `KTAStockEntry.get_basic_rate_for_manufactured_item()` override'ı ile kaldırılır; aynı iş emrinde birden fazla kısmi `FG-Only Manufacture` fişi (örn. `1.000` adetlik iş emrinde `300 + 300 + 400` adet) açılabilir.
  - `get_work_order_raw_materials()`, `get_unconsumed_raw_materials()`, `add_transfered_raw_materials_in_items()`, `validate_component_and_quantities()` ve `validate_raw_materials_exists()` kancaları `FG-Only Manufacture` akışıyla uyumludur.
  - Buna karşın `_validate_no_raw_materials_in_manufacture_entry()` ile standart koruma korunur: tüketim fişi varken `Manufacture` fişine doğrudan hammadde satırı (`not is_finished_item and not is_scrap_item`) eklenmesi `ValidationError` ile engellenmeye devam eder.
  - `BackflushService.create_finished_goods_entry()`, final ve kısa kapanış (short-close) teyitlerinde `se.flags.kta_is_final_confirmation` bayrağını iletir.

- **Fiili Tüketim Havuzu Maliyetleme Formülü:**
  - **Toplam Fiili Tüketim Maliyeti (`_get_total_consumed_cost`):** İş emrine bağlı onaylı (`docstatus = 1`) `Material Consumption for Manufacture` fişlerindeki çıkış satırlarının (`s_warehouse != ''`) `valuation_rate * transfer_qty` toplamıdır.
  - **Önceki FG-Only Manufacture Maliyeti (`_get_previous_fg_only_manufacture_cost`):** Aynı iş emrine bağlı, mevcut fiş hariç onaylı (`docstatus = 1`) ve hammadde çıkışı içermeyen (`total_outgoing_value == 0` ve `s_warehouse` satırı olmayan) `Manufacture` fişlerindeki mamul/hurda (`is_finished_item = 1` veya `is_scrap_item = 1`) `basic_amount` toplamıdır.
  - **Kalan Dağıtılmamış Havuz:**
    $$\text{Kalan Dağıtılmamış Havuz} = \max(0,\; \text{Toplam Fiili Tüketim Maliyeti} - \text{Önceki FG-Only Manufacture Maliyeti})$$
    *(İlgili envanter düzeltme / WIP hesabında bekleyen net fiili hammadde maliyeti.)*
  - Atanan tutardan hurda (`is_scrap_item`) ve manuel fiyatlı mamul maliyetleri düşüldükten sonra `basic_rate = cost_left / finished_item_qty` hesaplanır (`via_repost` sırasında `cost_left = max(cost_left, 0)` uygulanır).

- **Kısmi Stoklaştırma, Önden Giden Ara Operasyon Koruması ve Final Kapanış:**

| Durum | Koşul | Maliyetleme Davranışı |
|---|---|---|
| **Ara / Kısmi Stoklaştırma** | Final değil ve `Kalan Dağıtılmamış Havuz > 0` | `_get_proportional_actual_cost()` çalışır. Önden tüketim yapan ara operasyon (örn. `OP10` `1.000` adedi tüketirken `OP30` `300` adet stoklaştırıyorsa) tüm havuzu kısmi partiye yüklemez. Onaylı `Material Consumption` satırlarından her bileşen için (muadiller `custom_original_item` / `original_item` ile eşlenerek) ağırlıklı ortalama fiili çıkış birim maliyeti hesaplanır; `(partideki_miktar / is_emri_miktari) * recete_ihtiyac_miktari` ile çarpılarak **Orantısal Fiili Maliyet** bulunur ve `min(Kalan Dağıtılmamış Havuz, Orantısal Fiili Maliyet)` partiye atanır (`örnek birim maliyet` korunur). |
| **Final / Kısa Kapanış** | `se.flags.kta_is_final_confirmation`, bağlı `KTA Production Confirmation.is_final_confirmation = 1` veya `produced_qty + parti_miktarı >= wo.qty` | `_is_final_manufacture_entry()` tetiklenir ve `Kalan Dağıtılmamış Havuz` tutarının tamamı son `Manufacture` partisine aktarılır. Kısa kapanışta (örn. `300 + 500 = 800 < 1.000`) dahi envanter düzeltme / WIP hesabı kuruşu kuruşuna sıfırlanır (`0.00`). |
| **Havuz Sıfır (Fallback)** | `Kalan Dağıtılmamış Havuz <= 0` | Hata fırlatılmadan `_get_fallback_bom_cost()` üzerinden BOM tabanlı maliyete veya BOM/miktar yoksa güvenli `0` değerine düşülür. |

- **Eski Belgeli (`Legacy Manufacture`) İş Emirleri ve SAP CORS İptal Davranışı:**
  - **Legacy İzolasyonu:** Önceden standart hammadde satırlı `Manufacture` fişi (`total_outgoing_value > 0` veya `s_warehouse` satırı içeren) işlenmiş eski iş emirlerinden Shopfloor Hub üzerinden devam edildiğinde, eski fişler kendi içinde muhasebesel olarak dengelendiği için `Önceki FG-Only Manufacture Maliyeti` havuzuna dahil edilmez; yeni partiler yalnızca yeni `Material Consumption` fişlerinden doğru fiili maliyetle stoklanır.
  - **SAP CORS İptal (`docstatus = 2`):** İptal edilen `Stock Entry` fişleri (`docstatus = 2`) tüm maliyet havuzu sorgularının (`entry.docstatus = 1`) dışında bırakılır; yeniden teyit verildiğinde maliyetler sıfırdan tutarlı biçimde hesaplanır.

### 2.7 ReportService (`services/report_service.py`)
`[ 📊 Raporlar ]` görünümündeki iki ana raporun verilerini N+1 sorgu olmadan sınırlı toplu SQL ile üretir:
- **1. İş Emri Operasyon Tamamlanma Özeti (`get_operation_completion_report`):**
  - **Yetki & Parametre Doğrulama:** `Work Order` ve `KTA Production Confirmation` okuma izinlerini (`frappe.has_permission(..., "read", throw=True)`) ve `status_filter` (`completed`, `partial`, `unconfirmed`, `all`; geçersiz değerde `ValidationError(_("Geçersiz durum filtresi: {0}"))`) değerini doğrular.
  - **Yalnızca Aktif İş Emri Kapsamı:** `_fetch_active_wo_operations()` onaylı ve aktif iş emirlerinin (`wo.docstatus = 1`, `wo.status IN ('Not Started', 'In Process')`) **tüm** operasyonlarını — `completed_qty = 0` ve sıfır teyitli operasyonlar dahil (`Teyit Olmayanlar` / `unconfirmed` ve `Tümü` / `all` altında) — ve `Work Order.custom_released_with_shortage` ile `Work Order.creation` (`wo_creation`, `_format_datetime_str()` ile `YYYY-MM-DD HH:MM:SS` biçimli) alanlarını çeker; `Completed`, `Closed`, `Cancelled`, `Stopped` ve `Draft` iş emirleri kapsam dışındadır.
  - **Sınırlı Toplu SQL (Zero N+1):** Toplam 3 sınırlı sorgu ile (`_fetch_active_wo_operations`, `_fetch_confirmation_aggregates`, `_fetch_legacy_manufacture_aggregates`) hem `KTA Production Confirmation` (`docstatus = 1`) toplamlarını hem de CO11N dışındaki standart `Manufacture` fişlerini (`source_type`: `co11n` / `legacy` / `mixed` / `none`) derler.
  - **Durum Sınıflandırması ve Ön/Son Filtre Matematiği:**
    - `is_completed`: `(wo_qty > 0 and completed_qty >= wo_qty) or has_final == 1`; `is_unconfirmed`: `(not is_completed) and completed_qty <= 0 and confirmed_qty <= 0`.
    - `status`: `"completed"`, `"unconfirmed"` (`source_type = "none"` — aynı iş emrindeki başka operasyonlara ait `Manufacture` fişlerinden tarih/miktar/kullanıcı devralmaz) veya `"partial"`. Her satır pasif gösterge için `custom_released_with_shortage` (`0`/`1`) ve `wo_creation` alanlarını içerir.
    - `filter_options` (`operations`, `workstations`) aktif iş emirlerindeki tüm operasyon satırlarından üretilir.
    - `operation`, `workstation`, `from_date` / `to_date` (`last_posting_date` üzerinde) ve `search` (`work_order`, `production_item`, `item_name`, `operation`, `workstation`, `last_confirmed_by`) filtreleri uygulandıktan sonra `counts.shortage` / `summary.shortage_operations` (`custom_released_with_shortage == 1`) hesaplanır. Geriye dönük uyumluluk için API parametresi olarak `only_shortage` (`0`/`1`) desteklenmeye devam etse de arayüzdeki filtre düğmesi özel `material_shortage` raporuna taşınmıştır.
    - Ardından `status_filter` öncesindeki `counts` (`completed`, `partial`, `unconfirmed`, `all`) ile `summary.completed_operations`, `summary.partial_operations` ve `summary.unconfirmed_operations` hesaplanır; son olarak `status_filter` uygulanarak iş emri düzeyinde varsayılan `wo_creation DESC, work_order DESC` (operasyon içinde `sequence_id ASC`) sırasıyla `rows`, `summary.unique_work_orders` ve `summary.total_confirmed_qty` döner.
- **2. Eksik Malzeme ile Açılan İş Emirleri (`get_material_shortage_report`):**
  - **Yetki & Parametre Doğrulama:** `Work Order` okuma iznini (`frappe.has_permission("Work Order", "read", throw=True)`) ve `shortage_filter` (`VALID_SHORTAGE_FILTERS`: `all`, `active_shortage`, `critical`, `transfer_required`, `resolved`; geçersiz değerde `ValidationError(_("Geçersiz eksik malzeme filtresi: {0}"))`) değerini doğrular.
  - **Kapsam ve Sınırlı Toplu SQL (≤ 4 Sorgu / Zero N+1):** Yalnızca `docstatus = 1`, `status IN ('Not Started', 'In Process')` ve `COALESCE(custom_released_with_shortage, 0) = 1` koşullarını sağlayan aktif iş emirlerini (`wo.creation` dahil) çeker; toplam ≤ 4 sınırlı toplu sorguyla (`_resolve_report_company`, `_fetch_active_shortage_work_orders`, `_fetch_work_order_items_bulk`, `_fetch_bin_stock_maps` — `tabBin` INNER JOIN `tabWarehouse` `is_group = 0 AND disabled = 0`) tüm iş emri, hammadde satırı ve canlı depo bakiyelerini derler.
  - **Canlı Stok Hesaplaması & Kalem/İş Emri Sınıflandırması:** Her `Work Order Item` için `remaining_required_qty = max(0, required_qty - consumed_qty)`, hedef kaynak/hat deposu bakiyesi `line_actual_qty`, aynı şirkete ait diğer aktif ve grup dışı depolardaki toplam stok `other_warehouses_qty`, `shortage_qty = max(0, remaining_required_qty - line_actual_qty)` ve `coverage_pct` hesaplanır. Kalem `availability_status` değerleri `available` (`shortage_qty <= 0`), `transfer_required` (`line_actual_qty + other_warehouses_qty >= remaining_required_qty`) veya `critical_shortage` (şirket toplam stoğu yetersiz) olarak sınıflandırılıp şiddet sırasına göre sıralanır. İş emri düzeyi (`shortage_status`) ise kalem kırılımına göre `critical`, `transfer_required` veya `resolved` olarak belirlenir (`readiness_pct` ortalama kalem karşılama yüzdesidir; satır ayrıca `YYYY-MM-DD HH:MM:SS` biçimli `wo_creation` alanını içerir).
  - **Filtreleme & Sıralama:** `warehouse` (kalem `source_warehouse` eşleşmesi) ve `search` (iş emri, mamul kodu/adı, hammadde kodu/adı, operasyon, kaynak depo) filtrelerinden sonra `counts` (`all`, `active_shortage`, `critical`, `transfer_required`, `resolved`), seçili `shortage_filter` satırları, `summary` ve `filter_options.warehouses` döner; satırlar varsayılan olarak en yeni iş emirlerini en üste getirecek şekilde `wo_creation DESC, work_order DESC` sırasıyla listelenir.

---

## 🔌 3. Whitelisted API Uç Noktaları (`api.py`)

| Metot | Parametreler | Açıklama |
|---|---|---|
| `get_shopfloor_hub_context` *(legacy: `get_co11n_context`)* | `barcode` (str) | Barkod, İş Emri ID veya Job Card ID üzerinden iş emri başlık bilgilerini, operasyon listesini ve kalan miktarları döner. |
| `get_active_work_orders` | `search` (str), `status` (str), `limit` (int), `company` (str), `status_filter` (str), `include_drafts` (int) | Kenar çubuğu için iş emirlerini filtreler (`Work Orders` görünümünde `include_drafts=1`, `Operations` görünümünde taslaklar hariç). Pasif ve tamamlanmış (`Completed`, `Closed`, `Cancelled`, `Stopped`) iş emirleri filtrelenir; varsayılan olarak ve `limit=0` ile tüm aktif kayıtlar çekilir. |
| `get_item_default_bom` | `item_code` (str), `customer` (str) | Mamulün varsayılan aktif BOM'unu, `stock_uom` bilgisini ve çözümlenen `manufacturing_lead_days` ($T_{\text{prod}}$) süresini döner. |
| `create_work_order` | `item_code`, `qty`, `bom_no`, `source_warehouse`, `wip_warehouse`, `fg_warehouse`, `planned_start_date`, `planned_end_date`, `company`, `customer` | Varsayılan BOM, depo ve $T_{\text{prod}}$ termin hesabıyla `Draft` statüsünde yeni iş emri oluşturur. |
| `check_material_availability` | `work_order` (str) | Seçili iş emrinin bileşenleri için `Bin.actual_qty` bazlı stok uygunluk matrisini ve hazır olma yüzdesini döner. |
| `release_work_order` | `work_order` (str), `allow_shortage` (int) | Stok uygunluğunu kontrol eder; eksik yoksa veya `allow_shortage=1` ise iş emrini submit ederek serbest bırakır. |
| `get_work_order_print_options` | `work_order` (str, opsiyonel) | Aktif `Work Order` `Print Format` şablonlarını (varsayılan ilk sırada, `"Standard"` her zaman dahil), aktif `Letter Head` kayıtlarını, `Print Settings` bayraklarını (`allow_print_for_draft`, `allow_print_for_cancelled`, `with_letterhead`) ve `can_print` yetki/durum bilgisini döner. |
| `check_confirmation_materials` | `work_order` (str), `operation` (str), `yield_qty` (float), `is_final_confirmation` (int) | Teyit öncesi hat deposu malzeme uygunluğunu denetler, eksik varsa alternatif üretim (WIP) depolarındaki stokları döner. |
| `stage_confirmation_materials` | `work_order` (str), `transfers` (list[dict]) | Hat deposuna ikmal için `Material Transfer for Manufacture` stok fişi oluşturup submit eder. |
| `submit_production_confirmation` *(legacy: `submit_co11n_confirmation`)* | `payload` (dict/json) | CO11N üretim teyidini işler ve stok hareketini oluşturur. |
| `cancel_production_confirmation` *(legacy: `cancel_co11n_confirmation`)* | `confirmation_name` (str) | CORS iptal mekanizmasını çalıştırır. |
| `get_production_confirmations` *(legacy: `get_co11n_confirmations`)* | `work_order` (str) | İş emrine ait tüm üretim teyitlerini ve ilişkili tüketim/mamul `Stock Entry` fişlerini döner. |
| `get_operation_completion_report` | `status_filter`, `operation`, `workstation`, `from_date`, `to_date`, `search`, `company`, `only_shortage` | Onaylı ve aktif iş emirlerinin (`Not Started` / `In Process`) tüm operasyonları (`completed_qty = 0` dahil; `completed`/`partial`/`unconfirmed`/`all` ve geriye dönük uyumlu `only_shortage` `0`/`1`) için `wo_creation` (`Work Order.creation`, `YYYY-MM-DD HH:MM:SS`) dahil tamamlanma özetini (`wo_creation DESC, work_order DESC`; operasyon içi `sequence_id ASC` sıralı; `custom_released_with_shortage` dahil), KPI toplamlarını (`summary`), sekme sayaçlarını (`counts`) ve filtre seçeneklerini (`filter_options`) döner. |
| `get_material_shortage_report` | `shortage_filter`, `warehouse`, `search`, `company` | `custom_released_with_shortage = 1` ile serbest bırakılmış aktif iş emirlerinin (`Not Started` / `In Process`) ≤ 4 sınırlı toplu SQL sorgusuyla canlı `Bin` + `Warehouse` stok karşılama analizini (`wo_creation`, `line_actual_qty`, `other_warehouses_qty`, kalem `availability_status`: `critical_shortage`/`transfer_required`/`available`, iş emri `shortage_status`: `critical`/`transfer_required`/`resolved`), varsayılan `wo_creation DESC, work_order DESC` sırasıyla `summary`, `counts` ve `filter_options.warehouses` bilgilerini döner. |

---

## 🖥️ 4. Kullanıcı Arayüzü (Vue 3 SPA)

- **Desk Sayfası:** `erpnextkta/kta_shopfloor/page/shopfloor_hub/` (`/app/shopfloor_hub`)
- **Frontend Bileşenleri (`erpnextkta/public/shopfloor-hub/`):**
  - `App.vue`: Çoklu görünüm (`work_orders`, `operations`, `work_cards`, `reports`) orkestrasyonu, modal/panel geçişleri, rapor görünümünden `İş Emrine Git` çapraz gezinmesi (`handleOpenWorkOrderFromReport`) ve teyit durumu yönetimi (`ShopfloorAlerts.vue` ayrıştırılarak `<= 500` satır korunur).
  - `components/ShopfloorNavbar.vue`: Üst navigasyon çubuğu (`[ ⚡ Work Orders ]`, `[ 📋 Operations ]`, `[ ⏱️ Work Cards ]`, `[ 📊 Raporlar ]` [`Reports`]).
  - `components/ShopfloorAlerts.vue`: Hata ve teyit başarı bildirim şeridi (bağlı `KTA Production Confirmation` ve `Stock Entry` bağlantılarıyla).
  - `components/WorkOrderSidebar.vue`: Bağlamsal sol iş emri kenar çubuğu (`Work Orders`: `Tümü`, `Taslak`, `Serbest` + `+ Yeni İş Emri Aç` butonu; `Operations`: `Tümü`, `Devam Eden`, `Başlanmamış` [`Not Started`]; `Work Cards`: mali yıl filtreli `Completed` sekmesi).
  - `reports/registry.ts`, `reports/operationFormatters.ts`, `reports/tableSort.ts` & `reports/csvExport.ts`: Genişletilebilir rapor kataloğu (`REPORT_CATALOG` — `Üretim Teyitleri` altında `operation_completion` ve `Malzeme ve Stok` altında 2. özel rapor `material_shortage`), `groupRowsByWorkOrder` ile iş emri bazlı akordeon gruplama/sıralama/ortalama ilerleme yardımcıları, `toggleSortState` / `sortItems` (`SortDirection`: `asc` / `desc`) ile etkileşimli tablo sıralama yardımcıları ve UTF-8 BOM + formül enjeksiyon korumalı düz CSV dışa aktarım yardımcısı (`exportRowsToCsv`).
  - `components/ReportsSidebar.vue`, `components/ReportsWorkspace.vue` & `components/reports/SortableTh.vue`: `Reports` görünümünde sol çekmece rapor kataloğu (kategori gruplama, `Rapor Ara…`, aktif rozet), dinamik rapor render alanı ve her iki raporda artan/azalan (`asc` / `desc`) sütun başlığı sıralaması sağlayan yeniden kullanılabilir `SortableTh.vue` başlık bileşeni.
  - `components/reports/OperationCompletionReport.vue`, `components/reports/OperationCompletionFilters.vue`, `components/reports/OperationCompletionGroupRows.vue` & `components/reports/OperationCompletionDetail.vue`: **İş Emri Operasyon Tamamlanma Özeti** tablosu (`Tamamlananlar`, `Kısmi Üretimler`, `Teyit Olmayanlar`, `Tümü`), 5'li KPI şeridi (`Teyit Olmayan Operasyon` dahil), `OperationCompletionFilters.vue` içine ayrıştırılmış çoklu filtre çubuğu (`operation`, `workstation`, `from_date`, `to_date`, `search`; önceden burada yer alan `⚠️ Eksik Malzemeliler` açma/kapama düğmesi özel `material_shortage` raporuna taşındığı için arayüzden kaldırılmıştır), eksik malzeme ile serbest bırakılmış iş emirlerinde `.wo-cell` içindeki pasif `⚠️ Eksik Malzeme` uyarı etiketi, `groupRowsByWorkOrder` üzerinden her iş emri için tek akordeon satırı ve **`Oluşturma`** (`wo_creation`) dahil **9 sütunlu** iş emri tablosu (varsayılan `wo_creation DESC, work_order DESC` sıralı; `SortableTh.vue` / `tableSort.ts` ile tüm 7 veri sütun başlığında etkileşimli `asc`/`desc` sıralama; toplam `{0} Operasyon`, mini durum özet rozetleri `✓ completed_count` / `◐ partial_count` / `○ unconfirmed_count`, ortalama ilerleme `overall_pct` ve başlıkta `Tümünü Genişlet` / `Tümünü Daralt` [`toggleExpandAll`] düğmesi), iş emri genişletildiğinde `OperationCompletionGroupRows.vue` içinde `sequence_id` değerine göre artan sırada (eşitlikte operasyon adına göre alfabetik) listelenen alt operasyon satırları ve her alt satırda iç içe `<OperationCompletionDetail />` tembel (lazy) CO11N & `Stock Entry` detay paneli (`source_type === "none"` satırlarında ek `get_production_confirmations` ağ çağrısı yapılmadan kısa devre), `İş Emrine Git` aksiyonu ve e-tablo uyumluluğu için `"Oluşturma Tarihi"` (`wo_creation`), `"Eksik Malzeme"` (`Evet` / `Hayır`) ve `"Teyit Yok"` sütun/etiketleriyle düz (flat) operasyon bazlı satırları dışa aktarmayı sürdüren `CSV İndir`.
  - `components/reports/MaterialShortageReport.vue` & `components/reports/MaterialShortageItemsRow.vue`: **Eksik Malzeme ile Açılan İş Emirleri** (`material_shortage` — `Malzeme ve Stok` kategorisi) raporu; durum sekmeleri (`Tümü`, `Kritik Eksik`, `Transfer Gerekli`, `Stok Tamamlandı`), 4'lü KPI şeridi (`Eksikle Açılan İş Emri`, `Kritik Eksik`, `Transfer Gerekli`, `Toplam Eksik Kalem`), arama (`İş Emri, Ürün veya Hammadde Ara…`) ve `Tüm Kaynak Depolar` (`warehouse`) filtre çubuğu, **`Oluşturma`** (`wo_creation`) dahil **9 sütunlu** iş emri tablosu (varsayılan `wo_creation DESC, work_order DESC` sıralı; `SortableTh.vue` / `tableSort.ts` ile tüm 7 veri sütununda etkileşimli `asc`/`desc` sıralama), `Tümünü Genişlet` / `Tümünü Daralt` başlık düğmesi, `{0}/{1} Eksik` & `readiness_pct` ilerleme çubuğu, `İş Emrine Git` aksiyonu, genişletilebilir `MaterialShortageItemsRow.vue` alt tablosu (`Kalan İhtiyaç`, `Hat Deposu` [`line_actual_qty`], `Diğer Depolar` [`other_warehouses_qty`], `Eksik Miktar`, `Durum`: `Kritik Eksik` / `Transfer Gerekli` / `Mevcut`) ve `"Oluşturma Tarihi"` (`wo_creation`) dahil düz `(İş Emri, Hammadde)` satırları üreten `CSV İndir` (`shopfloor-eksik-malzeme-YYYY-MM-DD.csv`).
  - `components/CreateWorkOrderModal.vue`: Hızlı taslak iş emri açma penceresi, otomatik BOM/termin ($T_{\text{prod}}$) yükleme ve Gelişmiş Seçenekler akordeonu.
  - `components/WorkOrderReleasePanel.vue`: Hammadde Stok Uygunluk Matrisi, hazır olma ilerleme çubuğu, Eksik Hammadde Uyarısı (`Force Release`) modali, `Stok Yenile` yanında `WorkOrderPrintButton` (`🖨️ Yazdır`) ve `Operasyon Teyidine Geç` aksiyonu.
  - `components/MaterialStagingModal.vue`: Hat deposu (`wip_warehouse`) stok yetersizliğinde açılan kullanıcı onaylı ikmal penceresi; kaynak WIP depo seçimi ve tek tıkla `Material Transfer for Manufacture` transferi.
  - `components/WoStatsCard.vue`: İş emri başlık, sağ üst başlık çubuğunda kompakt `WorkOrderPrintButton` (`🖨️ Yazdır`) ve özet metrik kartı.
  - `components/WorkOrderPrintButton.vue`: Hem `[ ⚡ Work Orders ]` (`WorkOrderReleasePanel.vue`, `Stok Yenile` yanında) hem de `[ 📋 Operations ]` (`WoStatsCard.vue` başlık çubuğunda `compact` modda) görünümlerinde `🖨️ Yazdır` tetikleyicisini sunar.
  - `components/WorkOrderPrintModal.vue`: `erpnextkta.kta_shopfloor.api.get_work_order_print_options` ile aktif `Print Format` / `Letter Head` ve `Print Settings` izinlerini yükler; seçilen son şablonu tarayıcı `localStorage` (`kta_shopfloor_wo_print_format`) içinde saklar; opsiyonel `Antetli Yazdır` / `Antet` seçimi, canlı HTML `<iframe src="/printview?...">` önizlemesi (İş Emri ve Job Card barkodlarını `JsBarcode` ile oluşturur; `raw_printing` şablonlarında bilgilendirme uyarısı gösterir), `Tam Sayfa Önizle`, doğrudan tarayıcı `Yazdır` (`trigger_print=1`) ve `PDF İndir` (`frappe.utils.print_format.download_pdf` / `frappe.utils.weasyprint.download_pdf`) aksiyonlarını sunar.
  - `components/OperationsList.vue`: Operasyon adımları ve seçim listesi.
  - `components/ConfirmationPanel.vue`: Teyit miktarı girişi ve onay paneli.
  - `components/ConfirmationHistory.vue`: Geçmiş teyitler, çoklu stok fişi bağlantıları ve iptal (CORS) akışı.
- **Üretim Paketi:** `erpnextkta/public/dist/js/shopfloor-hub.bundle.*.js`
- **Öne Çıkan Özellikler:**
  - **Çoklu Görünüm & Bağlamsal Kenar Çubuğu:** Sekme değişiminde sol liste ve durum filtreleri otomatik uyarlanır.
  - **Hızlı İş Emri Açma & $T_{\text{prod}}$ Termin:** Yalnızca mamul ve miktar girerek taslak iş emri oluşturma; gelişmiş seçeneklerde reçete, depo ve tarih düzenleme.
  - **Hammadde Uygunluk Matrisi & Esnek Release:** Kalem bazında karşılama oranı (%), eksik uyarısıyla kontrollü serbest bırakma ve aktivite kaydı.
  - **İş Emri Yazdırma & Şablon/Antet Önizleme:** `[ ⚡ Work Orders ]` (`Stok Yenile` yanı) ve `[ 📋 Operations ]` (`WoStatsCard` başlık çubuğu) üzerinden `🖨️ Yazdır` ile varsayılan antet / özel iş emri şablonu seçimi, `localStorage` şablon hafızası, `JsBarcode` barkodlu canlı HTML önizleme, `Tam Sayfa Önizle`, `Yazdır` ve `PDF İndir` akışı.
  - **Kullanıcı Onaylı Hat İkmal Modali (User-Confirmed Staging):** Teyit öncesi pre-flight stok kontrolü, yalnızca üretim/WIP depolarından hat ikmali ve tek tıkla transfer + teyit akışı.
  - **Operasyon Teyit Kokpiti:** Dinamik operasyon listesi, milestone rozeti, dokunmatik uyumlu hızlı miktar butonları (`+1`, `+5`, `+10`, `+25`, `+50`, `Kalanın Tümü`), "Son Teyit (Kalanı Kapat)" bayrağı ve oluşan tüketim/üretim fişlerine doğrudan bağlantılar.
  - **Raporlar (Operasyon Tamamlanma Özeti & Eksik Malzeme ile Açılan İş Emirleri):** Genişletilebilir `ReportsSidebar` kataloğu, her iki raporda `Oluşturma` (`wo_creation`) dahil 9 sütunlu iş emri tablosu, varsayılan `wo_creation DESC, work_order DESC` sıralaması ve `SortableTh.vue` / `tableSort.ts` ile etkileşimli sütun başlığı sıralaması; *Üretim Teyitleri* altında aktif iş emri kapsamlı tamamlanan / kısmi / teyit olmayan operasyon analizi (`groupRowsByWorkOrder` akordeon gruplaması, `OperationCompletionGroupRows.vue` `sequence_id` sıralı alt satırlar, iç içe tembel `<OperationCompletionDetail />`, pasif `⚠️ Eksik Malzeme` göstergesi, `"Oluşturma Tarihi"` dahil düz operasyon bazlı CSV) ve *Malzeme ve Stok* altında eksikle açılan aktif iş emirlerinin canlı `Bin` + `Warehouse` stok karşılama analizi (`MaterialShortageReport.vue` / `MaterialShortageItemsRow.vue`, `critical` / `transfer_required` / `resolved` sınıflandırması, genişletilebilir hammadde kırılımı ve `"Oluşturma Tarihi"` dahil düz `(İş Emri, Hammadde)` UTF-8 BOM CSV dışa aktarma).

---

## 🧪 5. Test Kapsamı

Tüm servisler, stok girişi override'ları, şema alanları ve API uç noktaları için kapsamlı otomatik testler mevcuttur:
- `erpnextkta/tests/test_stock_entry_override.py` (`TestStockEntryOverride`, `TestStockEntryConsumptionCosting`)
- `erpnextkta/kta_shopfloor/tests/test_work_order_service.py`
- `erpnextkta/kta_shopfloor/tests/test_report_service.py`
- `erpnextkta/kta_shopfloor/tests/test_schema.py`
- `erpnextkta/kta_shopfloor/tests/test_confirmation_service.py`
- `erpnextkta/kta_shopfloor/tests/test_backflush_service.py`
- `erpnextkta/kta_shopfloor/tests/test_reversal_service.py`
- `erpnextkta/kta_shopfloor/tests/test_api.py`
- `erpnextkta/kta_shopfloor/doctype/kta_uretim_teyidi/test_kta_uretim_teyidi.py`

---

## 🚀 6. Yol Haritası (Roadmap): SAP LP12 Depo-Üretim İkmal Modülü

Gelecek sprintlerde depocuların iş emri bazlı çekme listeleri (*pull list*) görerek ana hammadde depolarından hat depolarına 2 adımlı toplu/dalga ikmal yapabileceği **SAP LP12 modeli** devreye alınacaktır:
- **Proaktif Hat Besleme:** Hat ikmalleri operatörün reaktif müdahalesi yerine ambar biriminin proaktif hazırlık listesiyle yürütülecektir.
- **2 Aşamalı İkmal (Staging):** Hammadde ambarından ara hazırlık alanına, oradan üretim hatlarına dalga bazlı transfer fişleri otomatik oluşturulacaktır.

</main>
