from __future__ import annotations
import frappe
from frappe import _
from .qc import _get_doc_for_idc_write, _assert_child_table_exists, _session_employee_name_or_throw

ENJEKSIYON_CHILD_FIELDNAME = "enjeksiyon_olcumleri"

@frappe.whitelist()
def get_enjeksiyon_tolerans(hammadde_no: str) -> dict:
    """Fetch tolerance values for a given raw material (hammadde) from KTA Enjeksiyon Toleranslari."""
    if not hammadde_no:
        return {}
    
    if not frappe.db.exists("KTA Enjeksiyon Toleranslari", {"hammadde_no": hammadde_no}):
        return {}
        
    doc = frappe.get_doc("KTA Enjeksiyon Toleranslari", {"hammadde_no": hammadde_no})
    
    def to_f(val):
        return float(val) if val else 0.0

    return {
        "hammadde_kazan_isisi_merkez": to_f(doc.hammadde_kazan_isisi_merkez),
        "hammadde_kazan_isisi_tolerans": to_f(doc.hammadde_kazan_isisi_tolerans),
        "ara_hortum_isisi_merkez": to_f(doc.ara_hortum_isisi_merkez),
        "ara_hortum_isisi_tolerans": to_f(doc.ara_hortum_isisi_tolerans),
        "kafa_meme_isisi_merkez": to_f(doc.kafa_meme_isisi_merkez),
        "kafa_meme_isisi_tolerans": to_f(doc.kafa_meme_isisi_tolerans),
        "soguk_su_isisi_min": to_f(doc.soguk_su_isisi_min),
        "soguk_su_isisi_maks": to_f(doc.soguk_su_isisi_maks),
        "motor_devir_min": to_f(doc.motor_devir_min),
        "motor_devir_maks": to_f(doc.motor_devir_maks),
        "enjeksiyon_zamani_min": to_f(doc.enjeksiyon_zamani_min),
        "enjeksiyon_zamani_maks": to_f(doc.enjeksiyon_zamani_maks),
        "sogutma_zamani_min": to_f(doc.sogutma_zamani_min),
        "sogutma_zamani_maks": to_f(doc.sogutma_zamani_maks),
        "cekme_kuvveti_min": to_f(doc.cekme_kuvveti_min)
    }

