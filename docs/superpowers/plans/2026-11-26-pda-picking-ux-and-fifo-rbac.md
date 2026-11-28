# PDA Picking UX Overhaul, FIFO Deviation Audit, Skip RBAC & FIFO `manufacturing_date` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the Approach A walk-order Line Replenishment Picking PDA UX with strict barcode verification, one-click FIFO override audit logging (`Stock Entry.remarks` + `KTA Line Replenishment Order.remarks`), `Stock Manager` skip RBAC + all-skipped cancellation, and `manufacturing_date`-aware FIFO sorting.

**Architecture:** Extend `KTA Line Replenishment Item` with skip/override fields, unify FIFO candidate sorting (`expiry_date -> manufacturing_date -> creation`) and strict picking/skip completion in `line_replenishment_service.py`, enrich `line_replenishment_picking.py` with walk-order sorting and live ledger balance lookup, and share one Vue 3 TypeScript composable (`useLineReplenishmentPicking.ts`) + `<Teleport to="body">` modals across both `/pda` (`PickingModuleView.vue`) and `/app/line-replenishment-picking` (`PdaApp.vue`). Keep `.agents/AGENTS.md` folder locks intact by routing edits through specialist subagents (`kta-stock`, `frontend-public`, `docs-i18n`) using `Workspace="inherit"`.

**Tech Stack:** Frappe v15 / ERPNext (Python 3, MariaDB/Frappe ORM), Vue 3 + TypeScript + Vite (`bench build --app erpnextkta --production`), Vitest + `@vue/test-utils`, Ruff, Frappe `FrappeTestCase`.

**Spec:** [2026-11-26-pda-picking-ux-and-fifo-rbac-design.md](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-26-pda-picking-ux-and-fifo-rbac-design.md)

## Global Constraints

- **Coordinator Role Lock (`.agents/AGENTS.md`):** Coordinator MUST NOT edit application source files under `erpnextkta/**`, `frontend/**`, or `docs/` (except `docs/superpowers/**`); dispatch `kta-stock`, `frontend-public`, and `docs-i18n` with `Workspace="inherit"`.
- **Visual & Palette Lock:** `PdaHubApp.vue`, `.pda-topbar`, `.pda-subbar`, and `erpnextkta/public/pda-hub/pda-hub.bundle.css` palette tokens (`--bg-color`, `--card-bg`, `--control-bg`, `--text-color`, `--text-muted`, `--border-color`, `--pda-primary`, `--pda-success`, `--pda-danger`, `--pda-surface-alt`) MUST remain untouched; render ONLY one sticky bottom action button (`TransferFooter.vue`).
- **Tablet Responsive Sizing (`>= 768px`) & Fixed Footer Anchoring:** Preserve mobile single-column layout below `768px`; at `min-width: 768px`, constrain picking content to `max-width: 960px` centered, place `OrderSelector` + `BarcodeScannerBar` side-by-side in 2 columns, render pending cards in a 2-column grid with compact tablet scale (`padding: 10px`, `min-height: 40px`), switch `TransferFooter.vue` to a horizontal row with a compact right-aligned action button (`min-width: 240px; min-height: 44px`), and bound modals to `max-width: 460px`. Anchor `TransferFooter.vue` with `position: fixed; bottom: 0; left: 0; right: 0; z-index: 38` (+ `safe-area-inset-bottom` and `padding-bottom: 112px` mobile / `84px` tablet on parent view) so it never floats upward when scrolled to the bottom.
- **Vue 500-Line & i18n Invariants:** Every `.vue` file MUST stay `<= 500` lines; define `const __ = (...args: any[]) => (window as any).__(...args);` inside `<script setup>`; render modals with `<Teleport to="body">`; support both Light and `[data-theme="dark"]` modes.
- **English Identifiers & Clean-CI:** All new DocType fields MUST use English snake_case (`is_skipped`, `skipped_by`, `is_fifo_override`); all backend tests MUST run dynamically on an empty Clean-CI `test_site` without hardcoded company/warehouse fixtures.
- **Documentation, CSV & Confidentiality:** Update `erpnextkta/www/docs/stok-lojistik.html`, `erpnextkta/www/docs/line_replenishment.html`, and `docs/kta_stok_lojistik_kilavuzu.md`; update `translations/{tr,en,de}.csv` strictly append-only (Title Case, 0 deletions, 0 duplicates); NEVER log unit costs, prices, or vendor/customer names in `remarks`, tests, or docs.
- **Build & Lint Tools:** Build exclusively via `bench build --app erpnextkta --production`; lint/format Python via `/home/frappe/frappe-bench/env/bin/ruff`.

