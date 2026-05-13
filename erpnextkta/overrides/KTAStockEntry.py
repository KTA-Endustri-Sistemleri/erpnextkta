import frappe
from frappe.model.docstatus import DocStatus
from erpnextkta.kta_stock.batch_manager import split_manufacturing_batches
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
                split_manufacturing_batches(self)

    def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
        """
        Base StockEntry.update_stock_ledger does not accept via_landed_cost_voucher, swallow it here
        """
        super().update_stock_ledger(allow_negative_stock=allow_negative_stock)