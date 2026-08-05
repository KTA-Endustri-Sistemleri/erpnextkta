import frappe
from frappe.model.docstatus import DocStatus
from erpnextkta.kta_stock.batch_manager import BatchSplitManager
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


class KTAStockEntry(StockEntry):
    def validate(self):
        # 1. Standart ERPNext kontrollerini yap
        super().validate()
        
        # 2. Sadece Manufacture tipinde ve Draft (0) durumundaysa çalış
        if self.purpose == "Manufacture" and self.work_order and self.docstatus == 0:
            # 3. Sonsuz döngü koruması (Flag)
            if not self.get("__splitting_batches"):
                self.set("__splitting_batches", True)
                BatchSplitManager.split_manufacturing_batches(self)

    def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
        """
        Base StockEntry.update_stock_ledger does not accept via_landed_cost_voucher, swallow it here
        """
        super().update_stock_ledger(allow_negative_stock=allow_negative_stock)

    def on_submit(self):
        super().on_submit()
        frappe.enqueue(
            "erpnextkta.overrides.KTAStockEntry.print_labels_on_submit",
            stock_entry=self.name,
            user=frappe.session.user,
            queue="short",
            timeout=120,
            now=frappe.flags.in_test,
            enqueue_after_commit=True,
        )

    def on_cancel(self):
        batches_to_disable = []
        if self.purpose == "Manufacture":
            batches_to_disable = self._get_generated_batches()
            
        super().on_cancel()
        
        self._delete_associated_labels()
        
        if self.purpose == "Manufacture":
            for batch_name in batches_to_disable:
                frappe.db.set_value("Batch", batch_name, "batch_qty", 0, update_modified=False)
                # Ensure the batch is marked as disabled to prevent future use if it's considered empty/cancelled.
                frappe.db.set_value("Batch", batch_name, "disabled", 1, update_modified=False)

    def on_trash(self):
        batches_to_delete = []
        if self.purpose == "Manufacture":
            batches_to_delete = self._get_generated_batches()
            
        self._delete_associated_labels()
        super().on_trash()
        
        if self.purpose == "Manufacture":
            for batch_name in batches_to_delete:
                try:
                    frappe.delete_doc("Batch", batch_name, ignore_permissions=True)
                except Exception:
                    # If deletion fails (e.g., due to LinkExistsError), ensure it's empty
                    frappe.db.set_value("Batch", batch_name, "batch_qty", 0, update_modified=False)
                    frappe.db.set_value("Batch", batch_name, "disabled", 1, update_modified=False)
                    
    def _delete_associated_labels(self):
        labels = frappe.get_all("KTA Stock Label", filters={
            "reference_doctype": "Stock Entry",
            "reference_name": self.name
        }, pluck="name")
        for label in labels:
            logs = frappe.get_all("KTA Print Log", filters={
                "label_doctype": "KTA Stock Label",
                "label_name": label
            }, pluck="name")
            for log in logs:
                try:
                    frappe.delete_doc("KTA Print Log", log, ignore_permissions=True, force=True)
                except Exception:
                    pass
            try:
                frappe.delete_doc("KTA Stock Label", label, ignore_permissions=True, force=True)
            except Exception:
                pass

    def _get_generated_batches(self):
        batches = set()
        
        # 1. Try to find bundles via voucher_no in DB (works even if doc is cancelled and row links are cleared)
        bundles = frappe.get_all("Serial and Batch Bundle", 
                                 filters={"voucher_type": "Stock Entry", "voucher_no": self.name},
                                 pluck="name")
                                 
        # 2. Fallback to row fields if not found (e.g. before save/submit)
        if not bundles:
            bundles = [row.get("serial_and_batch_bundle") for row in self.get("items", []) 
                      if row.get("is_finished_item") and row.get("serial_and_batch_bundle")]

        for bundle in bundles:
            entries = frappe.get_all("Serial and Batch Entry", 
                                    filters={"parent": bundle, "is_outward": 0},
                                    pluck="batch_no")
            for b in entries:
                if b:
                    batches.add(b)
        return list(batches)

def print_labels_on_submit(stock_entry, user=None):
    if user:
        frappe.set_user(user)

    from erpnextkta.kta_stock.label_manager import print_stock_entry_labels
    try:
        doc = frappe.get_doc("Stock Entry", stock_entry)
        if doc.stock_entry_type:
            is_printable = frappe.db.get_value("Stock Entry Type", doc.stock_entry_type, "custom_etiket_basilabilir")
            if is_printable:
                print_stock_entry_labels(stock_entry)
    except Exception as e:
        import traceback
        frappe.log_error(f"Stock Entry Print Error: {traceback.format_exc()}", "Stock Entry Submit Print Error")