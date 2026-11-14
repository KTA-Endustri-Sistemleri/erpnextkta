# MRP Analysis Reservations, Price Standardization & Zero-Consumption Leak Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add factory-wide reservation and net free stock columns to MRP Analysis, standardize price resolution to default supplier, fix finished goods and maintenance items leaking into the raw material report when zero-consumption is enabled using `get_zero_consumption_items`, complete the bottom total row, and update the balance value column header to TRY.

**Architecture:** Update backend SQL queries in `mrp_analysis.py` to aggregate warehouse-level reservation quantities from `tabBin` on `Kullanılabilir Stok` warehouses, strictly fetch `default_supplier` prices from `tabItem Price`, filter `sifir_tuketimi_goster` via `get_zero_consumption_items` on `custom_ara_malzeme_grubu = 'HAMMADDE' OR LIKE 'OBS%%'`, and clean up `mrp_analysis.js` UI filter definition.

**Tech Stack:** Python 3.11, MariaDB, Frappe Framework v15, ERPNext, JavaScript.

**Spec:** `docs/superpowers/specs/2026-11-15-mrp-analysis-reservations-design.md`

## Global Constraints
- Target branch is `main` (feature branch `feat/mrp-analysis-factory-reservations`).
- Conventional Commits enforced via `commitlint.config.js` (`feat(mrp): ...`, `fix(mrp): ...`, `docs(mrp): ...`).
- Python code formatted and linted with `ruff`.
- JavaScript formatted with `Prettier` and linted with `ESLint`.
- UI labels and strings wrapped in Frappe translation helpers `_("...")` and `__("...")`.
- When building frontend assets, NEVER use `yarn build` directly; use `bench build --app erpnextkta --production`.
- Do NOT modify or remove the summary cards (`report_summary`) at the bottom of the report.
- Maintain standard float formatting for `serbest_stok` and `rezerve_stok` (no colored pills or red highlights).
- Use `erpnextkta/tests/test_mrp_analysis.py` for automated tests to prevent Add/Add conflicts when rebasing `feat/mrp-modular-refactor`.

## Review Focus
1. **Zero-Consumption Item Leak:** When `sifir_tuketimi_goster=1`, non-raw materials (`BAKIM`, `AMBALAJ`, `ÜRÜN`, `YARIMAMUL`) must NOT appear; only `HAMMADDE` and obsolete raw materials (`OBS*`) should appear.
2. **Reservation Aggregation:** `rezerve_stok` must correctly aggregate all 3 reservation buckets (`reserved_qty_for_production`, `reserved_qty`, `reserved_qty_for_sub_contract`) across all `Kullanılabilir Stok` warehouses.
3. **Net Available Math:** `serbest_stok` must equal `round(depo_stok - rezerve_stok, 2)` (can be negative if reservations exceed stock).
4. **Bottom Total Row Completeness:** `depo_stok`, `rezerve_stok`, `serbest_stok`, and `bakiye_degeri` must have valid numeric sums in the bottom `TOPLAM` row, not `None`.
5. **Default Supplier Price Stability:** Price must strictly reflect the item's `default_supplier` latest buying price; removing the checkbox filter must not break existing callers.

---

### Task 1: Automated Unit Tests (`erpnextkta/tests/test_mrp_analysis.py`)

**Files:**
- Create: `erpnextkta/tests/test_mrp_analysis.py`

- [x] **Step 1.1: Write automated test cases for MRP Analysis**
  Create `erpnextkta/tests/test_mrp_analysis.py` with tests covering:
  - Presence of `rezerve_stok`, `serbest_stok` columns and updated `Bakiye Değeri (TL)` label.
  - Verification that for each data row `serbest_stok == round(depo_stok - rezerve_stok, 2)`.
  - Verification that the `TOPLAM` row contains numeric totals for `depo_stok`, `rezerve_stok`, `serbest_stok`, and `bakiye_degeri`.
  - Verification that `get_zero_consumption_items()` returns only items where `custom_ara_malzeme_grubu` is `'HAMMADDE'` or starts with `'OBS'`, and zero items with `'BAKIM'`, `'AMBALAJ'` or `'ÜRÜN'`.
  - Verification that item `10023999` returns the default supplier and positive purchase price.

- [x] **Step 1.2: Run test to confirm expected failure prior to implementation**
  Command: `docker exec -w /home/frappe/frappe-bench/sites --user frappe erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_mrp_analysis`
  Verify that tests fail on missing columns `rezerve_stok` / `serbest_stok` or `get_zero_consumption_items`.

- [x] **Step 1.3: Commit initial test suite**
  Commit: `test(mrp): add automated test suite for mrp analysis reservations and filters`

---

### Task 2: Backend Implementation in `mrp_analysis.py`

**Files:**
- Modify: `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.py`

