# KTA MRP: İş Emri Malzeme Tüketim Stratejisi (Kapasiteye Dağıtılmış Tüketim) Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KTA MRP Settings içerisine `wo_consumption_strategy` Select alanını eklemek, MRP motorunda (demand ve service katmanları) hammadde ihtiyacını anlık stoktan peşin düşmek yerine fabrikanın haftalık kapasite planındaki üretim hızına göre zaman fazlı tüketen kapasite odaklı modeli uygulamak, testlerini yazmak ve dokümantasyonunu senkronize etmek.

**Architecture:** `kta_mrp_settings.json` şemasına `wo_consumption_strategy` Select alanı eklenir. `settings.py` içinde `MrpSettings` sınıfına ve okuma metodlarına `is_capacity_leveled_consumption` desteği eklenir. `demand.py` içinde `ProductionPlan.material_driving_qty` metodu kapasite modunda `planned` adedini döndürür; `service.py` içinde ise `free_stock` fiziksel ambar stoğu (`actual_qty`) olarak ele alınır.

**Tech Stack:** Python 3.11, Frappe v15 / ERPNext, MariaDB, Pytest / Frappe Unit Tests.

**Spec:** [`docs/superpowers/specs/2026-11-17-mrp-wo-consumption-strategy-design.md`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-17-mrp-wo-consumption-strategy-design.md)

## Global Constraints
- Şema alan adı: `wo_consumption_strategy` (`Select`, default: `"Anlık Stok Rezervasyonu (Klasik)"`).
- Seçenekler: `Anlık Stok Rezervasyonu (Klasik)\nKapasiteye Dağıtılmış Tüketim (Zaman Fazlı)`.
- Geriye dönük %100 uyumluluk: Klasik modda mevcut `deduct_work_order_reservations` mantığı ve `planned - work_orders` korunur.
- Kapasite modunda: `free_stock = actual_qty`, `material_driving_qty = planned`.
- Null safety: Sayısal Frappe alanlarında her zaman `flt()` / `cint()` ve `None` kontrolü.
- Değişiklik sonrası `bench restart` ve `bench --site development.localhost clear-cache`.

## Review Focus
1. `wo_consumption_strategy` boş veya None geldiğinde varsayılan olarak `"Anlık Stok Rezervasyonu (Klasik)"` dönmelidir.
2. Kapasite modunda `free_stock` değeri `reserved_qty`'den etkilenmemeli, doğrudan `actual_qty`'ye eşit olmalıdır.
3. Kapasite modunda `material_driving_qty` açık iş emirlerini plandan düşmemeli, o haftanın toplam `planned` üretim adedini döndürmelidir.
4. Klasik modda `material_driving_qty` iş emirlerini plandan düşmeye (`max(0, planned - wo)`) devam etmelidir.
5. Çok dilli çevirilerde (TR, EN, DE) yeni Select etiketleri ve seçenekleri eksiksiz çevrilmelidir.

---

### Task 1: KTA MRP Settings Şeması ve Ayar Katmanı Güncellemesi (`kta-mrp`)

**Files:**
- Modify: `erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json`
- Modify: `erpnextkta/kta_mrp/mrp_engine/settings.py`
- Test: `erpnextkta/kta_mrp/tests/test_settings.py`

**Interfaces:**
- Consumes: Frappe DocType şeması, `KTA MRP Settings`
- Produces: `MrpSettings.wo_consumption_strategy: str`, `MrpSettings.is_capacity_leveled_consumption: bool`

- [x] **Step 1: Write failing tests in `test_settings.py`**
  ```python
  def test_wo_consumption_strategy_default(self):
      settings = get_mrp_settings()
      self.assertEqual(settings.wo_consumption_strategy, "Anlık Stok Rezervasyonu (Klasik)")
      self.assertFalse(settings.is_capacity_leveled_consumption)

  def test_wo_consumption_strategy_capacity_leveled(self):
      filters = {"wo_consumption_strategy": "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)"}
      settings = resolve_mrp_settings(filters)
      self.assertEqual(settings.wo_consumption_strategy, "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)")
      self.assertTrue(settings.is_capacity_leveled_consumption)
  ```

- [x] **Step 2: Run test to verify it fails**
  Run: `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_settings`
  Expected: FAIL with AttributeError or AssertionError on `wo_consumption_strategy`.

- [x] **Step 3: Update `kta_mrp_settings.json` and `settings.py`**
  - In `kta_mrp_settings.json`:
    Add `wo_consumption_strategy` (`Select`, options: `"Anlık Stok Rezervasyonu (Klasik)\nKapasiteye Dağıtılmış Tüketim (Zaman Fazlı)"`, default: `"Anlık Stok Rezervasyonu (Klasik)"`) under `sb_supply`.
  - In `settings.py`:
    Add field `wo_consumption_strategy: str = "Anlık Stok Rezervasyonu (Klasik)"` to `MrpSettings`.
    Add property `@property def is_capacity_leveled_consumption(self) -> bool: return self.wo_consumption_strategy == "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)"`.
    Update `get_mrp_settings()` and `resolve_mrp_settings()` to read `wo_consumption_strategy` with defensive fallback.

