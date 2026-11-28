# Faz 3 Implementation Plan: `Shopfloor Hub` Production Supply Return, Optional Split & Docs Sync

> **For agentic workers:** Coordinator dispatches specialist subagents (`kta-shopfloor`, `frontend-public`, `docs-i18n`) strictly respecting `.agents/subagents/*.md` folder locks. Required sub-skill: `superpowers:subagent-driven-development`.

**Goal:** Add `150x -> 110 HAMMADDE` warehouse return (`Return from Production Supply` or automatic `Package Split` on partial/legacy returns) and optional inter-line `split_packages` (`150x <-> 150x`) to `Shopfloor Hub -> Hatlar Arası Transfer`, and synchronize portal HTML docs, developer guides, and TR/EN/DE translations across all 3 phases.

**Architecture:** Reuses Faz 1's `Return from Production Supply` & `Package Split` Stock Entry Types and `relabeling_service.create_package_split_repack()`. At the `110` warehouse gate, full remaining standard `7+4` boxes move via `Return from Production Supply` (`Material Transfer`, updating label qty/warehouse and printing `Depo Giriş Etiketi`), while partial/split/`LEGACY` returns automatically route through 1-source `Package Split` (`Repack`) docs. Inside `150x <-> 150x`, `split_packages=0` keeps instant silent `Material Transfer` by default while `split_packages=1` enables package splitting and printing.

**Tech Stack:** Frappe Framework / ERPNext v15 (Python 3.11), Vue 3 + TypeScript (`shopfloor-hub`), `ZebraPrinterManager`, HTML Portal Docs + CSV translations.

**Spec:** `docs/superpowers/specs/2026-11-21-faz3-shopfloor-supply-return-and-split-design.md`

---

## Global Constraints

- Depends on Faz 1 (`erpnextkta/kta_stock/services/relabeling_service.py`, Stock Entry Types `"Return from Production Supply"` & `"Package Split"`).
- Existing `Line Transfers` (`deficit_pull`, `MaterialStagingModal`, default `idle_push`, `ManualLineTransferModal` with `split_packages=0`) MUST remain 100% unchanged and silent.
- `LineIdleStockTable.vue` is currently 440 lines; MUST stay strictly `< 500` lines (offload return modal UI to `ProductionSupplyReturnModal.vue`).
- Every `.vue` component MUST be `< 500` lines, define `const __ = (...args: any[]) => (window as any).__(...args);`, use `<Teleport to="body">` for modals, and support Light & `[data-theme="dark"]`.
- `docs-i18n` MUST update both `erpnextkta/www/docs/` HTML pages and `docs/*.md` + `erpnextkta/translations/{tr,en,de}.csv` with Title Case labels, whole-sentence keys, and **zero** real vendor/customer company names or real unit prices.
- Every commit message line strictly `<= 100` chars (`<= 75` chars target).

## Review Focus

1. **Strict `110` Gate Split Routing:** Returning a partial box where remaining qty stays in `150x` (or where `110`/other warehouse already holds >0 balance of that batch) MUST route to `Package Split` (`Repack`), never `Return from Production Supply` (`Material Transfer`). *(Pinned to Task 1 tests)*
2. **Return Target Warehouse Lock:** `execute_production_supply_return` MUST reject `150x` production warehouses, group warehouses (`is_group=1`), `is_rejected_warehouse=1`, and any warehouse outside `110 HAMMADDE`. *(Pinned to Task 1 tests)*
3. **Reservation Protection on Supply Returns:** Returning `qty > free_qty` from `150x` to `110` MUST fail without `allow_reserved_override=1` and succeed up to `actual_qty` when explicitly confirmed. *(Pinned to Task 1 tests)*
4. **`LineIdleStockTable.vue` `< 500` Lines Guard:** Adding `Depoya İade (110)` trigger and split toggle MUST keep `LineIdleStockTable.vue` strictly `< 500` lines via `ProductionSupplyReturnModal.vue`. *(Pinned to Task 3 verification)*
5. **Backwards Compatibility of `execute_line_transfer`:** Calling `execute_shopfloor_line_transfer` without `split_packages` MUST default to `0` (`Material Transfer`, no ZPL printed). *(Pinned to Task 2 & Task 4 tests)*

