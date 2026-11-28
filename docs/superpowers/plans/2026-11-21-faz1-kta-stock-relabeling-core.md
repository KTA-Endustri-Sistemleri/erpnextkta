# Faz 1 Implementation Plan: `kta_stock` Core Relabeling Engine & `rest-api` Migration

> **For agentic workers:** Coordinator dispatches specialist subagents (`kta-stock`, `overrides-hooks`, `frontend-public` only for temporary RPC path update, `docs-i18n` for temporary/setup translations if needed) strictly respecting `.agents/subagents/*.md` folder locks. Required sub-skill: `superpowers:subagent-driven-development`.

**Goal:** Consolidate legacy `erpnextkta/rest-api/` into `erpnextkta/kta_stock/services/`, set up `Return from Production Supply` & `Package Split` Stock Entry Types, implement the `7-char Lot + 4-char Box` relabeling/split/`LEGACY` conversion service, and fix ERPNext v15 bundle & label lifecycle bugs in `label_manager.py` and `KTAStockEntry.py` while keeping normal Desk transfers/repacks 100% silent.

**Architecture:** All stock reconciliation, lock, dashboard, and relabeling services live cleanly under `erpnextkta/kta_stock/services/`. Standard `Material Transfer` and `Repack` (`is_standard=1`) remain silent (`custom_etiket_basilabilir=0`), while `Return from Production Supply` and `Package Split` drive automatic `Depo Giriş Etiketi` label creation/updates and ZPL batch printing. Every package split uses 1 independent `Package Split` (`Repack`) document per source box to avoid ERPNext multi-FG valuation pooling and preserve PR/QI/FIFO metadata.

