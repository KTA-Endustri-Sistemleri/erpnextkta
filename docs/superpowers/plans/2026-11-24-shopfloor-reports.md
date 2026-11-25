# Shopfloor Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an extensible `Raporlar` (`reports`) view tab and left-drawer report catalog to Shopfloor Hub, starting with `İş Emri Operasyon Tamamlanma Özeti` (`operation_completion`).

**Architecture:** Declarative frontend report registry (`registry.ts`) paired with a dedicated backend service module (`report_service.py`) exposing `get_operation_completion_report` via `api.py` using at most 4 bounded SQL queries. Submitted confirmations for an expanded `(work_order, operation)` row are loaded lazily on demand via the existing `get_production_confirmations` endpoint.

**Tech Stack:** Frappe v15 / Python 3.11+ (`frappe.qb` / `frappe.db.sql`), Vue 3 (`<script setup lang="ts">`), TypeScript, Frappe CSS design tokens (Light + `[data-theme="dark"]`), `ruff`, `bench build --production`.

**Spec:** [2026-11-24-shopfloor-reports-design.md](../specs/2026-11-24-shopfloor-reports-design.md)

## Global Constraints

- Work strictly on branch `feat/shopfloor-work-order-print` in `/home/frappe/frappe-bench/apps/erpnextkta` (do NOT create a new branch; do NOT push to remote).
- Respect domain subagent ownership in `.agents/AGENTS.md`:
  - `kta-shopfloor` edits `erpnextkta/kta_shopfloor/**`.
  - `frontend-public` edits `erpnextkta/public/**`.
  - `docs-i18n` edits `erpnextkta/www/docs/**`, `docs/kta_shopfloor_hub_kilavuzu.md`, `erpnextkta/translations/**`.
  - NEVER modify `/home/frappe/frappe-bench/apps/erpnext/**` or `Manufacturing Settings` (`material_consumption = 1`, `get_rm_cost_from_consumption_entry = 1`).
- Every `.vue` file MUST remain `<= 500` lines.
- No hardcoded real company, customer, vendor, item, or warehouse names or real unit prices in code, tests, docs, or commits.
- Only the Coordinator runs `bench build --app erpnextkta --production`, `bench restart`, and `git commit`.

## Review Focus

1. **Active-Only Work Order Scope:** Draft (`docstatus != 1`), `Completed`, `Closed`, `Cancelled`, and `Stopped` Work Orders never appear; only submitted WOs with `status IN ('Not Started', 'In Process')` and `completed_qty > 0` appear.
2. **Pre- vs Post-Filter KPI & Count Semantics:** `counts` (`completed`, `partial`, `all`) and `summary.completed_operations` / `summary.partial_operations` reflect pre-`status_filter` totals; `summary.unique_work_orders` and `summary.total_confirmed_qty` reflect the filtered `rows`.
3. **Bounded Queries (Zero N+1):** `get_operation_completion_report` executes at most 4 SQL queries regardless of row count (main active WO/Op query, CO11N aggregate query, filter options query, optional stock entry count/join).
4. **SFC Size & Theme Compliance:** Extracting alert banners into `ShopfloorAlerts.vue` keeps `App.vue <= 500` lines; every new `.vue` file is `<= 500` lines and supports Light + `[data-theme="dark"]` via CSS variables.
5. **Localization & Docs Parity:** All UI `__("...")` and backend `_("...")` strings exist in `tr.csv`, `en.csv`, `de.csv`, and both `shopfloor-hub.html` and `docs/kta_shopfloor_hub_kilavuzu.md` document the `Raporlar` tab and `İş Emri Operasyon Tamamlanma Özeti`.

---

### Task 1: Backend Report Service, Whitelisted API & Tests (`kta-shopfloor`)

**Files:**
- Create: `erpnextkta/kta_shopfloor/services/report_service.py`
- Modify: `erpnextkta/kta_shopfloor/services/__init__.py`
- Modify: `erpnextkta/kta_shopfloor/api.py`
- Create: `erpnextkta/kta_shopfloor/tests/test_report_service.py`
- Modify: `erpnextkta/kta_shopfloor/tests/test_api.py`

