# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

from ._helpers import (
    HURDA_PARENT_COST_CENTER,
    get_child_table_fieldname,
    is_system_manager,
    require_my_employee,
    get_allowed_items_with_groups,
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


# -----------------------------
# NEW: BOM operation based filter
# -----------------------------

def _assert_hurda_item_allowed_for_operation(doc, parca_no: str):
    """Reject if parca_no is not in allowed BOM items for Job Card operation."""
    code = (parca_no or "").strip()
    if not code:
        frappe.throw(_("Parça Numarası (Item) boş olamaz."))

    allowed = get_allowed_items_with_groups(doc.name)
    if code not in allowed:
        frappe.throw(
            _(
                "Bu hurda parçası bu operasyon için izinli değil. "
                "Sadece BOM içinde ilgili operasyon satırındaki hammaddeler hurdaya yazılabilir."
            ),
            frappe.PermissionError,
        )

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_allowed_hurda_items(doctype, txt, searchfield, start, page_len, filters):
    """Link field search for allowed hurda items for given Calisma Karti.

    filters expected:
      - calisma_karti: Calisma Karti name
    """
    calisma_karti = (filters or {}).get("calisma_karti")
    if not calisma_karti:
        return []

    ck = frappe.get_doc("Calisma Karti", calisma_karti)
    ck.check_permission("read")

    txt = (txt or "").strip()

    allowed_items = get_allowed_items_with_groups(calisma_karti)
    if not allowed_items:
        return []

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
        tuple(allowed_items) + (f"%{txt}%", f"%{txt}%", int(start), int(page_len)),
    )

# -----------------------------
# CRUD (updated)
# -----------------------------

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

    # NEW enforcement
    _assert_hurda_item_allowed_for_operation(doc, parca_no)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")

    row = {
        "parca_no": (parca_no or "").strip(),
        "hurda_nedeni": hurda_nedeni,
        "miktar": float(miktar or 0),
        "birim": birim,
    }
    if depo:
        row["depo"] = depo

    doc.append(child_fieldname, row)
    doc.flags.ignore_validate_update_after_submit = True
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

    # NEW enforcement
    _assert_hurda_item_allowed_for_operation(doc, parca_no)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    target = next((r for r in rows if r.name == rowname), None)
    if not target:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    target.parca_no = (parca_no or "").strip()
    target.hurda_nedeni = hurda_nedeni
    target.miktar = float(miktar or 0)
    target.birim = birim
    target.depo = depo or None

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def delete_hurda(name: str, rowname: str):
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("write")

    _assert_can_write_on_doc(doc)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)
    if idx is None:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    rows.pop(idx)
    doc.set(child_fieldname, rows)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}
