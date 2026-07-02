# English comments as requested

import frappe
from frappe import _

ROLE_REQUIRED = "Stock Reconciliation Manager"


def get_context(context):
    # Server-side access control for the page itself
    user = frappe.session.user
    roles = frappe.get_roles(user) or []
    if not frappe.has_permission("Stock Reconciliation", "read"):
        frappe.throw(_("İzin verilmiyor"), frappe.PermissionError)
