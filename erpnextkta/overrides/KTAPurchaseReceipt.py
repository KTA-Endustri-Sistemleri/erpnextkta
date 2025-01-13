import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


class KTAPurchaseReceipt(PurchaseReceipt):
    def on_submit(self):
        if self.docstatus == 1 and self.is_return == 0:
            errors = []  # List to collect error messages

            for row in self.get("items"):
                item_has_batch_no = frappe.db.get_value("Item", {"name": row.item_code}, "has_batch_no")
                if item_has_batch_no == 1:
                    split_qty = row.custom_split_qty
                    if not split_qty or split_qty <= 0:
                        errors.append(
                            f"Row {row.idx}: custom_split_qty must be a positive number. Please set a valid value for custom_split_qty."
                        )
                    elif split_qty >= row.stock_qty:
                        errors.append(
                            f"Row {row.idx}: split_qty is greater than or equal to the total quantity. No splitting required."
                        )

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
                    split_batch(
                        batch_no=row_batch_number,
                        item_code=row.item_code,
                        warehouse=row.warehouse,
                        qty=remainder_qty
                    )

                # Use range(num_splits) to run the loop exactly num_splits times
                for _ in range(num_splits):
                    split_batch(
                        batch_no=row_batch_number,
                        item_code=row.item_code,
                        warehouse=row.warehouse,
                        qty=split_qty
                    )
