# Tasarım Dokümanı: Shopfloor Hub Raporlar Görünümü ve İş Emri Operasyon Tamamlanma Özeti

**Tarih:** 2026-11-24  
**Durum:** Taslak (Onay Bekliyor)  
**Dal:** `feat/shopfloor-work-order-print` (taban: `main` / `58c37a7`)  
**Seçilen Yaklaşım:** Yaklaşım 1 — Modüler Rapor Kayıt Defteri (`registry.ts`) + Ayrı `report_service.py`

---

## 1. Amaç ve Gerekçe (Intent & Why)

Mevcut Shopfloor Hub kokpitinde operatörler ve üretim sorumluları teyitleri yalnızca sol listeden seçilen **tek bir İş Emri** içine girerek `Operations` sekmesindeki `ConfirmationHistory` tablosundan görebilmektedir. Bu durum aktif sahada şu boşluğu yaratmaktadır:

- Aktif durumdaki (`Not Started` / `In Process`) iş emirleri genelinde hangi operasyonların teyidinin tamamlandığını, hangilerinin kısmi kaldığını ve son teyidin ne zaman kim tarafından girildiğini **tek bir toplu ekrandan** görme imkanı yoktur.
- Kullanıcılar Shopfloor Hub üst menüsünde (`ShopfloorNavbar.vue`) ayrı bir **`Raporlar`** sekmesi açılmasını; bu sekme aktifken sol kenar çubuğunun (drawer) iş emri listesi yerine **genişletilebilir bir rapor kataloğu** sunmasını istemektedir. Böylece ilk etapta **İş Emri Operasyon Tamamlanma Özeti** yayınlanacak, ilerleyen sprintlerde eklenecek yeni Shopfloor raporları mevcut kodu dağıtmadan aynı kataloğa takılabilecektir.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### 2.1 Hedefler (Goals)
1. **Üst Menü Sekmesi (`Raporlar`):** `ShopfloorNavbar.vue` içine 4. sekme olarak `[ 📊 Raporlar ]` (`reports`) görünümünün eklenmesi.
2. **Genişletilebilir Sol Rapor Çekmecesi (`ReportsSidebar.vue`):** `activeView === 'reports'` olduğunda sol çekmecenin `WorkOrderSidebar` yerine rapor kataloğunu göstermesi; bildirimli rapor listesinin deklaratif bir kayıt defterinden (`erpnextkta/public/shopfloor-hub/reports/registry.ts`) beslenmesi.
3. **İlk Rapor — İş Emri Operasyon Tamamlanma Özeti (`operation_completion`):**
   - Yalnızca aktif ve onaylı İş Emirleri (`docstatus = 1`, `status IN ('Not Started', 'In Process')`) üzerinde fiilen ilerleme almış (`completed_qty > 0`) her `(work_order, operation)` çiftini tek özet satırında listelemek.
   - Açılışta varsayılan olarak **`Tamamlandı`** filtresini (`pending_qty <= 0` veya `has_final == 1`) göstermek; tek tıkla **`Kısmi`** ve **`Tümü (Teyitli)`** sekmelerine geçiş sunmak.
   - `Operasyon`, `İstasyon`, `Son Teyit Tarih Aralığı` (`from_date`, `to_date`) ve serbest metin arama (`work_order`, `production_item`, `item_name`, `operation`, `workstation`, `last_confirmed_by`) filtreleri sunmak.
   - Dinamik KPI kartları (`Tamamlanan Operasyon`, `Kısmi Operasyon`, `Aktif İş Emri`, `Toplam Onaylanan Miktar`) göstermek.
   - Satır genişletme (expand) ile o iş emri ve operasyona ait tekil `KTA Production Confirmation` belgelerini ve ilişkili `Stock Entry` fişlerini mevcut `get_production_confirmations` API'si üzerinden tembel (lazy) yüklemek.
   - Satır bazında **`Operasyona Git`** aksiyonuyla tek tıkta `Operations` sekmesine geçip ilgili İş Emrini yüklemek ve tıklanan operasyonu otomatik seçmek.
   - Filtrelenmiş görünüm için istemci tarafında UTF-8 BOM destekli **CSV Dışa Aktarma** sunmak.

