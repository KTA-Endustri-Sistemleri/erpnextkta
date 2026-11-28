# Line Replenishment Draft Deduplication & Zero-Stock Lock Design

## 1. Problem Definition & Objectives
1. **In-Flight Draft Order Deduplication & Net Delta Calculation:**
   When generating replenishment lists for a target production line (e.g. `1502 JK - KTA`), planners may scan deficits repeatedly. If an open `Draft` replenishment order already exists for that line:
   - Re-requesting the same material leads to duplicate physical picks and inventory clutter on the line.
   - If requirement increases slightly (e.g., from 195 to 196), but the draft order already allocated a full rounded batch of 200 units, the in-flight draft batch satisfies the new requirement; no new replenishment should be triggered.
   - If requirement increases significantly beyond the draft order (e.g., from 195 to 250 with 200 in draft), only the uncovered delta (50 units) should be replenished.
2. **Hard Prevention of Zero-Stock Materials:**
   When an item cannot be sourced from sibling lines (no free stock) and has zero stock across all central warehouse shelves (`has_stock == False`), it must be strictly locked in the UI (disabled checkbox, cannot be selected even via "Select All") and blocked in the backend order creation API.

---

## 2. Mathematical Model & Algorithm

### 2.1 Net Deficit Delta Calculation
For target WIP warehouse $W_{\text{target}}$ and item $I$:
1. **Gross Reservation Deficit:**
   $$D_{\text{gross}} = \max(0, R_{\text{line}} - A_{\text{line}})$$
   where $R_{\text{line}}$ is `tabBin.reserved_qty_for_production` and $A_{\text{line}}$ is `tabBin.actual_qty`.
2. **In-Flight Draft Quantity:**
   $$Q_{\text{draft}} = \sum_{\text{order} \in \text{DraftOrders}(W_{\text{target}})} \text{row.deficit\_qty}$$
   Query: Sum `deficit_qty` from `tabKTA Line Replenishment Item` joined with `tabKTA Line Replenishment Order` where `target_warehouse = W_target` and `docstatus = 0` and `status = 'Draft'`. Also tracks list of draft order IDs (e.g. `["LRO-2026-00001"]`).
3. **Net Replenishable Deficit:**
   $$D_{\text{net}} = \max(0, D_{\text{gross}} - Q_{\text{draft}})$$
4. **Behavior by Deficit Delta:**
   - If $D_{\text{gross}} > 0$ and $D_{\text{net}} == 0$:
     Item is completely covered by draft orders.
     - `covered_by_draft = True`
     - `draft_orders = ["LRO-2026-00001"]`
     - `deficit_qty = 0.0`
     - `selectable = False`
     - Badge: `⏳ Taslak İkmalde: LRO-2026-00001 (200 Adet Bekliyor)`
   - If $D_{\text{gross}} > 0$ and $D_{\text{net}} > 0$:
     Item has uncovered remaining demand.
     - `covered_by_draft = False`
     - `draft_covered_qty = Q_draft`
     - `deficit_qty = D_net` (only uncoverable delta is sent to batch allocation)
     - Sourcing and FIFO allocation runs for $D_{\text{net}}$.

### 2.2 Hard Lock on Zero-Stock Items
For any item where $D_{\text{net}} > 0$:
- If FIFO batch allocation yields no stock (`has_stock == False`):
  - `selectable = False`
  - In `line_replenishment_hub.js`: Checkbox element is rendered with `disabled` attribute and `data-selectable="false"`.
  - "Select All" (`.select-all-checkbox`) explicitly filters out items where `selectable === false`.
  - In `line_replenishment_service.py` (`create_line_replenishment_order`): Validates that submitted items must have available stock or throws a validation error if all items have 0 stock.

---

## 3. UI / UX Specifications

### 3.1 Deficit Table Display
- **Status / Action Column:**
  - When `covered_by_draft === true`:
    `<span class="badge-draft-covered">⏳ Taslak İkmalde: ${item.draft_order_names} (${item.draft_qty} ${item.uom})</span>`
    Checkbox: `<input type="checkbox" disabled class="row-select-checkbox disabled">`
  - When `has_stock === false`:
    `<span class="badge-no-stock">🚫 Depoda Stok Yok</span>`
    Checkbox: `<input type="checkbox" disabled class="row-select-checkbox disabled">`
  - When `selectable === true`:
    Standard active checkbox, pre-selected.