## Review Focus

- **Out-of-order multi-box scan on same item:** Scanning `BATCH-02` (Row 2) before `BATCH-01` (Row 1) matches Row 2 cleanly as exact FIFO without falsely popping `FifoOverrideModal` against Row 1 — pinned in Task 3 (`PickingModuleView.spec.ts`).
- **Stale / moved box balance between scan and submit:** If a scanned box was transferred out or depleted before clicking `Transferi Tamamla`, `complete_line_replenishment_picking` validates live `get_batch_ledger_balances` and raises `frappe.ValidationError` — pinned in Task 2 (`test_line_replenishment_transfer.py`).
- **Split/backdated `manufacturing_date` & shelf-to-shelf Material Transfer FIFO order:** Older `manufacturing_date` with newer `Batch.creation` (and no `expiry_date`), as well as a box moved between shelves via Material Transfer, stays rank #1 in both `allocate_fifo_batches` and `bulk_allocate_fifo_batches` — pinned in Task 1 (`test_line_replenishment_service.py`).
- **Undo (`↩`) state reset after FIFO override or Skip:** Undoing an overridden or skipped row restores `suggested_batch_no`, `suggested_source_warehouse`, `picked_qty = deficit_qty`, `is_fifo_override = 0`, `is_skipped = 0`, and recalculates `TransferFooter` readiness — pinned in Task 3 (`PickingModuleView.spec.ts`).
- **Dual-consumer parity (`/pda` & Desk page) + 500-line & shell lock:** Both `PickingModuleView.vue` and `PdaApp.vue` stay `<= 500` lines, consume `useLineReplenishmentPicking.ts`, and leave `PdaHubApp.vue` and `pda-hub.bundle.css` unmodified — pinned in Task 3 verification step.

---

### Task 1: Schema, `manufacturing_date` FIFO Sorting, Walk-Order Details & Live Barcode Resolution (`kta-stock`)

**Files:**
- Modify: `erpnextkta/kta_stock/doctype/kta_line_replenishment_item/kta_line_replenishment_item.json`
- Modify: `erpnextkta/kta_stock/line_replenishment_service.py:225-503`
- Modify: `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py:1-174`
- Test: `erpnextkta/kta_stock/tests/test_line_replenishment_service.py`
- Test: `erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py`

**Interfaces:**
- Consumes: `erpnextkta.kta_stock.services.relabeling_service.get_batch_ledger_balances(item_code: str, batch_no: str) -> list[dict]`, `_PICKING_ALLOWED_ROLES`
- Produces:
  - `_SKIP_ALLOWED_ROLES = frozenset({"Stock Manager", "System Manager"})` in `line_replenishment_service.py`
  - `_fifo_candidate_sort_key(c: dict) -> tuple` in `line_replenishment_service.py`
  - `get_replenishment_order_details(order_name: str | None = None) -> dict | None` returning `can_skip_items: bool` and naturally shelf-sorted `items` with `has_batch_no`, `is_skipped`, `skipped_by`, `is_fifo_override`
  - `resolve_scanned_barcode(barcode: str | None = None, order_name: str | None = None) -> dict` returning `{item_code, batch_no, qty, warehouse, available_balances, already_in_target, batch_disabled, has_batch_no, label_name?, source?}`

- [x] **Step 1: Add the 3 English schema fields to `KTA Line Replenishment Item`**

Update `erpnextkta/kta_stock/doctype/kta_line_replenishment_item/kta_line_replenishment_item.json` `field_order` and `fields` with:
- `is_skipped` (`Check`, label `"Is Skipped"`, default `"0"`, `in_list_view: 1`)
- `skipped_by` (`Link`, label `"Skipped By"`, options `"User"`, `read_only: 1`)
- `is_fifo_override` (`Check`, label `"FIFO Override"`, default `"0"`, `read_only: 1`)

