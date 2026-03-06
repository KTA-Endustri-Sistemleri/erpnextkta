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

def get_allowed_items_with_groups(calisma_karti_name: str, alt_operasyon: str = None) -> list[str]:
    ck = frappe.db.get_value("Calisma Karti", calisma_karti_name, ["custom_work_order", "operasyon"], as_dict=True)
    if not ck or not ck.custom_work_order:
        return []

    wo = frappe.get_doc("Work Order", ck.custom_work_order)
    wo_items = [i.item_code for i in getattr(wo, "required_items", []) if i.item_code]

    if not wo_items:
        return []

    allowed_groups = []

    if alt_operasyon:
        # Check Alt Operasyon
        ao_doc = frappe.get_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon)
        parent_op = ao_doc.parent_operation

        current_groups = []
        for row in getattr(ao_doc, "allowed_material_groups", []):
            if row.item_group:
                current_groups.append(row.item_group)

        if current_groups:
            # If current sub-operation has groups defined, use ONLY them.
            allowed_groups = current_groups
        else:
            # If empty, use ALL prior sub-operations + parent operation
            ao_list = frappe.get_all("KTA Calisma Karti Alt Operasyonlari",
                                     filters={"parent_operation": parent_op, "sequence": ["<=", getattr(ao_doc, "sequence", 0)]},
                                     fields=["name"])
            for ao in ao_list:
                ao_detail = frappe.get_doc("KTA Calisma Karti Alt Operasyonlari", ao.name)
                for row in getattr(ao_detail, "allowed_material_groups", []):
                    if row.item_group:
                        allowed_groups.append(row.item_group)

            op_doc = frappe.get_doc("KTA Calisma Karti Operasyonlari", parent_op)
            for row in getattr(op_doc, "allowed_material_groups", []):
                if row.item_group:
                    allowed_groups.append(row.item_group)
    else:
        # Hurda logic (or missing alt_operasyon): fallback to parent_operation based on Calisma Karti
        if ck.operasyon:
            current_op_doc = frappe.get_doc("KTA Calisma Karti Operasyonlari", ck.operasyon)
            current_sequence = getattr(current_op_doc, "sequence", 0)

            # Kendisine eşit veya daha küçük sequence numarasına sahip TÜM Ana Operasyonları al
            previous_main_ops = frappe.get_all(
                "KTA Calisma Karti Operasyonlari",
                filters={"sequence": ["<=", current_sequence]},
                fields=["name"]
            )

            for main_op in previous_main_ops:
                op_doc = frappe.get_doc("KTA Calisma Karti Operasyonlari", main_op.name)
                
                # 1. Ana operasyonun kendisindeki malzeme gruplarını ekle
                for row in getattr(op_doc, "allowed_material_groups", []):
                    if row.item_group:
                        allowed_groups.append(row.item_group)

                # 2. Bu ana operasyona bağlı tüm Alt Operasyonların malzeme gruplarını çek ve ekle
                sub_ops = frappe.get_all(
                    "KTA Calisma Karti Alt Operasyonlari",
                    filters={"parent_operation": main_op.name},
                    fields=["name"]
                )
                for sub_op in sub_ops:
                    sub_op_doc = frappe.get_doc("KTA Calisma Karti Alt Operasyonlari", sub_op.name)
                    for row in getattr(sub_op_doc, "allowed_material_groups", []):
                        if row.item_group:
                            allowed_groups.append(row.item_group)

    allowed_groups = list(set(allowed_groups))

    # If allowed groups configured, filter Work Order items by those groups
    if allowed_groups:
        item_group_map = frappe._dict(frappe.get_all("Item",
                                       filters={"name": ["in", wo_items]},
                                       fields=["name", "item_group"],
                                       as_list=1))

        filtered_wo_items = []
        for i_code in wo_items:
            if item_group_map.get(i_code) in allowed_groups:
                filtered_wo_items.append(i_code)

        return list(set(filtered_wo_items))

    # If no groups are configured anywhere, just return work order items
    return list(set(wo_items))