- [ ] **Step 1:** Create `erpnextkta/kta_shopfloor/services/report_service.py` implementing `get_operation_completion_report`:
  - Resolve `company` via the same default/filter pattern as `get_active_work_orders` in `api.py`.
  - Validate `status_filter` (`"completed"`, `"partial"`, `"all"`; raise `frappe.ValidationError(_(...))` on invalid value).
  - Query submitted active Work Order Operations (`wo.docstatus = 1`, `wo.status IN ('Not Started', 'In Process')`, `op.completed_qty > 0`), applying `company`, `operation`, `workstation`, and `search` (`work_order`, `production_item`, `item_name`, `operation`, `workstation`) filters.
  - Query aggregated submitted `KTA Production Confirmation` rows (`docstatus = 1`) grouped by `(work_order, operation)` for matched WO names (plus linked `Stock Entry` count if needed) to compute `confirmed_qty`, `confirmation_count`, `final_confirmation_count`, `last_confirmation_at`, and `last_confirmed_by`.
  - Filter by `from_date` / `to_date` against `posting_date` / `last_confirmation_at` when provided.
  - Classify each row with `is_completed = (completed_qty >= qty)` and `completion_pct = round(min(100.0, (completed_qty / qty) * 100.0), 1)` (guarding `qty <= 0`).
  - Compute `counts` (`completed`, `partial`, `all`) and pre-filter `summary.completed_operations` / `summary.partial_operations` BEFORE applying `status_filter`, then apply `status_filter` (`"completed"` -> `is_completed`, `"partial"` -> `not is_completed`, `"all"` -> all) and compute `summary.unique_work_orders` and `summary.total_confirmed_qty`.
  - Populate `filter_options` (`operations`, `workstations`) sorted alphabetically from active WOs with `completed_qty > 0` for the company.
- [ ] **Step 2:** Re-export `get_operation_completion_report` in `erpnextkta/kta_shopfloor/services/__init__.py` and expose `@frappe.whitelist() def get_operation_completion_report(...)` in `erpnextkta/kta_shopfloor/api.py`.
- [ ] **Step 3:** Add tests in `erpnextkta/kta_shopfloor/tests/test_report_service.py` and `erpnextkta/kta_shopfloor/tests/test_api.py` verifying:
  - `Completed`, `Closed`, `Cancelled`, `Stopped`, and `Draft` WOs are excluded; active `Not Started` / `In Process` WOs with `completed_qty > 0` are included.
  - `status_filter` (`completed`, `partial`, `all`) + invalid value error + pre-filter `counts` vs post-filter `summary` (`unique_work_orders`, `total_confirmed_qty`).
  - Filters (`operation`, `workstation`, `from_date`, `to_date`, `search`, `company`) and `filter_options`.
  - Cancelled CO11N confirmations (`docstatus = 2`) and drafts (`docstatus = 0`) are excluded from aggregates, while operations completed without CO11N still render (`confirmation_count = 0`).
  - Query count bound (`<= 6` queries inside `frappe.assert_query_count` / `capture_queries` even with multiple WO/operation rows).
- [ ] **Step 4:** Run `ruff format --check` and `ruff check` on modified Python files and run `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_report_service`.

---

### Task 2: Frontend Reports Registry, Sidebar, Workspace & Export (`frontend-public`)

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/types.ts`
- Modify: `erpnextkta/public/shopfloor-hub/components/ShopfloorNavbar.vue`
- Create: `erpnextkta/public/shopfloor-hub/components/ShopfloorAlerts.vue`
- Create: `erpnextkta/public/shopfloor-hub/reports/csvExport.ts`
- Create: `erpnextkta/public/shopfloor-hub/components/reports/OperationCompletionDetail.vue`
- Create: `erpnextkta/public/shopfloor-hub/components/reports/OperationCompletionReport.vue`
- Create: `erpnextkta/public/shopfloor-hub/reports/registry.ts`
- Create: `erpnextkta/public/shopfloor-hub/components/ReportsSidebar.vue`
- Create: `erpnextkta/public/shopfloor-hub/components/ReportsWorkspace.vue`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue`