- [x] **Step 2: Migrate the local bench site so the new columns exist in MariaDB**

Run:
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost migrate`
Expected: Migration completes cleanly and `KTA Line Replenishment Item` exposes `is_skipped`, `skipped_by`, `is_fifo_override`.

- [x] **Step 3: Write failing backend tests for `manufacturing_date` FIFO priority, walk-order sorting, `can_skip_items`, and live `resolve_scanned_barcode`**

In `erpnextkta/kta_stock/tests/test_line_replenishment_service.py`:
- Add `test_fifo_prioritizes_manufacturing_date_over_creation_and_preserves_after_shelf_transfer`:
  - Assert `allocate_fifo_batches()` and `bulk_allocate_fifo_batches()` both place an earlier-`manufacturing_date` / newer-`creation` split batch (no `expiry_date`) ahead of a later-`manufacturing_date` receipt.
  - Execute a real `Material Transfer` `Stock Entry` moving that older batch to `self.shelf_2` and assert `allocate_fifo_batches()` still returns the older batch first with `warehouse == self.shelf_2`.

In `erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py`:
- Add `test_order_details_walk_order_sorting_role_flags_and_has_batch`:
  - Assert `get_replenishment_order_details` sorts shelves naturally (`W1A-02-01` before `W1A-10-01` before `W1B-01-01`).
  - Assert `can_skip_items` is `False` for `PDA_ROLE_STOCK_USER`/`Stock User` and `True` for `Stock Manager`.
  - Assert each row includes `has_batch_no`, `is_skipped`, `skipped_by`, `is_fifo_override`.
- Add `test_resolve_scanned_barcode_returns_live_shelf_and_target_flags`:
  - Assert `resolve_scanned_barcode(batch_id, order_name=order.name)` returns live `warehouse` and full ledger `qty` even if `KTA Stock Label.qty` differs.
  - Assert scanning a batch only located in `order.target_warehouse` returns `already_in_target == True` and `warehouse is None`.
  - Assert scanning a disabled batch returns `batch_disabled == True` and `qty == 0.0`.
  - Assert `resolve_scanned_barcode(code)` (without `order_name`) remains backward-compatible.

- [x] **Step 4: Run tests to verify failure**

Run:
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_service`
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page`
Expected: FAIL on missing sort keys, missing `can_skip_items`, and missing live warehouse fields.

- [x] **Step 5: Implement `_fifo_candidate_sort_key`, `_SKIP_ALLOWED_ROLES`, walk-order details, and live `resolve_scanned_barcode`**

In `erpnextkta/kta_stock/line_replenishment_service.py`:
- Define `_SKIP_ALLOWED_ROLES = frozenset({"Stock Manager", "System Manager"})`.
- Extract `_fifo_candidate_sort_key(c: dict) -> tuple` sorting `(exp is None, exp_str, mfg is None, mfg_str, created_str, c.get("batch_no") or "", c.get("warehouse") or "")`.
- Fetch `"manufacturing_date"` alongside `"name", "expiry_date", "creation"` in both `allocate_fifo_batches()` and `bulk_allocate_fifo_batches()` and sort both with `_fifo_candidate_sort_key`.

In `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py`:
- Implement `_natural_shelf_sort_key(row: dict) -> tuple` using `re.split(r"(\d+)", ...)`.
- Update `get_replenishment_order_details(order_name: str | None = None) -> dict | None` to attach `can_skip_items`, bulk-fetch `Item.has_batch_no`, add `has_batch_no`, `is_skipped`, `skipped_by`, `is_fifo_override` (preserving `picked_qty` fallback to `deficit_qty` only when `not is_skipped`), and sort `items_data` by `_natural_shelf_sort_key`.
- Update `resolve_scanned_barcode(barcode: str | None = None, order_name: str | None = None) -> dict` to resolve live warehouse balances via `get_batch_ledger_balances(item_code, batch_no)`, exclude `is_group`, `disabled`, `is_rejected_warehouse`, company mismatches, and `order.target_warehouse`, prefer suggested shelf if split across multiple shelves, and set `already_in_target` / `batch_disabled` / `has_batch_no`.

- [x] **Step 6: Run tests and Ruff to verify Task 1 passes**

Run:
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_service`
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page`
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/ruff check apps/erpnextkta/erpnextkta/kta_stock/line_replenishment_service.py apps/erpnextkta/erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py`
Expected: All tests PASS and Ruff clean.