### 2.2 Kapsam Dışı (Non-Goals)
- `Completed`, `Closed`, `Cancelled` veya `Stopped` statüsündeki İş Emirlerini listelemek (kullanıcı talebi doğrultusunda kapsam dışı bırakılmıştır).
- Henüz hiç teyit/üretim girişi almamış (`completed_qty == 0`, `Pending`) operasyonları bu rapora dahil etmek.
- Yeni bir ERPNext `Report` (Script Report) DocType'ı, veritabanı tablosu veya migration oluşturmak.
- Rapor ekranı içinden doğrudan teyit iptali (CORS storno) çalıştırmak (iptal işlemleri kontrollü biçimde `Operations` -> `ConfirmationHistory` üzerinden yürütülür; `Operasyona Git` aksiyonu kullanıcıyı doğrudan oraya taşır).
- Bu iterasyonda Operasyon Tamamlanma Özeti dışında 2. veya 3. bir rapor geliştirmek (yalnızca genişletilebilir altyapı kurulur).

### 2.3 Anti-Hedefler (Anti-Goals)
- Geçmişte tamamlanmış on binlerce iş emrini tarayıp rapor açılışını yavaşlatmak.
- Satır başına ek SQL sorgusu atan N+1 sorgu deseni kullanmak.
- `App.vue` (şu an 493 satır) veya yeni eklenecek herhangi bir `.vue` dosyasında **500 satır sınırını** aşmak ya da 928 satırlık `work_order_service.py` dosyasını rapor mantığıyla şişirmek.
- Yalnızca Light tema için sabit renkler (`#ffffff`, `#0f172a` vb.) yazarak Frappe Dark Theme (`[data-theme="dark"]`) görünümünü bozmak.

---

## 3. Mimari Kısıtlar ve Yönetişim Kuralları

- **Çalışma Dalı:** `feat/shopfloor-work-order-print` (taban: `main` / `58c37a7`, `v4.5.3`).
- **Çekirdek Koruması:** Standart ERPNext çekirdek dosyalarına (`/home/frappe/frappe-bench/apps/erpnext/**`) kesinlikle dokunulmaz.
- **Klasör ve Uzman Sınırları (`.agents/AGENTS.md`):**
  - `kta-shopfloor`: `erpnextkta/kta_shopfloor/**` (servis, API, unit/API testleri).
  - `frontend-public`: `erpnextkta/public/shopfloor-hub/**` (`.vue` dosyaları `<= 500` satır, tembel `const __ = (...args: any[]) => (window as any).__(...args);`, Frappe Light/Dark CSS değişkenleri).
  - `docs-i18n`: `erpnextkta/www/docs/shopfloor-hub.html`, `docs/kta_shopfloor_hub_kilavuzu.md`, `erpnextkta/translations/{tr,en,de}.csv` (sıfır ticari veri).
- **Kalite Kapısı:** Python için `/home/frappe/frappe-bench/env/bin/ruff check` ve `ruff format --check`; frontend paketi için yalnızca `bench build --app erpnextkta --production`; backend testleri; deploy sonrası `bench restart` ve `bench --site <site> clear-cache`.

---

## 4. Değerlendirilen Yaklaşımlar ve Seçilen Mimari

| Yaklaşım | Özet | Takas (Trade-off) | Karar |
|---|---|---|---|
| **Yaklaşım 1: Modüler Rapor Kayıt Defteri (`registry.ts`) + `report_service.py`** | Frontend'de deklaratif rapor registry + `ReportsSidebar` + `ReportsWorkspace` + dinamik rapor bileşeni; Backend'de tek geçişli toplu SQL sunan ayrı `report_service.py`. | İlk kurulumda birkaç modüler dosya eklenir; ancak 2., 3. rapor yalnızca 1 kayıt + 1 bileşenle sıfır refactor ile eklenir ve Shopfloor'a özel etkileşimler (`Operasyona Git`, satır içi fiş detayı) doğal çalışır. | **Seçilen** |
| **Yaklaşım 2: ERPNext Script Report + SPA Wrapper** | Standart `Report` DocType oluşturulur; SPA `frappe.desk.query_report.run` sonucunu sarar. | Standart Desk'te açılabilir; ancak DocType JSON/migrate gerektirir, satır içi lazy teyit detayı ve `Operations` sekmesine bağlamsal geçiş düz şemaya sığmaz. | Reddedildi |
| **Yaklaşım 3: Tek Bileşenli `ReportsView.vue` + `work_order_service.py`** | Tüm rapor menüsü ve tablo tek dosyaya yazılır. | Başlangıçta az dosya üretir; fakat 2. rapor gelir gelmez `500` satır ve `work_order_service.py` şişme sınırına çarpıp refactor zorunlu kılar. | Reddedildi |