**Tech Stack:** Frappe Framework / ERPNext v15 (Python 3.11), MariaDB, `KTAUnitTestCase` / `KTABaseTestCase`, `kta_system_utils.kta_zebra_utils.printer_manager`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-11-21-faz1-kta-stock-relabeling-core-design.md`

---

## Global Constraints

- Top-level Coordinator MUST NOT edit code directly under `erpnextkta/**`; delegate strictly by `.agents/subagents/*.md` `owned_paths`.
- Never call `se.set_stock_entry_type()` on `Return from Production Supply` or `Package Split` docs (Core overwrites `stock_entry_type` with the `is_standard=1` record).
- Strictly **1 `Package Split` (`Repack`) Stock Entry per split source box** (never combine distinct items or multiple split boxes into one `Repack`).
- Standard `Material Transfer`, `Material Transfer for Manufacture`, `Line Replenishment`, and standard `Repack` (`is_standard=1`) MUST remain silent (zero automatic labels).
- Every numeric comparison MUST guard `None` with `flt()` / `cint()`; SQL queries MUST use ORM or parameterized queries.
- Zero real vendor/customer names or unit prices in code, comments, tests, or commits; every commit message line strictly `<= 100` chars (`<= 75` chars target).

## Review Focus

1. **Cancelling `Return from Production Supply` must NOT delete PR labels:** Existing `Purchase Receipt` labels updated by a return keep `reference_doctype == "Purchase Receipt"`; cancelling or trashing the return `Stock Entry` calls `sync_batch_label_to_ledger_balance` to restore the original `qty` instead of deleting the label. *(Pinned to Task 5 & Task 7 tests)*
2. **Never overwrite custom `stock_entry_type` via `set_stock_entry_type()`:** All `Return from Production Supply` and `Package Split` Stock Entries MUST retain their exact `stock_entry_type` after `insert()` / `submit()`. *(Pinned to Task 4 & Task 7 tests)*
3. **1-source-box-per-doc invariant for `Package Split`:** Manual `Package Split` with >1 distinct incoming `item_code` raises `ValidationError` in `KTAStockEntry.validate()`, and programmatic splits create independent docs per source box so ERPNext `validate_repack_entry` never triggers `Set Basic Rate Manually` or pools rates. *(Pinned to Task 4 & Task 7 tests)*
4. **ERPNext v15 `serial_and_batch_bundle` & lot-based source lookup:** When `row.batch_no` is `None` on submitted entries, `label_manager.print_stock_entry_labels` reads inward `Serial and Batch Entry` rows (`is_outward=0`) and matches `source_warehouse` via `(item_code, batch[:-4])` then `item_code` instead of blindly picking the first `s_warehouse` row. *(Pinned to Task 5 tests)*
5. **FIFO age, GKK (`QI`) lock & `SerialandBatchBundle` 7-char naming preservation:** Newly minted `000x` child batches inherit `supplier`, `reference_doctype`, `reference_name`, `manufacturing_date`, and `expiry_date`; `clear_empty_labels()` checks actual net batch ledger balance `<= 0` across SLE+SBE rather than just empty SABE presence. *(Pinned to Task 3, Task 5 & Task 6 tests)*

---

## Subagent Ownership & File Structure

| Task | Subagent | Files Owned / Touched |
|---|---|---|
| Task 1 | `kta-stock` | Create `erpnextkta/kta_stock/services/__init__.py`, `stock_reconciliation_service.py`, `stock_reconciliation_dashboard_service.py`, `stock_reconciliation_lock.py`; Remove `erpnextkta/rest-api/**` |
| Task 1b | `overrides-hooks` | Modify `erpnextkta/hooks.py` (reco hook paths + `after_migrate`) |
| Task 1c | `frontend-public` | Temporary RPC path update in `erpnextkta/public/js/stock_reconciliation.js` & `erpnextkta/public/stock-reco-dashboard/App.vue` until Faz 2 |
| Task 2 | `kta-stock` | Create `erpnextkta/kta_stock/setup.py`; Test in `erpnextkta/kta_stock/tests/test_relabeling_service.py` |
| Task 3 | `kta-stock` | Create `erpnextkta/kta_stock/services/relabeling_service.py`; Test in `erpnextkta/kta_stock/tests/test_relabeling_service.py` |
| Task 4 | `kta-stock` | Extend `erpnextkta/kta_stock/services/relabeling_service.py` (`create_package_split_repack`); Update `stock_reconciliation_lock.py` (guard via `frappe.flags.kta_ignore_reco_lock`) |
| Task 5 | `kta-stock` | Modify `erpnextkta/kta_stock/label_manager.py`, `erpnextkta/kta_stock/batch_manager.py`; Update `erpnextkta/kta_stock/tests/test_label_manager.py` |
| Task 6 | `overrides-hooks` | Modify `erpnextkta/overrides/serial_batch_bundle_doc.py` |
| Task 7 | `overrides-hooks` | Modify `erpnextkta/overrides/KTAStockEntry.py`; Create `erpnextkta/tests/test_stock_entry_labeling.py` |

---

### Task 1: Migrate `erpnextkta/rest-api/` to `erpnextkta/kta_stock/services/` (`kta-stock`, `overrides-hooks`, `frontend-public`)

**Files:**
- Create: `erpnextkta/kta_stock/services/__init__.py`
- Create (move): `erpnextkta/kta_stock/services/stock_reconciliation_service.py` (from `rest-api/stock_reconciliation.py`)
- Create (move): `erpnextkta/kta_stock/services/stock_reconciliation_dashboard_service.py` (from `rest-api/stock_reconciliation_dashboard.py`)
- Create (move): `erpnextkta/kta_stock/services/stock_reconciliation_lock.py` (from `rest-api/stock_reconciliation_lock.py`)
- Delete: `erpnextkta/rest-api/__init__.py`, `stock_reconciliation.py`, `stock_reconciliation_dashboard.py`, `stock_reconciliation_lock.py`
- Modify: `erpnextkta/hooks.py:170-180`, `erpnextkta/public/js/stock_reconciliation.js`, `erpnextkta/public/stock-reco-dashboard/App.vue`
- Test: `erpnextkta/kta_stock/tests/test_relabeling_service.py`

**Interfaces:**
- Produces (identical `@frappe.whitelist()` & hook signatures under new module paths):
  - `erpnextkta.kta_stock.services.stock_reconciliation_service.{get_items_static, create_stock_reco_docs_for_warehouse_group}`
  - `erpnextkta.kta_stock.services.stock_reconciliation_dashboard_service.{get_years, get_dashboard, get_item_details}`
  - `erpnextkta.kta_stock.services.stock_reconciliation_lock.{validate_unique_draft_stock_reco_per_set_warehouse, validate_stock_entry_warehouse_lock}`

- [x] **Step 1: Write failing import & lock regression test (`kta-stock`)**
  In `erpnextkta/kta_stock/tests/test_relabeling_service.py`, import `stock_reconciliation_service`, `stock_reconciliation_dashboard_service`, and `validate_stock_entry_warehouse_lock` from `erpnextkta.kta_stock.services.*` and assert `frappe.get_hooks("doc_events")["Stock Reconciliation"]["validate"]` references `erpnextkta.kta_stock.services.stock_reconciliation_lock`.

- [x] **Step 2: Verify test fails**
  Run: `docker exec -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service`
  Expected: FAIL (`ModuleNotFoundError: No module named 'erpnextkta.kta_stock.services'`).

- [x] **Step 3: Move modules (`kta-stock`) & update worker path**
  Copy the 3 modules into `erpnextkta/kta_stock/services/`, update `frappe.enqueue` method path in `stock_reconciliation_service.py` (`erpnextkta.kta_stock.services.stock_reconciliation_service._job_create_stock_reco_docs_for_warehouse_group`), update `frappe.db.get_value(..., for update?)` nothing custom, delete `erpnextkta/rest-api/**`.

- [x] **Step 4: Update `hooks.py` (`overrides-hooks`) & temporary frontend RPC strings (`frontend-public`)**
  Update `doc_events` paths in `erpnextkta/hooks.py` for `Stock Reconciliation.validate` and `Stock Entry.validate`. Replace `erpnextkta.rest-api.stock_reconciliation*` strings in `erpnextkta/public/js/stock_reconciliation.js` and `erpnextkta/public/stock-reco-dashboard/App.vue` (temporary path sync until Faz 2 replaces `App.vue`).

- [x] **Step 5: Run test + `bench build`**
  Run test module + `grep -rn "rest-api" erpnextkta/` (expect 0 matches in code) + `bench build --app erpnextkta --production`. Expected: PASS.

---

### Task 2: `Stock Entry Type` Setup (`Return from Production Supply` & `Package Split`) (`kta-stock` & `overrides-hooks`)

**Files:**
- Create: `erpnextkta/kta_stock/setup.py`
- Modify: `erpnextkta/hooks.py:94-98` (`after_migrate`)
- Test: `erpnextkta/kta_stock/tests/test_relabeling_service.py`

**Interfaces:**
- Produces: `erpnextkta.kta_stock.setup.setup() -> None` and `setup_stock_entry_types() -> None`

- [x] **Step 1: Write failing test (`kta-stock`)**
  Assert after calling `setup()`, DB has:
  - `"Return from Production Supply"` (`purpose="Material Transfer"`, `custom_etiket_basilabilir=1`, `custom_etiket_sablonu="Depo Giriş Etiketi"`).
  - `"Package Split"` (`purpose="Repack"`, `custom_etiket_basilabilir=1`, `custom_etiket_sablonu="Depo Giriş Etiketi"`).
  - `"Repack"` (`is_standard=1`, `custom_etiket_basilabilir=0`, `custom_etiket_sablonu` empty/None).

- [x] **Step 2: Run test to verify it fails**
  Run test command; Expected: FAIL (`ImportError: cannot import setup`).

- [x] **Step 3: Implement `erpnextkta/kta_stock/setup.py` (`kta-stock`) & hook `after_migrate` (`overrides-hooks`)**
  Implement idempotent `setup_stock_entry_types()` and `setup()`, and add `"erpnextkta.kta_stock.setup.setup"` to `after_migrate` in `erpnextkta/hooks.py`.

- [x] **Step 4: Run `bench --site development.localhost migrate` & test**
  Verify exit code `0` and all setup assertions PASS.

---

### Task 3: Box Batch Standard, Inheritance & Upsert Sync (`relabeling_service.py`) (`kta-stock`)

**Files:**
- Create: `erpnextkta/kta_stock/services/relabeling_service.py`
- Test: `erpnextkta/kta_stock/tests/test_relabeling_service.py`

**Interfaces:**
- Consumes: `BatchSplitManager._get_last_batch_number_for_base`
- Produces:
  - `is_standard_kta_box_batch(batch_no: str | None) -> bool` (`^[A-Z0-9]{7}(?!0000)[0-9]{4}$` — rejects `LEGACY-10040004`, `R202400035-...`, `6640A670000`)
  - `extract_base_lot(batch_no: str | None) -> str | None` (`batch_no[:7]` when standard 11-char KTA box, else `None`)
  - `generate_new_base_lot(item_code: str, reference_doctype: str | None = None, reference_name: str | None = None, manufacturing_date: str | None = None, supplier: str | None = None, expiry_date: str | None = None) -> str`
  - `allocate_next_box_batches(base_lot: str, count: int, item_code: str, source_meta: dict | None = None) -> list[str]`
  - `resolve_batch_label_metadata(item_code: str, batch_no: str | None, fallback_ref: str = "SAYIM") -> dict`
  - `get_batch_ledger_balances(item_code: str, batch_no: str) -> list[dict]`
  - `upsert_box_label(item_code: str, batch_no: str, qty: float, target_warehouse: str | None = None, source_warehouse: str | None = None, reference_doctype: str | None = None, reference_name: str | None = None, posting_date: str | None = None, quality_ref: str | None = None, supplier_delivery_note: str | None = None) -> str`
  - `sync_batch_label_to_ledger_balance(item_code: str, batch_no: str) -> None`

- [x] **Step 1: Write failing unit/integration tests (`kta-stock`)**
  Pin tests for:
  1. `is_standard_kta_box_batch`: `"6640A670001"` -> `True`, `"6640A670000"` -> `False`, `"LEGACY-10040004"` -> `False`.
  2. `allocate_next_box_batches`: given existing `"6640A670001..0002"` with `reference_doctype="Purchase Receipt"`, `reference_name="PREC-TEST"`, `manufacturing_date="2025-01-10"`, next box `"6640A670003"` inherits all 3 fields verbatim.
  3. `generate_new_base_lot`: creates unique 7-char uppercase root `Batch` (`batch_qty=0`) preserving source metadata.
  4. `upsert_box_label`: updates `qty` and `target_warehouse` on existing PR label WITHOUT overwriting `reference_doctype="Purchase Receipt"` or creating a duplicate `sut_barcode` row.
  5. `sync_batch_label_to_ledger_balance`: updates `qty` when balance > 0 and deletes `KTA Stock Label` (and `KTA Print Log` children safely) when net ledger balance `<= 0`.

- [x] **Step 2: Run tests to verify failure**
  Expected: FAIL.

- [x] **Step 3: Implement helpers in `erpnextkta/kta_stock/services/relabeling_service.py` (`kta-stock`)**
  Implement exact batch validation, 7-char prefix generation, metadata resolution (checking label -> sibling lot label -> `Purchase Receipt` & `Quality Inspection`), `upsert_box_label`, and `get_batch_ledger_balances` across SLE (non-bundle legacy rows) + SBE/SABB (v15 bundle rows).

- [x] **Step 4: Run tests to verify pass**
  Expected: PASS.

---

### Task 4: Atomic 1-Source `Package Split` (`Repack`) Service (`kta-stock`)

**Files:**
- Modify: `erpnextkta/kta_stock/services/relabeling_service.py`
- Modify: `erpnextkta/kta_stock/services/stock_reconciliation_lock.py` (support `frappe.flags.kta_allow_reco_lock_bypass` only when Stock Reconciliation Manager system action executes post-reco split)
- Test: `erpnextkta/kta_stock/tests/test_relabeling_service.py`

**Interfaces:**
- Produces: `create_package_split_repack(item_code: str, source_warehouse: str, target_warehouse: str, source_batch: str | None, split_qtys: list[float], remarks: str | None = None, posting_date: str | None = None, ignore_reco_lock: bool = False) -> dict` returning `{"stock_entry": str, "base_lot": str, "created_batches": list[dict]}`

- [x] **Step 1: Write failing integration tests (`kta-stock`)**
  1. Partial split of `"6640A670001"` (`1000` in warehouse -> split `[350]` to another warehouse): creates submitted `Stock Entry` with `stock_entry_type == "Package Split"`, `purpose == "Repack"`, creates `"6640A670002"` with `350` qty, source `"6640A670001"` balance becomes `650`, and source PR label `qty` is synced to `650`.
  2. `LEGACY` split (`"LEGACY-TEST"` `100` qty -> `[60, 40]`): generates new 7-char `base_lot`, mints `{base_lot}0001` (`60`) and `{base_lot}0002` (`40`), preserves exact `basic_rate` across both target rows (`abs(se.value_difference) < 0.01`), leaves `0` on `"LEGACY-TEST"`, and deletes stale `"LEGACY-TEST"` label.
  3. Verify `se.stock_entry_type == "Package Split"` (never reverted to `"Repack"`), and verify `ignore_reco_lock=True` sets/clears `frappe.flags.kta_ignore_reco_lock` inside `try...finally` cleanly.

- [x] **Step 2: Run tests to verify failure**
  Expected: FAIL.

- [x] **Step 3: Implement `create_package_split_repack` & lock flag (`kta-stock`)**
  Validate inputs (`split_qtys > 0`, sum `<=` available batch qty in `source_warehouse`), determine/generate `base_lot`, allocate child batches (`000x`), build 1-source `Stock Entry` (`purpose="Repack"`, `stock_entry_type="Package Split"` — WITHOUT calling `set_stock_entry_type()`), propagate source batch valuation rate cleanly, wrap insert/submit in `frappe.flags.kta_ignore_reco_lock` `try...finally` when `ignore_reco_lock=True`, and sync source batch label via `sync_batch_label_to_ledger_balance`. Update `stock_reconciliation_lock.validate_stock_entry_warehouse_lock()` to honor `bool(getattr(frappe.flags, "kta_ignore_reco_lock", False))`.

- [x] **Step 4: Run tests to verify pass**
  Expected: PASS.

---

### Task 5: Fix `label_manager.py` (v15 Bundles, Source Mapping & `clear_empty_labels`) (`kta-stock`)

**Files:**
- Modify: `erpnextkta/kta_stock/label_manager.py:374-415,495-730`
- Test: `erpnextkta/kta_stock/tests/test_label_manager.py`

**Interfaces:**
- Produces:
  - `enqueue_print_labels_by_names(label_names: list[str], user: str | None = None) -> dict`
  - Updated `print_stock_entry_labels(stock_entry)` handling v15 `serial_and_batch_bundle`, lot/item source matching, no `custom_musteri_paketleme_miktari` virtual split on non-`Manufacture`, and calling `upsert_box_label`.
  - Updated `LabelPrinter.clear_empty_labels()` checking true ledger balance `<= 0`.

- [x] **Step 1: Write failing tests in `test_label_manager.py` (`kta-stock`)**
  1. `test_print_stock_entry_labels_reads_v15_bundle_and_skips_packaging_split`: Submitted `Return from Production Supply` with `row.batch_no=None` and inward `Serial and Batch Bundle` creates/updates 1 `Depo Giriş Etiketi` with exact bundle batch & qty, `source_warehouse = row.s_warehouse` (NOT `None`!), and ignores `custom_musteri_paketleme_miktari`.
  2. `test_print_stock_entry_labels_repack_matches_source_by_item_and_lot`: Multi-row `Package Split` matches incoming row to its own `item_code + base_lot` outgoing row rather than blindly picking `doc.items[0]`.
  3. `test_clear_empty_labels_deletes_zero_balance_batch_even_with_sabe_history`: Batch with net ledger qty `0` (prior inward+outward SABE rows) has its `Depo Giriş Etiketi` deleted; positive-balance batch label is untouched.

- [x] **Step 2: Run `test_label_manager.py` to verify failures**
  Expected: FAIL.

- [x] **Step 3: Refactor `label_manager.py` (`kta-stock`)**
  Implement `_extract_inward_batch_rows`, `_resolve_source_warehouse`, non-Manufacture delegation to `upsert_box_label` + `_print_pr_labels_by_names`, `enqueue_print_labels_by_names`, and accurate `clear_empty_labels()` using `get_batch_ledger_balances`. Preserve all existing `Manufacture` and `Purchase Receipt` behavior (`print_kta_wo_labels*`, `custom_split_kta_batches`).

- [x] **Step 4: Run `test_label_manager.py` to verify pass**
  Expected: All existing 6 + new 3 tests PASS.

---

### Task 6: Extend `SerialandBatchBundle` 7-Char Naming (`overrides-hooks`)

**Files:**
- Modify: `erpnextkta/overrides/serial_batch_bundle_doc.py:16-60`
- Test: `erpnextkta/tests/test_stock_entry_labeling.py`

**Interfaces:**
- Internal override in `SerialandBatchBundle._kta_get_preferred_name()`

- [x] **Step 1: Write failing test in `test_stock_entry_labeling.py` (`overrides-hooks`)**
  Submit a `Package Split` converting a `LEGACY` batch into new `{base_lot}0001` box and assert the inward `Serial and Batch Bundle` document `name == base_lot` (when unused in DB), and safely falls back if `base_lot` already exists as a bundle name.

- [x] **Step 2: Run test to verify failure**
  Expected: FAIL (ERPNext auto-hashed 20-char bundle name).

- [x] **Step 3: Update `autoname()` and `_kta_get_preferred_name()` in `serial_batch_bundle_doc.py` (`overrides-hooks`)**
  Extend `autoname()` condition to `self.voucher_type in ("Purchase Receipt", "Stock Entry", "Stock Reconciliation")`. Inside `_kta_get_preferred_name()`, preserve the `Purchase Receipt Item.batch_no` path for PRs, and for `Inward` `Stock Entry` (`Package Split`) and `Stock Reconciliation` extract the common 7-char `base_lot = batch_no[:-4]` across `self.entries` (populated before `save()` by `SerialBatchCreation`), returning `base_lot` only when uniform and unused in DB (`not frappe.db.exists("Serial and Batch Bundle", base_lot)`), else returning `None` safely.

- [x] **Step 4: Run test to verify pass**
  Expected: PASS.

---

### Task 7: `KTAStockEntry` Validation, Silence Guarantee & Cancel/Trash Label Sync (`overrides-hooks`)

**Files:**
- Modify: `erpnextkta/overrides/KTAStockEntry.py:207-355`
- Test: `erpnextkta/tests/test_stock_entry_labeling.py`

- [x] **Step 1: Write failing integration tests in `erpnextkta/tests/test_stock_entry_labeling.py` (`overrides-hooks`)**
  1. Standard `Material Transfer` and standard `Repack` (`is_standard=1`): submit triggers **0** calls to `print_stock_entry_labels` / zero labels created.
  2. Manual `Package Split` with 2 distinct incoming `item_code` rows: fails `validate()` with clear error requiring 1 doc per item/source box.
  3. `Return from Production Supply` full cycle: submit updates existing PR `KTA Stock Label.qty` while keeping `reference_doctype == "Purchase Receipt"`; cancelling the return Stock Entry restores PR label `qty` back to previous balance without deleting the PR label!
  4. `Package Split` cancel cycle: deletes only labels owned by `reference_name == se.name`, restores source box label `qty` to pre-split balance, and disables emptied child `000x` batches.

- [x] **Step 2: Run tests to verify failure**
  Expected: FAIL.

- [x] **Step 3: Update `KTAStockEntry.py` (`overrides-hooks`)**
  - Add `_validate_single_item_package_split()` inside `validate()`.
  - Extend `on_cancel()` / `on_trash()` to collect touched `(item_code, batch_no)` pairs for `Return from Production Supply` and `Package Split`, delete Stock Entry-owned labels (`_delete_associated_labels`), call `sync_batch_label_to_ledger_balance` for touched pairs, and disable emptied `Package Split` child batches on cancel.

- [x] **Step 4: Run Full Faz 1 Verification Suite (`overrides-hooks` & Coordinator)**
  Run:
  - `docker exec -w /home/frappe/frappe-bench erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/ruff check --no-cache --ignore EXE002 <modified_py_files>`
  - `docker exec -w /home/frappe/frappe-bench erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/ruff format --no-cache --check <modified_py_files>`
  - Run tests one-by-one: `test_label_manager`, `test_relabeling_service`, `test_stock_entry_labeling`, `test_purchase_receipt`, `test_line_replenishment_transfer`.
  - Verify `bench build --app erpnextkta --production`.
  Expected: All PASS cleanly.

- [x] **Step 5: Commit Faz 1 (Only when implementation is approved)**
  ```bash
  git add erpnextkta/ docs/
  git commit -m "feat(kta_stock): add core package split and relabeling engine"
  ```
  *(Every commit body bullet strictly `<= 75` chars.)*
