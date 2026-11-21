# Shopfloor Line Transfers (`Hatlar Arası Transfer`) & Pure Central Line Replenishment Plan

> **For agentic workers:** Coordinator dispatches specialist subagents (`kta-stock`, `kta-shopfloor`, `frontend-public`, `docs-i18n`) strictly respecting `.agents/subagents/*.md` folder locks.

**Goal:** Separate central raw material replenishment (`110 HAMMADDE -> 150x`) in Line Replenishment Hub/PDA from intra-shopfloor line transfers (`150x <-> 150x`) in a new 4th Shopfloor Hub tab (`Hatlar Arası Transfer`), backed by automatic LIFO batch allocation and reservation protection with explicit priority-shift override.

**Architecture:**
1. `kta_stock`: Remove `sourcing_strategy`, `sourcing_type`, and `free_stock_qty` from Line Replenishment DocTypes, order creation service, and PDA backend.
2. `kta_shopfloor`: Purify `reservation_deficit_service` to central warehouse only; build modular `line_transfer_service.py` with LIFO batch resolution, deficit-pull, idle-push, manual search, and instant `Stock Entry (Material Transfer)` execution; unify `confirmation_service.stage_confirmation_materials` and expose `work_order_service` sibling stock flags.
3. `frontend-public`: Remove sourcing strategy & source type UI from `line-replenishment-hub` / `pda`; build `Hatlar Arası Transfer` 4th tab components (<500 lines each) and integrate `MaterialStagingModal` & `WorkOrderReleasePanel`.
4. `docs-i18n`: Update portal HTML docs, developer guides, and TR/EN/DE translations.

**Spec:** `docs/superpowers/specs/2026-11-21-shopfloor-line-transfers-design.md`

---

## Tasks Checklist

- [x] **Step 1:** Write design spec and implementation plan under `docs/superpowers/`
- [x] **Step 2 (`kta-stock`):** Purify Line Replenishment DocTypes, `line_replenishment_service.py`, `line_replenishment_picking.py`, run `bench migrate`, and update/verify `kta_stock` tests
- [x] **Step 3 (`kta-shopfloor`):** Purify `reservation_deficit_service.py`, implement `line_transfer_service.py` (LIFO + reservation override), integrate `confirmation_service.py` / `work_order_service.py` / `api.py`, and add/verify tests
- [x] **Step 4 (`frontend-public`):** Clean up `line-replenishment-hub` & `pda`, implement 4th tab `Hatlar Arası Transfer` components (`<500` lines each), integrate `MaterialStagingModal` & `WorkOrderReleasePanel`
- [x] **Step 5 (`docs-i18n`):** Update `translations/{tr,en,de}.csv`, `erpnextkta/www/docs/{line_replenishment,shopfloor-hub}.html`, and `docs/*.md`
- [x] **Step 6 (Coordinator Final Gate):** Run `bench migrate`, `bench build --app erpnextkta --production`, full targeted test suite, `ruff check` & `ruff format --check`, Vue line count verification, and clean Conventional Commits (`<= 100` chars/line)