---

### Task 2: Strict Picking Completion, Intact-Box Guard, Skip RBAC, All-Skipped Cancellation & Remarks (`kta-stock`)

**Files:**
- Modify: `erpnextkta/kta_stock/line_replenishment_service.py:814-978`
- Test: `erpnextkta/kta_stock/tests/test_line_replenishment_transfer.py`

**Interfaces:**
- Consumes: `_SKIP_ALLOWED_ROLES` (Task 1), `KTA Line Replenishment Item` (`is_skipped`, `skipped_by`, `is_fifo_override` from Task 1), `relabeling_service.get_batch_ledger_balances`
- Produces:
  - `complete_line_replenishment_picking(order_name: str, picked_items: list[dict] | str | None = None) -> str`
  - Modular helpers `_match_picked_item_row`, `_validate_batch_and_box_balance`, `_build_replenishment_audit_remarks`

- [x] **Step 1: Write failing transfer, RBAC skip, all-skipped cancellation, and audit remarks tests**

In `erpnextkta/kta_stock/tests/test_line_replenishment_transfer.py`:
- `test_fifo_override_full_box_over_15_percent_accepted_and_logged_to_remarks`:
  - Suggest `BATCH-A` (100 qty) on `shelf_1`, scan intact `BATCH-B` (140 qty — exceeds manual +15% threshold) on `shelf_2`; assert `complete_line_replenishment_picking` succeeds, creates `Stock Entry` with `BATCH-B` / `shelf_2` / `140.0`, marks `row.is_fifo_override == 1`, and writes `[FIFO SAPMASI]` with both batches/shelves into `se.remarks` and `order.remarks` (no prices/vendor names).
- `test_picked_items_rejects_partial_box_duplicate_batch_stale_balance_and_incomplete_rows`:
  - Assert `ValidationError` when: (a) batch-tracked row submits partial `picked_qty < live_qty`, (b) two rows claim the same `(item_code, batch_no, s_warehouse)`, (c) scanned box stock was moved elsewhere before submit (stale balance), or (d) an order with 2 rows receives `picked_items` covering only 1 row.
- `test_skip_item_rejected_for_stock_user_and_allowed_for_stock_manager_with_deficit_reappearance`:
  - With a `KTA PDA Stock User` (or `Stock User`), sending `is_skipped: 1` raises `frappe.PermissionError`.
  - With a `Stock Manager`, picking Row 1 and skipping Row 2 creates a `Stock Entry` for Row 1 only, sets `order.status == "Completed"`, records `[ATLANAN KALEMLER]` in `se.remarks` and `order.remarks`, and `reservation_deficit_service._get_drafts_by_item(target_wh)` no longer deducts Row 2 so Row 2 reappears as deficit.
- `test_all_items_skipped_cancels_order_without_empty_stock_entry`:
  - With a `Stock Manager`, skipping all rows returns `""`, creates NO `Stock Entry` (`order.stock_entry` is empty/None), sets `order.status == "Cancelled"`, writes `[ATLANAN KALEMLER]` to `order.remarks`, and releases all skipped items back into `_get_drafts_by_item(target_wh)`.

- [x] **Step 2: Run transfer tests to verify failure**

