import re

import frappe
from erpnext.stock.utils import get_incoming_rate
from frappe import _
from frappe.utils import cint, flt, getdate, nowtime, today

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
                elif se_type == "Package Merge":
                    meta["label_type"] = resolve_item_default_label_type(item_code)
                    meta["reference_doctype"] = "Stock Entry"
                    meta["reference_name"] = ref_name
                    if se_vals.get("posting_date"):
                        meta["gr_posting_date"] = str(se_vals.get("posting_date"))
                    meta["quality_ref"] = "KARMA LOT"
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


def _validate_active_leaf_warehouse(
    warehouse: str,
    expected_company: str | None = None,
    role_label: str = "Hedef",
) -> str:
    """Validate an active non-group warehouse and optional company match, returning its company."""
    clean_wh = (warehouse or "").strip()
    if not clean_wh:
        frappe.throw(
            _("{0} depo bilgisi zorunludur.").format(role_label),
            frappe.ValidationError,
        )

    wh_meta = frappe.db.get_value(
        "Warehouse",
        clean_wh,
        ["name", "company", "is_group", "disabled"],
        as_dict=True,
    )
    if not wh_meta:
        frappe.throw(
            _("{0} depo bulunamadı: {1}").format(role_label, clean_wh),
            frappe.ValidationError,
        )
    if cint(wh_meta.is_group) or cint(wh_meta.disabled):
        frappe.throw(
            _("{0} depo işlem için uygun değil: {1}").format(role_label, clean_wh),
            frappe.ValidationError,
        )
    if expected_company and wh_meta.company != expected_company:
        frappe.throw(
            _("Kaynak ve hedef depolar aynı şirket altında olmalıdır."),
            frappe.ValidationError,
        )
    return wh_meta.company


def _normalize_merge_sources(
    item_code: str,
    source_boxes: list[dict],
    expected_company: str,
) -> list[dict]:
    """Validate source boxes, prevent duplicates, and resolve full-box ledger balances."""
    if not isinstance(source_boxes, (list, tuple)) or len(source_boxes) < 2:
        frappe.throw(
            _("Birleştirme için en az 2 kaynak koli seçilmelidir."),
            frappe.ValidationError,
        )

    seen_pairs: set[tuple[str, str]] = set()
    normalized: list[dict] = []
    for box in source_boxes:
        if not isinstance(box, dict):
            frappe.throw(
                _("Geçersiz kaynak koli girdisi."),
                frappe.ValidationError,
            )
        batch_no = str(box.get("batch_no") or "").strip()
        warehouse = str(box.get("warehouse") or "").strip()
        if not batch_no or not warehouse:
            frappe.throw(
                _("Her kaynak koli için parti ve depo bilgisi zorunludur."),
                frappe.ValidationError,
            )

        pair = (batch_no, warehouse)
        if pair in seen_pairs:
            frappe.throw(
                _("Aynı kaynak koli birden fazla kez eklenemez: {0}").format(batch_no),
                frappe.ValidationError,
            )
        seen_pairs.add(pair)

        batch_item = frappe.db.get_value("Batch", batch_no, "item")
        if not batch_item:
            frappe.throw(
                _("Parti bulunamadı: {0}").format(batch_no),
                frappe.ValidationError,
            )
        if batch_item != item_code:
            frappe.throw(
                _("Farklı ürün kodlarına ait koliler birleştirilemez."),
                frappe.ValidationError,
            )

        _validate_active_leaf_warehouse(
            warehouse, expected_company=expected_company, role_label="Kaynak"
        )
        balances = get_batch_ledger_balances(item_code, batch_no)
        available_qty = flt(
            next(
                (b.get("qty") for b in balances if b.get("warehouse") == warehouse), 0.0
            )
        )
        if available_qty <= _EPSILON:
            frappe.throw(
                _(
                    "Kaynak depoda bu parti için kullanılabilir stok bulunmamaktadır: {0}"
                ).format(batch_no),
                frappe.ValidationError,
            )

        supplied_qty = box.get("qty")
        if (
            supplied_qty is not None
            and supplied_qty != ""
            and abs(flt(supplied_qty) - available_qty) > _EPSILON
        ):
            frappe.throw(
                _(
                    "Koli birleştirmede kaynak kolinin depodaki tam bakiyesi kullanılmalıdır: {0}"
                ).format(batch_no),
                frappe.ValidationError,
            )

        normalized.append(
            {
                "batch_no": batch_no,
                "warehouse": warehouse,
                "qty": available_qty,
            }
        )

    return normalized


