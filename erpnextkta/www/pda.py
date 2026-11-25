import frappe
from frappe import _
from frappe.boot import load_translations

from erpnextkta.kta_stock.services.pda_service import (
    ALL_PDA_ROLES,
    get_pda_boot_data,
    has_valid_pda_device_cookie,
    set_pda_device_cookie,
)

no_cache = 1
sitemap = 0


def get_context(context):
    """Prepare auth-guarded boot context for the standalone /pda terminal."""
    if frappe.session.user == "Guest":
        if not has_valid_pda_device_cookie():
            frappe.local.flags.redirect_location = "/login?redirect-to=/pda"
            raise frappe.Redirect
    else:
        user_roles = set(frappe.get_roles(frappe.session.user))
        if not user_roles.intersection(ALL_PDA_ROLES):
            frappe.throw(
                _("Bu sayfaya erişim yetkiniz bulunmamaktadır."),
                frappe.PermissionError,
            )
        set_pda_device_cookie()

    bootinfo = frappe._dict(
        {
            "lang": str(getattr(frappe.local, "lang", None) or "tr"),
            "site_name": str(getattr(frappe.local, "site", "") or ""),
        }
    )
    load_translations(bootinfo)
    resolved_lang = str(
        bootinfo.get("lang") or getattr(frappe.local, "lang", None) or "tr"
    )
    bootinfo["lang"] = resolved_lang

    pda_boot = get_pda_boot_data()
    context.lang = resolved_lang
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.build_version = frappe.utils.get_build_version()
    context.boot = bootinfo
    context.boot_json = frappe.as_json(bootinfo).replace("</", "<\\/")
    context.pda_boot_data = pda_boot
    context.pda_boot_json = frappe.as_json(pda_boot).replace("</", "<\\/")
    return context