Run:
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer`
Expected: FAIL on the 4 new tests while existing 6 tests stay green.

- [x] **Step 3: Refactor `complete_line_replenishment_picking` into clean modular helpers**

In `erpnextkta/kta_stock/line_replenishment_service.py`:
- Keep `picked_items is None` headless mode unchanged for backward compatibility (all rows marked `is_picked = 1`).
- When `picked_items` list/JSON is passed:
  - Enforce 1-to-1 row resolution (`_match_picked_item_row`) so every row in `order.items` is explicitly resolved as picked (`is_picked=1`) or skipped (`is_skipped=1`); throw `ValidationError` if any row remains unresolved.
  - Enforce server-side RBAC: if any row is skipped and `not user_roles.intersection(_SKIP_ALLOWED_ROLES)`, throw `frappe.PermissionError`.
  - Enforce `is_skipped=1, skipped_by=user, is_picked=0, picked_qty=0.0, is_fifo_override=0` on skipped rows.
  - For each picked row: resolve group source warehouses via `get_leaf_warehouses`; block `s_warehouse == order.target_warehouse`, `disabled == 1`, or `is_rejected_warehouse == 1`; if `batch_no` present, validate `Batch.item == row.item_code`, `disabled == 0`, uniqueness of `(row.item_code, batch_no, s_warehouse)`, live ledger balance `live_qty > 1e-6`, and intact full box equality `abs(picked_qty - live_qty) <= 1e-6`; keep `max(deficit * 1.15, deficit + 1.0)` cap only for non-batch rows.
  - Mark `row.is_fifo_override = 1` when batch-tracked `picked_batch_no != suggested_batch_no` or `s_warehouse != suggested_source_warehouse`.
  - Build structured remarks via `_build_replenishment_audit_remarks(order, fifo_notes, skip_notes)`.
  - Branch cleanly:
    - If `not se_items` (all rows skipped): set `order.stock_entry = None`, `order.total_picked_qty = 0.0`, `order.status = "Cancelled"`, `order.remarks = audit_remarks`, `order.save(ignore_permissions=True)`, return `""`.
    - If `se_items`: create & submit `Stock Entry` with `se.remarks = audit_remarks`, set `order.status = "Completed"`, `order.stock_entry = se.name`, `order.total_picked_qty = total_picked`, `order.remarks = audit_remarks`, `order.save(ignore_permissions=True)`, return `se.name`.

- [x] **Step 4: Run transfer tests and Ruff to verify Task 2 passes**

Run:
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer`
`docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/ruff check apps/erpnextkta/erpnextkta/kta_stock/line_replenishment_service.py apps/erpnextkta/erpnextkta/kta_stock/tests/test_line_replenishment_transfer.py`
Expected: All tests in `test_line_replenishment_transfer` PASS (`10/10`) and Ruff clean.

---

### Task 3: Shared Picking Composable, Approach A Walk-Order Cards, Teleport Modals & Dual-App Sync (`frontend-public`)

**Files:**
- Modify: `erpnextkta/public/line-replenishment-pda/types.ts`
- Create: `erpnextkta/public/line-replenishment-pda/composables/useLineReplenishmentPicking.ts`
- Create: `erpnextkta/public/line-replenishment-pda/components/FifoOverrideModal.vue`
- Create: `erpnextkta/public/line-replenishment-pda/components/SkipItemModal.vue`
- Modify: `erpnextkta/public/line-replenishment-pda/components/PickingItemCard.vue`
- Modify: `erpnextkta/public/line-replenishment-pda/components/OrderSelector.vue`
- Modify: `erpnextkta/public/line-replenishment-pda/components/BarcodeScannerBar.vue`
- Modify: `erpnextkta/public/line-replenishment-pda/components/TransferFooter.vue`
- Modify: `erpnextkta/public/pda-hub/views/PickingModuleView.vue`
- Modify: `erpnextkta/public/line-replenishment-pda/PdaApp.vue`
- Test: `erpnextkta/public/pda-hub/__tests__/PickingModuleView.spec.ts`

**Interfaces:**
- Consumes: `get_open_replenishment_orders`, `get_replenishment_order_details`, `resolve_scanned_barcode`, `complete_line_replenishment_picking` (Tasks 1–2)
- Produces:
  - `compareShelfNames(a?: string | null, b?: string | null): number` in `types.ts`
  - `useLineReplenishmentPicking(options?: { onOrdersUpdated?: (count: number) => void; confirmTransfer?: ... })` in `composables/useLineReplenishmentPicking.ts`
  - `FifoOverrideModal.vue` (`candidate: FifoOverrideCandidate | null`, emits `confirm`, `cancel`)
  - `SkipItemModal.vue` (`item: PickingItem | null`, emits `confirm`, `cancel`)
  - Updated `PickingItemCard.vue` (props: `item`, `highlighted`, `canSkip`; emits: `undo`, `request-skip`, `update-qty`, `confirm-non-batch`)
  - Updated `TransferFooter.vue` (props: `canComplete`, `pickedCount`, `skippedCount`, `totalCount`, `pendingCount`, `allSkipped`, `loading`; emits: `complete`)

