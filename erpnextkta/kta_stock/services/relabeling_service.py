import re

import frappe
from erpnext.stock.utils import get_incoming_rate
from frappe import _
from frappe.utils import cint, flt, nowtime, today

from erpnextkta.kta_stock.batch_manager import BatchSplitManager

_STANDARD_KTA_BOX_RE = re.compile(r"^[A-Z0-9]{7}(?!0000)[0-9]{4}$")
_EPSILON = 1e-6
_INHERITED_BATCH_FIELDS = (
    "supplier",
    "reference_doctype",
    "reference_name",
    "manufacturing_date",
    "expiry_date",
    "stock_uom",
)


def is_standard_kta_box_batch(batch_no: str | None) -> bool:
    """Return True if batch_no matches 7 uppercase alnum lot + 4 non-zero box digits."""
    cleaned = str(batch_no or "").strip()
    return bool(_STANDARD_KTA_BOX_RE.fullmatch(cleaned))


def extract_base_lot(batch_no: str | None) -> str | None:
    """Extract the 7-char lot prefix from a standard KTA box batch, or None."""
    cleaned = str(batch_no or "").strip()
    if is_standard_kta_box_batch(cleaned):
        return cleaned[:7]
    return None


def generate_new_base_lot(
    item_code: str,
    reference_doctype: str | None = None,
    reference_name: str | None = None,
    manufacturing_date: str | None = None,
    supplier: str | None = None,
    expiry_date: str | None = None,
    stock_uom: str | None = None,
) -> str:
    """Generate a unique 7-char uppercase root Batch (batch_qty=0) preserving metadata."""
    base_lot = None
    for _attempt in range(100):
        candidate = frappe.generate_hash("", 7).upper()
        if not frappe.db.exists("Batch", candidate) and not frappe.db.exists(
            "Serial and Batch Bundle", candidate
        ):
            base_lot = candidate
            break

    if not base_lot:
        frappe.throw(_("Benzersiz 7 haneli lot ön eki üretilemedi."))

    resolved_uom = stock_uom or frappe.db.get_value("Item", item_code, "stock_uom")
    batch_payload = {
        "doctype": "Batch",
        "batch_id": base_lot,
        "item": item_code,
        "batch_qty": 0,
    }
    optional_fields = {
        "stock_uom": resolved_uom,
        "supplier": supplier,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "manufacturing_date": manufacturing_date,
        "expiry_date": expiry_date,
    }
    for key, val in optional_fields.items():
        if val:
            batch_payload[key] = val

    batch_doc = frappe.get_doc(batch_payload)
    batch_doc.insert(ignore_permissions=True)
    return batch_doc.name


def allocate_next_box_batches(
    base_lot: str,
    count: int,
    item_code: str,
    source_meta: dict | None = None,
) -> list[str]:
    """Allocate the next `count` 4-digit box batches under `base_lot`, inheriting source_meta."""
    alloc_count = cint(count)
    if alloc_count <= 0:
        return []

    meta = source_meta or {}
    resolved_uom = meta.get("stock_uom") or frappe.db.get_value(
        "Item", item_code, "stock_uom"
    )
    next_seq = BatchSplitManager._get_last_batch_number_for_base(base_lot) + 1
    created: list[str] = []

    for _idx in range(alloc_count):
        while frappe.db.exists("Batch", f"{base_lot}{next_seq:04d}"):
            next_seq += 1

        if next_seq > 9999:
            frappe.throw(
                _("Lot {0} için maksimum koli soneki (9999) aşıldı.").format(base_lot)
            )

        batch_id = f"{base_lot}{next_seq:04d}"
        batch_payload = {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
            "batch_qty": 0,
        }
        for field in _INHERITED_BATCH_FIELDS:
            val = resolved_uom if field == "stock_uom" else meta.get(field)
            if val:
                batch_payload[field] = val

        batch_doc = frappe.get_doc(batch_payload)
        batch_doc.insert(ignore_permissions=True)
        created.append(batch_doc.name)
        next_seq += 1

    return created


