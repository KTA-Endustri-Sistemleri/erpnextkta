# erpnextkta/overrides/stock_reconciliation.py

from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
    StockReconciliation as CoreStockReconciliation,
)

class StockReconciliation(CoreStockReconciliation):
    """
    Keep reconciliation rows intact even on submit.
    """

    def remove_items_with_no_change(self):
        # NO-OP: never drop unchanged rows
        return