- [x] **Step 1: Extend TypeScript contracts and natural shelf comparator in `types.ts`**

Update `erpnextkta/public/line-replenishment-pda/types.ts` with `can_skip_items`, `has_batch_no`, `is_skipped`, `skipped_by`, `is_fifo_override`, `warehouse`, `available_balances`, `already_in_target`, `batch_disabled`, `FifoOverrideCandidate`, and `compareShelfNames()`.

- [x] **Step 2: Write failing frontend tests in `erpnextkta/public/pda-hub/__tests__/PickingModuleView.spec.ts`**

Cover all Review Focus & Spec scenarios:
1. Renders pending cards in natural shelf walk-order (`W1A-02-01` before `W1A-10-01`).
2. Batch-tracked card renders shelf badge, full box qty badge, `item_code`, `item_name`, `suggested_batch_no` — and does NOT render checkbox, `-` / `+` buttons, qty `<input>`, or `Tümünü Al`.
3. Non-batch card (`has_batch_no: 0`) shows minimal qty control + `Onayla` exception button.
4. Duplicate barcode scan does NOT double `picked_qty` and shows `"zaten okutuldu"` feedback.
5. Bare `item_code` scan on batch-tracked item is rejected with `"parti takiplidir"` error.
6. Out-of-order multi-box scan on same item (`BATCH-02` scanned first when Row 1=`BATCH-01`, Row 2=`BATCH-02`) directly picks Row 2 WITHOUT triggering `FifoOverrideModal`.
7. Different batch scan opens `FifoOverrideModal` (with suggested vs scanned shelf/batch/real qty); cancel keeps pending; confirm picks row with `⚠️ FIFO Sapması`, collapses to green picked row, and undo (`↩`) resets all override fields.
8. `can_skip_items: false` hides `Atla`; `can_skip_items: true` allows skipping via `SkipItemModal`, shows `Atlanan (1)` tab, keeps `TransferFooter` disabled until remaining items are handled, and switches footer button to `"Emri İptal Et (Tümü Atlandı)"` when all rows are skipped.

- [x] **Step 3: Run Vitest on the new test file to confirm it fails before UI changes**

Run: `npx vitest run __tests__/PickingModuleView.spec.ts` (cwd: `erpnextkta/public/pda-hub`)
Expected: FAIL against current card/view implementation.

- [x] **Step 4: Implement `useLineReplenishmentPicking.ts`, Teleport modals, and updated Approach A components + views**

- Build `useLineReplenishmentPicking.ts` implementing all 8 barcode decision cases, duplicate-scan guard (`info`), FIFO modal state, Skip modal state, segmented tab state (`pending` | `picked` | `skipped`), undo handler, and `onCompleteTransfer` sending all resolved rows (`is_picked` + `is_skipped`). Note: DO NOT overwrite pending batch `picked_qty` UI state until picked, while keeping `picked_items` submission clean.
- Build `FifoOverrideModal.vue` (`<Teleport to="body">`, CSS vars + `[data-theme="dark"]`, lazy `__`) and `SkipItemModal.vue` (`<Teleport to="body">`), both centered with `max-width: 460px; width: calc(100% - 24px);`.
- Redesign `PickingItemCard.vue` (`<= 300` lines), enhance `OrderSelector.vue`, `BarcodeScannerBar.vue` (add `info` style + dark theme rules), and `TransferFooter.vue` (single viewport-fixed bottom bar using `position: fixed; bottom: 0; left: 0; right: 0; z-index: 38;` with `calc(10px + env(safe-area-inset-bottom, 0px))` and inner `.pda-footer-inner` wrapper so it stays pinned at scroll bottom and under `z-index: 1070–1200` modals/drawer, supporting both transfer and all-skipped cancel).
- Refactor both `PickingModuleView.vue` and `PdaApp.vue` to consume `useLineReplenishmentPicking`, keeping every `.vue` file strictly `<= 500` lines, giving the outer view sufficient bottom clearance (`padding-bottom: 112px` mobile / `84px` tablet), and preserving `PdaHubApp.vue` + `pda-hub.bundle.css` untouched.
- Add `@media (min-width: 768px)` tablet responsive rules across `PickingModuleView.vue`, `PdaApp.vue`, `OrderSelector.vue`, `BarcodeScannerBar.vue`, `PickingItemCard.vue`, and `TransferFooter.vue`: centered `max-width: 960px` container, 2-column top control bar (`minmax(0, 1fr) minmax(0, 1.2fr)`), 2-column pending card grid (`repeat(2, minmax(0, 1fr))`) with compact tablet padding/controls (`padding: 10px`, `min-height: 40px`), single-row collapsed picked/skipped list alignment, and horizontal `TransferFooter` (`flex-direction: row; justify-content: space-between`, right-aligned button `width: auto; min-width: 240px; min-height: 44px; padding: 8px 22px`).

