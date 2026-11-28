# Faz 2 Implementation Plan: 2-Tab Vue 3 + TypeScript Stock Reconciliation & Relabeling Hub (`stock-reco-dashboard`)

> **For agentic workers:** Coordinator dispatches specialist subagents (`kta-stock`, `frontend-public`, `docs-i18n` when strings added) strictly respecting `.agents/subagents/*.md` folder locks. Required sub-skill: `superpowers:subagent-driven-development`.

**Goal:** Build the Stock Reconciliation labeling/standardization backend endpoints and refactor `erpnextkta/public/stock-reco-dashboard/` into a modular, 2-tab Vue 3 + TypeScript SPA supporting batch count creation, Mod 1 / Mod 2 count-day relabeling with box splits & `LEGACY` conversion, and live Socket.IO variance/anomaly analytics.

**Architecture:** Tab 1 (`Sayım Operasyonları & Etiketleme`) consolidates bulk Stock Reconciliation creation, document browsing, and relabeling using Faz 1's `relabeling_service.py` (draft rows expand directly inside Draft Stock Reconciliation before atomic submit+print; submitted docs update/re-label single boxes directly or dispatch 1-source `Package Split` Repacks for splits/`LEGACY`). Tab 2 preserves 100% of the existing live variance/anomaly dashboard in clean TypeScript + Light/Dark theme components. Every `.vue` file stays strictly `< 500` lines.

**Tech Stack:** Frappe Framework / ERPNext v15 (Python 3.11), Vue 3 (`<script setup lang="ts">`), TypeScript, esbuild (`bench build`), Socket.IO (`frappe.realtime`), `ZebraPrinterManager.send_batch`.

**Spec:** `docs/superpowers/specs/2026-11-21-faz2-stock-reco-hub-vue-ts-design.md`

---

## Global Constraints

- Depends on Faz 1 (`erpnextkta/kta_stock/services/{stock_reconciliation_service.py, relabeling_service.py}`).
- Every `.vue` component MUST be `< 500` lines, include `const __ = (...args: any[]) => (window as any).__(...args);`, support Light & `[data-theme="dark"]`, use `<Teleport to="body">` for modals, use whole-sentence Title Case translations, and avoid TypeScript `as` casts inside `<template>` expressions.
- Stock Reconciliation Form Desk behavior (`Depodan Ürünleri Getir`, `remove_items_with_no_change` override) MUST continue working identically; no automatic label printing occurs when someone submits Stock Reconciliation directly in Desk without using the Relabeling Hub.
- Keep zero real supplier/customer company names or real unit prices in code/tests/copy.
- Every commit message line strictly `<= 100` chars (`<= 75` chars target).

## Review Focus

1. **ERPNext v15 `Stock Reconciliation Item` clears `batch_no` into `serial_and_batch_bundle` on submit:** Backend preview and relabeling MUST inspect `serial_and_batch_bundle` (`Serial and Batch Entry`) when `row.batch_no` is empty on submitted docs so Mod 1 / Mod 2 never shows `Batch: None`. *(Pinned to Task 1 tests)*
2. **Draft `Stock Reconciliation` relabeling MUST NOT print orphan labels before submit:** Draft splits/conversions must rewrite draft rows inside `Stock Reconciliation`, submit atomically (`Onayla ve Etiketleri Bas`), and print only if `submit()` succeeds. *(Pinned to Task 2 tests)*
3. **Deep-linking to an already-mounted `stock-reco-dashboard` Desk page:** Navigating back from a `Stock Reconciliation` Form (`frappe.route_options = { doc, tab }`) when `stock-reco-dashboard` is already cached in DOM MUST trigger `on_page_show` event synchronization in `stock_reco_dashboard.js` -> `App.vue` so the target document opens immediately. *(Pinned to Task 7 verification)*
4. **Lock bypass on post-submit `Package Split`:** If another Draft Stock Reconciliation exists on a sibling/parent warehouse, submitted-doc split must respect role permission (`Stock Reconciliation Manager`) or pass `ignore_reco_lock` only for `Stock Reconciliation Manager` users. *(Pinned to Task 2 tests)*
5. **`box_splits` sum validation & float tolerance:** Splitting `7.750` into `[5.0, 2.75]` must handle floating point precision (`abs(sum(splits) - qty) <= 0.0001`) without false mismatches or silent qty loss. *(Pinned to Task 2 & Task 5 tests)*

