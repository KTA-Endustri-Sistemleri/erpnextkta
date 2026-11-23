---
layout: default
title: "Shopfloor Hub (Çoklu Görünüm) Üretim ve Teyit Motoru Geliştirici Kılavuzu"
---

<main class="container" markdown="1">

# ⚡ Shopfloor Hub (Çoklu Görünüm Üretim ve Teyit Motoru)

**`kta_shopfloor`**, ERPNext üretim akışlarında iş emri açma / stok uygunluk kontrolü / serbest bırakma (`[ ⚡ Work Orders ]`) ve SAP CO11N (Tek Ekran Operasyon Teyidi) modelini (`[ 📋 Operations ]`) bir araya getiren bağımsız, modüler ve yüksek performanslı üretim kokpitidir.

---

## 🎯 1. Mimari Tasarım ve Ayrım

Bu modül, atölye sürelerini ve duruşlarını toplayan `kta_calisma_karti` modülünden tamamen izole edilmiştir:

- **`kta_calisma_karti`**: Sahadaki operatör sürelerini, duruşları ve krimp/kalite testlerini toplar. Job Card açık ve pasif bir süre sepeti (`Job Card Time Log`) olarak çalışır.
- **`kta_shopfloor`**:
  - **`[ ⚡ Work Orders ]` Görünümü**: Hızlı taslak iş emri oluşturma (`CreateWorkOrderModal`), $T_{\text{prod}}$ termin hesaplama, `Bin.actual_qty` bazlı hammadde uygunluk matrisi (`WorkOrderReleasePanel`) ve eksik parça uyarılı serbest bırakma (Shortage-Allowed Release) süreçlerini yönetir.
  - **`[ 📋 Operations ]` Görünümü**: Yetkili üretim yöneticisi veya vardiya amiri tarafından yapılan fiziki sayımları onaylar; orantısal hammadde sarfiyatı (261 Backflush), mamul girişi (101 GR), çoklu stok fişi takibi ve SAP CORS ters kayıt işlemlerini gerçekleştirir.

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
| - Çalışma Kartı       |             | - Work Orders / Ops            |
| - Süre Sayaçları      |             | - WorkOrderService             |
| - Krimp & QC          |             | - KTA Production Confirmation  |
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
| `check_confirmation_materials` | `work_order` (str), `operation` (str), `yield_qty` (float), `is_final_confirmation` (int) | Teyit öncesi hat deposu malzeme uygunluğunu denetler, eksik varsa alternatif üretim (WIP) depolarındaki stokları döner. |
| `stage_confirmation_materials` | `work_order` (str), `transfers` (list[dict]) | Hat deposuna ikmal için `Material Transfer for Manufacture` stok fişi oluşturup submit eder. |
| `submit_production_confirmation` *(legacy: `submit_co11n_confirmation`)* | `payload` (dict/json) | CO11N üretim teyidini işler ve stok hareketini oluşturur. |
| `cancel_production_confirmation` *(legacy: `cancel_co11n_confirmation`)* | `confirmation_name` (str) | CORS iptal mekanizmasını çalıştırır. |
| `get_production_confirmations` *(legacy: `get_co11n_confirmations`)* | `work_order` (str) | İş emrine ait tüm üretim teyitlerini ve ilişkili tüketim/mamul `Stock Entry` fişlerini döner. |

---

## 🖥️ 4. Kullanıcı Arayüzü (Vue 3 SPA)

- **Desk Sayfası:** `erpnextkta/kta_shopfloor/page/shopfloor_hub/` (`/app/shopfloor_hub`)
- **Frontend Bileşenleri (`erpnextkta/public/shopfloor-hub/`):**
  - `App.vue`: Çoklu görünüm (`work_orders` / `operations`) orkestrasyonu, modal/panel geçişleri ve teyit durumu yönetimi.
  - `components/ShopfloorNavbar.vue`: Üst navigasyon çubuğu (`[ ⚡ Work Orders ]` ve `[ 📋 Operations ]`).
  - `components/WorkOrderSidebar.vue`: Bağlamsal sol iş emri kenar çubuğu (`Work Orders`: `Tümü`, `Taslak`, `Serbest` + `+ Yeni İş Emri Aç` butonu; `Operations`: `Tümü`, `Devam Eden`, `Başlanmamış` [`Not Started`]; tamamlanan kayıtlar kokpitte gösterilmez).
  - `components/CreateWorkOrderModal.vue`: Hızlı taslak iş emri açma penceresi, otomatik BOM/termin ($T_{\text{prod}}$) yükleme ve Gelişmiş Seçenekler akordeonu.
  - `components/WorkOrderReleasePanel.vue`: Hammadde Stok Uygunluk Matrisi, hazır olma ilerleme çubuğu, Eksik Hammadde Uyarısı (`Force Release`) modali ve `Operasyon Teyidine Geç` aksiyonu.
  - `components/MaterialStagingModal.vue`: Hat deposu (`wip_warehouse`) stok yetersizliğinde açılan kullanıcı onaylı ikmal penceresi; kaynak WIP depo seçimi ve tek tıkla `Material Transfer for Manufacture` transferi.
  - `components/WoStatsCard.vue`: İş emri başlık ve özet metrik kartı.
  - `components/OperationsList.vue`: Operasyon adımları ve seçim listesi.
  - `components/ConfirmationPanel.vue`: Teyit miktarı girişi ve onay paneli.
  - `components/ConfirmationHistory.vue`: Geçmiş teyitler, çoklu stok fişi bağlantıları ve iptal (CORS) akışı.
- **Üretim Paketi:** `erpnextkta/public/dist/js/shopfloor-hub.bundle.*.js`
- **Öne Çıkan Özellikler:**
  - **Çoklu Görünüm & Bağlamsal Kenar Çubuğu:** Sekme değişiminde sol liste ve durum filtreleri otomatik uyarlanır.
  - **Hızlı İş Emri Açma & $T_{\text{prod}}$ Termin:** Yalnızca mamul ve miktar girerek taslak iş emri oluşturma; gelişmiş seçeneklerde reçete, depo ve tarih düzenleme.
  - **Hammadde Uygunluk Matrisi & Esnek Release:** Kalem bazında karşılama oranı (%), eksik uyarısıyla kontrollü serbest bırakma ve aktivite kaydı.
  - **Kullanıcı Onaylı Hat İkmal Modali (User-Confirmed Staging):** Teyit öncesi pre-flight stok kontrolü, yalnızca üretim/WIP depolarından hat ikmali ve tek tıkla transfer + teyit akışı.
  - **Operasyon Teyit Kokpiti:** Dinamik operasyon listesi, milestone rozeti, dokunmatik uyumlu hızlı miktar butonları (`+1`, `+5`, `+10`, `+25`, `+50`, `Kalanın Tümü`), "Son Teyit (Kalanı Kapat)" bayrağı ve oluşan tüketim/üretim fişlerine doğrudan bağlantılar.

---

## 🧪 5. Test Kapsamı

Tüm servisler, stok girişi override'ları, şema alanları ve API uç noktaları için kapsamlı otomatik testler mevcuttur:
- `erpnextkta/tests/test_stock_entry_override.py` (`TestStockEntryOverride`, `TestStockEntryConsumptionCosting`)
- `erpnextkta/kta_shopfloor/tests/test_work_order_service.py`
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
