# Line Replenishment Full Batch Rounding & Exact Shelf Location Design

## 1. Problem Definition & Domain Context
In KTA wire harness and shopfloor logistics:
1. **Exact Shelf / Rack Resolution:** `110 HAMMADDE - KTA` is a parent group warehouse containing over 900 physical rack/shelf warehouses (`W1A-01-01`, `W1B-04-01`, `W1E-08-02`, etc.). Assigning `110 HAMMADDE - KTA` directly as the source warehouse is insufficient for warehouse operators and invalid for ERPNext `Stock Entry` (which forbids group warehouses). The replenishment engine must pinpoint the exact shelf warehouse where the stock physically resides.
2. **No Batch / Drum Splitting (Full Package Issue):** Net requirements (e.g., 29 meters) cannot be fulfilled by cutting drums or opening sealed boxes inside raw material storage. If available batches are 15m + 15m, the warehouse issues both batches in their full quantities (15 + 15 = 30m).
3. **Zero Manual PDA Input:** Warehouse pickers using PDA barcode scanners should not manually type picked quantities. Scanning the allocated batch on the shelf must immediately confirm the full batch quantity as picked.

---

## 2. Core Architecture & Sourcing Flow

### 2.1 FIFO Multi-Batch & Shelf Allocation Algorithm
Function: `allocate_fifo_batches(item_code, parent_warehouse, required_qty)`
- **Scope:** Given an `item_code`, `parent_warehouse` (e.g. `110 HAMMADDE - KTA`), and `required_qty`:
  - Retrieves all active leaf warehouses (`is_group = 0`) under `parent_warehouse` using NestedSet bounds (`lft >= parent_lft AND rgt <= parent_rgt`).
  - Fetches positive batch balances using ERPNext's `get_batch_qty(item_code=item_code)` or `tabSerial and Batch Entry` / `tabBin`.
  - For non-batch items, fetches available positive stock directly from leaf `tabBin` records.
  - Sorts candidate batches/shelves strictly by FIFO:
    1. `expiry_date ASC` (nulls last)
    2. `creation ASC`
  - Iterates through candidate batches, accumulating full batch quantities:
    - Adds candidate batch with its `warehouse`, `batch_no`, and full `qty`.
    - Stops once `accumulated_qty >= required_qty`.
  - Returns a list of allocation dictionaries:
    ```python
    [
        {
            "item_code": "10025444",
            "warehouse": "W1A-01-01 - KTA",
            "batch_no": "0000000070",
            "allocated_qty": 15.0,
        },
        ...
    ]
    ```

### 2.2 Replenishment Order Item Decomposition
When `create_line_replenishment_order` receives a deficit item requiring multiple batches:
- Decomposes the single deficit item into discrete `KTA Line Replenishment Item` child rows, one per allocated batch/shelf:
  - `suggested_source_warehouse`: Exact shelf (e.g. `W1A-01-01 - KTA`)
  - `suggested_batch_no`: Batch ID (e.g. `0000000070`)
  - `deficit_qty`: Batch allocated quantity (e.g. `15.0`)
  - `picked_qty`: Defaults to `15.0`
  - `is_picked`: 0 (flips to 1 upon scan/confirmation)
- For non-batch items, allocates from the best shelf with sufficient stock; if multiple shelves are required, allocates whole packages or splits per shelf.

### 2.3 PDA Picking Experience
- **Page:** `Line Replenishment Picking` (`/app/line-replenishment-picking`)
- Cards clearly display:
  - **Shelf Badge:** `📍 W1A-01-01`
  - **Batch Badge:** `🏷️ 0000000070`
  - **Quantity:** `15 m`
- Barcode Scanner:
  - Scanning the batch barcode matches the exact row, marks `is_picked = 1`, and highlights the card in success green.
  - No prompt or keyboard popup asking for numeric quantity entry.

### 2.4 Atomic Material Transfer Submission
- `complete_line_replenishment_picking` compiles `Stock Entry` items directly from the child rows using their exact shelf warehouses (`W1A-01-01 - KTA`) and batch numbers.
- ERPNext validates stock availability at the leaf warehouse level and posts `Material Transfer` cleanly to target WIP line (`1501 KESMELER - KTA`).
