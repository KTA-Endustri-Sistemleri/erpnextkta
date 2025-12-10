# erpnextkta/overrides/stock_reconciliation.py

import frappe
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
    StockReconciliation as CoreStockReconciliation,
)


class StockReconciliation(CoreStockReconciliation):
    """
    Custom override for Stock Reconciliation.

    We only change the behavior of `remove_items_with_no_change` so that:
    - While the document is Draft (docstatus == 0), no items are filtered out.
    - On Submit / Cancel, we still keep the core behavior.
    """

    def remove_items_with_no_change(self):
        # Keep all items while the document is Draft so that count sheets stay stable
        if self.docstatus == 0:
            return

        # For submitted / cancelled docs, run the original logic
        super().remove_items_with_no_change()