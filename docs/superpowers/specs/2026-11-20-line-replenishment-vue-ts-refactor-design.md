# Design: Line Replenishment Vue 3 + TypeScript Refactor (Desktop Hub & PDA)

- **Date:** 2026-11-20
- **Author:** Coordinator (Tech Lead)
- **Status:** Approved / In Review
- **Target App:** `erpnextkta`
- **Scope:** `erpnextkta/public/line-replenishment-hub/**`, `erpnextkta/public/line-replenishment-pda/**`, `erpnextkta/kta_shopfloor/page/line_replenishment_hub/**`, `erpnextkta/kta_stock/page/line_replenishment_picking/**`, `erpnextkta/translations/**`, `docs/**`

---

## 1. Intent & Context

Line Replenishment (Hat İkmal / SAP LP12) allows warehouse operators and production planners to identify open material deficits on production lines (1501, 1502, 1503, 1504, 1509), calculate FIFO shelf allocations from central storage (`110 HAMMADDE`) or secondary lines, generate staging orders (`KTA Line Replenishment Order`), and execute picking via barcode terminals (PDA).

Currently, both the Desktop Hub (`line-replenishment-hub`) and PDA Picking (`line-replenishment-picking`) pages are implemented using vanilla jQuery and HTML string interpolation. This has caused:
1. Fragmented user experience with duplicate controls (redundant warehouse selectors, refresh buttons, and action buttons scattered across header, filter bar, and table).
2. Hardcoded Turkish strings bypassing Frappe's translation pipeline (`__`), breaking multilingual consistency across TR, EN, and DE.
3. Deficit table responsiveness issues on medium screens and omission of the critical "Depodan Çıkacak Miktar" (Issue / Pick Qty) column.
4. "Hat İkmal Emri Oluştur" (Create Replenishment Order) button floating at the top and remaining visible even when no materials are loaded.
5. Legacy vanilla JS in PDA picking with poor touch ergonomics.

This refactor modernizes both pages into Vue 3 + TypeScript SPAs under `erpnextkta/public/`, harmonized with the Shopfloor Hub layout and design language.

---

## 2. Goals, Non-Goals & Anti-Goals

### Goals
- **Shopfloor Hub Parity:** Adopt the full-bleed, sticky header, card-based layout proven in `erpnextkta/public/shopfloor-hub`.
- **Eliminate Duplicate Controls:** Consolidate redundant warehouse pickers and action buttons into a single clean workspace toolbar.
- **Table Responsiveness & Data Clarity:** Display "Depodan Çıkacak Miktar" (`available_stock`) alongside "Net Açık" (`deficit_qty`), "Mevcut Hat Stoğu" (`line_stock_qty`), and "Kaynak Depo / Raf", styled responsively with zero overflow clipping.
- **Conditional Order Button:** Place the "Hat İkmal Emri Oluştur" button directly underneath the deficits table; keep it hidden until actionable materials are returned.
- **Mobile/PDA Touch Ergonomics:** Build a clean mobile-first Vue 3 + TS interface for PDA barcode scanning with large touch targets, real-time pick progress, audio beeps, and shelf highlighting.
- **Full Multilingual i18n:** Wrap all static strings with `__("...")` in Vue templates and add missing mappings to `tr.csv`, `en.csv`, and `de.csv`.

### Non-Goals
- Modifying backend reservation logic or allocation algorithms (`line_replenishment_service.py` remains the single source of truth for stock calculations).
- Changing the schema of `KTA Line Replenishment Order` or `KTA Line Replenishment Item` DocTypes.

### Anti-Goals
- Monolithic code combining Desktop Hub and PDA into a single heavyweight bundle (operators on low-power PDAs must not load desktop data grids).
- Breaking Frappe Desk routing (`/app/line-replenishment-hub` and `/app/line-replenishment-picking` routes must remain identical).

---

## 3. Approaches Considered & Trade-offs

### Option A: Two Independent Bundles (`line-replenishment-hub.bundle.js` & `line-replenishment-pda.bundle.js`) [CHOSEN]
- **Structure:**
  - `erpnextkta/public/line-replenishment-hub/` (Desktop Hub SPA)
  - `erpnextkta/public/line-replenishment-pda/` (Mobile PDA SPA)
  - Page wrappers in `kta_shopfloor` and `kta_stock` act as thin loaders mounting the respective Vue apps.
