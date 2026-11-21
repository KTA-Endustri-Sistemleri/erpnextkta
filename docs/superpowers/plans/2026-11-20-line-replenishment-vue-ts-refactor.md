# Line Replenishment Vue 3 + TypeScript Refactor (Desktop Hub & PDA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the legacy vanilla JS Desktop Hub (`line-replenishment-hub`) and PDA Picking (`line-replenishment-picking`) pages into modern Vue 3 + TypeScript SPAs under `erpnextkta/public/`, harmonized with Shopfloor Hub layout, responsive tables with "Depodan Çıkacak Miktar", conditional order creation action below the table, and mobile touch ergonomics.

**Architecture:** Two independent Vue 3 + TypeScript bundles (`line-replenishment-hub.bundle.js` and `line-replenishment-pda.bundle.js`) compiled via Frappe's Vite/esbuild pipeline under `erpnextkta/public/`. Thin Desk page loaders mount the SPAs into `.layout-main-section` while hiding the legacy page-head.

**Tech Stack:** Vue 3 (Composition API, `<script setup>`), TypeScript, Tailwind CSS, Frappe UI API (`frappe.call`, `frappe.show_alert`, `frappe.msgprint`), Python unit tests.

**Spec:** `docs/superpowers/specs/2026-11-20-line-replenishment-vue-ts-refactor-design.md`

## Global Constraints

- No modifications to core reservation algorithms in `line_replenishment_service.py` or DocType schemas.
- Line length limit: <= 100 characters in git commit messages and PR descriptions.
- Zero commercial data in code, tests, or documentation.
- Title Case for all UI buttons, titles, and table headers.
- All strings must be wrapped in `__("...")` and synced to `translations/{tr,en,de}.csv`.
- Production build command: `bench build --app erpnextkta --production`.

## Review Focus

1. Zero-stock items and in-flight draft replenishment items must have their checkboxes disabled in `DeficitTable.vue` so they cannot be submitted.
2. "Depodan Çıkacak Miktar" (`available_stock`) must be displayed clearly and must not be confused with `deficit_qty`.
3. "Hat İkmal Emri Oluştur" button must remain hidden when no actionable deficits exist.
4. PDA Picking scanner input must remain auto-focused and support both keyboard barcode scanners and manual text input.
5. All legacy `.css` and vanilla jQuery code in `page/` must be safely removed without breaking Desk route registration.

---

### Task 1: Build Pipeline Scaffolding & TypeScript Configuration

**Files:**
- Create: `erpnextkta/public/line-replenishment-hub/tsconfig.json`
- Create: `erpnextkta/public/line-replenishment-hub/frappe.d.ts`
- Create: `erpnextkta/public/line-replenishment-hub/line-replenishment-hub.bundle.js`
- Create: `erpnextkta/public/line-replenishment-pda/tsconfig.json`
- Create: `erpnextkta/public/line-replenishment-pda/frappe.d.ts`
- Create: `erpnextkta/public/line-replenishment-pda/line-replenishment-pda.bundle.js`
- Modify: `erpnextkta/public/build.json` (or hooks bundle registration if needed)

**Interfaces:**
- Produces: `window.frappe.ui.setup_line_replenishment_hub_vue($parent)`
- Produces: `window.frappe.ui.setup_line_replenishment_pda_vue($parent)`

- [ ] **Step 1: Create TypeScript and bundle entry files for Desktop Hub**
  Create `erpnextkta/public/line-replenishment-hub/tsconfig.json`, `frappe.d.ts`, and `line-replenishment-hub.bundle.js` with `createApp` mounting hook.
- [ ] **Step 2: Create TypeScript and bundle entry files for PDA Picking**
  Create `erpnextkta/public/line-replenishment-pda/tsconfig.json`, `frappe.d.ts`, and `line-replenishment-pda.bundle.js` with `createApp` mounting hook.
- [ ] **Step 3: Test compilation with bench build**
  Run: `bench build --app erpnextkta --production`
  Expected: SUCCESS (bundle files generated in `erpnextkta/public/dist/js/`)
