import socket
import frappe
import json
from erpnext.controllers.accounts_controller import update_child_qty_rate
from frappe import _
from frappe.utils import nowdate, getdate, flt, today, add_days, cint
from collections import defaultdict
from babel.numbers import format_decimal

# Global doctype constants
DOCTYPE_PARTY_ACCOUNT = "Party Account"
DOCTYPE_CUSTOMER = "Customer"
DOCTYPE_ADDRESS = "Address"
DOCTYPE_KTA_DEPO_ETIKETLERI = "KTA Depo Etiketleri"
DOCTYPE_KTA_DEPO_ETIKETLERI_BOLME = "KTA Depo Etiketleri Bolme"
DOCTYPE_STOCK_ENTRY = "Stock Entry"
DOCTYPE_BOM = "BOM"
DOCTYPE_ITEM = "Item"
DOCTYPE_ITEM_CUSTOMER_DETAIL = "Item Customer Detail"
DOCTYPE_WORK_ORDER = "Work Order"
DOCTYPE_STOCK_ENTRY_DETAIL = "Stock Entry Detail"
DOCTYPE_SERIAL_AND_BATCH_BUNDLE = "Serial and Batch Bundle"
DOCTYPE_SERIAL_AND_BATCH_ENTRY = "Serial and Batch Entry"
DOCTYPE_KTA_IS_EMRI_ETIKETLERI = "KTA Is Emri Etiketleri"
DOCTYPE_KTA_ZEBRA_TEMPLATES = "KTA Zebra Templates"
DOCTYPE_KTA_USER_ZEBRA_PRINTERS = "KTA User Zebra Printers"
DOCTYPE_KTA_ZEBRA_PRINTERS = "KTA Zebra Printers"
DOCTYPE_BIN = "Bin"
DOCTYPE_STOCK_LEDGER_ENTRY = "Stock Ledger Entry"
DOCTYPE_KTA_MOBIL_DEPO = "KTA Mobil Depo"
DOCTYPE_KTA_MOBIL_DEPO_KALEMI = "KTA Mobil Depo Kalemi"
DOCTYPE_KTA_SUPPLY_ON = "KTA Supply On"
DOCTYPE_KTA_SUPPLY_ON_ENTRY = "KTA Supply On Entry"
DOCTYPE_KTA_SUPPLY_ON_COMPARISON = "KTA Supply On Comparison"
DOCTYPE_KTA_SUPPLY_ON_CHANGE = "KTA Supply On Change"
DOCTYPE_KTA_SO_SYNC_LOG = "KTA SO Sync Log"
DOCTYPE_DELIVERY_NOTE = "Delivery Note"
DOCTYPE_DELIVERY_NOTE_ITEM = "Delivery Note Item"
DOCTYPE_SALES_ORDER = "Sales Order"
DOCTYPE_SALES_ORDER_ITEM = "Sales Order Item"
DOCTYPE_SALES_INVOICE_ITEM = "Sales Invoice Item"
DOCTYPE_CALISMA_KARTI = "Calisma Karti"
DOCTYPE_CALISMA_KARTI_HURDA = "Calisma Karti Hurda"
DOCTYPE_UOM_CONVERSION_DETAIL = "UOM Conversion Detail"

# Global field constants
FIELD_CUSTOMER_INCOME_ACCOUNT = "customer_income_account"
FIELD_PARENT = "parent"
FIELD_PARENTTYPE = "parenttype"
FIELD_COMPANY = "company"
FIELD_DO_NOT_SPLIT = "do_not_split"
FIELD_GR_NUMBER = "gr_number"
FIELD_NAME = "name"
FIELD_QUALITY_REF = "quality_ref"
FIELD_ITEM_CODE = "item_code"
FIELD_ITEM_NAME = "item_name"
FIELD_ITEM_GROUP = "item_group"
FIELD_QTY = "qty"
FIELD_UOM = "uom"
FIELD_SUPPLIER_DELIVERY_NOTE = "supplier_delivery_note"
FIELD_SUT_BARCODE = "sut_barcode"
FIELD_GR_POSTING_DATE = "gr_posting_date"
FIELD_IDX = "idx"
FIELD_BATCH = "batch"
FIELD_STOCK_ENTRY_TYPE = "stock_entry_type"
FIELD_WORK_ORDER = "work_order"
FIELD_BOM_NO = "bom_no"
FIELD_CUSTOM_MUSTERI_INDEKSI_NO = "custom_musteri_indeksi_no"
FIELD_CUSTOM_MUSTERI_PAKETLEME_MIKTARI = "custom_musteri_paketleme_miktari"
FIELD_PRODUCTION_ITEM = "production_item"
FIELD_DESCRIPTION = "description"
FIELD_STOCK_UOM = "stock_uom"
FIELD_PARENTFIELD = "parentfield"
FIELD_IS_FINISHED_ITEM = "is_finished_item"
FIELD_DOCSTATUS = "docstatus"
FIELD_T_WAREHOUSE = "t_warehouse"
FIELD_TO_WAREHOUSE = "to_warehouse"
FIELD_POSTING_DATE = "posting_date"
FIELD_IS_OUTWARD = "is_outward"
FIELD_WAREHOUSE = "warehouse"
FIELD_BATCH_NO = "batch_no"
FIELD_ACTUAL_QTY = "actual_qty"
FIELD_BALANCE_QTY = "balance_qty"
FIELD_PLANT_NO_CUSTOMER = "plant_no_customer"
FIELD_PART_NO_CUSTOMER = "part_no_customer"
FIELD_DELIVERY_NOTE_NO = "delivery_note_no"
FIELD_DELIVERY_NOTE_DATE = "delivery_note_date"
FIELD_REF_CODE = "ref_code"
FIELD_CUSTOMER_NAME = "customer_name"
FIELD_CUSTOM_IRSALIYE_NO = "custom_irsaliye_no"
FIELD_LR_DATE = "lr_date"
FIELD_IS_RETURN = "is_return"
FIELD_S_WAREHOUSE = "s_warehouse"
FIELD_DEPO = "depo"
FIELD_HURDA_NEDENI = "hurda_nedeni"

# Global value constants
VALUE_MANUFACTURE = "Manufacture"
VALUE_CUSTOMER_ITEMS = "customer_items"
VALUE_ENTRIES = "entries"

# Global parent field constants
PARENT_FIELD_STOCK_ENTRY_DETAIL = "items"


def _get_supply_on_doc(supply_on_name: str):
    if not supply_on_name:
        frappe.throw(_("Supply On referansı belirtilmedi."))

    if not frappe.db.exists(DOCTYPE_KTA_SUPPLY_ON, supply_on_name):
        frappe.throw(_("Supply On kaydı bulunamadı: {0}").format(supply_on_name))

    return frappe.get_doc(DOCTYPE_KTA_SUPPLY_ON, supply_on_name)


@frappe.whitelist()
def get_customer_income_account(customer, company):
    """
    Fetch the customer income account from the Party Account child table.
    """
    try:
        frappe.logger().info(f"Fetching customer income account for Customer: {customer}, Company: {company}")

        # Fetch the value from the Party Account child table
        customer_income_account = frappe.get_value(
            DOCTYPE_PARTY_ACCOUNT,
            {FIELD_PARENT: customer, FIELD_PARENTTYPE: DOCTYPE_CUSTOMER, FIELD_COMPANY: company},
            FIELD_CUSTOMER_INCOME_ACCOUNT
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

    query_filter = {FIELD_DO_NOT_SPLIT: 0}
    if gr_number:
        query_filter[FIELD_GR_NUMBER] = gr_number
    elif label:
        query_filter[FIELD_NAME] = label
    elif q_ref:
        query_filter[FIELD_QUALITY_REF] = q_ref

    zebra_printer = get_zebra_printer_for_user()
    zebra_ip_address = zebra_printer.get("ip")
    zebra_port = zebra_printer.get("port")

    for data in frappe.get_all(
            doctype=DOCTYPE_KTA_DEPO_ETIKETLERI,
            filters=query_filter,
            fields={
                FIELD_ITEM_CODE,
                FIELD_ITEM_NAME,
                FIELD_ITEM_GROUP,
                FIELD_QTY,
                FIELD_UOM,
                FIELD_SUPPLIER_DELIVERY_NOTE,
                FIELD_SUT_BARCODE,
                FIELD_GR_POSTING_DATE,
                FIELD_QUALITY_REF
            }
    ):
        data.qty = format_kta_label_qty(data.qty)
        formatted_data = zebra_formatter(DOCTYPE_KTA_DEPO_ETIKETLERI, data)
        send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)


@frappe.whitelist()
def print_split_kta_pr_labels(label=None):
    if not label:
        frappe.msgprint("`label` must be provided.")
        return

    split_query_filter = {FIELD_PARENT: label}

    splits = frappe.get_all(
        doctype=DOCTYPE_KTA_DEPO_ETIKETLERI_BOLME,
        filters=split_query_filter,
        fields={FIELD_IDX, FIELD_QTY}
    )

    query_filter = {FIELD_DO_NOT_SPLIT: 1, FIELD_NAME: label}

    label_data = frappe.db.get_value(
        doctype=DOCTYPE_KTA_DEPO_ETIKETLERI,
        filters=query_filter,
        fieldname=[
            FIELD_ITEM_CODE,
            FIELD_ITEM_NAME,
            FIELD_ITEM_GROUP,
            FIELD_QTY,
            FIELD_UOM,
            FIELD_SUPPLIER_DELIVERY_NOTE,
            FIELD_BATCH,
            FIELD_SUT_BARCODE,
            FIELD_GR_POSTING_DATE,
            FIELD_QUALITY_REF
        ],
        as_dict=True
    )

    zebra_printer = get_zebra_printer_for_user()
    zebra_ip_address = zebra_printer.get("ip")
    zebra_port = zebra_printer.get("port")

    for split in splits:
        label_data.qty = format_kta_label_qty(split.qty)
        label_data.sut_barcode = f"{label_data.batch}{split.idx:04d}"
        formatted_data = zebra_formatter(DOCTYPE_KTA_DEPO_ETIKETLERI, label_data)
        send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)