- **Pros:**
  - Optimum bundle size: PDA operators load zero desktop grid overhead, ensuring fast startup on rugged handheld scanners.
  - Matches the established pattern of `shopfloor-hub.bundle.js`.
  - Independent lifecycle and testing.
- **Cons:** Shared utilities (e.g. status badge colors) must either be in a shared types file or symlinked/re-exported.
- **User Decision:** The user explicitly selected **Option A**.

---

## 4. Backend Contracts & Field Mappings

### 4.1 RPC Methods & Field Resolution
- **Deficits API:** `erpnextkta.kta_shopfloor.page.line_replenishment_hub.line_replenishment_hub.get_warehouse_reservation_deficits`
  - Returns rows with:
    - `item_code`: Item Code
    - `item_name`: Item Name
    - `deficit_qty`: Total net shortage on the line (Net Açık)
    - `line_stock_qty`: Stock currently on the line (Hat Stoğu)
    - `available_stock`: **Depodan Çıkacak Miktar** (allocated pick quantity from batches in source warehouse)
    - `suggested_source_warehouse`: Shelf / Source warehouse (e.g. `W1A-01-01 - KTA` or `110 HAMMADDE - KTA`)
    - `source_strategy`: `"Direct Central Store"` or `"Line Transfer"`
    - `has_stock`: Boolean indicating if source has stock
    - `in_flight_draft_orders`: List of open draft replenishment order IDs
- **Create Order RPC:** `erpnextkta.kta_stock.line_replenishment_service.create_line_replenishment_order`
  - Parameters: `target_warehouse`, `items` (JSON list of selected item dicts)
- **PDA Open Orders RPC:** `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_open_replenishment_orders`
- **PDA Order Details RPC:** `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.get_replenishment_order_details`
- **PDA Complete Picking RPC:** `erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking.complete_line_replenishment_picking`
  - Parameters: `order_name`, `picked_items` (JSON list with `item_code`, `picked_qty`, `batch_no`, `shelf_location`)

### 4.2 Status Badge Rules (`Durum Rozeti`)
- **Taslak İkmalde (Draft In-Flight):** If `row.in_flight_draft_orders && row.in_flight_draft_orders.length > 0`
  - Badge: Blue/Gray `⏳ Taslak İkmalde (LRO-...)`, Row checkbox disabled.
- **Tam Hazır (Ready):** If `row.has_stock && row.available_stock >= row.deficit_qty`
  - Badge: Green `🟢 Hazır`, Row checkbox enabled.
- **Kısmi Stok (Partial):** If `row.has_stock && row.available_stock > 0 && row.available_stock < row.deficit_qty`
  - Badge: Yellow `🟡 Kısmi Stok (${row.available_stock}/${row.deficit_qty})`, Row checkbox enabled.
- **Stok Yok (Zero Stock):** If `!row.has_stock || row.available_stock <= 0`
  - Badge: Red `🔴 Stok Yok`, Row checkbox disabled.

---

## 5. Detailed Component Architecture

### 5.1 Desktop Hub (`erpnextkta/public/line-replenishment-hub/`)
- **Bundle File:** `line-replenishment-hub.bundle.js`
- **App Structure:**
  - `App.vue`: Main state orchestrator (target warehouse, sourcing strategy, deficits list, selected rows, loading state).
  - `WorkspaceHeader.vue`: Sticky top bar:
    - Title: `Line Replenishment Hub` / `Hat İkmal Merkezi`
    - Quick Line Selector Pills (`1501 KESMELER`, `1502 JK`, `1503 RATIONAL`, `1504 ARCELIK`, `1509 BOSCH`)
    - Custom Warehouse Selector Link
    - Strategy Radio/Select: `Smart Sourcing (WIP First)` vs `Direct Central Store`
    - Refresh Action
  - `DeficitTable.vue`:
    - Responsive data table with sticky header.
    - Checkbox selection column (disabled for zero-stock & in-flight draft rows).
    - Columns:
      1. `Hammadde Kodu & Adı` (with copy pill)
      2. `Net Açık (Deficit)`
      3. `Hat Stoğu`
      4. **`Depodan Çıkacak Miktar`** (highlighted bold column: `available_stock`)
      5. `Kaynak Depo / Raf` (pill badge)
      6. `Kaynak Tipi` (Line Transfer vs Central Store)
      7. `Durum` (Hazır / Kısmi / Stok Yok / Taslak İkmalde)
  - `ActionBar.vue`: Positioned **directly UNDER** the table:
    - Only rendered when `deficits.length > 0`.
    - Displays: `X hammadde seçildi, toplam Y adet aktarılacak`.
    - Primary Button: `Hat İkmal Emri Oluştur`.
    - On success: Displays modern Frappe dialog with link to created Order and refreshes deficits list in-place.

