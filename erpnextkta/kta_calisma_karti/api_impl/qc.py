# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

# -----------------------------
# QC Update (Role-gated)
# -----------------------------

QC_ALLOWED_ROLES = {"KTA Kalite Kullanıcısı", "Quality Manager", "System Manager"}
QC_ALLOWED_VALUES = {"Onay Bekliyor", "Onaylandı", "Reddedildi"}

def _has_any_role(roles: set[str]) -> bool:
    """Return True if current user has any of the given roles."""
    user_roles = set(frappe.get_roles(frappe.session.user) or [])
    return bool(user_roles.intersection(roles))

@frappe.whitelist()
def update_kalite_kontrol(name: str, kalite_kontrol: str):
    """Update 'kalite_kontrol' on Calisma Karti.

    Security:
    - Only users with one of QC_ALLOWED_ROLES can update.
    - Uses server-side role check + ignore_permissions to bypass permlevel=1 restriction,
      while still remaining safe due to the strict role gate above.
    """

    if not _has_any_role(QC_ALLOWED_ROLES):
        frappe.throw(_("QC güncelleme yetkiniz yok."), frappe.PermissionError)

    val = (kalite_kontrol or "").strip()
    if val not in QC_ALLOWED_VALUES:
        frappe.throw(_("Geçersiz kalite kontrol durumu."))

    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    # permlevel=1 field -> bypass via ignore_permissions AFTER strict role gate
    doc.flags.ignore_permissions = True
    doc.db_set("kalite_kontrol", val, update_modified=True)

    return {"status": "success", "kalite_kontrol": val}
