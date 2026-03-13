# English comments as requested

from __future__ import annotations

import frappe
from frappe import _
from collections import defaultdict

from ._helpers import (
    first_child_table,
    is_system_manager,
    is_quality_user,
    require_my_employee,
)

def _attach_customer_groups(rows):
    """Attach customer_group(s) for each row (based on urun_kodu). Always adds keys."""
    item_codes = sorted({r.get("urun_kodu") for r in rows if r.get("urun_kodu")})
    groups_by_item = defaultdict(list)

    if item_codes:
        details = frappe.get_all(
            "Item Customer Detail",
            filters={
                "parenttype": "Item",
                "parent": ["in", item_codes],
            },
            fields=["parent", "customer_group"],
        )
        for d in details:
            cg = d.get("customer_group")
            if cg and cg not in groups_by_item[d["parent"]]:
                groups_by_item[d["parent"]].append(cg)

    for r in rows:
        code = r.get("urun_kodu")
        cgs = groups_by_item.get(code, [])
        r["customer_groups"] = cgs                  # her zaman var: list
        r["customer_group"] = cgs[0] if cgs else None  # her zaman var: str|None

    return rows

def _attach_operasyon_label(rows):
    """Replace Calisma Karti.operasyon (child row ID) with its calisma_karti_op label."""
    op_ids = sorted({r.get("operasyon") for r in rows if r.get("operasyon")})
    if not op_ids:
        return rows

    ops = frappe.get_all(
        "KTA Calisma Karti Operasyonlari",
        filters={"name": ["in", op_ids]},
        fields=["name", "calisma_karti_op"],
        limit_page_length=len(op_ids),
    )
    label_by_id = {o["name"]: o.get("calisma_karti_op") for o in ops}

    for r in rows:
        op_id = r.get("operasyon")
        if op_id:
            # If missing, keep original id to avoid breaking UI
            r["operasyon"] = label_by_id.get(op_id) or op_id

    return rows

def _attach_alt_operasyon_titles(rows):
    """Enrich alt_operasyon child table rows with title and sequence from master doctype."""
    if not rows:
        return rows

    names = sorted({r.get("alt_operasyon") for r in rows if r.get("alt_operasyon")})
    if not names:
        return rows

    masters = frappe.get_all(
        "KTA Calisma Karti Alt Operasyonlari",
        filters={"name": ["in", names]},
        fields=["name", "title", "sequence"],
        limit_page_length=len(names),
    )
    meta_by_name = {m["name"]: m for m in masters}

    for r in rows:
        master = meta_by_name.get(r.get("alt_operasyon"), {})
        r["alt_operasyon_title"] = master.get("title") or r.get("alt_operasyon")
        r["alt_operasyon_sequence"] = master.get("sequence") or 0

    return rows

