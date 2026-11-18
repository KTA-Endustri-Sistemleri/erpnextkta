# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe import _


def get_context(context):
    if not frappe.has_permission("Work Order", "read"):
        frappe.throw(
            _("Bu sayfaya erişim yetkiniz bulunmamaktadır."),
            frappe.PermissionError,
        )