- [ ] **Step 4: Commit**
  ```bash
  git add erpnextkta/public/line-replenishment-hub erpnextkta/public/line-replenishment-pda
  git commit -m "build(frontend): scaffold line replenishment hub and pda vue3 bundles"
  ```

---

### Task 2: Desktop Hub Vue 3 + TypeScript Components (`line-replenishment-hub`)

**Files:**
- Create: `erpnextkta/public/line-replenishment-hub/types.ts`
- Create: `erpnextkta/public/line-replenishment-hub/App.vue`
- Create: `erpnextkta/public/line-replenishment-hub/components/WorkspaceHeader.vue`
- Create: `erpnextkta/public/line-replenishment-hub/components/DeficitTable.vue`
- Create: `erpnextkta/public/line-replenishment-hub/components/ActionBar.vue`

**Interfaces:**
- Consumes: `erpnextkta.kta_shopfloor.page.line_replenishment_hub.line_replenishment_hub.get_warehouse_reservation_deficits`
- Consumes: `erpnextkta.kta_stock.line_replenishment_service.create_line_replenishment_order`
- Produces: Interactive Desktop Hub with quick line pills (1501-1509), responsive deficits grid, and bottom action bar.

- [ ] **Step 1: Define TypeScript models in `types.ts`**
  Add `DeficitItem`, `AllocatedBatch`, `SourcingStrategy`, and `FilterState` interfaces.
- [ ] **Step 2: Implement `WorkspaceHeader.vue`**
  Build top toolbar with quick line selector pills (`1501 KESMELER`, `1502 JK`, `1503 RATIONAL`, `1504 ARCELIK`, `1509 BOSCH`), custom warehouse link, and strategy selector (`Smart Sourcing (WIP First)` vs `Direct Central Store`).
- [ ] **Step 3: Implement `DeficitTable.vue`**
  Render responsive table with columns: Checkbox, `Hammadde Kodu & Adı`, `Net Açık (Deficit)`, `Hat Stoğu`, **`Depodan Çıkacak Miktar` (`available_stock`)**, `Kaynak Depo / Raf`, `Kaynak Tipi`, and `Durum Rozeti`. Zero-stock and in-flight draft rows disabled.
- [ ] **Step 4: Implement `ActionBar.vue`**
  Render bottom bar directly below `DeficitTable.vue`. Render ONLY when `items.length > 0`. On click, call `create_line_replenishment_order`, display success dialog with order link, and refresh list in-place.
- [ ] **Step 5: Assemble and verify production build**
  Run: `bench build --app erpnextkta --production`
  Expected: PASS
- [ ] **Step 6: Commit**
  ```bash
  git add erpnextkta/public/line-replenishment-hub
  git commit -m "feat(shopfloor): implement line replenishment hub vue3 typescript spa"
  ```

---

### Task 3: Mobile PDA Picking Vue 3 + TypeScript Components (`line-replenishment-pda`)

**Files:**
- Create: `erpnextkta/public/line-replenishment-pda/types.ts`
- Create: `erpnextkta/public/line-replenishment-pda/PdaApp.vue`
- Create: `erpnextkta/public/line-replenishment-pda/components/OrderSelector.vue`
- Create: `erpnextkta/public/line-replenishment-pda/components/BarcodeScannerBar.vue`
- Create: `erpnextkta/public/line-replenishment-pda/components/PickingItemCard.vue`
- Create: `erpnextkta/public/line-replenishment-pda/components/TransferFooter.vue`
- Create: `erpnextkta/public/line-replenishment-pda/utils/audio.ts`

**Interfaces:**
- Consumes: `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_open_replenishment_orders`
- Consumes: `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_replenishment_order_details`
- Consumes: `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.complete_line_replenishment_picking`

- [ ] **Step 1: Define TypeScript models and audio feedback utility**
  Create `types.ts` with `ReplenishmentOrder`, `PickingItem`. Implement `audio.ts` (`playBeep(success: boolean)`).