@frappe.whitelist()
def print_kta_wo_labels(work_order):
    details_of_wo = get_details_of_wo_for_label(work_order)

    for stock_entry in frappe.get_all(
            doctype=DOCTYPE_STOCK_ENTRY,
            filters={
                FIELD_STOCK_ENTRY_TYPE: VALUE_MANUFACTURE,
                FIELD_WORK_ORDER: work_order
            },
            fields=[FIELD_NAME]
    ):
        print_kta_wo_label(details_of_wo, stock_entry.name)


@frappe.whitelist()
def print_kta_wo_labels_of_stock_entry(stock_entry):
    stock_entry_doc = frappe.get_doc(DOCTYPE_STOCK_ENTRY, stock_entry)
    print_kta_wo_label(get_details_of_wo_for_label(stock_entry_doc.get(FIELD_WORK_ORDER)), stock_entry)


def get_details_of_wo_for_label(work_order):
    work_order_doc = frappe.get_doc(DOCTYPE_WORK_ORDER, work_order)
    bom_doc = frappe.get_doc(DOCTYPE_BOM, work_order_doc.get(FIELD_BOM_NO))

    material_index = "-"
    meta = frappe.get_meta(DOCTYPE_BOM)
    if meta.has_field(FIELD_CUSTOM_MUSTERI_INDEKSI_NO):
        material_index = bom_doc.get(FIELD_CUSTOM_MUSTERI_INDEKSI_NO)

    musteri_paketleme_miktari = frappe.db.get_value(
        doctype=DOCTYPE_ITEM_CUSTOMER_DETAIL,
        filters={
            FIELD_PARENT: work_order_doc.get(FIELD_PRODUCTION_ITEM),
            FIELD_PARENTTYPE: DOCTYPE_ITEM,
            FIELD_PARENTFIELD: VALUE_CUSTOMER_ITEMS
        },
        fieldname=[f"max({FIELD_CUSTOM_MUSTERI_PAKETLEME_MIKTARI}) as musteri_paketleme_miktari"]
    )

    if not musteri_paketleme_miktari:
        frappe.throw(
            f"No {FIELD_CUSTOM_MUSTERI_PAKETLEME_MIKTARI} found for Item: {work_order_doc.get(FIELD_PRODUCTION_ITEM)}")
        return None

    return {
        FIELD_WORK_ORDER: work_order_doc.get(FIELD_NAME),
        FIELD_DESCRIPTION: work_order_doc.get(FIELD_DESCRIPTION),
        FIELD_STOCK_UOM: work_order_doc.get(FIELD_STOCK_UOM),
        FIELD_PRODUCTION_ITEM: work_order_doc.get(FIELD_PRODUCTION_ITEM),
        "material_index": material_index,
        "musteri_paketleme_miktari": musteri_paketleme_miktari
    }


def print_kta_wo_label(work_order_details, stock_entry):
    source_warehouse = stock_entry

    stock_entry_detail = frappe.get_all(
        doctype=DOCTYPE_STOCK_ENTRY_DETAIL,
        filters={
            FIELD_PARENT: stock_entry,
            FIELD_PARENTTYPE: DOCTYPE_STOCK_ENTRY,
            FIELD_PARENTFIELD: PARENT_FIELD_STOCK_ENTRY_DETAIL,
            FIELD_ITEM_CODE: work_order_details.get(FIELD_PRODUCTION_ITEM),
            FIELD_IS_FINISHED_ITEM: 1,
            FIELD_DOCSTATUS: 1,
            FIELD_T_WAREHOUSE: ["is", "set"]
        },
        fields=[FIELD_NAME],
        as_list=True
    )

    if len(stock_entry_detail) > 1:
        frappe.throw(f"More than one Inward Type of Transaction found for Stock Entry: {stock_entry}")
        return

    stock_entry_detail_doc = frappe.get_doc(DOCTYPE_STOCK_ENTRY_DETAIL, stock_entry_detail[0])
    stock_entry_doc = frappe.get_doc(DOCTYPE_STOCK_ENTRY, stock_entry)

    destination_warehouse = stock_entry_doc.get(FIELD_TO_WAREHOUSE)
    if not destination_warehouse:
        destination_warehouse = stock_entry_detail_doc.get(FIELD_T_WAREHOUSE)

    batch_no = get_batch_from_stock_entry_detail(stock_entry_detail_doc)

    # Construct data
    data = frappe.get_doc({
        'doctype': DOCTYPE_KTA_IS_EMRI_ETIKETLERI,
        'print_date': frappe.utils.nowdate(),
        'material_number': work_order_details.get(FIELD_PRODUCTION_ITEM),
        'material_description': work_order_details.get(FIELD_DESCRIPTION),
        'material_index': work_order_details.get("material_index"),
        FIELD_WORK_ORDER: work_order_details.get(FIELD_WORK_ORDER),
        FIELD_GR_POSTING_DATE: frappe.utils.get_date_str(stock_entry_doc.get(FIELD_POSTING_DATE)),
        FIELD_GR_NUMBER: stock_entry,
        'gr_source_warehouse': source_warehouse,
        FIELD_TO_WAREHOUSE: destination_warehouse,
        FIELD_STOCK_UOM: work_order_details.get(FIELD_STOCK_UOM),
        FIELD_BATCH_NO: batch_no
    })

    musteri_paketleme_miktari = work_order_details.get("musteri_paketleme_miktari")
    num_packs = frappe.cint(stock_entry_detail_doc.get(FIELD_QTY) // musteri_paketleme_miktari)
    remainder_qty = stock_entry_detail_doc.get(FIELD_QTY) % musteri_paketleme_miktari

    zebra_printer = get_zebra_printer_for_user()
    zebra_ip_address = zebra_printer.get("ip")
    zebra_port = zebra_printer.get("port")

    if num_packs >= 1:
        for pack in range(1, num_packs + 1):
            data.qty = format_kta_label_qty(musteri_paketleme_miktari)
            data.sut_no = f"{batch_no}{pack:04d}"
            formatted_data = zebra_formatter(DOCTYPE_KTA_IS_EMRI_ETIKETLERI, data)
            send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)

    if remainder_qty > 0:
        data.qty = format_kta_label_qty(remainder_qty)
        data.sut_no = f"{batch_no}{num_packs + 1:04d}"
        formatted_data = zebra_formatter(DOCTYPE_KTA_IS_EMRI_ETIKETLERI, data)
        send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)

    data.delete()


def send_data_to_zebra(data, ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))
            s.sendall(data.encode("utf-8"))
            return None
    except Exception as e:
        frappe.log_error(title=f"ZPL Print Error {str(e)}", message="Printer Error")
        return {"status": "error", "message": f"Failed to send label {str(e)}"}


def zebra_formatter(doctype_name, data):
    doc = frappe.get_doc(DOCTYPE_KTA_ZEBRA_TEMPLATES, doctype_name)
    return doc.get("zebra_template").format(data=data)