---

## 5. Backend Tasarımı

### 5.1 Modül ve Whitelisted API Sözleşmesi
- **Yeni Servis:** `erpnextkta/kta_shopfloor/services/report_service.py`
- **API Sarmalayıcı (`erpnextkta/kta_shopfloor/api.py`):**
  ```python
  @frappe.whitelist()
  def get_operation_completion_report(
      status_filter: str = "completed",
      operation: str | None = None,
      workstation: str | None = None,
      from_date: str | None = None,
      to_date: str | None = None,
      search: str | None = None,
      company: str | None = None,
  ) -> dict:
  ```

### 5.2 Yetki ve Şirket Çözümleme
- **Yetki Doğrulama:** Girişte mutlaka `frappe.has_permission("Work Order", "read", throw=True)` ve `frappe.has_permission("KTA Production Confirmation", "read", throw=True)` çağrılır.
- **Şirket Çözümleme:** `get_active_work_orders` ile birebir aynı kural uygulanır (`company` parametresi verilmemişse user default / `Global Defaults.default_company`; `not frappe.flags.in_test` durumunda `_Test%` şirket gelirse aktif ilk gerçek şirket seçilir).

### 5.3 Tek Geçişli Toplu Veri Toplama (Maksimum 4 Sınırlı Sorgu, N+1 Yok)
1. **Aktif İş Emirleri:** `Work Order` üzerinden `docstatus = 1`, `status IN ('Not Started', 'In Process')`, `company = target_company` olan iş emirleri (`name`, `production_item`, `item_name`, `qty`, `produced_qty`, `status`, `stock_uom`, `creation`) çekilir. Liste boşsa boş payload erken döndürülür.
2. **Operasyon Satırları:** `Work Order Operation` tablosundan `parent IN active_wo_names` kayıtları (`parent`, `operation`, `workstation`, `sequence_id`, `idx`, `completed_qty`, `status`) çekilir.
   - *Operasyonsuz İş Emri Fallback'i:* Rotasında hiç `Work Order Operation` satırı olmayan aktif iş emirleri için, ilgili iş emrine ait `KTA Production Confirmation` (`docstatus = 1`) kayıtlarındaki tekil `operation` değerleri (yoksa eğer legacy `Manufacture` girişi varsa `_("Üretim")`) sanal operasyon satırı olarak üretilir.
3. **Shopfloor Teyit Agregasyonu (`KTA Production Confirmation`):** `docstatus = 1` ve `work_order IN active_wo_names` için parametreli SQL ile `(work_order, operation)` bazında:
   - `co11n_qty = COALESCE(SUM(yield_qty), 0)`
   - `confirmation_count = COUNT(*)`
   - `has_final = MAX(COALESCE(is_final_confirmation, 0))`
   - En son teyide ait (`ORDER BY posting_date DESC, posting_time DESC, creation DESC`) `last_posting_date`, `last_posting_time`, `last_confirmed_by`, `last_confirmation`.
4. **Eski Usul `Manufacture` Agregasyonu (`Stock Entry`):** `ConfirmationService.get_operation_quantities()` ile tam tutarlılık için `docstatus = 1`, `purpose = 'Manufacture'`, `work_order IN active_wo_names` ve `name` değeri `KTA Production Confirmation.stock_entry` içinde yer almayan fişler `work_order` bazında toplanır (`legacy_manufacture_qty = COALESCE(SUM(fg_completed_qty), 0)` ve son fişin `posting_date`, `posting_time`, `owner` bilgisi).