def _is_product_or_semi_finished_group(item_group: str | None) -> bool:
    if not item_group:
        return False
    target_groups = {"ÜRÜNLER", "YARI MAMULLER"}
    if item_group in target_groups:
        return True
    if frappe.db.exists("Item Group", item_group):
        lft_rgt = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"])
        if lft_rgt and lft_rgt[0] is not None:
            from frappe.utils.nestedset import get_ancestors_of

            ancestors = get_ancestors_of("Item Group", item_group) or []
            if any(anc in target_groups for anc in ancestors):
                return True
    return False


def _resolve_wo_material_index(wo_name: str, bom_no: str | None) -> str:
    """Resolve material_index from Work Order custom field or linked BOM customer index."""
    if frappe.get_meta("Work Order").has_field("material_index"):
        val = frappe.db.get_value("Work Order", wo_name, "material_index")
        if val:
            return str(val)

    if (
        bom_no
        and frappe.db.exists("BOM", bom_no)
        and frappe.get_meta("BOM").has_field("custom_musteri_indeksi_no")
    ):
        val = frappe.db.get_value("BOM", bom_no, "custom_musteri_indeksi_no")
        if val:
            return str(val)

    return "-"


def resolve_item_default_label_type(item_code: str | None) -> str:
    """Return default label type for item: 'İş Emri Etiketi' for manufactured/BOM/product groups, else 'Depo Giriş Etiketi'."""
    if not item_code:
        return "Depo Giriş Etiketi"

    item = frappe.db.get_value(
        "Item",
        item_code,
        ["item_group", "is_purchase_item", "default_bom"],
        as_dict=True,
    )
    if not item:
        return "Depo Giriş Etiketi"

    if cint(item.get("is_purchase_item")) == 0 or item.get("default_bom"):
        return "İş Emri Etiketi"

    item_group = item.get("item_group")
    if _is_product_or_semi_finished_group(item_group):
        return "İş Emri Etiketi"

    return "Depo Giriş Etiketi"


def _merge_missing_meta(target: dict, source: dict | None):
    if not source:
        return
    for key in (
        "quality_ref",
        "supplier_delivery_note",
        "gr_posting_date",
        "reference_doctype",
        "reference_name",
        "label_type",
        "work_order",
        "material_index",
    ):
        val = source.get(key)
        if not val:
            continue
        if (
            key == "supplier_delivery_note"
            and (not target.get(key) or target.get(key) == "-")
        ) or not target.get(key):
            target[key] = val


def _has_complete_meta(meta: dict) -> bool:
    if (
        meta.get("label_type") == "İş Emri Etiketi"
        or meta.get("reference_doctype") == "Work Order"
    ):
        return bool(
            meta.get("quality_ref")
            and (meta.get("reference_name") or meta.get("work_order"))
        )
    return bool(
        meta.get("quality_ref")
        and meta.get("supplier_delivery_note")
        and meta.get("supplier_delivery_note") != "-"
        and meta.get("gr_posting_date")
        and meta.get("reference_doctype")
        and meta.get("reference_name")
    )