- [ ] **Step 2: Implement `OrderSelector.vue` & `BarcodeScannerBar.vue`**
  Touch-friendly order selection dropdown/card and auto-focused scanner input supporting barcode scan events and `KTA Stock Label` decoding.
- [ ] **Step 3: Implement `PickingItemCard.vue`**
  Touch card with high-contrast **Shelf Location Badge** (e.g. `W1A-01-01`), progress bar, `+1`, `-1`, and `Tümünü Al` actions, enforcing 15% tolerance.
- [ ] **Step 4: Implement `TransferFooter.vue`**
  Sticky bottom action bar with `Transferi Tamamla` button, enabled when all items are picked.
- [ ] **Step 5: Assemble `PdaApp.vue` and verify production build**
  Run: `bench build --app erpnextkta --production`
  Expected: PASS
- [ ] **Step 6: Commit**
  ```bash
  git add erpnextkta/public/line-replenishment-pda
  git commit -m "feat(stock): implement line replenishment pda picking vue3 spa"
  ```

---

### Task 4: Frappe Desk Page Loaders & Legacy Cleanup

**Files:**
- Modify: `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.js`
- Delete: `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.css`
- Modify: `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.js`
- Delete: `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.css`

- [ ] **Step 1: Update `line_replenishment_hub.js`**
  Remove legacy jQuery rendering. Hide `.page-head`, set fullwidth styling, load `line-replenishment-hub.bundle.js`, and mount via `frappe.ui.setup_line_replenishment_hub_vue`. Remove `line_replenishment_hub.css`.
- [ ] **Step 2: Update `line_replenishment_picking.js`**
  Remove legacy vanilla `LineReplenishmentPicking` class. Hide `.page-head`, load `line-replenishment-pda.bundle.js`, and mount via `frappe.ui.setup_line_replenishment_pda_vue`. Remove `line_replenishment_picking.css`.
- [ ] **Step 3: Commit**
  ```bash
  git add erpnextkta/kta_shopfloor/page erpnextkta/kta_stock/page
  git commit -m "refactor(desk): mount line replenishment vue bundles and remove legacy files"
  ```

---

### Task 5: Multilingual i18n Synchronization

**Files:**
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`

- [ ] **Step 1: Check and add missing translation keys**
  Ensure all keys (`Depodan Çıkacak Miktar`, `Hat İkmal Emri Oluştur`, `Kaynak Depo / Raf`, `Aktif İkmal Siparişi`, `Transferi Tamamla`, `Tümünü Al`, `Taslak İkmalde`, etc.) are defined with consistent Title Case across TR, EN, and DE.
- [ ] **Step 2: Commit**
  ```bash
  git add erpnextkta/translations/
  git commit -m "docs(i18n): sync line replenishment translations for tr en and de"
  ```

---

### Task 6: Page Tests & Final Quality Verification

**Files:**
- Modify: `erpnextkta/kta_shopfloor/tests/test_line_replenishment_hub_page.py`
- Modify: `erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py`

- [ ] **Step 1: Update page test suites**
  Update `test_line_replenishment_hub_page.py` and `test_line_replenishment_picking_page.py` to assert bundle registration (`line-replenishment-hub.bundle.js` and `line-replenishment-pda.bundle.js`), page registration, and container mount points.
- [ ] **Step 2: Run all stock and shopfloor unit tests**
  Run: `bench --site kta.local run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_line_replenishment_hub_page`
  Run: `bench --site kta.local run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page`
  Run: `bench --site kta.local run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_service`
  Expected: ALL PASSED
- [ ] **Step 3: Run production frontend build and linting**
  Run: `bench build --app erpnextkta --production`
  Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/`
  Expected: ALL PASSED with 0 errors.
- [ ] **Step 4: Commit**
  ```bash
  git add erpnextkta/kta_shopfloor/tests erpnextkta/kta_stock/tests
  git commit -m "test(page): update line replenishment page tests for vue3 bundles"
  ```