### 5.4 Miktar, Durum ve Kaynak Türü Hesabı
Her `(work_order, operation)` satırı için `ConfirmationService.get_operation_quantities()` formülü korunur:
- `total_completed = legacy_manufacture_qty + co11n_qty`
- `completed_qty = min(wo_qty, total_completed)` (`wo_qty > 0` ise; aksi halde `total_completed`)
- `pending_qty = max(0.0, wo_qty - completed_qty)`
- **`completed_qty <= 0` olan satırlar elenir** (henüz hiç ilerleme olmayan operasyonlar rapora girmez).
- `status`: `pending_qty <= 0` veya `has_final == 1` ise `"completed"`, aksi halde `"partial"`.
- `completion_percent`: `has_final == 1` veya `pending_qty <= 0` ise `100.0`; aksi halde `min(100.0, round((completed_qty / wo_qty) * 100.0, 1))`.
- `source_type`:
  - `co11n_qty > 0` ve `legacy_manufacture_qty > 0` -> `"mixed"`
  - `co11n_qty > 0` -> `"co11n"`
  - aksi halde -> `"legacy"`
- `last_posting_date`, `last_posting_time`, `last_confirmed_by`: Öncelikle en güncel Shopfloor teyidinden alınır; yalnızca `"legacy"` satırlarda ilgili `Stock Entry`'den doldurulur (`last_posting_time` `HH:MM:SS` metnine normalize edilir).

### 5.5 Filtreleme, Sekme Sayaçları ve Sıralama Kuralları
1. `filter_options` (`operations`, `workstations`), tüm aktif ilerlemiş satırlar (`completed_qty > 0`) üzerinden tekil ve alfabetik sıralı üretilir; böylece filtre seçenekleri kullanıcı seçim yaptığında kaybolmaz.
2. Ardından şu 5 filtre `status_filter` **uygulanmadan önce** çalıştırılır:
   - `operation` (tam eşleşme)
   - `workstation` (tam eşleşme)
   - `from_date` / `to_date` (`last_posting_date` alanı üzerinde kapsayıcı `>= from_date` ve `<= to_date`; geçersiz veya boş değerler yok sayılır)
   - `search` (büyük/küçük harf duyarsız alt dize eşleşmesi: `work_order`, `production_item`, `item_name`, `operation`, `workstation`, `last_confirmed_by`)
3. Sekme sayaçları (`counts: { completed, partial, all }`) bu aşamadaki satır kümesinden hesaplanır; böylece üst sekmelerdeki adetler o an seçili Operasyon/İstasyon/Tarih/Arama filtreleriyle her zaman tutarlı kalır.
4. Son adımda `status_filter` (`"completed"` varsayılan, `"partial"`, veya `"all"` — geçersiz değerler `"completed"` veya `"all"` yerine güvenli biçimde `"completed"` varsayılanına düşer) uygulanır.
5. Dönen `rows` listesi deterministik sırayla dizilir:
   `(last_posting_date DESC, last_posting_time DESC, work_order DESC, sequence_id ASC)`.
6. Üst KPI nesnesi (`summary`):
   - `completed_operations` ve `partial_operations`: `status_filter` **uygulanmadan önceki** (ancak `operation`, `workstation`, `from_date`, `to_date`, `search` filtreleri uygulanmış) kümeden hesaplanır (`counts.completed` ve `counts.partial` ile uyumlu; böylece varsayılan `Tamamlandı` sekmesinde bile sahadaki açık `Kısmi` operasyon sayısı KPI şeridinde sıfır görünmez).
   - `unique_work_orders` ve `total_confirmed_qty`: `status_filter` **sonrasında** dönen `rows` kümesi üzerinden hesaplanır ve tabloda görünen satırların toplamını yansıtır.

