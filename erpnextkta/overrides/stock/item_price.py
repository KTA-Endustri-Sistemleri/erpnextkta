import frappe
from erpnext.stock.doctype.item_price.item_price import ItemPrice

class KTAItemPrice(ItemPrice):
    def before_save(self):
        # Call the standard ERPNext logic first
        super(KTAItemPrice, self).before_save()
        
        # Override standard logic to set reference to custom_eski_kod
        # ONLY if it's a selling price list (selling == 1)
        if self.selling and self.customer:
            eski_kod = frappe.db.get_value("Customer", self.customer, "custom_eski_kod")
            if eski_kod:
                self.reference = eski_kod
