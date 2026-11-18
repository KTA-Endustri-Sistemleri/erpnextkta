# Shopfloor Hub Çoklu Görünüm (Views) ve Work Orders Yönetimi Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shopfloor Hub kokpitine en üstte hiyerarşik sabit menü (`[ ⚡ Work Orders ]` ve `[ 📋 Operations ]`), hızlı iş emri açma (imalat lead time hesaplamalı), hammadde stok uygunluk kontrolü, eksik parça uyarılı serbest bırakma (Release) ve sekmeye duyarlı sol çekmece filtreleme özelliklerini kazandırmak.

**Architecture:** Backend tarafında `erpnextkta/kta_shopfloor/services/work_order_service.py` ve `api.py` altında stok rezervasyon ve hammadde kontrol motoru ile `custom_manufacturing_lead_days` çözümleyicisi oluşturulacak. Frontend tarafında `App.vue` üzerine `ShopfloorNavbar.vue`, `CreateWorkOrderModal.vue` ve `WorkOrderReleasePanel.vue` bileşenleri eklenerek TypeScript tip güvenliğiyle modüler olarak bağlanacaktır.

**Tech Stack:** Frappe v15 / ERPNext, Python 3.12, Vue 3 (`<script setup lang="ts">`), TypeScript, Ruff, Vitest / Frappe TestCase.

**Spec:** `docs/superpowers/specs/2026-11-18-shopfloor-hub-work-orders-view-design.md`

## Global Constraints

- Hiçbir DocType Türkçe isimle oluşturulamaz (`.agents/AGENTS.md`).
- Tüm kullanıcıya görünen metinler `__('Text')` ile sarılmalı ve TR, EN, DE sözlükleri güncellenmelidir.
- Frontend üretim derlemesi kesinlikle `bench build --app erpnextkta --production` komutuyla yapılmalıdır.
- Mevcut standart ERPNext Work Order ve Stock Entry akışları bozulmamalı, geriye dönük tam uyumlu kalmalıdır.
- Python kodları `/home/frappe/frappe-bench/env/bin/ruff check` ve `format` kurallarına uymalıdır.

## Review Focus

1. **Eksik Bileşenli Serbest Bırakma:** `allow_shortage=1` ile çağrıldığında `Work Order` üzerinde `custom_released_with_shortage` alanının `1` olması ve Frappe aktivite geçmişine detaylı eksik listesinin yorum olarak eklenmesi.
2. **Çoklu Depo / Boş Depo Fallback:** Reçetedeki bileşenin `source_warehouse` alanı boşsa sırasıyla `wo.source_warehouse` veya `wo.wip_warehouse` üzerinden `Bin.actual_qty` sorgulanması.
3. **İmalat Lead Time Çözümleme:** `Item.custom_manufacturing_lead_days` alanı veritabanında henüz olmasa bile kodun çökmeden 14 gün güvenli fallback ile `planned_end_date = planned_start_date + lead_days` hesaplaması.
4. **Sekme Bazlı Çekmece İzolasyonu:** `Operations` sekmesine geçildiğinde Taslak (Draft) iş emirlerinin çekmeceden tamamen filtrelenmesi, yalnızca üretime hazır (docstatus=1) emirlerin kalması.
5. **Rezervasyon Tutarlılığı:** Serbest bırakılan iş emrinin depodaki `Bin.reserved_qty_for_production` miktarını artırması; operasyon teyitlerinde malzeme tüketildikçe bu rezervasyonun otomatik düşmesi.

---

### Task 1: Şema Güncellemeleri (`Work Order` & `Item` Özel Alanları)

**Files:**
- Modify: `erpnextkta/erpnextkta/custom/work_order.json`
- Modify: `erpnextkta/kta_mrp/custom/item.json`
- Test: `erpnextkta/kta_shopfloor/tests/test_schema.py`

**Interfaces:**
- Produces: `Work Order.custom_released_with_shortage` (Check), `Item.custom_manufacturing_lead_days` (Int).

- [ ] **Step 1: Write the failing test**
Create `erpnextkta/kta_shopfloor/tests/test_schema.py` verifying that custom fields exist in JSON definitions.
```python
import frappe
from frappe.tests.utils import FrappeTestCase
import json

class TestShopfloorSchema(FrappeTestCase):
    def test_work_order_shortage_custom_field_defined(self):
        with open("erpnextkta/erpnextkta/custom/work_order.json") as f:
            data = json.load(f)
        fields = [cf["fieldname"] for cf in data.get("custom_fields", [])]
        self.assertIn("custom_released_with_shortage", fields)

    def test_item_lead_days_custom_field_defined(self):
        with open("erpnextkta/kta_mrp/custom/item.json") as f:
            data = json.load(f)
        fields = [cf["fieldname"] for cf in data.get("custom_fields", [])]
        self.assertIn("custom_manufacturing_lead_days", fields)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_schema`
