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
            formatted_data = zebra_formatter_2("KTA Depo Etiketleri", data)
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


def zebra_formatter(data):
    return f"""
            CT~~CD,~CC^~CT~
            ^XA
            ~TA000
            ~JSN
            ^LT0
            ^MNW
            ^MTT
            ^PON
            ^PMN
            ^LH0,0
            ^JMA
            ^PR5,5
            ~SD15
            ^JUS
            ^LRN
            ^CI27
            ^PA0,1,1,0
            ^XZ
            ^XA
            ^MMT
            ^PW799
            ^LL480
            ^LS0
            ^FO24,142^GFA,397,848,16,:Z64:eJzN0jFuwyAUBuAfIfWN7wbmIo59lRyDwa2JOnTMlah6j4gjMDJYoY9ASJ2hXcv2Wcj8/4N5g3GUPVaoBGC+wnjKQWWvtuJ8c9TyqdrN4lQ+FY/sDoFc4s+oL8V0s2Wku1+LDY50qfttlP0DQOf6P3GODyM187nmiVbyFJMTp5vd3SOUhPnwA44mN2/0HgySkVbNp8DdOox0ivwVJ13tB8kjR44qdFvp20zFi8xjaXZy8CTzsoh4rAn7RX/45ckL/sUaddAJq0yZq8nzFeu1m53JWHO3KVf4wxPe2Ft2dy+w2lvqTvIwgiXffIiIKsiW5nK/v3p78rT3NOwt+XbnjYyFSp7U+9S829z6utpHKtd5+Nq3O9R5zFu1avPi+hi+Ae+hzhU=:AC7A
            ^FO24,70^GFA,349,848,16,:Z64:eJzN0j1uwzAMBeBnCChH3cC6iGtfJcfQ4KIyMmTMhTqo6D0CHYGjBiMq5Z/E0pCu5fYJgvhIaJhhHCWPTzQRwHCH8ZRCk3wzZ6fFrORotRvEMR9ld9q9B3JRf7O6ZdNiqxF3f2QbnOi23rcs91uArut74sRPI27W1zUPW8mTTU4cF7vdHRoJc/EtTiZtnukcDKKRqTZPQT+sQkcT6x/u1WrfSh5p2TXhYSvzbqbsUfYxbnbSuJd9WTCe1aMs+sNvlUf8i1KMxHnQ3RFprnw/mGp/gU1lfbDOng5uwfTCpnKrX1v+T2VX9Ft8yDOSK/Ja5Yt5akfxcR+yq2JfvxystMI=:59FF
            ^FO24,294^GFA,181,320,16,:Z64:eJxd0MENAyEMBMA98eBJB6ERdLSVJ6W5lJTgAk5sHOyLQviNhNZe9wtkEhwTlS+gT3fmcNNdKOGxbFhuZSjMPekD9lp2n8fuBnEXLD+B5U/+dFeKz1+u6ua/x+aWxfNqzEsS83aft+P/vW+nWB9amP70o5bo5/2p33tMN+Jeb0Wxfj0=:7C9F
            ^FO24,368^GFA,285,708,12,:Z64:eJzN0TEOwyAMBVBHDB65QXOQknItpKYVVYZey1IugtQLIHVhiEIdINAOHbrV0xuw+QaAWgZ+80fpBXqLkfrojF6hJ4wuOSb7bKvZYbOSdnBoA080CpNN8aVaWuPLGe5lR58NoXoFb/iu5JBsUy90MeCddi84ueZbsXAKb76YDnue7JwBcPNYbCXa0+Zv7/APpQSJUHwSJNdiLfh7mvlJiye6Sqo2YvdMQbjsYSbf7X40q+cXn998fLNuM1VPI1J1zaBky8aumRW2Xdh1xxfYbZkx:E32B
            ^FO24,248^GFA,249,416,16,:Z64:eJyVzrENwjAQBdCzrnDpBZC9BZVJhmEIgoiCswizXBZBlrKAO1LF3MWWAg0Sv3vS19cHACT4yr/+mTasSJ2e8goDuFxtRvadHYqdqqZ2FDfizI6n6cnuQQd4BYvVS7Uqvia22n2L4pm47+cH0j0V8/5u/LDs4RT5jz9bpKGvXsFf2L1n6xytK+6azcmaUGyrdfBHsWObwCbfiI0YOvmzmdubVfSHzaSDE6diZFvwFpY34SCA3Q==:0646
            ^FO24,328^GFA,173,312,12,:Z64:eJyNzrERwyAMBVA4FyrZAC8S22tRJBf5UngtRtEIlBS5KAh0hnPlX71C0pcxLc703PE1b8YZgaOz5MURmAYn9VacxZbMQoCjg/o1OKQ+Uyx3+FecB6dQu05js+UMR2y7lr/woe5dPdED9qSO/uyq1h9A/FSjA1zFf7oQZfI=:4E45
            ^FO190,22^GFA,533,1040,52,:Z64:eJyN00FKAzEUBuAXsshK3tZFnblFEUwnh+kF3HWghaZ04S30Ii4iXfQWEujCpRE3Aw4TX9KMTayoDBMSki9M8v5RegAFCMz36J3SA/c9hLcHyU1be9uiVRoq5rgD39EUqmD0D2aApjDc8g58/4dRhREmmCGazQDrk9mMhuVmTQa1IOODmT09w9IgALTU0Igb6tMer6C2pgV68HZBpgbxCK6mqcy4300TDY7mIxhmC8PJ7HKzAszNW1jOTWn2elaYDrBK3yYP90cjNHpLI+670RySuX7RUPfB+CEZFg2WRuy1fC9NnRsbjk/9wmxNaQa6bqppNPPqaKpo5lVmlslc7sk8ROOiWdCqYCSEhkbHO0Bv5E0yV8EgKA+u+zIdLW+/GytVZigHymu3Kow7N3VuRDQymimlj2LDbDTT0dTsZC7uYkZXQrsmmoZ2kOh3MaM0ChmlCaqfxGQwGAosN6mm/zXMBhOzIyd0upOZjKYhI5IRIv6nXTA6GbqUMyOhLQ04R4UUlEr8BKeBZ6Y=:6A1B
            ^FO655,144^GFA,353,944,16,:Z64:eJzd0DFSxSAQBuCfodiSG8BFeMm1UqghJ/BKOO8AXoFXWb51LKTIBCExBjJjYetP9TW7/Ats0WjzV/8WKwMFEaApRZMCLHni2sq1NlCNO6iheH153sPJEab2haFt5T4eNskXd41nWF27a91pjEu9z2BMtdXZLqra5JimFLd5uY/0J99ai1uQL4f/X4jBCsZpDKvNjJjtDeLqfsFcrCZePabi3tMUVs/GLQqXQNfNTJvl1RcKJp8UHoN4c6uD9J8KA4t0+DkbCbs/XhEZT7V5qPx+L7Y/5rtIcXfex0mk+du5jOOxcv4vjzLY3bkP99Lr3blv43wPNnS43MuQU5u/AMFZvZ8=:5B90
            ^FO16,56^GB767,408,2^FS
            ^FO639,136^GB144,328,2^FS
            ^FPH,3^FT152,93^A@N,28,27,TT0003M_^FH\^CI28^FD{data.item_name}^FS^CI27
            ^FPH,3^FT0,317^A@N,28,27,TT0003M_^FB593,1,15,R^FH\^CI28^FD{data.supplier_delivery_note}^FS^CI27
            ^FPH,6^FT152,277^A@N,28,27,TT0003M_^FH\^CI28^FD{data.qty}^FS^CI27
            ^FPH,3^FT152,357^A@N,28,27,TT0003M_^FH\^CI28^FD{data.gr_posting_date}^FS^CI27
            ^FPH,3^FT0,277^A@N,28,27,TT0003M_^FB632,1,15,R^FH\^CI28^FD{data.uom}^FS^CI27
            ^BY2,3,80^FT152,459^BCN,,Y,Y
            ^FH\^FD>:{data.sut_barcode}^FS
            ^BY2,3,96^FT152,232^BCN,,Y,N
            ^FH\^FD>:{data.item_code}^FS
            ^PQ1,0,1,Y
            ^XZ
        """


def zebra_formatter_2(doctype_name, data):
    doc = frappe.get_doc("KTA Zebra Templates", doctype_name)
    return doc.get("zebra_template").format(data=data)
