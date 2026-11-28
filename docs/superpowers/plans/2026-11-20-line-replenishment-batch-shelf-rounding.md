# Line Replenishment Full Batch Rounding & Exact Shelf Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement FIFO multi-batch shelf allocation, whole-batch rounding without splitting, and exact shelf (rack) warehouse resolution in Line Replenishment.

**Architecture:** Extend backend replenishment services to resolve physical leaf warehouses (shelves) under central warehouse trees and accumulate discrete full batches until net requirement is satisfied. Update order generation, PDA picking, desktop hub, and Stock Entry creation to operate on exact shelf warehouses and full batch quantities without requiring manual quantity entry.

**Tech Stack:** Frappe v15, ERPNext Stock, MariaDB NestedSet, Python 3.12, Vanilla JS / Desk Pages, pytest / Frappe test runner.

**Spec:** [Line Replenishment Full Batch Rounding & Exact Shelf Design](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/superpowers/specs/2026-11-20-line-replenishment-batch-shelf-rounding-design.md)

## Global Constraints
- Target branch is `main` (current dev branch `feat-partial-job-card-submit`).
- Coordinator does not edit source files directly; dispatch specialist subagents (`kta-stock`, `kta-shopfloor`, `docs-i18n`).
- Commit messages follow Conventional Commits and every line is strictly <= 100 characters.
- Zero commercial confidential supplier or customer names and prices.
- Build command: `bench build --app erpnextkta --production`.

---

## Tasks

### Task 1: Backend FIFO Multi-Batch & Exact Shelf Allocation Engine
**Subagent:** `kta-stock`
**Files to Modify/Create:**
- `erpnextkta/kta_stock/line_replenishment_service.py`
- `erpnextkta/kta_stock/tests/test_line_replenishment_service.py`

- [ ] Write failing unit test `test_allocate_fifo_batches_exact_shelves_and_whole_quantities` in `test_line_replenishment_service.py`.
- [ ] Implement `allocate_fifo_batches(item_code, parent_warehouse, required_qty)` in `line_replenishment_service.py` to traverse child leaf warehouses under parent warehouse and return full batches in FIFO order until `accumulated_qty >= required_qty`.
- [ ] Update `create_line_replenishment_order` to decompose deficit items into discrete child rows per allocated batch/shelf.
- [ ] Ensure non-batch items resolve to the leaf shelf warehouse with the highest positive balance.
- [ ] Run test suite `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_stock.tests.test_line_replenishment_service` and verify passing.
- [ ] Lint and format files with ruff.
- [ ] Commit with message `feat(stock): implement FIFO multi-batch shelf allocation and full batch rounding`.

### Task 2: Picking Completion & Atomic Stock Entry with Leaf Warehouses
**Subagent:** `kta-stock`
**Files to Modify/Create:**
- `erpnextkta/kta_stock/line_replenishment_service.py`
- `erpnextkta/kta_stock/tests/test_line_replenishment_transfer.py`

- [ ] Write failing unit test in `test_line_replenishment_transfer.py` verifying that picking full rounded batches creates `Stock Entry` from exact leaf warehouses without failing on over-picking tolerance.
- [ ] Update `complete_line_replenishment_picking` to allow full rounded batch quantities without triggering artificial 15% tolerance limits when items were pre-allocated by the engine.
- [ ] Verify `Material Transfer` items correctly pull from leaf warehouses (`s_warehouse`) to target WIP warehouse (`t_warehouse`).
- [ ] Run test suite `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer` and verify passing.
- [ ] Lint and format files with ruff.
- [ ] Commit with message `feat(stock): execute material transfer from exact shelf warehouses with full batch quantities`.

### Task 3: PDA Mobile Interface & Zero Manual Input Picking
**Subagent:** `kta-stock`
**Files to Modify/Create:**
- `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.js`
- `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.css`
- `erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py`

- [ ] Update PDA card templates to prominently display shelf location badge (`📍 Raf: W1A-01-01`), batch badge (`🏷️ Parti: 0000000070`), and quantity (`📦 Miktar: 15 m`).
- [ ] Update barcode scanning logic: scanning the batch number automatically confirms the row with its full quantity without popping up keyboard/dialog.
- [ ] Add visual feedback for auto-confirmed full batches.
- [ ] Run test suite `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page` and verify passing.
- [ ] Commit with message `feat(stock): update PDA picking interface with prominent shelf badges and instant scan confirmation`.

### Task 4: Desktop Line Replenishment Hub Shelf Visibility
**Subagent:** `kta-shopfloor`
**Files to Modify/Create:**
- `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.js`
- `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.css`
- `erpnextkta/kta_shopfloor/tests/test_line_replenishment_hub_page.py`

- [ ] Update deficit table rendering in `Line Replenishment Hub` to display allocated shelf location badges and batch details under each item row.
- [ ] When order is generated, show the split batches and exact shelves in the confirmation modal.
- [ ] Run test suite `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_shopfloor.tests.test_line_replenishment_hub_page` and verify passing.
- [ ] Commit with message `feat(shopfloor): display exact shelf locations and allocated batches in Line Replenishment Hub`.

### Task 5: Documentation & Translations Sync
**Subagent:** `docs-i18n`
**Files to Modify/Create:**
- `erpnextkta/translations/tr.csv`, `en.csv`, `de.csv`
- `erpnextkta/www/docs/line_replenishment.html`
- `docs/developer_guides/line_replenishment_guide.md`

- [ ] Add new UI translation keys for shelf location (`Raf Lokasyonu`, `Shelf Location`, `Regalplatz`) and full batch issue (`Tam Koli Çıkışı`, `Full Batch Issue`, `Komplette Chargenausgabe`).
- [ ] Update portal documentation `/docs/line_replenishment` with exact shelf navigation and no-split picking policy.
- [ ] Update developer guide `docs/developer_guides/line_replenishment_guide.md`.
- [ ] Commit with message `docs(i18n): document full batch picking and exact shelf location mechanics`.

### Task 6: Coordinator Quality Gate
**Coordinator:**
- [ ] Run full test suites across affected modules (`kta_stock`, `kta_shopfloor`).
- [ ] Run `bench build --app erpnextkta --production`.
- [ ] Run `ruff check` and `ruff format --check` on all modified python files.
- [ ] Verify clean git status and commit history.
