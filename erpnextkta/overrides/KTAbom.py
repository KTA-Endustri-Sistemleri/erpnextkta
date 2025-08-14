import frappe
from erpnext.manufacturing.doctype.bom.bom import BOM


class KTAbom(BOM):

    def manage_default_bom(self):
        super().manage_default_bom()
        if self.is_default == 1:
            frappe.db.set_value("Item", self.item, "custom_musteri_indeksi_no", self.custom_musteri_indeksi_no)
        else:
            frappe.db.set_value("Item", self.item, "custom_musteri_indeksi_no", None)