@frappe.whitelist()
def get_my_calisma_kartlari(order_by=None, start=0, page_length=200, customer_group=None, durum=None, search_term=None, qc_filter=None):
    """Return assigned Calisma Karti rows for list UI (with customer_group info and filters)."""

    fields = [
        "name",
        "custom_work_order",
        "is_karti",
        "operasyon",
        "urun_kodu",
        "is_istasyonu",
        "operator",
        "durum",
        "baslangic_saati",
        "bitis_saati",
        "modified",
        "creation",
        "kalite_kontrol",
    ]

    allowed = {
        "modified_desc": "modified desc",
        "modified_asc": "modified asc",
        "creation_desc": "creation desc",
        "creation_asc": "creation asc",
        "name_asc": "name asc",
        "name_desc": "name desc",
    }
    order_by = allowed.get(order_by or "modified_desc", "modified desc")
    start = int(start or 0)
    page_length = int(page_length or 200)

    # Build filters dynamically
    db_filters = {}
    
    if durum:
        db_filters["durum"] = durum
        
    if search_term:
        search_term = f"%{search_term}%"
        # Since frappe.get_all or_filters are tricky with dicts, we use SQL where conditions if needed, 
        # but typical ERPNext allows lists in filters for IN, or string for LIKE in specific fields. 
        # A safer cross-field search requires custom SQL or specific fields.
        # We'll map search_term to name or custom_work_order or is_karti
        db_filters["name"] = ["like", search_term]
        
    if not (is_system_manager() or is_quality_user()):
        db_filters["operator"] = require_my_employee()
        
    if qc_filter:
        db_filters["kalite_kontrol"] = qc_filter

    rows = frappe.get_all(
        "Calisma Karti",
        filters=db_filters,
        fields=fields,
        order_by=order_by,
        limit_start=start,
        limit_page_length=page_length,
    )

    # If search_term is provided, frappe's dictionary filters perform AND logic.
    # For a true OR search across name, work_order, item_code, it's better to fetch and filter in app
    # OR write Frappe DB OR filters.
    # To be safe and keep it simple: if search_term is given, we fetch broader and filter in memory if DB fails us,
    # OR we use frappe.get_list with `or_filters`.
    
    if search_term:
        # Re-fetch with proper OR filters if search_term is present to cover all bases
        or_filters = {
            "name": ["like", search_term],
            "custom_work_order": ["like", search_term],
            "is_karti": ["like", search_term],
            "urun_kodu": ["like", search_term]
        }
        
        # Remove the 'name' strict filter from db_filters used previously
        if "name" in db_filters:
            del db_filters["name"]
            
        rows = frappe.get_all(
            "Calisma Karti",
            filters=db_filters,
            or_filters=or_filters,
            fields=fields,
            order_by=order_by,
            limit_start=start,
            limit_page_length=page_length,
        )

    rows = _attach_customer_groups(rows)
    rows = _attach_operasyon_label(rows)
    
    if customer_group:
        rows = [r for r in rows if r.get("customer_group") == customer_group or customer_group in (r.get("customer_groups") or [])]
        
    return rows

@frappe.whitelist()
def get_calisma_karti_detail(name: str):
    """Return detail payload for Vue UI.

    - If System Manager: allow any card
    - Else: only allow if operator == current user's Employee
    """

    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    if not (is_system_manager() or is_quality_user()):
        emp = require_my_employee()
        if doc.operator != emp:
            frappe.throw(_("Bu çalışma kartını görüntüleme yetkiniz yok."), frappe.PermissionError)

    hurdalar = first_child_table(doc, ["hurdalar", "hurda", "calisma_karti_hurda"])
    duruslar = first_child_table(doc, ["duruslar", "durus", "operasyon_duruslari"])
    idc_olcumleri = first_child_table(doc, ["idc_olcumleri", "idc_olcumleri", "calisma_karti_idc_olcumleri"])
    barkod_kayitlari = first_child_table(doc, ["barkod_kayitlari", "barkod_kayitlari", "calisma_karti_barkod_kayitlari"])
    alt_operasyon_kayitlari = first_child_table(doc, ["alt_operasyon_kayitlari", "alt_operasyon", "calisma_karti_alt_operasyon_kayitlari"])

    # Enrich alt_operasyon rows with title and sequence from the master doctype
    _attach_alt_operasyon_titles(alt_operasyon_kayitlari)

    return {
        "name": doc.name,
        "custom_work_order": doc.custom_work_order,
        "is_karti": doc.is_karti,
        "operasyon": doc.operasyon,
        "urun_kodu": doc.urun_kodu,
        "is_istasyonu": doc.is_istasyonu,
        "operator": doc.operator,
        "durum": doc.durum,
        "baslangic_saati": doc.baslangic_saati,
        "bitis_saati": doc.bitis_saati,
        "hurdalar": hurdalar,
        "duruslar": duruslar,
        "idc_olcumleri": idc_olcumleri,
        "barkod_kayitlari": barkod_kayitlari,
        "alt_operasyon_kayitlari": alt_operasyon_kayitlari,
        "tamamlanan_miktar": float(doc.tamamlanan_miktar or 0),
        "kalite_kontrol": doc.kalite_kontrol,
        "quality_inspection": doc.quality_inspection or None,
        "creation": doc.creation,
        "max_kart_suresi_dk": frappe.db.get_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk") or 430,
        "kart_uyari_suresi_dk": frappe.db.get_single_value("KTA Calisma Karti Settings", "kart_uyari_suresi_dk") or 400,
    }

def _assert_can_write_on_doc(doc):
    if is_system_manager() or is_quality_user():
        return
    emp = require_my_employee()
    if doc.operator != emp:
        frappe.throw(_("Bu İşlem için yetkiniz yok."), frappe.PermissionError)

