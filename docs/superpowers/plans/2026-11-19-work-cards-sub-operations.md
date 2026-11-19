# Work Cards & Sub-Operation Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the "Work Cards" (Çalışma Kartları) 3rd cockpit tab in Shopfloor Hub, backed
by a sub-operation analytics backend service that maps route templates, sub-operation material
consumptions, unique card durations, and scrap allocations.

**Architecture:** A read-only analytics service resolves the full routing checklist of
operations and sub-operations for a Work Order, aggregating real-time data from `Calisma Karti`
and child records with quality inspection guards. Duration is strictly deduplicated at unique
card level, and scraps are mapped either to sub-operation raw materials or operation-level
unassigned scrap buckets. The frontend presents this tree via a 3-tab cockpit navbar, an
analytics panel, and collapsible sub-operation cards with live badge states.

**Tech Stack:** Python 3.12 (Frappe ORM, MariaDB), Vue 3 + Tailwind CSS, TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-19-work-cards-sub-operations-design.md`

## Global Constraints

- STRICT: Every line in markdown, code, and commit message must be <= 100 characters.
- Zero commercial or confidential data (no vendor names or unit prices).
- Title Case UI labels and complete sentence translations.
- Production build command: `bench build --app erpnextkta --production`.
- Defensive Null-Safety: All numeric aggregations must wrap fields in `flt(val or 0)`.
- DocType Terminology: English singular Title Case (e.g., `Calisma Karti`, `Job Card`).

## Review Focus

- Work Order with no Job Cards or unstarted operations (graceful empty state with `⚪ Başlanmadı`).
- Sub-operations with `is_tuketim_hesaplanir == 0` displaying process details without breaking
  consumption formulas.
- Multi-step cards not inflating duration (unique card duration summation).
- Unmatched scraps placed at operation level instead of being lost.
- Permission checks throwing proper `frappe.PermissionError` on unpermitted Work Order.

---

### Task 1: Backend Analytics Service Core (`work_card_analytics_service.py` & unit test)

**Files:**
- Create: `erpnextkta/kta_calisma_karti/services/work_card_analytics_service.py`
- Test: `erpnextkta/kta_calisma_karti/tests/test_work_card_analytics.py`

**Interfaces:**
- Consumes: Frappe ORM queries on `Work Order`, `Job Card`, `KTA Operation ERPNext Mappings`,
  `KTA Calisma Karti Operasyonlari`, `KTA Calisma Karti Alt Operasyonlari`, `Calisma Karti`,
  `Calisma Karti Alt Operasyon Kayitlari`, and `Calisma Karti Hurda`.
- Produces: `get_work_order_card_analytics(work_order: str) -> dict[str, Any]` returning:
  - `work_order`: string ID
  - `production_item`: string Item Code
  - `item_name`: string Item Name
  - `qty`: float target quantity
  - `summary`: dict (`total_cards`, `completed_cards`, `in_progress_cards`,
    `total_duration_mins`, `total_scrap_qty`)
  - `operations`: list of operations with `unmatched_scraps` and `sub_operations` tree.

- [ ] **Step 1: Write the failing unit tests**

Create `erpnextkta/kta_calisma_karti/tests/test_work_card_analytics.py` with tests covering all
five Review Focus cases:
```python
import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_calisma_karti.services.work_card_analytics_service import (
    get_work_order_card_analytics,
)


