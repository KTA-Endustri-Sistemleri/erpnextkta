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
    for data in frappe.get_all(doctype="KTA Depo Etiketleri",
                               filters=query_filter,
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

    splits = frappe.get_all(doctype=kta_depo_etiketleri_bolme_doctype,
                            filters=split_query_filter,
                            fields={"idx",
                                    "qty"})

    query_filter = {"do_not_split": 1, "name": label}

    label = frappe.db.get_value(doctype=kta_depo_etiketleri_doctype,
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
def print_kta_wo_labels(work_order):
    # Constants for DocTypes
    stock_entry_doctype = "Stock Entry"
    stock_entry_type = "Manufacture"

    details_of_wo = get_details_of_wo_for_label(work_order)

    for stock_entry in frappe.get_all(
            doctype=stock_entry_doctype,
            filters={
                "stock_entry_type": stock_entry_type,
                "work_order": work_order
            },
            fields=[
                "name"
            ]
    ):
        print_kta_wo_label(details_of_wo, stock_entry.name)


@frappe.whitelist()
def print_kta_wo_labels_of_stock_entry(stock_entry):
    # Constants for DocTypes
    stock_entry_doctype = "Stock Entry"

    stock_entry_doc = frappe.get_doc(stock_entry_doctype, stock_entry)

    print_kta_wo_label(get_details_of_wo_for_label(stock_entry_doc.get("work_order")), stock_entry)


def get_details_of_wo_for_label(work_order):
    # Constants for DocTypes
    bom_doctype = "BOM"
    item_doctype = "Item"
    item_customer_detail_doctype = "Item Customer Detail"
    item_customer_detail_parentfield = "customer_items"
    work_order_doctype = "Work Order"

    work_order_doc = frappe.get_doc(work_order_doctype, work_order)

    bom_doc = frappe.get_doc(bom_doctype, work_order_doc.get("bom_no"))
    material_index = "-"
    meta = frappe.get_meta("BOM")
    if meta.has_field("custom_musteri_indeksi_no"):
        material_index = bom_doc.get("custom_musteri_indeksi_no")

    musteri_paketleme_miktari = frappe.db.get_value(
        doctype=item_customer_detail_doctype,
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
        return None

    return {
        "work_order": work_order_doc.get("name"),
        "description": work_order_doc.get("description"),
        "stock_uom": work_order_doc.get("stock_uom"),
        "production_item": work_order_doc.get("production_item"),
        "material_index": material_index,
        "musteri_paketleme_miktari": musteri_paketleme_miktari
    }


def print_kta_wo_label(work_order_details, stock_entry):
    stock_entry_detail_doctype = "Stock Entry Detail"
    stock_entry_detail_docstatus = 1
    stock_entry_detail_is_finished_item = 1
    stock_entry_detail_parentfield = "items"
    stock_entry_doctype = "Stock Entry"
    kta_is_emri_etiketleri_name = "KTA İş Emri Etiketleri"
    virtual_doctype = "KTA Is Emri Etiketleri"

    source_warehouse = stock_entry

    stock_entry_detail = frappe.get_all(
        doctype=stock_entry_detail_doctype,
        filters={
            "parent": stock_entry,
            "parenttype": stock_entry_doctype,
            "parentfield": stock_entry_detail_parentfield,
            "item_code": work_order_details.get("production_item"),
            "is_finished_item": stock_entry_detail_is_finished_item,
            "docstatus": stock_entry_detail_docstatus,
            "t_warehouse": ["is", "set"]
        },
        fields=[
            "name"
        ],
        as_list=True
    )
    if len(stock_entry_detail) > 1:
        frappe.throw(f"More than one Inward Type of Transaction found for Stock Entry: {stock_entry}")
        return

    stock_entry_detail_doc = frappe.get_doc(stock_entry_detail_doctype, stock_entry_detail[0])

    stock_entry_doc = frappe.get_doc(stock_entry_doctype, stock_entry)

    destination_warehouse = stock_entry_doc.get("to_warehouse")
    if not destination_warehouse:
        destination_warehouse = stock_entry_detail_doc.get("t_warehouse")

    batch_no = get_batch_from_stock_entry_detail(stock_entry_detail_doc)

    # Construct data
    data = frappe.get_doc({
        'doctype': virtual_doctype,
        'print_date': frappe.utils.nowdate(),
        'material_number': work_order_details.get("production_item"),
        'material_description': work_order_details.get("description"),
        'material_index': work_order_details.get("material_index"),
        'work_order': work_order_details.get("work_order"),
        'gr_posting_date': frappe.utils.get_date_str(stock_entry_doc.get("posting_date")),
        'gr_number': stock_entry,
        'gr_source_warehouse': source_warehouse,
        'to_warehouse': destination_warehouse,
        'stock_uom': work_order_details.get("stock_uom"),
        'batch_no': batch_no
    })
    musteri_paketleme_miktari = work_order_details.get("musteri_paketleme_miktari")
    num_packs = frappe.cint(stock_entry_detail_doc.get("qty") // musteri_paketleme_miktari)
    remainder_qty = stock_entry_detail_doc.get("qty") % musteri_paketleme_miktari

    zebra_printer = get_zebra_printer_for_user()
    zebra_ip_address = zebra_printer.get("ip")
    zebra_port = zebra_printer.get("port")

    if num_packs >= 1:
        # Use range to run the loop exactly num_packs times
        for pack in range(1, num_packs + 1):
            data.qty = format_kta_label_qty(musteri_paketleme_miktari)
            data.sut_no = f"{batch_no}{pack:04d}"
            formatted_data = zebra_formatter(kta_is_emri_etiketleri_name, data)
            send_data_to_zebra(formatted_data, zebra_ip_address, zebra_port)

    if remainder_qty > 0:
        data.qty = format_kta_label_qty(remainder_qty)
        data.sut_no = f"{batch_no}{num_packs + 1:04d}"
        formatted_data = zebra_formatter(kta_is_emri_etiketleri_name, data)
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
    doc = frappe.get_doc("KTA Zebra Templates", doctype_name)
    return doc.get("zebra_template").format(data=data)


def custom_split_kta_batches(row=None, q_ref="ATLA 5/1"):
    # for row in self.get(table_name):
    if row.serial_and_batch_bundle:
        row_batch_number = frappe.db.get_value(
            doctype="Serial and Batch Entry",
            filters={"parent": row.serial_and_batch_bundle},
            fieldname="batch_no"
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
        doctype="KTA User Zebra Printers",
        filters={
            "user": user,
            "disabled": 0
        },
        fieldname="printer"
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
            "batch_no": ["is", "set"],
            "docstatus": 1
        },
        fieldname="batch_no"
    )
    if not batch_no:
        frappe.throw(f"More than one batch found for Stock Entry Detail: {stock_entry_detail.name}")
        return None

    return batch_no


@frappe.whitelist()
def find_bins_of_sut(sut, mobil):
    # Constants for DocTypes
    label = get_label_item_batch(sut)

    sabe_parents = get_sabe_parents_of_bins_for_batch(get_bins_of_item(label.item_code), label.batch)

    sle_entries = get_warehouse_quantity_for_sabe_parents(sabe_parents)

    if len(sle_entries) == 0:
        frappe.throw(f"No Stock Ledger Entries found for SUT: {sut}")

    parent_doctype = "KTA Mobil Depo"
    # Get the parent document

    child_doctype = "KTA Mobil Depo Kalemi"
    child_table_name = "mobile_items"
    for sle_entry in sle_entries:
        # Append to child table
        child = frappe.new_doc(
            doctype=child_doctype,
            parent=mobil,
            parentfield=child_table_name,
            parenttype=parent_doctype,
            sut_barcode=sut,
            item_code=label.item_code,
            batch=label.batch,
            source_warehouse=sle_entry.warehouse,
            qty=sle_entry.balance_qty
        )
        child.insert()


def get_label_item_batch(sut):
    label_doctype = "KTA Depo Etiketleri"
    items = frappe.get_all(
        doctype=label_doctype,
        filters={
            "sut_barcode": sut,
            "do_not_split": 0
        },
        fields=[
            "item_code",
            "batch"
        ]
    )
    number_of_items = len(items)
    if number_of_items > 1:
        return None
    elif number_of_items == 0:
        return None
    return items[0]


def get_bins_of_item(item, empty=None):
    bin_doctype = "Bin"
    query_filter = {"item_code": item}
    if empty:
        query_filter["actual_qty"] = 0
    else:
        query_filter["actual_qty"] = [">", 0]

    return frappe.get_all(
        doctype=bin_doctype,
        filters=query_filter,
        fields=[
            "warehouse"
        ],
        pluck="warehouse"
    )


def get_sabe_parents_of_bins_for_batch(bins, batch):
    sabb_doctype = "Serial and Batch Bundle"
    sabe_doctype = "Serial and Batch Entry"
    sabe_parentfield = "entries"
    return frappe.get_all(
        doctype=sabe_doctype,
        filters={
            "warehouse": ["in", bins],
            "batch_no": batch,
            "parenttype": sabb_doctype,
            "parentfield": sabe_parentfield,
            "docstatus": 1
        },
        fields=[
            "parent"
        ],
        pluck="parent"
    )


def get_warehouse_quantity_for_sabe_parents(sabe_parents):
    sle_doctype = "Stock Ledger Entry"
    return frappe.get_all(
        doctype=sle_doctype,
        filters={
            "serial_and_batch_bundle": ["in", sabe_parents],
            "docstatus": 1,
            "is_cancelled": 0
        },
        fields=[
            "warehouse",
            "sum(actual_qty) as balance_qty"
        ]
    )


@frappe.whitelist()
def clear_warehouse_labels():
    label_doctype_name = "KTA Depo Etiketleri"
    label_doctype = frappe.qb.DocType(label_doctype_name)
    item_code = frappe.qb.Field("item_code")
    batch = frappe.qb.Field("batch")

    results = (
        frappe.qb.from_(label_doctype)
        .select(item_code, batch)
        .groupby(item_code, batch)
    ).run(as_dict=True)

    for result in results:
        if len(get_sabe_parents_of_bins_for_batch(get_bins_of_item(result.item_code), result.batch)) == 0:
            labels_to_delete = (
                frappe.qb.from_(label_doctype)
                .select("name")
                .where((item_code == result.item_code) & (batch == result.batch))
            ).run()
            frappe.db.delete(label_doctype_name, filters={"name": labels_to_delete})

    return frappe.utils.nowdate()


@frappe.whitelist()
def process_supply_on(supply_on):
    supply_on_doctype = "KTA Supply On Head"
    supply_on = frappe.get_doc(supply_on_doctype, supply_on)
    supply_on_eval_table = "table_evaluation"

    # Clear all existing child table items before processing new ones
    supply_on.set("table_evaluation", [])
    supply_on.save()

    supply_on_balances = get_balances_from_supply_on(supply_on.name)

    if not supply_on_balances:
        frappe.throw(f"No supply on balances found for supply on: {supply_on.name}")
        return

    for balance in supply_on_balances:
        # Initialize error messages
        errors = {
            "plant_no": None,
            "part_no": None,
            "bom": None
        }

        # Process customer
        customer = None
        if balance.plant_no_customer:
            customer = frappe.get_value("Customer",
                                        {"custom_eski_kod": balance.plant_no_customer},
                                        "name")
            if not customer:
                errors["plant_no"] = f"{balance.plant_no_customer} ile Müşteri Bulunamadı"
            elif isinstance(customer, list):
                errors["plant_no"] = f"Multiple customers found for ID {balance.plant_no_customer}"
                customer = None

        # Process item
        item = None
        if balance.part_no_customer and customer:
            # First try direct item match
            item = frappe.get_value("Item", balance.part_no_customer, "name")

            # If not found, try customer reference
            if not item:
                ref_item = frappe.get_value("Item Customer Detail",
                                            {"ref_code": balance.part_no_customer,
                                             "customer_name": customer},
                                            "parent")
                if ref_item:
                    item = ref_item
                else:
                    errors["part_no"] = f"Item {balance.part_no_customer} bulunamadı"

        # Get last delivery note if item exists
        last_delivery = [{'max_custom_irsaliye_no': None, 'lr_date': None}]
        if item and customer:
            last_delivery = get_last_delivery_note(customer, item)
        if item:
            # Check for BOM
            if not frappe.get_all("BOM", filters={"item": item, "is_default": 1}, limit=1):
                errors["bom"] = "Varsayılan BOM bulunamadı"

        # Append evaluation data
        supply_on.append(
            supply_on_eval_table,
            {
                "plant_no_customer": balance.plant_no_customer,
                "plant_no_error_message": errors["plant_no"],
                "part_no_customer": balance.part_no_customer,
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

    supply_on.save()
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


def get_data(conditions, filters):
    conditions = ""
    if filters.get("from_date") and filters.get("to_date"):
        conditions += " and so.transaction_date between %(from_date)s and %(to_date)s"

    if filters.get("company"):
        conditions += " and so.company = %(company)s"

    if filters.get("sales_order"):
        conditions += " and so.name in %(sales_order)s"

    if filters.get("status"):
        conditions += " and so.status in %(status)s"

    if filters.get("warehouse"):
        conditions += " and soi.warehouse = %(warehouse)s"

    data = frappe.db.sql(
        f"""
        SELECT
            so.transaction_date as date,
            soi.delivery_date AS `delivery_date`,
            so.name AS `sales_order`,
            so.status,
            so.customer,
            soi.item_code,
            DATEDIFF(CURRENT_DATE, soi.delivery_date) AS `delay_days`,
            IF(so.status in ('Completed','To Bill'), 0, (SELECT delay_days)) AS `delay`,
            soi.qty,
            soi.delivered_qty,
            (soi.qty - soi.delivered_qty) AS `pending_qty`,
            IFNULL(SUM(sii.qty), 0) AS `billed_qty`,
            soi.base_amount AS `amount`,
            (soi.delivered_qty * soi.base_rate) AS `delivered_qty_amount`,
            (soi.billed_amt * IFNULL(so.conversion_rate, 1)) AS `billed_amount`,
            (soi.base_amount - (soi.billed_amt * IFNULL(so.conversion_rate, 1))) AS `pending_amount`,
            soi.warehouse AS `warehouse`,
            so.company,
            soi.name,
            soi.description AS `description`
        FROM
            `tabSales Order` so,
            `tabSales Order Item` soi
        LEFT JOIN `tabSales Invoice Item` sii
            ON sii.so_detail = soi.name and sii.docstatus = 1
        WHERE
            soi.parent = so.name
            and so.status not in ('Stopped', 'On Hold')
            and so.docstatus = 1
            and soi.item_code = 
            {conditions}
        GROUP BY soi.name, so.transaction_date, soi.item_code
    """,
        filters,
        as_dict=1,
    )

    return data


def get_balances_from_supply_on(supply_on):
    supply_on_doctype = "KTA Supply On Head"
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
                         """, (supply_on, supply_on_doctype), as_dict=True)


@frappe.whitelist()
def get_items_from_calisma_karti(source_name: str, target_doc=None):
    """
    Stock Entry > Get Items From > Calisma Karti
    'Calisma Karti' içindeki 'Calisma Karti Hurda' satırlarını,
    Stock Entry 'items' formatında döndürür.
    NOTE: map_current_doc bu fonksiyonu (source_name, target_doc) imzasıyla çağırır.
    """
    if not source_name:
        frappe.throw("Çalışma Kartı seçilmedi.")

    doc = frappe.get_doc("Calisma Karti", source_name)

    # Parent'tan varsayılan kaynak depo (alan adın farklıysa buraya ekleyebilirsin)
    parent_src_wh = (
            getattr(doc, "source_warehouse", None)
            or getattr(doc, "s_warehouse", None)
            or getattr(doc, "warehouse", None)
            or None
    )

    items = []
    # Parent'taki tablo alan adını bilmesek de güvenli yöntemi kullan:
    for row in doc.get_all_children():
        if row.doctype != "Calisma Karti Hurda":
            continue

        item_code = row.parca_no
        qty = row.miktar
        uom = row.birim  # Link → UOM
        row_src_wh = getattr(row, "depo", None)  # Link → Warehouse
        s_wh = row_src_wh or parent_src_wh

        if not item_code or not qty:
            continue

        item = frappe.db.get_value(
            "Item", item_code, ["item_name", "stock_uom", "description"], as_dict=True
        )
        if not item:
            frappe.throw(f"Item bulunamadı: {item_code}")

        stock_uom = item.stock_uom
        uom_final = uom or stock_uom

        # UOM dönüşüm faktörü
        conv = 1.0
        if uom and uom != stock_uom:
            conv_row = frappe.db.get_value(
                "UOM Conversion Detail",
                {"parent": item_code, "uom": uom},
                "conversion_factor",
            )
            conv = float(conv_row) if conv_row else 1.0

        # Açıklama + hurda nedeni
        desc_bits = []
        if item.description:
            desc_bits.append(item.description)
        if getattr(row, "hurda_nedeni", None):
            desc_bits.append(f"Hurda Nedeni: {row.hurda_nedeni}")
        description = " | ".join(desc_bits) if desc_bits else item.item_name

        items.append({
            "item_code": item_code,
            "item_name": item.item_name,
            "description": description,
            "uom": uom_final,
            "stock_uom": stock_uom,
            "conversion_factor": conv,
            "qty": qty,
            "s_warehouse": s_wh,  # Material Issue mantığı: kaynak depo
        })

    if not items:
        frappe.throw("Seçilen Çalışma Kartında aktarılabilir hurda satırı yok.")

    return items