def _handle_baslat(doc, now):
    durum = doc.get_durum()
    if durum == "durusta":
        # Handle as continuation if "Baslat" sent for a paused card
        _handle_devam_et(doc, now)
        return
        
    if durum != "hazir":
        frappe.throw("Sadece Hazır durumundaki işlemler başlatılabilir.")
    
    doc.baslangic_saati = now
    
    # Auto-pause other active cards for this operator
    _auto_pause_other_active_cards(doc, now)

def _handle_devam_et(doc, now):
    if doc.get_durum() != "durusta":
        frappe.throw("Sadece durdurulmuş bir işlem devam ettirilebilir.")
    
    if doc.duruslar:
        last_row = doc.duruslar[-1]
        if not last_row.durus_bitis:
            last_row.durus_bitis = now
            from frappe.utils import get_datetime
            start_dt = get_datetime(last_row.durus_baslangic)
            end_dt = get_datetime(last_row.durus_bitis)
            last_row.durus_suresi = (end_dt - start_dt).total_seconds() / 60
            
    _auto_pause_other_active_cards(doc, now)

def _handle_durus(doc, now, durus_nedeni, aciklama):
    durum = doc.get_durum()
    if durum == "bitmis":
        frappe.throw("Bitmiş bir işlemde duruş yapılamaz.")
    if durum == "hazir":
        frappe.throw("Başlamamış bir işlemde duruş yapılamaz.")
    if doc.aktif_durus_var_mi():
        frappe.throw("Bu işlem zaten durdurulmuş.")

    if not durus_nedeni:
        frappe.throw("Duruşa geçmek için Duruş Nedeni belirtilmelidir.")
        
    doc.append(
        "duruslar",
        {
            "durus_nedeni": durus_nedeni,
            "durus_baslangic": now,
            "aciklama": aciklama,
        },
    )

def _handle_bitis(doc, now, aciklama, qty):
    durum = doc.get_durum()
    if durum == "hazir":
        frappe.throw("Başlamamış işlem bitirilemez.")
    if durum == "bitmis":
        frappe.throw("Bu kart zaten bitmiş.")

    # 1. Close active durus if any
    if doc.aktif_durus_var_mi():
        last_row = doc.duruslar[-1]
        last_row.durus_bitis = now
        from frappe.utils import get_datetime
        start_dt = get_datetime(last_row.durus_baslangic)
        end_dt = get_datetime(last_row.durus_bitis)
        last_row.durus_suresi = (end_dt - start_dt).total_seconds() / 60

    # 2. Add requested amount
    doc.tamamlanan_miktar = (doc.tamamlanan_miktar or 0.0) + qty

    # 3. Check amount constraint
    total_done = float(doc.tamamlanan_miktar or 0)
    if total_done <= 0:
        # Check operation strictness config
        op_doc = frappe.db.get_value("KTA Calisma Karti Operasyonlari", doc.operasyon, "miktar_zorunlu_mu")
        miktar_zorunlu_mu = op_doc if op_doc is not None else 1

        if miktar_zorunlu_mu:
            frappe.throw("Bu operasyon için tamamlanan miktar (üretim adedi) bildirilmesi zorunludur.")
        else:
            if not doc.get("alt_operasyon_kayitlari"):
                frappe.throw("Üretim adedi girilmeden işlemin bitirilebilmesi için en az bir alt operasyon kaydı bulunmalıdır.")

    doc.bitis_saati = now

    # Optional final note/durus reason
    if aciklama and len(doc.duruslar) > 0:
        doc.duruslar[-1].aciklama = aciklama

    # 4. Submit linked Quality Inspection (if draft)
    _submit_linked_quality_inspection(doc)


def _submit_linked_quality_inspection(doc):
    """Submit the Quality Inspection linked to this Calisma Karti if it is still a Draft.

    Called when the card is finished (Bitis). Safe — any error is logged but does not
    block the card from being finished.
    """
    qi_name = (getattr(doc, "quality_inspection", None) or "").strip()
    if not qi_name:
        return

    try:
        qi_docstatus = frappe.db.get_value("Quality Inspection", qi_name, "docstatus")
        if qi_docstatus == 0:  # Draft → submit
            qi_doc = frappe.get_doc("Quality Inspection", qi_name)
            qi_doc.submit()
            frappe.logger().info(
                f"[kta] Quality Inspection {qi_name} submitted on Bitis of {doc.name}"
            )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"[kta] QI submit failed for {qi_name} (Calisma Karti: {doc.name})"
        )
