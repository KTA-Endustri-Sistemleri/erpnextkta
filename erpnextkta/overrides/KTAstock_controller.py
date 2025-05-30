import frappe
from erpnext.controllers.stock_controller import StockController


class KTAStockController(StockController):
    """
    Custom overriding class for handling stock control in KTA module.
    This class extends the base StockController class and provides specific KTA functions
    for stock operations.
    """

    def validate_inspection(self):
        """Checks if quality inspection is set/ is valid for Items that require inspection."""
        inspection_state_map = {
            "Purchase Receipt": "Etiketleme"
        }
        inspection_required_state = inspection_state_map.get(self.doctype)

        # return if inspection is not required in state
        if (self.workflow_state == inspection_required_state and
                frappe.db.get_single_value(
                    "Stock Settings", "allow_to_make_quality_inspection_after_purchase_or_delivery"
                )):
            return
        else:
            super.validate_inspection()
