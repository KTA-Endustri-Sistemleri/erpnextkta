from __future__ import annotations
import frappe
from frappe import _

from ._helpers import require_my_employee, is_system_manager, is_quality_user
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed


def _get_allowed_groups_for_alt_op(alt_operasyon_name: str) -> list[str]:
    """Return allowed item_groups for the given alt operasyon.

    Priority:
    1. Sub-op's own allowed_material_groups (if any)
    2. Parent operation's allowed_material_groups (if any)
    3. Empty list → unrestricted
    """
    sub_op = frappe.get_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon_name)

    # 1. Sub-op level
    sub_groups = [row.item_group for row in (sub_op.allowed_material_groups or []) if row.item_group]
    if sub_groups:
        return sub_groups

    # 2. Parent operation level
    if sub_op.parent_operation:
        parent_op = frappe.get_doc("KTA Calisma Karti Operasyonlari", sub_op.parent_operation)
        parent_groups = [row.item_group for row in (parent_op.allowed_material_groups or []) if row.item_group]
        if parent_groups:
            return parent_groups

    # 3. No restriction
    return []


def _assert_hammadde_allowed(alt_operasyon: str, hammadde: str):
    """Validate that hammadde's item_group is within allowed groups."""
    if not hammadde:
        return
    allowed = _get_allowed_groups_for_alt_op(alt_operasyon)
    if not allowed:
        return  # unrestricted
    item_group = frappe.db.get_value("Item", hammadde, "item_group")
    if item_group not in allowed:
        frappe.throw(
            _("Seçilen hammadde ({0}) bu alt operasyon için izin verilmiyor. İzin verilen gruplar: {1}").format(
                hammadde, ", ".join(allowed)
            ),
            frappe.ValidationError,
        )


def _assert_can_write(doc):
    """Raise PermissionError if current user is not allowed to write the given CK."""
    if is_system_manager() or is_quality_user():
        return
    emp = require_my_employee()
    if doc.operator != emp:
        frappe.throw(_("Bu İşlem için yetkiniz yok."), frappe.PermissionError)


@frappe.whitelist()
def add_alt_operasyon_kaydi(
    calisma_karti: str,
    alt_operasyon: str,
    adet: float = 0,
    hammadde: str = None,
    uom: str = None,
    note: str = None,
):
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    if hammadde:
        _assert_hammadde_allowed(alt_operasyon, hammadde)

    doc.append(
        "alt_operasyon_kayitlari",
        {
            "alt_operasyon": alt_operasyon,
            "hammadde": hammadde,
            "adet": adet,
            "uom": uom,
            "note": note,
        },
    )
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:add")
    return doc.get("alt_operasyon_kayitlari")[-1].name


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_allowed_hammadde_items(doctype, txt, searchfield, start, page_len, filters):
    """Link field search for allowed hammadde items based on alt operasyon material groups.

    Priority:
    1. Sub-op's own allowed_material_groups (if any)
    2. Parent operation's allowed_material_groups (if any)
    3. No restriction -> all items

    filters expected:
      - alt_operasyon: KTA Calisma Karti Alt Operasyonlari name
    """
    alt_operasyon = (filters or {}).get("alt_operasyon")
    txt = (txt or "").strip()
    like = f"%{txt}%"

    allowed_groups = _get_allowed_groups_for_alt_op(alt_operasyon) if alt_operasyon else []

    if allowed_groups:
        groups_placeholder = ", ".join(["%s"] * len(allowed_groups))
        return frappe.db.sql(
            f"""
            SELECT name, item_name, item_group
            FROM `tabItem`
            WHERE
                item_group IN ({groups_placeholder})
                AND disabled = 0
                AND (name LIKE %s OR item_name LIKE %s)
            ORDER BY name ASC
            LIMIT %s, %s
            """,
            tuple(allowed_groups) + (like, like, int(start), int(page_len)),
        )
    else:
        return frappe.db.sql(
            """
            SELECT name, item_name, item_group
            FROM `tabItem`
            WHERE
                disabled = 0
                AND (name LIKE %s OR item_name LIKE %s)
            ORDER BY name ASC
            LIMIT %s, %s
            """,
            (like, like, int(start), int(page_len)),
        )


@frappe.whitelist()
def update_alt_operasyon_kaydi(
    calisma_karti: str,
    row_id: str,
    alt_operasyon: str,
    adet: float = 0,
    hammadde: str = None,
    uom: str = None,
    note: str = None,
):
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    if hammadde:
        _assert_hammadde_allowed(alt_operasyon, hammadde)

    row = doc.get("alt_operasyon_kayitlari", {"name": row_id})
    if not row:
        frappe.throw(_("Kayıt bulunamadı."))
    row = row[0]

    row.alt_operasyon = alt_operasyon
    row.hammadde = hammadde
    row.adet = adet
    row.uom = uom
    row.note = note

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:update")
    return row.name


@frappe.whitelist()
def delete_alt_operasyon_kaydi(calisma_karti: str, row_id: str):
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)

    to_remove = [r for r in doc.get("alt_operasyon_kayitlari") if r.name == row_id]
    if not to_remove:
        frappe.throw(_("Kayıt bulunamadı."))

    for r in to_remove:
        doc.remove(r)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:delete")
    return True