class TestWorkCardAnalyticsService(FrappeTestCase):
    def test_permission_error_on_unpermitted_work_order(self):
        # User without read access raises frappe.PermissionError
        frappe.set_user("test_no_perm@example.com")
        try:
            get_work_order_card_analytics("NON-EXISTENT-OR-FORBIDDEN-WO")
            self.fail("Should raise PermissionError")
        except (frappe.PermissionError, frappe.DoesNotExistError):
            pass
        finally:
            frappe.set_user("Administrator")

    def test_empty_work_order_graceful_response(self):
        # Empty/unstarted WO returns 0 metrics and 'Başlanmadı' badges
        result = get_work_order_card_analytics("TEST-EMPTY-WO")
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["total_cards"], 0)
        for op in result.get("operations", []):
            for sub in op.get("sub_operations", []):
                self.assertEqual(sub["status"], "Başlanmadı")
                self.assertEqual(sub["status_badge"], "⚪ Başlanmadı")
                self.assertEqual(sub["total_process_qty"], 0.0)

    def test_non_consumption_sub_operation(self):
        # is_tuketim_hesaplanir == 0 returns process qty and duration,
        # but empty consumptions list without calculation errors
        result = get_work_order_card_analytics("TEST-WO-WITH-NON-CONSUMPTION")
        for op in result.get("operations", []):
            for sub in op.get("sub_operations", []):
                if sub.get("is_tuketim_hesaplanir") == 0:
                    self.assertEqual(sub["consumptions"], [])
                    self.assertGreaterEqual(sub["total_process_qty"], 0.0)

    def test_duration_deduplication_multi_step_card(self):
        # Single card with multiple sub-ops must not double count
        # duration in operation or summary level
        result = get_work_order_card_analytics("TEST-WO-MULTI-STEP")
        summary_dur = result["summary"]["total_duration_mins"]
        total_unique = sum(
            op["total_duration_mins"] for op in result["operations"]
        )
        self.assertEqual(summary_dur, total_unique)

    def test_unmatched_scraps_attached_to_operation(self):
        # Scraps not matching sub-op raw materials land in unmatched_scraps
        result = get_work_order_card_analytics("TEST-WO-SCRAPS")
        for op in result.get("operations", []):
            if op.get("unmatched_scraps"):
                for sc in op["unmatched_scraps"]:
                    self.assertIn("item_code", sc)
                    self.assertIn("qty", sc)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_calisma_karti.tests.test_work_card_analytics
```
Expected: FAIL with `ModuleNotFoundError: No module named '...work_card_analytics_service'`

- [ ] **Step 3: Implement `work_card_analytics_service.py`**

Create `erpnextkta/kta_calisma_karti/services/work_card_analytics_service.py` with:
- `validate_work_order_access(work_order: str) -> None`: checks `frappe.has_permission`.
- `get_route_template(work_order: str) -> list[dict]`: reads `Job Card` and mapped
  `KTA Calisma Karti Operasyonlari` / `KTA Calisma Karti Alt Operasyonlari`.
- `aggregate_card_metrics(work_order: str, operations: list[dict]) -> dict`:
  - Queries `Calisma Karti` where `custom_work_order = work_order` and `docstatus != 2`.
  - Queries `Calisma Karti Alt Operasyon Kayitlari` where `docstatus != 2` and
    `quality_inspection_status NOT IN ('Reddedildi', 'Rejected', 'Red')`.
  - Computes consumption: `(boyut_mm * adet) / 1000.0` for length items; `adet` for discrete.
  - Queries `Calisma Karti Hurda` where `docstatus != 2`. Matches `parca_no` to sub-op raw
    materials; else attaches to operation `unmatched_scraps`.
  - Deduplicates card durations: `total_duration_mins` at op & summary levels uses unique cards.
  - Formats status badge: `⚪ Başlanmadı`, `🔵 Devam Ediyor`, `🟢 Tamamlandı`.
- Main facade: `get_work_order_card_analytics(work_order: str) -> dict[str, Any]`

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_calisma_karti.tests.test_work_card_analytics
```
Expected: PASS (OK)

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_calisma_karti/services/work_card_analytics_service.py \
  erpnextkta/kta_calisma_karti/tests/test_work_card_analytics.py