def resolve_batch_label_metadata(
    item_code: str,
    batch_no: str | None,
    fallback_ref: str = "SAYIM",
) -> dict:
    """Resolve quality, delivery note, posting date, and origin reference for a batch label."""
    meta = {
        "quality_ref": None,
        "supplier_delivery_note": None,
        "gr_posting_date": None,
        "reference_doctype": None,
        "reference_name": None,
        "label_type": None,
        "work_order": None,
        "material_index": None,
    }
    label_fields = [
        "quality_ref",
        "supplier_delivery_note",
        "gr_posting_date",
        "reference_doctype",
        "reference_name",
        "label_type",
        "work_order",
        "material_index",
    ]

    if batch_no:
        direct_labels = frappe.get_all(
            "KTA Stock Label",
            filters={"label_type": ["in", ["Depo Giriş Etiketi", "İş Emri Etiketi"]]},
            or_filters=[["sut_barcode", "=", batch_no], ["batch", "=", batch_no]],
            fields=label_fields,
            order_by="creation asc",
            limit=1,
        )
        if direct_labels:
            _merge_missing_meta(meta, direct_labels[0])

    if not _has_complete_meta(meta) and is_standard_kta_box_batch(batch_no):
        base_lot = extract_base_lot(batch_no)
        sibling_labels = frappe.get_all(
            "KTA Stock Label",
            filters={
                "label_type": ["in", ["Depo Giriş Etiketi", "İş Emri Etiketi"]],
                "item_code": item_code,
            },
            or_filters=[
                ["batch", "like", f"{base_lot}%"],
                ["sut_barcode", "like", f"{base_lot}%"],
            ],
            fields=label_fields,
            order_by="creation asc",
            limit=5,
        )
        for sibling in sibling_labels:
            _merge_missing_meta(meta, sibling)
            if _has_complete_meta(meta):
                break

    if (
        not _has_complete_meta(meta)
        and batch_no
        and frappe.db.exists("Batch", batch_no)
    ):
        batch_ref = frappe.db.get_value(
            "Batch", batch_no, ["reference_doctype", "reference_name"], as_dict=True
        )
        if batch_ref:
            ref_dt = batch_ref.get("reference_doctype")
            ref_name = batch_ref.get("reference_name")

            if ref_dt == "Work Order" and ref_name:
                meta["label_type"] = "İş Emri Etiketi"
                meta["reference_doctype"] = "Work Order"
                meta["reference_name"] = ref_name
                meta["work_order"] = ref_name
                wo_vals = (
                    frappe.db.get_value(
                        "Work Order",
                        ref_name,
                        ["bom_no", "planned_start_date"],
                        as_dict=True,
                    )
                    or {}
                )
                meta["material_index"] = _resolve_wo_material_index(
                    ref_name, wo_vals.get("bom_no")
                )
                if wo_vals.get("planned_start_date"):
                    meta["gr_posting_date"] = str(
                        wo_vals.get("planned_start_date")
                    ).split(" ")[0]
                meta["quality_ref"] = "ATLA 5/1"
                meta["supplier_delivery_note"] = "-"

            elif ref_dt == "Stock Entry" and ref_name:
                se_vals = (
                    frappe.db.get_value(
                        "Stock Entry",
                        ref_name,
                        [
                            "purpose",
                            "stock_entry_type",
                            "work_order",
                            "posting_date",
                        ],
                        as_dict=True,
                    )
                    or {}
                )
                purpose = se_vals.get("purpose")
                se_type = se_vals.get("stock_entry_type")
                if purpose == "Manufacture" or se_type == "Manufacture":
                    meta["label_type"] = "İş Emri Etiketi"
                    meta["reference_doctype"] = "Stock Entry"
                    meta["reference_name"] = ref_name
                    wo_name = se_vals.get("work_order")
                    if wo_name:
                        meta["work_order"] = wo_name
                        wo_vals = (
                            frappe.db.get_value(
                                "Work Order",
                                wo_name,
                                ["bom_no", "planned_start_date"],
                                as_dict=True,
                            )
                            or {}
                        )
                        meta["material_index"] = _resolve_wo_material_index(
                            wo_name, wo_vals.get("bom_no")
                        )
                        if wo_vals.get("planned_start_date") and not se_vals.get(
                            "posting_date"
                        ):
                            meta["gr_posting_date"] = str(
                                wo_vals.get("planned_start_date")
                            ).split(" ")[0]
                    if se_vals.get("posting_date"):
                        meta["gr_posting_date"] = str(se_vals.get("posting_date"))
                    meta["quality_ref"] = "ATLA 5/1"
                    meta["supplier_delivery_note"] = "-"

            elif ref_dt == "Purchase Receipt" and ref_name:
                pr_name = ref_name
                meta["label_type"] = "Depo Giriş Etiketi"
                pr_vals = frappe.db.get_value(
                    "Purchase Receipt",
                    pr_name,
                    ["supplier_delivery_note", "posting_date"],
                    as_dict=True,
                )
                qi_name = frappe.db.get_value(
                    "Quality Inspection",
                    {
                        "reference_type": "Purchase Receipt",
                        "reference_name": pr_name,
                        "item_code": item_code,
                        "docstatus": ["<", 2],
                    },
                    "name",
                    order_by="docstatus desc, modified desc",
                )
                if not qi_name:
                    qi_name = frappe.db.get_value(
                        "Quality Inspection",
                        {
                            "reference_type": "Purchase Receipt",
                            "reference_name": pr_name,
                            "docstatus": ["<", 2],
                        },
                        "name",
                        order_by="docstatus desc, modified desc",
                    )
                _merge_missing_meta(
                    meta,
                    {
                        "label_type": "Depo Giriş Etiketi",
                        "quality_ref": qi_name or "ATLA 5/1",
                        "supplier_delivery_note": pr_vals.get("supplier_delivery_note")
                        if pr_vals
                        else None,
                        "gr_posting_date": pr_vals.get("posting_date")
                        if pr_vals
                        else None,
                        "reference_doctype": "Purchase Receipt",
                        "reference_name": pr_name,
                    },
                )

    if not meta.get("label_type"):
        meta["label_type"] = resolve_item_default_label_type(item_code)

    if meta.get("label_type") == "İş Emri Etiketi":
        meta["quality_ref"] = meta.get("quality_ref") or "ATLA 5/1"
    else:
        meta["quality_ref"] = meta.get("quality_ref") or fallback_ref
    meta["supplier_delivery_note"] = meta.get("supplier_delivery_note") or "-"
    meta["gr_posting_date"] = meta.get("gr_posting_date") or today()
    return meta


