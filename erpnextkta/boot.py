import frappe

def boot_session(bootinfo):
    admin_roles = frappe.db.get_single_value("KTA Calisma Karti Settings", "admin_roles") or ""
    if admin_roles:
        bootinfo.kta_admin_roles = [r.strip() for r in admin_roles.split(",") if r.strip()]
    else:
        # Fallback values if settings ever become empty
        bootinfo.kta_admin_roles = ["System Manager", "Quality Manager", "Manufacturing Manager"]

    try:
        from erpnextkta.kta_mrp.mrp_engine.settings import get_mrp_settings
        mrp_settings = get_mrp_settings()
        bootinfo.kta_mrp_settings = {
            "planning_horizon_days": mrp_settings.planning_horizon_days,
            "backlog_lookback_days": mrp_settings.backlog_lookback_days,
            "default_production_time_days": mrp_settings.default_production_time_days,
            "urgent_shortage_weeks": mrp_settings.urgent_shortage_weeks,
        }
    except Exception:
        bootinfo.kta_mrp_settings = {"planning_horizon_days": 90}

