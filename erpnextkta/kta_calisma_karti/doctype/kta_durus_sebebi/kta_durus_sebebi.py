# Copyright (c) 2026, KTA and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KTADurusSebebi(Document):
    def on_trash(self):
        """Sistem tarafından kullanılan kayıtların silinmesini engelle."""
        if self.is_system:
            frappe.throw(
                frappe._("Sistem kaydı olan '{0}' silinemez.").format(self.reason),
                title=frappe._("Silme Engeli")
            )