---

## Subagent Ownership & File Structure

| Task | Subagent | Files Owned / Touched |
|---|---|---|
| Task 1 | `kta-shopfloor` | Modify `erpnextkta/kta_shopfloor/services/line_transfer_service.py` (`get_raw_material_return_warehouses`, `is_valid_raw_material_return_warehouse`, `execute_production_supply_return`) & `erpnextkta/kta_shopfloor/api.py`; Test in `erpnextkta/kta_shopfloor/tests/test_line_transfer_service.py` |
| Task 2 | `kta-shopfloor` | Modify `erpnextkta/kta_shopfloor/services/line_transfer_service.py` (`split_packages` opt-in on `execute_line_transfer`) & `erpnextkta/kta_shopfloor/api.py`; Test in `test_line_transfer_service.py` |
| Task 3 | `frontend-public` | Modify `erpnextkta/public/shopfloor-hub/types.ts`; Create `erpnextkta/public/shopfloor-hub/components/ProductionSupplyReturnModal.vue` (`< 400` lines) |
| Task 4 | `frontend-public` | Modify `erpnextkta/public/shopfloor-hub/components/{LineIdleStockTable.vue, ManualLineTransferModal.vue, LineTransfersPanel.vue}` (each `< 500` lines) |
| Task 5 | `docs-i18n` | Modify `erpnextkta/www/docs/{stok-lojistik, shopfloor-hub}.html`, `docs/{kta_stok_lojistik_kilavuzu, kta_shopfloor_hub_kilavuzu}.md`, `erpnextkta/translations/{tr,en,de}.csv` |

---

### Task 1: Backend `150x -> 110` Production Supply Return Service (`kta-shopfloor`)

**Files:**
- Modify: `erpnextkta/kta_shopfloor/services/line_transfer_service.py`
- Modify: `erpnextkta/kta_shopfloor/api.py`
- Test: `erpnextkta/kta_shopfloor/tests/test_line_transfer_service.py`

**Interfaces:**
- Consumes: `erpnextkta.kta_stock.services.relabeling_service.{is_standard_kta_box_batch, get_batch_ledger_balances, create_package_split_repack}`
- Produces:
  - `is_valid_raw_material_return_warehouse(warehouse: str | None) -> bool`
  - `get_raw_material_return_warehouses(company: str | None = None) -> list[dict]` -> `[{"warehouse": str, "label": str}]`
  - `execute_production_supply_return(returns: list[dict] | str, allow_reserved_override: int | bool = 0, remarks: str | None = None) -> dict` -> `{"success": True, "stock_entries": list[str], "return_stock_entry": str | None, "split_stock_entries": list[str], "returned_items": list[dict], "used_reserved_stock": bool}`
  - Whitelisted endpoints in `erpnextkta/kta_shopfloor/api.py`: `get_raw_material_return_warehouses` & `execute_shopfloor_supply_return`

- [x] **Step 1: Write failing tests in `test_line_transfer_service.py` (`kta-shopfloor`)**
  1. `test_return_target_warehouse_validation_rejects_production_and_groups`: `150x` leaf, `110 HAMMADDE` group, and `is_rejected_warehouse=1` return `False`; active `110` leaf shelf returns `True`.
  2. `test_full_remaining_standard_box_return_creates_return_entry_and_updates_label`: Returning entire remaining balance (`40`) of `"LOT12340001"` from `150x` to `110` shelf (with `0` other stock of `"LOT12340001"`): submits `Return from Production Supply` (`Material Transfer`) and sets existing PR/box label `qty=40` & `target_warehouse=110 shelf` while preserving PR reference.
  3. `test_partial_box_or_legacy_return_routes_to_package_split`: Returning `15` out of `40` of `"LOT12340001"` (or any qty of `"LEGACY-ITEM"`): creates submitted `Package Split` (`Repack`), mints `"LOT12340002"` (`15`) in `110`, leaves `"LOT12340001"` (`25`) in `150x`, and syncs both labels.
  4. `test_return_respects_reserved_qty_protection`: Fails unless `allow_reserved_override=1`.

