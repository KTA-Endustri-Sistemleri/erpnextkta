import socket
import frappe
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
DOCTYPE_KTA_SUPPLY_ON_HEAD = "KTA Supply On Head"
DOCTYPE_KTA_SUPPLY_ON = "KTA Supply On"
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
VALUE_TABLE_EVALUATION = "table_evaluation"


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
            FIELD_PARENTFIELD: VALUE_ENTRIES,
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
            formatted_data = zebra_formatter(DOCTYPE_KTA_DEPO_ETIKETLERI, data)
            send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)

    if remainder_qty > 0:
        data.qty = format_kta_label_qty(remainder_qty)
        data.sut_no = f"{batch_no}{num_packs + 1:04d}"
        formatted_data = zebra_formatter(DOCTYPE_KTA_DEPO_ETIKETLERI, data)
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
def process_supply_on(supply_on):
    supply_on_doc = frappe.get_doc(DOCTYPE_KTA_SUPPLY_ON_HEAD, supply_on)
    supply_on_doc.set(VALUE_TABLE_EVALUATION, [])
    supply_on_doc.save()

    supply_on_balances = get_balances_from_supply_on(supply_on)

    if not supply_on_balances:
        frappe.throw(f"No supply on balances found for supply on: {supply_on}")
        return

    for balance in supply_on_balances:
        errors = {"plant_no": None, "part_no": None, "bom": None}

        # Process customer
        customer = None
        if balance.plant_no_customer:
            # First find the address using custom_eski_kod field
            address = frappe.get_value(DOCTYPE_ADDRESS, {"custom_eski_kod": balance.plant_no_customer}, "name")
            if address:
                # Then find the customer through the links child table
                address_doc = frappe.get_doc(DOCTYPE_ADDRESS, address)
                customer = None
                for link in address_doc.links:
                    if link.link_doctype == DOCTYPE_CUSTOMER:
                        customer = link.link_name
                        break
                
                if not customer:
                    errors["plant_no"] = f"Address {address} için Customer linki bulunamadı"
            else:
                # No address found with custom_eski_kod
                errors["plant_no"] = f"{balance.plant_no_customer} ile Address bulunamadı"
                customer = None

        # Process item
        item = None
        if balance.part_no_customer and customer:
            item = frappe.get_value(DOCTYPE_ITEM, balance.part_no_customer, FIELD_NAME)
            if not item:
                ref_item = frappe.get_value(
                    DOCTYPE_ITEM_CUSTOMER_DETAIL,
                    {FIELD_REF_CODE: balance.part_no_customer, FIELD_CUSTOMER_NAME: customer},
                    FIELD_PARENT
                )
                if ref_item:
                    item = ref_item
                else:
                    errors["part_no"] = f"Item {balance.part_no_customer} bulunamadı"

        # Get last delivery note if item exists
        last_delivery = [{'max_custom_irsaliye_no': None, 'lr_date': None}]
        if item and customer:
            last_delivery = get_last_delivery_note(customer, item)

        if item:
            if not frappe.get_all(DOCTYPE_BOM, filters={"item": item, "is_default": 1}, limit=1):
                errors["bom"] = "Varsayılan BOM bulunamadı"

        # Append evaluation data
        supply_on_doc.append(
            VALUE_TABLE_EVALUATION,
            {
                FIELD_PLANT_NO_CUSTOMER: balance.plant_no_customer,
                "plant_no_error_message": errors["plant_no"],
                FIELD_PART_NO_CUSTOMER: balance.part_no_customer,
                "part_no_error_message": errors["part_no"],
                "part_no_bom_error_message": errors["bom"],
                "total_qty": balance.total_qty,
                "closed_qty": balance.closed_qty,
                "balance_qty": balance.balance_qty,
                "customer": customer,
                "item": item,
                "last_delivery_note": balance.delivery_note_no,
                "last_delivery_date": balance.delivery_note_date,
                "kta_last_delivery_note": last_delivery[0]['max_custom_irsaliye_no'] if last_delivery else None,
                "kta_last_delivery_date": last_delivery[0]['lr_date'] if last_delivery else None
            }
        )

    supply_on_doc.save()
    return True


def get_last_delivery_note(customer_name, item_name):
    return frappe.db.sql("""SELECT MAX(tdn.custom_irsaliye_no) AS max_custom_irsaliye_no,
                                   tdn.lr_date
                            FROM `tabDelivery Note` tdn
                                     INNER JOIN `tabDelivery Note Item` tdni
                                                ON tdn.name = tdni.parent
                                                    AND tdni.item_code = %s
                                     INNER JOIN (SELECT MAX(dn.lr_date) as max_date
                                                 FROM `tabDelivery Note` dn
                                                          INNER JOIN `tabDelivery Note Item` dni
                                                                     ON dn.name = dni.parent
                                                                         AND dni.item_code = %s
                                                 WHERE dn.customer = %s
                                                   AND dn.docstatus = 1
                                                   AND dn.is_return = 0) latest ON tdn.lr_date = latest.max_date
                            WHERE tdn.customer = %s
                              AND tdn.is_return = 0
                              AND tdn.docstatus = 1
                            GROUP BY tdn.lr_date;
                         """, (item_name, item_name, customer_name, customer_name), as_dict=True)


def get_balances_from_supply_on(supply_on):
    return frappe.db.sql("""
                         SELECT plant_no_customer,
                                part_no_customer,
                                delivery_note_no,
                                delivery_note_date,
                                MAX(EFZ)                     AS `total_qty`,
                                MAX(EFZ_customer)            AS `closed_qty`,
                                MAX(EFZ) - MAX(EFZ_customer) AS `balance_qty`
                         FROM `tabKTA Supply On`
                         WHERE parent = %s
                           AND parenttype = %s
                         GROUP BY plant_no_customer,
                                  part_no_customer,
                                  delivery_note_no,
                                  delivery_note_date
                         """, (supply_on, DOCTYPE_KTA_SUPPLY_ON_HEAD), as_dict=True)


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

        item_code = row.parca_no
        qty = row.miktar
        uom = row.birim
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
        if getattr(row, FIELD_HURDA_NEDENI, None):
            desc_bits.append(f"Hurda Nedeni: {row.hurda_nedeni}")
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