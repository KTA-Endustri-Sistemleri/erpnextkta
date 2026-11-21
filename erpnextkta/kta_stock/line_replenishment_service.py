# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json

import frappe
from frappe import _
from frappe.utils import flt


def get_leaf_warehouses(parent_warehouse: str | None) -> list[str]:
    """Return all leaf warehouses (is_group = 0) under the given warehouse or tree."""
    if not parent_warehouse:
        return []

    wh_doc = frappe.db.get_value(
        "Warehouse",
        parent_warehouse,
        ["name", "is_group", "lft", "rgt"],
        as_dict=True,
    )
    if not wh_doc:
        return (
            [parent_warehouse]
            if frappe.db.exists("Warehouse", parent_warehouse)
            else []
        )

    if not wh_doc.is_group:
        return [wh_doc.name]

    leaf_warehouses = frappe.get_all(
        "Warehouse",
        filters={
            "lft": [">=", wh_doc.lft],
            "rgt": ["<=", wh_doc.rgt],
            "is_group": 0,
        },
        pluck="name",
        order_by="name asc",
    )
    if not leaf_warehouses:
        leaf_warehouses = frappe.get_all(
            "Warehouse",
            filters={
                "parent_warehouse": wh_doc.name,
                "is_group": 0,
            },
            pluck="name",
            order_by="name asc",
        )
    return leaf_warehouses