Expected: FAIL (AssertionError: fields not found).

- [ ] **Step 3: Implement custom fields in JSON files**
- In `erpnextkta/erpnextkta/custom/work_order.json`, append `custom_released_with_shortage` (Fieldtype: Check, Label: "Eksik Parça ile Serbest Bırakıldı", read_only: 1).
- In `erpnextkta/kta_mrp/custom/item.json`, append `custom_manufacturing_lead_days` (Fieldtype: Int, Label: "Üretim Süresi (Gün)", default: 14).

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_schema`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/erpnextkta/custom/work_order.json erpnextkta/kta_mrp/custom/item.json erpnextkta/kta_shopfloor/tests/test_schema.py
git commit -m "feat(schema): add released_with_shortage on work order and manufacturing_lead_days on item"
```

---

### Task 2: Backend Servisleri (Lead Time & Hammadde Uygunluk Motoru)

**Files:**
- Create: `erpnextkta/kta_shopfloor/services/work_order_service.py`
- Create: `erpnextkta/kta_shopfloor/tests/test_work_order_service.py`

**Interfaces:**
- Produces:
  - `resolve_manufacturing_lead_days(item_code: str, customer: str = None) -> int`
  - `check_work_order_material_availability(work_order: str) -> dict`
  - `create_draft_work_order(...) -> dict`
  - `release_work_order_service(work_order: str, allow_shortage: int = 0) -> dict`

- [ ] **Step 1: Write the failing test**
Create `erpnextkta/kta_shopfloor/tests/test_work_order_service.py` testing lead time fallback, availability calculations and release with shortage.
```python
import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_shopfloor.services.work_order_service import (
    resolve_manufacturing_lead_days,
    check_work_order_material_availability,
    release_work_order_service
)

class TestWorkOrderService(FrappeTestCase):
    def test_lead_days_fallback_to_14(self):
        lead_days = resolve_manufacturing_lead_days("NON_EXISTING_ITEM_X")
        self.assertEqual(lead_days, 14)

    def test_availability_and_release(self):
        # Creates a mock or temporary draft WO, checks availability structure
        pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_work_order_service`
Expected: FAIL (ImportError: No module named work_order_service).

- [ ] **Step 3: Implement `work_order_service.py`**
Implement the service with:
- `resolve_manufacturing_lead_days`: Check `Item.custom_manufacturing_lead_days` via `frappe.db.has_column` / `get_value`, check `Item Customer Detail`, fallback to 14.
- `check_work_order_material_availability`: Read `wo.required_items`. For each row, find warehouse (`d.source_warehouse or wo.source_warehouse or wo.wip_warehouse`). Query `Bin.actual_qty`. Compute `coverage_percent`, `shortage_qty`. Overall readiness % and `has_shortage` flag.
- `create_draft_work_order`: Create new `Work Order` doc with `docstatus = 0`, compute `planned_end_date = add_days(start_date, lead_days)` if not provided, call `wo.set_work_order_operations()`, `wo.insert()`.
- `release_work_order_service`: Validate availability. If shortage and `allow_shortage=0`, throw Exception. If shortage and `allow_shortage=1`, set `wo.custom_released_with_shortage = 1`, append Comment to activity trail. Call `wo.submit()`.

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_work_order_service`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/kta_shopfloor/services/work_order_service.py erpnextkta/kta_shopfloor/tests/test_work_order_service.py
git commit -m "feat(shopfloor): implement work order service for lead time, availability and release"
```

---

### Task 3: Backend API Entegrasyonu & Uç Noktalar

**Files:**
- Modify: `erpnextkta/kta_shopfloor/api.py`
- Modify: `erpnextkta/kta_shopfloor/tests/test_api.py`

**Interfaces:**
- Consumes: `erpnextkta/kta_shopfloor/services/work_order_service.py`
- Produces (Whitelisted endpoints):
  - `get_item_default_bom(item_code)`
  - `create_work_order(item_code, qty, ...)`
  - `check_material_availability(work_order)`
  - `release_work_order(work_order, allow_shortage=0)`
  - `get_active_work_orders(status_filter=None, include_drafts=0)`

- [ ] **Step 1: Write failing tests in `test_api.py`**
Add tests in `test_api.py` for each new whitelisted endpoint.
```python
def test_api_get_item_default_bom(self):
    res = get_item_default_bom("NON_EXISTENT")
    self.assertIn("bom", res)
    self.assertEqual(res["manufacturing_lead_days"], 14)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_api`