@frappe.whitelist()
def add_enjeksiyon_olcumu(name: str, payload: str | dict):
    """Add a new enjeksiyon measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, ENJEKSIYON_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    row = {
        "kontrol_periyodu": payload.get("kontrol_periyodu"),
        "hammadde_no": payload.get("hammadde_no"),
        "goz_kontrol": 1 if payload.get("goz_kontrol") else 0,
        "cekme_kuvveti_olculen": float(payload.get("cekme_kuvveti_olculen") or 0),
        "hammadde_kazan_isisi": float(payload.get("hammadde_kazan_isisi") or 0),
        "ara_hortum_isisi": float(payload.get("ara_hortum_isisi") or 0),
        "kafa_meme_isisi": float(payload.get("kafa_meme_isisi") or 0),
        "soguk_su_isisi": float(payload.get("soguk_su_isisi") or 0),
        "motor_devir": float(payload.get("motor_devir") or 0),
        "hammadde_enjeksiyon_zamani": float(payload.get("hammadde_enjeksiyon_zamani") or 0),
        "sogutma_zamani": float(payload.get("sogutma_zamani") or 0),
        "hata_kodu": payload.get("hata_kodu"),
        "hata_miktari": float(payload.get("hata_miktari") or 0),
        
        # Hedef degerleri de payload'dan alip kaydediyoruz (frontend get_enjeksiyon_tolerans cagirip payload'a ekler)
        "hedef_hammadde_kazan_isisi_merkez": float(payload.get("hedef_hammadde_kazan_isisi_merkez") or 0),
        "hedef_hammadde_kazan_isisi_tolerans": float(payload.get("hedef_hammadde_kazan_isisi_tolerans") or 0),
        "hedef_ara_hortum_isisi_merkez": float(payload.get("hedef_ara_hortum_isisi_merkez") or 0),
        "hedef_ara_hortum_isisi_tolerans": float(payload.get("hedef_ara_hortum_isisi_tolerans") or 0),
        "hedef_kafa_meme_isisi_merkez": float(payload.get("hedef_kafa_meme_isisi_merkez") or 0),
        "hedef_kafa_meme_isisi_tolerans": float(payload.get("hedef_kafa_meme_isisi_tolerans") or 0),
        "hedef_soguk_su_isisi_min": float(payload.get("hedef_soguk_su_isisi_min") or 0),
        "hedef_soguk_su_isisi_maks": float(payload.get("hedef_soguk_su_isisi_maks") or 0),
        "hedef_motor_devir_min": float(payload.get("hedef_motor_devir_min") or 0),
        "hedef_motor_devir_maks": float(payload.get("hedef_motor_devir_maks") or 0),
        "hedef_enjeksiyon_zamani_min": float(payload.get("hedef_enjeksiyon_zamani_min") or 0),
        "hedef_enjeksiyon_zamani_maks": float(payload.get("hedef_enjeksiyon_zamani_maks") or 0),
        "hedef_sogutma_zamani_min": float(payload.get("hedef_sogutma_zamani_min") or 0),
        "hedef_sogutma_zamani_maks": float(payload.get("hedef_sogutma_zamani_maks") or 0),
        "hedef_cekme_kuvveti_min": float(payload.get("hedef_cekme_kuvveti_min") or 0),

        "olcum_tarihi": frappe.utils.now_datetime(),
        "operator": _session_employee_name_or_throw(),
    }

    doc.append(ENJEKSIYON_CHILD_FIELDNAME, row)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def update_enjeksiyon_olcumu(name: str, rowname: str, payload: str | dict):
    """Update an existing enjeksiyon measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, ENJEKSIYON_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    rows = doc.get(ENJEKSIYON_CHILD_FIELDNAME) or []
    target = next((r for r in rows if r.name == rowname), None)
    if not target:
        frappe.throw(_("Enjeksiyon ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    target.kontrol_periyodu = payload.get("kontrol_periyodu")
    target.hammadde_no = payload.get("hammadde_no")
    target.goz_kontrol = 1 if payload.get("goz_kontrol") else 0
    target.cekme_kuvveti_olculen = float(payload.get("cekme_kuvveti_olculen") or 0)
    target.hammadde_kazan_isisi = float(payload.get("hammadde_kazan_isisi") or 0)
    target.ara_hortum_isisi = float(payload.get("ara_hortum_isisi") or 0)
    target.kafa_meme_isisi = float(payload.get("kafa_meme_isisi") or 0)
    target.soguk_su_isisi = float(payload.get("soguk_su_isisi") or 0)
    target.motor_devir = float(payload.get("motor_devir") or 0)
    target.hammadde_enjeksiyon_zamani = float(payload.get("hammadde_enjeksiyon_zamani") or 0)
    target.sogutma_zamani = float(payload.get("sogutma_zamani") or 0)
    target.hata_kodu = payload.get("hata_kodu")
    target.hata_miktari = float(payload.get("hata_miktari") or 0)
    
    target.hedef_hammadde_kazan_isisi_merkez = float(payload.get("hedef_hammadde_kazan_isisi_merkez") or 0)
    target.hedef_hammadde_kazan_isisi_tolerans = float(payload.get("hedef_hammadde_kazan_isisi_tolerans") or 0)
    target.hedef_ara_hortum_isisi_merkez = float(payload.get("hedef_ara_hortum_isisi_merkez") or 0)
    target.hedef_ara_hortum_isisi_tolerans = float(payload.get("hedef_ara_hortum_isisi_tolerans") or 0)
    target.hedef_kafa_meme_isisi_merkez = float(payload.get("hedef_kafa_meme_isisi_merkez") or 0)
    target.hedef_kafa_meme_isisi_tolerans = float(payload.get("hedef_kafa_meme_isisi_tolerans") or 0)
    target.hedef_soguk_su_isisi_min = float(payload.get("hedef_soguk_su_isisi_min") or 0)
    target.hedef_soguk_su_isisi_maks = float(payload.get("hedef_soguk_su_isisi_maks") or 0)
    target.hedef_motor_devir_min = float(payload.get("hedef_motor_devir_min") or 0)
    target.hedef_motor_devir_maks = float(payload.get("hedef_motor_devir_maks") or 0)
    target.hedef_enjeksiyon_zamani_min = float(payload.get("hedef_enjeksiyon_zamani_min") or 0)
    target.hedef_enjeksiyon_zamani_maks = float(payload.get("hedef_enjeksiyon_zamani_maks") or 0)
    target.hedef_sogutma_zamani_min = float(payload.get("hedef_sogutma_zamani_min") or 0)
    target.hedef_sogutma_zamani_maks = float(payload.get("hedef_sogutma_zamani_maks") or 0)
    target.hedef_cekme_kuvveti_min = float(payload.get("hedef_cekme_kuvveti_min") or 0)

    target.olcum_tarihi = frappe.utils.now_datetime()
    target.operator = _session_employee_name_or_throw()

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def delete_enjeksiyon_olcumu(name: str, rowname: str):
    """Delete an enjeksiyon measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, ENJEKSIYON_CHILD_FIELDNAME)

    rows = doc.get(ENJEKSIYON_CHILD_FIELDNAME) or []
    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)

    if idx is None:
        frappe.throw(_("Enjeksiyon ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    rows.pop(idx)
    doc.set(ENJEKSIYON_CHILD_FIELDNAME, rows)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_enjeksiyon_allowed_items(doctype, txt, searchfield, start, page_len, filters):
    """Link field search for allowed enjeksiyon items that have tolerance data.

    filters expected:
      - calisma_karti: Calisma Karti name
    """
    from ._helpers import get_allowed_items_with_groups
    
    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

    calisma_karti = (filters or {}).get("calisma_karti")
    if not calisma_karti:
        return []

    allowed_items = get_allowed_items_with_groups(calisma_karti)
    if not allowed_items:
        return []

    txt = (txt or "").strip()

    items_placeholder = ", ".join(["%s"] * len(allowed_items))
    return frappe.db.sql(
        f"""
        SELECT name, item_name, item_group
        FROM `tabItem`
        WHERE
            name IN ({items_placeholder})
            AND disabled = 0
            AND name IN (SELECT hammadde_no FROM `tabKTA Enjeksiyon Toleranslari`)
            AND (name LIKE %s OR item_name LIKE %s)
        ORDER BY name ASC
        LIMIT %s, %s
        """,
        tuple(allowed_items) + (f"%{txt}%", f"%{txt}%", int(start), int(page_len)),
    )