- [ ] **Step 1:** Update `types.ts` (`WorkOrderViewMode` includes `'reports'`, plus `ReportCategory`, `ReportDefinition`, `OperationCompletionRow`, `OperationCompletionResponse`, `OperationCompletionStatusFilter`) and add `{ id: 'reports', icon: '📊', label: 'Reports' }` to `ShopfloorNavbar.vue`.
- [ ] **Step 2:** Create `ShopfloorAlerts.vue` to extract `.co11n-alert` error/success banners out of `App.vue` so `App.vue` stays safely `<= 500` lines.
- [ ] **Step 3:** Create `reports/csvExport.ts` (UTF-8 BOM + CSV formula-injection neutralization for leading `=`, `+`, `-`, `@`, `\t`, `\r` + formatted download) and `components/reports/OperationCompletionDetail.vue` (lazy fetch via `get_production_confirmations`, filter by `operation`, show submitted confirmations, `yield_qty`, `posting_date` / `posting_time`, `confirmed_by`, `is_final_confirmation`, linked Stock Entry pill links).
- [ ] **Step 4:** Create `components/reports/OperationCompletionReport.vue`:
  - Header + `Yenile` + `CSV İndir` buttons.
  - Status pill bar (`Tamamlananlar`, `Kısmi Üretimler`, `Tümü`) using `response.counts` and pre-filter/post-filter KPI summary strip.
  - Filter bar (`search`, `operation`, `workstation`, `from_date`, `to_date`, `Filtreleri Temizle`).
  - Expandable data table (`İş Emri`, `Ürün`, `Operasyon`, `İş İstasyonu`, `Planlanan`, `Tamamlanan`, `Onaylı (CO11N)`, `İlerleme %`, `Son Onay`, `İşlem`) with `"İş Emrine Git"` cross-navigation (`select-work-order`) and inline `OperationCompletionDetail`.
- [ ] **Step 5:** Create `reports/registry.ts`, `ReportsSidebar.vue` (drawer header, search filter, category grouping, active badge), and `ReportsWorkspace.vue` (`defineAsyncComponent` / dynamic component switcher by `activeReportId`), then wire `activeView === 'reports'` in `App.vue` (`handleViewChange` skips `sidebarRef` fetch in `reports` mode; `"İş Emrine Git"` switches back to `work_orders` and loads that WO + operation).
- [ ] **Step 6:** Verify `wc -l` for every `.vue` file is `<= 500` and list all new `__("...")` translation keys.

---

### Task 3: Documentation & Translation Sync (`docs-i18n`)

**Files:**
- Modify: `erpnextkta/www/docs/shopfloor-hub.html`
- Modify: `docs/kta_shopfloor_hub_kilavuzu.md`
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`

- [ ] **Step 1:** Document the new `Raporlar` navbar tab, extensible left drawer catalog, `İş Emri Operasyon Tamamlanma Özeti` filters, active-WO scope (excluding `Completed` WOs), CO11N detail drawer, and CSV export in both `erpnextkta/www/docs/shopfloor-hub.html` and `docs/kta_shopfloor_hub_kilavuzu.md` (with zero commercial data).
- [ ] **Step 2:** Add all new `__("...")` and backend `_("...")` keys cleanly to `tr.csv`, `en.csv`, and `de.csv` without duplicates and validate CSV column integrity and Jinja2/HTML tags.

---

### Task 4: Verification, Production Asset Build, Commit & Service Restart (Coordinator)

- [ ] **Step 1:** Run `/home/frappe/frappe-bench/env/bin/ruff check` and `ruff format --check` on `report_service.py`, `api.py`, `test_report_service.py`, `test_api.py`.
- [ ] **Step 2:** Verify `wc -l` (`<= 500`) across all Shopfloor Hub `.vue` files and build production assets via `bench build --app erpnextkta --production`.
- [ ] **Step 3:** Run `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module ...` serially for `test_report_service`, `test_api`, and `test_confirmation_service`.
- [ ] **Step 4:** Execute a read-only `bench --site old.kta-endustri.com.tr execute` check calling `get_operation_completion_report` and verify zero `Completed` WOs, accurate counts/summary math, and `Manufacturing Settings` (`material_consumption = 1`, `get_rm_cost_from_consumption_entry = 1`).
- [ ] **Step 5:** Commit changes cleanly on `feat/shopfloor-work-order-print` (Conventional Commits `<= 100` chars/line, do NOT push), run `bench restart && bench --site old.kta-endustri.com.tr clear-cache`, and verify `supervisorctl status`.
