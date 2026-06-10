import frappe
from kta_system_utils.kta_zebra_utils.printer_manager import ZebraPrinterManager
from erpnextkta.kta_stock.batch_manager import BatchSplitManager

class LabelPrinter:
    @staticmethod
    def print_pr_labels(gr_number=None, label=None, q_ref=None):
        if not gr_number and not label and not q_ref:
            frappe.msgprint("Either `gr_number`, `label` or 'q_ref' must be provided.")
            return

        query_filter = {"do_not_split": 0, "label_type": "Depo Giriş Etiketi"}
        if gr_number:
            query_filter["reference_name"] = gr_number
        elif label:
            query_filter["name"] = label
        elif q_ref:
            query_filter["quality_ref"] = q_ref

        zebra_printer = ZebraPrinterManager.get_printer_for_user()
        if not zebra_printer:
            labels_to_log = frappe.get_all("KTA Stock Label", filters=query_filter, fields=["name"])
            for lbl in labels_to_log:
                ZebraPrinterManager.create_print_log(
                    label_doctype="KTA Stock Label",
                    label_name=lbl.name,
                    printer=None,
                    status="Failed",
                    zpl=None,
                    error="Kullanıcı için varsayılan yazıcı bulunamadı"
                )
            return
            
        for data in frappe.get_all(
                doctype="KTA Stock Label",
                filters=query_filter,
                fields=[
                    "name", "item_code", "item_name", "item_group", "qty", "uom",
                    "supplier_delivery_note", "sut_barcode", "gr_posting_date", "quality_ref", "batch", "reference_name"
                ]
        ):
            # Compatibility map for old ZPL templates
            data.gr_number = data.reference_name
            data.qty = ZebraPrinterManager.format_qty(data.qty)
            formatted_data = ZebraPrinterManager.format_data(data.label_type or "Depo Giriş Etiketi", data)
            zebra_printer.send(formatted_data, label_doctype="KTA Stock Label", label_name=data.name)
            
            curr_count = frappe.db.get_value("KTA Stock Label", data.name, "print_count") or 0
            frappe.db.set_value(
                "KTA Stock Label",
                data.name,
                {
                    "print_count": curr_count + 1,
                    "last_printed_at": frappe.utils.now(),
                    "last_printed_by": frappe.session.user or "Administrator"
                },
                update_modified=False
            )
        frappe.db.commit()

    @staticmethod
    def print_split_pr_labels(label=None):
        if not label:
            frappe.msgprint("`label` must be provided.")
            return

        split_query_filter = {"parent": label}
        splits = frappe.get_all(
            doctype="KTA Stock Label Split",
            filters=split_query_filter,
            fields=["idx", "qty"]
        )

        query_filter = {"do_not_split": 1, "name": label}
        label_data = frappe.db.get_value(
            doctype="KTA Stock Label",
            filters=query_filter,
            fieldname=[
                "name", "item_code", "item_name", "item_group", "qty", "uom",
                "supplier_delivery_note", "batch", "sut_barcode", "gr_posting_date", "quality_ref", "reference_name"
            ],
            as_dict=True
        )
        if not label_data: return

        zebra_printer = ZebraPrinterManager.get_printer_for_user()
        if not zebra_printer:
            ZebraPrinterManager.create_print_log(
                label_doctype="KTA Stock Label",
                label_name=label,
                printer=None,
                status="Failed",
                zpl=None,
                error="Kullanıcı için varsayılan yazıcı bulunamadı"
            )
            return

        label_data.gr_number = label_data.reference_name
        base_batch = label_data.batch[:7] if label_data.batch and len(label_data.batch) > 7 else label_data.batch
        for split in splits:
            label_data.qty = ZebraPrinterManager.format_qty(split.qty)
            label_data.batch = base_batch
            label_data.sut_barcode = f"{base_batch}{split.idx:04d}"
            formatted_data = ZebraPrinterManager.format_data(label_data.label_type or "Depo Giriş Etiketi", label_data)
            zebra_printer.send(formatted_data, label_doctype="KTA Stock Label", label_name=label_data.name)

        curr_count = frappe.db.get_value("KTA Stock Label", label, "print_count") or 0
        frappe.db.set_value(
            "KTA Stock Label",
            label,
            {
                "print_count": curr_count + 1,
                "last_printed_at": frappe.utils.now(),
                "last_printed_by": frappe.session.user or "Administrator"
            },
            update_modified=False
        )
        frappe.db.commit()

    @staticmethod
    def get_details_of_wo_for_label(work_order):
        work_order_doc = frappe.get_doc("Work Order", work_order)
        bom_doc = frappe.get_doc("BOM", work_order_doc.bom_no)

        material_index = "-"
        meta = frappe.get_meta("BOM")
        if meta.has_field("custom_musteri_indeksi_no"):
            material_index = bom_doc.get("custom_musteri_indeksi_no")

        musteri_paketleme_miktari = frappe.db.get_value(
            doctype="Item Customer Detail",
            filters={
                "parent": work_order_doc.production_item,
                "parenttype": "Item",
                "parentfield": "customer_items"
            },
            fieldname=["max(custom_musteri_paketleme_miktari) as musteri_paketleme_miktari"]
        )

        if not musteri_paketleme_miktari:
            frappe.throw(f"No custom_musteri_paketleme_miktari found for Item: {work_order_doc.production_item}")
            return None

        return {
            "work_order": work_order_doc.name,
            "description": work_order_doc.description,
            "stock_uom": work_order_doc.stock_uom,
            "production_item": work_order_doc.production_item,
            "material_index": material_index,
            "musteri_paketleme_miktari": musteri_paketleme_miktari
        }

    @staticmethod
    def print_wo_label(work_order_details, stock_entry):
        stock_entry_detail = frappe.get_all(
            doctype="Stock Entry Detail",
            filters={
                "parent": stock_entry,
                "parenttype": "Stock Entry",
                "parentfield": "items",
                "item_code": work_order_details.get("production_item"),
                "is_finished_item": 1,
                "docstatus": 1,
                "t_warehouse": ["is", "set"]
            },
            fields=["name"],
            as_list=True
        )

        if len(stock_entry_detail) > 1:
            frappe.throw(f"More than one Inward Type of Transaction found for Stock Entry: {stock_entry}")
            return
        if not stock_entry_detail: return

        stock_entry_detail_doc = frappe.get_doc("Stock Entry Detail", stock_entry_detail[0])
        stock_entry_doc = frappe.get_doc("Stock Entry", stock_entry)

        destination_warehouse = stock_entry_doc.get("to_warehouse") or stock_entry_detail_doc.get("t_warehouse")

        batch_no = None
        if stock_entry_detail_doc.get("serial_and_batch_bundle"):
            batch_no = frappe.db.get_value(
                "Serial and Batch Entry",
                filters={
                    "parent": stock_entry_detail_doc.serial_and_batch_bundle,
                    "parenttype": "Serial and Batch Bundle",
                    "parentfield": "entries",
                    "is_outward": 0,
                    "warehouse": stock_entry_detail_doc.t_warehouse,
                    "batch_no": ["is", "set"],
                    "docstatus": 1
                },
                fieldname="batch_no"
            )

        base_batch_no = BatchSplitManager.get_base_batch_from_work_order(work_order_details.get("work_order")) or batch_no

        data_name = frappe.db.get_value("KTA Stock Label", {"reference_doctype": "Stock Entry", "reference_name": stock_entry}, "name")
        if data_name:
            data = frappe.get_doc("KTA Stock Label", data_name)
        else:
            data = frappe.get_doc({
                'doctype': "KTA Stock Label",
                'label_type': "İş Emri Etiketi",
                'reference_doctype': "Stock Entry",
                'reference_name': stock_entry,
                'item_code': work_order_details.get("production_item"),
                'item_name': work_order_details.get("description"),
                'material_index': work_order_details.get("material_index"),
                'gr_posting_date': stock_entry_doc.get("posting_date"),
                'source_warehouse': stock_entry,
                'target_warehouse': destination_warehouse,
                'uom': work_order_details.get("stock_uom"),
                'batch': base_batch_no,
                'qty': qty,
                'sut_barcode': sut,
                'print_count': 1,
                'last_printed_at': frappe.utils.now(),
                'last_printed_by': frappe.session.user or "Administrator"
            })
            data.insert(ignore_permissions=True)
            
            # Legacy mapping for ZPL
            data.material_number = data.item_code
            data.material_description = data.item_name
            data.work_order = work_order_details.get("work_order")
            data.gr_number = stock_entry
            data.gr_source_warehouse = data.source_warehouse
            data.to_warehouse = data.target_warehouse
            data.stock_uom = data.uom
            data.batch_no = data.batch
            data.sut_no = data.sut_barcode
            data.print_date = frappe.utils.nowdate()
            data.qty = ZebraPrinterManager.format_qty(data.qty)

            formatted_data = ZebraPrinterManager.format_data(data.label_type or "İş Emri Etiketi", data)
            zebra_printer.send(formatted_data, label_doctype="KTA Stock Label", label_name=data.name)

        if batch_entries:
            for entry in batch_entries:
                save_and_print_wo_label(entry.get("qty"), entry.get("batch_no"))
        else:
            musteri_paketleme_miktari = work_order_details.get("musteri_paketleme_miktari")
            num_packs = frappe.cint(stock_entry_detail_doc.qty // musteri_paketleme_miktari)
            remainder_qty = stock_entry_detail_doc.qty % musteri_paketleme_miktari

            if num_packs >= 1:
                for pack in range(1, num_packs + 1):
                    save_and_print_wo_label(musteri_paketleme_miktari, f"{batch_no}{pack:04d}")

            if remainder_qty > 0:
                save_and_print_wo_label(remainder_qty, f"{batch_no}{num_packs + 1:04d}")


    @staticmethod
    def create_depo_label(row, batch_no, qty, sut_code, q_ref):
        existing = frappe.db.get_value(
            "KTA Stock Label",
            {"reference_name": row.parent, "sut_barcode": sut_code, "label_type": "Depo Giriş Etiketi"},
            "name"
        )
        if existing:
            return existing

        purchase_receipt = frappe.get_cached_doc("Purchase Receipt", row.parent)
        etiket_item_group = frappe.db.get_value("Item", row.item_code, "item_group")

        etiket = frappe.get_doc({
            "doctype": "KTA Stock Label",
            "label_type": "Depo Giriş Etiketi",
            "reference_doctype": "Purchase Receipt",
            "reference_name": row.parent,
            "supplier_delivery_note": purchase_receipt.get("supplier_delivery_note"),
            "qty": qty,
            "uom": row.stock_uom,
            "batch": batch_no,
            "gr_posting_date": purchase_receipt.get("posting_date"),
            "item_code": row.item_code,
            "sut_barcode": sut_code,
            "item_name": row.item_name,
            "item_group": etiket_item_group,
            "quality_ref": q_ref,
            "do_not_split": row.custom_do_not_split,
        })
        etiket.insert(ignore_permissions=True)
        return etiket.name

    @staticmethod
    def clear_empty_labels():
        label_doctype = frappe.qb.DocType("KTA Stock Label")
        item_code_field = frappe.qb.Field("item_code")
        batch_field = frappe.qb.Field("batch")

        results = (
            frappe.qb.from_(label_doctype)
            .select(item_code_field, batch_field)
            .where(frappe.qb.Field("label_type") == "Depo Giriş Etiketi")
            .groupby(item_code_field, batch_field)
        ).run(as_dict=True)

        for result in results:
            bins = BatchSplitManager.get_bins_of_item(result.item_code)
            sabe_parents = BatchSplitManager.get_sabe_parents_of_bins_for_batch(bins, result.batch)
            
            if not sabe_parents:
                labels_to_delete = (
                    frappe.qb.from_(label_doctype)
                    .select(frappe.qb.Field("name"))
                    .where((item_code_field == result.item_code) & (batch_field == result.batch))
                ).run(pluck=True)
                
                if labels_to_delete:
                    frappe.db.delete("KTA Stock Label", filters={"name": ["in", labels_to_delete]})

        return frappe.utils.nowdate()

    @staticmethod
    def get_label_item_batch(sut):
        items = frappe.get_all(
            "KTA Stock Label",
            filters={"sut_barcode": sut, "do_not_split": 0, "label_type": "Depo Giriş Etiketi"},
            fields=["item_code", "batch"]
        )

        if len(items) != 1:
            return None
            
        return items[0]


@frappe.whitelist()
def check_queue_health():
    try:
        import frappe.utils.background_jobs as bj
        from rq import Queue, Worker
        conn = bj.get_redis_conn()
        q = Queue('short', connection=conn)
        
        workers = Worker.all(connection=conn)
        short_workers = [w for w in workers if "short" in w.queue_names()]
        
        if not short_workers:
            frappe.msgprint(
                "<strong>UYARI:</strong> Arka plan kuyruk yöneticisi (worker) aktif değil! "
                "Etiket basım işleri sıraya alınacak ancak yazıcıya gönderilmeyecektir. "
                "Lütfen sistem yöneticinizle iletişime geçin.",
                indicator="red",
                alert=True
            )
            return False
            
        if q.count >= 10:
            frappe.msgprint(
                f"<strong>UYARI:</strong> Yazıcı kuyruğu yoğun! Sıradaki iş sayısı: {q.count}. "
                "Etiketlerin basılması gecikebilir.",
                indicator="orange",
                alert=True
            )
            
    except Exception as e:
        frappe.log_error(f"Queue Health Check Error: {e}", "Queue Monitor")
        
    return True

@frappe.whitelist()
def print_kta_pr_labels(gr_number=None, label=None, q_ref=None):
    check_queue_health()
    LabelPrinter.print_pr_labels(gr_number, label, q_ref)

@frappe.whitelist()
def print_split_kta_pr_labels(label=None):
    check_queue_health()
    LabelPrinter.print_split_pr_labels(label)

@frappe.whitelist()
def print_kta_wo_labels(work_order):
    details = LabelPrinter.get_details_of_wo_for_label(work_order)
    for stock_entry in frappe.get_all(
            doctype="Stock Entry",
            filters={"stock_entry_type": "Manufacture", "work_order": work_order},
            fields=["name"]
    ):
        LabelPrinter.print_wo_label(details, stock_entry.name)

@frappe.whitelist()
def print_kta_wo_labels_of_stock_entry(stock_entry):
    stock_entry_doc = frappe.get_doc("Stock Entry", stock_entry)
    LabelPrinter.print_wo_label(LabelPrinter.get_details_of_wo_for_label(stock_entry_doc.work_order), stock_entry)

@frappe.whitelist()
def resplit_and_print_kta_wo_labels(stock_entry):
    BatchSplitManager.resplit_submitted_manufacturing_batches(stock_entry)
    print_kta_wo_labels_of_stock_entry(stock_entry)

@frappe.whitelist()
def reprint_depo_label(label_name):
    frappe.enqueue(
        "erpnextkta.kta_stock.label_manager._print_pr_labels_by_names",
        label_names=[label_name],
        user=frappe.session.user,
        queue="short",
        timeout=60,
        now=frappe.flags.in_test,
    )

@frappe.whitelist()
def clear_warehouse_labels():
    return LabelPrinter.clear_empty_labels()


def _print_pr_labels_by_names(label_names, user=None):
    if not label_names:
        return

    if isinstance(label_names, str):
        import json
        label_names = json.loads(label_names)

    zebra_printer = ZebraPrinterManager.get_printer_for_user(user=user or frappe.session.user)
    if not zebra_printer:
        for name in label_names:
            ZebraPrinterManager.create_print_log(
                label_doctype="KTA Stock Label",
                label_name=name,
                printer=None,
                status="Failed",
                zpl=None,
                error=f"Kullanıcı için varsayılan yazıcı bulunamadı: {user or frappe.session.user}",
                user=user or frappe.session.user
            )
        return

    zpl_batch = []
    lbl_names = []
    
    for data in frappe.get_all(
        doctype="KTA Stock Label",
        filters={"name": ["in", label_names]},
        fields=[
            "name", "item_code", "item_name", "item_group", "qty", "uom",
            "supplier_delivery_note", "sut_barcode", "gr_posting_date",
            "quality_ref", "do_not_split", "reference_name", "batch", "label_type"
        ],
        order_by="creation asc"
    ):
        data.gr_number = data.reference_name
        data.qty = ZebraPrinterManager.format_qty(data.qty)
        
        # Use the new label_type as template name (Depo Giriş Etiketi or İş Emri Etiketi)
        template_name = data.label_type or "Depo Giriş Etiketi"
        formatted_data = ZebraPrinterManager.format_data(template_name, data)
        
        zpl_batch.append(formatted_data)
        lbl_names.append(data.name)

    if zpl_batch:
        zebra_printer.send_batch(
            data_list=zpl_batch,
            label_doctype="KTA Stock Label",
            label_names=lbl_names
        )
        for name in lbl_names:
            curr_count = frappe.db.get_value("KTA Stock Label", name, "print_count") or 0
            frappe.db.set_value(
                "KTA Stock Label",
                name,
                {
                    "print_count": curr_count + 1,
                    "last_printed_at": frappe.utils.now(),
                    "last_printed_by": user or frappe.session.user or "Administrator"
                },
                update_modified=False
            )
        frappe.db.commit()


def custom_split_kta_batches(row=None, q_ref="ATLA 5/1", submitting_user=None):
    check_queue_health()
    if not row:
        return

    if isinstance(row, str):
        row = frappe.get_doc("Purchase Receipt Item", row)

    allocations = BatchSplitManager.split_purchase_receipt_batches(row)
    if not allocations:
        return

    created_label_names = []
    for allocation in allocations:
        label_name = LabelPrinter.create_depo_label(
            row=row,
            batch_no=allocation["batch_no"],
            qty=allocation["qty"],
            sut_code=allocation.get("sut_code"),
            q_ref=q_ref,
        )
        if label_name:
            created_label_names.append(label_name)

    if not created_label_names:
        return

    frappe.enqueue(
        "erpnextkta.kta_stock.label_manager._print_pr_labels_by_names",
        label_names=created_label_names,
        user=submitting_user or frappe.session.user,
        queue="short",
        timeout=120,
        retry=3,
        now=frappe.flags.in_test,
    )