def get_batch_ledger_balances(item_code: str, batch_no: str) -> list[dict]:
    """Return non-zero warehouse balances for (item_code, batch_no) across SLE and v15 SBE/SABB."""
    if not item_code or not batch_no:
        return []

    rows = frappe.db.sql(
        """
        SELECT warehouse, SUM(qty) AS qty
        FROM (
            SELECT
                sle.warehouse AS warehouse,
                sle.actual_qty AS qty
            FROM `tabStock Ledger Entry` sle
            WHERE sle.is_cancelled = 0
              AND (sle.serial_and_batch_bundle IS NULL OR sle.serial_and_batch_bundle = '')
              AND sle.item_code = %(item_code)s
              AND sle.batch_no = %(batch_no)s

            UNION ALL

            SELECT
                COALESCE(NULLIF(sabe.warehouse, ''), sabb.warehouse) AS warehouse,
                sabe.qty AS qty
            FROM `tabSerial and Batch Entry` sabe
            INNER JOIN `tabSerial and Batch Bundle` sabb ON sabb.name = sabe.parent
            WHERE sabb.docstatus = 1
              AND sabb.is_cancelled = 0
              AND sabb.item_code = %(item_code)s
              AND sabe.batch_no = %(batch_no)s
        ) ledger_entries
        GROUP BY warehouse
        HAVING ABS(SUM(qty)) > 1e-6
        ORDER BY qty DESC, warehouse ASC
        """,
        {"item_code": item_code, "batch_no": batch_no},
        as_dict=True,
    )
    return [
        {"warehouse": row.warehouse, "qty": flt(row.qty)}
        for row in rows
        if row.warehouse
    ]