def custom_split_kta_batches(row=None, q_ref="ATLA 5/1"):
    if row.serial_and_batch_bundle:
        row_batch_number = frappe.db.get_value(
            doctype=DOCTYPE_SERIAL_AND_BATCH_ENTRY,
            filters={FIELD_PARENT: row.serial_and_batch_bundle},
            fieldname=FIELD_BATCH_NO
        )

        if not row_batch_number:
            frappe.throw(f"Row {row.idx}: No batch number found for the item {row.item_code}.")

        if row.custom_do_not_split == 0:
            split_qty = row.custom_split_qty
            num_packs = frappe.cint(row.stock_qty // split_qty)
            remainder_qty = row.stock_qty % split_qty

            if num_packs >= 1:
                for pack in range(1, num_packs + 1):
                    custom_create_packages(row, row_batch_number, split_qty, pack, q_ref)

            if remainder_qty > 0:
                custom_create_packages(row, row_batch_number, remainder_qty, num_packs + 1, q_ref)
        elif row.custom_do_not_split == 1:
            custom_create_packages(row, row_batch_number, row.stock_qty, 0, q_ref)


def custom_create_packages(row, batch_no, qty, pack_no, q_ref):
    etiket_item_group = frappe.db.get_value(DOCTYPE_ITEM, row.item_code, FIELD_ITEM_GROUP)
    purchase_receipt = frappe.get_doc("Purchase Receipt", row.parent)

    etiket = frappe.get_doc(
        dict(
            doctype=DOCTYPE_KTA_DEPO_ETIKETLERI,
            gr_number=row.parent,
            supplier_delivery_note=purchase_receipt.get(FIELD_SUPPLIER_DELIVERY_NOTE),
            qty=qty,
            uom=row.stock_uom,
            batch=batch_no,
            gr_posting_date=purchase_receipt.get(FIELD_POSTING_DATE),
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
    user = frappe.session.user

    printer = frappe.db.get_value(
        doctype=DOCTYPE_KTA_USER_ZEBRA_PRINTERS,
        filters={"user": user, "disabled": 0},
        fieldname="printer"
    )

    if printer is not None:
        zebra_printer = frappe.get_doc(DOCTYPE_KTA_ZEBRA_PRINTERS, printer)
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
    if not stock_entry_detail.get("serial_and_batch_bundle"):
        return None

    batch_no = frappe.db.get_value(
        DOCTYPE_SERIAL_AND_BATCH_ENTRY,
        filters={
            FIELD_PARENT: stock_entry_detail.get("serial_and_batch_bundle"),
            FIELD_PARENTTYPE: DOCTYPE_SERIAL_AND_BATCH_BUNDLE,
            FIELD_PARENTFIELD: VALUE_ENTRIES,
            FIELD_IS_OUTWARD: 0,
            FIELD_WAREHOUSE: stock_entry_detail.get(FIELD_T_WAREHOUSE),
            FIELD_BATCH_NO: ["is", "set"],
            FIELD_DOCSTATUS: 1
        },
        fieldname=FIELD_BATCH_NO
    )

    if not batch_no:
        frappe.throw(f"More than one batch found for Stock Entry Detail: {stock_entry_detail.name}")
        return None

    return batch_no


@frappe.whitelist()
def find_bins_of_sut(sut, mobil):
    label = get_label_item_batch(sut)
    sabe_parents = get_sabe_parents_of_bins_for_batch(get_bins_of_item(label.item_code), label.batch)
    sle_entries = get_warehouse_quantity_for_sabe_parents(sabe_parents)

    if len(sle_entries) == 0:
        frappe.throw(f"No Stock Ledger Entries found for SUT: {sut}")

    for sle_entry in sle_entries:
        child = frappe.new_doc(
            doctype=DOCTYPE_KTA_MOBIL_DEPO_KALEMI,
            parent=mobil,
            parentfield="mobile_items",
            parenttype=DOCTYPE_KTA_MOBIL_DEPO,
            sut_barcode=sut,
            item_code=label.item_code,
            batch=label.batch,
            source_warehouse=sle_entry.warehouse,
            qty=sle_entry.balance_qty
        )
        child.insert()


def get_label_item_batch(sut):
    items = frappe.get_all(
        doctype=DOCTYPE_KTA_DEPO_ETIKETLERI,
        filters={FIELD_SUT_BARCODE: sut, FIELD_DO_NOT_SPLIT: 0},
        fields=[FIELD_ITEM_CODE, FIELD_BATCH]
    )

    number_of_items = len(items)
    if number_of_items > 1:
        return None
    elif number_of_items == 0:
        return None
    return items[0]


def get_bins_of_item(item, empty=None):
    query_filter = {FIELD_ITEM_CODE: item}
    if empty:
        query_filter[FIELD_ACTUAL_QTY] = 0
    else:
        query_filter[FIELD_ACTUAL_QTY] = [">", 0]

    return frappe.get_all(
        doctype=DOCTYPE_BIN,
        filters=query_filter,
        fields=[FIELD_WAREHOUSE],
        pluck=FIELD_WAREHOUSE
    )


def get_sabe_parents_of_bins_for_batch(bins, batch):
    return frappe.get_all(
        doctype=DOCTYPE_SERIAL_AND_BATCH_ENTRY,
        filters={
            FIELD_WAREHOUSE: ["in", bins],
            FIELD_BATCH_NO: batch,
            FIELD_PARENTTYPE: DOCTYPE_SERIAL_AND_BATCH_BUNDLE,
            FIELD_PARENTFIELD: VALUE_ENTRIES,
            FIELD_DOCSTATUS: 1
        },
        fields=[FIELD_PARENT],
        pluck=FIELD_PARENT
    )


def get_warehouse_quantity_for_sabe_parents(sabe_parents):
    return frappe.get_all(
        doctype=DOCTYPE_STOCK_LEDGER_ENTRY,
        filters={
            "serial_and_batch_bundle": ["in", sabe_parents],
            FIELD_DOCSTATUS: 1,
            "is_cancelled": 0
        },
        fields=[FIELD_WAREHOUSE, f"sum(actual_qty) as {FIELD_BALANCE_QTY}"]
    )


@frappe.whitelist()
def clear_warehouse_labels():
    label_doctype = frappe.qb.DocType(DOCTYPE_KTA_DEPO_ETIKETLERI)
    item_code = frappe.qb.Field(FIELD_ITEM_CODE)
    batch = frappe.qb.Field(FIELD_BATCH)

    results = (
        frappe.qb.from_(label_doctype)
        .select(item_code, batch)
        .groupby(item_code, batch)
    ).run(as_dict=True)

    for result in results:
        if len(get_sabe_parents_of_bins_for_batch(get_bins_of_item(result.item_code), result.batch)) == 0:
            labels_to_delete = (
                frappe.qb.from_(label_doctype)
                .select(FIELD_NAME)
                .where((item_code == result.item_code) & (batch == result.batch))
            ).run()
            frappe.db.delete(DOCTYPE_KTA_DEPO_ETIKETLERI, filters={FIELD_NAME: labels_to_delete})

    return frappe.utils.nowdate()


@frappe.whitelist()
def get_items_from_calisma_karti(source_name: str, target_doc=None):
    """
    Stock Entry > Get Items From > Calisma Karti
    'Calisma Karti' içindeki 'Calisma Karti Hurda' satırlarını,
    Stock Entry 'items' formatında döndürür.
    """
    if not source_name:
        frappe.throw("Çalışma Kartı seçilmedi.")

    doc = frappe.get_doc(DOCTYPE_CALISMA_KARTI, source_name)
    parent_src_wh = getattr(doc, FIELD_S_WAREHOUSE, None) or getattr(doc, FIELD_WAREHOUSE, None) or None

    items = []
    for row in doc.get_all_children():
        if row.doctype != DOCTYPE_CALISMA_KARTI_HURDA:
            continue

        # Field names may vary across deployments; use safe access with fallbacks
        item_code = getattr(row, "parca_no", None) or getattr(row, FIELD_ITEM_CODE, None)
        qty = getattr(row, "miktar", None) or getattr(row, FIELD_QTY, None)
        uom = getattr(row, "birim", None) or getattr(row, FIELD_UOM, None)
        row_src_wh = getattr(row, FIELD_DEPO, None)
        s_wh = row_src_wh or parent_src_wh

        if not item_code or not qty:
            continue

        item = frappe.db.get_value(
            DOCTYPE_ITEM, item_code, [FIELD_ITEM_NAME, FIELD_STOCK_UOM, FIELD_DESCRIPTION], as_dict=True
        )
        if not item:
            frappe.throw(f"Item bulunamadı: {item_code}")

        stock_uom = item.stock_uom
        uom_final = uom or stock_uom

        # UOM dönüşüm faktörü
        conv = 1.0
        if uom and uom != stock_uom:
            conv_row = frappe.db.get_value(
                DOCTYPE_UOM_CONVERSION_DETAIL,
                {FIELD_PARENT: item_code, "uom": uom},
                "conversion_factor",
            )
            conv = float(conv_row) if conv_row else 1.0

        # Açıklama + hurda nedeni
        desc_bits = []
        if item.description:
            desc_bits.append(item.description)
        hurda_nedeni_val = getattr(row, FIELD_HURDA_NEDENI, None)
        if hurda_nedeni_val:
            desc_bits.append(f"Hurda Nedeni: {hurda_nedeni_val}")
        description = " | ".join(desc_bits) if desc_bits else item.item_name

        items.append({
            FIELD_ITEM_CODE: item_code,
            FIELD_ITEM_NAME: item.item_name,
            FIELD_DESCRIPTION: description,
            "uom": uom_final,
            FIELD_STOCK_UOM: stock_uom,
            "conversion_factor": conv,
            FIELD_QTY: qty,
            FIELD_S_WAREHOUSE: s_wh,
        })

    if not items:
        frappe.throw("Seçilen Çalışma Kartında aktarılabilir hurda satırı yok.")

    return items

@frappe.whitelist()
def compare_supply_on_documents(current_supply_on_name):
    """
    Verilen KTA Supply On dokümanını, CREATION sırasına göre ondan ÖNCE gelen
    bir önceki KTA Supply On dokümanı ile karşılaştır.

    Burada:
      - previous_supply_on → ham veri
      - current_supply_on  → sevkiyatlar düşülmüş veri
    """
    DOCTYPE = DOCTYPE_KTA_SUPPLY_ON

    resolved_name = current_supply_on_name

    # Geçerli dokümanı al
    current = frappe.get_doc(DOCTYPE, resolved_name)

    # Tüm Supply On kayıtlarını creation sırasına göre al (artan)
    all_heads = frappe.get_all(
        DOCTYPE,
        fields=["name", "creation"],
        order_by="creation asc",
    )

    # Listedeki current index'ini bul
    current_index = None
    for idx, row in enumerate(all_heads):
        if row.name == current.name:
            current_index = idx
            break

    if current_index is None:
        frappe.throw(f"Current Supply On kaydı bulunamadı: {current.name}")

    if current_index == 0:
        frappe.msgprint("Karşılaştırma için önceki Supply On kaydı bulunamadı (bu ilk kayıt).")
        return

    # Bir önceki kayıt:
    previous_supply_on_name = all_heads[current_index - 1].name

    # Comparison doc
    comparison_doc = frappe.new_doc("KTA Supply On Comparison")
    comparison_doc.comparison_date = frappe.utils.now()
    comparison_doc.previous_supply_on = previous_supply_on_name
    comparison_doc.current_supply_on = current_supply_on_name
    comparison_doc.status = "Draft"

    # 🔹 Eski veri: ham
    previous_data = get_supply_on_data(previous_supply_on_name, apply_shipments=False)

    # 🔹 Yeni veri: ham (sevkiyat düşümü artık senkronizasyon aşamasında yapılacak)
    current_data = get_supply_on_data(resolved_name, apply_shipments=False)

    # Karşılaştırma yap
    changes = detect_changes(previous_data, current_data)

    # Değişiklikleri kaydet
    for change in changes:
        comparison_doc.append("changes", change)

    comparison_doc.save()
    frappe.db.commit()

    return comparison_doc.name


def get_supply_on_data(supply_on_name, apply_shipments=False):
    """
    Supply On verilerini unique key ile dict olarak getir.

    Key: order_no + part_no_customer + plant_no_customer

    apply_shipments=True ise:
      - Bu Supply On satırları üzerinde sevk parametresi + sevk irsaliyeleri
        dikkate alınarak delivery_quantity'ler düşürülür.
    """
    rows = frappe.db.sql("""
        SELECT 
            order_no,
            NULL AS order_item,
            part_no_customer,
            delivery_date,
            delivery_quantity,
            NULL AS efz,
            plant_no_customer
        FROM `tabKTA Supply On Entry`
        WHERE parent = %s AND parenttype = %s
        ORDER BY order_no, part_no_customer, plant_no_customer, delivery_date
    """, (supply_on_name, DOCTYPE_KTA_SUPPLY_ON), as_dict=True)

    # 🔹 YENİ: Sevkiyat düşümü sadece current Supply On için uygulanacak
    if apply_shipments:
        rows = adjust_supply_on_with_shipments(rows)

    data_dict = defaultdict(list)
    for row in rows:
        key = f"{row.order_no}_{row.part_no_customer}_{row.plant_no_customer}"
        data_dict[key].append(row)

    for key in data_dict:
        data_dict[key].sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
        )

    return data_dict


def detect_changes(previous_data, current_data):
    """
    İki Supply On veri seti arasındaki değişiklikleri tespit et.

    Adımlar (her key = order_no + part_no_customer + plant_no_customer için):

      1) (tarih, qty) birebir aynı olan satırları her iki taraftan da çıkar.
      2) Aynı tarihe sahip (key + tarih) satırlar için toplam qty'leri karşılaştır:
         - Toplamlar eşitse -> o tarihte net değişiklik yok, satırlar tamamen düşülür.
         - Toplamlar farklıysa -> "Miktar Artışı/Azalışı" değişikliği üretilir,
           sonra o tarihteki satırlar her iki taraftan da düşülür.
      3) Kalan satırlar:
         - Eski + yeni listeler tarih bazında artan sıralanır,
         - Satır satır yürütülür:
             * Hem tarih hem qty değişmiş  -> "Tarih ve Miktar Değişikliği"
             * Sadece tarih değişmiş       -> "Tarih Değişikliği"
             * Sadece qty değişmiş         -> "Miktar Artışı/Azalışı"
         - Sadece eski tarafta kalanlar   -> "Silinen Satır"
         - Sadece yeni tarafta kalanlar   -> "Yeni Satır"
    """

    changes = []

    all_keys = set(previous_data.keys()) | set(current_data.keys())

    for key in all_keys:
        prev_rows = previous_data.get(key, [])
        curr_rows = current_data.get(key, [])

        # ---------------------------
        # 1) (tarih, qty) TAM eşleşen satırları düş
        # ---------------------------
        sig_to_prev_idx = defaultdict(list)
        for i, r in enumerate(prev_rows):
            sig = (str(r.delivery_date), int(r.delivery_quantity or 0))
            sig_to_prev_idx[sig].append(i)

        matched_prev_idx = set()
        matched_curr_idx = set()

        for j, curr in enumerate(curr_rows):
            sig = (str(curr.delivery_date), int(curr.delivery_quantity or 0))
            if sig_to_prev_idx.get(sig):
                i = sig_to_prev_idx[sig].pop()
                matched_prev_idx.add(i)
                matched_curr_idx.add(j)

        unmatched_prev = [
            r for i, r in enumerate(prev_rows) if i not in matched_prev_idx
        ]
        unmatched_curr = [
            r for j, r in enumerate(curr_rows) if j not in matched_curr_idx
        ]

        # Eğer hiçbir şey kalmadıysa bu key için değişiklik yok
        if not unmatched_prev and not unmatched_curr:
            continue

        # ---------------------------
        # 2) Aynı TARİH için toplam qty karşılaştırması
        #    (key + tarih bazında)
        # ---------------------------
        prev_by_date = defaultdict(list)
        curr_by_date = defaultdict(list)

        for r in unmatched_prev:
            prev_by_date[str(r.delivery_date)].append(r)

        for r in unmatched_curr:
            curr_by_date[str(r.delivery_date)].append(r)

        # Her iki tarafta da görünen tarihler
        common_dates = set(prev_by_date.keys()) & set(curr_by_date.keys())

        dates_to_drop_from_prev = set()
        dates_to_drop_from_curr = set()

        for date_str in common_dates:
            prev_list = prev_by_date[date_str]
            curr_list = curr_by_date[date_str]

            prev_total = sum(int(r.delivery_quantity or 0) for r in prev_list)
            curr_total = sum(int(r.delivery_quantity or 0) for r in curr_list)

            # Temsilci satır (customer/item mapping için)
            sample = curr_list[0] if curr_list else prev_list[0]

            if prev_total == curr_total:
                # Bu tarihte net değişiklik yok -> hepsini yok say
                dates_to_drop_from_prev.add(date_str)
                dates_to_drop_from_curr.add(date_str)
            else:
                # Miktar Artışı / Azalışı
                qty_diff = curr_total - prev_total
                if qty_diff > 0:
                    change_type = "Miktar Artışı"
                else:
                    change_type = "Miktar Azalışı"

                customer, item = get_customer_and_item(
                    sample.plant_no_customer,
                    sample.part_no_customer,
                )

                changes.append({
                    "order_no": sample.order_no,
                    "order_item": sample.order_item,
                    "part_no_customer": sample.part_no_customer,
                    "plant_no_customer": sample.plant_no_customer,
                    "customer": customer,
                    "item": item,
                    "change_type": change_type,
                    "old_delivery_date": sample.delivery_date,  # aynı tarih
                    "new_delivery_date": sample.delivery_date,
                    "old_delivery_quantity": prev_total,
                    "new_delivery_quantity": curr_total,
                    "difference": qty_diff,
                    "old_efz": prev_list[0].efz if prev_list else None,
                    "new_efz": curr_list[0].efz if curr_list else None,
                    "action_required": 1,
                    "action_status": "Beklemede",
                })

                # Bu tarihteki satırları da artık düştük sayalım
                dates_to_drop_from_prev.add(date_str)
                dates_to_drop_from_curr.add(date_str)

        # Bu tarihleri unmatched listelerden çıkar
        if dates_to_drop_from_prev:
            unmatched_prev = [
                r for r in unmatched_prev if str(r.delivery_date) not in dates_to_drop_from_prev
            ]
        if dates_to_drop_from_curr:
            unmatched_curr = [
                r for r in unmatched_curr if str(r.delivery_date) not in dates_to_drop_from_curr
            ]

        # 2. adımdan sonra da hiçbir şey kalmadıysa bu key için başka değişiklik yok
        if not unmatched_prev and not unmatched_curr:
            continue

        # ---------------------------
        # 3) Kalan satırları tarih sırasına göre satır satır karşılaştır
        # ---------------------------
        unmatched_prev.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
        )
        unmatched_curr.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
        )

        i = j = 0
        len_prev = len(unmatched_prev)
        len_curr = len(unmatched_curr)

        # 3.a) Hem eski hem yeni tarafın satırları varken
        while i < len_prev and j < len_curr:
            prev = unmatched_prev[i]
            curr = unmatched_curr[j]

            customer, item = get_customer_and_item(
                curr.plant_no_customer,
                curr.part_no_customer,
            )

            date_changed = curr.delivery_date != prev.delivery_date
            qty_changed = curr.delivery_quantity != prev.delivery_quantity
            qty_diff = (curr.delivery_quantity or 0) - (prev.delivery_quantity or 0)

            if date_changed and qty_changed:
                change_type = "Tarih ve Miktar Değişikliği"
            elif date_changed:
                change_type = "Tarih Değişikliği"
            else:
                # Sadece miktar
                if qty_diff > 0:
                    change_type = "Miktar Artışı"
                elif qty_diff < 0:
                    change_type = "Miktar Azalışı"
                else:
                    # teorik olarak buraya düşmemeli ama emniyet için
                    i += 1
                    j += 1
                    continue

            changes.append({
                "order_no": curr.order_no,
                "order_item": curr.order_item,
                "part_no_customer": curr.part_no_customer,
                "plant_no_customer": curr.plant_no_customer,
                "customer": customer,
                "item": item,
                "change_type": change_type,
                "old_delivery_date": prev.delivery_date,
                "new_delivery_date": curr.delivery_date,
                "old_delivery_quantity": prev.delivery_quantity,
                "new_delivery_quantity": curr.delivery_quantity,
                "difference": qty_diff,
                "old_efz": prev.efz,
                "new_efz": curr.efz,
                "action_required": 1,
                "action_status": "Beklemede",
            })

            i += 1
            j += 1

        # 3.b) Sadece eski tarafta kalan satırlar -> Silinen Satır
        while i < len_prev:
            prev = unmatched_prev[i]
            customer, item = get_customer_and_item(
                prev.plant_no_customer,
                prev.part_no_customer,
            )

            changes.append({
                "order_no": prev.order_no,
                "order_item": prev.order_item,
                "part_no_customer": prev.part_no_customer,
                "plant_no_customer": prev.plant_no_customer,
                "customer": customer,
                "item": item,
                "change_type": "Silinen Satır",
                "old_delivery_date": prev.delivery_date,
                "old_delivery_quantity": prev.delivery_quantity,
                "old_efz": prev.efz,
                "action_required": 1,
                "action_status": "Beklemede",
            })

            i += 1

        # 3.c) Sadece yeni tarafta kalan satırlar -> Yeni Satır
        while j < len_curr:
            curr = unmatched_curr[j]
            customer, item = get_customer_and_item(
                curr.plant_no_customer,
                curr.part_no_customer,
            )

            changes.append({
                "order_no": curr.order_no,
                "order_item": curr.order_item,
                "part_no_customer": curr.part_no_customer,
                "plant_no_customer": curr.plant_no_customer,
                "customer": customer,
                "item": item,
                "change_type": "Yeni Satır",
                "new_delivery_date": curr.delivery_date,
                "new_delivery_quantity": curr.delivery_quantity,
                "new_efz": curr.efz,
                "action_required": 1,
                "action_status": "Beklemede",
            })

            j += 1

    return changes



