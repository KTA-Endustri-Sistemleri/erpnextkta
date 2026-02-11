# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA"

def is_system_manager() -> bool:
    """Return True if current user has System Manager role."""
    return "System Manager" in (frappe.get_roles(frappe.session.user) or [])

def is_quality_user() -> bool:
    """Return True if current user has KTA Kalite Kullanıcısı role."""
    return "KTA Kalite Kullanıcısı" in (frappe.get_roles(frappe.session.user) or [])

def get_my_employee_or_none() -> str | None:
    """Resolve current user's Employee.name robustly.

    Common mappings:
    - Employee.user_id == frappe.session.user
    - Employee.company_email / personal_email == frappe.session.user
    """
    user = frappe.session.user

    # Check available columns first (schema-safe)
    try:
        cols = frappe.db.get_table_columns("Employee") or []
    except Exception:
        cols = []

    checks: list[tuple[str, str]] = []
    if "user_id" in cols:
        checks.append(("user_id", user))
    if "company_email" in cols:
        checks.append(("company_email", user))
    if "personal_email" in cols:
        checks.append(("personal_email", user))

    for field, value in checks:
        emp = frappe.db.get_value("Employee", {field: value}, "name")
        if emp:
            return emp

    return None

def require_my_employee() -> str:
    emp = get_my_employee_or_none()
    if not emp:
        frappe.throw(
            _(
                "Employee eşleşmesi bulunamadı. Lütfen Employee kayıtlarında user_id / company_email / personal_email alanlarını kontrol edin. User: {0}"
            ).format(frappe.session.user)
        )
    return emp

def first_child_table(doc, candidates: list[str]) -> list[dict]:
    """Return first existing child table from candidate fieldnames."""
    for fn in candidates:
        rows = doc.get(fn)
        if rows:
            return [r.as_dict() for r in rows]
    return []

def get_child_table_fieldname(parent_doc, child_doctype: str) -> str:
    """Find the parent Table fieldname that points to the given child doctype."""
    meta = frappe.get_meta(parent_doc.doctype)
    for df in meta.fields:
        if df.fieldtype == "Table" and df.options == child_doctype:
            return df.fieldname
    frappe.throw(_("Parent doctype içinde '{0}' child table alanı bulunamadı.").format(child_doctype))
