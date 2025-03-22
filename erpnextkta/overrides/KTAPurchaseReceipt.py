import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.stock.doctype.batch.batch import split_batch
import socket

class KTAPurchaseReceipt(PurchaseReceipt):

    def send_data_to_zebra(self, data, ip, port):
        message = """
            ^XA
            ^FO50,50^A0N,40,40^FD*Batch No: 123456*^FS
            ^XZ
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((ip, port))
                s.sendall(message.encode("utf-8"))
        except Exception as e:
            frappe.log_error(f"ZPL Print Error {str(e)}", "Printer Error")
            return {"status": "error", "message": f"Failed to send label {str(e)}"}


    def zebra_formatter(self, data):
       return """
            ^XA
            ^FO50,50^A0N,40,40^FD*Batch No: 123456*^FS
            ^XZ
        """

    def print_zebra(self):
        data = frappe.db.get_value(
            "KTA Depo Etiketleri",
            {"gr_number": self.name},
            ["item_code", "qty", "uom", "sut", "item_name", "supplier_delivery_note", "gr_posting_date"],
            as_dict=True
        )

        formatted_data = self.zebra_formatter(data)
        self.send_data_to_zebra(formatted_data, "10.41.10.23", 9100)

        self.send_data_to_zebra(formatted_data, "10.41.10.23", 9100)

        self.send_data_to_zebra(formatted_data, "10.41.10.23", 9100)

    def custom_split_batch(self, row, batch_no, qty):
        """Helper function to split a batch."""
        batch = split_batch(
            batch_no=batch_no,
            item_code=row.item_code,
            warehouse=row.warehouse,
            qty=qty
        )

        frappe.get_doc(
            dict(
                doctype="KTA Depo Etiketleri",
                gr_number=row.parent,
                item_code=row.item_code,
                item_code_barcode=row.item_code,
                qty=qty,
                uom=row.stock_uom,
                sut=batch,
                sut_barcode=batch,
                item_name=row.item_name,
                supplier_delivery_note=self.supplier_delivery_note,
                gr_posting_date=self.posting_date
            )
        ).insert()
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
                num_splits = frappe.cint(row.stock_qty // split_qty)  # Use row.stock_qty directly
                remainder_qty = row.stock_qty % split_qty

                if remainder_qty > 0:
                    self.custom_split_batch(row, row_batch_number, remainder_qty)

                # Use range(num_splits) to run the loop exactly num_splits times
                for _ in range(num_splits):
                    self.custom_split_batch(row, row_batch_number, split_qty)

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
        if self.docstatus == 1 and self.is_return == 0:
            self.verify_batch()
            super().on_submit()
            self.custom_split_kta_batches(table_name="items")
            self.print_zebra()
        else:
            super().on_submit()