def get_customer_and_item(plant_no_customer, part_no_customer):
    """
    Plant no'dan Customer, part_no_customer'dan Item bul.

    Customer:
      - Address.custom_eski_kod == plant_no_customer
      - Address.links (Dynamic Link) içinde link_doctype='Customer' satırının link_name'i

    Item:
      - Item.name == part_no_customer ise doğrudan onu kullan
    """
    customer = None
    item = None

    # 🔹 1) Customer: Address → Dynamic Link üzerinden
    if plant_no_customer:
        # Önce Address kaydını bul
        address_name = frappe.db.get_value(
            "Address",
            {"custom_eski_kod": plant_no_customer},
            "name"
        )

        if address_name:
            # Address'in links alt tablosundan Customer link'ini çek
            customer = frappe.db.get_value(
                "Dynamic Link",
                {
                    "parenttype": "Address",
                    "parent": address_name,
                    "link_doctype": "Customer",
                },
                "link_name",
            )

    # 🔹 2) Item: part_no_customer = bizim Item kodumuz
    if part_no_customer:
        # Item'name' ile bire bir eşleşiyorsa kullan
        item = frappe.db.get_value(
            "Item",
            {"name": part_no_customer},
            "name"
        )

    return customer, item

@frappe.whitelist()
def sync_sales_orders_from_supply_on(supply_on_name=None, supply_on_reference=None):
    """
    Supply On'dan senkronizasyon başlat.
    """
    reference_name = supply_on_reference or supply_on_name
    if not reference_name:
        frappe.throw(_("Supply On seçilmedi."))
    return _sync_sales_orders_from_supply_on(reference_name)


