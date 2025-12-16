import frappe
from frappe.model.docstatus import DocStatus

import erpnextkta.api
from erpnext.controllers.stock_controller import make_quality_inspections
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


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
        if errors:
            frappe.throw("\n".join(errors))

    def validate_items_quality_inspection(self):
        if self.docstatus == DocStatus.cancelled() and self.is_return == 0:
            super().validate_items_quality_inspection()

    def on_submit(self):
        try:
            if self.docstatus == DocStatus.submitted() and self.is_return == 0:
                self.verify_batch()
                self.set_serial_and_batch_bundle()

                qi_items = []
                rows_to_split_now = []

                for item in self.items:
                    doc = frappe.get_doc('Item', item.get("item_code"))
                    self._ensure_base_batch(item, doc)
                    if doc.get("inspection_required_before_purchase"):
                        meta = frappe.get_meta('Item')
                        if meta.has_field('custom_atlama_sayisi'):
                            atlama_sayisi = doc.get("custom_atlama_sayisi")
                            atlama_sirasi = doc.get("custom_atlama_sirasi")
                            if atlama_sayisi > 0:
                                doc.db_set('custom_atlama_sirasi', atlama_sirasi + 1, commit=True)
                                if atlama_sirasi % atlama_sayisi == 0 or atlama_sayisi > atlama_sirasi:
                                    qi_items.append(item)
                                else:
                                    rows_to_split_now.append(item.name)
                            else:
                                doc.db_set('custom_atlama_sirasi', 2, commit=True)
                                qi_items.append(item)
                        else:
                            qi_items.append(item)
                    else:
                        rows_to_split_now.append(item.name)

                self.set_serial_and_batch_bundle()

                if rows_to_split_now:
                    self.flags.kta_rows_to_split = rows_to_split_now
                else:
                    self.flags.kta_rows_to_split = None

                super().on_submit()
                self.print_zebra()
                make_quality_inspections(self.doctype, self.name, qi_items)
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}")
        finally:
            if hasattr(self, "flags"):
                self.flags.kta_rows_to_split = None

    def print_zebra(self):
        erpnextkta.api.print_kta_pr_labels(gr_number=self.name)

    def _ensure_base_batch(self, row, item_doc):
        if not item_doc.get("has_batch_no"):
            return

        needs_batch = row.batch_no

        if not needs_batch:
            batch_doc = frappe.get_doc(
                {
                    "doctype": "Batch",
                    "item": row.item_code,
                    "supplier": self.get("supplier"),
                    "reference_doctype": self.doctype,
                    "reference_name": self.name,
                    "manufacturing_date": row.get("manufacturing_date") or self.posting_date,
                    "expiry_date": row.get("expiry_date"),
                    "stock_uom": row.get("stock_uom"),
                    "description": row.get("description"),
                }
            )
            batch_doc.batch_id = frappe.generate_hash(length=7).upper()
            if not batch_doc.batch_id:
                batch_doc.batch_id = frappe.generate_hash(length=7).upper()

            batch_doc.flags.ignore_permissions = True
            batch_doc.insert()
            needs_batch = batch_doc.name

        updates = {"batch_no": needs_batch, "use_serial_batch_fields": 1}
        row.batch_no = needs_batch
        row.use_serial_batch_fields = 1
        row.db_set(updates, commit=False)

    def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
        if (
            getattr(self.flags, "kta_rows_to_split", None)
            and self.docstatus == DocStatus.submitted()
            and not self.is_return
        ):
            self._run_pending_batch_splits()

        super().update_stock_ledger(
            allow_negative_stock=allow_negative_stock, via_landed_cost_voucher=via_landed_cost_voucher
        )

    def _run_pending_batch_splits(self):
        row_names = getattr(self.flags, "kta_rows_to_split", None)
        if not row_names:
            return

        for row_name in row_names:
            row_doc = frappe.get_doc("Purchase Receipt Item", row_name)
            erpnextkta.api.custom_split_kta_batches(row=row_doc)

        self.flags.kta_rows_to_split = None
