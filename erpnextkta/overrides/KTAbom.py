import frappe
from frappe import _
from erpnext.manufacturing.doctype.bom.bom import BOM


class KTAbom(BOM):

    def validate(self):
        super().validate()
        self._validate_item_operations()

    def _validate_item_operations(self):
        """Ensure every raw material is assigned to an operation
        when the BOM has operations."""
        if not self.with_operations or not self.operations:
            return

        missing = []
        for d in self.items:
            if not d.operation:
                missing.append(
                    _("Row {0}: {1}").format(d.idx, d.item_code)
                )

        if missing:
            frappe.msgprint(
                _("The following raw materials are not assigned to any operation: {0}").format(
                    "<br>".join(missing)
                ),
                title=_("Missing Operation Assignment"),
                indicator="orange",
            )


    def manage_default_bom(self):
        super().manage_default_bom()
        if self.is_default == 1:
            frappe.db.set_value("Item", self.item, "custom_musteri_indeksi_no", self.custom_musteri_indeksi_no)
        else:
            frappe.db.set_value("Item", self.item, "custom_musteri_indeksi_no", None)