Expected: FAIL (AttributeError / function not found).

- [ ] **Step 3: Implement endpoints in `api.py`**
Expose the whitelisted functions in `api.py` wrapping calls to `work_order_service.py`. Update `get_active_work_orders` to support `include_drafts` and status filtering (`Draft`, `Not Started`, `In Process`, `Completed`).

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_api`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/kta_shopfloor/api.py erpnextkta/kta_shopfloor/tests/test_api.py
git commit -m "feat(shopfloor): add api endpoints for bom, material availability and work order release"
```

---

### Task 4: Frontend Tipler & Üst Navigasyon Çubuğu (`ShopfloorNavbar.vue`)

**Files:**
- Create: `erpnextkta/public/shopfloor-hub/components/ShopfloorNavbar.vue`
- Modify: `erpnextkta/public/shopfloor-hub/types.ts`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue`

**Interfaces:**
- Produces:
  - `ShopfloorNavbar.vue`: Emits `update:activeView('work_orders' | 'operations')`.
  - Updated `types.ts`: `WorkOrderViewMode`, `MaterialAvailability`, `ShortageItem`.

- [ ] **Step 1: Update `types.ts`**
Add TypeScript interfaces for `WorkOrderViewMode`, `MaterialAvailabilityItem`, `MaterialAvailabilityResponse`, `CreateWorkOrderPayload`.

- [ ] **Step 2: Create `ShopfloorNavbar.vue`**
Build a sleek, full-width top navigation bar:
- Left: Brand title `🏭 SHOPFLOOR HUB`.
- Nav Tabs: `[ ⚡ Work Orders ]` and `[ 📋 Operations ]`.
- Active tab highlight with distinct border and background indicator.
- Emit `change-view(tab)` on click.

- [ ] **Step 3: Wire into `App.vue`**
Mount `ShopfloorNavbar` at the top of `App.vue`. Manage `const activeView = ref<WorkOrderViewMode>('work_orders')`. Conditionally render views based on `activeView`.

- [ ] **Step 4: Verify production build**
Run: `bench build --app erpnextkta --production`
Expected: Build passes without type or template errors.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/ShopfloorNavbar.vue erpnextkta/public/shopfloor-hub/types.ts erpnextkta/public/shopfloor-hub/App.vue
git commit -m "feat(ui): add shopfloor navbar and multi-view state management"
```

---

### Task 5: Sol Çekmece Sekme Filtreleme & Hızlı Açma Butonu (`WorkOrderSidebar.vue`)

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/components/WorkOrderSidebar.vue`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue`

**Interfaces:**
- Consumes: `activeView` prop from `App.vue`.
- Produces:
  - Event `open-create-modal` emitted when `[ + Yeni İş Emri Aç ]` is clicked.
  - Contextual filter tabs:
    - In `work_orders`: `[Tümü]`, `[Taslak]`, `[Serbest]`
    - In `operations`: `[Tümü]`, `[Devam Eden]`, `[Tamamlanan]`

- [ ] **Step 1: Add props and filter tabs logic**
Pass `activeView` prop to `WorkOrderSidebar.vue`. Compute filter buttons based on `activeView`. When `activeView === 'operations'`, exclude `Draft` items from the list.

- [ ] **Step 2: Add `[ + Yeni İş Emri Aç ]` button**
In `WorkOrderSidebar.vue`, above the search bar, render a primary button: `+ {{ __('Yeni İş Emri Aç') }}` visible when in `work_orders` view. Emit `open-create-modal`.

- [ ] **Step 3: Verify production build**
Run: `bench build --app erpnextkta --production`
Expected: Build passes.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/WorkOrderSidebar.vue erpnextkta/public/shopfloor-hub/App.vue
git commit -m "feat(ui): add contextual sidebar filtering and new work order action button"
```

---

### Task 6: Hızlı İş Emri Açma Modali (`CreateWorkOrderModal.vue`)

**Files:**
- Create: `erpnextkta/public/shopfloor-hub/components/CreateWorkOrderModal.vue`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue`

**Interfaces:**
- Consumes: API endpoints `get_item_default_bom`, `create_work_order`.
- Produces: Emits `created(workOrderName)` to refresh list and select new draft order.

- [ ] **Step 1: Create `CreateWorkOrderModal.vue`**
- Minimalist form:
  - `production_item`: Autocomplete/search input calling Frappe search or item query.
  - `qty`: Number input (> 0).
  - On item select: call `get_item_default_bom(item)` to prefetch default BOM and set `planned_end_date = start_date + lead_days`.