---

## Subagent Ownership & File Structure

| Task | Subagent | Files Owned / Touched |
|---|---|---|
| Task 1 | `kta-stock` | Modify `erpnextkta/kta_stock/services/stock_reconciliation_service.py` (`list_stock_reconciliations`, `get_stock_reconciliation_label_preview`); Test in `erpnextkta/kta_stock/tests/test_stock_reconciliation_relabeling.py` |
| Task 2 | `kta-stock` | Modify `erpnextkta/kta_stock/services/stock_reconciliation_service.py` (`submit_and_print_stock_reconciliation`, `relabel_submitted_stock_reconciliation`); Test in `test_stock_reconciliation_relabeling.py` |
| Task 3 | `frontend-public` | Create `erpnextkta/public/stock-reco-dashboard/{tsconfig.json, frappe.d.ts, types.ts}`; Update `stock-reco-dashboard.bundle.js` |
| Task 4 | `frontend-public` | Create `erpnextkta/public/stock-reco-dashboard/components/{BulkCreateRecoModal.vue, RecoDocumentsList.vue}` (`< 500` lines each) |
| Task 5 | `frontend-public` | Create `erpnextkta/public/stock-reco-dashboard/components/RecoLabelingWorkspace.vue` (`< 500` lines; Mod 1 / Mod 2, box splits, LEGACY flag, print trigger) |
| Task 6 | `frontend-public` | Create `erpnextkta/public/stock-reco-dashboard/components/{RecoAnalyticsTab.vue, RecoItemDrawer.vue}` (`< 500` lines each); Refactor `App.vue` (`< 500` lines) |
| Task 7 | `kta-stock` & `frontend-public` | Modify `erpnextkta/kta_stock/page/stock_reco_dashboard/stock_reco_dashboard.js` (`on_page_show` route options) & `erpnextkta/public/js/stock_reconciliation.js` (add hub shortcut button) |

---

### Task 1: Stock Reconciliation Listing & v15-Aware Label Health Preview API (`kta-stock`)

**Files:**
- Modify: `erpnextkta/kta_stock/services/stock_reconciliation_service.py`
- Create: `erpnextkta/kta_stock/tests/test_stock_reconciliation_relabeling.py`

**Interfaces:**
- Produces:
  - `@frappe.whitelist() def list_stock_reconciliations(status_filter: str = "all", warehouse: str | None = None, search: str | None = None, limit: int = 50) -> list[dict]`
  - `@frappe.whitelist() def get_stock_reconciliation_label_preview(stock_reconciliation: str) -> dict` returning `{"doc": {...}, "rows": [{"row_name", "item_code", "item_name", "uom", "warehouse", "batch_no", "is_standard_batch", "is_legacy", "qty", "current_qty", "label_name", "label_qty", "status", "suggested_mode1_selected"}], "summary": {"total_positive", "valid", "qty_changed", "missing_label", "legacy_batch"}}`

- [x] **Step 1: Write failing tests in `test_stock_reconciliation_relabeling.py` (`kta-stock`)**
  1. Test `get_stock_reconciliation_label_preview` on a **submitted** `Stock Reconciliation` whose row has `batch_no=None` and a `Serial and Batch Bundle` holding two batches (`6640A670001` qty changed, `LEGACY-TEST` legacy): returns 2 preview entries with exact statuses `"qty_changed"` and `"legacy_batch"` and `suggested_mode1_selected == True`.
  2. Test valid box row (`label.qty == row.qty` & standard `7+4` batch): returns status `"valid"` and `suggested_mode1_selected == False`.