def _analyze_merge_lot_and_target(
    item_code: str,
    normalized_sources: list[dict],
    allow_mixed_lots: bool | int,
) -> tuple[bool, str, str, list[dict]]:
    """Detect same-lot vs mixed-lot merge, enforce confirmation, and mint 1 target box batch."""
    distinct_batches = list(dict.fromkeys(s["batch_no"] for s in normalized_sources))
    all_standard = all(is_standard_kta_box_batch(b) for b in distinct_batches)
    base_lots = {extract_base_lot(b) for b in distinct_batches}
    is_mixed_lot = (not all_standard) or (len(base_lots) > 1)

    if is_mixed_lot and not cint(allow_mixed_lots):
        frappe.throw(
            _(
                "Farklı ana lotlara ait kolileri birleştirmek için karma lot onayı gereklidir."
            ),
            frappe.ValidationError,
        )

    batch_metas = [
        frappe.db.get_value("Batch", b, list(_INHERITED_BATCH_FIELDS), as_dict=True)
        or {}
        for b in distinct_batches
    ]
    expiry_dates = [
        getdate(m.get("expiry_date")) for m in batch_metas if m.get("expiry_date")
    ]
    min_expiry = str(min(expiry_dates)) if expiry_dates else None

    if not is_mixed_lot:
        base_lot = next(iter(base_lots))
        source_meta: dict = {}
        for field in _INHERITED_BATCH_FIELDS:
            source_meta[field] = next(
                (m.get(field) for m in batch_metas if m.get(field)), None
            )
        if min_expiry:
            source_meta["expiry_date"] = min_expiry
    else:
        stock_uom = next(
            (m.get("stock_uom") for m in batch_metas if m.get("stock_uom")), None
        ) or frappe.db.get_value("Item", item_code, "stock_uom")
        base_lot = generate_new_base_lot(
            item_code=item_code, expiry_date=min_expiry, stock_uom=stock_uom
        )
        source_meta = {"expiry_date": min_expiry, "stock_uom": stock_uom}

    target_batch = allocate_next_box_batches(
        base_lot=base_lot,
        count=1,
        item_code=item_code,
        source_meta=source_meta,
    )[0]
    return is_mixed_lot, base_lot, target_batch, batch_metas


def _build_merge_audit_remarks(
    item_uom: str,
    normalized_sources: list[dict],
    target_batch: str,
    target_warehouse: str,
    total_qty: float,
    is_mixed_lot: bool,
    remarks: str | None = None,
) -> str:
    """Build deterministic audit trail text for Stock Entry.remarks and Batch.description."""
    audit_prefix = "[KARMA LOT BİRLEŞTİRME]" if is_mixed_lot else "[KOLİ BİRLEŞTİRME]"
    src_parts = ", ".join(
        f"{s['batch_no']} ({flt(s['qty'])} {item_uom} @ {s['warehouse']})"
        for s in normalized_sources
    )
    audit_line = (
        f"{audit_prefix} Kaynaklar: {src_parts} -> "
        f"Hedef: {target_batch} ({total_qty} {item_uom} @ {target_warehouse})"
    )
    if remarks:
        return f"{remarks}\n{audit_line}"
    return audit_line