git commit -m "feat(cards): implement work card sub-operation analytics service"
```

---

### Task 2: API Facade & Whitelist Endpoint (`api.py`)

**Files:**
- Create: `erpnextkta/kta_calisma_karti/api_impl/analytics.py`
- Modify: `erpnextkta/kta_calisma_karti/api.py:15-30`
- Test: `erpnextkta/kta_calisma_karti/tests/test_api.py`

**Interfaces:**
- Consumes: `erpnextkta.kta_calisma_karti.services.work_card_analytics_service`
- Produces: Whitelisted endpoint `erpnextkta.kta_calisma_karti.api.get_work_order_card_analytics`
  callable via `frappe.call`.

- [ ] **Step 1: Write failing test in `test_api.py`**

In `erpnextkta/kta_calisma_karti/tests/test_api.py`, add:
```python
    def test_get_work_order_card_analytics_whitelisted(self):
        import erpnextkta.kta_calisma_karti.api as api
        self.assertTrue(hasattr(api, "get_work_order_card_analytics"))
        fn = getattr(api, "get_work_order_card_analytics")
        self.assertTrue(getattr(fn, "__whitelisted__", False))
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_calisma_karti.tests.test_api
```
Expected: FAIL (AssertionError: function not found in `api`).

- [ ] **Step 3: Implement endpoint and re-export in `api.py`**

Create `erpnextkta/kta_calisma_karti/api_impl/analytics.py`:
```python
import frappe
from erpnextkta.kta_calisma_karti.services.work_card_analytics_service import (
    get_work_order_card_analytics as _get_analytics,
)


@frappe.whitelist()
def get_work_order_card_analytics(work_order: str) -> dict:
    if not work_order:
        frappe.throw(frappe._("Work Order is required"), frappe.MandatoryError)
    return _get_analytics(work_order.strip())
```

In `erpnextkta/kta_calisma_karti/api.py`:
```python
from .api_impl.analytics import get_work_order_card_analytics
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_calisma_karti.tests.test_api
```
Expected: PASS (OK)

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_calisma_karti/api_impl/analytics.py \
  erpnextkta/kta_calisma_karti/api.py \
  erpnextkta/kta_calisma_karti/tests/test_api.py
git commit -m "feat(api): expose get_work_order_card_analytics endpoint"
```

---

### Task 3: Frontend Sub-Operation Component (`WorkCardSubOperationCard.vue`)

**Files:**
- Create: `erpnextkta/public/shopfloor-hub/components/WorkCardSubOperationCard.vue`
- Modify: `erpnextkta/public/shopfloor-hub/types.ts:60-120`

**Interfaces:**
- Consumes: `SubOperationAnalytics` interface from `types.ts`.
- Produces: `<WorkCardSubOperationCard :sub-op="subOp" />` collapsible Vue 3 component.

- [ ] **Step 1: Add TypeScript interfaces to `types.ts`**

In `erpnextkta/public/shopfloor-hub/types.ts`, append:
```typescript
export interface MaterialConsumptionItem {
  item_code: string;
  item_name?: string | null;
  total_qty: number;
  uom: string;
}

export interface ScrapAllocationItem {
  item_code: string;
  qty: number;
  uom: string;
  reason?: string | null;
}

export interface CardDetailItem {
  card_name: string;
  operator?: string | null;
  durum: string;
  net_calisma_suresi: number;
  islem_adedi: number;
  creation: string;
}

export interface SubOperationAnalytics {
  sub_op_id: string;
  title: string;
  sequence: number;
  status: string;
  status_badge: string;
  is_tuketim_hesaplanir: number;
  total_process_qty: number;
  total_duration_mins: number;
  consumptions: MaterialConsumptionItem[];
  scraps: ScrapAllocationItem[];
  cards: CardDetailItem[];
}
```

- [ ] **Step 2: Implement `WorkCardSubOperationCard.vue`**