- [x] **Step 2: Run test to verify failure**
  Run: `docker exec -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_stock_reconciliation_relabeling`
  Expected: FAIL (`ImportError`).

- [x] **Step 3: Implement `list_stock_reconciliations` and `get_stock_reconciliation_label_preview` (`kta-stock`)**
  Enforce `frappe.has_permission("Stock Reconciliation", "read", throw=True)`. Read both `row.batch_no` and `Serial and Batch Entry` rows (`is_outward=0`, positive qty) so both Draft and Submitted docs resolve every counted batch accurately. Match active `Depo Giriş Etiketi` records in bulk (`batch IN (...)`) to avoid N+1 queries.

- [x] **Step 4: Run tests to verify pass**
  Expected: PASS.

---

### Task 2: Draft Submit+Print & Submitted Relabeling/Split Execution APIs (`kta-stock`)

**Files:**
- Modify: `erpnextkta/kta_stock/services/stock_reconciliation_service.py`
- Test: `erpnextkta/kta_stock/tests/test_stock_reconciliation_relabeling.py`

**Interfaces:**
- Consumes: `relabeling_service.{generate_new_base_lot, allocate_next_box_batches, upsert_box_label, create_package_split_repack, resolve_batch_label_metadata}` and `label_manager.{enqueue_print_labels_by_names, LabelPrinter.clear_empty_labels}`
- Produces:
  - `@frappe.whitelist(methods=["POST"]) def submit_and_print_stock_reconciliation(stock_reconciliation: str, selected_items: list[dict] | str, print_labels: int = 1) -> dict`
  - `@frappe.whitelist(methods=["POST"]) def relabel_submitted_stock_reconciliation(stock_reconciliation: str, selected_items: list[dict] | str, print_labels: int = 1) -> dict`

- [x] **Step 1: Write failing tests (`kta-stock`)**
  1. Draft `Stock Reconciliation` with a `LEGACY` item (`batch_no="LEGACY-TEST"`, `current_qty=77.5`, `qty=77.5`) and `box_splits=[50.0, 27.5], convert_legacy=1`: calling `submit_and_print_stock_reconciliation` retains a zero-out row (`batch_no="LEGACY-TEST", qty=0`), appends 2 new `{base_lot}0001` (`50.0`) & `{base_lot}0002` (`27.5`) rows preserving `valuation_rate`, submits (`docstatus == 1`), verifies `"LEGACY-TEST"` net balance is `0` (NOT doubled to `155`!), removes `"LEGACY-TEST"` label, creates 2 new `KTA Stock Label` records, and calls `enqueue_print_labels_by_names`.
  2. Draft standard `7+4` box split (`batch_no="6640A670001"`, `qty=77.5`, `box_splits=[50.0, 27.5]`): retains `50.0` on `"6640A670001"` and mints 1 sibling `"6640A670002"` for `27.5` (copying `valuation_rate`).
  3. Draft float sum mismatch (`sum(box_splits) != qty`): throws `frappe.ValidationError` and leaves document in `docstatus == 0` with **0** printed/created labels.
  4. Submitted `Stock Reconciliation`: direct relabel updates/creates `KTA Stock Label` for single standard row without extra Stock Entry; multi-box split or `convert_legacy=1` calls `create_package_split_repack(..., ignore_reco_lock=True)` when Manager runs under sibling Draft lock and prints only the newly formed labels.

- [x] **Step 2: Run tests to verify failure**
  Expected: FAIL.

- [x] **Step 3: Implement both endpoints in `stock_reconciliation_service.py` (`kta-stock`)**
  Validate permissions (`write` and `"submit"` for Draft submit). Parse JSON payload, verify `abs(sum(box_splits) - qty) <= 1e-4` when `box_splits` is supplied, expand Draft rows cleanly before `doc.submit()` (always keeping explicit `qty=0` row for replaced `LEGACY` batches and copying `valuation_rate` / `current_valuation_rate`), run `LabelPrinter.clear_empty_labels()` once after submit/split, and invoke `enqueue_print_labels_by_names` when `cint(print_labels) == 1`.

