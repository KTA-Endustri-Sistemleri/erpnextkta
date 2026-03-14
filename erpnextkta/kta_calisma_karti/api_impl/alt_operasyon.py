from __future__ import annotations
import frappe
from frappe import _

from ._helpers import require_my_employee, is_system_manager, is_quality_user, get_allowed_items_with_groups
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed


def _assert_hammadde_allowed(calisma_karti: str, hammadde: str, alt_operasyon: str = None):
    """Validate that hammadde is allowed based on BOM sequence."""
    if not hammadde:
        return
    allowed_items = get_allowed_items_with_groups(calisma_karti, alt_operasyon)
    if not allowed_items:
        frappe.throw(
            _("İş emrinde bu aşama için izin verilen malzeme grubunda hammadde bulunamadı."),
            frappe.ValidationError,
        )
    if hammadde not in allowed_items:
        frappe.throw(
            _("Seçilen hammadde ({0}) iş emri BOM'unda bu aşama için izin verilmiyor.").format(hammadde),
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
        _assert_hammadde_allowed(calisma_karti, hammadde, alt_operasyon)

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
    doc.flags.ignore_validate_update_after_submit = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:add")
    return doc.get("alt_operasyon_kayitlari")[-1].name


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_allowed_hammadde_items(doctype, txt, searchfield, start, page_len, filters):
    """Link field search for allowed hammadde items based on Work Order BOM operation sequence.

    filters expected:
      - calisma_karti: Calisma Karti name
    """
    calisma_karti = (filters or {}).get("calisma_karti")
    alt_operasyon = (filters or {}).get("alt_operasyon")
    txt = (txt or "").strip()
    like = f"%{txt}%"

    allowed_items = get_allowed_items_with_groups(calisma_karti, alt_operasyon) if calisma_karti else []

    if allowed_items:
        items_placeholder = ", ".join(["%s"] * len(allowed_items))
        return frappe.db.sql(
            f"""
            SELECT name, item_name, item_group
            FROM `tabItem`
            WHERE
                name IN ({items_placeholder})
                AND disabled = 0
                AND (name LIKE %s OR item_name LIKE %s)
            ORDER BY name ASC
            LIMIT %s, %s
            """,
            tuple(allowed_items) + (like, like, int(start), int(page_len)),
        )
    else:
        return []


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
        _assert_hammadde_allowed(calisma_karti, hammadde, alt_operasyon)

    row = doc.get("alt_operasyon_kayitlari", {"name": row_id})
    if not row:
        frappe.throw(_("Kayıt bulunamadı."))
    row = row[0]

    row.alt_operasyon = alt_operasyon
    row.hammadde = hammadde
    row.adet = adet
    row.uom = uom
    row.note = note

    doc.flags.ignore_validate_update_after_submit = True
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

    doc.flags.ignore_validate_update_after_submit = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:delete")
    return True


@frappe.whitelist()
def get_alt_operasyon_options(parent_operation: str):
    """Return active sub-operations for a given parent operation as {label, value} pairs."""
    ops = frappe.get_all(
        "KTA Calisma Karti Alt Operasyonlari",
        filters={
            "parent_operation": parent_operation,
            "is_active": 1,
        },
        fields=["name", "title"],
        order_by="sequence ASC, title ASC",
    )
    return [{"label": o.title, "value": o.name} for o in ops]
