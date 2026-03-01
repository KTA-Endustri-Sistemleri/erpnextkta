from __future__ import annotations
import frappe
from frappe import _

from ._helpers import require_my_employee, is_system_manager, is_quality_user
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed


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
