# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe import _

class KTACalismaKartiOperasyonlari(Document):
    def validate(self):
        # 1. Müşteri grubu seçildiyse Plant Floor zorunludur
        if self.customer_group and not self.plant_floor:
            frappe.throw(_("Müşteri Grubu seçildiğinde Üretim Sahası (Plant Floor) zorunludur."))

        # 2. Unique kontrolü (Mükerrerlik engellemesi)
        filters = {
            "calisma_karti_op": self.calisma_karti_op,
            "customer_group": self.customer_group or ("is", "not set"),
            "plant_floor": self.plant_floor or ("is", "not set"),
        }

        existing = frappe.db.get_value(self.doctype, filters, "name")
        if existing and existing != self.name:
            frappe.throw(
                _("Bu operasyon kombinasyonu zaten tanımlı: {0} / {1} / {2} (Kayıt: {3})").format(
                    self.calisma_karti_op, 
                    self.customer_group or "Genel (Müşterisiz)", 
                    self.plant_floor or "-", 
                    existing
                ),
                frappe.DuplicateEntryError,
            )
