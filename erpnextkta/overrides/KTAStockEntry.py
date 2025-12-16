import frappe
from frappe.model.docstatus import DocStatus

import erpnextkta.api
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


class KTAStockEntry(StockEntry):

    def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
        if (
            hasattr(self, "purpose")
            and self.purpose == "Manufacture"
            and self.docstatus == DocStatus.submitted()
        ):
            erpnextkta.api.split_manufacturing_batches(self)

        super().update_stock_ledger(
            allow_negative_stock=allow_negative_stock, via_landed_cost_voucher=via_landed_cost_voucher
        )