Create `erpnextkta/public/shopfloor-hub/components/WorkCardSubOperationCard.vue`:
- `<script setup lang="ts">` with `isOpen = ref(false)`.
- Global translation helper: `const __ = (...args: any[]) => (window as any).__(...args);`.
- Header:
  - Sequence badge: `#{{ subOp.sequence }}`
  - Title: `{{ subOp.title }}`
  - Status badge: `⚪ Başlanmadı`, `🔵 Devam Ediyor`, `🟢 Tamamlandı`
  - Process qty badge: `{{ subOp.total_process_qty }} Adet`
  - Duration badge: `{{ subOp.total_duration_mins }} dk`
  - Tüketimsiz rozet: `[ 🔍 Tüketimsiz İşlem ]` if `subOp.is_tuketim_hesaplanir === 0`
- Collapsible Body (`v-if="isOpen"`):
  - Consumptions section (table with item_code, item_name, total_qty, uom).
  - Scraps section (table with item_code, qty, uom, reason).
  - Contributing cards section (card_name link, operator, durum, süre, islem_adedi).
  - Empty state fallback if `subOp.cards.length === 0`: `{{ __('Henüz Kart Açılmadı') }}`.

- [ ] **Step 3: Verify TypeScript compilation**

Run: `bench build --app erpnextkta --production`
Expected: SUCCESS

- [ ] **Step 4: Commit**

```bash
git add erpnextkta/public/shopfloor-hub/types.ts \
  erpnextkta/public/shopfloor-hub/components/WorkCardSubOperationCard.vue
git commit -m "feat(hub): add WorkCardSubOperationCard component"
```

---

### Task 4: Frontend Main Analytics Panel & Navbar

**Files:**
- Create: `erpnextkta/public/shopfloor-hub/components/WorkCardAnalyticsPanel.vue`
- Modify: `erpnextkta/public/shopfloor-hub/components/ShopfloorNavbar.vue:1-35`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue:1-40,340-390`
- Modify: `erpnextkta/public/shopfloor-hub/types.ts:1-10`

**Interfaces:**
- Consumes: `WorkOrderViewMode` union (`"work_orders" | "operations" | "work_cards"`),
  `frappe.call` invoking `erpnextkta.kta_calisma_karti.api.get_work_order_card_analytics`.
- Produces: 3rd tab in Shopfloor Hub cockpit with summary stats, operation list, and
  hierarchical sub-operation drilldown.

- [ ] **Step 1: Extend `WorkOrderViewMode` in `types.ts`**

Change in `erpnextkta/public/shopfloor-hub/types.ts`:
```typescript
export type WorkOrderViewMode = "work_orders" | "operations" | "work_cards";

export interface WorkCardSummaryStats {
  total_cards: number;
  completed_cards: number;
  in_progress_cards: number;
  total_duration_mins: number;
  total_scrap_qty: number;
}

export interface OperationCardAnalytics {
  operation_name: string;
  job_card?: string | null;
  status: string;
  total_duration_mins: number;
  unmatched_scraps: ScrapAllocationItem[];
  sub_operations: SubOperationAnalytics[];
}

