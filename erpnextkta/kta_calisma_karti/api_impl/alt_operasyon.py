from __future__ import annotations
import frappe
from frappe import _
from frappe.utils import flt

from ._helpers import require_my_employee, has_admin_roles, get_allowed_items_with_groups, get_my_employee_or_none, has_qc_role
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed


def _is_coklu_hammadde(calisma_karti: str) -> bool:
    """Return True if the operation uses the multi-material screen."""
    operasyon = frappe.db.get_value(
        "Calisma Karti", calisma_karti, "operasyon"
    )
    if not operasyon:
        return False
    ekran_tipi = frappe.db.get_value(
        "KTA Calisma Karti Operasyonlari", operasyon, "ekran_tipi"
    )
    return ekran_tipi == "Çoklu Hammadde"


def _get_wo_required_qty_map(work_order: str) -> dict[str, float]:
    """Return {item_code: required_qty} from Work Order required_items."""
    rows = frappe.get_all(
        "Work Order Item",
        filters={"parent": work_order, "parenttype": "Work Order"},
        fields=["item_code", "required_qty"],
    )
    return {r.item_code: flt(r.required_qty) for r in rows}


def _get_existing_consumption(
    work_order: str, exclude_row: str = None
) -> dict[str, float]:
    """Sum material consumption across ALL job cards of this work order.

    Returns {item_code: total_consumed} aggregated from hammadde/adet,
    hammadde_2/adet_2, hammadde_3/adet_3 columns.
    """
    exclude_condition = ""
    params = [work_order]
    if exclude_row:
        exclude_condition = "AND aok.name != %s"
        params.append(exclude_row)

    # Three separate queries for clarity and correctness
    totals: dict[str, float] = {}

    for h_col, a_col in [
        ("hammadde", "adet"),
        ("hammadde_2", "adet_2"),
        ("hammadde_3", "adet_3"),
    ]:
        rows = frappe.db.sql(
            f"""
            SELECT aok.{h_col} AS item_code, SUM(aok.{a_col}) AS total
            FROM `tabCalisma Karti Alt Operasyon Kayitlari` aok
            JOIN `tabCalisma Karti` ck ON ck.name = aok.parent
            WHERE ck.custom_work_order = %s
              AND IFNULL(aok.{h_col}, '') != ''
              AND IFNULL(aok.quality_inspection_status, '') != 'Reddedildi'
              {exclude_condition}
            GROUP BY aok.{h_col}
            """,
            tuple(params),
            as_dict=True,
        )
        for r in rows:
            totals[r.item_code] = totals.get(r.item_code, 0) + flt(r.total)

    return totals


def _get_wo_scrap_totals(work_order: str) -> dict[str, float]:
    """Sum scrap quantities per item from submitted Stock Entries linked to this work order.

    Considers Stock Entry types: 'Scrap for Manufacturing' and 'Material Issue'.
    """
    rows = frappe.db.sql(
        """
        SELECT sed.item_code, SUM(sed.qty) AS total
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.work_order = %s
          AND se.docstatus = 1
          AND se.stock_entry_type IN ('Scrap for Manufacturing', 'Material Issue')
        GROUP BY sed.item_code
        """,
        (work_order,),
        as_dict=True,
    )
    return {r.item_code: flt(r.total) for r in rows}