@frappe.whitelist()
def allocate_fifo_batches(
    item_code: str | None = None,
    parent_warehouse: str | None = None,
    required_qty: float = 0.0,
    target_warehouse: str | None = None,
) -> list[dict]:
    """Allocate full FIFO batches from leaf warehouses under parent_warehouse.

    Finds leaf warehouses (is_group = 0) under parent_warehouse.
    Excludes target_warehouse from candidates to prevent self-replenishment.
    For batch-tracked items:
      - Fetches available batches with positive balance in leaf warehouses.
      - Sorts batches strictly by FIFO: (expiry_date is None, expiry_date, creation).
      - Allocates entire batches (no splitting) until accumulated_qty >= required_qty.
    For non-batch items:
      - Allocates from leaf shelves with positive stock until accumulated_qty >= required_qty.
    Returns:
      list of {"warehouse": str, "batch_no": str | None, "allocated_qty": float}
    """
    if not item_code or not parent_warehouse:
        return []

    req_qty = flt(required_qty or 0)
    if req_qty <= 0:
        return []

    leaf_warehouses = get_leaf_warehouses(parent_warehouse)
    if target_warehouse:
        leaf_warehouses = [w for w in leaf_warehouses if w != target_warehouse]
    if not leaf_warehouses:
        return []

    parent_is_group = bool(
        frappe.db.get_value("Warehouse", parent_warehouse, "is_group")
    )
    fallback_leaf = leaf_warehouses[0]
    search_warehouses = list(set(leaf_warehouses + [parent_warehouse]))
    if target_warehouse:
        search_warehouses = [w for w in search_warehouses if w != target_warehouse]

    has_batch = frappe.db.get_value("Item", item_code, "has_batch_no")

    if not has_batch:
        bins = frappe.get_all(
            "Bin",
            filters={
                "item_code": item_code,
                "warehouse": ["in", search_warehouses],
                "actual_qty": [">", 0],
            },
            fields=["warehouse", "actual_qty"],
            order_by="actual_qty desc, warehouse asc",
        )
        if not bins:
            sle_stock = frappe.db.sql(
                """
                SELECT warehouse, SUM(actual_qty) AS actual_qty
                FROM `tabStock Ledger Entry`
                WHERE item_code = %(item_code)s
                  AND warehouse IN %(warehouses)s
                  AND is_cancelled = 0
                GROUP BY warehouse
                HAVING SUM(actual_qty) > 0
                ORDER BY actual_qty DESC, warehouse ASC
                """,
                {"item_code": item_code, "warehouses": tuple(search_warehouses)},
                as_dict=True,
            )
            bins = sle_stock

        allocated = []
        accumulated_qty = 0.0
        for b in bins:
            shelf_wh = b.get("warehouse")
            if shelf_wh == parent_warehouse and parent_is_group:
                shelf_wh = fallback_leaf
            avail = flt(b.get("actual_qty") or 0)
            if avail <= 0:
                continue
            needed = req_qty - accumulated_qty
            take_qty = min(avail, needed)
            allocated.append(
                {
                    "warehouse": shelf_wh,
                    "batch_no": None,
                    "allocated_qty": take_qty,
                }
            )
            accumulated_qty += take_qty
            if accumulated_qty >= req_qty:
                break
        return allocated

    available_batches: dict[tuple[str, str], float] = {}

    # 1. Primary lookup: Direct high-performance query on Stock Ledger Entry + Serial and Batch Entry
    candidate_warehouses = tuple(search_warehouses)
    pos_bins = frappe.db.sql(
        """
        SELECT warehouse FROM `tabBin`
        WHERE item_code = %s AND warehouse IN %s AND actual_qty > 0
        """,
        (item_code, tuple(search_warehouses)),
        pluck=True,
    )
    if pos_bins:
        candidate_warehouses = tuple(pos_bins)

    sle_batches = frappe.db.sql(
        """
        SELECT warehouse, batch_no, SUM(qty) AS qty
        FROM (
            SELECT sle.warehouse, sle.batch_no, sle.actual_qty AS qty
            FROM `tabStock Ledger Entry` sle
            WHERE sle.item_code = %(item_code)s
              AND sle.warehouse IN %(warehouses)s
              AND sle.is_cancelled = 0
              AND sle.batch_no IS NOT NULL
              AND sle.batch_no != ''
              AND (sle.serial_and_batch_bundle IS NULL OR sle.serial_and_batch_bundle = '')

            UNION ALL

            SELECT COALESCE(sbe.warehouse, sle.warehouse) AS warehouse,
                   sbe.batch_no,
                   sbe.qty AS qty
            FROM `tabStock Ledger Entry` sle
            JOIN `tabSerial and Batch Entry` sbe ON sbe.parent = sle.serial_and_batch_bundle
            WHERE sle.item_code = %(item_code)s
              AND sle.warehouse IN %(warehouses)s
              AND sle.is_cancelled = 0
              AND sbe.batch_no IS NOT NULL
              AND sbe.batch_no != ''
        ) AS combined
        GROUP BY warehouse, batch_no
        HAVING SUM(qty) > 0
        """,
        {"item_code": item_code, "warehouses": candidate_warehouses},
        as_dict=True,
    )
    for sb in sle_batches:
        wh = sb.warehouse
        if wh in search_warehouses:
            if wh == parent_warehouse and parent_is_group:
                wh = fallback_leaf
            key = (wh, sb.batch_no)
            available_batches[key] = flt(sb.qty)

    # 2. Fallback: Standard ERPNext batch balance query if needed
    if not available_batches:
        try:
            from erpnext.stock.doctype.batch.batch import get_batch_qty

            raw_batches = get_batch_qty(item_code=item_code) or []
            for b in raw_batches:
                wh = b.get("warehouse")
                b_no = b.get("batch_no")
                qty = flt(b.get("qty") or 0)
                if wh and wh in search_warehouses and b_no and qty > 0:
                    if wh == parent_warehouse and parent_is_group:
                        wh = fallback_leaf
                    key = (wh, b_no)
                    available_batches[key] = available_batches.get(key, 0.0) + qty
        except Exception:  # noqa: BLE001
            available_batches = {}

    if not available_batches:
        return []

    candidate_batch_nos = list({b_no for (_, b_no) in available_batches})
    batch_records = frappe.get_all(
        "Batch",
        filters={"name": ["in", candidate_batch_nos], "disabled": 0},
        fields=["name", "expiry_date", "creation"],
    )
    batch_meta = {b.name: b for b in batch_records}

    active_candidates = []
    for (wh, b_no), qty in available_batches.items():
        if b_no in batch_meta:
            meta = batch_meta[b_no]
            active_candidates.append(
                {
                    "warehouse": wh,
                    "batch_no": b_no,
                    "qty": qty,
                    "expiry_date": meta.get("expiry_date"),
                    "creation": meta.get("creation"),
                }
            )

    if not active_candidates:
        return []

    def _fifo_sort_key(c):
        exp = c.get("expiry_date")
        created = c.get("creation")
        exp_str = str(exp) if exp else ""
        created_str = str(created) if created else ""
        return (
            exp is None,
            exp_str,
            created_str,
            c.get("batch_no") or "",
            c.get("warehouse") or "",
        )

    sorted_candidates = sorted(active_candidates, key=_fifo_sort_key)

    # Full batch accumulation without splitting
    allocated = []
    accumulated_qty = 0.0
    for cand in sorted_candidates:
        b_qty = flt(cand["qty"])
        allocated.append(
            {
                "warehouse": cand["warehouse"],
                "batch_no": cand["batch_no"],
                "allocated_qty": b_qty,
            }
        )
        accumulated_qty += b_qty
        if accumulated_qty >= req_qty:
            break

    return allocated