export interface WorkOrderCardAnalyticsResponse {
  work_order: string;
  production_item: string;
  item_name?: string | null;
  qty: number;
  summary: WorkCardSummaryStats;
  operations: OperationCardAnalytics[];
}
```

- [ ] **Step 2: Update `ShopfloorNavbar.vue`**

In `erpnextkta/public/shopfloor-hub/components/ShopfloorNavbar.vue`, update `tabs` array:
```typescript
const tabs: NavTab[] = [
  { id: 'work_orders', icon: '⚡', label: 'Work Orders' },
  { id: 'operations', icon: '📋', label: 'Operations' },
  { id: 'work_cards', icon: '📇', label: 'Work Cards' },
];
```

- [ ] **Step 3: Implement `WorkCardAnalyticsPanel.vue`**

Create `erpnextkta/public/shopfloor-hub/components/WorkCardAnalyticsPanel.vue`:
- Props: `workOrder: string`, `loadingWorkOrder?: boolean`.
- State: `analyticsData = ref<WorkOrderCardAnalyticsResponse | null>(null)`,
  `loading = ref<boolean>(false)`, `error = ref<string | null>(null)`.
- Watch `props.workOrder`: calls `erpnextkta.kta_calisma_karti.api.get_work_order_card_analytics`.
- Top metrics row:
  - Toplam Kart (`summary.total_cards`)
  - Tamamlanan Kart (`summary.completed_cards`)
  - Devam Eden Kart (`summary.in_progress_cards`)
  - Toplam Çalışma Süresi (`summary.total_duration_mins` dk)
  - Toplam Hurda (`summary.total_scrap_qty`)
- Operation list accordion:
  - Operation title + Job Card link + total op duration badge.
  - Unmatched scraps banner if `op.unmatched_scraps.length > 0`.
  - Loop over `op.sub_operations` rendering `<WorkCardSubOperationCard :sub-op="subOp" />`.

- [ ] **Step 4: Wire `WorkCardAnalyticsPanel` into `App.vue`**

In `erpnextkta/public/shopfloor-hub/App.vue`:
- Import `WorkCardAnalyticsPanel`.
- Under `<template v-if="activeView === 'work_orders'"> ... </template>`, add:
```html
<template v-else-if="activeView === 'work_cards'">
  <WorkCardAnalyticsPanel
    v-if="selectedWorkOrder"
    :work-order="selectedWorkOrder"
    :loading-work-order="loading"
  />
  <div v-else class="empty-state">
    <div class="empty-icon">📇</div>
    <h3 class="empty-title">{{ __('Work Cards') }}</h3>
    <p class="empty-desc">
      {{ __('Select a Work Order to inspect cards.') }}
    </p>
  </div>
</template>
```

- [ ] **Step 5: Run production build check**

Run: `bench build --app erpnextkta --production`
Expected: SUCCESS with zero TypeScript or bundling errors.

- [ ] **Step 6: Commit**

```bash
git add erpnextkta/public/shopfloor-hub/types.ts \
  erpnextkta/public/shopfloor-hub/components/ShopfloorNavbar.vue \
  erpnextkta/public/shopfloor-hub/components/WorkCardAnalyticsPanel.vue \
  erpnextkta/public/shopfloor-hub/App.vue
git commit -m "feat(hub): add Work Cards 3rd tab and WorkCardAnalyticsPanel"
```

---

### Task 5: Translations & Portal Docs Sync (`tr.csv`, `en.csv`, `de.csv`, `erpnextkta/www/docs/`)

**Files:**
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/www/docs/shopfloor-hub.html`
- Modify: `erpnextkta/www/docs/calisma-karti.html`

**Interfaces:**
- Consumes: UI translation keys in Title Case and unified sentences.
- Produces: Updated translations and end-user portal documentation under `/docs/`.

- [ ] **Step 1: Update CSV dictionaries**

Append following pairs to `erpnextkta/translations/tr.csv`:
```csv
"Work Cards","Çalışma Kartları"
"Sub-Operation Analytics","Alt Operasyon Analitiği"
"No Material Consumption","Tüketimsiz İşlem"
"Process Count","İşlem Adedi"
"Net Work Duration","Net Çalışma Süresi"
"Contributing Cards","Katkı Sağlayan Kartlar"
"Not Started","Başlanmadı"
"Unassigned Scraps","Eşleşmeyen Hurdalar"
"Select a Work Order to inspect cards.","Kartları incelemek için bir iş emri seçin."
```

Append to `erpnextkta/translations/en.csv`:
```csv
"Work Cards","Work Cards"
"Sub-Operation Analytics","Sub-Operation Analytics"
"No Material Consumption","No Material Consumption"
"Process Count","Process Count"
"Net Work Duration","Net Work Duration"
"Contributing Cards","Contributing Cards"
"Not Started","Not Started"
"Unassigned Scraps","Unassigned Scraps"
"Select a Work Order to inspect cards.","Select a Work Order to inspect cards."
```

