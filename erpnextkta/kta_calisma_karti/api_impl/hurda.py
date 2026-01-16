# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

from ._helpers import (
    HURDA_PARENT_COST_CENTER,
    get_child_table_fieldname,
    is_system_manager,
    require_my_employee,
)

@frappe.whitelist()
def get_hurda_nedeni_options(parent_cost_center: str = HURDA_PARENT_COST_CENTER):
    """Return cost center names whose parent_cost_center matches given value."""

    rows = frappe.get_all(
        "Cost Center",
        filters={"parent_cost_center": parent_cost_center, "is_group": 0},
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )
    return [r["name"] for r in rows]

def _assert_can_write_on_doc(doc):
    """Non-System Manager must be operator to modify."""
    if is_system_manager():
        return
    emp = require_my_employee()
    if doc.operator != emp:
        frappe.throw(_("Bu çalışma kartını düzenleme yetkiniz yok."), frappe.PermissionError)

def _assert_cost_center_allowed(hurda_nedeni: str):
    ok = frappe.db.exists(
        "Cost Center",
        {"name": hurda_nedeni, "parent_cost_center": HURDA_PARENT_COST_CENTER},
    )
    if not ok:
        frappe.throw(_("Hurda Nedeni geçersiz. Lütfen listeden seçin."))

@frappe.whitelist()
def add_hurda(
    name: str,
    parca_no: str,
    hurda_nedeni: str,
    miktar: float,
    birim: str,
    depo: str | None = None,
):
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("write")

    _assert_can_write_on_doc(doc)
    _assert_cost_center_allowed(hurda_nedeni)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")

    row = {
        "parca_no": parca_no,
        "hurda_nedeni": hurda_nedeni,
        "miktar": float(miktar or 0),
        "birim": birim,
    }
    if depo:
        row["depo"] = depo

    doc.append(child_fieldname, row)
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def update_hurda(
    name: str,
    rowname: str,
    parca_no: str,
    hurda_nedeni: str,
    miktar: float,
    birim: str,
    depo: str | None = None,
):
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("write")

    _assert_can_write_on_doc(doc)
    _assert_cost_center_allowed(hurda_nedeni)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    target = None
    for r in rows:
        if r.name == rowname:
            target = r
            break

    if not target:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    target.parca_no = parca_no
    target.hurda_nedeni = hurda_nedeni
    target.miktar = float(miktar or 0)
    target.birim = birim
    target.depo = depo or None

    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def delete_hurda(name: str, rowname: str):
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("write")

    _assert_can_write_on_doc(doc)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    idx = None
    for i, r in enumerate(rows):
        if r.name == rowname:
            idx = i
            break

    if idx is None:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    rows.pop(idx)
    doc.set(child_fieldname, rows)
    doc.save()

    return {"status": "success"}
