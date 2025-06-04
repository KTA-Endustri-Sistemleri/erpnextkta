import frappe
import socket

from babel.numbers import format_decimal
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.stock.doctype.batch.batch import split_batch
from frappe.model.docstatus import DocStatus


class KTAPurchaseReceipt(PurchaseReceipt):

    def verify_batch(self):
        errors = []
        for item in self.get("items"):
            if item.custom_do_not_split == 0:
                item_has_batch_no = frappe.db.get_value("Item", {"name": item.item_code},
                                                        "has_batch_no")
                if item_has_batch_no == 1:
                    split_qty = item.custom_split_qty
                    if not split_qty or split_qty <= 0:
                        errors.append(
                            f"Row {item.idx}: custom_split_qty must be a positive number. Please set a valid value for custom_split_qty."
                        )
                    # item.use_serial_batch_fields = 1
                    # batch = frappe.get_doc(dict(doctype="Batch", item=item.item_code)).insert()
                    # item.batch_no = batch

                    # company = frappe.db.get_value("Warehouse", warehouse, "company")
                    #
                    # from_bundle_id = make_batch_bundle(
                    #     item_code=item_code,
                    #     warehouse=warehouse,
                    #     batches=frappe._dict({batch_no: qty}),
                    #     company=company,
                    #     type_of_transaction="Outward",
                    #     qty=qty,
                    # )
                    #
                    # to_bundle_id = make_batch_bundle(
                    #     item_code=item_code,
                    #     warehouse=warehouse,
                    #     batches=frappe._dict({batch.name: qty}),
                    #     company=company,
                    #     type_of_transaction="Inward",
                    #     qty=qty,
                    # )
        if errors:
            frappe.throw("\n".join(errors))

    def custom_split_kta_batches(self, table_name=None):
        for row in self.get(table_name):
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
                        self.custom_create_packages(row, row_batch_number, split_qty, pack)

                if remainder_qty > 0:
                    self.custom_create_packages(row, row_batch_number, remainder_qty, num_packs + 1)

    def custom_split_batch(self, row, batch_no, qty):
        """Helper function to split a batch."""
        batch = split_batch(
            batch_no=batch_no,
            item_code=row.item_code,
            warehouse=row.warehouse,
            qty=qty
        )

        etiket = frappe.get_doc(
            dict(
                doctype="KTA Depo Etiketleri",
                gr_number=row.parent,
                supplier_delivery_note=self.supplier_delivery_note,
                qty=qty,
                uom=row.stock_uom,
                batch=batch_no,
                gr_posting_date=self.posting_date,
                item_code=row.item_code,
                sut_barcode=batch,
                item_name=row.item_name
            )
        )
        etiket.insert()

        frappe.db.commit()

    def custom_create_packages(self, row, batch_no, qty, pack_no):
        etiket = frappe.get_doc(
            dict(
                doctype="KTA Depo Etiketleri",
                gr_number=row.parent,
                supplier_delivery_note=self.supplier_delivery_note,
                qty=qty,
                uom=row.stock_uom,
                batch=batch_no,
                gr_posting_date=self.posting_date,
                item_code=row.item_code,
                sut_barcode=f"{batch_no}{pack_no:04d}",
                item_name=row.item_name
            )
        )
        etiket.insert()

        frappe.db.commit()

    def validate_items_quality_inspection(self):
        if self.docstatus == DocStatus.cancelled() and self.is_return == 0:
            super().validate_items_quality_inspection()

    def on_submit(self):
        try:
            if self.docstatus == DocStatus.submitted() and self.is_return == 0:
                self.verify_batch()
                super().on_submit()
                self.custom_split_kta_batches(table_name="items")
                self.print_zebra()
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}")

    def print_zebra(self):
        # Get the current logged-in user
        user = frappe.session.user

        # Query the printer for this user that is both enabled and marked as default
        printer = frappe.db.get_value(
            "KTA User Zebra Printers",
            {
                "user": user,
                "disabled": 0
                #        "is_default": 1  # Assuming there's a field to mark default printers
            },
            ["printer"]
        )
        if printer:
            zebra_printer = frappe.get_doc("KTA Zebra Printers", {"printer_name": printer})
            ip_address = zebra_printer.ip
            port = zebra_printer.port

            # Example usage:
            # frappe.msgprint(f"Printer IP: {ip_address}, Port: {port}")
            # printer will now contain ip_address and port if found, or None if not
            for data in frappe.get_all("KTA Depo Etiketleri", filters={"gr_number": self.name},
                                       fields={"item_code", "qty", "uom", "sut_barcode", "item_name",
                                               "supplier_delivery_note",
                                               "gr_posting_date"}):
                if data.qty % 1 == 0:
                    data.qty = format_decimal(f"{data.qty:g}", locale='tr_TR')
                else:
                    data.qty = format_decimal(f"{data.qty:.2f}", locale='tr_TR')
                # "10.41.10.23", 9100
                formatted_data = self.zebra_formatter(data)
                self.send_data_to_zebra(formatted_data, ip_address, port)
        else:
            frappe.msgprint("No default printer found for the current user.")