Append to `erpnextkta/translations/de.csv`:
```csv
"Work Cards","Arbeitskarten"
"Sub-Operation Analytics","Unteroperationsanalytik"
"No Material Consumption","Kein Materialverbrauch"
"Process Count","Bearbeitungsmenge"
"Net Work Duration","Nettoarbeitszeit"
"Contributing Cards","Beteiligte Karten"
"Not Started","Nicht Begonnen"
"Unassigned Scraps","Nicht Zugewiesener Ausschuss"
"Select a Work Order to inspect cards.","Wählen Sie einen Auftrag zur Ansicht."
```

- [ ] **Step 2: Update Portal Documentation in `erpnextkta/www/docs/shopfloor-hub.html`**

Add section "3. Çalışma Kartları ve Alt Operasyon Analitiği (Work Cards Tab)":
- Explain the 3rd tab purpose (cockpit tracking of actual shopfloor work cards).
- Document the full route checklist approach (Opsiyon 1: Tam Rota Kontrol Listesi).
- Document sub-operation consumption formulas (length vs. discrete).
- Document non-consumption sub-operations (`is_tuketim_hesaplanir == 0`).
- Document unique card duration deduplication and scrap allocation logic.

- [ ] **Step 3: Update `erpnextkta/www/docs/calisma-karti.html`**

Add cross-reference note linking `Calisma Karti` shopfloor lifecycle with the new Shopfloor Hub
cockpit tab `/desk#shopfloor-hub` (Work Cards tab).

- [ ] **Step 4: Verify CSV and documentation syntax**

Verify CSV line structure and validate HTML syntax in portal pages.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/translations/tr.csv \
  erpnextkta/translations/en.csv \
  erpnextkta/translations/de.csv \
  erpnextkta/www/docs/shopfloor-hub.html \
  erpnextkta/www/docs/calisma-karti.html
git commit -m "docs(hub): sync translations and portal documentation for work cards tab"
```

---

### Task 6: Coordinator Quality Gate & Verification

**Files:**
- Test: All modified files in Tasks 1-5.

**Interfaces:**
- Consumes: Test runners, build pipeline, ruff linter.
- Produces: Clean pass across all repository gates.

- [ ] **Step 1: Run frontend production build**

Run: `bench build --app erpnextkta --production`
Expected: Build finished successfully without warnings or syntax errors.

- [ ] **Step 2: Run backend tests**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta --module erpnextkta.kta_calisma_karti
```
Expected: All tests PASS.

- [ ] **Step 3: Run Python linter & format checks**

Run:
```bash
SRCS="erpnextkta/kta_calisma_karti/services/work_card_analytics_service.py"
SRCS="$SRCS erpnextkta/kta_calisma_karti/api_impl/analytics.py"
SRCS="$SRCS erpnextkta/kta_calisma_karti/tests/test_work_card_analytics.py"
/home/frappe/frappe-bench/env/bin/ruff check $SRCS
/home/frappe/frappe-bench/env/bin/ruff format --check $SRCS
```
Expected: All checks pass with 0 errors.

- [ ] **Step 4: Run line length verification (<= 100 characters)**

Verify with python one-liner:
```bash
python3 -c "
import sys
for p in sys.argv[1:]:
    with open(p) as f:
        for idx, line in enumerate(f, 1):
            if len(line.rstrip('\r\n')) > 100:
                print(f'{p}:{idx} exceeds 100 chars ({len(line.rstrip())})')
" docs/superpowers/plans/2026-11-19-work-cards-sub-operations.md
```
Expected: Zero lines exceeding 100 characters.

- [ ] **Step 5: Handoff / Final Gate Completion**

All deliverables verified against spec requirements and design invariants.
