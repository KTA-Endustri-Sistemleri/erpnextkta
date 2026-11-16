import frappe


def execute():
    role_name = "KTA Gümrük Sorumlusu"
    if not frappe.db.exists("Role", role_name):
        role = frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1,
            }
        )
        role.insert(ignore_permissions=True)

    # Assign to Ceren Keçici, Ömür Muslu and Administrator
    target_users = [
        "ceren.kecici@kta-endustri.com.tr",
        "omur.muslu@kta-endustri.com.tr",
        "Administrator",
    ]
    for user_email in target_users:
        if frappe.db.exists("User", user_email):
            user = frappe.get_doc("User", user_email)
            if not any(r.role == role_name for r in user.roles):
                user.append("roles", {"role": role_name})
                user.save(ignore_permissions=True)

    # Ensure Workflow State exists
    state_name = "Mal Kabul Uyuşmazlığı"
    if not frappe.db.exists("Workflow State", state_name):
        frappe.get_doc(
            {
                "doctype": "Workflow State",
                "workflow_state_name": state_name,
                "style": "Danger",
            }
        ).insert(ignore_permissions=True)

    # Ensure Workflow Actions exist
    actions = ["Uyuşmazlık Bildir", "Sorun Çözüldü", "Gümrüğe İade"]
    for act in actions:
        if not frappe.db.exists("Workflow Action Master", act):
            frappe.get_doc(
                {
                    "doctype": "Workflow Action Master",
                    "workflow_action_name": act,
                }
            ).insert(ignore_permissions=True)
