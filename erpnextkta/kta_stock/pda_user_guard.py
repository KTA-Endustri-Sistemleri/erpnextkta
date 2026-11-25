import frappe
from frappe.utils import cint


def _get_preserve_flag_set() -> set[str]:
    preserve = getattr(frappe.local.flags, "_kta_preserve_pda_website_users", None)
    if not isinstance(preserve, set):
        preserve = set()
        frappe.local.flags._kta_preserve_pda_website_users = preserve
    return preserve


def _is_pure_pda_website_user(user_id: str) -> bool:
    """Return True if user holds at least one KTA PDA role and no desk_access=1 role."""
    assigned_roles = frappe.get_all(
        "Has Role",
        filters={"parent": user_id, "parenttype": "User"},
        pluck="role",
    )
    if not assigned_roles:
        return False

    role_rows = frappe.get_all(
        "Role",
        filters={"name": ["in", assigned_roles], "disabled": 0},
        fields=["name", "desk_access"],
    )
    has_pda_website_role = False
    for row in role_rows:
        if cint(row.desk_access) == 1:
            return False
        if (row.name or "").startswith("KTA PDA "):
            has_pda_website_role = True

    return has_pda_website_role


def mark_pure_pda_website_user_before_employee_save(doc, method=None) -> None:
    """Mark linked pure PDA Website User before Employee.on_update syncs User."""
    user_id = getattr(doc, "user_id", None)
    if not user_id:
        return

    preserve = _get_preserve_flag_set()
    if _is_pure_pda_website_user(user_id):
        preserve.add(user_id)
    else:
        preserve.discard(user_id)


def strip_auto_employee_role_for_pure_pda_user(doc, method=None) -> None:
    """Remove auto-appended Employee role during Employee-triggered User sync only."""
    preserve = getattr(frappe.local.flags, "_kta_preserve_pda_website_users", None)
    if not isinstance(preserve, set) or doc.name not in preserve:
        return

    preserve.discard(doc.name)
    doc.set(
        "roles",
        [row for row in (doc.get("roles") or []) if row.role != "Employee"],
    )


def clear_pure_pda_website_user_flag_after_employee_save(doc, method=None) -> None:
    """Ensure temporary pure-PDA Website User flag is cleared after Employee save."""
    user_id = getattr(doc, "user_id", None)
    if not user_id:
        return

    preserve = getattr(frappe.local.flags, "_kta_preserve_pda_website_users", None)
    if isinstance(preserve, set):
        preserve.discard(user_id)
