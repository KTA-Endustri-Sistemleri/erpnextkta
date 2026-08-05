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
        super().on_cancel()
        if self.purpose == "Manufacture":
            batches = frappe.get_all("Batch", filters={
                "stock_entry_reference_doctype": "Stock Entry",
                "stock_entry_reference_name": self.name
            }, pluck="name")
            for batch_name in batches:
                frappe.db.set_value("Batch", batch_name, "batch_qty", 0, update_modified=False)
                # Ensure the batch is marked as disabled to prevent future use if it's considered empty/cancelled.
                frappe.db.set_value("Batch", batch_name, "disabled", 1, update_modified=False)

    def on_trash(self):
        if self.purpose == "Manufacture":
            batches = frappe.get_all("Batch", filters={
                "stock_entry_reference_doctype": "Stock Entry",
                "stock_entry_reference_name": self.name
            }, pluck="name")
            
            for batch_name in batches:
                try:
                    frappe.delete_doc("Batch", batch_name, ignore_permissions=True)
                except Exception:
                    # If deletion fails (e.g., due to LinkExistsError), ensure it's empty
                    frappe.db.set_value("Batch", batch_name, "batch_qty", 0, update_modified=False)
                    frappe.db.set_value("Batch", batch_name, "disabled", 1, update_modified=False)
                    
        super().on_trash()


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