def bulk_allocate_fifo_batches(
    items_to_allocate: list[dict],
    target_warehouse: str | None = None,
) -> dict[str, list[dict]]:
    """Bulk allocate FIFO batches for multiple items in high-performance batch queries.

    items_to_allocate: list of {
        'item_code': str,
        'parent_warehouse': str,
        'required_qty': float
    }
    Returns: dict mapping item_code to list of {"warehouse": str, "batch_no": str | None, "allocated_qty": float}
    """
    if not items_to_allocate:
        return {}

    allocated_map: dict[str, list[dict]] = {}

    # 1. Resolve item batch properties and warehouses
    items_by_code = {item["item_code"]: item for item in items_to_allocate}
    all_item_codes = list(items_by_code.keys())

    item_has_batch = {
        d.name: bool(d.has_batch_no)
        for d in frappe.get_all(
            "Item",
            filters={"name": ["in", all_item_codes]},
            fields=["name", "has_batch_no"],
        )
    }

    # Group warehouses per parent
    parent_whs = list(
        {
            item["parent_warehouse"]
            for item in items_to_allocate
            if item.get("parent_warehouse")
        }
    )
    leaf_whs_cache: dict[str, list[str]] = {}
    search_whs_cache: dict[str, list[str]] = {}
    is_group_cache: dict[str, bool] = {}

    for p_wh in parent_whs:
        leaves = get_leaf_warehouses(p_wh)
        if target_warehouse:
            leaves = [w for w in leaves if w != target_warehouse]
        leaf_whs_cache[p_wh] = leaves

        p_is_group = bool(frappe.db.get_value("Warehouse", p_wh, "is_group"))
        is_group_cache[p_wh] = p_is_group

        s_whs = list(set(leaves + [p_wh]))
        if target_warehouse:
            s_whs = [w for w in s_whs if w != target_warehouse]
        search_whs_cache[p_wh] = s_whs

    all_candidate_whs = list(
        {wh for s_list in search_whs_cache.values() for wh in s_list}
    )

    # Separate non-batch items
    batch_item_codes = [c for c in all_item_codes if item_has_batch.get(c, False)]
    non_batch_item_codes = [
        c for c in all_item_codes if not item_has_batch.get(c, False)
    ]

    for c in non_batch_item_codes:
        item_req = items_by_code[c]
        allocated_map[c] = allocate_fifo_batches(
            item_code=c,
            parent_warehouse=item_req["parent_warehouse"],
            required_qty=item_req["required_qty"],
            target_warehouse=target_warehouse,
        )

    if not batch_item_codes or not all_candidate_whs:
        return allocated_map

    # 2. Fast bin scan to find shelves with positive stock
    positive_bins = frappe.db.sql(
        """
        SELECT item_code, warehouse, actual_qty
        FROM `tabBin`
        WHERE item_code IN %(item_codes)s
          AND warehouse IN %(warehouses)s
          AND actual_qty > 0
        """,
        {"item_codes": tuple(batch_item_codes), "warehouses": tuple(all_candidate_whs)},
        as_dict=True,
    )

    if not positive_bins:
        # No positive bins found, fall back to individual allocation
        for c in batch_item_codes:
            item_req = items_by_code[c]
            allocated_map[c] = allocate_fifo_batches(
                item_code=c,
                parent_warehouse=item_req["parent_warehouse"],
                required_qty=item_req["required_qty"],
                target_warehouse=target_warehouse,
            )
        return allocated_map

    tuple_str = ", ".join(
        [
            f"({frappe.db.escape(b.item_code)}, {frappe.db.escape(b.warehouse)})"
            for b in positive_bins
        ]
    )

    # 3. High-performance unified batch query
    batches_data = frappe.db.sql(
        f"""
        SELECT item_code, warehouse, batch_no, SUM(qty) AS qty
        FROM (
            SELECT sle.item_code, sle.warehouse, sle.batch_no, sle.actual_qty AS qty
            FROM `tabStock Ledger Entry` sle
            WHERE (sle.item_code, sle.warehouse) IN ({tuple_str})
              AND sle.is_cancelled = 0
              AND sle.batch_no IS NOT NULL
              AND sle.batch_no != ''
              AND (sle.serial_and_batch_bundle IS NULL OR sle.serial_and_batch_bundle = '')

            UNION ALL

            SELECT sle.item_code, COALESCE(sbe.warehouse, sle.warehouse) AS warehouse,
                   sbe.batch_no,
                   sbe.qty AS qty
            FROM `tabStock Ledger Entry` sle
            JOIN `tabSerial and Batch Entry` sbe ON sbe.parent = sle.serial_and_batch_bundle
            WHERE (sle.item_code, sle.warehouse) IN ({tuple_str})
              AND sle.is_cancelled = 0
              AND sbe.batch_no IS NOT NULL
              AND sbe.batch_no != ''
        ) AS combined
        GROUP BY item_code, warehouse, batch_no
        HAVING SUM(qty) > 0
        """,
        as_dict=True,
    )

    # 4. Fetch Batch metadata in bulk
    batch_nos = list({b.batch_no for b in batches_data if b.get("batch_no")})
    batch_meta = {}
    if batch_nos:
        batch_records = frappe.get_all(
            "Batch",
            filters={"name": ["in", batch_nos], "disabled": 0},
            fields=["name", "expiry_date", "creation"],
        )
        batch_meta = {b.name: b for b in batch_records}

    # 5. Group candidates per item_code and sort by FIFO
    candidates_by_item: dict[str, list[dict]] = {}
    for b in batches_data:
        i_code = b.item_code
        b_no = b.batch_no
        wh = b.warehouse
        qty = flt(b.qty)

        item_req = items_by_code.get(i_code)
        if not item_req:
            continue
        p_wh = item_req["parent_warehouse"]
        s_whs = search_whs_cache.get(p_wh, [])
        if wh not in s_whs:
            continue

        if wh == p_wh and is_group_cache.get(p_wh):
            fallback_leaves = leaf_whs_cache.get(p_wh, [])
            wh = fallback_leaves[0] if fallback_leaves else wh

        meta = batch_meta.get(b_no)
        if not meta:
            continue

        candidates_by_item.setdefault(i_code, []).append(
            {
                "warehouse": wh,
                "batch_no": b_no,
                "qty": qty,
                "expiry_date": meta.get("expiry_date"),
                "creation": meta.get("creation"),
            }
        )

    def _fifo_sort_key(c):
        exp = c.get("expiry_date")
        exp_str = str(exp) if exp else ""
        created_str = str(c.get("creation")) if c.get("creation") else ""
        return (exp is None, exp_str, created_str)

    # 6. Allocate FIFO per item
    for c in batch_item_codes:
        item_req = items_by_code[c]
        req_qty = flt(item_req["required_qty"] or 0)
        cands = candidates_by_item.get(c, [])
        cands.sort(key=_fifo_sort_key)

        allocated = []
        accumulated_qty = 0.0
        for cand in cands:
            allocated.append(
                {
                    "warehouse": cand["warehouse"],
                    "batch_no": cand["batch_no"],
                    "allocated_qty": cand["qty"],
                }
            )
            accumulated_qty += cand["qty"]
            if accumulated_qty >= req_qty:
                break
        allocated_map[c] = allocated

    return allocated_map


