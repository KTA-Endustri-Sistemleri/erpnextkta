import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


class KTAPurchaseReceipt(PurchaseReceipt):
    def on_submit(self):
        if self.docstatus == 1 and self.is_return == 0:
            errors = []  # List to collect error messages
            for row in self.get("items"):
                split_qty = row.get("custom_split_qty")
                if not split_qty or split_qty <= 0:
                    errors.append(
                        f"Row {row.idx}: custom_split_qty must be a positive number. Please set a valid value for custom_split_qty.")

            # If there are errors, throw them as a single message
            if errors:
                frappe.throw("\n".join(errors))  # Combine errors with newline characters

            # Proceed with posting and batch splitting if no errors
            super().on_submit()
            self.split_kta_batches(table_name="items")
        else:
            super().on_submit()

    def split_kta_batches(self, table_name=None):
        from erpnext.stock.doctype.batch.batch import split_batch

        for row in self.get(table_name):
            row_batch_number = frappe.db.get_value("Serial and Batch Entry",
                                                   {"parent": row.serial_and_batch_bundle},
                                                   "batch_no")
            split_qty = row.get("custom_split_qty")
            if split_qty < row.get("stock_qty"):
                total_qty = row.qty
                num_splits = total_qty // split_qty
                remainder_qty = total_qty % split_qty

                if remainder_qty > 0:
                    split_batch(
                        batch_no=row_batch_number,
                        item_code=row.item_code,
                        warehouse=row.warehouse,
                        qty=remainder_qty
                    )

                for _ in range(num_splits):
                    split_batch(
                        batch_no=row_batch_number,
                        item_code=row.item_code,
                        warehouse=row.warehouse,
                        qty=split_qty
                    )
            else:
                frappe.msgprint(
                    f"Row {row.idx}: split_qty is greater than or equal to the total quantity. No splitting required.")