### 5.6 Dönüş JSON Şeması
```json
{
  "rows": [
    {
      "work_order": "WO-2026-0001",
      "wo_status": "In Process",
      "production_item": "ITEM-001",
      "item_name": "Örnek Mamul",
      "stock_uom": "Adet",
      "wo_qty": 1000.0,
      "operation": "OP10 Kesim",
      "sequence_id": 1,
      "workstation": "İstasyon A",
      "completed_qty": 1000.0,
      "co11n_qty": 1000.0,
      "legacy_manufacture_qty": 0.0,
      "pending_qty": 0.0,
      "completion_percent": 100.0,
      "status": "completed",
      "has_final_confirmation": 0,
      "confirmation_count": 2,
      "last_confirmation": "CONF-2026-00120",
      "last_posting_date": "2026-11-24",
      "last_posting_time": "09:40:15",
      "last_confirmed_by": "operator@example.com",
      "source_type": "co11n"
    }
  ],
  "summary": {
    "completed_operations": 1,
    "partial_operations": 0,
    "unique_work_orders": 1,
    "total_confirmed_qty": 1000.0
  },
  "counts": {
    "completed": 1,
    "partial": 0,
    "all": 1
  },
  "filter_options": {
    "operations": ["OP10 Kesim"],
    "workstations": ["İstasyon A"]
  }
}
```

### 5.7 Satır Detay Açılımı (Teyit & Stok Fişleri)
Satır genişletildiğinde ayrı bir backend endpoint yazılmaz; mevcut `erpnextkta.kta_shopfloor.api.get_production_confirmations(work_order)` çağrılır ve dönen kayıtlar istemcide `c.operation === row.operation` (sanal/operasyonsuz durumda tüm kayıtlar) ile süzülerek `ConfirmationHistory.vue` tarzında `Teyit No`, `Miktar`, `Tarih/Saat`, `Kullanıcı`, `Durum` ve ilişkili `Tüketim` / `Üretim` `Stock Entry` bağlantıları gösterilir.

---

## 6. Frontend Tasarımı (`erpnextkta/public/shopfloor-hub/`)

### 6.1 Dosya ve Bileşen Haritası (500 Satır Sınırı Korumalı)
- **`types.ts`:**
  - `WorkOrderViewMode = 'work_orders' | 'operations' | 'work_cards' | 'reports'`
  - `ReportStatusFilter = 'completed' | 'partial' | 'all'`
  - `OperationCompletionRow`, `OperationCompletionSummary`, `OperationCompletionCounts`, `OperationCompletionFilterOptions`, `OperationCompletionReportResponse`
- **`components/ShopfloorNavbar.vue`:**
  - `tabs` dizisine 4. sekme eklenir: `{ id: 'reports', icon: '📊', label: 'Raporlar' }` (not: mevcut diğer tab etiketleri İngilizce key kullanıp `tr.csv` üzerinden çevrildiğinden tutarlılık için `label: 'Reports'` kullanılıp `tr.csv`/`en.csv`/`de.csv` üzerinden çevrilmesi önerilir; buna Koordinatör karar verecektir).
- **`reports/registry.ts` (Yeni — Genişletilebilir Rapor Kataloğu):**
  - `ShopfloorReportId = 'operation_completion'` (ileride union büyütülür).
  - `ShopfloorReportDefinition`: `{ id, title, description, category, icon, component }`.
  - İlk kayıt: `operation_completion` (`title: 'Operasyon Tamamlanma Özeti'`, `category: 'Üretim Teyitleri'`, `icon: '✅'`, `component: OperationCompletionReport`).
- **`components/ReportsSidebar.vue` (Yeni, `<= 250` satır):**
  - Mevcut `WorkOrderSidebar.vue` ile aynı genişlik ve görsel dil (`sidebar-header`, arama kutusu, aktif kart vurgusu, Light + Dark tema uyumu).
  - Üstte `Raporlar` başlığı + kayıtlı rapor sayısı rozeti (`{N} Rapor`), rapor adına/açıklamasına göre arama ve tıklanan raporu `select-report` olayıyla `App.vue`'ya iletme.
- **`components/ReportsWorkspace.vue` (Yeni, `<= 120` satır):**
  - `selectedReportId` üzerinden `SHOPFLOOR_REPORTS` içinden aktif raporu `<component :is="activeReport.component" />` ile render eder.
  - Rapor bileşeninden gelen `open-operation` olayını (`workOrder`, `operation`) `App.vue`'ya iletir.
