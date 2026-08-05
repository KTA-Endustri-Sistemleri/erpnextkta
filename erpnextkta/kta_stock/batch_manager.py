import frappe
from frappe.utils import flt, cint
from frappe import _

class BatchSplitManager:
    @staticmethod
    def get_base_batch_from_work_order(work_order, item_code=None):
        if not work_order:
            return None

        filters = {"reference_doctype": "Work Order", "reference_name": work_order}
        if item_code:
            filters["item"] = item_code

        base_batches = frappe.get_all(
            "Batch",
            filters=filters,
            pluck="name",
            order_by="creation asc",
            limit_page_length=1,
        )

        return base_batches[0] if base_batches else None

    @staticmethod
    def get_bins_of_item(item_code, empty=False):
        """Returns warehouse list for a given item where actual_qty is > 0 (or == 0 if empty=True)."""
        filters = {"item_code": item_code}
        if empty:
            filters["actual_qty"] = 0
        else:
            filters["actual_qty"] = [">", 0]

        return frappe.get_all(
            "Bin",
            filters=filters,
            pluck="warehouse"
        )

    @staticmethod
    def get_sabe_parents_of_bins_for_batch(bins, batch_no):
        """Returns parent Serial and Batch Bundle names for given warehouses and batch."""
        if not bins:
            return []
            
        return frappe.get_all(
            "Serial and Batch Entry",
            filters={
                "warehouse": ["in", bins],
                "batch_no": batch_no,
                "parenttype": "Serial and Batch Bundle",
                "parentfield": "entries",
                "docstatus": 1
            },
            pluck="parent"
        )

    @staticmethod
    def get_warehouse_quantity_for_sabe_parents(sabe_parents):
        """Returns warehouse-wise quantity totals for given Serial and Batch Bundle parents."""
        if not sabe_parents:
            return []
            
        return frappe.get_all(
            "Stock Ledger Entry",
            filters={
                "serial_and_batch_bundle": ["in", sabe_parents],
                "docstatus": 1,
                "is_cancelled": 0
            },
            fields=["warehouse", "sum(actual_qty) as balance_qty"],
            group_by="warehouse"
        )

    @staticmethod
    def get_base_batch_for_work_order(work_order, item_code=None):
        return BatchSplitManager.get_base_batch_from_work_order(work_order, item_code)

    @staticmethod
    def _get_single_inward_batch_entry(bundle_name):
        entries = frappe.get_all(
            "Serial and Batch Entry",
            filters={
                "parent": bundle_name,
                "parenttype": "Serial and Batch Bundle",
                "is_outward": 0,
            },
            fields=["batch_no", "qty"],
            order_by="idx asc",
        )
        return entries[0] if len(entries) == 1 else None

    @staticmethod
    def _get_customer_packaging_qty(item_code):
        result = frappe.get_all(
            "Item Customer Detail",
            filters={
                "parent": item_code,
                "parenttype": "Item",
                "parentfield": "customer_items",
            },
            fields=["max(custom_musteri_paketleme_miktari) as packaging_qty"],
            limit=1,
        )
        return flt(result[0].packaging_qty or 0) if result else 0

    @staticmethod
    def _get_last_batch_number_for_base(base_batch_number):
        if not base_batch_number: return 0
        prefix_len = len(base_batch_number)
        total_len = prefix_len + 4

        last_batch = frappe.db.sql("""
            SELECT name FROM `tabBatch`
            WHERE name LIKE %s
            AND LENGTH(name) = %s
            ORDER BY name DESC LIMIT 1
        """, (f"{base_batch_number}%", total_len))

        if not last_batch:
            return 0

        suffix = last_batch[0][0][prefix_len:]
        return int(suffix) if suffix.isdigit() else 0

    @staticmethod
    def _create_split_batch_record(row, parent_doc, base_batch_number, pack_no, is_manufacturing):
        batch_id = f"{base_batch_number}{pack_no:04d}"
        if frappe.db.exists("Batch", batch_id):
            return batch_id

        batch_doc = frappe.get_doc({
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": row.item_code,
            "stock_uom": row.get("stock_uom"),
            "description": row.get("description"),
            "batch_qty": 0,
        })

        if is_manufacturing:
            batch_doc.update({
                "reference_doctype": "Work Order",
                "reference_name": parent_doc.work_order,
                "manufacturing_date": parent_doc.get("posting_date"),
            })
        else:
            batch_doc.update({
                "supplier": parent_doc.get("supplier"),
                "reference_doctype": "Purchase Receipt",
                "reference_name": parent_doc.name,
                "manufacturing_date": row.get("manufacturing_date") or parent_doc.get("posting_date"),
                "expiry_date": row.get("expiry_date"),
            })

        batch_doc.flags.ignore_permissions = True
        batch_doc.insert()
        return batch_doc.name

    @staticmethod
    def _prepare_batch_allocations(row, base_source_doc, base_batch_number, is_manufacturing=False):
        if is_manufacturing:
            qty = flt(row.get("transfer_qty") or row.get("qty") or row.get("stock_qty") or 0)
            split_qty = BatchSplitManager._get_customer_packaging_qty(row.item_code)
        else:
            qty = flt(row.stock_qty or 0)
            split_qty = flt(row.custom_split_qty or 0)

        if not qty:
            return []

        if not is_manufacturing and row.get("custom_do_not_split"):
            return [{
                "batch_no": base_batch_number,
                "qty": qty,
                "sut_code": f"{base_batch_number}{0:04d}",
                "pack_no": 0,
            }]

        if split_qty <= 0:
            return []

        remainder_qty = qty % split_qty
        num_packs = cint(qty // split_qty)
        
        total_packs = num_packs + (1 if remainder_qty > 0 else 0)
        
        if total_packs > 300:
            frappe.throw(_("Miktar ve paketleme oranına göre çok fazla ({0}) paket/batch oluşmaktadır. Lütfen transfer miktarını veya müşteri paketleme miktarını kontrol ediniz. (Maks: 300)").format(total_packs))
        allocations = []

        start_pack_no = 1
        if is_manufacturing:
            start_pack_no = BatchSplitManager._get_last_batch_number_for_base(base_batch_number) + 1

        for i in range(num_packs):
            pack_no = start_pack_no + i
            batch_no = BatchSplitManager._create_split_batch_record(row, base_source_doc, base_batch_number, pack_no, is_manufacturing)
            allocations.append({
                "batch_no": batch_no,
                "qty": split_qty,
                "sut_code": f"{base_batch_number}{pack_no:04d}",
                "pack_no": pack_no,
            })

        if remainder_qty > 0:
            pack_no = start_pack_no + num_packs
            batch_no = BatchSplitManager._create_split_batch_record(row, base_source_doc, base_batch_number, pack_no, is_manufacturing)
            allocations.append({
                "batch_no": batch_no,
                "qty": remainder_qty,
                "sut_code": f"{base_batch_number}{pack_no:04d}",
                "pack_no": pack_no,
            })

        return allocations

    @staticmethod
    def _get_reliable_incoming_rate(row, bundle_doc):
        if bundle_doc.name and flt(bundle_doc.docstatus) == 1:
            sle_rate = frappe.db.get_value(
                "Stock Ledger Entry",
                {
                    "serial_and_batch_bundle": bundle_doc.name,
                    "actual_qty": (">", 0),
                    "is_cancelled": 0,
                    "docstatus": 1,
                },
                "incoming_rate",
            )
            if flt(sle_rate):
                return flt(sle_rate)

        for entry in bundle_doc.get("entries", []):
            if flt(entry.get("incoming_rate")):
                return flt(entry.incoming_rate)

        if row.doctype == "Purchase Receipt Item":
            db_values = frappe.db.get_value("Purchase Receipt Item", row.name, ["valuation_rate", "rate", "base_rate"], as_dict=True)
            if db_values:
                rate = flt(db_values.valuation_rate) or flt(db_values.rate) or flt(db_values.base_rate)
                if rate: return rate
        elif row.doctype == "Stock Entry Detail":
            db_values = frappe.db.get_value("Stock Entry Detail", row.name, ["valuation_rate", "basic_rate"], as_dict=True)
            if db_values:
                rate = flt(db_values.valuation_rate) or flt(db_values.basic_rate)
                if rate: return rate

        rate = flt(row.get("valuation_rate")) or flt(row.get("rate"))
        if rate: return rate

        item_valuation = frappe.db.get_value("Item", row.item_code, "valuation_rate")
        if flt(item_valuation): return flt(item_valuation)

        last_purchase_rate = frappe.db.get_value("Item", row.item_code, "last_purchase_rate")
        if flt(last_purchase_rate): return flt(last_purchase_rate)

        return 0.0

    @staticmethod
    def _recalculate_batch_qty(batch_no):
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(sabe.qty), 0) as total_qty
            FROM `tabSerial and Batch Entry` sabe
            JOIN `tabSerial and Batch Bundle` sabb ON sabe.parent = sabb.name
            WHERE sabe.batch_no = %s
              AND sabb.is_cancelled = 0
              AND sabb.docstatus = 1
        """, batch_no)
        new_qty = flt(result[0][0]) if result else 0.0
        frappe.db.set_value("Batch", batch_no, "batch_qty", new_qty, update_modified=False)

    @staticmethod
    def _update_bundle_safely(row, allocations):
        bundle_name = row.get("serial_and_batch_bundle")
        if not bundle_name:
            return

        bundle_doc = frappe.get_doc("Serial and Batch Bundle", bundle_name)
        bundle_doc.flags.ignore_validate = True
        bundle_doc.flags.ignore_validate_update_after_submit = True
        bundle_doc.flags.ignore_links = True
        
        warehouse = row.get("warehouse") or row.get("t_warehouse") or row.get("s_warehouse")
        if not warehouse:
            frappe.throw(_("{0}. satır için depo bulunamadı").format(row.name))

        original_incoming_rate = BatchSplitManager._get_reliable_incoming_rate(row, bundle_doc)

        bundle_doc.set("entries", [])
        total_qty = 0
        total_amount = 0.0
        for alloc in allocations:
            alloc_qty = flt(alloc["qty"])
            stock_value_diff = alloc_qty * original_incoming_rate
            bundle_doc.append("entries", {
                "batch_no": alloc["batch_no"],
                "qty": alloc_qty,
                "warehouse": warehouse,
                "is_outward": 0,
                "incoming_rate": original_incoming_rate,
                "stock_value_difference": stock_value_diff,
            })
            total_qty += alloc_qty
            total_amount += stock_value_diff
        
        bundle_doc.total_qty = total_qty
        bundle_doc.total_amount = total_amount
        if total_qty:
            bundle_doc.avg_rate = total_amount / total_qty
        
        bundle_doc.save(ignore_permissions=True)
        frappe.clear_document_cache("Serial and Batch Bundle", bundle_name)

        for alloc in allocations:
            child_batch = alloc["batch_no"]
            child_qty = flt(alloc["qty"])
            current_qty = flt(frappe.db.get_value("Batch", child_batch, "batch_qty"))
            frappe.db.set_value("Batch", child_batch, "batch_qty", current_qty + child_qty, update_modified=False)

        if row.get("batch_no"):
            BatchSplitManager._recalculate_batch_qty(row.batch_no)

    @staticmethod
    def split_manufacturing_batches(stock_entry):
        if stock_entry.flags.in_split_process:
            return
        
        stock_entry.flags.in_split_process = True
        doc = stock_entry if not isinstance(stock_entry, str) else frappe.get_doc("Stock Entry", stock_entry)

        if not doc or doc.doctype != "Stock Entry" or doc.get("purpose") != "Manufacture":
            return

        packaging_cache = {}
        for row in doc.get("items", []):
            if not row.get("is_finished_item"):
                continue

            bundle_name = row.get("serial_and_batch_bundle")
            if not bundle_name:
                continue

            base_entry = BatchSplitManager._get_single_inward_batch_entry(bundle_name)
            if not base_entry or not base_entry.get("batch_no"):
                continue

            base_batch_prefix = BatchSplitManager.get_base_batch_for_work_order(doc.work_order, row.item_code)
            if not base_batch_prefix:
                base_batch_prefix = base_entry.get("batch_no")

            split_qty = packaging_cache.get(row.item_code)
            if split_qty is None:
                split_qty = BatchSplitManager._get_customer_packaging_qty(row.item_code)
                packaging_cache[row.item_code] = split_qty

            if not split_qty:
                continue

            allocations = BatchSplitManager._prepare_batch_allocations(
                row=row,
                base_source_doc=doc,
                base_batch_number=base_batch_prefix,
                is_manufacturing=True
            )

            if not allocations:
                continue

            BatchSplitManager._update_bundle_safely(row, allocations)

    @staticmethod
    def split_purchase_receipt_batches(row):
        """
        Purchase Receipt Item satırının batch'ini böler.
        Bundle'ı günceller ve allocation listesini döner.
        Etiket oluşturma sorumluluğu çağırana aittir.
        """
        if row.doctype != "Purchase Receipt Item":
            return []

        batch_number = None
        if row.get("serial_and_batch_bundle"):
            batch_number = frappe.db.get_value(
                "Serial and Batch Entry",
                {"parent": row.serial_and_batch_bundle, "is_outward": 0},
                "batch_no"
            )

            if not batch_number:
                batch_number = frappe.db.get_value(
                    "Serial and Batch Entry",
                    {"parent": row.serial_and_batch_bundle, "is_outward": 1},
                    "batch_no"
                )

        if not batch_number:
            batch_number = row.get("batch_no")

        if not batch_number:
            batch_number = frappe.db.get_value("Batch", {
                "reference_name": row.parent,
                "item": row.item_code
            }, "name")

        if not batch_number:
            frappe.log_error(f"Batch bulunamadı: Satır {row.idx}, Ürün {row.item_code}", "KTA Split Error")
            return []

        purchase_receipt = frappe.get_cached_doc("Purchase Receipt", row.parent)
        allocations = BatchSplitManager._prepare_batch_allocations(row, purchase_receipt, batch_number)

        if not allocations:
            return []

        BatchSplitManager._update_bundle_safely(row, allocations)
        return allocations

    @staticmethod
    def resplit_submitted_manufacturing_batches(stock_entry):
        doc = frappe.get_doc("Stock Entry", stock_entry)
        if doc.purpose != "Manufacture":
            return

        for row in doc.get("items"):
            if not row.is_finished_item:
                continue

            bundle_name = row.get("serial_and_batch_bundle")
            if not bundle_name:
                continue

            base_entry = BatchSplitManager._get_single_inward_batch_entry(bundle_name)
            if not base_entry:
                entries = frappe.get_all("Serial and Batch Entry", filters={"parent": bundle_name, "is_outward": 0}, fields=["batch_no"], order_by="idx asc", limit=1)
                if not entries: continue
                base_entry = entries[0]
                
            base_batch_prefix = BatchSplitManager.get_base_batch_for_work_order(doc.work_order, row.item_code)
            if not base_batch_prefix:
                base_batch_prefix = base_entry.get("batch_no")

            split_qty = BatchSplitManager._get_customer_packaging_qty(row.item_code)
            if not split_qty:
                continue

            allocations = BatchSplitManager._prepare_batch_allocations(
                row=row,
                base_source_doc=doc,
                base_batch_number=base_batch_prefix,
                is_manufacturing=True
            )

            if not allocations:
                continue

            old_entries = frappe.get_all("Serial and Batch Entry", filters={"parent": bundle_name, "is_outward": 0}, fields=["batch_no"])
            BatchSplitManager._update_bundle_safely(row, allocations)
            
            new_batches = [a["batch_no"] for a in allocations]
            for old in old_entries:
                if old.batch_no not in new_batches:
                    frappe.db.set_value("Batch", old.batch_no, "batch_qty", 0, update_modified=False)


@frappe.whitelist()
def check_packaging_quantity_mismatch(stock_entry):
    stock_entry_doc = frappe.get_doc("Stock Entry", stock_entry)
    if stock_entry_doc.purpose != "Manufacture":
        return {"mismatch": False}

    for row in stock_entry_doc.get("items"):
        if not row.is_finished_item:
            continue
        
        bundle_name = row.get("serial_and_batch_bundle")
        if not bundle_name:
            continue
            
        packaging_qty = BatchSplitManager._get_customer_packaging_qty(row.item_code)
        if not packaging_qty:
            continue
            
        entries = frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": bundle_name, "is_outward": 0},
            fields=["qty"],
            order_by="idx asc",
            limit=2
        )
        
        if entries:
            first_pack_qty = flt(entries[0].qty)
            if first_pack_qty != packaging_qty and (len(entries) > 1 or first_pack_qty != row.qty):
                return {"mismatch": True, "item": row.item_code}

    return {"mismatch": False}


@frappe.whitelist()
def find_bins_of_sut(sut, mobil):
    from erpnextkta.kta_stock.label_manager import LabelPrinter

    label = LabelPrinter.get_label_item_batch(sut)
    if not label:
        frappe.throw(frappe._("SUT barkodu için etiket bulunamadı: {0}").format(sut))

    sabe_parents = BatchSplitManager.get_sabe_parents_of_bins_for_batch(
        BatchSplitManager.get_bins_of_item(label.item_code), label.batch
    )
    sle_entries = BatchSplitManager.get_warehouse_quantity_for_sabe_parents(sabe_parents)

    if not sle_entries:
        frappe.throw(frappe._("SUT için Stok Defteri Kaydı bulunamadı: {0}").format(sut))

    for sle_entry in sle_entries:
        child = frappe.new_doc("KTA Mobil Depo Kalemi")
        child.update({
            "parent": mobil,
            "parentfield": "mobile_items",
            "parenttype": "KTA Mobil Depo",
            "sut_barcode": sut,
            "item_code": label.item_code,
            "batch": label.batch,
            "source_warehouse": sle_entry.warehouse,
            "qty": sle_entry.balance_qty
        })
        child.insert()