- [x] **Step 2: Run tests to verify failure**
  Run: `docker exec -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_line_transfer_service`
  Expected: FAIL.

- [x] **Step 3: Implement return validation, routing & API endpoints (`kta-shopfloor`)**
  Resolve the `110` root warehouse company-safely via `KTA MRP Settings` or normalized `"110 hammadde"` / `"110 raw material"` group node + `lft/rgt` leaf traversal (excluding groups, disabled, `is_rejected_warehouse=1`, and `150x`). Support explicit `batch_no` when supplied (else LIFO), NEVER call `se.set_stock_entry_type()` on `Return from Production Supply` docs, group eligible full-box standard returns into one `Return from Production Supply` Stock Entry, and execute partial/legacy returns per source box via `create_package_split_repack`.

- [x] **Step 4: Run tests to verify pass**
  Expected: PASS.

---

### Task 2: Optional `split_packages` Support on Inter-Line Transfers (`kta-shopfloor`)

**Files:**
- Modify: `erpnextkta/kta_shopfloor/services/line_transfer_service.py:1001-1075`
- Modify: `erpnextkta/kta_shopfloor/api.py:675-694`
- Test: `erpnextkta/kta_shopfloor/tests/test_line_transfer_service.py`

**Interfaces:**
- Modifies: `execute_line_transfer(..., split_packages: int | bool = 0)` and `api.execute_shopfloor_line_transfer(..., split_packages: int = 0)`

- [x] **Step 1: Write failing tests in `test_line_transfer_service.py` (`kta-shopfloor`)**
  1. Default (`split_packages=0`): Partial transfer `1501 -> 1502` creates `Material Transfer` (no `Package Split`, no labels created).
  2. Opt-in (`split_packages=1`): Partial transfer `1501 -> 1502` creates `Package Split` (`Repack`) with new `000x` box batch in `1502` and `Depo Giriş Etiketi` created/queued for printing; full standard box moves via `Material Transfer` and prints its updated label.

- [x] **Step 2: Run tests to verify failure**
  Expected: FAIL.

- [x] **Step 3: Implement `split_packages` branch in `line_transfer_service.py` & `api.py` (`kta-shopfloor`)**
  Keep default path untouched; when `cint(split_packages) == 1`, split partial/legacy allocations via `create_package_split_repack`, move full standard allocations via `Material Transfer` and call `upsert_box_label` + `enqueue_print_labels_by_names`.

- [x] **Step 4: Run tests to verify pass**
  Expected: PASS.

---

