import socket

import frappe
from babel.numbers import format_decimal


@frappe.whitelist()
def get_customer_income_account(customer, company):
    """
    Fetch the customer income account from the Party Account child table.
    """
    try:
        frappe.logger().info(f"Fetching customer income account for Customer: {customer}, Company: {company}")

        # Fetch the value from the Party Account child table
        customer_income_account = frappe.get_value(
            "Party Account",
            {"parent": customer, "parenttype": "Customer", "company": company},
            "customer_income_account"  # Fetch the customer_income_account field
        )

        frappe.logger().info(f"Fetched customer income account: {customer_income_account}")
        return customer_income_account
    except Exception as e:
        frappe.log_error(f"Error fetching customer income account: {e}")
        return None


@frappe.whitelist()
def print_kta_pr_labels(gr_number=None, label=None, q_ref=None):
    if not gr_number and not label and not q_ref:
        frappe.msgprint("Either `gr_number`, `label` or 'q_ref' must be provided.")
        return

    query_filter = {"do_not_split": 0}
    if gr_number:
        query_filter["gr_number"] = gr_number
    elif label:
        query_filter["name"] = label
    elif q_ref:
        query_filter["quality_ref"] = q_ref

    zebra_printer = get_zebra_printer_for_user()
    zebra_ip_address = zebra_printer.get("ip")
    zebra_port = zebra_printer.get("port")
    for data in frappe.get_all("KTA Depo Etiketleri", filters=query_filter,
                               fields={"item_code",
                                       "item_name",
                                       "item_group",
                                       "qty",
                                       "uom",
                                       "supplier_delivery_note",
                                       "sut_barcode",
                                       "gr_posting_date",
                                       "quality_ref"}):
        data.qty = format_kta_label_qty(data.qty)
        formatted_data = zebra_formatter("KTA Depo Etiketleri", data)
        send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)


@frappe.whitelist()
def print_split_kta_pr_labels(label=None):
    kta_depo_etiketleri_bolme_doctype = "KTA Depo Etiketleri Bolme"
    kta_depo_etiketleri_doctype = "KTA Depo Etiketleri"

    if not label:
        frappe.msgprint("`label` must be provided.")
        return

    split_query_filter = {"parent": label}

    splits = frappe.get_all(kta_depo_etiketleri_bolme_doctype,
                            filters=split_query_filter,
                            fields={"idx",
                                    "qty"})

    query_filter = {"do_not_split": 1, "name": label}

    label = frappe.db.get_value(kta_depo_etiketleri_doctype,
                                filters=query_filter,
                                fieldname=["item_code",
                                           "item_name",
                                           "item_group",
                                           "qty",
                                           "uom",
                                           "supplier_delivery_note",
                                           "batch",
                                           "sut_barcode",
                                           "gr_posting_date",
                                           "quality_ref"],
                                as_dict=True)

    zebra_printer = get_zebra_printer_for_user()
    zebra_ip_address = zebra_printer.get("ip")
    zebra_port = zebra_printer.get("port")
    for split in splits:
        label.qty = format_kta_label_qty(split.qty)
        label.sut_barcode = f"{label.batch}{split.idx:04d}"
        formatted_data = zebra_formatter(kta_depo_etiketleri_doctype, label)
        send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)


