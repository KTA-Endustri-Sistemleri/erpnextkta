import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.stock.doctype.batch.batch import split_batch
import socket


class KTAPurchaseReceipt(PurchaseReceipt):

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
            ^MTD
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
            ^FO286,25^GB0,407,1^FS
            ^FO23,110^GB743,0,1^FS
            ^FO27,179^GB582,0,1^FS
            ^FO23,221^GB588,0,1^FS
            ^FO23,266^GB586,0,1^FS
            ^FO23,318^GB586,0,1^FS
            ^FO23,376^GB586,0,1^FS
            ^FO608,376^GB158,0,1^FS
            ^FO27,130^GFA,533,1344,32,:Z64:eJy11DtywyAQBuBVKCh1g+goOhqacZHSV2Imha9BJkXKkA5PMJt/FyRLflZRYaH9YEGCNdFy5XOTytwYmYi94UwGLReI+jBGw5PhQK7LI0/EwXChnj25KO6ClSGpulfntfteQrl6qD4NklCd/cBRUm585Fj9Q9pJUlbvpDN7ccx55bG52zf/BByypBTfq6fRO5uaY+JdNsmpv8XuFz6on8S/dGEYsnhSN4FOWTxv3VQvhjr174TPW3TI2UePT16dL/0oL6Oe1ePa93B9GfVy5Xi5n8VTucrPwarLlpv7Xh54LLKZ6k48b9w/8clyMUdEXkiWAS9rl4OFB6zPeKteNj5Vd4jE5nzprJtpExyP2bX9uePJrfevOR5snH1q52PcIU6DupyvXj2ibz1f46E5+sn5hHupH9/OJ27iHnnww6EPg/gwO8pg8TCcPbT62Djqa/FWX7jBMd176hGbMDDA+7k+146ENPtc37jRw/+Hsgp1a79xdeWx0+v/un0yv32yfhtvRf8AzO4Xvw==:CA55
            ^FO27,190^GFA,321,648,24,:Z64:eJyV0UFuwyAQBdAfecEm0hyBo/hKPQHmZC1HIcoFnJ2lIKafwS6xmi7K6vNkf+NhrnAFS8W0tQAsyWl0eVZzhdThuXk0j16Hr+bSPPUA6OGJDXS+wkDPTje6T/KJIGmxADyzuzeX3evwWzH3Xwg+lSsYcHmyvFgPt+znN0+uyft2zuae/jg8zj52Z8D02F694pdj9+vZ7WfDgiJsS3BausN8jjzq4bfh/uSbuWo2jAwQrX0+3aXN88dXc7YFyZw/AySF3S/FrcFlqS2Ahf2+dl+nbTjvF8d6iafFZ9+vj/+5/NEj6bT9Bjhv8OY=:BC39
            ^FO27,232^GFA,249,462,22,:Z64:eJxt0cENwyAMBVAjDhwZIWv05s0C3YxuQjZwbqmU4rp2nTRST0gPCX3+xwHIbQaYCJjlCARYkatp2UzvctsP5d30QYFJSDXwcI28uUbXhRLvmBsCiG4FdjBdT6Wb6UqpD9fUwfRJuc2aoZrK04eC6cKmr7/Kpu2q5a+iauqWQVQzXDQSmk6UJa+r/y3r3z61tTKilKA9ZO3hq8E1nZ2VcfSbrN9q6ltE3UJ3E536z25vbabVlg==:A092
            ^FO27,277^GFA,265,504,24,:Z64:eJxt0csNwyAMBmBHHHKJxAgehc0CG3SErsImYQSqHppDZNeOoU2i3MwnXv4dCBxB5OJWmH2GoSJICYGTuSfzFUHKvyObbwhSiudxd9nQXcrdWT02J5RVhuDzuMitEDH/HA9OzRnlnaLulyS+Tfv5gZ+wjUXfaA4XB/84+dIdH/no3Dyf/XP1yfp9Nx+l06Lu063P7f8vBvI3Xtn61WSq5tDyUeeD9zxr7HnOTr3nL275J3KreJ9XDTYvAvPLfL82qthY:EBB9
            ^FO27,323^GFA,321,984,24,:Z64:eJzN0kFuAyEMBVCjWbDkCNykXKwVk5N15iZEuQBdhajILvaE4ETTSNnFrHiWLPMFAIDJsFvv5q9UyL5YPuiJEtBsiLS7OnxR7gu7ocVwW3kezuuFEsTDPx4T+8QtKtqXfW9L+ATs6JRfaBY/N7fiNW4O7Pacu39+sf/ivpNyp72Ku1Pu+z946f5xeerbfHcsPbc792vtOV+dlMMz9z/i35KDp2owzsqDeCA0GJbhfOnutXvlaXjl4QkiUff2FPknw13WnvfdDt/y717YCeLh6nYVncQRwgGnO6/D66Ob5isa7Y1u3jKHPx84Z84=:1DCA
            ^FO27,379^GFA,209,820,20,:Z64:eJzF0LENwyAUBNCPXLj8IzAKo8FmZhRG+FEaCsSFWMgBG9l0ufIVp9MRHWFHl/zLbgOA1kSMSMYbb11ruTfOxTAy92gaX/O3RqDdxJ5sK2Z6M5ubt72vLKpmtav7WvNzxr5+8LPMoX51svhsQOB3onazAoRf+WoyMnS2AHFs1s1Z/98al3QxUcX0yEJrLCqz8MjksA+mShZs:443B
            ^FO292,55^GFA,525,1596,57,:Z64:eJyd1T1SxCAUwPGXSUGZI7yLOHIsmwhYeQxvouxs4TXiWKRTuo0jw5NHPnYh0ahd8h9++SAwkUcP6KoBGnJInTz6igKApk54aIVFQ2R97aWFapActQdO8ieoSmgZ0t+hHqHZhbqEJody2IJNWEECjmT34f0vIIgODTCMx8BXmmDtYIIfgaNCy0n2Hq4TbBLsz/AR9PMMg57gI6hmgSoNRptDfCrhp+f4HzhcwOu+naA0SDaeVuQX2M/w7SZCGiGeYZsgFPBhBV2KtMA2QV1CBH1a3RF5AczQK4ahgBLNGnKcIOWQLuEtzfD9xNCPEDJY+d/CsEAKDOMLGGA4fQ5Jpl1DWmCcUqI4rh6hWmCcvTPse4ZpoSqdQ+E2oM6hSlAWsNuHeoQmg80+DDJBnGFNdEcD2gISda3MoJcc5yW3wLSR0wOEb6HJocMt6EXXYgYHNDHOu+Mqh1fb8PU5QZtgtw+bH6FweFjDygtXwuYQoxJn2GzC2qVfwCV8iVEJx+kLCbb6KQ==:56D5
            ^FO634,113^GFA,193,544,16,:Z64:eJytz7ENwjAQheEXXXGlN8CjeDGUZAM2YBKEzCR4BJdXWD4IEOnORSr+7queHvCNMlz/9l4iIcEMLqoPbUhcBxfvMDhmbs6rd9pNdZL3XgLfrGcE545wt27GKh9fB5+sO2I8sg5+Iqrdu6xJ1wOH7M2bl268aP55+09l9Jmdq/dUGxdrETJ+ARtzvs8=:19B1
            ^FO645,160^GFA,221,324,12,:Z64:eJxl0MsJwzAMBmAFH3TUBvUm1mIlMXSAbNBJQgl0EUEXMPRiqKkquw5J6e27/Y+hQHDi8pBRUIGrodBKGg9e+VI9+uibsVSzCt83z93MwCj8EFyqJ0xmWsC/YXSJn0K3H1NpfgldDz4B5mYV77vDn11qnsTrbtZottzA3dZn9yzBb9bqSVez7QrUTc1n/DoG7LZ/zAXFPLTfsqv+AE+Rjpk=:1587
            ^FO617,393^GFA,137,168,8,:Z64:eJz7/4GfwYDhgcX/D/YNBgwfKtgYDA5A6IQHUDoBjQaqv3CDjaEASN8A0jZQ2h5K8zdAaGagOSdmsDEwAM05C6ITIPQBHDTIvqMSQHOB+o4DafsG+wMgWp4BRAMAOHI1Qw==:0E99
            ^FO426,376^GB0,55,1^FS
            ^FO431,395^GFA,325,420,21,:Z64:eJxV0TFOxDAQBdCxXKScI/gm64utNl6loMwROAqWKCj3BpAVBeUO2oIprAx/4oCgsvwk23++D0SZ+NxCo1Ry0CgkfCCyypMCxyVNwo0UGEz4QYBYX5Zk1IARm3mJa9gwdxxM+bE66nCro5XV8Qos8TWI4yltyLXxEw1vQXBTaVzNsRzZHBveJB2qzb94QbSOXz9YeC6j0Lrh5Q9m7Xi/7ViBsdHR8XPHj5qsgjpaj+TjPS+OiCTWw0+O4scRXsa8+piTZHs3R4zp6IWcgVdTIAqRvKMe4j/0koueopgAUbIkIL6jNGD2UNt3fANWm8cy:DF27
            ^FO609,111^GB0,323,1^FS
            ^FO609,197^GB161,0,1^FS
            ^BY2,3,39^FT349,156^BCN,,Y,N
            ^FH\^FD>:{data.item_code}^FS
            ^FPH,3^FT295,206^A@N,22,22,TT0003M_^FH\^CI28^FD{data.item_name}^FS^CI27
            ^FPH,3^FT292,250^A@N,22,22,TT0003M_^FH\^CI28^FD{data.supplier_delivery_note}^FS^CI27
            ^FPH,6^FT292,368^A@N,32,31,TT0003M_^FH\^CI28^FD{data.qty}^FS^CI27
            ^FPH,3^FT292,415^A@N,22,22,TT0003M_^FH\^CI28^FD{data.gr_posting_date}^FS^CI27
            ^FPH,3^FT458,358^A@N,22,22,TT0003M_^FH\^CI28^FD{data.uom}^FS^CI27
            ^BY2,3,26^FT345,295^BCN,,Y,N
            ^FH\^FD>:{data.sut}^FS
            ^PQ1,0,1,Y
            ^XZ
        """

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
            frappe.msgprint(f"Printer IP: {ip_address}, Port: {port}")
            # printer will now contain ip_address and port if found, or None if not
            for data in frappe.get_all("KTA Depo Etiketleri", filters={"gr_number": self.name},
                                       fields={"item_code", "qty", "uom", "sut", "item_name", "supplier_delivery_note",
                                               "gr_posting_date"}):
                # "10.41.10.23", 9100
                formatted_data = self.zebra_formatter(data)
                self.send_data_to_zebra(formatted_data, ip_address, port)
        else:
            frappe.msgprint("No default printer found for the current user.")

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
                sut_barcode=f"{batch_no}{pack_no:03d}",
                item_name=row.item_name
            )
        )
        etiket.insert()

        frappe.db.commit()

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

                split_qty = row.custom_split_qty
                num_packs = frappe.cint(row.stock_qty // split_qty)  # Use row.stock_qty directly
                remainder_qty = row.stock_qty % split_qty

                if num_packs >= 1:
                    # Use range to run the loop exactly num_packs times
                    for pack in range(1, num_packs+1):
                        self.custom_create_packages(row, row_batch_number, split_qty, pack)

                if remainder_qty > 0:
                    self.custom_create_packages(row, row_batch_number, remainder_qty, num_packs + 1)

    def verify_batch(self):
        errors = []

        for row in self.get("items"):
            item_has_batch_no = frappe.db.get_value("Item", {"name": row.item_code}, "has_batch_no")
            if item_has_batch_no == 1:
                split_qty = row.custom_split_qty
                if not split_qty or split_qty <= 0:
                    errors.append(
                        f"Row {row.idx}: custom_split_qty must be a positive number. Please set a valid value for custom_split_qty."
                    )

        if errors:
            frappe.throw("\n".join(errors))

    def on_submit(self):
        try:
            if self.docstatus == 1 and self.is_return == 0:
                self.verify_batch()
                super().on_submit()
                self.custom_split_kta_batches(table_name="items")
                self.print_zebra()
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}")
