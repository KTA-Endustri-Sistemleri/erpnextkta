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
            ^POI
            ~TA000
            ~JSN
            ^LT0
            ^MNW
            ^MTD
            ^PON
            ^PMN
            ^LH0,0
            ^JMA
            ^PR4,4
            ~SD15
            ^JUS
            ^LRN
            ^CI27
            ^PA0,1,1,0
            ^XZ
            ^XA
            ^MMT
            ^PW812
            ^LL448
            ^LS0
            ^FO9,29^GB409,747,1^FS
            ^FO9,512^GB407,0,1^FS
            ^FO94,33^GB0,743,1^FS
            ^FO163,190^GB0,582,1^FS
            ^FO205,188^GB0,588,1^FS
            ^FO250,190^GB0,586,1^FS
            ^FO302,190^GB0,586,1^FS
            ^FO360,190^GB0,586,1^FS
            ^FO360,33^GB0,158,1^FS
            ^FO113,518^GFA,477,1512,6,:Z64:eJzVlDtuw0AMRCmo2FJHUI6QAwSQj5KbSIAvtkaKlGlTbudW5RaCmeFwZSn+wDaSFFnYr9jPkBzS7lSjSKeayQOpw4qxEKtLxpZszuj7uLN+daJ2WMWi5N2rgYCI6ihSq04igWoNlBGa+s5uFIvrH2xe5EmG1/lQhnIrw6LMDPtoXvWD+dbTw2/0fd4pFfGt67im63ssj1tyuLKe8N3IM55EecFdaIq7VJl+CsytNU6zA3O/EDcxoljEyStlv9mXxk5xPMrfePvDxVgNybhWo1TMoTVWR2/jMp/k3jgFYyQ1rE4LjxW5jrXHovRk7ZW2ccnk9nq1i3WqoB/GCl1ux1qdmKJsml0O+jH0CX2INi0g+2DMM7Gfk83PZ2KGifPjfHh+bG0MmB/khIqCDsik0Te6t7/QZfjzTpe2/J/ZIiA4kXnhr8zMv+syfzqhGJ+ZMZ0pPCzckcMZ7/btC1OWGlE=:7B5F
            ^FO171,585^GFA,253,740,4,:Z64:eJzNks0NwyAMhV/EgUuljOBRskrH6A026SoeIEtkA44cUNwHNFIqpal6qQr6hGTjH54RM8gBpysoBkvwVjDa2mhxGiBR8LK/yu+IEPo9mYx1tpjcSQTPc7PR76zfb3E1vuVx5+/4uH7Uj17hNMMr9VTquVDPpel5o4KZFDJT25m2mXpXLlV/x3p1FgjxIPFAPFwS+BIwlv0MCmRKEFESCTp/OK8h89oK/rPaXyV27mTc8ab3B76pzt0=:5CEA
            ^FO213,597^GFA,185,519,3,:Z64:eJytkcENgCAMRWs4cOwIHYXRYANGcBTZwCFcwMQLB0It6kGNojH+vAMNP/wPgA0Nj4qj5oScBQqWnCGgDVkHu26JR5ziBxPgRsS8B3QGTGBGKEFunc6eryr1Kjqm1IJ8VD5qn7DPVGDyHWFbqD2Cuy51xcsyP90oqiHhtPzm5nw4ZwaeBJwK:AD78
            ^FO258,593^GFA,225,531,3,:Z64:eJylkbENAyEMRX2ioGQEbxJWySYwmlc5ZQGkNBQIxwak3AGp8vWFMDyMMRDo4GQ4Wy6OqxgpYPQIOCxzCn1LGCGFB0/wQ8h8NdgKroBPoBfFHs3Mf5qyacIHXL0BtqKnoWypOKrurHiytuLbB9z0IcS5mNXL7Stzl2lr0joGz8c4ldUpI7Sxh8yGlVFSeD1llldl8yru3X52pMKblvI+7LSx7A==:C425
            ^FO306,605^GFA,325,990,6,:Z64:eJytkzEOwjAMRR0xZOwRyhEYmQg3ayUGrpWt10BiYM3YIcLY34GoQ2kryPAUpfG38/VLJOuscJFcpiaS5z5EajhypJbv4EMYmAtJmYUDJ+FFjoVPUmZwrPxUrePywh0PdsodqoLSQaFVOqg1NifzWHlVZq+Mvu55GKc3rdZ0TFNa1V6lr81Q5qH5+UO/kRt926o/t/akeTggD0e86ySvF328NESnvW5emVpl7rgveRCTEnwzq0jdG+FRRmNNiHzW/h6Z+Xs2pgtV3Vf+rr/EZDeN5Y8wf9QUyxUZfd3jfPdOb6y10Ekru78AnpNp/g==:AED9
            ^FO362,643^GFA,217,774,6,:Z64:eJytkTEOwyAMRY06MHKEHMW9WSIx9FrecpAOXTsyoPxgEwllaBVXZXhiwO9/GWIAQtdJsRBdotvsPDY1f+VP/rsiCIVKSShiYaEEaYYJT+PrZLYmtXHFuzFrFOdNG+ZqLIN/34m9icZZebMpVgYzTMpgttR7AmXwoaz6YSxx3LGW88s+2z3d2aJG1pHbOxx96HN/Xpx07s3p3wFfZhrk:F409
            ^FO32,53^GFA,393,2260,5,:Z64:eJzVlU1ugzAQhWfEgqWP4N6Eq+QksXe9Fl31GHVvwK5EtTydZ0OlJoqbEgSpJT5ZMPPmx2PBIhL4Gqi6eKyiqlz3vbaeYBDIBhPIjV0giZrkD2XP0UVV0Y8KD9CE5aUe9DEwgZ1RMDzs5NsrIk14UUTG7v37XcHkUXyzStEryjnGZYtRNPdatJbdomtd4ESI2wJvc9GIQQ5yVjxRix3LoO4u3lP5mquShs9fMxJRk7NqZzTFLs0mviK1Qi4POPcrJX6rFNreY5Ioj48ewICB9USdng7JuPQADrTXPdrzyBYulceNP/4BG8zGtnd1hx6UkAkQD/TAAEQgKT7lOfBJXjWk+1BYTIkBmjwvGQ6wCGl+j2vCDfiPf7Dz7m4wV18GtT2K:FC8D
            ^FO90,47^GFA,209,696,6,:Z64:eJylkdEJwzAMROXqo58ZwaNktASyWKCLdIR8Gmqi6C7BpaXEDhX4IWPrTrJFF4mj6JKv0cxqPA/3rbPBpUWn0gl0wus3m2Yp0Y8X+P8blgi8GcHAqggGKvRmnDG9OYFJmT/S5+l+H5uic2ju+ofXV9x8ec9e55ylcz5lcCbUar5zoriyKfzJYDO8VhR3GVTmtGp4mQ3qDs6e:DFC6
            ^FO138,63^GFA,217,450,5,:Z64:eJx9kDEOwzAIRXEYOvYIPkqOVqRerFIvlJHBCv0f2jSV0jA82QaejSdBqBELMYhIPERaOJa3CJMroRtyy0SWZHG1jU1F6ST/o7GgG28BOtAonSN4hX9wB1y5evoukXX1luwtS/rKfBxoCDsCLZx10IT3XzjS79FJ72lo2Rf+JFwRKyeNgq4Ci8ts+LW+R54x+y3OXkzubx/NL6nTnEk=:6380
            ^FO371,121^GFA,137,244,4,:Z64:eJxj/v//ATMIf2BgYPzfwMDA/4+BgcH+AZB4AKbZ/4HFQfLMULUMuEECNkyEPgaGAnsGhg/1DYwHHh5gZjyQAMbMDWDM2M7wgPE/4wGGGn6gA/kwtDJjwzB/YZEDABYgMNM=:290D
            ^FO360,372^GB55,0,1^FS
            ^FO376,200^GFA,289,498,3,:Z64:eJy1UDuuAyEMHB5Stnuk3CJaXyTi3WyXLmVukFwlRyE3IB0FgjfeaPNvY40QtmewGWlVFsAUdBku4i9gumfyyHmPKZgWu5YJ14o7FQmjwN8RRhbZIsG2TDIlN/Ua6IEBkAA5QRIc57ZqOGvSk3dWWNduUGY/q57CRrPL3b444ljlMMrgFdsZZXSluly6VGzMQFxkK8DDVDidZfWDSXFOYpJc0jW18ybKIZN8Vd2W/+nxu4EfUMVW2fMFmkA3gr3SJ9DMRwO/4eES/iNepv8Dr3atUw==:5A94
            ^FO95,189^GB323,0,1^FS
            ^FO181,29^GB0,161,1^FS
            ^BY2,3,39^FT140,450^BCB,,Y,N,,A
            ^FD{data.item_code}^FS
            ^FPH,3^FT190,504^A@B,22,22,TT0003M_^FH\^CI28^FD{data.item_name}^FS^CI27
            ^FPH,3^FT234,507^A@B,22,22,TT0003M_^FH\^CI28^FD{data.supplier_delivery_note}^FS^CI27
            ^FPH,6^FT352,507^A@B,32,31,TT0003M_^FH\^CI28^FD{data.qty}^FS^CI27
            ^FPH,3^FT399,507^A@B,22,22,TT0003M_^FH\^CI28^FD{data.gr_posting_date}^FS^CI27
            ^FPH,3^FT342,341^A@B,22,22,TT0003M_^FH\^CI28^FD{data.uom}^FS^CI27
            ^BY2,3,26^FT279,454^BCB,,Y,N,,A
            ^FD{data.sut}^FS
            ^PQ1,,,Y
            ^XZ
        """

    def print_zebra(self):
        printer = frappe.db.get_value(
            "KTA User Zebra Printers",
            {"disabled": 0},
            ["item_code", "qty", "uom", "sut", "item_name", "supplier_delivery_note", "gr_posting_date"],
            as_dict=True
        )

        data = frappe.db.get_value(
            "KTA Depo Etiketleri",
            {"gr_number": self.name},
            ["item_code", "qty", "uom", "sut", "item_name", "supplier_delivery_note", "gr_posting_date"],
            as_dict=True
        )
        # "10.41.10.23", 9100
        formatted_data = self.zebra_formatter(data)
        self.send_data_to_zebra(formatted_data, "10.41.10.23", 9100)

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

                # Use range(num_splits) to run the loop exactly num_splits times
                for pack in range(1, num_packs):
                    self.custom_create_packages(row, row_batch_number, split_qty, pack)

                if remainder_qty > 0:
                    self.custom_create_packages(row, row_batch_number, remainder_qty, num_packs+1)


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
                # self.print_zebra()
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}")