@frappe.whitelist()
def print_kta_wo_labels(work_order=None):
    # Constants for DocTypes
    bom_doctype = "BOM"
    item_doctype = "Item"
    item_customer_detail_doctype = "Item Customer Detail"
    item_customer_detail_parentfield = "customer_items"
    stock_entry_doctype = "Stock Entry"
    stock_entry_type_manufacture = "Manufacture"
    stock_entry_detail_doctype = "Stock Entry Detail"
    stock_entry_detail_docstatus = 1
    stock_entry_detail_is_finished_item = 1
    stock_entry_detail_parentfield = "items"
    work_order_doctype = "Work Order"
    kta_is_emri_etiketleri_name = "KTA İş Emri Etiketleri"

    work_order_doc = frappe.get_doc(work_order_doctype, work_order)

    stock_entry_data = frappe.db.get_value(
        stock_entry_doctype,
        filters={
            "stock_entry_type": stock_entry_type_manufacture,
            "work_order": work_order
        },
        fieldname=[
            "name",
            "posting_date",
            "to_warehouse"
        ],
        as_dict=True
    )
    source_warehouse = work_order

    destination_warehouse = stock_entry_data.to_warehouse

    if not destination_warehouse:
        destination_warehouse = frappe.db.get_all(
            stock_entry_detail_doctype,
            filters={
                "parent": stock_entry_data.name,
                "parenttype": stock_entry_doctype,
                "parentfield": stock_entry_detail_parentfield,
                "t_warehouse": ["not in", None]
            },
            fields=[
                "t_warehouse"
            ],
            group_by="t_warehouse"
        )

        if len(destination_warehouse) > 1:
            frappe.throw(f"More than one destination warehouse found for Work Order: {work_order}")
            return

    stock_entry_detail_data = frappe.db.get_value(
        stock_entry_detail_doctype,
        filters={
            "parent": stock_entry_data.name,
            "parenttype": stock_entry_doctype,
            "parentfield": stock_entry_detail_parentfield,
            "item_code": work_order_doc.get("production_item"),
            "is_finished_item": stock_entry_detail_is_finished_item,
            "docstatus": stock_entry_detail_docstatus,
            "t_warehouse": ["is", "set"]
        },
        fieldname=[
            "name"
        ]
    )

    stock_entry_detail_doc = frappe.get_doc(stock_entry_detail_doctype, stock_entry_detail_data)

    batch_no = get_batch_from_stock_entry_detail(stock_entry_detail_doc)

    bom_doc = frappe.get_doc(bom_doctype, work_order_doc.get("bom_no"))

    # Construct data
    data = dict()
    data["print_date"] = frappe.utils.nowdate()
    data["material_number"] = work_order_doc.get("production_item")
    data["material_description"] = work_order_doc.get("description")
    meta = frappe.get_meta("BOM")
    if meta.has_field("custom_musteri_indeksi_no"):
        data["material_index"] = bom_doc.get("custom_musteri_indeksi_no")
    data["work_order"] = work_order_doc.get("name")
    data["gr_posting_date"] = stock_entry_data.get("posting_date")
    data["gr_number"] = stock_entry_data.get("name")
    data["gr_source_warehouse"] = source_warehouse[0]
    data["to_warehouse"] = destination_warehouse[0]
    data["stock_uom"] = work_order_doc.get("stock_uom")
    data["batch_no"] = batch_no

    musteri_paketleme_miktari = frappe.db.get_value(
        item_customer_detail_doctype,
        filters={
            "parent": work_order_doc.get("production_item"),
            "parenttype": item_doctype,
            "parentfield": item_customer_detail_parentfield
        },
        fieldname=[
            "max(custom_musteri_paketleme_miktari) as musteri_paketleme_miktari"
        ]
    )

    if not musteri_paketleme_miktari:
        frappe.throw(f"No custom_musteri_paketleme_miktari found for Item: {work_order_doc.get('production_item')}")
        return

    num_packs = frappe.cint(work_order_doc.get("qty") // musteri_paketleme_miktari)
    remainder_qty = work_order_doc.get("qty") % musteri_paketleme_miktari

    zebra_printer = get_zebra_printer_for_user()
    zebra_ip_address = zebra_printer.get("ip")
    zebra_port = zebra_printer.get("port")

    if num_packs >= 1:
        # Use range to run the loop exactly num_packs times
        for pack in range(1, num_packs + 1):
            data["qty"] = format_kta_label_qty(musteri_paketleme_miktari)
            data["sut_no"] = f"{batch_no}{pack:04d}"
            formatted_data = zebra_formatter(kta_is_emri_etiketleri_name, data)
            send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)

    if remainder_qty > 0:
        data["qty"] = format_kta_label_qty(work_order_doc.get("remainder_qty"))
        data["sut_no"] = f"{batch_no}{num_packs + 1:04d}"
        formatted_data = zebra_formatter(kta_is_emri_etiketleri_name, data)
        send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)


def send_data_to_zebra(data, ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))
            s.sendall(data.encode("utf-8"))
            return None
    except Exception as e:
        frappe.log_error(f"ZPL Print Error {str(e)}", "Printer Error")
        return {"status": "error", "message": f"Failed to send label {str(e)}"}


