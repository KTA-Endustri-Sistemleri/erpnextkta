# erpnextkta/kta_stock/services/stock_reconciliation_service.py

import json

import frappe
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
    get_item_and_warehouses,
    get_item_data,
    get_itemwise_batch,
)
from frappe import _
from frappe.utils import cint, flt, nowtime, today

from erpnextkta.kta_stock.label_manager import (
    LabelPrinter,
    enqueue_print_labels_by_names,
)
from erpnextkta.kta_stock.services.relabeling_service import (
    allocate_next_box_batches,
    create_package_split_repack,
    extract_base_lot,
    generate_new_base_lot,
    get_batch_ledger_balances,
    is_standard_kta_box_batch,
    upsert_box_label,
)


def get_items_for_stock_reco_static(warehouse: str, company: str):
    """
    Return all item/warehouse pairs that currently have non-zero stock.

    Behavior:
    - If `warehouse` is a group: scan its warehouse tree (including itself).
    - If `warehouse` is a leaf: scan only that warehouse.

    Rules:
    - We look at Bin.actual_qty (current stock).
    - Only stock items, no variants, not disabled.
    - If actual_qty becomes 0, the pair will no longer appear in future runs.
    """

    wh = frappe.get_cached_doc("Warehouse", warehouse)

    if cint(wh.is_group):
        # group -> tree query
        warehouse_condition = "w.lft >= %s and w.rgt <= %s"
        params = (wh.lft, wh.rgt)
    else:
        # leaf -> only itself
        warehouse_condition = "bin.warehouse = %s"
        params = (warehouse,)

    items = frappe.db.sql(
        f"""
        select
            i.name as item_code,
            i.item_name,
            bin.warehouse as warehouse,
            i.has_serial_no,
            i.has_batch_no
        from `tabBin` bin
        join `tabItem` i on i.name = bin.item_code
        join `tabWarehouse` w on w.name = bin.warehouse
        where
            {warehouse_condition}
            and w.is_group = 0
            and ifnull(bin.actual_qty, 0) != 0
            and ifnull(i.disabled, 0) = 0
            and i.is_stock_item = 1
            and i.has_variants = 0
        """,
        params,
        as_dict=True,
    )

    # ensure one row per (item_code, warehouse)
    seen = set()
    deduped = []
    for row in items:
        key = (row["item_code"], row["warehouse"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


@frappe.whitelist()
def get_items_static(
    warehouse: str,
    posting_date: str,
    posting_time: str,
    company: str,
    item_code: str | None = None,
    ignore_empty_stock: int | str = 0,
):
    """
    Drop-in replacement for core `get_items` used by Stock Reconciliation,
    but with a different source for the base item list.
    Optimized to fetch balances in bulk.
    """

    ignore_empty_stock = cint(ignore_empty_stock)

    if item_code and warehouse:
        items = get_item_and_warehouses(item_code, warehouse)
    else:
        items = get_items_for_stock_reco_static(warehouse, company)

    if not items:
        return []

    # Bulk fetch data to avoid N+1 queries
    itemwise_batch_data = get_itemwise_batch(
        warehouse, posting_date, company, item_code
    )
    balances = get_bulk_stock_balances(warehouse, posting_date, posting_time)

    # We only need serial nos if some items have them
    has_serial_items = any(d.get("has_serial_no") for d in items)
    serial_nos_map = get_bulk_serial_nos(warehouse) if has_serial_items else {}

    res = []
    for d in items:
        key = (d.item_code, d.warehouse)

        # Get balance from pre-fetched data
        qty, valuation_rate = balances.get(key, (0.0, 0.0))

        if key in itemwise_batch_data:
            # Batch items: valuation rate comes from item-warehouse balance (standard ERPNext behavior)
            for row in itemwise_batch_data.get(key):
                if ignore_empty_stock and not row.qty:
                    continue

                args = get_item_data(row, row.qty, valuation_rate)
                res.append(args)
        else:
            # Serialized or Normal items
            serial_no = serial_nos_map.get(key, "") if d.get("has_serial_no") else ""

            if ignore_empty_stock and not qty:
                continue

            args = get_item_data(d, qty, valuation_rate, serial_no)
            res.append(args)

    # stable ordering by item_code / warehouse / batch_no
    res.sort(key=lambda r: (r["item_code"], r["warehouse"], (r.get("batch_no") or "")))

    return res


def get_bulk_stock_balances(warehouse: str, posting_date: str, posting_time: str):
    """
    Fetches latest qty and valuation rate for all items in a warehouse (or group).
    """
    wh = frappe.get_cached_doc("Warehouse", warehouse)

    # Fast path for today's date: use Bin table
    if posting_date >= today():
        data = frappe.db.sql(
            """
            select
                bin.item_code, bin.warehouse, bin.actual_qty, bin.valuation_rate
            from `tabBin` bin
            join `tabWarehouse` w on w.name = bin.warehouse
            where w.lft >= %s and w.rgt <= %s
        """,
            (wh.lft, wh.rgt),
            as_dict=True,
        )

        return {
            (d.item_code, d.warehouse): (flt(d.actual_qty), flt(d.valuation_rate))
            for d in data
        }

    # Robust path for past dates: use ROW_NUMBER over SLE
    # Note: Requires MariaDB 10.2+ or MySQL 8.0+
    try:
        data = frappe.db.sql(
            """
            select warehouse, item_code, qty_after_transaction, valuation_rate
            from (
                select
                    warehouse, item_code, qty_after_transaction, valuation_rate,
                    ROW_NUMBER() OVER (
                        PARTITION BY item_code, warehouse
                        ORDER BY posting_date DESC, posting_time DESC, creation DESC, name DESC
                    ) as rn
                from `tabStock Ledger Entry`
                where warehouse in (select name from tabWarehouse where lft >= %s and rgt <= %s)
                and posting_date <= %s
                and (posting_date < %s or posting_time <= %s)
                and is_cancelled = 0
            ) t
            where rn = 1
        """,
            (wh.lft, wh.rgt, posting_date, posting_date, posting_time),
            as_dict=True,
        )
    except Exception:  # noqa: BLE001
        # Fallback for very old DBs (though unlikely) or complex cases
        return {}

    return {
        (d.item_code, d.warehouse): (
            flt(d.qty_after_transaction),
            flt(d.valuation_rate),
        )
        for d in data
    }


def get_bulk_serial_nos(warehouse: str):
    """
    Fetches all active serial numbers grouped by item and warehouse.
    """
    wh = frappe.get_cached_doc("Warehouse", warehouse)
    data = frappe.db.sql(
        """
        select item_code, warehouse, GROUP_CONCAT(name SEPARATOR '\n') as serial_nos
        from `tabSerial No`
        where warehouse in (select name from tabWarehouse where lft >= %s and rgt <= %s)
        and status = 'Active'
        group by item_code, warehouse
    """,
        (wh.lft, wh.rgt),
        as_dict=True,
    )

    return {(d.item_code, d.warehouse): d.serial_nos for d in data}


# ----------------------------
# Bulk creation (Background Job)
# ----------------------------


@frappe.whitelist()
def create_stock_reco_docs_for_warehouse_group(
    warehouse_group: str,
    company: str,
    posting_date: str | None = None,
    posting_time: str | None = None,
    ignore_empty_stock: int | str = 0,
):
    """
    Enqueue bulk creation to avoid request timeouts.
    Returns immediately with a job id (if available).
    """

    if not warehouse_group:
        frappe.throw(_("Depo Grubu zorunludur"))
    if not company:
        frappe.throw(_("Şirket zorunludur"))

    posting_date = posting_date or today()
    posting_time = posting_time or nowtime()
    ignore_empty_stock = cint(ignore_empty_stock)

    requested_by = frappe.session.user

    job = frappe.enqueue(
        method="erpnextkta.kta_stock.services.stock_reconciliation_service._job_create_stock_reco_docs_for_warehouse_group",
        queue="long",
        timeout=60 * 60,  # 1 hour
        job_name=f"Bulk Stock Reco: {warehouse_group} ({posting_date} {posting_time})",
        warehouse_group=warehouse_group,
        company=company,
        posting_date=posting_date,
        posting_time=posting_time,
        ignore_empty_stock=ignore_empty_stock,
        requested_by=requested_by,
    )

    return {
        "queued": True,
        "job_id": getattr(job, "id", None),
        "message": _(
            "Arkaplan görevi sıraya alındı. Tamamlandığında bildirim alacaksınız."
        ),
    }


def _job_create_stock_reco_docs_for_warehouse_group(
    warehouse_group: str,
    company: str,
    posting_date: str,
    posting_time: str,
    ignore_empty_stock: int,
    requested_by: str | None = None,
):
    """
    Worker job: create one Stock Reconciliation (DRAFT) per leaf warehouse under the group.
    Optimized: fetches all items for the group once and partitions them.
    """

    group = frappe.get_doc("Warehouse", warehouse_group)
    if not group.is_group:
        frappe.throw(_("Seçilen depo bir grup olmalıdır"))

    # Fetch ALL items for the entire group in one go
    all_rows = get_items_static(
        warehouse=warehouse_group,
        posting_date=posting_date,
        posting_time=posting_time,
        company=company,
        item_code=None,
        ignore_empty_stock=ignore_empty_stock,
    )

    if not all_rows:
        frappe.throw(_("Bu depo grubunda stoğu olan ürün bulunamadı"))

    # Partition by warehouse
    warehouse_partition = {}
    for row in all_rows:
        wh = row["warehouse"]
        if wh not in warehouse_partition:
            warehouse_partition[wh] = []
        warehouse_partition[wh].append(row)

    created = []
    skipped = []

    # Get leaf warehouses under this group (to identify empty ones)
    leaf_warehouses = frappe.get_all(
        "Warehouse",
        filters={
            "lft": (">", group.lft),
            "rgt": ("<", group.rgt),
            "is_group": 0,
        },
        pluck="name",
        order_by="name asc",
    )

    for wh in leaf_warehouses:
        rows = warehouse_partition.get(wh)

        if not rows:
            skipped.append(wh)
            continue

        doc = frappe.new_doc("Stock Reconciliation")
        doc.company = company
        doc.posting_date = posting_date
        doc.posting_time = posting_time
        doc.purpose = "Stock Reconciliation"

        if doc.meta.has_field("set_warehouse"):
            doc.set_warehouse = wh
        if doc.meta.has_field("warehouse"):
            doc.warehouse = wh

        doc.set("items", [])
        for row in rows:
            row["use_serial_batch_fields"] = 1
            doc.append("items", row)

        doc.insert()  # DRAFT

        created.append({"warehouse": wh, "name": doc.name, "item_count": len(rows)})

    if requested_by:
        _notify_bulk_stock_reco_result(
            user=requested_by,
            warehouse_group=warehouse_group,
            created=created,
            skipped=skipped,
        )

    return {
        "count": len(created),
        "documents": created,
        "skipped_count": len(skipped),
        "skipped_warehouses": skipped,
    }


def _notify_bulk_stock_reco_result(
    user: str, warehouse_group: str, created: list, skipped: list
):
    """
    Notify user via Notification Log when the background job is done.
    """
    created_count = len(created)
    skipped_count = len(skipped)

    preview = "\n".join([f"- {d['name']} ({d['warehouse']})" for d in created[:20]])
    more = "" if created_count <= 20 else f"\n... (+{created_count - 20} more)"

    msg = (
        f"Warehouse Group: {warehouse_group}\n"
        f"Created: {created_count}\n"
        f"Skipped (no stock): {skipped_count}\n\n"
        f"Created docs:\n{preview}{more}"
    )

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "subject": _("Toplu Stok Uzlaştırması Tamamlandı"),
            "email_content": msg.replace("\n", "<br>"),
            "for_user": user,
            "type": "Alert",
        }
    ).insert(ignore_permissions=True)