def send_data_to_zebra(self, data, ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))
            s.sendall(data.encode("utf-8"))
    except Exception as e:
        frappe.log_error(f"ZPL Print Error {str(e)}", "Printer Error")
        return {"status": "error", "message": f"Failed to send label {str(e)}"}


def zebra_formatter(self, data):
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
            ^FO23,25^GB747,409,1^FS
            ^FO23,75^GB747,0,1^FS
            ^FO23,152^GB747,0,1^FS
            ^FO23,220^GB624,0,1^FS
            ^FO25,265^GB622,0,1^FS
            ^FO26,343^GB745,0,1^FS
            ^FO23,392^GB747,0,1^FS
            ^FO23,158^GFA,397,848,16,:Z64:eJzN0jFuwyAUBuAfIfWN7wbmIo59lRyDwa2JOnTMlah6j4gjMDJYoY9ASJ2hXcv2Wcj8/4N5g3GUPVaoBGC+wnjKQWWvtuJ8c9TyqdrN4lQ+FY/sDoFc4s+oL8V0s2Wku1+LDY50qfttlP0DQOf6P3GODyM187nmiVbyFJMTp5vd3SOUhPnwA44mN2/0HgySkVbNp8DdOox0ivwVJ13tB8kjR44qdFvp20zFi8xjaXZy8CTzsoh4rAn7RX/45ckL/sUaddAJq0yZq8nzFeu1m53JWHO3KVf4wxPe2Ft2dy+w2lvqTvIwgiXffIiIKsiW5nK/v3p78rT3NOwt+XbnjYyFSp7U+9S829z6utpHKtd5+Nq3O9R5zFu1avPi+hi+Ae+hzhU=:AC7A
            ^FO26,81^GFA,349,600,24,:Z64:eJyV0T1OxDAQBeBnWWJK3yC+SEiussdwsSu82oKSKxlRcAvkG+DSRRTz7DirZYECd/ONNJ6feYH1UgKeoDKABfMCB8wrbJASVQlqoa+YS/PSPGmmdvfN/UzPNUVXu4/GP0bx2bwm/UH/xCihujR3Bnl33f1U3eIgdF09bnVcYp0BkBf6ux9V3P6ll/TTkbsbulx9RXKcq7p4yCV0z839vY9QHOo5DDjY4mHKjS9yiRbZcnumxN5n83M0N97mgo6jnJN5S5MOsCr2PUCHgXOxVRbGgNT3trnjnu9cqh95lyN9qo7NPRufeEeHxNBtd7y+Cb8/+ac//OHH7+EXATequg==:E212
            ^FO27,227^GFA,265,480,24,:Z64:eJxl0T0OwyAMBeCHGNjKDcJFULhSx4xIvRhHyRE8dqhwHdtI/clC+JTA03N7gTkOhInCJzIIE/K0aZ64q3eK3C9n88xDfVDiod7VBd2zLECVPyHeIm2yzSeVB12ezPewfMOnVwx1oh1PPQfqB6B+p3q9a55pXiRIPpZP90Lq9ff7P+9fvrnXNOzeYjlvy+PwnOZ55XTf3ROVQB/nrB6S99B4SG8sl5L2Fr0365OvnfvqGeprLmHNZZrD5xh8jm/UfLDY:A5F1
            ^FO27,268^GFA,305,848,16,:Z64:eJzd0jFuwzAMBVAaHDTqBvZBylrXMtAgcOEh12LgiwjoBQx08RCIoW0pFrN0r7YHCCL/t8MDPDtZIQEhA4QEPqpRxsNy2Alnj91mL3E3+bFdoIVuynaH22Yp7jf3wPk+0KAmgPJ+cZBj/sVYYCDj0Zgcy2N3fh9Z0javzM8+97kv7bbvLeb59+jVJU+Q791nXtz96iMha0Qoff23o6Fwrdwj+1Q5IHdirZ+k8sRXz8ZD3VOYecV4+nPmpan9Y02/f/jrzR9vDnYedXxxbGz2JW/zqE1e/d9MH2rT1xNNaZ0/:AD62
            ^FO27,343^GFA,249,416,16,:Z64:eJyVzrENwjAQBdCzrnDpBZC9BZVJhmEIgoiCswizXBZBlrKAO1LF3MWWAg0Sv3vS19cHACT4yr/+mTasSJ2e8goDuFxtRvadHYqdqqZ2FDfizI6n6cnuQQd4BYvVS7Uqvia22n2L4pm47+cH0j0V8/5u/LDs4RT5jz9bpKGvXsFf2L1n6xytK+6azcmaUGyrdfBHsWObwCbfiI0YOvmzmdubVfSHzaSDE6diZFvwFpY34SCA3Q==:0646
            ^FO27,398^GFA,173,312,12,:Z64:eJyNzrERwyAMBVA4FyrZAC8S22tRJBf5UngtRtEIlBS5KAh0hnPlX71C0pcxLc703PE1b8YZgaOz5MURmAYn9VacxZbMQoCjg/o1OKQ+Uyx3+FecB6dQu05js+UMR2y7lr/woe5dPdED9qSO/uyq1h9A/FSjA1zFf7oQZfI=:4E45
            ^FO206,41^GFA,533,1040,52,:Z64:eJyN00FKAzEUBuAXsshK3tZFnblFEUwnh+kF3HWghaZ04S30Ii4iXfQWEujCpRE3Aw4TX9KMTayoDBMSki9M8v5RegAFCMz36J3SA/c9hLcHyU1be9uiVRoq5rgD39EUqmD0D2aApjDc8g58/4dRhREmmCGazQDrk9mMhuVmTQa1IOODmT09w9IgALTU0Igb6tMer6C2pgV68HZBpgbxCK6mqcy4300TDY7mIxhmC8PJ7HKzAszNW1jOTWn2elaYDrBK3yYP90cjNHpLI+670RySuX7RUPfB+CEZFg2WRuy1fC9NnRsbjk/9wmxNaQa6bqppNPPqaKpo5lVmlslc7sk8ROOiWdCqYCSEhkbHO0Bv5E0yV8EgKA+u+zIdLW+/GytVZigHymu3Kow7N3VuRDQymimlj2LDbDTT0dTsZC7uYkZXQrsmmoZ2kOh3MaM0ChmlCaqfxGQwGAosN6mm/zXMBhOzIyd0upOZjKYhI5IRIv6nXTA6GbqUMyOhLQ04R4UUlEr8BKeBZ6Y=:6A1B
            ^FO650,152^GFA,353,944,16,:Z64:eJzd0DFSxSAQBuCfodiSG8BFeMm1UqghJ/BKOO8AXoFXWb51LKTIBCExBjJjYetP9TW7/Ats0WjzV/8WKwMFEaApRZMCLHni2sq1NlCNO6iheH153sPJEab2haFt5T4eNskXd41nWF27a91pjEu9z2BMtdXZLqra5JimFLd5uY/0J99ai1uQL4f/X4jBCsZpDKvNjJjtDeLqfsFcrCZePabi3tMUVs/GLQqXQNfNTJvl1RcKJp8UHoN4c6uD9J8KA4t0+DkbCbs/XhEZT7V5qPx+L7Y/5rtIcXfex0mk+du5jOOxcv4vjzLY3bkP99Lr3blv43wPNnS43MuQU5u/AMFZvZ8=:5B90
            ^FO679,407^GFA,193,252,12,:Z64:eJxdzzsOAiEYBOAhFHQ/FzDsFSzHSPRKW1Ku97LgKByBksKIkF3Q2H3VPPCGIFAlALpGQaaOzbYmUYlma15UFh1pG+Gwitnoun2zBX03cRYHhu4VEA/m4YBLGi647rbFvnDPw0/cph38kcOffIoBT3sv54bWObctjzI325oFiXr7+4X6/fsB1FYyNw==:EE00
            ^FO466,392^GB0,42,1^FS
            ^FO467,407^GFA,345,480,24,:Z64:eJxd0TFuwzAMQFEKHDTqBtJFBPdaHoJEB8tAw0PGXKBoWeQCAjpUgxCWlOC2KODlPxg2RWWAREgLnMF1x75YZQB9LhXpBBfw4mooWjxdGlJTD1JasqrDnXTcKggkKWu0mo71jDvDV0meTotVm04Rb6Qe9YfZarqnhPfi9H2AuFr16SXgO7gHJYbUrF5/XIp6eEKoVm9/HB/kpXi2uv864cZO6L9/svpYiNXtevgHe2FAnr5fjzm36qVmZ66193EuXpDMF3OrrR97oBZKTfYdK/MXsU3RGmBNOhWNGj72nNWD+ajpdi9LglXPpT5vydzGjhGye+puR6l/A6OJrrA=:AE43
            ^FO647,152^GB0,191,1^FS
            ^FO643,392^GB0,42,1^FS
            ^BY2,3,39^FT200,192^BCN,,Y,N
            ^FH\^FD>:{data.item_code}^FS
            ^FPH,3^FT200,104^A@N,28,27,TT0003M_^FH\^CI28^FD{data.item_name}^FS^CI27
            ^FPH,3^FT202,250^A@N,28,27,TT0003M_^FH\^CI28^FD{data.supplier_delivery_note}^FS^CI27
            ^FPH,6^FT202,383^A@N,38,38,TT0003M_^FH\^CI28^FD{data.qty}^FS^CI27
            ^FPH,3^FT202,420^A@N,28,27,TT0003M_^FH\^CI28^FD{data.gr_posting_date}^FS^CI27
            ^FPH,3^FT542,383^A@N,38,38,TT0003M_^FH\^CI28^FD{data.uom}^FS^CI27
            ^BY2,3,39^FT206,309^BCN,,Y,N
            ^FH\^FD>:{data.sut_barcode}^FS
            ^PQ1,0,1,Y
            ^XZ
        """