- **`components/reports/OperationCompletionReport.vue` (Yeni, `<= 450` satır; gerekirse alt bileşenle bölünür):**
  - **KPI Şeridi:** 4 kart (`Tamamlanan Operasyon`, `Kısmi Operasyon`, `Aktif İş Emri`, `Toplam Onaylanan Miktar`).
  - **Durum Sekmeleri:** `Tamamlandı (N)` *(varsayılan seçili)*, `Kısmi (N)`, `Tümü (N)`.
  - **Filtre Çubuğu:** `Operasyon` select, `İstasyon` select, `Başlangıç Tarihi` / `Bitiş Tarihi`, `Ara...` (300 ms debounce), `Temizle`, `↻ Yenile` ve `⬇ CSV İndir`.
  - **Tablo ve Satır Genişletme:**
    - Sütunlar: Genişlet oku (`▶/▼`), `İş Emri` (yeni sekmede link + ürün kodu/adı), `Operasyon` (+ istasyon alt satırı), `Onaylanan / Hedef` (+ ilerleme yüzdesi çubuğu), `Son Teyit` (tarih + saat + son teyit no linki), `Teyit Eden` (+ teyit sayısı rozeti), `Durum` (`✓ Tamamlandı` / `⏳ Kısmi` + varsa `Son` veya `Eski Usul` alt etiketi), `İşlem` (`Operasyona Git` butonu).
    - Satır tıklandığında altında detay paneli açılır; `get_production_confirmations` cevabı `(work_order, operation)` anahtarıyla önbelleklenir (aynı satır tekrar açılırsa yeniden istek atılmaz; `Yenile` basıldığında önbellek temizlenir).
- **Ekran Düzeni Metin Eskizi:**
```
+-----------------------------------------------------------------------------------+
| 🏭 SHOPFLOOR HUB   [ ⚡ Work Orders ] [ 📋 Operations ] [ ⏱️ Work Cards ] [ 📊 Raporlar ] |
+----------------------+------------------------------------------------------------+
| 📊 Raporlar   [1]    | Operasyon Tamamlanma Özeti                     [⬇ CSV] [↻] |
| [🔍 Rapor ara...]    |------------------------------------------------------------|
|                      | [Tamamlanan: 42] [Kısmi: 18] [Aktif WO: 51] [Miktar: 12.4K]|
| > ✅ Operasyon       | [Tamamlandı (42)] [Kısmi (18)] [Tümü (60)]                 |
|     Tamamlanma Özeti | [Operasyon ▾] [İstasyon ▾] [Başl.] [Bitiş] [Ara...] [Temiz]|
|                      |------------------------------------------------------------|
|                      | İş Emri     | Operasyon  | Onay/Hedef | Son Teyit | İşlem  |
|                      | > WO-2026.. | OP10 Kesim | 1000/1000  | 24.11 09:4| [Git ↗]|
|                      |   └ CONF-.. | 24.11 09:40 | ⚙ STE-.. | ✓ Tamamlandı      |
+----------------------+------------------------------------------------------------+
```
- **`App.vue` ve `500` Satır Kuralı Önlemi:**
  - `App.vue` halihazırda **493** satır olduğu için `ReportsSidebar`, `ReportsWorkspace` ve `handleOpenOperationFromReport` eklendiğinde `500` satır sınırını geçmemek adına başarı/hata uyarı şeridi (<div class="co11n-alert">) `components/ShopfloorAlerts.vue` bileşenine taşınır (veya benzer küçük bir parça ayrılır) ki `App.vue` eklemelerden sonra dahi `<= 470` satırda kalsın.
  - `handleOpenOperationFromReport(workOrderName: string, operationName: string)`: `activeView.value = 'operations'` yapar, `await nextTick()`, `await sidebarRef.value?.fetchWorkOrders()`, `await loadWorkOrder(workOrderName)` çağırır ve `context.value?.operations` içinde `op.operation === operationName` eşleşmesini bulursa `selectOperation(matchedOp)` çalıştırır.

---

## 7. Koordinatör / Geliştirici Tarafında Sabitlenen Küçük Kararlar

