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
def print_to_zebra_kta(gr_number=None, label=None):
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
    if not gr_number and not label:
        frappe.msgprint("Either `gr_number` or `label` must be provided.")
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

        for data in frappe.get_all("KTA Depo Etiketleri", filters=query_filter,
                                   fields={"item_code", "qty", "uom", "sut_barcode", "item_name",
                                           "supplier_delivery_note",
                                           "gr_posting_date"}):
            if data.qty % 1 == 0:
                data.qty = format_decimal(f"{data.qty:g}", locale='tr_TR')
            else:
                data.qty = format_decimal(f"{data.qty:.2f}", locale='tr_TR')
            # "10.41.10.23", 9100
            # formatted_data = zebra_formatter(data)
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