def delete_labels_with_print_logs(label_names: list[str]) -> None:
    """Bulk-delete KTA Print Log, child Split rows, and KTA Stock Label records in chunks."""
    cleaned_names = [name for name in (label_names or []) if name]
    if not cleaned_names:
        return

    chunk_size = 1000
    for idx in range(0, len(cleaned_names), chunk_size):
        chunk = cleaned_names[idx : idx + chunk_size]
        frappe.db.delete(
            "KTA Print Log",
            filters={"label_doctype": "KTA Stock Label", "label_name": ["in", chunk]},
        )
        frappe.db.delete(
            "KTA Stock Label Split",
            filters={"parenttype": "KTA Stock Label", "parent": ["in", chunk]},
        )
        frappe.db.delete("KTA Stock Label", filters={"name": ["in", chunk]})


def upsert_box_label(
    item_code: str,
    batch_no: str,
    qty: float,
    target_warehouse: str | None = None,
    source_warehouse: str | None = None,
    reference_doctype: str | None = None,
    reference_name: str | None = None,
    posting_date: str | None = None,
    quality_ref: str | None = None,
    supplier_delivery_note: str | None = None,
    fallback_ref: str = "SAYIM",
    label_type: str | None = None,
) -> str | int:
    """Create or update the single Depo Giriş / İş Emri Etiketi record for a box batch, preserving PR/WO refs."""
    meta = resolve_batch_label_metadata(item_code, batch_no, fallback_ref=fallback_ref)
    eff_label_type = (
        label_type
        or meta.get("label_type")
        or resolve_item_default_label_type(item_code)
    )
    eff_quality_ref = (
        quality_ref
        or meta.get("quality_ref")
        or ("ATLA 5/1" if eff_label_type == "İş Emri Etiketi" else fallback_ref)
    )
    eff_sdn = supplier_delivery_note or meta.get("supplier_delivery_note") or "-"
    eff_gr_date = posting_date or meta.get("gr_posting_date") or today()

    existing_name = frappe.db.get_value(
        "KTA Stock Label",
        {
            "sut_barcode": batch_no,
            "label_type": ["in", ["Depo Giriş Etiketi", "İş Emri Etiketi"]],
        },
        "name",
    )
    if existing_name:
        existing = frappe.db.get_value(
            "KTA Stock Label",
            existing_name,
            [
                "label_type",
                "reference_doctype",
                "reference_name",
                "quality_ref",
                "supplier_delivery_note",
                "gr_posting_date",
                "work_order",
                "material_index",
            ],
            as_dict=True,
        )
        updates = {
            "qty": flt(qty),
            "item_code": item_code,
            "batch": batch_no,
        }
        if not existing or not existing.get("label_type"):
            updates["label_type"] = eff_label_type

        if target_warehouse is not None:
            updates["target_warehouse"] = target_warehouse
        if source_warehouse is not None:
            updates["source_warehouse"] = source_warehouse

        if existing and existing.get("reference_doctype") not in (
            "Purchase Receipt",
            "Work Order",
        ):
            if reference_doctype:
                updates["reference_doctype"] = reference_doctype
            if reference_name:
                updates["reference_name"] = reference_name

        if existing and not existing.get("quality_ref"):
            updates["quality_ref"] = eff_quality_ref
        if existing and not existing.get("supplier_delivery_note"):
            updates["supplier_delivery_note"] = eff_sdn
        if existing and not existing.get("gr_posting_date"):
            updates["gr_posting_date"] = eff_gr_date
        if meta.get("work_order"):
            updates["work_order"] = meta.get("work_order")
        if meta.get("material_index"):
            updates["material_index"] = meta.get("material_index")

        frappe.db.set_value("KTA Stock Label", existing_name, updates)
        return existing_name

    item_info = (
        frappe.db.get_value(
            "Item",
            item_code,
            ["item_name", "item_group", "stock_uom"],
            as_dict=True,
        )
        or {}
    )
    label_doc = frappe.get_doc(
        {
            "doctype": "KTA Stock Label",
            "label_type": eff_label_type,
            "reference_doctype": reference_doctype or meta.get("reference_doctype"),
            "reference_name": reference_name or meta.get("reference_name"),
            "work_order": meta.get("work_order"),
            "material_index": meta.get("material_index"),
            "item_code": item_code,
            "item_name": item_info.get("item_name") or item_code,
            "item_group": item_info.get("item_group"),
            "uom": item_info.get("stock_uom"),
            "qty": flt(qty),
            "batch": batch_no,
            "sut_barcode": batch_no,
            "source_warehouse": source_warehouse,
            "target_warehouse": target_warehouse,
            "gr_posting_date": eff_gr_date,
            "quality_ref": eff_quality_ref,
            "supplier_delivery_note": eff_sdn,
            "do_not_split": 0,
        }
    )
    label_doc.flags.ignore_links = True
    label_doc.insert(ignore_permissions=True)
    return label_doc.name