@frappe.whitelist()
def allocate_fifo_batch(
    item_code: str | None = None,
    warehouse: str | None = None,
    required_qty: float = 0.0,
) -> str | None:
    """Find the oldest active batch with positive balance in the given warehouse or tree.

    Sorts candidate batches by expiry_date ASC, creation ASC (FIFO).
    Returns None if the item is not batch-tracked or if no active batch has positive stock.
    """
    if not item_code or not warehouse:
        return None

    allocations = allocate_fifo_batches(
        item_code=item_code,
        parent_warehouse=warehouse,
        required_qty=required_qty or 1.0,
    )
    if allocations:
        return allocations[0].get("batch_no")
    return None


@frappe.whitelist()
def get_warehouse_leaf_stock(
    item_code: str | None = None,
    warehouse: str | None = None,
    target_warehouse: str | None = None,
) -> float:
    """Return total actual stock for item_code across leaf warehouses under warehouse."""
    if not item_code or not warehouse:
        return 0.0

    leaf_warehouses = get_leaf_warehouses(warehouse)
    if target_warehouse:
        leaf_warehouses = [w for w in leaf_warehouses if w != target_warehouse]

    search_warehouses = list(set(leaf_warehouses + [warehouse]))
    if target_warehouse:
        search_warehouses = [w for w in search_warehouses if w != target_warehouse]

    if not search_warehouses:
        return 0.0

    bin_res = frappe.db.sql(
        """
        SELECT COALESCE(SUM(actual_qty), 0)
        FROM `tabBin`
        WHERE item_code = %(item_code)s
          AND warehouse IN %(warehouses)s
        """,
        {"item_code": item_code, "warehouses": tuple(search_warehouses)},
    )
    bin_stock = flt(bin_res[0][0]) if bin_res else 0.0
    if bin_stock > 0:
        return bin_stock

    sle_res = frappe.db.sql(
        """
        SELECT COALESCE(SUM(actual_qty), 0)
        FROM `tabStock Ledger Entry`
        WHERE item_code = %(item_code)s
          AND warehouse IN %(warehouses)s
          AND is_cancelled = 0
        """,
        {"item_code": item_code, "warehouses": tuple(search_warehouses)},
    )
    sle_stock = flt(sle_res[0][0]) if sle_res else 0.0
    return max(sle_stock, 0.0)


