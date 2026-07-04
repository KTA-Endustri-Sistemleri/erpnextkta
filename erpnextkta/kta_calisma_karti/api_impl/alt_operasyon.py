from __future__ import annotations
import frappe
from frappe import _

from ._helpers import require_my_employee, has_admin_roles, get_allowed_items_with_groups
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed


def _assert_hammadde_allowed(calisma_karti: str, hammadde: str, alt_operasyon: str = None):
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
    if doc.docstatus == 2:
        frappe.throw(_("İptal edilmiş kartta işlem yapılamaz."))
    if doc.get_durum() in ["bitmis", "reddedildi"]:
        frappe.throw(_("İşlemi bitmiş veya reddedilmiş karta müdahale edemezsiniz."))

    if has_admin_roles():
        return
    emp = require_my_employee()
    if doc.operator != emp:
        frappe.throw(_("Bu İşlem için yetkiniz yok."), frappe.PermissionError)

def _calculate_tuketim(hammadde, boyut, islem_adedi):
    if not hammadde:
        return islem_adedi, None
    uom = frappe.db.get_value("Item", hammadde, "stock_uom")
    if uom and uom.lower() in ["m", "metre", "meter"]:
        boyut = float(boyut or 0)
        islem = float(islem_adedi or 0)
        return (boyut * islem) / 1000.0, uom
    return float(islem_adedi or 0), uom


