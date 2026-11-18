# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, nowtime


class KTAProductionConfirmation(Document):
    def validate(self):
        self.validate_defaults()
        self.validate_yield_qty()

    def validate_defaults(self):
        if not self.posting_date:
            self.posting_date = nowdate()
        if not self.posting_time:
            self.posting_time = nowtime()
        if not self.confirmed_by or self.confirmed_by == "session_user":
            self.confirmed_by = frappe.session.user or "Administrator"

    def validate_yield_qty(self):
        if flt(self.yield_qty) <= 0:
            frappe.throw(
                _("Sağlam Miktar (Yield Qty) sıfırdan büyük olmalıdır."),
                frappe.ValidationError,
            )