# ----------------------------
# Relabeling Hub APIs (Faz 2)
# ----------------------------

_QTY_EPSILON = 1e-4


@frappe.whitelist()
def list_stock_reconciliations(
    status_filter: str = "all",
    warehouse: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List Draft and Submitted Stock Reconciliations with optional warehouse/search filters."""
    frappe.has_permission("Stock Reconciliation", "read", throw=True)

    status_key = (status_filter or "all").strip().lower()
    if status_key == "draft":
        docstatus_clause = "sr.docstatus = 0"
    elif status_key == "submitted":
        docstatus_clause = "sr.docstatus = 1"
    else:
        docstatus_clause = "sr.docstatus IN (0, 1)"

    conditions = [docstatus_clause]
    row_limit = min(max(cint(limit) or 50, 1), 200)
    params: dict = {"limit": row_limit}

    wh_filter = (warehouse or "").strip()
    if wh_filter:
        params["warehouse"] = wh_filter
        conditions.append(
            "(sr.set_warehouse = %(warehouse)s OR EXISTS ("
            "SELECT 1 FROM `tabStock Reconciliation Item` sri "
            "WHERE sri.parent = sr.name AND sri.warehouse = %(warehouse)s))"
        )

    search_text = (search or "").strip()
    if search_text:
        params["search_like"] = f"%{search_text}%"
        conditions.append(
            "(sr.name LIKE %(search_like)s OR IFNULL(sr.set_warehouse, '') LIKE %(search_like)s)"
        )

    where_sql = " AND ".join(conditions)
    headers = frappe.db.sql(
        f"""
        SELECT
            sr.name,
            sr.posting_date,
            sr.posting_time,
            sr.purpose,
            sr.set_warehouse,
            sr.company,
            sr.docstatus,
            sr.owner,
            sr.modified
        FROM `tabStock Reconciliation` sr
        WHERE {where_sql}
        ORDER BY sr.modified DESC
        LIMIT %(limit)s
        """,
        params,
        as_dict=True,
    )

    if not headers:
        return []

    names = tuple(row.name for row in headers)
    counts = frappe.db.sql(
        """
        SELECT
            parent,
            COUNT(*) AS item_count,
            SUM(CASE WHEN IFNULL(qty, 0) > 0 THEN 1 ELSE 0 END) AS positive_item_count
        FROM `tabStock Reconciliation Item`
        WHERE parent IN %(names)s
        GROUP BY parent
        """,
        {"names": names},
        as_dict=True,
    )
    count_map = {c.parent: c for c in counts}

    result = []
    for row in headers:
        c = count_map.get(row.name)
        result.append(
            {
                "name": row.name,
                "posting_date": str(row.posting_date) if row.posting_date else None,
                "posting_time": str(row.posting_time) if row.posting_time else None,
                "purpose": row.purpose,
                "set_warehouse": row.set_warehouse,
                "company": row.company,
                "docstatus": cint(row.docstatus),
                "owner": row.owner,
                "modified": str(row.modified) if row.modified else None,
                "item_count": cint(c.item_count) if c else 0,
                "positive_item_count": cint(c.positive_item_count) if c else 0,
            }
        )
    return result


def _load_bundle_inward_entries_map(bundle_names: list[str]) -> dict[str, list[dict]]:
    if not bundle_names:
        return {}
    entries = frappe.get_all(
        "Serial and Batch Entry",
        filters={
            "parent": ["in", bundle_names],
            "parenttype": "Serial and Batch Bundle",
            "is_outward": 0,
            "qty": [">", 0],
        },
        fields=["parent", "batch_no", "qty"],
        order_by="idx asc",
    )
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        grouped.setdefault(entry.parent, []).append(
            {"batch_no": entry.batch_no, "qty": flt(entry.qty)}
        )
    return grouped


def _extract_reco_row_batches(
    doc, row, bundle_entries_map: dict[str, list[dict]] | None = None
) -> list[dict]:
    """Resolve counted batch/qty pairs for a Stock Reconciliation Item row (v15 bundle-aware)."""
    bundle_name = row.get("serial_and_batch_bundle")
    if bundle_name:
        if bundle_entries_map is not None:
            entries = bundle_entries_map.get(bundle_name) or []
        else:
            entries = (
                _load_bundle_inward_entries_map([bundle_name]).get(bundle_name) or []
            )
        positive_entries = [e for e in entries if flt(e.get("qty")) > 0]
        if positive_entries:
            return positive_entries

    if flt(row.get("qty")) > 0:
        return [{"batch_no": row.get("batch_no"), "qty": flt(row.get("qty"))}]

    return []


def _load_label_map_for_batches(batches: list[str]) -> dict[str, dict]:
    if not batches:
        return {}
    labels = frappe.get_all(
        "KTA Stock Label",
        filters={"label_type": "Depo Giriş Etiketi"},
        or_filters=[["sut_barcode", "in", batches], ["batch", "in", batches]],
        fields=["name", "sut_barcode", "batch", "qty"],
        order_by="creation asc",
    )
    label_map: dict[str, dict] = {}
    for lbl in labels:
        if lbl.sut_barcode and lbl.sut_barcode not in label_map:
            label_map[lbl.sut_barcode] = lbl
        if lbl.batch and lbl.batch not in label_map:
            label_map[lbl.batch] = lbl
    return label_map


@frappe.whitelist()
def get_stock_reconciliation_label_preview(stock_reconciliation: str) -> dict:
    """Build v15-aware label health preview for a Draft or Submitted Stock Reconciliation."""
    frappe.has_permission("Stock Reconciliation", "read", throw=True)
    doc = frappe.get_doc("Stock Reconciliation", stock_reconciliation)

    bundle_names = list(
        {
            row.serial_and_batch_bundle
            for row in (doc.items or [])
            if row.get("serial_and_batch_bundle")
        }
    )
    bundle_entries_map = _load_bundle_inward_entries_map(bundle_names)

    item_codes = list(
        {row.item_code for row in (doc.items or []) if row.get("item_code")}
    )
    item_meta_map: dict[str, dict] = {}
    if item_codes:
        for it in frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "stock_uom", "has_batch_no"],
        ):
            item_meta_map[it.name] = it

    extracted_entries: list[tuple[object, dict]] = []
    batch_set: set[str] = set()
    for row in doc.items or []:
        for entry in _extract_reco_row_batches(doc, row, bundle_entries_map):
            extracted_entries.append((row, entry))
            if entry.get("batch_no"):
                batch_set.add(entry["batch_no"])

    label_map = _load_label_map_for_batches(list(batch_set))

    preview_rows: list[dict] = []
    summary = {
        "total_positive": 0,
        "valid": 0,
        "qty_changed": 0,
        "missing_label": 0,
        "legacy_batch": 0,
    }

    for row, entry in extracted_entries:
        batch_no = entry.get("batch_no")
        qty = flt(entry.get("qty"))
        item_info = item_meta_map.get(row.item_code) or {}
        has_batch_no = cint(item_info.get("has_batch_no"))
        is_standard = is_standard_kta_box_batch(batch_no)
        is_legacy = not is_standard

        lbl = label_map.get(batch_no) if batch_no else None
        label_name = str(lbl.get("name")) if lbl and lbl.get("name") else None
        label_qty = flt(lbl.get("qty")) if lbl else None

        if is_legacy:
            status = "legacy_batch"
        elif not label_name:
            status = "missing_label"
        elif abs(flt(label_qty) - qty) > _QTY_EPSILON:
            status = "qty_changed"
        else:
            status = "valid"

        summary["total_positive"] += 1
        summary[status] += 1

        preview_rows.append(
            {
                "row_name": row.name,
                "item_code": row.item_code,
                "item_name": row.get("item_name")
                or item_info.get("item_name")
                or row.item_code,
                "uom": row.get("stock_uom") or item_info.get("stock_uom"),
                "warehouse": row.warehouse,
                "batch_no": batch_no,
                "is_standard_batch": is_standard,
                "is_legacy": is_legacy,
                "qty": qty,
                "current_qty": flt(row.get("current_qty")),
                "label_name": label_name,
                "label_qty": label_qty,
                "status": status,
                "suggested_mode1_selected": status != "valid",
                "has_batch_no": has_batch_no,
            }
        )

    return {
        "doc": {
            "name": doc.name,
            "docstatus": cint(doc.docstatus),
            "posting_date": str(doc.posting_date) if doc.posting_date else None,
            "posting_time": str(doc.posting_time) if doc.posting_time else None,
            "set_warehouse": doc.set_warehouse,
            "company": doc.company,
            "purpose": doc.purpose,
        },
        "rows": preview_rows,
        "summary": summary,
    }


def _parse_selected_items(selected_items: list[dict] | str) -> list[dict]:
    if isinstance(selected_items, str):
        parsed = json.loads(selected_items) if selected_items.strip() else []
    else:
        parsed = list(selected_items or [])

    if not isinstance(parsed, list) or not parsed:
        frappe.throw(_("Lütfen en az bir satır seçin."))

    return parsed


def _resolve_reco_row(doc, sel: dict, bundle_entries_map: dict[str, list[dict]]):
    row_name = sel.get("row_name")
    if row_name:
        for row in doc.items:
            if row.name == row_name:
                return row
        frappe.throw(_("Seçilen satır bulunamadı: {0}").format(row_name))

    sel_item = sel.get("item_code")
    sel_wh = sel.get("warehouse")
    sel_batch = (
        sel.get("batch_no")
        if sel.get("batch_no") is not None
        else sel.get("source_batch")
    )
    for row in doc.items:
        if row.item_code != sel_item or row.warehouse != sel_wh:
            continue
        row_batches = [
            e.get("batch_no")
            for e in _extract_reco_row_batches(doc, row, bundle_entries_map)
        ]
        if sel_batch in row_batches or row.get("batch_no") == sel_batch:
            return row

    frappe.throw(
        _("Seçilen ürün/depo satırı bulunamadı: {0} ({1})").format(sel_item, sel_wh)
    )


def _resolve_selection_batch_and_qty(
    doc, row, sel: dict, bundle_entries_map: dict[str, list[dict]]
) -> tuple[str | None, float]:
    sel_batch = (
        sel.get("batch_no")
        if sel.get("batch_no") is not None
        else sel.get("source_batch")
    )
    extracted = _extract_reco_row_batches(doc, row, bundle_entries_map)

    if sel_batch is None and extracted:
        sel_batch = extracted[0].get("batch_no")

    if sel.get("qty") is not None:
        target_qty = flt(sel.get("qty"))
    else:
        matched_entry = next(
            (e for e in extracted if e.get("batch_no") == sel_batch), None
        )
        target_qty = (
            flt(matched_entry.get("qty")) if matched_entry else flt(row.get("qty"))
        )

    return sel_batch, target_qty


def _validate_box_splits(splits_raw, expected_qty: float) -> list[float] | None:
    if not splits_raw:
        return None
    splits = [flt(q) for q in splits_raw]
    if any(q <= 0 for q in splits):
        frappe.throw(_("Tüm kutu miktarları sıfırdan büyük olmalıdır."))
    if abs(sum(splits) - flt(expected_qty)) > _QTY_EPSILON:
        frappe.throw(
            _("Kutu kırılım toplamı ({0}) satır miktarı ({1}) ile eşleşmiyor.").format(
                sum(splits), flt(expected_qty)
            )
        )
    return splits


def _get_reco_row_rate(row) -> float:
    rate = flt(row.get("valuation_rate")) or flt(row.get("current_valuation_rate"))
    if rate > 0:
        return rate
    return flt(
        frappe.db.get_value(
            "Bin",
            {"item_code": row.item_code, "warehouse": row.warehouse},
            "valuation_rate",
        )
    )


def _get_batch_inherited_meta(batch_no: str | None) -> dict:
    if not batch_no or not frappe.db.exists("Batch", batch_no):
        return {}
    return (
        frappe.db.get_value(
            "Batch",
            batch_no,
            [
                "supplier",
                "reference_doctype",
                "reference_name",
                "manufacturing_date",
                "expiry_date",
                "stock_uom",
            ],
            as_dict=True,
        )
        or {}
    )


def _resolve_current_qty_for_zero_out(row, batch_no: str | None) -> float:
    curr_qty = flt(row.get("current_qty"))
    if curr_qty > 0:
        return curr_qty
    if batch_no:
        balances = get_batch_ledger_balances(row.item_code, batch_no)
        return flt(
            sum(flt(b["qty"]) for b in balances if b["warehouse"] == row.warehouse)
        )
    return 0.0


def _clear_draft_row_bundles(row, cleared_bundles: set[str]) -> None:
    for field in ("serial_and_batch_bundle", "current_serial_and_batch_bundle"):
        b_name = row.get(field)
        if b_name:
            cleared_bundles.add(b_name)
            row.set(field, None)
    row.use_serial_batch_fields = 1


def _cleanup_orphan_draft_bundles(doc, cleared_bundles: set[str]) -> None:
    if not cleared_bundles:
        return
    still_used = {
        val
        for row in doc.items
        for val in (
            row.get("serial_and_batch_bundle"),
            row.get("current_serial_and_batch_bundle"),
        )
        if val
    }
    for bundle_name in cleared_bundles - still_used:
        if (
            frappe.db.get_value("Serial and Batch Bundle", bundle_name, "docstatus")
            == 0
        ):
            frappe.delete_doc(
                "Serial and Batch Bundle", bundle_name, ignore_permissions=True
            )


def _append_reco_batch_row(
    doc,
    template_row,
    batch_no: str,
    qty: float,
    rate: float,
    allow_zero: int,
) -> None:
    doc.append(
        "items",
        {
            "item_code": template_row.item_code,
            "item_name": template_row.get("item_name"),
            "warehouse": template_row.warehouse,
            "batch_no": batch_no,
            "qty": flt(qty),
            "current_qty": 0,
            "valuation_rate": rate,
            "allow_zero_valuation_rate": allow_zero,
            "use_serial_batch_fields": 1,
        },
    )


@frappe.whitelist(methods=["POST"])
def submit_and_print_stock_reconciliation(
    stock_reconciliation: str,
    selected_items: list[dict] | str,
    print_labels: int = 1,
) -> dict:
    """Expand/standardize selected Draft rows in-place, submit Stock Reconciliation, and print labels."""
    parsed_items = _parse_selected_items(selected_items)
    doc = frappe.get_doc("Stock Reconciliation", stock_reconciliation)
    frappe.has_permission("Stock Reconciliation", "write", doc=doc, throw=True)
    frappe.has_permission("Stock Reconciliation", "submit", doc=doc, throw=True)

    if doc.docstatus != 0:
        frappe.throw(
            _("Yalnızca Taslak (Draft) sayım belgeleri bu işlemle onaylanabilir.")
        )

    bundle_names = [
        r.serial_and_batch_bundle
        for r in (doc.items or [])
        if r.get("serial_and_batch_bundle")
    ]
    bundle_entries_map = _load_bundle_inward_entries_map(bundle_names)

    validated_selections: list[
        tuple[object, dict, str | None, float, list[float] | None]
    ] = []
    for sel in parsed_items:
        row = _resolve_reco_row(doc, sel, bundle_entries_map)
        source_batch, target_qty = _resolve_selection_batch_and_qty(
            doc, row, sel, bundle_entries_map
        )
        if target_qty <= 0:
            frappe.throw(_("Seçili satır miktarı sıfırdan büyük olmalıdır."))
        splits = _validate_box_splits(sel.get("box_splits"), target_qty)
        validated_selections.append((row, sel, source_batch, target_qty, splits))

    cleared_bundles: set[str] = set()
    labels_to_upsert: list[tuple[str, str, str, float]] = []
    touched_pairs: set[tuple[str, str]] = set()

    for orig_row, sel, source_batch, target_qty, splits in validated_selections:
        convert_legacy = cint(sel.get("convert_legacy"))
        is_std = is_standard_kta_box_batch(source_batch)
        rate = _get_reco_row_rate(orig_row)
        allow_zero = 1 if rate <= 0 else 0
        source_meta = _get_batch_inherited_meta(source_batch)

        if convert_legacy or (not is_std and splits):
            target_splits = splits if splits else [target_qty]
            base_lot = generate_new_base_lot(
                item_code=orig_row.item_code,
                reference_doctype=source_meta.get("reference_doctype"),
                reference_name=source_meta.get("reference_name"),
                manufacturing_date=source_meta.get("manufacturing_date"),
                supplier=source_meta.get("supplier"),
                expiry_date=source_meta.get("expiry_date"),
                stock_uom=source_meta.get("stock_uom"),
            )
            new_batches = allocate_next_box_batches(
                base_lot=base_lot,
                count=len(target_splits),
                item_code=orig_row.item_code,
                source_meta=source_meta,
            )

            _clear_draft_row_bundles(orig_row, cleared_bundles)
            orig_current_qty = _resolve_current_qty_for_zero_out(orig_row, source_batch)

            if source_batch and orig_current_qty > 0:
                orig_row.batch_no = source_batch
                orig_row.qty = 0
                orig_row.current_qty = orig_current_qty
                orig_row.valuation_rate = rate
                orig_row.current_valuation_rate = (
                    flt(orig_row.get("current_valuation_rate")) or rate
                )
                orig_row.allow_zero_valuation_rate = allow_zero
                touched_pairs.add((orig_row.item_code, source_batch))
                rows_to_add = list(zip(new_batches, target_splits))
            else:
                if source_batch:
                    touched_pairs.add((orig_row.item_code, source_batch))
                orig_row.batch_no = new_batches[0]
                orig_row.qty = target_splits[0]
                orig_row.current_qty = 0
                orig_row.valuation_rate = rate
                orig_row.allow_zero_valuation_rate = allow_zero
                rows_to_add = list(zip(new_batches[1:], target_splits[1:]))

            for new_batch, split_qty in rows_to_add:
                _append_reco_batch_row(
                    doc, orig_row, new_batch, split_qty, rate, allow_zero
                )

            for new_batch, split_qty in zip(new_batches, target_splits):
                labels_to_upsert.append(
                    (orig_row.item_code, orig_row.warehouse, new_batch, split_qty)
                )
                touched_pairs.add((orig_row.item_code, new_batch))

        elif is_std and splits and len(splits) >= 2:
            _clear_draft_row_bundles(orig_row, cleared_bundles)
            orig_row.batch_no = source_batch
            orig_row.qty = splits[0]
            orig_row.valuation_rate = rate
            orig_row.allow_zero_valuation_rate = allow_zero

            extra_batches = allocate_next_box_batches(
                base_lot=extract_base_lot(source_batch),
                count=len(splits) - 1,
                item_code=orig_row.item_code,
                source_meta=source_meta,
            )
            for extra_batch, split_qty in zip(extra_batches, splits[1:]):
                _append_reco_batch_row(
                    doc, orig_row, extra_batch, split_qty, rate, allow_zero
                )

            labels_to_upsert.append(
                (orig_row.item_code, orig_row.warehouse, source_batch, splits[0])
            )
            touched_pairs.add((orig_row.item_code, source_batch))
            for extra_batch, split_qty in zip(extra_batches, splits[1:]):
                labels_to_upsert.append(
                    (orig_row.item_code, orig_row.warehouse, extra_batch, split_qty)
                )
                touched_pairs.add((orig_row.item_code, extra_batch))

        else:
            if splits:
                orig_row.qty = splits[0]
            if not orig_row.get("batch_no") and source_batch:
                _clear_draft_row_bundles(orig_row, cleared_bundles)
                orig_row.batch_no = source_batch
            elif orig_row.get("serial_and_batch_bundle"):
                _clear_draft_row_bundles(orig_row, cleared_bundles)
            orig_row.use_serial_batch_fields = 1
            if source_batch:
                eff_qty = splits[0] if splits else target_qty
                labels_to_upsert.append(
                    (orig_row.item_code, orig_row.warehouse, source_batch, eff_qty)
                )
                touched_pairs.add((orig_row.item_code, source_batch))

    doc.save(ignore_permissions=True)
    _cleanup_orphan_draft_bundles(doc, cleared_bundles)
    doc.submit()

    label_names: list[str] = []
    for item_code, wh, batch_no, box_qty in labels_to_upsert:
        if not batch_no or flt(box_qty) <= 0:
            continue
        lbl_name = upsert_box_label(
            item_code=item_code,
            batch_no=batch_no,
            qty=flt(box_qty),
            target_warehouse=wh,
            reference_doctype="Stock Reconciliation",
            reference_name=doc.name,
            posting_date=doc.posting_date,
            fallback_ref="SAYIM",
        )
        if lbl_name is not None:
            lbl_str = str(lbl_name)
            if lbl_str not in label_names:
                label_names.append(lbl_str)

    if touched_pairs:
        LabelPrinter.clear_empty_labels(pairs=list(touched_pairs))

    queued_print_count = 0
    if cint(print_labels) == 1 and label_names:
        print_res = enqueue_print_labels_by_names(label_names)
        queued_print_count = cint(print_res.get("queued"))

    return {
        "stock_reconciliation": doc.name,
        "docstatus": doc.docstatus,
        "labels": label_names,
        "queued_print_count": queued_print_count,
    }


@frappe.whitelist(methods=["POST"])
def relabel_submitted_stock_reconciliation(
    stock_reconciliation: str,
    selected_items: list[dict] | str,
    print_labels: int = 1,
) -> dict:
    """Relabel or split boxes on an already-submitted Stock Reconciliation."""
    parsed_items = _parse_selected_items(selected_items)
    doc = frappe.get_doc("Stock Reconciliation", stock_reconciliation)
    frappe.has_permission("Stock Reconciliation", "write", doc=doc, throw=True)

    if doc.docstatus != 1:
        frappe.throw(
            _(
                "Bu işlem yalnızca onaylanmış (Submitted) sayım belgeleri için kullanılabilir."
            )
        )

    bundle_names = [
        r.serial_and_batch_bundle
        for r in (doc.items or [])
        if r.get("serial_and_batch_bundle")
    ]
    bundle_entries_map = _load_bundle_inward_entries_map(bundle_names)

    validated_selections: list[
        tuple[object, dict, str | None, float, list[float] | None]
    ] = []
    for sel in parsed_items:
        row = _resolve_reco_row(doc, sel, bundle_entries_map)
        source_batch, target_qty = _resolve_selection_batch_and_qty(
            doc, row, sel, bundle_entries_map
        )
        if not source_batch:
            frappe.throw(
                _(
                    "Parti numarası olmayan satır için etiketleme/bölme yapılamaz: {0}"
                ).format(row.item_code)
            )
        if target_qty <= 0:
            frappe.throw(_("Seçili satır miktarı sıfırdan büyük olmalıdır."))
        splits = _validate_box_splits(sel.get("box_splits"), target_qty)
        validated_selections.append((row, sel, source_batch, target_qty, splits))

    is_reco_manager = any(
        role in frappe.get_roles()
        for role in ("Stock Reconciliation Manager", "System Manager")
    )

    created_se_names: list[str] = []
    label_names: list[str] = []
    touched_pairs: set[tuple[str, str]] = set()

    def _upsert_and_collect(item_code: str, wh: str, batch_no: str, qty: float):
        lbl_name = upsert_box_label(
            item_code=item_code,
            batch_no=batch_no,
            qty=flt(qty),
            target_warehouse=wh,
            reference_doctype="Stock Reconciliation",
            reference_name=doc.name,
            posting_date=doc.posting_date,
            fallback_ref="SAYIM",
        )
        if lbl_name is not None:
            lbl_str = str(lbl_name)
            if lbl_str not in label_names:
                label_names.append(lbl_str)
        touched_pairs.add((item_code, batch_no))

    for orig_row, sel, source_batch, target_qty, splits in validated_selections:
        convert_legacy = cint(sel.get("convert_legacy"))
        is_std = is_standard_kta_box_batch(source_batch)

        if is_std and (not splits or len(splits) <= 1) and not convert_legacy:
            eff_qty = splits[0] if splits else target_qty
            _upsert_and_collect(
                orig_row.item_code, orig_row.warehouse, source_batch, eff_qty
            )
            continue

        if is_std and splits and len(splits) > 1 and not convert_legacy:
            split_res = create_package_split_repack(
                item_code=orig_row.item_code,
                source_warehouse=orig_row.warehouse,
                target_warehouse=orig_row.warehouse,
                source_batch=source_batch,
                split_qtys=splits[1:],
                remarks=_("Sayım sonrası koli bölme ({0})").format(doc.name),
                posting_date=doc.posting_date,
                ignore_reco_lock=is_reco_manager,
            )
            created_se_names.append(split_res["stock_entry"])
            _upsert_and_collect(
                orig_row.item_code, orig_row.warehouse, source_batch, splits[0]
            )
            for created in split_res["created_batches"]:
                _upsert_and_collect(
                    orig_row.item_code,
                    orig_row.warehouse,
                    created["batch_no"],
                    created["qty"],
                )
        else:
            target_splits = splits if splits else [target_qty]
            split_res = create_package_split_repack(
                item_code=orig_row.item_code,
                source_warehouse=orig_row.warehouse,
                target_warehouse=orig_row.warehouse,
                source_batch=source_batch,
                split_qtys=target_splits,
                remarks=_("Sayım sonrası standart koli dönüştürme ({0})").format(
                    doc.name
                ),
                posting_date=doc.posting_date,
                ignore_reco_lock=is_reco_manager,
            )
            created_se_names.append(split_res["stock_entry"])
            touched_pairs.add((orig_row.item_code, source_batch))
            for created in split_res["created_batches"]:
                _upsert_and_collect(
                    orig_row.item_code,
                    orig_row.warehouse,
                    created["batch_no"],
                    created["qty"],
                )

    if touched_pairs:
        LabelPrinter.clear_empty_labels(pairs=list(touched_pairs))

    queued_print_count = 0
    if cint(print_labels) == 1 and label_names:
        print_res = enqueue_print_labels_by_names(label_names)
        queued_print_count = cint(print_res.get("queued"))

    return {
        "stock_reconciliation": doc.name,
        "stock_entries": created_se_names,
        "labels": label_names,
        "queued_print_count": queued_print_count,
    }
