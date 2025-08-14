import frappe
from erpnext.manufacturing.doctype.bom.bom import BOM

class KTAbom(BOM):

    def manage_default_bom(self):
        super().manage_default_bom()
        if self.is_default == 1:
<<<<<<< HEAD
            frappe.db.set_value("Item", self.item, "custom_musteri_indeksi_no", self.custom_musteri_indeksi_no)
=======
            frappe.db.set_value("Item", self.item, "custom_musteri_indeksi", self.custom_musteri_indeksi_no)
>>>>>>> 8a9f6af (alpkan gelistirmeler calisma karti + mrp)
        else:
            frappe.db.set_value("Item", self.item, "custom_musteri_indeksi_no", None)
