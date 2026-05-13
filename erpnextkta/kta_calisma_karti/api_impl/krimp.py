# English comments as requested

from __future__ import annotations
import frappe
from frappe import _
from .qc import _get_doc_for_idc_write, _assert_child_table_exists, _session_employee_name_or_throw

KRIMP_CHILD_FIELDNAME = "krimp_olcumleri"

@frappe.whitelist()
def add_krimp_olcumu(name: str, payload: str | dict):
    """Add a new krimp measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, KRIMP_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    row = {
        "kablo_no": payload.get("kablo_no"),
        "kontak_no": payload.get("kontak_no"),
        "kalip_no": payload.get("kalip_no"),
        "makine_pres_no": payload.get("makine_pres_no"),
        "kablo_kesiti": payload.get("kablo_kesiti"),
        "hedef_kablo_boyu": float(payload.get("hedef_kablo_boyu") or 0),
        "olculen_kablo_boyu": float(payload.get("olculen_kablo_boyu") or 0),
        "hedef_iletken_krimp_yuksekliği": float(payload.get("hedef_iletken_krimp_yuksekliği") or 0),
        "olculen_iletken_krimp_yuksekliği": float(payload.get("olculen_iletken_krimp_yuksekliği") or 0),
        "izokrimp_yuksekligi": float(payload.get("izokrimp_yuksekligi") or 0),
        "siyirma_boyu": float(payload.get("siyirma_boyu") or 0),
        "cekme_kuvveti_n": float(payload.get("cekme_kuvveti_n") or 0),
        "capak_boyu": float(payload.get("capak_boyu") or 0),
        "radus_mevcut": 1 if payload.get("radus_mevcut") else 0,
        "tel_kesme_mevcut": 1 if payload.get("tel_kesme_mevcut") else 0,
        "olcum_tarihi": frappe.utils.now_datetime(),
        "operator": _session_employee_name_or_throw(),
    }

    doc.append(KRIMP_CHILD_FIELDNAME, row)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def update_krimp_olcumu(name: str, rowname: str, payload: str | dict):
    """Update an existing krimp measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, KRIMP_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    rows = doc.get(KRIMP_CHILD_FIELDNAME) or []
    target = next((r for r in rows if r.name == rowname), None)
    if not target:
        frappe.throw(_("Krimp ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    target.kablo_no = payload.get("kablo_no")
    target.kontak_no = payload.get("kontak_no")
    target.kalip_no = payload.get("kalip_no")
    target.makine_pres_no = payload.get("makine_pres_no")
    target.kablo_kesiti = payload.get("kablo_kesiti")
    target.hedef_kablo_boyu = float(payload.get("hedef_kablo_boyu") or 0)
    target.olculen_kablo_boyu = float(payload.get("olculen_kablo_boyu") or 0)
    target.hedef_iletken_krimp_yuksekliği = float(payload.get("hedef_iletken_krimp_yuksekliği") or 0)
    target.olculen_iletken_krimp_yuksekliği = float(payload.get("olculen_iletken_krimp_yuksekliği") or 0)
    target.izokrimp_yuksekligi = float(payload.get("izokrimp_yuksekligi") or 0)
    target.siyirma_boyu = float(payload.get("siyirma_boyu") or 0)
    target.cekme_kuvveti_n = float(payload.get("cekme_kuvveti_n") or 0)
    target.capak_boyu = float(payload.get("capak_boyu") or 0)
    target.radus_mevcut = 1 if payload.get("radus_mevcut") else 0
    target.tel_kesme_mevcut = 1 if payload.get("tel_kesme_mevcut") else 0

    target.olcum_tarihi = frappe.utils.now_datetime()
    target.operator = _session_employee_name_or_throw()

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def delete_krimp_olcumu(name: str, rowname: str):
    """Delete a krimp measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, KRIMP_CHILD_FIELDNAME)

    rows = doc.get(KRIMP_CHILD_FIELDNAME) or []
    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)

    if idx is None:
        frappe.throw(_("Krimp ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    rows.pop(idx)
    doc.set(KRIMP_CHILD_FIELDNAME, rows)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}
