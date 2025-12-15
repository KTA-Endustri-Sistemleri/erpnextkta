# English comments as requested

import frappe
from frappe import _

ROLE_REQUIRED = "Stock Reconciliation Manager"


def get_context(context):
    # Server-side access control for the page itself
    if not frappe.has_role(ROLE_REQUIRED):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    context.title = _("Stock Reconciliation Dashboard")