- [x] **Step 4: Run bench migrate and verify tests pass**
  Run:
  `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost migrate`
  `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_settings`
  Expected: PASS (All tests pass).

---

### Task 2: Talep ve Malzeme İhtiyacı Motorunda Kapasite Tüketim Mantığı (`kta-mrp`)

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/demand.py`
- Modify: `erpnextkta/kta_mrp/mrp_engine/service.py`
- Test: `erpnextkta/kta_mrp/tests/test_service.py`

**Interfaces:**
- Consumes: `MrpSettings.is_capacity_leveled_consumption`
- Produces:
  - `ProductionPlan.material_driving_qty(item_code, week, capacity_leveled: bool)`
  - `_build_single_material()` ve `MaterialRequirementSummary.free_stock`

- [x] **Step 1: Write failing tests in `test_service.py`**
  ```python
  def test_capacity_leveled_wo_consumption_driving_qty_and_stock(self):
      """Kapasiteye dağıtılmış tüketim modunda hammadde stoktan düşülmez ve iş emirleri plandan silinmez."""
      # 1. Driving qty testi
      plan = ProductionPlan(
          weeks=["2026_w47"],
          planned={"ITEM-A": {"2026_w47": 7000}},
          work_orders={"ITEM-A": {"2026_w47": 2000}},
      )
      # Klasik mod: 7000 - 2000 = 5000
      self.assertEqual(plan.material_driving_qty("ITEM-A", "2026_w47", capacity_leveled=False), 5000)
      # Kapasite modu: toplam planlanan 7000 doğrudan hammadde talep eder
      self.assertEqual(plan.material_driving_qty("ITEM-A", "2026_w47", capacity_leveled=True), 7000)

  def test_service_material_requirements_with_capacity_leveled_strategy(self):
      """Service katmanında wo_consumption_strategy ayarına göre serbest stok hesaplaması doğrulanmalıdır."""
      # Kapasite modu ayarı ile çağrıldığında free_stock actual_qty'ye eşit olmalı
      ...
  ```

- [x] **Step 2: Run test to verify it fails**
  Run: `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_service`
  Expected: FAIL with TypeError or AssertionError.

- [x] **Step 3: Update `demand.py` and `service.py`**
  - In `demand.py`:
    Update `material_driving_qty(self, item_code, week, capacity_leveled: bool = False)`:
    If `capacity_leveled`: return `planned` (never subtract work orders).
    Else: return `max(0, planned - (work_orders.get(...)))`.
  - In `service.py`:
    In `MaterialRequirementSummary`: add `capacity_leveled: bool = False`. If `capacity_leveled`, `free_stock` returns `self.actual`.
    In `_build_single_material()`: check `settings.is_capacity_leveled_consumption`.
    In `get_material_requirements_data()`: pass `capacity_leveled=settings.is_capacity_leveled_consumption` to `material_driving_qty`.

- [x] **Step 4: Run test to verify it passes**
  Run: `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_service`
  Expected: PASS (All tests pass).

---

### Task 3: Dokümantasyon ve Çok Dilli Çeviri Senkronizasyonu (`docs-i18n`)

**Files:**
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/www/docs/mrp-settings.html`
- Modify: `docs/mrp_settings.md`

**Interfaces:**
- Consumes: `wo_consumption_strategy` etiket, açıklama ve seçenekleri
- Produces: TR, EN, DE çevirileri ve portal dokümantasyonu

- [x] **Step 1: Update CSV translation files**
  Add keys:
  - `İş Emri Malzeme Tüketim Stratejisi` -> `Work Order Material Consumption Strategy` / `Materialverbrauchsstrategie für Fertigungsaufträge`
  - `Anlık Stok Rezervasyonu (Klasik)` -> `Instant Stock Reservation (Classic)` / `Sofortige Bestandsreservierung (Klassisch)`
  - `Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)` -> `Capacity-Leveled Consumption (Time-Phased)` / `Kapazitätsorientierter Verbrauch (Zeitphasenorientiert)`
  - Açıklama metinlerinin İngilizce ve Almanca karşılıkları.

- [x] **Step 2: Update Portal and Developer Documentation**
  - Update `erpnextkta/www/docs/mrp-settings.html`:
    Add section explaining the two strategies, the 2-week early pull problem, and how capacity-leveled consumption resolves it.
  - Update `docs/mrp_settings.md`:
    Document `wo_consumption_strategy` parameter and runtime behavior.

- [x] **Step 3: Verify translation compilation**
  Run: `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench build --app erpnextkta --production`
  Expected: Clean build and translation compilation.

---

### Task 4: Koordinatör Kalite Kapısı ve Nihai Doğrulama (Coordinator Quality Gate)

**Files:**
- Check all modified files.

- [x] **Step 1: Run Ruff linter and formatter on modified files**
  Run:
  `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_mrp/`
  `/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_mrp/`

- [x] **Step 2: Restart Bench Services and Clear Cache**
  Run:
  `bench restart`
  `bench --site development.localhost clear-cache`

- [x] **Step 3: Run Full MRP Test Suite**
  Run:
  `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_settings`
  `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_service`
  `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_netting`
  Expected: All tests pass (100% OK).