def _assert_within_wo_limits(
    calisma_karti: str,
    new_items: list[tuple[str, float]],
    exclude_row: str = None,
):
    """Validate that new consumption does not exceed Work Order limits.

    Args:
        calisma_karti: Calisma Karti name.
        new_items: List of (item_code, consumption_qty) for the new/updated row.
        exclude_row: Row name to exclude from existing totals (update scenario).
    """
    if not _is_coklu_hammadde(calisma_karti):
        return

    ck_data = frappe.db.get_value(
        "Calisma Karti", calisma_karti, ["custom_work_order", "operasyon"], as_dict=True
    )
    if not ck_data or not ck_data.custom_work_order or not ck_data.operasyon:
        return

    work_order = ck_data.custom_work_order
    
    tuketim_limiti_aktif = frappe.db.get_value(
        "KTA Calisma Karti Operasyonlari", ck_data.operasyon, "tuketim_limiti_aktif"
    )
    
    if not tuketim_limiti_aktif:
        return

    required_map = _get_wo_required_qty_map(work_order)
    if not required_map:
        return

    existing = _get_existing_consumption(work_order, exclude_row)
    scrap_totals = _get_wo_scrap_totals(work_order)

    # Aynı operasyon içerisinde (örn. sağ ve sol terminal) aynı hammadde seçilirse toplamını almalıyız.
    aggregated_new_items = {}
    for item_code, new_qty in new_items:
        if not item_code or flt(new_qty) == 0:
            continue
        aggregated_new_items[item_code] = aggregated_new_items.get(item_code, 0) + flt(new_qty)

    for item_code, total_new_qty in aggregated_new_items.items():
        wo_limit = required_map.get(item_code)
        if wo_limit is None:
            continue

        scrap_allowance = flt(scrap_totals.get(item_code, 0))
        allowed = wo_limit + scrap_allowance
        current = flt(existing.get(item_code, 0))
        projected = current + total_new_qty

        if flt(projected, 3) > flt(allowed, 3):
            scrap_line = ""
            if scrap_allowance > 0:
                scrap_line = _(
                    "<li><b>Fire Toleransı:</b> +{0}</li>"
                ).format(frappe.format_value(scrap_allowance, {"fieldtype": "Float"}))

            msg = _(
                "<b>{0}</b> hammaddesi için iş emrindeki tüketim limiti aşılıyor!<br><br>"
                "<ul>"
                "<li><b>İş Emri Miktarı:</b> {1}</li>"
                "{2}"
                "<li><b>Toplam İzin:</b> {3}</li>"
                "<li><b>Mevcut Tüketim:</b> {4}</li>"
                "<li><b>Yeni Eklenen:</b> {5}</li>"
                "<li><b>Oluşacak Toplam:</b> <span style='color:red;'>{6}</span></li>"
                "</ul>"
                "Lütfen girdiğiniz işlem adedini kontrol edin."
            ).format(
                item_code,
                frappe.format_value(wo_limit, {"fieldtype": "Float"}),
                scrap_line,
                frappe.format_value(allowed, {"fieldtype": "Float"}),
                frappe.format_value(current, {"fieldtype": "Float"}),
                frappe.format_value(total_new_qty, {"fieldtype": "Float"}),
                frappe.format_value(projected, {"fieldtype": "Float"}),
            )
            frappe.throw(msg, title=_("Tüketim Limiti Aşıldı"), exc=frappe.ValidationError)

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
    satir_no: str = None,
):
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    
    if hammadde: _assert_hammadde_allowed(calisma_karti, hammadde, alt_operasyon)
    if hammadde_2: _assert_hammadde_allowed(calisma_karti, hammadde_2, alt_operasyon)
    if hammadde_3: _assert_hammadde_allowed(calisma_karti, hammadde_3, alt_operasyon)

    # Tek Taraf Validation
    ao_doc = frappe.get_cached_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon)
    op_tipi = ao_doc.get("operasyon_tipi")
    
    if op_tipi == "Tek Taraf":
        if not hammadde_2 and not hammadde_3:
            frappe.throw(_("Tek Taraflı operasyonda Sol veya Sağ uca mutlaka bir terminal seçilmelidir."))
        if hammadde_2 and hammadde_3:
            frappe.throw(_("Tek Taraflı operasyonda her iki uca birden terminal seçilemez."))
        if hammadde_2 and float(boyut_2_mm or 0) > 0:
            frappe.throw(_("Sol uca terminal seçildiğinde Sol Sıyırma (mm) girilemez."))
        if hammadde_3 and float(boyut_3_mm or 0) > 0:
            frappe.throw(_("Sağ uca terminal seçildiğinde Sağ Sıyırma (mm) girilemez."))
    elif op_tipi == "Çift Taraf":
        if not hammadde_2 or not hammadde_3:
            frappe.throw(_("Çift Taraflı operasyonlarda hem Sol hem de Sağ uca terminal seçilmesi zorunludur."))
            
    if hammadde_2:
        islem_adedi_2 = islem_adedi_1
    if hammadde_3:
        islem_adedi_3 = islem_adedi_1

    adet_1, uom_1 = _calculate_tuketim(hammadde, boyut_1_mm, islem_adedi_1)
    adet_2, uom_2 = _calculate_tuketim(hammadde_2, boyut_2_mm, islem_adedi_2)
    adet_3, uom_3 = _calculate_tuketim(hammadde_3, boyut_3_mm, islem_adedi_3)

    _assert_within_wo_limits(
        calisma_karti,
        [(hammadde, adet_1), (hammadde_2, adet_2), (hammadde_3, adet_3)],
    )

    new_ao_row = doc.append(
        "alt_operasyon_kayitlari",
        {
            "alt_operasyon": alt_operasyon,
            "title": ao_doc.title,
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
            "satir_no": satir_no,
        },
    )
    
    # Otomatik Krimp Formu Ekleme
    new_krimp = None
    op_meta = frappe.db.get_value(
        "KTA Calisma Karti Operasyonlari", doc.operasyon,
        ["has_krimp", "alt_operasyon_bazli_kalite"], as_dict=True
    )

    if op_meta and op_meta.get("has_krimp") and op_meta.get("alt_operasyon_bazli_kalite"):
        # Zeki Logic: Gelen verilere göre T1 ve T2'yi belirle (Sabit Eşleştirme)
        # T1 her zaman Sol Uç, T2 her zaman Sağ Uç
        sol_kontak = (hammadde_2 or "").strip()
        sag_kontak = (hammadde_3 or "").strip()
        sol_siyirma = float(boyut_2_mm or 0)
        sag_siyirma = float(boyut_3_mm or 0)

        krimp_kontak_1 = sol_kontak
        siyirma_1 = sol_siyirma
        krimp_kontak_2 = sag_kontak
        siyirma_2 = sag_siyirma
        
        # Sağ uçta (T2) terminal veya sıyırma varsa, veya operasyon tipi Çift Taraf ise T2 alanlarını aç
        is_cift_tarafli = 1 if (sag_kontak or sag_siyirma > 0 or ao_doc.get("operasyon_tipi") == "Çift Taraf") else 0
            
        new_krimp = doc.append(
            "krimp_olcumleri",
            {
                "kablo_no": hammadde or "",
                "hedef_kablo_boyu": float(boyut_1_mm or 0),
                "kontak_no": krimp_kontak_1,
                "siyirma_boyu": siyirma_1,
                "is_cift_tarafli": is_cift_tarafli,
                "yon_2_kontak_no": krimp_kontak_2,
                "yon_2_siyirma_boyu": siyirma_2,
                "olcum_tarihi": frappe.utils.now_datetime(),
                "operator": require_my_employee(), # Default operator
            }
        )

    doc.flags.ignore_validate_update_after_submit = True
    doc.flags.ignore_links = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    if new_krimp and getattr(new_krimp, "name", None) and new_ao_row.name:
        frappe.db.set_value("Calisma Karti Krimp Olcumleri", new_krimp.name, "alt_operasyon_kaydi", new_ao_row.name)
        frappe.db.commit()
    
    from erpnextkta.kta_calisma_karti.api_impl.qc import _update_parent_qc_status_from_alt_ops
    doc.reload()
    _update_parent_qc_status_from_alt_ops(doc)
    
    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:add")
    return new_ao_row.name


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
        return []

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_alt_operasyon_kayitlari(doctype, txt, searchfield, start, page_len, filters):
    calisma_karti = (filters or {}).get("calisma_karti")
    if not calisma_karti:
        return []

    txt = (txt or "").strip()
    like = f"%{txt}%"
    
    return frappe.db.sql(
        f"""
        SELECT name, alt_operasyon
        FROM `tabCalisma Karti Alt Operasyon Kayitlari`
        WHERE parent = %s
          AND (name LIKE %s OR alt_operasyon LIKE %s)
        ORDER BY idx ASC
        LIMIT %s, %s
        """,
        (calisma_karti, like, like, int(start), int(page_len))
    )

