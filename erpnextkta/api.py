import frappe
import socket
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
            'Party Account',
            {'parent': customer, 'parenttype': 'Customer', 'company': company},
            'customer_income_account'  # Fetch the customer_income_account field
        )

        frappe.logger().info(f"Fetched customer income account: {customer_income_account}")
        return customer_income_account
    except Exception as e:
        frappe.log_error(f"Error fetching customer income account: {e}")
        return None


@frappe.whitelist()
def print_to_zebra_kta(gr_number=None, label=None, q_ref=None):
    # Get the current logged-in user
    user = frappe.session.user

    # Query the printer for this user that is both enabled and marked as default
    printer = frappe.db.get_value(
        "KTA User Zebra Printers",
        {
            "user": user,
            "disabled": 0
            # "is_default": 1 # Assuming there's a field to mark default printers
        },
        ["printer"]
    )
    if not gr_number and not label and not q_ref:
        frappe.msgprint("Either `gr_number`, `label` or 'q_ref' must be provided.")
        return
    if printer is not None:
        zebra_printer = frappe.get_doc("KTA Zebra Printers", printer)
        ip_address = zebra_printer.get("ip")
        port = zebra_printer.get("port")

        query_filter = {}
        if gr_number:
            query_filter = {"gr_number": gr_number}
        elif label:
            query_filter = {"name": label}
        elif q_ref:
            query_filter = {"quality_ref": q_ref}

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
            if data.qty % 1 == 0:
                data.qty = format_decimal(f"{data.qty:g}", locale='tr_TR')
            else:
                data.qty = format_decimal(f"{data.qty:.2f}", locale='tr_TR')
            formatted_data = zebra_formatter("KTA Depo Etiketleri", data)
            send_data_to_zebra(formatted_data, ip_address, port)

    else:
        frappe.msgprint("No default printer found for the current user.")


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

        num_packs = 1
        remainder_qty = 0
        split_qty = row.custom_split_qty

        if row.custom_do_not_split == 0:
            num_packs = frappe.cint(row.stock_qty // split_qty)  # Use row.stock_qty directly
            remainder_qty = row.stock_qty % split_qty

        if num_packs >= 1:
            # Use range to run the loop exactly num_packs times
            for pack in range(1, num_packs + 1):
                custom_create_packages(row, row_batch_number, split_qty, pack, q_ref)

        if remainder_qty > 0:
            custom_create_packages(row, row_batch_number, remainder_qty, num_packs + 1, q_ref)


def custom_create_packages(row, batch_no, qty, pack_no, q_ref):
    etiket_item_group = frappe.db.get_value("Item", row.item_code, 'item_group')
    purchase_receipt = frappe.get_doc("Purchase Receipt", row.parent)

    etiket = frappe.get_doc(
        dict(
            doctype="KTA Depo Etiketleri",
            gr_number=row.parent,
            supplier_delivery_note=purchase_receipt.supplier_delivery_note,
            qty=qty,
            uom=row.stock_uom,
            batch=batch_no,
            gr_posting_date=purchase_receipt.posting_date,
            item_code=row.item_code,
            sut_barcode=f"{batch_no}{pack_no:04d}",
            item_name=row.item_name,
            item_group=etiket_item_group,
            quality_ref=q_ref
        )
    )
    etiket.insert()

    frappe.db.commit()