@frappe.whitelist()
def add_alt_operasyon_kaydi(
    calisma_karti: str,
    alt_operasyon: str,
    hammadde: str = None, boyut_1_mm: float = 0, islem_adedi_1: float = 0,
    hammadde_2: str = None, boyut_2_mm: float = 0, islem_adedi_2: float = 0,
    hammadde_3: str = None, boyut_3_mm: float = 0, islem_adedi_3: float = 0,
    note: str = None,
):
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    
    if hammadde: _assert_hammadde_allowed(calisma_karti, hammadde, alt_operasyon)
    if hammadde_2: _assert_hammadde_allowed(calisma_karti, hammadde_2, alt_operasyon)
    if hammadde_3: _assert_hammadde_allowed(calisma_karti, hammadde_3, alt_operasyon)

    # Tek Taraf Validation
    ao_doc = frappe.get_cached_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon)
    if ao_doc.operasyon_tipi == "Tek Taraf":
        if not hammadde_2 and not hammadde_3:
            frappe.throw(_("Tek Taraflı operasyonda Sol veya Sağ uca mutlaka bir terminal seçilmelidir."))
        if hammadde_2 and hammadde_3:
            frappe.throw(_("Tek Taraflı operasyonda her iki uca birden terminal seçilemez."))
        if hammadde_2 and float(boyut_2_mm or 0) > 0:
            frappe.throw(_("Sol uca terminal seçildiğinde Sol Sıyırma (mm) girilemez."))
        if hammadde_3 and float(boyut_3_mm or 0) > 0:
            frappe.throw(_("Sağ uca terminal seçildiğinde Sağ Sıyırma (mm) girilemez."))
    elif ao_doc.operasyon_tipi == "Çift Taraf":
        if not hammadde_2 or not hammadde_3:
            frappe.throw(_("Çift Taraflı operasyonlarda hem Sol hem de Sağ uca terminal seçilmesi zorunludur."))
            
    if hammadde_2:
        islem_adedi_2 = islem_adedi_1
    if hammadde_3:
        islem_adedi_3 = islem_adedi_1

    adet_1, uom_1 = _calculate_tuketim(hammadde, boyut_1_mm, islem_adedi_1)
    adet_2, uom_2 = _calculate_tuketim(hammadde_2, boyut_2_mm, islem_adedi_2)
    adet_3, uom_3 = _calculate_tuketim(hammadde_3, boyut_3_mm, islem_adedi_3)

    doc.append(
        "alt_operasyon_kayitlari",
        {
            "alt_operasyon": alt_operasyon,
            "hammadde": hammadde,
            "boyut_1_mm": boyut_1_mm,
            "islem_adedi_1": islem_adedi_1,
            "adet": adet_1,
            "uom": uom_1,
            "hammadde_2": hammadde_2,
            "boyut_2_mm": boyut_2_mm,
            "islem_adedi_2": islem_adedi_2,
            "adet_2": adet_2,
            "uom_2": uom_2,
            "hammadde_3": hammadde_3,
            "boyut_3_mm": boyut_3_mm,
            "islem_adedi_3": islem_adedi_3,
            "adet_3": adet_3,
            "uom_3": uom_3,
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
    calisma_karti = (filters or {}).get("calisma_karti")
    alt_operasyon = (filters or {}).get("alt_operasyon")
    hammadde_sira = (filters or {}).get("hammadde_sira") or "Tümü"
    txt = (txt or "").strip()
    like = f"%{txt}%"

    allowed_items = get_allowed_items_with_groups(calisma_karti, alt_operasyon, hammadde_sira) if calisma_karti else []

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
    hammadde: str = None, boyut_1_mm: float = 0, islem_adedi_1: float = 0,
    hammadde_2: str = None, boyut_2_mm: float = 0, islem_adedi_2: float = 0,
    hammadde_3: str = None, boyut_3_mm: float = 0, islem_adedi_3: float = 0,
    note: str = None,
):
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    
    if hammadde: _assert_hammadde_allowed(calisma_karti, hammadde, alt_operasyon)
    if hammadde_2: _assert_hammadde_allowed(calisma_karti, hammadde_2, alt_operasyon)
    if hammadde_3: _assert_hammadde_allowed(calisma_karti, hammadde_3, alt_operasyon)

    # Tek Taraf Validation
    ao_doc = frappe.get_cached_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon)
    if ao_doc.operasyon_tipi == "Tek Taraf":
        if not hammadde_2 and not hammadde_3:
            frappe.throw(_("Tek Taraflı operasyonda Sol veya Sağ uca mutlaka bir terminal seçilmelidir."))
        if hammadde_2 and hammadde_3:
            frappe.throw(_("Tek Taraflı operasyonda her iki uca birden terminal seçilemez."))
        if hammadde_2 and float(boyut_2_mm or 0) > 0:
            frappe.throw(_("Sol uca terminal seçildiğinde Sol Sıyırma (mm) girilemez."))
        if hammadde_3 and float(boyut_3_mm or 0) > 0:
            frappe.throw(_("Sağ uca terminal seçildiğinde Sağ Sıyırma (mm) girilemez."))
    elif ao_doc.operasyon_tipi == "Çift Taraf":
        if not hammadde_2 or not hammadde_3:
            frappe.throw(_("Çift Taraflı operasyonlarda hem Sol hem de Sağ uca terminal seçilmesi zorunludur."))
            
    if hammadde_2:
        islem_adedi_2 = islem_adedi_1
    if hammadde_3:
        islem_adedi_3 = islem_adedi_1

    row = doc.get("alt_operasyon_kayitlari", {"name": row_id})
    if not row:
        frappe.throw(_("Kayıt bulunamadı."))
    row = row[0]

    adet_1, uom_1 = _calculate_tuketim(hammadde, boyut_1_mm, islem_adedi_1)
    adet_2, uom_2 = _calculate_tuketim(hammadde_2, boyut_2_mm, islem_adedi_2)
    adet_3, uom_3 = _calculate_tuketim(hammadde_3, boyut_3_mm, islem_adedi_3)

    row.alt_operasyon = alt_operasyon
    row.hammadde = hammadde
    row.boyut_1_mm = boyut_1_mm
    row.islem_adedi_1 = islem_adedi_1
    row.adet = adet_1
    row.uom = uom_1
    
    row.hammadde_2 = hammadde_2
    row.boyut_2_mm = boyut_2_mm
    row.islem_adedi_2 = islem_adedi_2
    row.adet_2 = adet_2
    row.uom_2 = uom_2
    
    row.hammadde_3 = hammadde_3
    row.boyut_3_mm = boyut_3_mm
    row.islem_adedi_3 = islem_adedi_3
    row.adet_3 = adet_3
    row.uom_3 = uom_3
    
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
    fields = ["name", "title"]
    if frappe.get_meta("KTA Calisma Karti Alt Operasyonlari").has_field("hammadde_sayisi"):
        fields.append("hammadde_sayisi")
    if frappe.get_meta("KTA Calisma Karti Alt Operasyonlari").has_field("operasyon_tipi"):
        fields.append("operasyon_tipi")

    ops = frappe.get_all(
        "KTA Calisma Karti Alt Operasyonlari",
        filters={
            "parent_operation": parent_operation,
            "is_active": 1,
        },
        fields=fields,
        order_by="sequence ASC, title ASC",
    )
    
    parent_ekran_tipi = "Tekli Hammadde"
    parent_allowed_materials_count = 0
    if parent_operation:
        parent_ekran_tipi = frappe.db.get_value("KTA Calisma Karti Operasyonlari", parent_operation, "ekran_tipi") or "Tekli Hammadde"
        parent_allowed_materials_count = frappe.db.count("KTA Sub Operation Allowed Material Groups", filters={"parent": parent_operation, "parenttype": "KTA Calisma Karti Operasyonlari"})

    for o in ops:
        if not o.get("hammadde_sayisi"):
            count = frappe.db.count("KTA Sub Operation Allowed Material Groups", filters={"parent": o.name, "parenttype": "KTA Calisma Karti Alt Operasyonlari"})
            if count == 0:
                count = parent_allowed_materials_count
            o["hammadde_sayisi"] = str(count) if count > 0 else "1"

    return {
        "options": [{"label": o.title, "value": o.name, "hammadde_sayisi": o.get("hammadde_sayisi") or "1", "operasyon_tipi": o.get("operasyon_tipi") or ""} for o in ops],
        "ekran_tipi": parent_ekran_tipi
    }