def sync_batch_label_to_ledger_balance(item_code: str, batch_no: str) -> None:
    """Sync existing Depo Giriş / İş Emri Etiketi qty/warehouse to net ledger balance or delete at zero."""
    label_names = frappe.get_all(
        "KTA Stock Label",
        filters={
            "label_type": ["in", ["Depo Giriş Etiketi", "İş Emri Etiketi"]],
            "item_code": item_code,
        },
        or_filters=[["batch", "=", batch_no], ["sut_barcode", "=", batch_no]],
        pluck="name",
    )
    if not label_names:
        return

    balances = get_batch_ledger_balances(item_code, batch_no)
    total_qty = flt(sum(flt(b["qty"]) for b in balances))

    if total_qty > _EPSILON:
        positive_balances = [b for b in balances if flt(b["qty"]) > _EPSILON]
        best_wh = (
            max(positive_balances, key=lambda b: flt(b["qty"]))["warehouse"]
            if positive_balances
            else None
        )
        for label_name in label_names:
            updates = {"qty": total_qty}
            if best_wh:
                updates["target_warehouse"] = best_wh
            frappe.db.set_value("KTA Stock Label", label_name, updates)
        return

    delete_labels_with_print_logs(label_names)


def _resolve_source_valuation_rate(
    item_code: str,
    source_warehouse: str,
    posting_date: str,
    posting_time: str,
    total_split_qty: float,
    company: str | None,
    source_batch: str | None,
) -> float:
    rate = flt(
        get_incoming_rate(
            {
                "item_code": item_code,
                "warehouse": source_warehouse,
                "posting_date": posting_date,
                "posting_time": posting_time,
                "qty": -1 * flt(total_split_qty),
                "company": company,
                "batch_no": source_batch,
            },
            raise_error_if_no_rate=False,
        )
    )
    if rate > 0:
        return rate

    return flt(
        frappe.db.get_value(
            "Bin",
            {"item_code": item_code, "warehouse": source_warehouse},
            "valuation_rate",
        )
    )