def zebra_formatter(doctype_name, data):
    doc = frappe.get_doc("KTA Zebra Templates", doctype_name)
    return doc.get("zebra_template").format(data=data)


def custom_split_kta_batches(row=None, q_ref="ATLA 5/1"):
    # for row in self.get(table_name):
    if row.serial_and_batch_bundle:
        row_batch_number = frappe.db.get_value(
            "Serial and Batch Entry",
            {"parent": row.serial_and_batch_bundle},
            "batch_no"
        )

        if not row_batch_number:
            frappe.throw(f"Row {row.idx}: No batch number found for the item {row.item_code}.")

        if row.custom_do_not_split == 0:
            split_qty = row.custom_split_qty
            num_packs = frappe.cint(row.stock_qty // split_qty)  # Use row.stock_qty directly
            remainder_qty = row.stock_qty % split_qty

            if num_packs >= 1:
                # Use range to run the loop exactly num_packs times
                for pack in range(1, num_packs + 1):
                    custom_create_packages(row, row_batch_number, split_qty, pack, q_ref)

            if remainder_qty > 0:
                custom_create_packages(row, row_batch_number, remainder_qty, num_packs + 1, q_ref)
        elif row.custom_do_not_split == 1:
            custom_create_packages(row, row_batch_number, row.stock_qty, 0, q_ref)


def custom_create_packages(row, batch_no, qty, pack_no, q_ref):
    etiket_item_group = frappe.db.get_value("Item", row.item_code, "item_group")
    purchase_receipt = frappe.get_doc("Purchase Receipt", row.parent)

    etiket = frappe.get_doc(
        dict(
            doctype="KTA Depo Etiketleri",
            gr_number=row.parent,
            supplier_delivery_note=purchase_receipt.get("supplier_delivery_note"),
            qty=qty,
            uom=row.stock_uom,
            batch=batch_no,
            gr_posting_date=purchase_receipt.get("posting_date"),
            item_code=row.item_code,
            sut_barcode=f"{batch_no}{pack_no:04d}",
            item_name=row.item_name,
            item_group=etiket_item_group,
            quality_ref=q_ref,
            do_not_split=row.custom_do_not_split
        )
    )
    etiket.insert()

    frappe.db.commit()


def get_zebra_printer_for_user():
    # Get the current logged-in user
    user = frappe.session.user

    # Query the printer for this user that is both enabled and marked as default
    printer = frappe.db.get_value(
        "KTA User Zebra Printers",
        {
            "user": user,
            "disabled": 0
        },
        ["printer"]
    )

    if printer is not None:  # Check if a printer was found
        zebra_printer = frappe.get_doc("KTA Zebra Printers", printer)
        return zebra_printer
    else:
        frappe.msgprint("No default printer found for the current user.")
        return None


def format_kta_label_qty(qty):
    if qty % 1 == 0:
        return format_decimal(f"{qty:g}", locale="tr_TR")
    else:
        return format_decimal(f"{qty:.2f}", locale="tr_TR")


def get_batch_from_stock_entry_detail(stock_entry_detail):
    serial_and_batch_bundle_doctype = "Serial and Batch Bundle"
    serial_and_batch_entry_doctype = "Serial and Batch Entry"
    serial_and_batch_entry_parentfield = "entries"
    serial_and_batch_entry_is_outward = 0

    if not stock_entry_detail.get("serial_and_batch_bundle"):
        return None

    batch_no = frappe.db.get_value(
        serial_and_batch_entry_doctype,
        filters={
            "parent": stock_entry_detail.get("serial_and_batch_bundle"),
            "parenttype": serial_and_batch_bundle_doctype,
            "parentfield": serial_and_batch_entry_parentfield,
            "is_outward": serial_and_batch_entry_is_outward,
            "warehouse": stock_entry_detail.get("t_warehouse"),
            "batch_no": ["is", "set"]
        },
        fieldname="batch_no"
    )
    if not batch_no:
        frappe.throw(f"More than one batch found for Stock Entry Detail: {stock_entry_detail.name}")
        return None

    return batch_no