- [x] **Step 4: Run tests to verify pass**
  Expected: PASS.

---

### Task 3: SPA TypeScript Scaffolding & Entry Point (`frontend-public`)

**Files:**
- Create: `erpnextkta/public/stock-reco-dashboard/tsconfig.json`
- Create: `erpnextkta/public/stock-reco-dashboard/frappe.d.ts`
- Create: `erpnextkta/public/stock-reco-dashboard/types.ts`
- Modify: `erpnextkta/public/stock-reco-dashboard/stock-reco-dashboard.bundle.js`

**Interfaces:**
- Produces TypeScript interfaces: `RecoMainTab` (`"operations" | "analytics"`), `RecoRelabelMode` (`"mode1_changed" | "mode2_all"`), `StockRecoListRow`, `StockRecoPreviewRow`, `StockRecoPreviewResponse`, `StockRecoRelabelSelection`, `StockRecoRelabelResult`, `RecoAnalyticsItem`, `RecoAnomalyItem`, `RecoDocDetail`.

- [x] **Step 1: Add TypeScript config & declarations matching `shopfloor-hub` (`frontend-public`)**
  Create `tsconfig.json`, `frappe.d.ts`, `types.ts`, and add `const __` support cleanly via strict TS types (all property names matching Task 1 & Task 2 backend JSON contracts verbatim).

- [x] **Step 2: Verify TypeScript compilation baseline (`npx tsc --noEmit` / `bench build`)**

---

### Task 4: Bulk Create Modal & Reco Documents List Components (`frontend-public`)

**Files:**
- Create: `erpnextkta/public/stock-reco-dashboard/components/BulkCreateRecoModal.vue` (`< 350` lines)
- Create: `erpnextkta/public/stock-reco-dashboard/components/RecoDocumentsList.vue` (`< 350` lines)

**Interfaces:**
- `BulkCreateRecoModal.vue`: Props `(show, defaultCompany)`, Emits `(close, queued)`; calls `create_stock_reco_docs_for_warehouse_group`. Uses `<Teleport to="body">`, Light & Dark CSS vars.
- `RecoDocumentsList.vue`: Props `(docs, selectedDocName, loading, statusFilter, search)`, Emits `(select-doc, update:statusFilter, update:search, refresh)`.

- [x] **Step 1: Implement `BulkCreateRecoModal.vue` & `RecoDocumentsList.vue` (`frontend-public`)**
  Use Link/warehouse autocomplete or fetched group warehouse dropdown (`Warehouse`, `is_group=1`), whole-sentence `__(...)`, zero `as` casts in templates.

- [x] **Step 2: Verify line count `< 500` on each file**

---

### Task 5: Reco Labeling Workspace Component (`Mod 1 / Mod 2`, Box Splits & `LEGACY`) (`frontend-public`)

**Files:**
- Create: `erpnextkta/public/stock-reco-dashboard/components/RecoLabelingWorkspace.vue` (`< 480` lines)

**Interfaces:**
- Props: `(preview: StockRecoPreviewResponse | null, loading: boolean, submitting: boolean)`
- Emits: `(refresh, execute)` emitting `{ mode, selectedItems, isDraftSubmit, printLabels }`

- [x] **Step 1: Implement `RecoLabelingWorkspace.vue` (`frontend-public`)**
  - Top bar: Document title, `docstatus` badge (`Taslak` / `Onaylı`), status counters (`Uyumlu`, `Değişen`, `Eksik`, `LEGACY`), **Mod 1** vs **Mod 2** pill toggle.
  - Table: Selection checkbox, Item code/name, Warehouse, Batch & format badge (`LEGACY` highlight + "Standart Koliye Çevir" toggle), System qty vs Existing Label qty diff, inline **Kutu Kırılımı** editor (`+ Kutu Ekle`, live remaining sum validation against `row.qty`).
  - Bottom action bar: Print checkbox (default checked), selected row & label count summary, primary button dynamically labeled **`Onayla ve Etiketleri Bas`** (when `docstatus === 0`) or **`Etiketleri Güncelle ve Bas`** (when `docstatus === 1`).