def _auto_pause_other_active_cards(hedef_doc, now_dt):
    if not hedef_doc.operator:
        return
        
    kartlar = frappe.get_all(
        "Calisma Karti",
        filters={
            "operator": hedef_doc.operator,
            "name": ["!=", hedef_doc.name],
            "docstatus": 1,
            "bitis_saati": ["is", "not set"]
        },
        fields=["name"]
    )
    
    for k in kartlar:
        eski_doc = frappe.get_doc("Calisma Karti", k.name)
        if eski_doc.get_durum() == "calisiyor":
            eski_doc.append("duruslar", {
                "durus_nedeni": "Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı.",
                "durus_baslangic": now_dt,
            })
            eski_doc.update_durum()
            eski_doc.flags.ignore_validate_update_after_submit = True
            eski_doc.save(ignore_permissions=True)

            # Force-update read-only status fields on submitted document
            frappe.db.set_value("Calisma Karti", eski_doc.name, {
                "durum": eski_doc.durum,
                "toplam_sure": eski_doc.toplam_sure,
                "toplam_durus": eski_doc.toplam_durus,
                "net_calisma_suresi": eski_doc.net_calisma_suresi
            }, update_modified=False)
            from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed
            publish_calisma_karti_changed(eski_doc.name, reason="auto_pause")

@frappe.whitelist()
def islem_yap(docname, islem_tipi, durus_nedeni=None, aciklama=None, tamamlanan_miktar=None):
    doc = frappe.get_doc("Calisma Karti", docname)

    doc.check_permission("write")
    _assert_can_write_on_doc(doc)

    doc.reload()

    if doc.docstatus != 1:
        frappe.throw(_("İşlem yapmak için kartın 'Onaylı' (Submit edilmiş) olması gerekir."))

    durum = doc.get_durum()
    if (doc.kalite_kontrol or '').strip() == 'Reddedildi':
        frappe.throw('Reddedilmiş çalışma kartında işlem yapılamaz.')

    from frappe.utils import now_datetime
    now = now_datetime()
    qty = 0.0
    if tamamlanan_miktar is not None and str(tamamlanan_miktar).strip() != "":
        try:
            qty = float(tamamlanan_miktar)
        except Exception:
            frappe.throw("Tamamlanan miktar sayısal olmalıdır.")
        if qty < 0:
            frappe.throw("Tamamlanan miktar negatif olamaz.")

    if islem_tipi == "Baslat":
        _handle_baslat(doc, now)
    elif islem_tipi == "Durus":
        _handle_durus(doc, now, durus_nedeni, aciklama)
        if qty > 0:
            doc.tamamlanan_miktar = (doc.tamamlanan_miktar or 0.0) + qty
    elif islem_tipi == "DevamEt":
        _handle_devam_et(doc, now)
    elif islem_tipi == "Bitis":
        _handle_bitis(doc, now, aciklama, qty)
    else:
        frappe.throw("Geçersiz işlem tipi.")

    doc.update_durum()

    doc.flags.ignore_validate_update_after_submit = True
    doc.save(ignore_permissions=True)
    
    # Force-update read-only fields on submitted document using db.set_value.
    # Standard doc.save() often ignores read-only fields even if allow_on_submit is 1.
    frappe.db.set_value("Calisma Karti", doc.name, {
        "baslangic_saati": doc.baslangic_saati,
        "bitis_saati": doc.bitis_saati,
        "durum": doc.durum,
        "toplam_sure": doc.toplam_sure,
        "toplam_durus": doc.toplam_durus,
        "net_calisma_suresi": doc.net_calisma_suresi
    }, update_modified=False)
    
    frappe.db.commit()

    from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed
    publish_calisma_karti_changed(docname, reason=f"islem_yap:{islem_tipi}")

    return {
        "status": "success",
        "docname": docname,
        "islem_tipi": islem_tipi,
        "durum": doc.get_durum(),
        "tamamlanan_miktar": float(doc.tamamlanan_miktar or 0),
    }