@frappe.whitelist()
def create_line_replenishment_order(
    target_warehouse: str | None = None,
    items: list[dict] | str | None = None,
    company: str | None = None,
    **_kwargs,
) -> str:
    """Create a new KTA Line Replenishment Order in Draft status.

    Validates that target_warehouse is non-empty and not a group warehouse.
    Ensures items has at least one row with deficit_qty > 0.
    Allocates FIFO full batches per leaf shelf warehouse when available.
    Rejects items with zero stock and aborts if no items have available stock.
    """
    if not target_warehouse or not str(target_warehouse).strip():
        frappe.throw(
            _("Hedef ambar (Target Warehouse) seçimi zorunludur."),
            frappe.ValidationError,
        )

    target_wh = str(target_warehouse).strip()

    if frappe.db.exists("Warehouse", target_wh) and frappe.db.get_value(
        "Warehouse", target_wh, "is_group"
    ):
        frappe.throw(
            _("Grup ambarı hedef ambar olarak seçilemez: {0}").format(target_wh),
            frappe.ValidationError,
        )

    if isinstance(items, str):
        items = json.loads(items)

    if not items or not isinstance(items, list):
        frappe.throw(
            _("İkmal kalemleri (Items) boş olamaz."),
            frappe.ValidationError,
        )

    valid_items = [d for d in items if flt(d.get("deficit_qty") or 0) > 0]
    if not valid_items:
        frappe.throw(
            _(
                "İkmal listesinde açık miktarı (deficit_qty > 0) olan en az bir kalem bulunmalıdır."
            ),
            frappe.ValidationError,
        )

    if not company:
        company = (
            frappe.db.get_value("Warehouse", target_wh, "company")
            or frappe.defaults.get_user_default("Company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
        )

    order_items = []
    for d in valid_items:
        item_code = d.get("item_code")
        if not item_code:
            continue

        item_meta = (
            frappe.db.get_value(
                "Item",
                item_code,
                ["item_name", "stock_uom"],
                as_dict=True,
            )
            or {}
        )

        item_name = d.get("item_name") or item_meta.get("item_name") or item_code
        uom = d.get("uom") or item_meta.get("stock_uom") or ""
        deficit_qty = flt(d.get("deficit_qty") or 0)
        reserved_qty = flt(d.get("reserved_qty") or 0)
        line_actual_qty = flt(d.get("line_actual_qty") or 0)
        suggested_source_wh = d.get("suggested_source_warehouse")
        suggested_batch_no = d.get("suggested_batch_no")

        allocations = []
        if suggested_source_wh:
            allocations = allocate_fifo_batches(
                item_code=item_code,
                parent_warehouse=suggested_source_wh,
                required_qty=deficit_qty,
                target_warehouse=target_wh,
            )

        if allocations:
            for alloc in allocations:
                alloc_qty = flt(alloc.get("allocated_qty") or 0)
                order_items.append(
                    {
                        "item_code": item_code,
                        "item_name": item_name,
                        "uom": uom,
                        "reserved_qty": reserved_qty,
                        "line_actual_qty": line_actual_qty,
                        "deficit_qty": alloc_qty,
                        "picked_qty": alloc_qty,
                        "suggested_source_warehouse": alloc.get("warehouse"),
                        "suggested_batch_no": alloc.get("batch_no"),
                    }
                )
        else:
            leaf_stock = (
                get_warehouse_leaf_stock(
                    item_code=item_code,
                    warehouse=suggested_source_wh,
                    target_warehouse=target_wh,
                )
                if suggested_source_wh
                else 0.0
            )

            if leaf_stock <= 0:
                continue

            order_items.append(
                {
                    "item_code": item_code,
                    "item_name": item_name,
                    "uom": uom,
                    "reserved_qty": reserved_qty,
                    "line_actual_qty": line_actual_qty,
                    "deficit_qty": deficit_qty,
                    "picked_qty": deficit_qty,
                    "suggested_source_warehouse": suggested_source_wh,
                    "suggested_batch_no": suggested_batch_no,
                }
            )

    if not order_items:
        frappe.throw(
            _(
                "Seçilen hammaddelerin hiçbirinde depoda veya hatlarda mevcut stok bulunamadı."
            ),
            frappe.ValidationError,
        )

    order_doc = frappe.get_doc(
        {
            "doctype": "KTA Line Replenishment Order",
            "target_warehouse": target_wh,
            "company": company,
            "status": "Draft",
            "items": order_items,
        }
    )
    order_doc.insert(ignore_permissions=True)
    return order_doc.name


@frappe.whitelist()
def override_item_source(
    order_name: str | None = None,
    item_code: str | None = None,
    new_source_warehouse: str | None = None,
    new_batch_no: str | None = None,
) -> dict:
    """Override source warehouse for an item in a Draft replenishment order.

    Re-allocates FIFO batch for the item in the new source warehouse if batch is not supplied.
    """
    if not order_name:
        frappe.throw(
            _("Sipariş numarası (Order Name) zorunludur."),
            frappe.ValidationError,
        )

    order = frappe.get_doc("KTA Line Replenishment Order", order_name)

    if order.status != "Draft":
        frappe.throw(
            _(
                "Sadece Taslak (Draft) durumdaki siparişlerin kaynak ambarı değiştirilebilir."
            ),
            frappe.ValidationError,
        )

    matched = False
    updated_batch = None

    for row in order.items:
        if row.item_code == item_code:
            matched = True
            row.suggested_source_warehouse = new_source_warehouse
            if new_batch_no:
                row.suggested_batch_no = new_batch_no
            else:
                row.suggested_batch_no = allocate_fifo_batch(
                    item_code=item_code,
                    warehouse=new_source_warehouse,
                    required_qty=row.deficit_qty,
                )
            updated_batch = row.suggested_batch_no

    if not matched:
        frappe.throw(
            _("Kalem {0} ikmal siparişinde bulunamadı.").format(item_code),
            frappe.ValidationError,
        )

    order.save(ignore_permissions=True)
    return {
        "order_name": order.name,
        "item_code": item_code,
        "suggested_source_warehouse": new_source_warehouse,
        "suggested_batch_no": updated_batch,
    }


@frappe.whitelist()
def complete_line_replenishment_picking(
    order_name: str,
    picked_items: list[dict] | str | None = None,
) -> str:
    """Complete picking for a KTA Line Replenishment Order and execute Material Transfer.

    Validates that the order exists and is not already Completed or Cancelled.
    Applies over-picking tolerance check (max 15% over deficit_qty).
    Ensures s_warehouse is always a leaf warehouse (never a group warehouse).
    Creates and submits a Material Transfer Stock Entry atomically.
    Updates the order status to Completed and links the Stock Entry.
    Returns the created Stock Entry name.
    """
    if not order_name:
        frappe.throw(
            _("Sipariş numarası (Order Name) zorunludur."),
            frappe.ValidationError,
        )

    order = frappe.get_doc("KTA Line Replenishment Order", order_name)

    if order.status in ["Completed", "Cancelled"]:
        frappe.throw(
            _("Sipariş {0} zaten {1} durumunda, işlem yapılamaz.").format(
                order.name, order.status
            ),
            frappe.ValidationError,
        )

    if isinstance(picked_items, str):
        picked_items = json.loads(picked_items)

    if picked_items and isinstance(picked_items, list):
        for p_item in picked_items:
            row_id = p_item.get("name")
            item_code = p_item.get("item_code")
            p_batch = p_item.get("picked_batch_no") or p_item.get("batch_no")

            for row in order.items:
                matched = False
                if row_id and row.name == row_id:
                    matched = True
                elif item_code and row.item_code == item_code:
                    if p_batch:
                        if (
                            row.suggested_batch_no == p_batch
                            or row.picked_batch_no == p_batch
                        ):
                            matched = True
                    else:
                        matched = True

                if matched:
                    if "picked_qty" in p_item and p_item.get("picked_qty") is not None:
                        row.picked_qty = flt(p_item.get("picked_qty"))
                    if p_item.get("picked_source_warehouse"):
                        row.picked_source_warehouse = p_item.get(
                            "picked_source_warehouse"
                        )
                    if p_item.get("picked_batch_no"):
                        row.picked_batch_no = p_item.get("picked_batch_no")
                    row.is_picked = 1
                    if row_id or p_batch:
                        break

    se_items = []
    total_picked = 0.0

    for row in order.items:
        picked_qty = (
            flt(row.picked_qty)
            if (row.picked_qty is not None and flt(row.picked_qty) > 0)
            else flt(row.deficit_qty)
        )
        deficit_qty = flt(row.deficit_qty)
        max_allowed = max(deficit_qty * 1.15, deficit_qty + 1.0)

        if picked_qty > max_allowed:
            frappe.throw(
                _(
                    "Kalem {0} için fazla toplama izin verilen %15 toleransı aşmaktadır."
                ).format(row.item_code),
                frappe.ValidationError,
            )

        row.picked_qty = picked_qty
        row.is_picked = 1
        total_picked += picked_qty

        s_warehouse = row.picked_source_warehouse or row.suggested_source_warehouse
        t_warehouse = order.target_warehouse
        batch_no = row.picked_batch_no or row.suggested_batch_no

        if s_warehouse and frappe.db.get_value("Warehouse", s_warehouse, "is_group"):
            leafs = get_leaf_warehouses(s_warehouse)
            candidate_leafs = [l for l in leafs if l != t_warehouse]
            if not candidate_leafs:
                candidate_leafs = leafs

            if candidate_leafs:
                leaf_found = None
                if batch_no:
                    for l_wh in candidate_leafs:
                        b_exists = frappe.db.exists(
                            "Stock Ledger Entry",
                            {
                                "item_code": row.item_code,
                                "batch_no": batch_no,
                                "warehouse": l_wh,
                                "is_cancelled": 0,
                            },
                        )
                        if b_exists:
                            leaf_found = l_wh
                            break
                if not leaf_found and not batch_no:
                    for l_wh in candidate_leafs:
                        stock_qty = frappe.db.get_value(
                            "Bin",
                            {"item_code": row.item_code, "warehouse": l_wh},
                            "actual_qty",
                        )
                        if stock_qty and flt(stock_qty) > 0:
                            leaf_found = l_wh
                            break
                s_warehouse = leaf_found or candidate_leafs[0]
            else:
                frappe.throw(
                    _(
                        "Kaynak ambar {0} grup ambarıdır ve altında yaprak ambar bulunamadı."
                    ).format(s_warehouse),
                    frappe.ValidationError,
                )

        item_row = {
            "item_code": row.item_code,
            "qty": picked_qty,
            "s_warehouse": s_warehouse,
            "t_warehouse": t_warehouse,
            "uom": row.uom,
        }
        if batch_no:
            item_row["batch_no"] = batch_no
            item_row["use_serial_batch_fields"] = 1

        se_items.append(item_row)

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.purpose = "Material Transfer"
    se.company = order.company
    for item_data in se_items:
        se.append("items", item_data)
    se.insert(ignore_permissions=True)
    se.submit()

    order.status = "Completed"
    order.stock_entry = se.name
    order.total_picked_qty = total_picked
    order.save(ignore_permissions=True)

    return se.name


@frappe.whitelist()
def cancel_line_replenishment_order(order_name: str) -> str:
    """Cancel a Line Replenishment Order and roll back its linked Stock Entry."""
    if not order_name:
        frappe.throw(
            _("Sipariş numarası (Order Name) zorunludur."),
            frappe.ValidationError,
        )
    order = frappe.get_doc("KTA Line Replenishment Order", order_name)
    order.cancel()
    return order.name
