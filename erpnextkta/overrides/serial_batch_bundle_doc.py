import frappe
from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import (
    SerialandBatchBundle as ERPNextSerialandBatchBundle,
)


class SerialandBatchBundle(ERPNextSerialandBatchBundle):
    """
    Override Serial & Batch Bundle naming so Purchase Receipt bundles reuse the
    SUT prefix (first 7 alphanumeric chars of the base batch). All other flows
    defer to ERPNext's default autoname logic.
    """

    def autoname(self):
        preferred = self._kta_get_preferred_name()
        if preferred:
            self.name = preferred
            return

        super().autoname()

    def _kta_get_preferred_name(self):
        if self.voucher_type != "Purchase Receipt" or not self.voucher_detail_no:
            return None

        batch_no = frappe.db.get_value("Purchase Receipt Item", self.voucher_detail_no, "batch_no")
        if not batch_no:
            return None

        filtered = "".join(filter(str.isalnum, batch_no.upper()))
        if len(filtered) < 7:
            return None

        candidate = filtered[:7]

        if frappe.db.exists("Serial and Batch Bundle", candidate):
            return None

        return candidate
