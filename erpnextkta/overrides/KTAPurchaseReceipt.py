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
                super().on_submit()
                qi_items = []
                for item in self.items:
                    doc = frappe.get_doc('Item', item.get("item_code"))
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
                                    erpnextkta.api.custom_split_kta_batches(row=item)
                            else:
                                doc.db_set('custom_atlama_sirasi', 2, commit=True)
                                qi_items.append(item)
                self.print_zebra()
                make_quality_inspections(self.doctype, self.name, qi_items)
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}")

    def print_zebra(self):
        erpnextkta.api.print_kta_pr_labels(gr_number=self.name)