Bu kararlar kullanıcı deneyimini bozmadan inşa sırasında netlik sağlamak amacıyla tasarım seviyesinde sabitlenmiştir (gerekirse uygulama aşamasında değiştirilebilir):
1. **Varsayılan Sekme Etiketi Key'i:** `ShopfloorNavbar.vue` içindeki mevcut `Work Orders`, `Operations`, `Work Cards` etiketleriyle tutarlılık için yeni sekme key'i `'Reports'` olacak ve `tr.csv` içinde `'Raporlar'`, `de.csv` içinde `'Berichte'` olarak çevrilecektir.
2. **Tarih Aralığı Filtresi Hedefi:** `from_date` / `to_date` filtreleri satırın son teyit tarihi (`last_posting_date`) üzerinden uygulanır (ör. sadece bugün veya bu hafta tamamlanan operasyonları süzebilmek için).
3. **Eski Usul (`legacy`) Satır Detayı:** Operasyona ait `KTA Production Confirmation` kaydı yoksa (`source_type === 'legacy'`), genişleyen detay paneli `"Bu ilerleme doğrudan standart Üretim (Manufacture) stok fişinden gelmektedir."` bilgisini gösterir.
4. **CSV Dosya Adı ve Ayraç:** İstemci tarafında `shopfloor-operasyon-tamamlanma-YYYY-MM-DD.csv` adıyla UTF-8 BOM (`\uFEFF`) eklenerek Excel Türkçe karakter uyumu sağlanır.
5. **KPI Şeridi (`summary`) Hesaplama Ayrımı (Koordinatör Kararı):** `summary.completed_operations` ve `summary.partial_operations` değerleri `status_filter` öncesindeki (`operation`/`workstation`/`tarih`/`search` sonrası) kümeden beslenerek hem tamamlanan hem kısmi adedin eşzamanlı görünmesini sağlar; `summary.unique_work_orders` ve `summary.total_confirmed_qty` ise aktif sekmedeki (`rows`) tabloyu yansıtır.

---

## 8. Test, Dokümantasyon ve Çeviri Planı (Özet)

- **Backend Testleri (`erpnextkta/kta_shopfloor/tests/test_report_service.py` ve `test_api.py`):**
  - `Completed`, `Closed`, `Cancelled`, `Stopped` ve `Draft` (`docstatus = 0`) iş emirlerinin rapor dışında kaldığının doğrulanması.
  - Aktif iş emrinde `completed_qty == 0` olan operasyonların filtrelendiğinin; `co11n`, `legacy` ve `is_final_confirmation = 1` (short-close) durumlarının doğru `status` (`completed` / `partial`) ve `source_type` ürettiğinin doğrulanması.
  - `status_filter`, `operation`, `workstation`, `from_date` / `to_date`, `search` filtrelerinin ve sekme `counts` / `summary` hesaplarının doğrulanması.
  - `Work Order` veya `KTA Production Confirmation` okuma yetkisi olmayan kullanıcı için `frappe.PermissionError` doğrulanması.
  - SQL sorgu sayısının aktif iş emri sayısından bağımsız (sabit/N+1'siz) olduğunun kontrolü.
- **Dokümantasyon & Çeviri:**
  - `erpnextkta/www/docs/shopfloor-hub.html` ve `docs/kta_shopfloor_hub_kilavuzu.md` içine `[ 📊 Raporlar ]` görünümü ve `get_operation_completion_report` API'sinin işlenmesi (sıfır ticari veri).
  - Tüm yeni `__("...")` metinlerinin `tr.csv`, `en.csv`, `de.csv` dosyalarına eklenmesi.

---

## 9. İnşa Aşamasına Bırakılan Detaylar (What's Left to the Builder)

- Tablo kolon genişlikleri, mobil kart/yatay kaydırma kırılım noktaları ve KPI kartlarının CSS ayrıntıları.
- İstemci tarafında sütun başlıklarına tıklanarak ikincil sıralama veya sayfalama/sanal liste ihtiyacı olup olmadığı.
- `report_service.py` içindeki SQL ve birleştirme mantığının küçük özel yardımcı fonksiyonlara (`_fetch_active_work_orders`, `_fetch_wo_operations`, `_fetch_confirmation_aggregates`, `_fetch_legacy_manufacture_aggregates`, `_build_report_row`, `_apply_report_filters`) ayrılması.
- `OperationCompletionReport.vue` 450 satıra yaklaşırsa alt tablo veya satır detayının alt bileşene (`OperationCompletionDetailRow.vue`) bölünmesi.