@frappe.whitelist()
def sync_sales_orders_from_comparison(comparison_name):
    """
    Karşılaştırmadan Sales Order'ları senkronize et
    """
    comparison = frappe.get_doc("KTA Supply On Comparison", comparison_name)
    return _sync_sales_orders_from_supply_on(comparison.current_supply_on, comparison=comparison)


def _sync_sales_orders_from_supply_on(supply_on_name, comparison=None):
    """
    Seçilen Supply On için sevkiyat düşülmüş değişiklikleri üretip ERP'ye uygular.
    comparison parametresi verilirse log'lara eklenir ve durum güncellenir.
    """
    supply_on_doc = _get_supply_on_doc(supply_on_name)
    sync_changes = [frappe._dict(change) for change in build_sales_order_sync_changes(supply_on_doc.name)]

    sync_log = frappe.new_doc("KTA SO Sync Log")
    sync_log.supply_on = supply_on_doc.name
    if comparison:
        sync_log.comparison = comparison.name
    sync_log.sync_date = frappe.utils.now()
    sync_log.status = "In Progress"
    sync_log.total_changes = len(sync_changes)
    
    created = updated = closed = errors = 0
    
    try:
        if not sync_changes:
            sync_log.status = "Completed"
            sync_log.comment = "No changes detected for this Supply On."
            sync_log.save()
            supply_on_doc.last_sync_log = sync_log.name
            supply_on_doc.save()
            return {
                'sync_log': sync_log.name,
                'created': 0,
                'updated': 0,
                'closed': 0,
                'errors': 0,
                'info': 'No changes detected',
            }

        # SO bazında grupla
        changes_by_so = group_changes_by_sales_order(sync_changes)
        
        # Her SO için işlem
        for so_identifier, so_changes in changes_by_so.items():
            try:
                result = process_sales_order_batch(so_identifier, so_changes)
                
                for detail in result['details']:
                    sync_log.append("sync_details", detail)
                
                created += result.get('created', 0)
                updated += result.get('updated', 0)
                closed += result.get('closed', 0)
                errors += result.get('errors', 0)
                
            except Exception as e:
                errors += len(so_changes)
                frappe.log_error(f"SO Batch Error: {str(e)}", "SO Sync Batch")
        
        sync_log.created_so = created
        sync_log.updated_so = updated
        sync_log.closed_so = closed
        sync_log.errors = errors
        sync_log.status = "Completed" if errors == 0 else "Failed"
        
        if comparison:
            comparison.status = "Synced"
            comparison.save()
        
        supply_on_doc.last_sync_log = sync_log.name
        supply_on_doc.save()
        
    except Exception as e:
        sync_log.status = "Failed"
        sync_log.error_log = str(e)
        frappe.log_error(str(e), "SO Sync Critical Error")
    
    sync_log.save()
    frappe.db.commit()
    
    result = {
        'sync_log': sync_log.name,
        'created': created,
        'updated': updated,
        'closed': closed,
        'errors': errors
    }

    return result