def _assert_qc_unlocked(doc, row):
    """Check if the alt operasyon row is QC-locked.
    
    Rules:
    - Only applies when alt_operasyon_bazli_kalite is active on the operation
    - Row is locked when quality_inspection_status == "Onaylandı" AND quality_inspection is set
    - QC-allowed roles can always bypass (but will be warned about linked QI in frontend)
    - Normal users are blocked with a descriptive error message
    """
    op_has_qc = frappe.db.get_value(
        "KTA Calisma Karti Operasyonlari", doc.operasyon, 
        "alt_operasyon_bazli_kalite"
    )
    if not op_has_qc:
        return

    qi_status = (row.quality_inspection_status or "").strip()
    qi_name = (row.quality_inspection or "").strip()

    if qi_status != "Onaylandı" or not qi_name:
        return

    if has_qc_role():
        return

    frappe.throw(
        _("Bu alt operasyon kaydı kalite tarafından onaylanmıştır ({0}). "
          "Değişiklik için kalite birimini bilgilendirin.").format(qi_name)
    )

def _cancel_linked_quality_inspection(qi_name: str):
    """Cancel and delete the linked Quality Inspection document."""
    if not frappe.db.exists("Quality Inspection", qi_name):
        return

    qi = frappe.get_doc("Quality Inspection", qi_name)

    if qi.docstatus == 1:
        qi.cancel()
        frappe.db.commit()

    frappe.delete_doc("Quality Inspection", qi_name, force=True, ignore_permissions=True)
    frappe.db.commit()