def create_package_merge_repack(
    item_code: str,
    source_boxes: list[dict],
    target_warehouse: str,
    allow_mixed_lots: bool = False,
    remarks: str | None = None,
    posting_date: str | None = None,
    ignore_reco_lock: bool = False,
) -> dict:
    """Create and submit a N-source -> 1-target Package Merge (Repack) Stock Entry."""
    clean_item = (item_code or "").strip()
    clean_target_wh = (target_warehouse or "").strip()
    if not clean_item or not clean_target_wh:
        frappe.throw(
            _("Ürün ve hedef depo bilgileri zorunludur."), frappe.ValidationError
        )

    company = _validate_active_leaf_warehouse(clean_target_wh, role_label="Hedef")
    normalized_sources = _normalize_merge_sources(clean_item, source_boxes, company)

    sp_name = f"pkg_merge_{frappe.generate_hash('', 8)}"
    frappe.db.savepoint(sp_name)
    try:
        is_mixed_lot, base_lot, target_batch, batch_metas = (
            _analyze_merge_lot_and_target(
                clean_item, normalized_sources, allow_mixed_lots
            )
        )

        eff_posting_date = posting_date or today()
        eff_posting_time = nowtime()
        for src in normalized_sources:
            src["rate"] = _resolve_source_valuation_rate(
                item_code=clean_item,
                source_warehouse=src["warehouse"],
                posting_date=eff_posting_date,
                posting_time=eff_posting_time,
                total_split_qty=src["qty"],
                company=company,
                source_batch=src["batch_no"],
            )

        total_qty = flt(sum(s["qty"] for s in normalized_sources), 6)
        weighted_rate = (
            flt(sum(s["qty"] * s["rate"] for s in normalized_sources) / total_qty)
            if total_qty > 0
            else 0.0
        )
        item_uom = (
            frappe.db.get_value("Item", clean_item, "stock_uom")
            or batch_metas[0].get("stock_uom")
            or "Nos"
        )
        final_remarks = _build_merge_audit_remarks(
            item_uom=item_uom,
            normalized_sources=normalized_sources,
            target_batch=target_batch,
            target_warehouse=clean_target_wh,
            total_qty=total_qty,
            is_mixed_lot=is_mixed_lot,
            remarks=remarks,
        )

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Repack"
        se.stock_entry_type = "Package Merge"
        se.company = company
        se.posting_date = eff_posting_date
        se.posting_time = eff_posting_time
        se.remarks = final_remarks

        for src in normalized_sources:
            se.append(
                "items",
                {
                    "item_code": clean_item,
                    "s_warehouse": src["warehouse"],
                    "qty": src["qty"],
                    "batch_no": src["batch_no"],
                    "use_serial_batch_fields": 1,
                    "allow_zero_valuation_rate": 1 if src["rate"] <= 0 else 0,
                },
            )
        se.append(
            "items",
            {
                "item_code": clean_item,
                "t_warehouse": clean_target_wh,
                "qty": total_qty,
                "batch_no": target_batch,
                "is_finished_item": 1,
                "use_serial_batch_fields": 1,
                "basic_rate": max(0.0, weighted_rate),
                "allow_zero_valuation_rate": 1 if weighted_rate <= 0 else 0,
            },
        )

        prev_flag = getattr(frappe.flags, "kta_ignore_reco_lock", False)
        try:
            if ignore_reco_lock:
                frappe.flags.kta_ignore_reco_lock = True
            se.insert(ignore_permissions=True)
            batch_updates: dict[str, object] = {"description": final_remarks}
            if is_mixed_lot:
                batch_updates["reference_doctype"] = "Stock Entry"
                batch_updates["reference_name"] = se.name
            frappe.db.set_value(
                "Batch", target_batch, batch_updates, update_modified=False
            )
            se.submit()
        finally:
            if ignore_reco_lock:
                if prev_flag:
                    frappe.flags.kta_ignore_reco_lock = prev_flag
                else:
                    frappe.flags.pop("kta_ignore_reco_lock", None)

        for src_batch in dict.fromkeys(s["batch_no"] for s in normalized_sources):
            sync_batch_label_to_ledger_balance(clean_item, src_batch)
    except Exception:
        frappe.db.rollback(save_point=sp_name)
        raise

    return {
        "stock_entry": se.name,
        "item_code": clean_item,
        "base_lot": base_lot,
        "target_batch": target_batch,
        "target_warehouse": clean_target_wh,
        "total_qty": total_qty,
        "is_mixed_lot": is_mixed_lot,
        "remarks": final_remarks,
        "source_batches": [s["batch_no"] for s in normalized_sources],
    }