def build_sales_order_sync_changes(supply_on_name):
    """
    ✅ DÜZELTİLMİŞ: Supply On satırlarını grupla ve sadece NET değişiklikleri tespit et
    
    ÖNEMLI: Sales Order Item seviyesinde delivery_date karşılaştırması yapılıyor
    
    Mantık:
    1. Supply On'dan ham veriyi al ve sevkiyatları düş
    2. Key bazında (customer + order_no + item) grupla
    3. Her key için:
       - Önce tam eşleşenleri (tarih + qty) çıkar
       - Sonra aynı tarihteki toplam qty'leri karşılaştır
       - Kalan satırları sırayla eşleştir
    4. Sadece NET değişiklikleri kaydet
    """
    rows = frappe.db.sql(
        """
        SELECT 
            order_no,
            part_no_customer,
            delivery_date,
            delivery_quantity,
            plant_no_customer
        FROM `tabKTA Supply On Entry`
        WHERE parent = %s
        ORDER BY order_no, part_no_customer, plant_no_customer, delivery_date
        """,
        (supply_on_name,),
        as_dict=True,
    )

    if not rows:
        return []

    # ✅ Sevkiyatları düş
    adjusted_rows = adjust_supply_on_with_shipments(rows)
    far_future = getdate("2199-12-31")

    # ✅ Supply On satırlarını key bazında grupla
    plan_rows_by_key = defaultdict(list)
    customers = set()

    for row in adjusted_rows:
        if not row.order_no:
            continue

        customer, item_code = get_customer_and_item(
            row.plant_no_customer,
            row.part_no_customer,
        )

        if not (customer and item_code):
            continue

        plan_entry = frappe._dict({
            "customer": customer,
            "order_no": row.order_no,
            "order_item": None,
            "part_no_customer": row.part_no_customer,
            "plant_no_customer": row.plant_no_customer,
            "item": item_code,
            "delivery_date": row.delivery_date,
            "planned_qty": flt(row.delivery_quantity or 0),
            "new_efz": None,
        })

        key = (customer, row.order_no, item_code)
        plan_rows_by_key[key].append(plan_entry)
        customers.add(customer)

    # ✅ Her key için satırları tarih sırasına göre sırala
    for plan_list in plan_rows_by_key.values():
        plan_list.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )

    changes = []

    # ✅ ERP'deki açık Sales Order'ları al (SOI delivery_date ile!)
    open_sales_orders = fetch_open_sales_orders_with_item_dates(customers)

    erp_rows_by_key = defaultdict(list)

    for so in open_sales_orders:
        if not so.po_no:
            continue

        # ERP'nin hesapladığı pending_qty alanını öncelikle kullan; yoksa qty - delivered
        # pending_qty alanı varsa onu esas al; yoksa qty - delivered'a geri düş
        pending_qty = flt(getattr(so, "pending_qty", 0))
        if pending_qty is None or pending_qty == 0:
            pending_qty = flt(so.qty) - flt(so.delivered_qty)
        pending_qty = max(pending_qty, 0)
        if pending_qty <= 0:
            continue

        key = (so.customer, so.po_no, so.item_code)
        erp_rows_by_key[key].append(frappe._dict({
            "sales_order": so.sales_order,
            "sales_order_item": so.sales_order_item,
            "delivery_date": so.item_delivery_date,  # ✅ SOI delivery_date kullan
            "qty": flt(so.qty),
            "delivered_qty": flt(so.delivered_qty),
            "pending_qty": pending_qty,
        }))

    # ✅ ERP satırlarını da tarih sırasına göre sırala
    for erp_list in erp_rows_by_key.values():
        erp_list.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )

    # ✅ Her key için karşılaştırma yap
    all_keys = set(plan_rows_by_key.keys()) | set(erp_rows_by_key.keys())

    for key in all_keys:
        plan_rows = list(plan_rows_by_key.get(key, []))
        erp_rows = list(erp_rows_by_key.get(key, []))
        
        customer, order_no, item_code = key

        # ========================================
        # ADIM 1: TAM EŞLEŞENLERİ ÇIKAR (tarih + qty)
        # ========================================
        sig_to_plan_idx = defaultdict(list)
        for i, r in enumerate(plan_rows):
            sig = (str(r.delivery_date), int(r.planned_qty or 0))
            sig_to_plan_idx[sig].append(i)

        matched_plan_idx = set()
        matched_erp_idx = set()

        for j, erp in enumerate(erp_rows):
            open_qty = max(flt(getattr(erp, "pending_qty", 0)), 0)
            sig = (str(erp.delivery_date), int(open_qty))
            
            if sig_to_plan_idx.get(sig):
                i = sig_to_plan_idx[sig].pop()
                matched_plan_idx.add(i)
                matched_erp_idx.add(j)

        unmatched_plan = [
            r for i, r in enumerate(plan_rows) if i not in matched_plan_idx
        ]
        unmatched_erp = [
            r for j, r in enumerate(erp_rows) if j not in matched_erp_idx
        ]

        # Hiçbir şey kalmadıysa bu key için değişiklik yok
        if not unmatched_plan and not unmatched_erp:
            continue

        # ========================================
        # ADIM 2: AYNI TARİH İÇİN TOPLAM QTY KARŞILAŞTIRMASI
        # ========================================
        plan_by_date = defaultdict(list)
        erp_by_date = defaultdict(list)

        for r in unmatched_plan:
            plan_by_date[str(r.delivery_date)].append(r)

        for r in unmatched_erp:
            erp_by_date[str(r.delivery_date)].append(r)

        # Her iki tarafta da görünen tarihler
        common_dates = set(plan_by_date.keys()) & set(erp_by_date.keys())

        dates_to_drop_from_plan = set()
        dates_to_drop_from_erp = set()

        for date_str in common_dates:
            plan_list = plan_by_date[date_str]
            erp_list = erp_by_date[date_str]

            plan_total = sum(int(r.planned_qty or 0) for r in plan_list)
            erp_total = sum(int(flt(getattr(r, "pending_qty", 0))) for r in erp_list)

            # Temsilci satır
            sample_plan = plan_list[0] if plan_list else None
            sample_erp = erp_list[0] if erp_list else None

            if plan_total == erp_total:
                # ✅ Bu tarihte net değişiklik yok -> satırları düş
                dates_to_drop_from_plan.add(date_str)
                dates_to_drop_from_erp.add(date_str)
            else:
                # ✅ Miktar farkı var -> TEK BİR değişiklik kaydı oluştur
                qty_diff = plan_total - erp_total
                
                if qty_diff > 0:
                    change_type = "Miktar Artışı"
                else:
                    change_type = "Miktar Azalışı"

                # ERP referansı: ilk erp satırını kullan
                matched_so = sample_erp.sales_order if sample_erp else None
                matched_so_item = sample_erp.sales_order_item if sample_erp else None

                changes.append({
                    "order_no": order_no,
                    "order_item": sample_plan.order_item if sample_plan else (sample_erp.sales_order_item if sample_erp else None),
                    "part_no_customer": sample_plan.part_no_customer if sample_plan else None,
                    "plant_no_customer": sample_plan.plant_no_customer if sample_plan else None,
                    "customer": customer,
                    "item": item_code,
                    "change_type": change_type,
                    "old_delivery_date": date_str,
                    "new_delivery_date": date_str,
                    "old_delivery_quantity": erp_total,
                    "new_delivery_quantity": plan_total,
                    "difference": qty_diff,
                    "old_efz": sample_erp.sales_order if sample_erp else None,
                    "new_efz": sample_plan.new_efz if sample_plan else None,
                    "action_required": 1,
                    "action_status": "Beklemede",
                    "matched_sales_order": matched_so,
                    "matched_sales_order_item": matched_so_item,
                })

                # Bu tarihteki satırları düş
                dates_to_drop_from_plan.add(date_str)
                dates_to_drop_from_erp.add(date_str)

        # Tarihleri listelerden çıkar
        if dates_to_drop_from_plan:
            unmatched_plan = [
                r for r in unmatched_plan if str(r.delivery_date) not in dates_to_drop_from_plan
            ]
        if dates_to_drop_from_erp:
            unmatched_erp = [
                r for r in unmatched_erp if str(r.delivery_date) not in dates_to_drop_from_erp
            ]

        # Adım 2'den sonra da hiçbir şey kalmadıysa devam etme
        if not unmatched_plan and not unmatched_erp:
            continue

        # ========================================
        # ADIM 3: KALAN SATIRLARI TARİH SIRASINA GÖRE EŞLEŞTİR
        # ========================================
        unmatched_plan.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )
        unmatched_erp.sort(
            key=lambda r: getdate(r.delivery_date) if r.delivery_date else far_future
        )

        i = j = 0
        len_plan = len(unmatched_plan)
        len_erp = len(unmatched_erp)

        # ✅ ÖNCE: order_item referansı varsa onu eşleştir
        plan_with_ref = []
        plan_without_ref = []
        
        for plan in unmatched_plan:
            if plan.order_item:
                plan_with_ref.append(plan)
            else:
                plan_without_ref.append(plan)
        
        # Referanslı satırları eşleştir
        for plan in plan_with_ref:
            matched_erp = None
            matched_idx = None
            
            for idx, erp in enumerate(unmatched_erp):
                if erp.sales_order_item == plan.order_item:
                    matched_erp = erp
                    matched_idx = idx
                    break
            
            if matched_erp:
                # ✅ Eşleşme bulundu
                unmatched_erp.pop(matched_idx)
                
                open_qty = max(flt(getattr(matched_erp, "pending_qty", 0)), 0)
                new_qty = flt(plan.planned_qty)
                old_date = matched_erp.delivery_date  # ✅ SOI delivery_date
                new_date = plan.delivery_date or old_date

                change_type = determine_change_type_for_sync(open_qty, new_qty, old_date, new_date)
                
                if change_type:
                    changes.append({
                        "order_no": order_no,
                        "order_item": plan.order_item,
                        "part_no_customer": plan.part_no_customer,
                        "plant_no_customer": plan.plant_no_customer,
                        "customer": customer,
                        "item": item_code,
                        "change_type": change_type,
                        "old_delivery_date": old_date,
                        "new_delivery_date": new_date,
                        "old_delivery_quantity": open_qty,
                        "new_delivery_quantity": new_qty,
                        "difference": new_qty - open_qty,
                        "old_efz": None,
                        "new_efz": plan.new_efz,
                        "action_required": 1,
                        "action_status": "Beklemede",
                        "matched_sales_order": matched_erp.sales_order,
                        "matched_sales_order_item": matched_erp.sales_order_item,
                    })
            else:
                # ✅ ERP'de eşleşme yok -> Yeni Satır
                plan_without_ref.append(plan)
        
        # Referanssız satırları sırayla eşleştir
        unmatched_plan = plan_without_ref
        
        i = j = 0
        len_plan = len(unmatched_plan)
        len_erp = len(unmatched_erp)

        # Her iki tarafta da satır varken
        while i < len_plan and j < len_erp:
            plan = unmatched_plan[i]
            erp = unmatched_erp[j]

            open_qty = max(flt(getattr(erp, "pending_qty", 0)), 0)
            new_qty = flt(plan.planned_qty)
            old_date = erp.delivery_date  # ✅ SOI delivery_date
            new_date = plan.delivery_date or old_date

            change_type = determine_change_type_for_sync(open_qty, new_qty, old_date, new_date)
            
            if change_type:
                changes.append({
                    "order_no": order_no,
                    "order_item": plan.order_item,
                    "part_no_customer": plan.part_no_customer,
                    "plant_no_customer": plan.plant_no_customer,
                    "customer": customer,
                    "item": item_code,
                    "change_type": change_type,
                    "old_delivery_date": old_date,
                    "new_delivery_date": new_date,
                    "old_delivery_quantity": open_qty,
                    "new_delivery_quantity": new_qty,
                    "difference": new_qty - open_qty,
                    "old_efz": None,
                    "new_efz": plan.new_efz,
                    "action_required": 1,
                    "action_status": "Beklemede",
                    "matched_sales_order": erp.sales_order,
                    "matched_sales_order_item": erp.sales_order_item,
                })

            i += 1
            j += 1

        # ✅ Sadece Supply On tarafında kalan satırlar -> Yeni Satır
        while i < len_plan:
            plan = unmatched_plan[i]
            
            if flt(plan.planned_qty) > 0:
                changes.append({
                    "order_no": order_no,
                    "order_item": plan.order_item,
                    "part_no_customer": plan.part_no_customer,
                    "plant_no_customer": plan.plant_no_customer,
                    "customer": customer,
                    "item": item_code,
                    "change_type": "Yeni Satır",
                    "old_delivery_date": None,
                    "new_delivery_date": plan.delivery_date,
                    "old_delivery_quantity": 0,
                    "new_delivery_quantity": plan.planned_qty,
                    "difference": plan.planned_qty,
                    "old_efz": None,
                    "new_efz": plan.new_efz,
                    "action_required": 1,
                    "action_status": "Beklemede",
                    "matched_sales_order": None,
                    "matched_sales_order_item": None,
                })

            i += 1

        # ✅ Sadece ERP tarafında kalan satırlar -> Silinen Satır
        while j < len_erp:
            erp = unmatched_erp[j]
            open_qty = max(flt(getattr(erp, "pending_qty", 0)), 0)
            
            if open_qty > 0:
                changes.append({
                    "order_no": order_no,
                    "order_item": None,
                    "part_no_customer": None,
                    "plant_no_customer": None,
                    "customer": customer,
                    "item": item_code,
                    "change_type": "Silinen Satır",
                    "old_delivery_date": erp.delivery_date,  # ✅ SOI delivery_date
                    "new_delivery_date": erp.delivery_date,
                    "old_delivery_quantity": open_qty,
                    "new_delivery_quantity": 0,
                    "difference": -open_qty,
                    "old_efz": None,
                    "new_efz": None,
                    "action_required": 1,
                    "action_status": "Beklemede",
                    "matched_sales_order": erp.sales_order,
                    "matched_sales_order_item": erp.sales_order_item,
                })

            j += 1

    return changes