### 5.2 PDA Picking (`erpnextkta/public/line-replenishment-pda/`)
- **Bundle File:** `line-replenishment-pda.bundle.js`
- **App Structure:**
  - `PdaApp.vue`: Mobile-first shell for handheld barcode terminals.
  - `OrderSelector.vue`: Quick card selector for open `KTA Line Replenishment Order` documents (with search filter).
  - `BarcodeScannerBar.vue`:
    - Auto-focused barcode input supporting physical wedge scanners and manual entry.
    - Decodes Item Code, `KTA Stock Label` barcode, or Shelf Barcode.
    - Audio feedback (`play_beep` on success/error).
  - `PickingItemCard.vue`:
    - Card per item with high-contrast **Shelf Location Badge** (e.g., `W1A-01-01`).
    - Required vs Picked quantity progress bar.
    - Touch buttons: `+1`, `-1`, and `Tümünü Al` (Pick All).
    - Tolerance guard: Enforces +15% over-pick limit.
  - `TransferFooter.vue`:
    - Sticky bottom action bar.
    - `Transferi Tamamla` button (enabled once picking requirements are satisfied).
    - Submits transfer and displays confirmation receipt modal.

---

## 6. Page Loaders & Desk Registration
- `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.js`:
  Mounted via `frappe.require("line-replenishment-hub.bundle.js")` and `frappe.ui.setup_line_replenishment_hub_vue($parent)`.
- `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.js`:
  Mounted via `frappe.require("line-replenishment-pda.bundle.js")` and `frappe.ui.setup_line_replenishment_pda_vue($parent)`.
- Legacy standalone CSS files are safely retired; all styles are scoped inside Vue SFCs with Tailwind / Frappe Desk theme variables.

---

## 7. Multilingual & i18n Dictionary
All user-facing strings registered across `tr.csv`, `en.csv`, and `de.csv`:
- `Hat İkmal Merkezi` / `Line Replenishment Hub` / `Liniennachschub-Hub`
- `Depodan Çıkacak Miktar` / `Quantity to Issue` / `Ausgabemenge`
- `Hat İkmal Emri Oluştur` / `Create Replenishment Order` / `Nachschubauftrag Erstellen`
- `Kaynak Depo / Raf` / `Source Warehouse / Shelf` / `Quelllager / Regal`
- `Aktif İkmal Siparişi` / `Active Replenishment Order` / `Aktiver Nachschubauftrag`
- `Transferi Tamamla` / `Complete Transfer` / `Transfer Abschließen`
- `Tümünü Al` / `Pick All` / `Alles Entnehmen`
- `Taslak İkmalde` / `In Draft Replenishment` / `Im Nachschubentwurf`

---

## 8. Verification & Quality Gates
1. **Frontend Production Build:** `bench build --app erpnextkta --production` passes with 0 errors.
2. **Page Registration Tests:**
   - `test_line_replenishment_hub_page.py`
   - `test_line_replenishment_picking_page.py`
   Updated to verify Vue mount and bundle loading.
3. **Backend Stock Tests:**
   - `bench --site kta.local run-tests --app erpnextkta --doctype "KTA Line Replenishment Order"`
   - `bench --site kta.local run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_service`
4. **Code Quality:** Ruff check and format pass.
