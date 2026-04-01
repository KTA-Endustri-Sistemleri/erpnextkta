import frappe

def boot_session(bootinfo):
    admin_roles = frappe.db.get_single_value("KTA Calisma Karti Settings", "admin_roles") or ""
    if admin_roles:
        bootinfo.kta_admin_roles = [r.strip() for r in admin_roles.split(",") if r.strip()]
    else:
        # Fallback values if settings ever become empty
        bootinfo.kta_admin_roles = ["System Manager", "Quality Manager", "Manufacturing Manager"]