def fetch_open_sales_orders_with_item_dates(customers):
    """
    ✅ YENİ: Sales Order Item seviyesindeki delivery_date'i getir
    
    Verilen müşteri listesi için açık Sales Order kayıtlarını
    SOI (Sales Order Item) delivery_date ile getir.
    """
    if not customers:
        return []

    placeholders = ", ".join(["%s"] * len(customers))
    query = f"""
        SELECT
            so.name AS sales_order,
            soi.name AS sales_order_item,
            so.customer,
            so.po_no,
            soi.item_code,
            soi.qty,
            soi.delivered_qty,
            soi.pending_qty,
            soi.delivery_date AS item_delivery_date
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON so.name = soi.parent
        WHERE so.docstatus = 1
          AND so.status IN ('To Deliver', 'To Deliver and Bill')
          AND so.customer IN ({placeholders})
        ORDER BY so.customer, so.po_no, soi.item_code, soi.delivery_date
    """

    return frappe.db.sql(query, tuple(customers), as_dict=True)




def determine_change_type_for_sync(open_qty, new_qty, old_date, new_date):
    """
    Supply On planı ile ERP'deki açık miktarı karşılaştırarak change_type belirle.
    """
    open_qty = flt(open_qty)
    new_qty = flt(new_qty)

    if new_qty <= 0 and open_qty <= 0:
        return None

    if new_qty <= 0 and open_qty > 0:
        return "Silinen Satır"

    date_changed = False
    if new_date and old_date:
        date_changed = getdate(new_date) != getdate(old_date)
    elif new_date and not old_date:
        date_changed = True

    qty_changed = abs(new_qty - open_qty) > 0.0001

    if not qty_changed and not date_changed:
        return None

    if qty_changed and date_changed:
        return "Tarih ve Miktar Değişikliği"

    if qty_changed:
        return "Miktar Artışı" if new_qty > open_qty else "Miktar Azalışı"

    if date_changed:
        return "Tarih Değişikliği"

    return None


def group_changes_by_sales_order(changes):
    """
    ✅ DÜZELTİLMİŞ: Değişiklikleri Sales Order bazında grupla
    
    Eşleştirme mantığı:
    1. Customer + PO No + Item Code ile ara
    2. Bulamazsa NEW olarak işaretle
    """
    grouped = defaultdict(list)
    so_cache = {}
    
    for change in changes:
        customer = change.customer
        order_no = change.order_no  # ✅ Direkt kullan
        item_code = change.item
        
        so_name = getattr(change, "matched_sales_order", None)
        
        # ✅ Customer + PO No + Item ile ara ve her bir SO'yu yalnızca bir kez kullan
        if not so_name and customer and order_no and item_code and change.change_type != "Yeni Satır":
            key = (customer, order_no, item_code)
            available = so_cache.get(key)
            if available is None:
                rows = frappe.db.sql("""
                    SELECT DISTINCT so.name
                    FROM `tabSales Order` so
                    INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
                    WHERE so.customer = %s
                        AND so.po_no = %s
                        AND soi.item_code = %s
                        AND so.docstatus = 1
                        AND so.status IN ('To Deliver', 'To Deliver and Bill')
                    ORDER BY soi.delivery_date, so.transaction_date, so.name
                """, (customer, order_no, item_code), as_dict=True)
                available = [row.name for row in rows]
                so_cache[key] = available
            
            if available:
                so_name = available.pop(0)
        
        # Gruplama
        if so_name:
            key = (customer, order_no, so_name)
        else:
            key = (customer, order_no or "-", "NEW")
        
        grouped[key].append(change)
    
    return grouped


def process_sales_order_batch(so_identifier, changes):
    """
    ✅ DÜZELTİLMİŞ: Detayları doğru şekilde kaydet
    """
    customer, order_no, so_name = so_identifier
    details = []
    created = updated = closed = errors = 0
    
    if so_name == "NEW":
        # ✅ Manuel işlem gerekli - VERİLERİ DOĞRU KAYDET
        for change in changes:
            details.append({
                "action": "Error",
                "sales_order": None,
                "customer": customer,
                "item": change.item,  # ✅ Direkt kullan
                "order_no": change.order_no,  # ✅ Direkt kullan
                "order_item": change.order_item,  # ✅ Direkt kullan
                "old_qty": change.old_delivery_quantity,  # ✅ Direkt kullan
                "new_qty": change.new_delivery_quantity,  # ✅ Direkt kullan
                "old_date": change.old_delivery_date,  # ✅ Direkt kullan
                "new_date": change.new_delivery_date,  # ✅ Direkt kullan
                "change_type": change.change_type,
                "error_message": f"PO {order_no} için ERPNext'te Sales Order bulunamadı. Manuel oluşturulmalı."
            })
        
        errors = len(changes)
    
    else:
        # Mevcut SO güncelle
        result = update_existing_sales_order_batch(so_name, changes)
        details.extend(result['details'])
        updated = result.get('updated', 0)
        closed = result.get('closed', 0)
        errors = result.get('errors', 0)
    
    return {
        'details': details,
        'created': created,
        'updated': updated,
        'closed': closed,
        'errors': errors
    }


def update_existing_sales_order_batch(so_name, changes):
    """
    ✅ DÜZELTİLMİŞ: Sales Order Item seviyesinde delivery_date güncelle
    
    Mevcut Sales Order'ı toplu güncelle.

    KURALLAR:
    - Eşleştirme: sadece item_code (change.item) üzerinden yapılacak.
    - Yeni qty hesabı:
        new_total_qty = delivered_qty + new_delivery_quantity
    - Yeni tarih: SOI delivery_date güncellenir
    - Yeni satır (Yeni Satır) ERP'ye eklenmeyecek; sadece log'a yazılacak.
    - ERP güncellemesi için core fonksiyon:
        erpnext.controllers.accounts_controller.update_child_qty_rate
      kullanılacak.
    """
    details = []
    updated = closed = errors = 0
    earliest_new_order_date = None

    try:
        so = frappe.get_doc("Sales Order", so_name)

        if not so.items:
            frappe.log_error(f"Sales Order {so_name} has no items", "SO Update Error")
            return {
                "details": [{
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": so.customer if getattr(so, "customer", None) else None,
                    "error_message": "Sales Order'da hiç item yok."
                }],
                "updated": 0,
                "closed": 0,
                "errors": 1,
            }

        for change in changes:
            target_item = None
            for item in so.items:
                if item.item_code == getattr(change, "item", None):
                    target_item = item
                    break

            if not target_item:
                details.append({
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": getattr(change, "item", None),
                    "order_no": so.po_no,
                    "change_type": getattr(change, "change_type", None),
                    "error_message": "Sales Order içinde eşleşen item bulunamadı."
                })
                errors += 1
                continue

            change_type = getattr(change, "change_type", None)
            item_dict = target_item.as_dict()
            new_date = target_item.delivery_date
            action = None
            new_pending_qty = flt(getattr(change, "new_delivery_quantity", 0) or 0)

            if change_type != "Silinen Satır" and new_pending_qty <= 0:
                change_type = "Silinen Satır"
                if hasattr(change, "change_type"):
                    change.change_type = "Silinen Satır"
                change.new_delivery_quantity = 0

            detail_entry = None
            needs_update = False

            if change_type == "Silinen Satır":
                delivered_qty = flt(target_item.delivered_qty)
                billed_amt = flt(getattr(target_item, "billed_amt", 0))
                rate_for_billing = flt(target_item.rate) or flt(getattr(target_item, "base_rate", 0))
                billed_qty = flt(billed_amt / rate_for_billing) if rate_for_billing else 0
                protected_qty = max(delivered_qty, billed_qty)

                if protected_qty == 0 and len(so.items) == 1:
                    # Hiç teslimat/fatura yoksa siparişi iptal et ve sil
                    so.cancel()
                    frappe.delete_doc("Sales Order", so_name, force=1, ignore_permissions=True)

                    details.append({
                        "action": "Closed",
                        "sales_order": so_name,
                        "customer": so.customer,
                        "item": target_item.item_code,
                        "order_no": so.po_no,
                        "old_qty": target_item.qty,
                        "new_qty": 0,
                        "old_date": target_item.delivery_date,
                        "new_date": target_item.delivery_date,
                        "change_type": "Silinen Satır (SO cancelled & deleted - no deliveries made)",
                    })

                    return {
                        "details": details,
                        "updated": updated,
                        "closed": closed + 1,
                        "errors": errors,
                    }

                reason_bits = []
                if delivered_qty > 0:
                    # Parçalı teslim edilen satırı qty = delivered_qty yaparak kapat
                    reason_bits.append("Teslim edilen qty")

                if billed_qty > delivered_qty:
                    # Faturalandırılan miktarı koru
                    reason_bits.append("Faturalandırılan qty")

                if protected_qty > 0:
                    new_total_qty = protected_qty
                else:
                    # Teslimat ve fatura yoksa satır qty'sini sıfırla
                    new_total_qty = 0
                    reason_bits = ["Teslimat yok, qty sıfırlandı"]

                detail_change_type = "Silinen Satır (" + " ve ".join(reason_bits) + ")"

                item_dict["qty"] = new_total_qty
                item_dict["delivery_date"] = target_item.delivery_date
                action = "Closed"
                needs_update = True

                detail_entry = {
                    "action": "Closed",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "new_qty": new_total_qty,
                    "old_date": target_item.delivery_date,
                    "new_date": target_item.delivery_date,
                    "change_type": detail_change_type,
                }

            elif change_type in [
                "Miktar Artışı",
                "Miktar Azalışı",
                "Tarih Değişikliği",
                "Tarih ve Miktar Değişikliği",
            ]:
                desired_pending_qty = max(flt(getattr(change, "new_delivery_quantity", 0) or 0), 0)
                new_total_qty = flt(target_item.delivered_qty) + desired_pending_qty
                item_dict["qty"] = new_total_qty

                # ✅ Yeni tarih: SOI delivery_date güncellenir
                new_date = getattr(change, "new_delivery_date", None) or target_item.delivery_date
                item_dict["delivery_date"] = new_date
                # Tarih öne çekiliyorsa belge tarihini de uyarlamak üzere takip et
                if new_date:
                    if earliest_new_order_date is None or getdate(new_date) < getdate(earliest_new_order_date):
                        earliest_new_order_date = new_date
                action = "Updated"
                needs_update = True

                detail_entry = {
                    "action": "Updated",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "new_qty": new_total_qty,
                    "old_date": target_item.delivery_date,
                    "new_date": new_date,
                    "change_type": change_type,
                }

            elif change_type == "Yeni Satır":
                details.append({
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "new_qty": getattr(change, "new_delivery_quantity", None),
                    "old_date": target_item.delivery_date,
                    "new_date": getattr(change, "new_delivery_date", None),
                    "change_type": "Yeni Satır (ERP'ye eklenmedi)",
                    "error_message": "Kural: Her Sales Order tek satır. Yeni satır ERP'de manuel açılmalı.",
                })
                errors += 1
                continue

            else:
                details.append({
                    "action": "Error",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "item": target_item.item_code,
                    "order_no": so.po_no,
                    "old_qty": target_item.qty,
                    "old_date": target_item.delivery_date,
                    "change_type": change_type,
                    "error_message": f"Bilinmeyen change_type: {change_type}",
                })
                errors += 1
                continue

            if not needs_update:
                continue

            # ✅ SOI delivery_date'i string formatında hazırla
            delivery_date_value = item_dict.get("delivery_date") or target_item.delivery_date
            delivery_date_str = (
                str(getdate(delivery_date_value)) if delivery_date_value else None
            )

            trans_items = [{
                "docname": target_item.name,
                "item_code": target_item.item_code,
                "qty": item_dict["qty"],
                "rate": target_item.rate,
                "uom": target_item.uom,
                "conversion_factor": target_item.conversion_factor,
                "delivery_date": delivery_date_str,  # ✅ SOI delivery_date
            }]

            update_child_qty_rate(
                parent_doctype="Sales Order",
                trans_items=json.dumps(trans_items),
                parent_doctype_name=so.name,
                child_docname="items",
            )

            if action == "Closed":
                closed += 1
            elif action == "Updated":
                updated += 1

            so.reload()

            if detail_entry:
                details.append(detail_entry)

        # Eğer tüm satırlar 0'a çekildiyse ve teslimat/fatura yoksa siparişi iptal edip sil
        if so.docstatus == 1:
            has_delivery_or_billing = any(
                flt(it.delivered_qty) > 0 or flt(getattr(it, "billed_amt", 0)) > 0
                for it in so.items
            )
            all_zero_qty = all(flt(it.qty) <= 0 for it in so.items)

            if all_zero_qty and not has_delivery_or_billing:
                so.cancel()
                frappe.delete_doc("Sales Order", so_name, force=1, ignore_permissions=True)

                details.append({
                    "action": "Closed",
                    "sales_order": so_name,
                    "customer": so.customer,
                    "order_no": so.po_no,
                    "change_type": "Silinen Satır (SO cancelled & deleted - all items removed)",
                })

                return {
                    "details": details,
                    "updated": updated,
                    "closed": closed + 1,
                    "errors": errors,
                }

        # Belge tarihini gerekirse öne çek
        if earliest_new_order_date and getdate(earliest_new_order_date) < getdate(so.transaction_date):
            so.db_set("transaction_date", earliest_new_order_date, update_modified=False)

        return {
            "details": details,
            "updated": updated,
            "closed": closed,
            "errors": errors,
        }

    except Exception as e:
        frappe.log_error(f"Update SO Error: {str(e)}", "SO Update")

        for change in changes:
            details.append({
                "action": "Error",
                "sales_order": so_name,
                "customer": getattr(so, "customer", None) if "so" in locals() else getattr(change, "customer", None),
                "item": getattr(change, "item", None),
                "order_no": getattr(change, "order_no", None),
                "order_item": getattr(change, "order_item", None),
                "old_qty": getattr(change, "old_delivery_quantity", None),
                "new_qty": getattr(change, "new_delivery_quantity", None),
                "old_date": getattr(change, "old_delivery_date", None),
                "new_date": getattr(change, "new_delivery_date", None),
                "change_type": getattr(change, "change_type", None),
                "error_message": str(e),
            })

        return {
            "details": details,
            "updated": 0,
            "closed": 0,
            "errors": len(changes),
        }