- [x] **Step 5: Run Vitest suite, line-count check, and visual-lock diff check**

Run:
- `npx vitest run` (cwd: `erpnextkta/public/pda-hub`)
- PowerShell check: line counts of all modified `.vue` files `<= 500`, and `git diff --name-only -- erpnextkta/public/pda-hub/PdaHubApp.vue erpnextkta/public/pda-hub/pda-hub.bundle.css` returns empty.
Expected: All Vitest suites PASS, zero `.vue` file > 500 lines, `PdaHubApp.vue` and `pda-hub.bundle.css` untouched.

---

### Task 4: Portal Docs, Developer Guide, Multilingual CSVs (`docs-i18n`) & Coordinator Quality Gate

**Files:**
- Modify: `erpnextkta/www/docs/stok-lojistik.html`
- Modify: `erpnextkta/www/docs/line_replenishment.html`
- Modify: `docs/kta_stok_lojistik_kilavuzu.md`
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`

**Interfaces:**
- Consumes: Exact UI copy strings from Task 3 components/composable and RBAC/audit behavior from Tasks 1–2.
- Produces: Synchronized portal HTML docs, developer guide markdown, and append-only zero-duplicate EN/DE/TR translation mappings.

- [x] **Step 1: Update portal HTML documentation and developer guide**

In `erpnextkta/www/docs/stok-lojistik.html`, `erpnextkta/www/docs/line_replenishment.html`, and `docs/kta_stok_lojistik_kilavuzu.md`:
- Document the Approach A walk-order PDA picking UX (batch card rules vs non-batch exception, duplicate scan guard).
- Document the strict FIFO deviation warning modal (`Stock Entry.remarks` & `KTA Line Replenishment Order.remarks` audit trail).
- Document `Stock Manager`-only item skipping, all-skipped `Cancelled` behavior (no empty Stock Entry), and automatic deficit reappearance.
- Document `manufacturing_date`-aware FIFO preservation across shelf transfers, splits, and backdated receipts.

- [x] **Step 2: Append new translation strings to `tr.csv`, `en.csv`, `de.csv`**

Collect every newly added `__("...")` string across Task 1–3 files and append unique Title Case / full-sentence entries strictly at the bottom of `erpnextkta/translations/{tr,en,de}.csv` (0 deletions, 0 duplicate keys).

- [x] **Step 3: Execute Coordinator Final Quality Gate**

Run:
1. `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench build --app erpnextkta --production`
2. `npx vitest run` (in `erpnextkta/public/pda-hub`)
3. Backend Clean-CI test suite:
   `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_service`
   `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page`
   `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer`
   `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_doctypes`
4. Ruff lint & format check:
   `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/ruff check apps/erpnextkta/erpnextkta/kta_stock/`
   `docker exec -u frappe -w /home/frappe/frappe-bench erpnext-dev-frappe-1 /home/frappe/frappe-bench/env/bin/ruff format --check apps/erpnextkta/erpnextkta/kta_stock/`
5. CSV integrity check (0 deletions, 0 duplicates) and mark spec status as Implemented.
Expected: All builds, Vitest specs, backend tests, CSV checks, and Ruff checks pass cleanly.