@frappe.whitelist()
def update_alt_operasyon_kaydi(
    calisma_karti: str,
    row_id: str,
    alt_operasyon: str,
    hammadde: str = None, boyut_1_mm: float = 0, islem_adedi_1: float = 0,
    hammadde_2: str = None, boyut_2_mm: float = 0, islem_adedi_2: float = 0,
    hammadde_3: str = None, boyut_3_mm: float = 0, islem_adedi_3: float = 0,
    note: str = None,
    satir_no: str = None,
):
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    
    row = doc.get("alt_operasyon_kayitlari", {"name": row_id})
    if row:
        _assert_qc_unlocked(doc, row[0])
    
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

    _assert_within_wo_limits(
        calisma_karti,
        [(hammadde, adet_1), (hammadde_2, adet_2), (hammadde_3, adet_3)],
        exclude_row=row_id,
    )

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
    row.satir_no = satir_no

    ao_doc = frappe.get_cached_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon)
    
    krimp_row_id = next((r.name for r in doc.get("krimp_olcumleri") if r.alt_operasyon_kaydi == row_id), None)
    if krimp_row_id:
        krimp_row = doc.get("krimp_olcumleri", {"name": krimp_row_id})[0]
        krimp_row.kablo_no = hammadde or ""
        krimp_row.hedef_kablo_boyu = float(boyut_1_mm or 0)
        
        # Zeki Logic: Gelen verilere göre T1 ve T2'yi belirle (Sabit Eşleştirme)
        # T1 her zaman Sol Uç, T2 her zaman Sağ Uç
        sol_kontak = (hammadde_2 or "").strip()
        sag_kontak = (hammadde_3 or "").strip()
        sol_siyirma = float(boyut_2_mm or 0)
        sag_siyirma = float(boyut_3_mm or 0)

        krimp_kontak_1 = sol_kontak
        siyirma_1 = sol_siyirma
        krimp_kontak_2 = sag_kontak
        siyirma_2 = sag_siyirma
        
        is_cift_tarafli = 1 if (sag_kontak or sag_siyirma > 0 or ao_doc.get("operasyon_tipi") == "Çift Taraf") else 0
            
        krimp_row.kontak_no = krimp_kontak_1
        krimp_row.siyirma_boyu = siyirma_1
        krimp_row.is_cift_tarafli = is_cift_tarafli
        krimp_row.yon_2_kontak_no = krimp_kontak_2
        krimp_row.yon_2_siyirma_boyu = siyirma_2

    doc.flags.ignore_validate_update_after_submit = True
    doc.flags.ignore_links = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    from erpnextkta.kta_calisma_karti.api_impl.qc import _update_parent_qc_status_from_alt_ops
    doc.reload()
    _update_parent_qc_status_from_alt_ops(doc)

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

    row = to_remove[0]
    _assert_qc_unlocked(doc, row)

    qi_name = (row.quality_inspection or "").strip()
    if qi_name and has_qc_role():
        _cancel_linked_quality_inspection(qi_name)

    for r in to_remove:
        doc.remove(r)

    krimp_to_remove = [r for r in doc.get("krimp_olcumleri", []) if r.alt_operasyon_kaydi == row_id]
    for r in krimp_to_remove:
        doc.remove(r)

    doc.flags.ignore_validate_update_after_submit = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    from erpnextkta.kta_calisma_karti.api_impl.qc import _update_parent_qc_status_from_alt_ops
    doc.reload()
    _update_parent_qc_status_from_alt_ops(doc)

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


@frappe.whitelist()
def get_item_uom(item_code: str) -> str:
    if not item_code:
        return ""
    return frappe.db.get_value("Item", item_code, "stock_uom") or ""


@frappe.whitelist()
def is_kut_kablo_operation(operasyon_name: str) -> bool:
    allowed = frappe.db.get_all(
        "KTA Sub Operation Allowed Material Groups",
        filters={
            "parent": operasyon_name,
            "parenttype": "KTA Calisma Karti Alt Operasyonlari"
        },
        fields=["item_group"],
        ignore_permissions=True
    )
    if not allowed:
        return False
    has_terminal = any("terminal" in (a.item_group or "").lower() for a in allowed)
    return not has_terminal
