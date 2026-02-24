# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe import _

class KTACalismaKartiOperasyonlari(Document):
    def validate(self):

        if not (self.calisma_karti_op and self.customer_group and self.plant_floor):
            return

        filters = {
            "calisma_karti_op": self.calisma_karti_op,
            "customer_group": self.customer_group,
            "plant_floor": self.plant_floor,
        }

        existing = frappe.db.exists(self.doctype, filters)
        if existing and existing != self.name:
            frappe.throw(
                _("Bu kombinasyon zaten var: {0} / {1} / {2} (Kayıt: {3})").format(
                    self.calisma_karti_op, self.customer_group, self.plant_floor, existing
                ),
                frappe.DuplicateEntryError,
            )
