# Line Replenishment Draft Deduplication & Zero-Stock Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deduplicate replenishment demand against in-flight Draft replenishment orders and enforce hard selection locks on zero-stock items.

**Architecture:** Extend `reservation_deficit_service.py` to query active Draft replenishment orders for the target WIP warehouse, deduct in-flight quantities from gross deficits, and compute net replenishable deltas. Update `line_replenishment_hub.js` and CSS to disable checkboxes for fully covered or zero-stock items, preventing duplicate orders or phantom picking requests.

**Tech Stack:** Frappe v15, ERPNext Stock, MariaDB, Python 3.12, Vanilla JS / Desk Pages, pytest / Frappe test runner.

**Spec:** [Draft Deduplication & Zero-Stock Lock Design Spec](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/superpowers/specs/2026-11-20-line-replenishment-draft-dedup-zero-stock-lock-design.md)

## Global Constraints
- Target branch is `main` (current working branch `feat-partial-job-card-submit`).
- Coordinator does not edit source files directly; dispatch specialist subagents (`kta-shopfloor`, `kta-stock`, `docs-i18n`).
- Commit messages follow Conventional Commits and every line is strictly <= 100 characters.
- Zero commercial confidential supplier/customer names or unit prices.
- Build command: `bench build --app erpnextkta --production`.

---

## Tasks

### Task 1: In-Flight Draft Order Net Delta & Deduplication Engine
**Subagent:** `kta-shopfloor`
**Files to Modify/Create:**
- `erpnextkta/kta_shopfloor/services/reservation_deficit_service.py`
- `erpnextkta/kta_shopfloor/tests/test_reservation_deficit_service.py`

- [ ] Write failing unit tests in `test_reservation_deficit_service.py`:
  - `test_draft_order_fully_covers_deficit_dedup`: Gross deficit 195, Draft order has 195/200 -> net deficit 0, `covered_by_draft=True`, `selectable=False`.
  - `test_draft_order_partially_covers_deficit_delta`: Gross deficit 250, Draft order has 200 -> net deficit 50, only 50 is sent for FIFO batch allocation.
- [ ] In `reservation_deficit_service.py`:
  - Query all open Draft orders for `target_warehouse`:
    `SELECT parent, item_code, SUM(deficit_qty) as draft_qty FROM tabKTA Line Replenishment Item WHERE docstatus = 0 GROUP BY parent, item_code`.
  - For each deficit item, calculate $Q_{\text{draft}} = \sum \text{draft\_qty}$.
  - Compute $D_{\text{net}} = \max(0, D_{\text{gross}} - Q_{\text{draft}})$.
  - Set `draft_covered_qty`, `draft_orders`, `covered_by_draft` flag, and adjust `deficit_qty = D_net`.
  - Set `selectable = True` only if $D_{\text{net}} > 0$ and `has_stock == True`; otherwise `selectable = False`.
- [ ] Run test suite `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_shopfloor.tests.test_reservation_deficit_service` and verify passing.
- [ ] Lint and format with ruff.
- [ ] Commit with message `feat(shopfloor): deduct in-flight draft replenishment orders from line deficits`.

### Task 2: Desktop Hub Hard Selection Locks & Badges
**Subagent:** `kta-shopfloor`
**Files to Modify/Create:**
- `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.js`
- `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.css`
- `erpnextkta/kta_shopfloor/tests/test_line_replenishment_hub_page.py`

- [ ] In `line_replenishment_hub.js`:
  - Map `covered_by_draft`, `draft_orders`, `draft_covered_qty`, and `selectable` to item state.
  - Disable row checkbox if `selectable === false` (`<input type="checkbox" disabled ...>`).
  - Update "Select All" (`.select-all-checkbox`) to toggle only rows where `item.selectable !== false`.
  - Render dedicated badge for draft-covered items:
    `<span class="badge-draft-covered">⏳ Taslak İkmalde: ${item.draft_orders.join(', ')} (${item.draft_covered_qty} ${item.uom})</span>`.
  - Render dedicated badge for out-of-stock items:
    `<span class="badge-no-stock">🚫 Depoda Stok Yok (Seçilemez)</span>`.
  - In `create_replenishment_order`, filter out any item where `selectable === false` or `has_stock === false`.
- [ ] In `line_replenishment_hub.css`:
  - Add styles for `.badge-draft-covered` and disabled checkboxes (`cursor: not-allowed; opacity: 0.5`).
- [ ] Update `test_line_replenishment_hub_page.py` to assert presence of draft-covered badges and selection locks.
- [ ] Run test suite `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_shopfloor.tests.test_line_replenishment_hub_page` and verify passing.
- [ ] Lint and format with ruff.
- [ ] Commit with message `feat(shopfloor): enforce hard selection locks on zero-stock and draft-covered items`.

### Task 3: Backend Order Creation Guard for Zero-Stock Items
**Subagent:** `kta-stock`
**Files to Modify/Create:**
- `erpnextkta/kta_stock/line_replenishment_service.py`
- `erpnextkta/kta_stock/tests/test_line_replenishment_service.py`

- [ ] In `create_line_replenishment_order`:
  - Verify that submitted items must have available stock; reject items where both central warehouse shelves and sibling lines have 0 available stock if no batch was allocatable.
- [ ] Write unit test in `test_line_replenishment_service.py` verifying zero-stock item rejection guard.
- [ ] Run test suite `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_stock.tests.test_line_replenishment_service` and verify passing.
- [ ] Lint and format with ruff.
- [ ] Commit with message `feat(stock): add backend validation guard rejecting zero-stock replenishment items`.

### Task 4: Documentation & Translations Sync
**Subagent:** `docs-i18n`
**Files to Modify/Create:**
- `erpnextkta/translations/tr.csv`, `en.csv`, `de.csv`
- `erpnextkta/www/docs/line_replenishment.html`
- `docs/developer_guides/line_replenishment_guide.md`

- [ ] Add translation keys for draft coverage and selection locks (`Taslak İkmalde`, `Covered by Draft`, `In Entwurfsauftrag abgedeckt`, `Depoda Stok Yok (Seçilemez)`).
- [ ] Document in-flight draft deduplication formulas ($D_{\text{net}} = D_{\text{gross}} - Q_{\text{draft}}$) and zero-stock hard lock in portal docs and developer guide.
- [ ] Commit with message `docs(i18n): document in-flight draft deduplication and zero-stock lock rules`.

### Task 5: Coordinator Final Quality Gate
**Coordinator:**
- [ ] Run `bench build --app erpnextkta --production`.
- [ ] Run full test suites across `kta_stock` and `kta_shopfloor`.
- [ ] Run `ruff check` and `ruff format --check` across all touched python files.
- [ ] Verify clean git status and commit history with line length <= 100.