def update_so_item_qty_rate(so_name, item_name, new_qty, rate):
    """
    ✅ ERPNext API fonksiyonunu çağırarak SO Item güncelle
    
    API: erpnext.controllers.accounts_controller.update_child_qty_rate
    
    Args:
        so_name: Sales Order name
        item_name: Sales Order Item name (child table row)
        new_qty: Yeni miktar
        rate: Item rate (fiyat)
    """
    from erpnext.controllers.accounts_controller import update_child_qty_rate
    
    try:
        # ✅ Doğrudan Python fonksiyonunu çağır
        update_child_qty_rate(
            parent_doctype="Sales Order",
            trans_items=[{
                "docname": item_name,  # SO Item'ın name'i (child row)
                "qty": new_qty,
                "rate": rate
            }],
            parent_doctype_name=so_name
        )
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(
            f"update_child_qty_rate failed for SO {so_name}, Item {item_name}: {str(e)}",
            "SO Item Update Error"
        )
        raise

def get_item_rate(item_code, customer):
    """
    Item için müşteriye özel fiyat al
    
    Dosya: api.py
    Çağrılır: update_existing_sales_order_batch() içinden
    """
    # Önce müşteriye özel fiyat
    rate = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "customer": customer,
            "selling": 1
        },
        "price_list_rate"
    )
    
    if not rate:
        # Standart fiyat listesinden
        default_price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
        
        if default_price_list:
            rate = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": item_code,
                    "price_list": default_price_list,
                    "selling": 1
                },
                "price_list_rate"
            )
    
    if not rate:
        # Item'ın standart rate'i
        rate = frappe.db.get_value("Item", item_code, "standard_rate")
    
    return flt(rate, 2) or 0

def get_delivery_time_for_plant(plant_no_customer):
    """
    Plant numarasına göre KTA Sevk Parametreleri'nden delivery_time (gün) döner.
    """
    if not plant_no_customer:
        return 0
    
    # Plant no'ya göre Address bul
    address_name = frappe.db.get_value(
        "Address",
        {"custom_eski_kod": plant_no_customer},
        "name"
    )
    
    if not address_name:
        return 0
    
    # Address üzerinden KTA Sevk Parametreleri kaydını bul
    delivery_time = frappe.db.get_value(
        "KTA Sevk Parametreleri",
        {"customer_address": address_name},
        "delivery_time"
    )
    
    return cint(delivery_time or 0)
    
def get_shipped_qty_for_window(customer, plant_no_customer, item_code, delivery_time_days):
    """
    Belirli müşteri + plant + item için
    (bugün - delivery_time_days, bugün] aralığında sevk edilen toplam qty.
    """
    if not (customer and plant_no_customer and item_code and delivery_time_days > 0):
        return 0

    end_date = getdate(today())
    start_date = add_days(end_date, -delivery_time_days)

    # shipping_address_name → Address.custom_eski_kod = plant_no_customer
    rows = frappe.db.sql("""
        SELECT SUM(dni.qty) AS total_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        LEFT JOIN `tabAddress` addr ON addr.name = dn.shipping_address_name
        WHERE dn.docstatus = 1
          AND dn.posting_date BETWEEN %s AND %s
          AND dni.item_code = %s
          AND dn.customer = %s
          AND COALESCE(addr.custom_eski_kod, '') = %s
    """, (start_date, end_date, item_code, customer, plant_no_customer), as_dict=True)

    total = rows[0].total_qty if rows and rows[0].total_qty is not None else 0
    return flt(total)


def adjust_supply_on_with_shipments(rows):
    """
    Verilen Supply On satır listesi üzerinde, sevk parametresi + sevk irsaliyelerini
    dikkate alarak teslimat miktarlarını düşer.

    Grup = (plant_no_customer, part_no_customer)
    Her grup için:
      - plant'tan delivery_time alınır
      - customer + item map edilir (get_customer_and_item)
      - verilen pencere için Delivery Note'larda sevk edilen qty bulunur
      - shipped_qty, en yakın teslim tarihinden başlayarak satırlardan düşülür
    """
    # İrsaliye düşümü geçici olarak devre dışı
    # Aşağıdaki blok daha önce sevk edilen qty'leri düşüyordu.
    # ileride yeniden aktifleştirilmek üzere korunuyor.
    #
    # # plant + part bazında grupla
    # groups = defaultdict(list)
    # for r in rows:
    #     key = (r.plant_no_customer, r.part_no_customer)
    #     groups[key].append(r)
    #
    # for (plant_no, part_no), group_rows in groups.items():
    #     # Customer + Item mapping
    #     customer, item_code = get_customer_and_item(plant_no, part_no)
    #     if not (customer and item_code):
    #         continue
    #
    #     delivery_time_days = get_delivery_time_for_plant(plant_no)
    #     if delivery_time_days <= 0:
    #         continue
    #
    #     shipped_qty = get_shipped_qty_for_window(customer, plant_no, item_code, delivery_time_days)
    #     if shipped_qty <= 0:
    #         continue
    #
    #     # En yakın teslimat tarihinden başlayarak sırala
    #     group_rows.sort(
    #         key=lambda r: getdate(r.delivery_date) if r.delivery_date else getdate("1900-01-01")
    #     )
    #
    #     # shipped_qty'yi satırlara uygula
    #     for r in group_rows:
    #         if shipped_qty <= 0:
    #             break
    #
    #         row_qty = flt(r.delivery_quantity or 0)
    #         if row_qty <= 0:
    #             continue
    #
    #         consume = min(shipped_qty, row_qty)
    #         r.delivery_quantity = row_qty - consume
    #         shipped_qty -= consume

    return rows
