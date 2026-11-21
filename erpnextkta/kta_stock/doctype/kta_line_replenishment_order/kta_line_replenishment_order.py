import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class KTALineReplenishmentOrder(Document):
    def validate(self):
        self._validate_target_warehouse()
        self._calculate_totals()
        self._handle_status_cancellation()

    def _validate_target_warehouse(self):
        if not self.target_warehouse:
            frappe.throw(_("Target Warehouse is mandatory."))

    def _calculate_totals(self):
        total_deficit = 0.0
        total_picked = 0.0
        for item in self.get("items", []):
            total_deficit += flt(item.deficit_qty)
            total_picked += flt(item.picked_qty)
        self.total_deficit_qty = total_deficit
        self.total_picked_qty = total_picked

    def _handle_status_cancellation(self):
        before_save = self.get_doc_before_save()
        if (
            self.status == "Cancelled"
            and before_save
            and before_save.status != "Cancelled"
        ):
            self.on_cancel()

    def on_cancel(self):
        if self.stock_entry:
            se = frappe.get_doc("Stock Entry", self.stock_entry)
            if se.docstatus == 1:
                se.cancel()

    def cancel(self):
        if getattr(self, "docstatus", 0) == 1:
            return super().cancel()
        self.status = "Cancelled"
        self.on_cancel()
        return self.save(ignore_permissions=True)
