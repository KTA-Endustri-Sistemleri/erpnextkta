import frappe
import erpnextkta.api

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.stock.doctype.batch.batch import split_batch
from frappe.model.docstatus import DocStatus
from erpnext.controllers.stock_controller import make_quality_inspections


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
                make_quality_inspections(self.doctype, self.name, self.items)
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}")

    def print_zebra(self):
        erpnextkta.api.print_to_zebra_kta(gr_number=self.name)