- [x] **Step 2: Verify file `< 500` lines and zero template TS casts**

---

### Task 6: Port Live Variance & Anomaly Analytics Tab + Modular `App.vue` (`frontend-public`)

**Files:**
- Create: `erpnextkta/public/stock-reco-dashboard/components/RecoAnalyticsTab.vue` (`< 480` lines)
- Create: `erpnextkta/public/stock-reco-dashboard/components/RecoItemDrawer.vue` (`< 350` lines)
- Modify: `erpnextkta/public/stock-reco-dashboard/App.vue` (`< 400` lines)

- [x] **Step 1: Implement `RecoAnalyticsTab.vue` & `RecoItemDrawer.vue` (`frontend-public`)**
  Migrate all KPIs, progress bar, rule-based Anomaly rules (`CONTRADICTION`, `CONCENTRATION`, `CHURN`, `OSCILLATION`, `DOC_SPIKE`, `DOC_OSCILLATION`), Top Risks, sortable table, CSV export, and drawer breakdown from old `App.vue` — replacing hardcoded English strings with `__(...)` and hardcoded `#fff`/`#111827` colors with Light & `[data-theme="dark"]` Frappe/KTA CSS variables.

- [x] **Step 2: Implement slim 2-tab `App.vue` (`frontend-public`)**
  Manage `activeTab` (`"operations" | "analytics"`), `selectedDocName`, custom window/Frappe event listener for `route_options` updates from `stock_reco_dashboard.js`, Socket.IO `stock_reco_dashboard_update` listener (refreshing active document/list or analytics), and modal/error state.

- [x] **Step 3: Check line counts (`wc -l`) on all `.vue` files in `stock-reco-dashboard/`**
  Expected: Every single file `< 500` lines.

---

### Task 7: Desk Form Shortcut & Page Route Options Sync (`kta-stock` & `frontend-public`)

**Files:**
- Modify: `erpnextkta/kta_stock/page/stock_reco_dashboard/stock_reco_dashboard.js`
- Modify: `erpnextkta/public/js/stock_reconciliation.js`

- [x] **Step 1: Update `stock_reco_dashboard.js` (`kta-stock`)**
  In both `load_vue(wrapper)` (initial) and `on_page_show(wrapper)` (re-navigation), read and clear `frappe.route_options` (`doc`, `tab`) and pass/dispatch them (`window.dispatchEvent(new CustomEvent("kta-stock-reco-route", { detail }))`) so clicking the button from a Stock Reconciliation form always opens Tab 1 pre-loaded on that exact document.

- [x] **Step 2: Update `erpnextkta/public/js/stock_reconciliation.js` (`frontend-public`)**
  Preserve `get_items` (`get_items_static`) intact; add **`Sayım ve Etiket Merkezinde Aç`** custom button inside `refresh(frm)` routing via `frappe.route_options = { doc: frm.doc.name, tab: "operations" }; frappe.set_route("stock-reco-dashboard");`.

- [x] **Step 3: Run Full Faz 2 Verification Gate (Coordinator)**
  - `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bash -lc 'export PATH="/home/frappe/.nvm/versions/node/v22.23.4/bin:$PATH" && bench build --app erpnextkta --production'`
  - `ruff check` & `ruff format --check` on modified Python files
  - `run-tests` on `test_stock_reconciliation_relabeling` + Faz 1 `kta_stock` suite + check `< 500` lines per Vue file.
  Expected: All PASS.

- [x] **Step 4: Commit Faz 2 (When approved)**
  ```bash
  git add erpnextkta/ docs/superpowers/specs/2026-11-21-faz2-stock-reco-hub-vue-ts-design.md docs/superpowers/plans/2026-11-21-faz2-stock-reco-hub-vue-ts.md
  git commit -m "feat(stock-reco): add vue3 relabeling and analytics hub"
  ```
