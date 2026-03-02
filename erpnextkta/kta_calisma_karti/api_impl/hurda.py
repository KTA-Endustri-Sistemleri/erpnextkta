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


# -----------------------------
# NEW: BOM operation based filter
# -----------------------------

_JOB_CARD_REF_FIELDS = [
    # try common fieldnames; keep safe fallback order
    "is_karti",
    "job_card",
    "job_card_no",
    "custom_job_card_ref",
    "custom_job_card",
]

def _get_job_card_name_from_calisma_karti(doc) -> str:
    """Extract Job Card reference from Calisma Karti with fallback fieldnames."""
    for f in _JOB_CARD_REF_FIELDS:
        val = getattr(doc, f, None)
        if val:
            return str(val)
    frappe.throw(_("Çalışma Kartı üzerinde Job Card referansı bulunamadı."))


def _get_allowed_hurda_item_codes_for_doc(doc) -> set[str]:
    """Allowed = BOM.items where operation matches Job Card.operation."""
    jc_name = _get_job_card_name_from_calisma_karti(doc)
    jc = frappe.get_doc("Job Card", jc_name)

    operation = (getattr(jc, "operation", None) or "").strip()
    bom_no = (getattr(jc, "bom_no", None) or "").strip()

    if not operation:
        frappe.throw(_("Job Card üzerinde operasyon bulunamadı."))
    if not bom_no:
        frappe.throw(_("Job Card üzerinde BOM No bulunamadı."))

    # Find the processing order (idx) of the current operation
    current_op_idx = frappe.db.get_value(
        "BOM Operation",
        {"parent": bom_no, "parenttype": "BOM", "operation_no": operation},
        "idx"
    )

    if not current_op_idx:
        # Fallback to strict match if idx not found
        valid_operations = [operation]
    else:
        # Get all operations up to current_op_idx
        prev_ops = frappe.get_all(
            "BOM Operation",
            filters={
                "parent": bom_no,
                "parenttype": "BOM",
                "idx": ["<=", current_op_idx]
            },
            fields=["operation_no"]
        )
        valid_operations = [o.get("operation_no") for o in prev_ops if o.get("operation_no")]

    if not valid_operations:
        valid_operations = [operation]

    # BOM Item child table doctype is "BOM Item"
    rows = frappe.get_all(
        "BOM Item",
        filters={
            "parent": bom_no,
            "parenttype": "BOM",
            "parentfield": "items",
            "operation": ["in", valid_operations],
        },
        fields=["item_code"],
        limit_page_length=2000,
    )

    allowed = { (r.get("item_code") or "").strip() for r in rows if r.get("item_code") }
    allowed.discard("")
    return allowed


def _assert_hurda_item_allowed_for_operation(doc, parca_no: str):
    """Reject if parca_no is not in allowed BOM items for Job Card operation."""
    code = (parca_no or "").strip()
    if not code:
        frappe.throw(_("Parça Numarası (Item) boş olamaz."))

    allowed = _get_allowed_hurda_item_codes_for_doc(doc)
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

    # Resolve Job Card from Calisma Karti (same fallback approach you used elsewhere)
    jc_name = None
    for f in ["is_karti", "job_card", "job_card_no", "custom_job_card_ref", "custom_job_card"]:
        v = getattr(ck, f, None)
        if v:
            jc_name = str(v)
            break
    if not jc_name:
        frappe.throw(_("Çalışma Kartı üzerinde Job Card referansı bulunamadı."), frappe.ValidationError)

    jc = frappe.get_doc("Job Card", jc_name)
    operation = (getattr(jc, "operation", None) or "").strip()
    bom_no = (getattr(jc, "bom_no", None) or "").strip()

    if not operation:
        frappe.throw(_("Job Card üzerinde operasyon bulunamadı."), frappe.ValidationError)
    if not bom_no:
        frappe.throw(_("Job Card üzerinde BOM No bulunamadı."), frappe.ValidationError)

    txt = (txt or "").strip()

    # Only BOM items where BOM Item.operation is in valid set (idx <= current_operation idx)
    return frappe.db.sql(
        """
        select i.name, i.item_name
        from `tabBOM Item` bi
        inner join `tabItem` i on i.name = bi.item_code
        where
            bi.parent = %(bom_no)s
            and bi.parenttype = 'BOM'
            and bi.parentfield = 'items'
            and bi.operation IN (
                select bo.operation_no 
                from `tabBOM Operation` bo 
                where bo.parent = %(bom_no)s 
                  and bo.idx <= (
                      select curr_bo.idx 
                      from `tabBOM Operation` curr_bo 
                      where curr_bo.parent = %(bom_no)s 
                        and curr_bo.operation_no = %(operation)s 
                      limit 1
                  )
            )
            and (
                i.name like %(like)s
                or i.item_name like %(like)s
            )
        order by i.name asc
        limit %(start)s, %(page_len)s
        """,
        {
            "bom_no": bom_no,
            "operation": operation,
            "like": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
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