### Task 3: Types & `ProductionSupplyReturnModal.vue` (`frontend-public`)

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/types.ts`
- Create: `erpnextkta/public/shopfloor-hub/components/ProductionSupplyReturnModal.vue` (`< 400` lines)

**Interfaces:**
- Types added to `types.ts`: `RawMaterialReturnWarehouseOption`, `ProductionSupplyReturnPayloadItem` (`{ item_code, qty, source_warehouse, target_warehouse, batch_no?: string | null }`), `ProductionSupplyReturnResponse`, plus optional `split_packages?: number | boolean` on `LineTransferPayloadItem` and `stock_entries?: string[]` on `LineTransferResponse`.
- Modal props/emits match `ManualLineTransferModal.vue` (`<Teleport to="body">`, Light & Dark CSS variables, Escape key handler, reserved override confirmation).

- [x] **Step 1: Update `types.ts` and implement `ProductionSupplyReturnModal.vue` (`frontend-public`)**
  Pre-fill selected items from `Atıl Hat Stoğu`, fetch `erpnextkta.kta_shopfloor.api.get_raw_material_return_warehouses`, validate `qty <= actual_qty`, allow optional `batch_no` override when scanning/picking a specific open box, show reserved warning inline, emit confirmed return payload. (Note: `LineIdleStockTable.vue`'s split checkbox applies ONLY to `150x <-> 150x`; returns to `110` always enforce §2.1 auto gate routing.)

- [x] **Step 2: Verify `< 500` lines and clean TS syntax**

---

### Task 4: Wire Return & Optional Package Split in `LineIdleStockTable`, `ManualLineTransferModal` & `LineTransfersPanel` (`frontend-public`)

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/components/LineIdleStockTable.vue` (MUST remain `< 500` lines — currently 440 lines!)
- Modify: `erpnextkta/public/shopfloor-hub/components/ManualLineTransferModal.vue` (`< 450` lines)
- Modify: `erpnextkta/public/shopfloor-hub/components/LineTransfersPanel.vue` (`< 450` lines)

- [x] **Step 1: Update `LineIdleStockTable.vue` (`frontend-public`)**
  Add **`↩️ Depoya İade (110)`** button beside `Seçilenleri Gönder` (enabled whenever rows are selected regardless of `targetWarehouse` being a `150x` hat!), add compact `Yeni Koliye Böl ve Etiket Bas` checkbox for inter-line send, keep total line count `< 500`.

- [x] **Step 2: Update `ManualLineTransferModal.vue` & `LineTransfersPanel.vue` (`frontend-public`)**
  Add `split_packages` toggle in `ManualLineTransferModal.vue`; handle return modal state + `execute_shopfloor_supply_return` execution + reserved warning modal reuse cleanly in `LineTransfersPanel.vue`.

- [x] **Step 3: Build Vue bundle & verify `< 500` lines per `.vue` file**
  Run `bench build --app erpnextkta --production`. Expected: Exit `0`, zero warnings/errors.

---

### Task 5: Portal Documentation, Developer Guides & Multilingual Translations (`docs-i18n`)

**Files:**
- Modify: `erpnextkta/www/docs/stok-lojistik.html`
- Modify: `erpnextkta/www/docs/shopfloor-hub.html`
- Modify: `docs/kta_stok_lojistik_kilavuzu.md`
- Modify: `docs/kta_shopfloor_hub_kilavuzu.md`
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`

- [x] **Step 1: Update Portal HTML Docs & Developer Guides (`docs-i18n`)**
  Document `Return from Production Supply`, `Package Split`, `7 hane Lot + 4 hane Kutu` standard, Sayım Merkezi (`Mod 1 / Mod 2`, `LEGACY` standartlaştırma), `Atıl Hat Stoğu → Depoya İade (150x → 110)`, and new `kta_stock/services` module paths. Strictly verify zero commercial company names or unit prices.

- [x] **Step 2: Synchronize `tr.csv`, `en.csv`, `de.csv` (`docs-i18n`)**
  Add all new strings from Faz 1, Faz 2, and Faz 3 with Title Case compliance, whole-sentence integrity, and collision checks against existing translations.

- [x] **Step 3: Coordinator Final Quality Gate**
  Run `bench migrate`, `bench build --app erpnextkta --production`, full `kta_stock` + `kta_shopfloor` + `erpnextkta.tests.test_stock_entry_labeling` test suite, `ruff check` & `ruff format --check` on all modified Python files, and verify `< 500` lines on all modified `.vue` files.

- [x] **Step 4: Commit Faz 3 (When approved)**
  ```bash
  git add erpnextkta/ docs/
  git commit -m "feat(shopfloor): add supply return, package split, and docs"
  ```