- [x] **Step 2.1: Add `get_zero_consumption_items` and Update Zero-Consumption Loop**
  - Implement `get_zero_consumption_items()` at bottom of `mrp_analysis.py` querying `tabBin` + `tabWarehouse` + `tabItem` filtering on `wh.warehouse_type = 'Kullanılabilir Stok'`, `bin.actual_qty > 0`, `item.disabled = 0`, and `(item.custom_ara_malzeme_grubu = 'HAMMADDE' OR item.custom_ara_malzeme_grubu LIKE 'OBS%%')`.
  - Update lines 60-76 in `mrp_analysis.py` to loop over `for item_code in get_zero_consumption_items():`.

- [x] **Step 2.2: Standardize Default Supplier Price Resolution**
  - Remove `fiyat_varsayilan_tedarikci = cint(...)` filter handling (line 19).
  - Replace lines 102-142 with a single, clean SQL query that fetches the latest buying price for each raw material and matches `def_sup == p.supplier`.
  - Eliminate the obsolete non-default supplier `else` block.

- [x] **Step 2.3: Aggregate Reservations in `stock_data` Query**
  Update lines 143-158 in `mrp_analysis.py`:
  - Compute `SUM(COALESCE(bin.reserved_qty_for_production, 0) + COALESCE(bin.reserved_qty, 0) + COALESCE(bin.reserved_qty_for_sub_contract, 0)) as total_reserved`.
  - Populate `reserved_map[d.item_code] = d.total_reserved or 0`.

- [x] **Step 2.4: Update Column Definitions and Row Generation**
  Update `columns` list:
  - Add `rezerve_stok` (Float, width 110) and `serbest_stok` (Float, width 110) immediately following `depo_stok`.
  - Rename label `"Bakiye Değeri"` to `"Bakiye Değeri (TL)"` with width 130.
  Update row creation:
  - Set `rezerve_stok = reserved_map.get(hammadde, 0)`.
  - Set `serbest_stok = round(depo_stok - rezerve_stok, 2)`.
  - Accumulate `depo_stok`, `rezerve_stok`, `serbest_stok`, and `bakiye_degeri` into `column_totals`.

- [x] **Step 2.5: Populate `TOPLAM` Row**
  In `total_row` dictionary:
  - Add `total_row["depo_stok"] = round(column_totals["depo_stok"], 2)`.
  - Add `total_row["rezerve_stok"] = round(column_totals["rezerve_stok"], 2)`.
  - Add `total_row["serbest_stok"] = round(column_totals["serbest_stok"], 2)`.
  - Add `total_row["bakiye_degeri"] = round(column_totals["bakiye_degeri"], 2)`.

- [x] **Step 2.6: Run tests to verify backend passes**
  Command: `docker exec -w /home/frappe/frappe-bench/sites --user frappe erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_mrp_analysis`
  Confirm all tests pass.

- [x] **Step 2.7: Commit backend changes**
  Commit: `feat(mrp): add reservation columns, default supplier pricing and total row in mrp analysis`

---

### Task 3: Frontend Cleanup in `mrp_analysis.js`

**Files:**
- Modify: `erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.js`

- [x] **Step 3.1: Remove `fiyat_varsayilan_tedarikci` filter definition**
  In `mrp_analysis.js`, delete the `fiyat_varsayilan_tedarikci` filter entry.

- [x] **Step 3.2: Build frontend assets**
  Run: `docker exec -w /home/frappe/frappe-bench --user frappe erpnext-dev-frappe-1 bench build --app erpnextkta --production`
  Ensure build succeeds without errors.

- [x] **Step 3.3: Commit frontend changes**
  Commit: `fix(mrp): remove redundant default supplier price checkbox filter from mrp analysis`

---

### Task 4: Full Verification & Code Quality

- [x] **Step 4.1: Run code linter and formatting**
  Run `ruff check erpnextkta/kta_mrp/report/mrp_analysis/mrp_analysis.py` and format if needed.

- [x] **Step 4.2: Live Report Verification in Bench Console**
  Run an end-to-end verification script testing:
  - Report execution with default filters.
  - Report execution with `sifir_tuketimi_goster: 1`.
  - Verification of `10023999` row: `depo_stok`, `rezerve_stok`, `serbest_stok`, `fiyat`, `para_birimi`.
  - Verification of `TOPLAM` row values.

- [x] **Step 4.3: Final conventional commit and clean status check**
  Run `git status` and `git log -n 4` to verify git state is clean and atomic.

---

### Task 5: Fix Period Calculation for Rolling Year
- [x] **Step 5.1: Update `get_period_dates` in `report_utils.py`**
  Change "Yıllık" period from fixed calendar year end (`date(year, 12, 31)`) to rolling 12 months (`add_months(current_date, 12)`) so late-year queries cover upcoming year's orders.
- [x] **Step 5.2: Add unit test in `test_mrp_analysis.py`**
  Add `test_period_dates_rolling_year` verifying rolling 12-month window.