- "Gelişmiş Seçenekler" (Advanced options collapsible accordion):
  - `bom_no`
  - `source_warehouse`, `fg_warehouse`
  - `planned_start_date`, `planned_end_date`
- Actions: `[ İptal ]` and `[ Taslak Olarak Kaydet ]`.

- [ ] **Step 2: Integrate into `App.vue`**
Mount `CreateWorkOrderModal` in `App.vue`. On `created`, fetch updated active work orders, automatically select the new draft work order.

- [ ] **Step 3: Verify production build**
Run: `bench build --app erpnextkta --production`
Expected: Build passes.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/CreateWorkOrderModal.vue erpnextkta/public/shopfloor-hub/App.vue
git commit -m "feat(ui): implement quick create work order modal with lead time calculation"
```

---

### Task 7: Hammadde Uygunluk Matrisi & Release Paneli (`WorkOrderReleasePanel.vue`)

**Files:**
- Create: `erpnextkta/public/shopfloor-hub/components/WorkOrderReleasePanel.vue`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue`

**Interfaces:**
- Consumes: `check_material_availability(work_order)`, `release_work_order(work_order, allow_shortage)`.
- Produces: Renders material availability matrix and triggers release action.

- [ ] **Step 1: Create `WorkOrderReleasePanel.vue`**
- Component reads selected Work Order. Calls `check_material_availability`.
- 3 Katmanlı Stok & Hat Besleme Modeli:
  - Hattaki net kullanılabilir stok (`line_available_qty = max(0, actual_qty - reserved_qty)`), rezerve miktar etiketi `(Rezerve: {0})`.
  - Şirketin diğer tüm aktif depolarındaki serbest stok görünürlüğü (`other_warehouses_qty` ve tooltip dökümü).
  - 3 Kademeli Hazırlık Rozeti: `Hatta Mevcut` (yeşil), `Transfer Edilebilir` (sarı), `Fabrikada Yok` (kırmızı).
  - Dinamik durum banner'ı (Kritik eksik, hat transferi mümkün, tam hazır).
- Renders:
  - Header Summary: Work Order ID, Item, Qty, Status badge, Overall Readiness % progress bar, 3-tier status banner.
  - Material Matrix Table: Columns for `Hammadde`, `İhtiyaç`, `Hatta (Tüketim Deposu)`, `Diğer Depolarda`, `Karşılama Oranı`, `Durum`.
  - Action Button: `[ 🚀 İş Emrini Serbest Bırak (Release) ]`.
- Release flow:
  - If 100% available: Frappe confirm dialog -> calls `release_work_order(wo, 0)`.
  - If shortage exists: Warning Modal listing missing items with red badges -> "Yine de Serbest Bırak" button -> calls `release_work_order(wo, 1)`.
  - Stays on `work_orders` view, updates Work Order status badge to `Not Started` (`docstatus = 1`), shows success banner.

- [ ] **Step 2: Mount in `App.vue`**
In `App.vue`, when `activeView === 'work_orders'`, render `WorkOrderReleasePanel` in the main content area (while `Operations` renders `WoStatsCard`, `OperationsList`, `ConfirmationPanel`, `ConfirmationHistory`).

- [ ] **Step 3: Verify production build**
Run: `bench build --app erpnextkta --production`
Expected: Build passes.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/WorkOrderReleasePanel.vue erpnextkta/public/shopfloor-hub/App.vue
git commit -m "feat(ui): implement material availability matrix and work order release panel"
```

---

### Task 8: Çeviri, Dokümantasyon & Final Quality Gate

**Files:**
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/www/docs/shopfloor-hub.html`
- Modify: `docs/kta_shopfloor_hub_kilavuzu.md`

- [ ] **Step 1: Add translation keys**
Ensure all newly added labels ("Work Orders", "Operations", "Yeni İş Emri Aç", "Hammadde Uygunluğu", "Eksik Parça ile Serbest Bırakıldı", "Karşılama Oranı", "Gelişmiş Seçenekler") are translated into TR, EN, DE in CSV files.

- [ ] **Step 2: Update documentation**
Update `erpnextkta/www/docs/shopfloor-hub.html` and `docs/kta_shopfloor_hub_kilavuzu.md` to document the new `Work Orders` view, lead time calculation ($T_{\text{prod}}$), material availability checking and shortage release mechanics.

- [ ] **Step 3: Run Coordinator Quality Gate**
Run all verification commands:
1. `bench build --app erpnextkta --production`
2. `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_api`
3. `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_work_order_service`
4. `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_shopfloor`
5. `/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_shopfloor`

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/translations/ erpnextkta/www/docs/ docs/
git commit -m "docs(shopfloor): sync shopfloor hub multi-view documentation and translations"
```