def create_package_split_repack(
    item_code: str,
    source_warehouse: str,
    target_warehouse: str,
    source_batch: str | None,
    split_qtys: list[float],
    remarks: str | None = None,
    posting_date: str | None = None,
    ignore_reco_lock: bool = False,
) -> dict:
    """Create and submit a 1-source -> N-target Package Split (Repack) Stock Entry."""
    if not item_code or not source_warehouse or not target_warehouse:
        frappe.throw(_("Ürün, kaynak depo ve hedef depo zorunludur."))

    normalized_qtys = [flt(q) for q in (split_qtys or [])]
    if not normalized_qtys or any(q <= 0 for q in normalized_qtys):
        frappe.throw(
            _("Bölme miktarları boş olamaz ve tüm değerler sıfırdan büyük olmalıdır.")
        )

    total_split_qty = flt(sum(normalized_qtys))

    if source_batch:
        balances = get_batch_ledger_balances(item_code, source_batch)
        available = flt(
            sum(flt(b["qty"]) for b in balances if b["warehouse"] == source_warehouse)
        )
    else:
        available = flt(
            frappe.db.get_value(
                "Bin",
                {"item_code": item_code, "warehouse": source_warehouse},
                "actual_qty",
            )
        )

    if available + _EPSILON < total_split_qty:
        frappe.throw(
            _("Kaynak depoda yeterli stok yok. Mevcut: {0}, İstenen: {1}").format(
                available, total_split_qty
            )
        )

    source_meta: dict = {}
    if source_batch:
        source_meta = (
            frappe.db.get_value(
                "Batch",
                source_batch,
                list(_INHERITED_BATCH_FIELDS),
                as_dict=True,
            )
            or {}
        )
        if is_standard_kta_box_batch(source_batch):
            base_lot = extract_base_lot(source_batch)
        else:
            base_lot = generate_new_base_lot(
                item_code=item_code,
                reference_doctype=source_meta.get("reference_doctype"),
                reference_name=source_meta.get("reference_name"),
                manufacturing_date=source_meta.get("manufacturing_date"),
                supplier=source_meta.get("supplier"),
                expiry_date=source_meta.get("expiry_date"),
                stock_uom=source_meta.get("stock_uom"),
            )
    else:
        base_lot = generate_new_base_lot(item_code=item_code)

    created_batches = allocate_next_box_batches(
        base_lot=base_lot,
        count=len(normalized_qtys),
        item_code=item_code,
        source_meta=source_meta,
    )

    company = frappe.db.get_value(
        "Warehouse", source_warehouse, "company"
    ) or frappe.db.get_value("Warehouse", target_warehouse, "company")
    eff_posting_date = posting_date or today()
    eff_posting_time = nowtime()
    source_rate = _resolve_source_valuation_rate(
        item_code=item_code,
        source_warehouse=source_warehouse,
        posting_date=eff_posting_date,
        posting_time=eff_posting_time,
        total_split_qty=total_split_qty,
        company=company,
        source_batch=source_batch,
    )
    allow_zero = 1 if source_rate <= 0 else 0

    se = frappe.new_doc("Stock Entry")
    se.purpose = "Repack"
    se.stock_entry_type = "Package Split"
    se.company = company
    se.posting_date = eff_posting_date
    se.posting_time = eff_posting_time
    if remarks:
        se.remarks = remarks

    se.append(
        "items",
        {
            "item_code": item_code,
            "s_warehouse": source_warehouse,
            "qty": total_split_qty,
            "batch_no": source_batch,
            "use_serial_batch_fields": 1 if source_batch else 0,
            "allow_zero_valuation_rate": allow_zero,
        },
    )
    for target_batch, split_qty in zip(created_batches, normalized_qtys):
        se.append(
            "items",
            {
                "item_code": item_code,
                "t_warehouse": target_warehouse,
                "qty": split_qty,
                "batch_no": target_batch,
                "is_finished_item": 1,
                "use_serial_batch_fields": 1,
                "allow_zero_valuation_rate": allow_zero,
            },
        )

    prev_flag = getattr(frappe.flags, "kta_ignore_reco_lock", False)
    try:
        if ignore_reco_lock:
            frappe.flags.kta_ignore_reco_lock = True
        se.insert(ignore_permissions=True)
        se.submit()
    finally:
        if ignore_reco_lock:
            if prev_flag:
                frappe.flags.kta_ignore_reco_lock = prev_flag
            else:
                frappe.flags.pop("kta_ignore_reco_lock", None)

    if source_batch:
        sync_batch_label_to_ledger_balance(item_code, source_batch)

    return {
        "stock_entry": se.name,
        "base_lot": base_lot,
        "created_batches": [
            {"batch_no": batch_no, "qty": flt(qty)}
            for batch_no, qty in zip(created_batches, normalized_qtys)
        ],
    }
