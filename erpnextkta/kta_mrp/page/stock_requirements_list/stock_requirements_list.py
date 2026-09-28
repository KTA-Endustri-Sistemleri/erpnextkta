import frappe
from frappe import _


def get_context(context):
    """Server-side access control for the page."""
    # Şimdilik kısıt yok — tüm desk kullanıcıları erişebilir
    if frappe.session.user == "Guest":
        frappe.throw(_("İzin verilmiyor"), frappe.PermissionError)
