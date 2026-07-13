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

    totals: dict[str, float] = {}

    rows = frappe.db.sql(
        f"""
        SELECT 
            hk.hammadde AS item_code, 
            hk.boyut_mm, 
            hk.islem_adedi
        FROM `tabKTA Calisma Karti Hammadde Kayitlari` hk
        JOIN `tabCalisma Karti` ck ON ck.name = hk.parent
        JOIN `tabCalisma Karti Alt Operasyon Kayitlari` aok ON aok.name = hk.alt_operasyon_ref
        WHERE ck.custom_work_order = %s
          AND IFNULL(hk.hammadde, '') != ''
          AND IFNULL(aok.quality_inspection_status, '') != 'Reddedildi'
          {exclude_condition}
        """,
        tuple(params),
        as_dict=True,
    )

    for r in rows:
        adet, _ = _calculate_tuketim(r.item_code, r.boyut_mm, r.islem_adedi)
        totals[r.item_code] = totals.get(r.item_code, 0) + float(adet or 0)

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
            frappe.throw(msg, title=_("Tüketim Limiti Aşıldı"))


def _assert_within_wip_limits(
    new_items: list[dict],
    source_wip_ids: str,
    exclude_row: str = None
):
    import json
    if not source_wip_ids:
        return

    try:
        wip_ids = json.loads(source_wip_ids)
    except Exception:
        wip_ids = [x.strip() for x in source_wip_ids.split(",") if x.strip()]

    if not wip_ids:
        return

    from frappe.utils import flt

    yon_capacity = {"Sol": 0.0, "Sağ": 0.0, "Orta": 0.0}
    yon_consumed = {"Sol": 0.0, "Sağ": 0.0, "Orta": 0.0}

    for wip_id in wip_ids:
        if frappe.db.exists("KTA Sanal Yarimamul", wip_id):
            wip = frappe.get_doc("KTA Sanal Yarimamul", wip_id)
            if wip.graph_state:
                graph = json.loads(wip.graph_state)
                for node in graph.get("nodes", []):
                    # Kapasite tespiti
                    if node.get("type") == "Uç (T1)":
                        yon = "Sol"
                    elif node.get("type") == "Uç (T2)":
                        yon = "Sağ"
                    elif node.get("type") == "Kablo Merkezi":
                        yon = "Orta"
                    elif "Birleşim" in str(node.get("type")):
                        yon = "Birleşim"
                    else:
                        yon = None
                    
                    if yon:
                        for m in node.get("materials", []):
                            yon_capacity[yon] = yon_capacity.get(yon, 0.0) + flt(m.get("islem_adedi"))

                    # Graph üzerinde tanımlı olan node'lardan tüketimleri sildik, çünkü 
                    # Tip 3 gibi operasyonlar node eklemez, yeni WIP yaratır.
                    # Gerçek tüketimi veritabanından, bu WIP'i kullanan kayıtlardan çekeceğiz.

    # Veritabanından mevcut tüketimleri çekelim
    used_records_dict = {}
    for wid in wip_ids:
        recs = frappe.db.get_all(
            "KTA Calisma Karti Hammadde Kayitlari",
            filters={"source_wip_ids": ["like", f"%{wid}%"]},
            fields=["name", "islem_adedi", "yon", "source_wip_ids", "alt_operasyon_ref"]
        )
        for r in recs:
            used_records_dict[r.name] = r

    # Tam eşleşenleri filtrele (virgülle ayrılmış olabileceği için)
    for r in used_records_dict.values():
        if r.source_wip_ids:
            s_wips = [x.strip() for x in r.source_wip_ids.split(",")]
            if any(w in s_wips for w in wip_ids):
                # Eğer bu satır hariç tutulacaksa atla (Örn: Düzenleme modu)
                if exclude_row and r.alt_operasyon_ref == exclude_row:
                    continue
                y = r.yon or "Orta"
                if y in yon_consumed:
                    yon_consumed[y] += flt(r.islem_adedi)

    # Yeni tüketim tespiti
    new_consumed = {"Sol": 0.0, "Sağ": 0.0, "Orta": 0.0}
    for item in new_items:
        y = item.get("yon") or "Orta"
        if y in new_consumed:
            new_consumed[y] += flt(item.get("islem_adedi") or 0)

    # Gerçek kapasite
    if yon_capacity.get("Birleşim", 0) > 0:
        base_capacity = yon_capacity["Birleşim"]
    else:
        base_capacity = max([v for k, v in yon_capacity.items() if k != "Birleşim"]) if any(v for k, v in yon_capacity.items() if k != "Birleşim") else 0

    # Doğrulama
    for y in ["Sol", "Sağ", "Orta"]:
        projected = yon_consumed[y] + new_consumed[y]
        if base_capacity > 0 and projected > base_capacity:
            frappe.throw(
                frappe._(
                    "<b>WIP Miktar Limiti Aşıldı!</b><br>"
                    "Kablo üretim kapasitesi: {0}<br>"
                    "{1} yönündeki önceki tüketimler: {2}<br>"
                    "Yeni girilen: {3}<br>"
                    "Toplam ulaşılacak miktar: <span style='color:red;'>{4}</span>"
                ).format(base_capacity, y, yon_consumed[y], new_consumed[y], projected),
                title=frappe._("WIP Kapasite Hatası")
            )

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

def distribute_wip_consumption(wip_ids_str, requested_adet, exclude_row=None):
    """
    Given a comma-separated string of WIP IDs and a total requested adet,
    distributes the requested amount across the WIPs based on their remaining capacity.
    Returns a list of dicts: [{"wip_id": "WIP-1", "islem_adedi": 500}, ...]
    """
    if not wip_ids_str:
        return []
        
    wips = [x.strip() for x in wip_ids_str.split(",") if x.strip()]
    if len(wips) == 1:
        return [{"wip_id": wips[0], "islem_adedi": requested_adet}]
        
    # We must calculate remaining capacity for each WIP.
    # We can use the existing `get_work_order_pool` logic, but for performance, 
    # we'll do a simplified capacity check here.
    distribution = []
    remaining_to_allocate = float(requested_adet)
    
    for wid in wips:
        if remaining_to_allocate <= 0:
            break
            
        wip = frappe.db.get_value("KTA Sanal Yarimamul", wid, ["name", "graph_state"], as_dict=1)
        if not wip or not wip.graph_state:
            continue
            
        import json
        g = json.loads(wip.graph_state)
        nodes = g.get("nodes", [])
        
        yon_capacity = {}
        for node in nodes:
            yon = None
            if node.get("type") == "Uç (T1)": yon = "Sol"
            elif node.get("type") == "Uç (T2)": yon = "Sağ"
            elif node.get("type") == "Kablo Merkezi": yon = "Orta"
            elif "Birleşim" in str(node.get("type")): yon = "Birleşim"
            
            if yon:
                for m in node.get("materials", []):
                    yon_capacity[yon] = yon_capacity.get(yon, 0.0) + float(m.get("islem_adedi") or 0)
                    
        if yon_capacity.get("Birleşim", 0) > 0:
            base_cap = yon_capacity["Birleşim"]
        else:
            base_cap = max([v for k, v in yon_capacity.items() if k != "Birleşim"]) if any(v for k, v in yon_capacity.items() if k != "Birleşim") else 0
            
        used_recs = frappe.db.get_all(
            "KTA Calisma Karti Hammadde Kayitlari",
            filters={"source_wip_ids": ["like", f"%{wid}%"]},
            fields=["islem_adedi", "yon", "source_wip_ids", "alt_operasyon_ref", "parent"]
        )
        def _ds(p):
            if not p: return 2
            v = frappe.db.get_value("Calisma Karti", p, "docstatus")
            return v if v is not None else 2
            
        valid_used_recs = []
        for r in used_recs:
            if r.get("alt_operasyon_ref"):
                ao_parent = frappe.db.get_value("Calisma Karti Alt Operasyon Kayitlari", r.get("alt_operasyon_ref"), "parent")
                if ao_parent != r.get("parent"):
                    continue
            if _ds(r.get("parent")) < 2:
                valid_used_recs.append(r)
        
        yon_consumed = {}
        for r in valid_used_recs:
            if r.get("source_wip_ids"):
                s_wips = [x.strip() for x in r.get("source_wip_ids").split(",")]
                if wid in s_wips:
                    if exclude_row and r.get("alt_operasyon_ref") == exclude_row:
                        continue
                    y = r.get("yon") or "Orta"
                    yon_consumed[y] = yon_consumed.get(y, 0.0) + float(r.get("islem_adedi") or 0)
                    
        max_cons = max(yon_consumed.values()) if any(yon_consumed.values()) else 0
        available_cap = base_cap - max_cons
        
        if available_cap <= 0:
            continue
            
        take = min(available_cap, remaining_to_allocate)
        distribution.append({"wip_id": wid, "islem_adedi": take})
        remaining_to_allocate -= take
        
    # If there's still remaining_to_allocate, we just put it on the first one (fallback)
    if remaining_to_allocate > 0 and wips:
        if distribution:
            distribution[0]["islem_adedi"] += remaining_to_allocate
        else:
            distribution.append({"wip_id": wips[0], "islem_adedi": remaining_to_allocate})
            
    return distribution


@frappe.whitelist()
def add_alt_operasyon_kaydi(
    calisma_karti: str,
    alt_operasyon: str,
    note: str = None,
    satir_no: str = None,
    hammadde_tuketimleri=None,
    source_wip_ids: str = None,
    **kwargs
):
    frappe.log_error(title="DEBUG: add_alt_operasyon_kaydi payload", message=frappe.as_json({"hammadde_tuketimleri": hammadde_tuketimleri, "source_wip_ids": source_wip_ids}))
    import json
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    
    if isinstance(hammadde_tuketimleri, str):
        hammadde_tuketimleri = json.loads(hammadde_tuketimleri)
    if not hammadde_tuketimleri:
        hammadde_tuketimleri = []

    ao_doc = frappe.get_cached_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon)
    
    # Calculate totals for limits
    items_to_check = []
    for t in hammadde_tuketimleri:
        adet, uom = _calculate_tuketim(t.get("hammadde"), t.get("boyut_mm"), t.get("islem_adedi"))
        dedup_key = (t.get("hammadde"), adet, t.get("source_wip_ids"))
        items_to_check.append(dedup_key)
        t["hesaplanan_adet"] = adet
        t["hesaplanan_uom"] = uom

    _assert_within_wo_limits(calisma_karti, items_to_check)

    new_ao_row = doc.append(
        "alt_operasyon_kayitlari",
        {
            "alt_operasyon": alt_operasyon,
            "title": ao_doc.title,
            "note": note,
            "satir_no": satir_no,
        },
    )
    
    new_wip_id = None
    if ao_doc.sanal_yarimamul_davranisi and not source_wip_ids:
        wip = frappe.get_doc({
            "doctype": "KTA Sanal Yarimamul",
            "is_emri": doc.custom_work_order,
            "calisma_karti": calisma_karti,
            "status": "Aktif",
            "is_graph_based": 1
        })
        wip.insert(ignore_permissions=True)
        new_wip_id = wip.name
    elif not source_wip_ids:
        new_wip_id = f"{calisma_karti}-{frappe.generate_hash(length=6)}"

    # Add hammadde tuketimleri
    new_ht_rows = []
    has_orta = any(t.get("yon") == "Orta" for t in hammadde_tuketimleri)
    for t in hammadde_tuketimleri:
        if t.get("hammadde") or (t.get("boyut_mm") and float(t.get("boyut_mm")) > 0) or t.get("source_wip_ids"):
            row_data = {
                "alt_operasyon_ref": new_ao_row.name,
                "hammadde": t.get("hammadde") or None,
                "boyut_mm": t.get("boyut_mm") or 0,
                "islem_adedi": t.get("islem_adedi") or 1,
                "uom": t.get("uom"),
                "yon": t.get("yon") or "Orta",
                "source_wip_ids": t.get("source_wip_ids"),
                "hedef_kavite": t.get("hedef_kavite")
            }
            if row_data["yon"] == "Orta":
                row_data["wip_id"] = new_wip_id
            
            raw_source = t.get("source_wip_ids")
            
            if raw_source and "," in raw_source:
                distributed = distribute_wip_consumption(raw_source, row_data["islem_adedi"])
                for d in distributed:
                    split_row = row_data.copy()
                    split_row["source_wip_ids"] = d["wip_id"]
                    split_row["islem_adedi"] = d["islem_adedi"]
                    ht_row = doc.append("hammadde_tuketimleri", split_row)
                    new_ht_rows.append(ht_row)
            else:
                row_data["source_wip_ids"] = raw_source
                ht_row = doc.append("hammadde_tuketimleri", row_data)
                new_ht_rows.append(ht_row)

    # For auto Krimp forms, try to extract terminals and cables
    kablo_no = ""
    boyut_1_mm = 0
    krimp_kontak_1 = ""
    siyirma_1 = 0
    krimp_kontak_2 = ""
    siyirma_2 = 0
    
    for t in hammadde_tuketimleri:
        h = t.get("hammadde")
        yon = t.get("yon")
        ig = frappe.db.get_value("Item", h, "item_group") or "" if h else ""
        
        # Kablo tespiti: Yön Orta ise direkt kablo kabul et, değilse item_group'tan tahmin et
        if (yon == "Orta" or (not yon and ("kablo" in ig.lower() or "cable" in ig.lower() or "wire" in ig.lower()))) and not kablo_no:
            kablo_no = h or ""
            boyut_1_mm = t.get("boyut_mm") or 0
            
        elif yon == "Sol":
            if h and not krimp_kontak_1 and ("terminal" in ig.lower() or "kontak" in ig.lower()):
                krimp_kontak_1 = h
            if not siyirma_1 and t.get("boyut_mm"):
                siyirma_1 = float(t.get("boyut_mm") or 0)
                
        elif yon == "Sağ":
            if h and not krimp_kontak_2 and ("terminal" in ig.lower() or "kontak" in ig.lower()):
                krimp_kontak_2 = h
            if not siyirma_2 and t.get("boyut_mm"):
                siyirma_2 = float(t.get("boyut_mm") or 0)
                
        # Eski veri (yon yoksa) Sol/Sağ terminal tahmini
        elif not yon and h and ("terminal" in ig.lower() or "kontak" in ig.lower()):
            if not krimp_kontak_1:
                krimp_kontak_1 = h
                siyirma_1 = float(t.get("boyut_mm") or 0)
            elif not krimp_kontak_2:
                krimp_kontak_2 = h
                siyirma_2 = float(t.get("boyut_mm") or 0)

    is_cift_tarafli = 1 if (krimp_kontak_2 or siyirma_2 > 0) else 0
        
    new_krimp = None
    op_meta = frappe.db.get_value("KTA Calisma Karti Operasyonlari", doc.operasyon, 
                                 ["miktar_zorunlu_mu", "has_krimp", "has_idc", "has_barkod", "has_enjeksiyon", "alt_operasyon_bazli_kalite", "yuzde_yuz_kalite_kontrol"], as_dict=1) or {}

    if op_meta and op_meta.get("has_krimp") and op_meta.get("alt_operasyon_bazli_kalite"):
        new_krimp = doc.append(
            "krimp_olcumleri",
            {
                "kablo_no": kablo_no,
                "hedef_kablo_boyu": float(boyut_1_mm or 0),
                "kontak_no": krimp_kontak_1,
                "siyirma_boyu": siyirma_1,
                "is_cift_tarafli": is_cift_tarafli,
                "yon_2_kontak_no": krimp_kontak_2,
                "yon_2_siyirma_boyu": siyirma_2,
                "olcum_tarihi": frappe.utils.now_datetime(),
                "operator": require_my_employee(),
            }
        )

    doc.flags.ignore_validate_update_after_submit = True
    doc.flags.ignore_links = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    if new_krimp and getattr(new_krimp, "name", None) and new_ao_row.name:
        frappe.db.set_value("Calisma Karti Krimp Olcumleri", new_krimp.name, "alt_operasyon_kaydi", new_ao_row.name)
        
    for r in new_ht_rows:
        if r.name and new_ao_row.name:
            frappe.db.set_value("KTA Calisma Karti Hammadde Kayitlari", r.name, "alt_operasyon_ref", new_ao_row.name)
            
    frappe.db.commit()
    
    # ----------------------------------------------------
    # GRAPH CORE ENGINE INTEGRATION (Executes immediately)
    # ----------------------------------------------------
    from erpnextkta.kta_calisma_karti.api_impl.wip_graph_engine import process_operation
    import json
    
    if ao_doc.sanal_yarimamul_davranisi:
        # Re-fetch the saved rows for this new_ao_row to pass to process_operation
        saved_hts = frappe.get_all("KTA Calisma Karti Hammadde Kayitlari", 
                                   filters={"alt_operasyon_ref": new_ao_row.name, "parent": calisma_karti},
                                   fields=["*"])
        
        operation_data = {
            "sanal_yarimamul_davranisi": ao_doc.sanal_yarimamul_davranisi,
            "davranis_alt_parametresi": ao_doc.davranis_alt_parametresi,
            "damar_sayisi": ao_doc.damar_sayisi,
            "hedef_node_id": None, 
            "pin_number": None,
            "is_emri": doc.custom_work_order,
            "calisma_karti": doc.name,
            "operation_ref": new_ao_row.name
        }
        
        # Extract hedef_node_id if applicable
        for t in saved_hts:
            if t.get("hedef_node_id"):
                operation_data["hedef_node_id"] = t.get("hedef_node_id")
                break
                
        if note and "Pin: " in note:
            parts = note.split("Pin: ")
            if len(parts) > 1:
                operation_data["pin_number"] = parts[-1].split("\n")[0].strip()
        
        # Need to determine wip_ids_for_graph
        wip_ids_for_graph = []
        for t in saved_hts:
            wids = t.get("source_wip_ids") or t.get("wip_id")
            if wids:
                try:
                    parsed = json.loads(wids)
                    wip_ids_for_graph.extend(parsed)
                except:
                    wip_ids_for_graph.extend([x.strip() for x in wids.split(",") if x.strip()])
                    
        # Remove duplicates while preserving order
        wip_ids_for_graph = list(dict.fromkeys(wip_ids_for_graph))
        
        if not wip_ids_for_graph and new_wip_id:
            wip_ids_for_graph = [new_wip_id]
            
        graph_materials = []
        for t in saved_hts:
            if t.get("hammadde") or t.get("boyut_mm"):
                graph_materials.append({
                    "hammadde": t.get("hammadde") or "", 
                    "boyut_mm": t.get("boyut_mm"),
                    "yon": t.get("yon"),
                    "islem_adedi": t.get("islem_adedi")
                })
        
        if wip_ids_for_graph:
            try:
                tracking = process_operation(wip_ids_for_graph, operation_data, graph_materials, is_draft=(doc.docstatus == 0))
                import json
                new_ao_row.wip_snapshots = json.dumps(tracking)
                new_ao_row.save(ignore_permissions=True)
                
                # Assign generated result_wip_id to the first Hammadde Kayitlari row for UI linking
                res_wip = tracking.get("result_wip_id")
                if res_wip:
                    target_hts = frappe.db.get_all("KTA Calisma Karti Hammadde Kayitlari", filters={"alt_operasyon_ref": new_ao_row.name, "parent": calisma_karti})
                    if target_hts:
                        frappe.db.set_value("KTA Calisma Karti Hammadde Kayitlari", target_hts[0].name, "wip_id", res_wip)
                        frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Graph Engine Error for {wip_ids_for_graph}: {str(e)}", "WIP Graph Engine Add Row")
                frappe.throw(f"Sanal Yarımamül (WIP) Graph Hatası: {str(e)}")

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
    note: str = None,
    satir_no: str = None,
    hammadde_tuketimleri=None,
    source_wip_ids: str = None,
    **kwargs
):
    import json
    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    doc.check_permission("write")
    _assert_can_write(doc)
    
    row = doc.get("alt_operasyon_kayitlari", {"name": row_id})
    if not row:
        frappe.throw(_("Kayıt bulunamadı."))
    row = row[0]
    
    _assert_qc_unlocked(doc, row)
    
    if isinstance(hammadde_tuketimleri, str):
        hammadde_tuketimleri = json.loads(hammadde_tuketimleri)
    if not hammadde_tuketimleri:
        hammadde_tuketimleri = []

    items_to_check = []
    for t in hammadde_tuketimleri:
        adet, uom = _calculate_tuketim(t.get("hammadde"), t.get("boyut_mm"), t.get("islem_adedi"))
        dedup_key = (t.get("hammadde"), adet, t.get("source_wip_ids"))
        items_to_check.append(dedup_key)

    _assert_within_wo_limits(calisma_karti, items_to_check, exclude_row=row_id)
    _assert_within_wip_limits(hammadde_tuketimleri, source_wip_ids, exclude_row=row_id)

    row.alt_operasyon = alt_operasyon
    row.note = note
    row.satir_no = satir_no

    # Extract old wip data
    old_h = [r for r in doc.get("hammadde_tuketimleri") if r.alt_operasyon_ref == row_id]
    old_wip_id = None
    old_source_wip_ids = source_wip_ids
    for r in old_h:
        if r.wip_id:
            old_wip_id = r.wip_id
        if not source_wip_ids and r.source_wip_ids:
            old_source_wip_ids = r.source_wip_ids

    # Clear old hammaddes for this row
    for r in old_h:
        doc.remove(r)
        
    wip_id_to_use = old_wip_id or f"{calisma_karti}-{frappe.generate_hash(length=6)}"

    for t in hammadde_tuketimleri:
        if t.get("hammadde") or (t.get("boyut_mm") and float(t.get("boyut_mm")) > 0):
            row_data = {
                "alt_operasyon_ref": row_id,
                "hammadde": t.get("hammadde") or None,
                "boyut_mm": t.get("boyut_mm") or 0,
                "islem_adedi": t.get("islem_adedi") or 1,
                "uom": t.get("uom"),
                "yon": t.get("yon") or "Orta",
                "source_wip_ids": t.get("source_wip_ids"),
                "hedef_kavite": t.get("hedef_kavite")
            }
            if row_data["yon"] == "Orta":
                row_data["wip_id"] = wip_id_to_use
            
            raw_source = t.get("source_wip_ids") or source_wip_ids
            
            if raw_source and "," in raw_source:
                distributed = distribute_wip_consumption(raw_source, row_data["islem_adedi"], exclude_row=row_id)
                for d in distributed:
                    split_row = row_data.copy()
                    split_row["source_wip_ids"] = d["wip_id"]
                    split_row["islem_adedi"] = d["islem_adedi"]
                    doc.append("hammadde_tuketimleri", split_row)
            else:
                row_data["source_wip_ids"] = raw_source
                doc.append("hammadde_tuketimleri", row_data)

    kablo_no = ""
    boyut_1_mm = 0
    krimp_kontak_1 = ""
    siyirma_1 = 0
    krimp_kontak_2 = ""
    siyirma_2 = 0
    for t in hammadde_tuketimleri:
        h = t.get("hammadde")
        yon = t.get("yon")
        ig = frappe.db.get_value("Item", h, "item_group") or "" if h else ""
        
        # Kablo tespiti: Yön Orta ise direkt kablo kabul et, değilse item_group'tan tahmin et
        if (yon == "Orta" or (not yon and ("kablo" in ig.lower() or "cable" in ig.lower() or "wire" in ig.lower()))) and not kablo_no:
            kablo_no = h or ""
            boyut_1_mm = t.get("boyut_mm") or 0
            
        elif yon == "Sol":
            if h and not krimp_kontak_1 and ("terminal" in ig.lower() or "kontak" in ig.lower()):
                krimp_kontak_1 = h
            if not siyirma_1 and t.get("boyut_mm"):
                siyirma_1 = float(t.get("boyut_mm") or 0)
                
        elif yon == "Sağ":
            if h and not krimp_kontak_2 and ("terminal" in ig.lower() or "kontak" in ig.lower()):
                krimp_kontak_2 = h
            if not siyirma_2 and t.get("boyut_mm"):
                siyirma_2 = float(t.get("boyut_mm") or 0)
                
        # Eski veri (yon yoksa) Sol/Sağ terminal tahmini
        elif not yon and h and ("terminal" in ig.lower() or "kontak" in ig.lower()):
            if not krimp_kontak_1:
                krimp_kontak_1 = h
                siyirma_1 = float(t.get("boyut_mm") or 0)
            elif not krimp_kontak_2:
                krimp_kontak_2 = h
                siyirma_2 = float(t.get("boyut_mm") or 0)

    ao_doc = frappe.get_cached_doc("KTA Calisma Karti Alt Operasyonlari", alt_operasyon)
    is_cift_tarafli = 1 if (krimp_kontak_2 or siyirma_2 > 0) else 0

    krimp_row_id = next((r.name for r in doc.get("krimp_olcumleri") if r.alt_operasyon_kaydi == row_id), None)
    if krimp_row_id:
        frappe.db.set_value(
            "Calisma Karti Krimp Olcumleri",
            krimp_row_id,
            {
                "kablo_no": kablo_no,
                "hedef_kablo_boyu": float(boyut_1_mm),
                "kontak_no": krimp_kontak_1,
                "siyirma_boyu": siyirma_1,
                "is_cift_tarafli": is_cift_tarafli,
                "yon_2_kontak_no": krimp_kontak_2,
                "yon_2_siyirma_boyu": siyirma_2,
            }
        )

    doc.flags.ignore_validate_update_after_submit = True
    doc.flags.ignore_links = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    # ----------------------------------------------------
    # GRAPH CORE ENGINE INTEGRATION (Executes immediately)
    # ----------------------------------------------------
    from erpnextkta.kta_calisma_karti.api_impl.wip_graph_engine import process_operation
    
    if ao_doc.sanal_yarimamul_davranisi:
        # Re-fetch the saved rows for this row to pass to process_operation
        saved_hts = frappe.get_all("KTA Calisma Karti Hammadde Kayitlari", 
                                   filters={"alt_operasyon_ref": row.name, "parent": calisma_karti},
                                   fields=["*"])
        
        operation_data = {
            "sanal_yarimamul_davranisi": ao_doc.sanal_yarimamul_davranisi,
            "davranis_alt_parametresi": ao_doc.davranis_alt_parametresi,
            "damar_sayisi": ao_doc.damar_sayisi,
            "hedef_node_id": None, 
            "pin_number": None,
            "is_emri": doc.custom_work_order,
            "calisma_karti": doc.name,
            "operation_ref": row.name
        }
        
        for t in saved_hts:
            if t.get("hedef_node_id"):
                operation_data["hedef_node_id"] = t.get("hedef_node_id")
                break
                
        if note and "Pin: " in note:
            parts = note.split("Pin: ")
            if len(parts) > 1:
                operation_data["pin_number"] = parts[-1].split("\n")[0].strip()
        
        wip_ids_for_graph = []
        for t in saved_hts:
            wids = t.get("source_wip_ids") or t.get("wip_id")
            if wids:
                try:
                    parsed = json.loads(wids)
                    wip_ids_for_graph.extend(parsed)
                except:
                    wip_ids_for_graph.extend([x.strip() for x in wids.split(",") if x.strip()])
                    
        wip_ids_for_graph = list(dict.fromkeys(wip_ids_for_graph))
        
        if not wip_ids_for_graph and wip_id_to_use:
            wip_ids_for_graph = [wip_id_to_use]
            
        graph_materials = []
        for t in saved_hts:
            if t.get("hammadde") or t.get("boyut_mm"):
                graph_materials.append({
                    "hammadde": t.get("hammadde") or "", 
                    "boyut_mm": t.get("boyut_mm"),
                    "yon": t.get("yon"),
                    "islem_adedi": t.get("islem_adedi")
                })
        
        if wip_ids_for_graph:
            try:
                tracking = process_operation(wip_ids_for_graph, operation_data, graph_materials, is_draft=(doc.docstatus == 0))
                import json
                new_ao_row.wip_snapshots = json.dumps(tracking)
                new_ao_row.save(ignore_permissions=True)
                
                # Assign generated result_wip_id to the first Hammadde Kayitlari row for UI linking
                res_wip = tracking.get("result_wip_id")
                if res_wip:
                    target_hts = frappe.db.get_all("KTA Calisma Karti Hammadde Kayitlari", filters={"alt_operasyon_ref": new_ao_row.name, "parent": calisma_karti})
                    if target_hts:
                        frappe.db.set_value("KTA Calisma Karti Hammadde Kayitlari", target_hts[0].name, "wip_id", res_wip)
                        frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Graph Engine Error for {wip_ids_for_graph}: {str(e)}", "WIP Graph Engine Update Row")
                frappe.throw(f"Sanal Yarımamül (WIP) Graph Hatası: {str(e)}")
    from erpnextkta.kta_calisma_karti.api_impl.qc import _update_parent_qc_status_from_alt_ops
    doc.reload()
    _update_parent_qc_status_from_alt_ops(doc)

    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:update")
    return row.name


@frappe.whitelist()
def delete_alt_operasyon_kaydi(calisma_karti: str, row_id: str):
    import json
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

    wips_to_check_for_delete = set()
    ht_to_remove = [r for r in doc.get("hammadde_tuketimleri", []) if r.alt_operasyon_ref == row_id]
    for r in ht_to_remove:
        if r.wip_id:
            wips_to_check_for_delete.add(r.wip_id)
        if r.source_wip_ids:
            for wid in [x.strip() for x in r.source_wip_ids.split(",") if x.strip()]:
                wips_to_check_for_delete.add(wid)
        doc.remove(r)
        

    doc.flags.ignore_validate_update_after_submit = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    # SNAPSHOT ROLLBACK LOGIC
    import json
    if row and getattr(row, "wip_snapshots", None):
        try:
            tracking = json.loads(row.wip_snapshots)
            created_wips = tracking.get("created_wips", [])
            mutated_wips = tracking.get("mutated_wips", {})
            
            # 1. Delete created wips
            for cw in created_wips:
                if frappe.db.exists("KTA Sanal Yarimamul", cw):
                    frappe.delete_doc("KTA Sanal Yarimamul", cw, force=True, ignore_permissions=True)
            
            # 2. Restore mutated wips
            for mw_id, snapshot in mutated_wips.items():
                if frappe.db.exists("KTA Sanal Yarimamul", mw_id):
                    wip = frappe.get_doc("KTA Sanal Yarimamul", mw_id)
                    wip.status = snapshot.get("status")
                    wip.graph_state = snapshot.get("graph_state")
                    wip.save(ignore_permissions=True)
                    
        except Exception as e:
            frappe.log_error(f"Snapshot Rollback Error: {e}")
            
    frappe.db.commit()


    from erpnextkta.kta_calisma_karti.api_impl.qc import _update_parent_qc_status_from_alt_ops
    doc.reload()
    _update_parent_qc_status_from_alt_ops(doc)

    publish_calisma_karti_changed(calisma_karti, reason="alt_operasyon:delete")
    return True


@frappe.whitelist()
def get_alt_operasyon_options(parent_operation: str):
    fields = ["name", "title", "sanal_yarimamul_davranisi", "davranis_alt_parametresi", "damar_sayisi"]
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
        "options": [{"label": o.title, "value": o.name, "hammadde_sayisi": o.get("hammadde_sayisi") or "1", "operasyon_tipi": o.get("operasyon_tipi") or "", "sanal_yarimamul_davranisi": o.get("sanal_yarimamul_davranisi"), "davranis_alt_parametresi": o.get("davranis_alt_parametresi")} for o in ops],
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

@frappe.whitelist()
def get_work_order_pool(work_order: str, operasyon: str, exclude_row: str = None):
    if not work_order or not operasyon:
        return []
        
    current_sequence = frappe.db.get_value("KTA Calisma Karti Operasyonlari", operasyon, "sequence")
    if not current_sequence:
        return []
    current_sequence = int(current_sequence)
    
    # 1. Get all Calisma Kartis in this WO
    cards = frappe.db.get_all("Calisma Karti", filters={"custom_work_order": work_order}, fields=["name", "operasyon"])
    
    valid_cards = []
    all_cards_in_wo = []
    for c in cards:
        all_cards_in_wo.append(c.name)
        if c.operasyon:
            seq = frappe.db.get_value("KTA Calisma Karti Operasyonlari", c.operasyon, "sequence")
            if seq is not None and int(seq) <= current_sequence:
                valid_cards.append(c.name)
                
    if not valid_cards:
        return []
        
    # ----------------------------------------------------
    # Graph-Based WIPs
    # ----------------------------------------------------
    available_wips = []
    graph_wips = frappe.db.get_all(
        "KTA Sanal Yarimamul",
        filters={"is_emri": work_order, "status": ["in", ["Aktif", "Rezervasyon"]], "is_graph_based": 1},
        fields=["name", "calisma_karti", "graph_state"]
    )
    
    # Rezervasyon olanlari sadece eger ayni is emrine aitse gosteriyoruz. Zaten filtrede is_emri var. 
    # Ama sadece guncel kartin (ya da genel olarak bu is emrindeki) rezervasyonlari. (is_emri eslesmesi yeterli).

    
    for gw in graph_wips:
        import json
        try:
            g = json.loads(gw.graph_state or "{}")
            t1_node = next((n for n in g.get("nodes", []) if n.get("type") == "Uç (T1)"), None)
            c_nodes = [n for n in g.get("nodes", []) if n.get("type") == "Kablo Merkezi"]
            c_node = c_nodes[0] if c_nodes else None
            t2_node = next((n for n in g.get("nodes", []) if n.get("type") == "Uç (T2)"), None)
            
            parts = []
            is_merged = len(c_nodes) > 1
            
            if is_merged:
                c_strs = []
                for cn in c_nodes:
                    mats = cn.get("materials", [])
                    if mats:
                        c_strs.append(" + ".join([f"{m.get('hammadde')} ({m.get('boyut_mm') or 0}MM)" for m in mats]))
                rich_label = "Birleşik Kablo (Doppel vb.): " + " / ".join(c_strs)
            else:
                if t1_node:
                    mats = t1_node.get("materials", [])
                    if mats:
                        parts.append("T1: " + " + ".join([str(m.get("hammadde")) for m in mats]) + " (DOLU)")
                    else:
                        parts.append("T1: (AÇIK)")
                        
                if c_node:
                    mats = c_node.get("materials", [])
                    if mats:
                        c_str = "C: " + " + ".join([f"{m.get('hammadde')} ({m.get('boyut_mm') or 0}MM)" for m in mats])
                        parts.append(c_str)
                        
                if t2_node:
                    mats = t2_node.get("materials", [])
                    if mats:
                        parts.append("T2: " + " + ".join([str(m.get("hammadde")) for m in mats]) + " (DOLU)")
                    else:
                        parts.append("T2: (AÇIK)")
                        
                if parts:
                    rich_label = " — ".join(parts)
                else:
                    rich_label = "İşleniyor (Graph)"
        except Exception:
            rich_label = "İşleniyor (Graph)"
            
        op_code = ""
        if gw.calisma_karti:
            op_name = ck_map.get(gw.calisma_karti) if 'ck_map' in locals() else frappe.db.get_value("Calisma Karti", gw.calisma_karti, "operasyon")
            if op_name:
                op_code = op_name.split(" - ")[0].strip()
                
        yon_capacity = {"Sol": 0.0, "Sağ": 0.0, "Orta": 0.0}
        yon_consumed = {"Sol": 0.0, "Sağ": 0.0, "Orta": 0.0}

        for node in g.get("nodes", []):
            # Kapasite tespiti
            if node.get("type") == "Uç (T1)":
                yon = "Sol"
            elif node.get("type") == "Uç (T2)":
                yon = "Sağ"
            elif node.get("type") == "Kablo Merkezi":
                yon = "Orta"
            else:
                yon = None
            
            if yon:
                for m in node.get("materials", []):
                    yon_capacity[yon] = yon_capacity.get(yon, 0.0) + float(m.get("islem_adedi") or 0)

        # Birleşim (Doppel) vb ise Orta kapasitelerin ortalaması veya min değeri mantıklı olabilir
        # Ancak Orta toplamı her zaman en doğru kapasitedir (Birleşik kablolar için kablo merkezlerinin minimumu)
        c_nodes_capacity = []
        for n in g.get("nodes", []):
            if n.get("type") == "Kablo Merkezi":
                c_cap = sum(float(m.get("islem_adedi") or 0) for m in n.get("materials", []))
                if c_cap > 0:
                    c_nodes_capacity.append(c_cap)
                    
        if c_nodes_capacity:
            base_capacity = min(c_nodes_capacity)
        else:
            base_capacity = max([v for k, v in yon_capacity.items()]) if any(v for k, v in yon_capacity.items()) else 0

        # Graph'taki tüketimleri değil, DB'deki gerçek tüketimleri baz alıyoruz
        used_records = frappe.db.get_all(
            "KTA Calisma Karti Hammadde Kayitlari",
            filters={"source_wip_ids": ["like", f"%{gw.name}%"]},
            fields=["islem_adedi", "yon", "source_wip_ids", "alt_operasyon_ref", "parent"]
        )
        def _ds2(p):
            if not p: return 2
            v = frappe.db.get_value("Calisma Karti", p, "docstatus")
            return v if v is not None else 2
            
        valid_used_records = []
        for r in used_records:
            if r.get("alt_operasyon_ref"):
                ao_parent = frappe.db.get_value("Calisma Karti Alt Operasyon Kayitlari", r.get("alt_operasyon_ref"), "parent")
                if ao_parent != r.get("parent"):
                    continue
            if _ds2(r.get("parent")) < 2:
                valid_used_records.append(r)
        
        for r in valid_used_records:
            if r.get("source_wip_ids"):
                s_wips = [x.strip() for x in r.get("source_wip_ids").split(",")]
                if gw.name in s_wips:
                    if exclude_row and r.get("alt_operasyon_ref") == exclude_row:
                        continue
                    y = r.get("yon") or "Orta"
                    if y in yon_consumed:
                        yon_consumed[y] += float(r.get("islem_adedi") or 0)


        # O kablo üzerinde HERHANGİ BİR YÖNDE yapılan en yüksek tüketim, kablonun geri kalan limitini belirler.
        max_consumed = max(yon_consumed.values()) if any(yon_consumed.values()) else 0
        
        adet = (base_capacity - max_consumed) if base_capacity > 0 else 1
        
        if adet <= 0:
            continue
                
        available_wips.append({
            "wip_id": gw.name,
            "label": f"[{op_code}][Sanal] {rich_label}" if op_code else f"[Sanal] {rich_label}",
            "is_graph_based": 1,
            "_sort_op": op_code,
            "_sort_satir": -1, # Sanal WIP'ler üstte görünsün
            "islem_adedi": adet
        })
        
    # Görsel Gruplama (Aggregation): Aynı etikete (label) sahip WIP'leri birleştir
    grouped_wips = {}
    for wip in available_wips:
        lbl = wip["label"]
        if lbl not in grouped_wips:
            grouped_wips[lbl] = {
                "wip_id": wip["wip_id"],
                "label": lbl,
                "is_graph_based": 1,
                "_sort_op": wip.get("_sort_op", ""),
                "_sort_satir": wip.get("_sort_satir", 99999),
                "islem_adedi": wip["islem_adedi"]
            }
        else:
            grouped_wips[lbl]["wip_id"] += f",{wip['wip_id']}"
            grouped_wips[lbl]["islem_adedi"] += wip["islem_adedi"]

    aggregated_wips = list(grouped_wips.values())
    
    # Sort from smallest to largest by Operation Code and Row No
    aggregated_wips.sort(key=lambda x: (x.get("_sort_op", ""), x.get("_sort_satir", 99999)))
            
    return aggregated_wips

@frappe.whitelist()
def get_wip_source_info(wip_ids):
    import json
    if isinstance(wip_ids, str):
        try:
            wip_ids = json.loads(wip_ids)
        except Exception:
            wip_ids = [wip_ids]
            
    if not wip_ids:
        return {}
        
    # Get the source hammadde records that GENERATED these WIPs
    sources = frappe.db.get_all(
        "KTA Calisma Karti Hammadde Kayitlari",
        filters={"wip_id": ["in", wip_ids]},
        fields=["wip_id", "alt_operasyon_ref", "parent"]
    )
    
    if not sources:
        return {}
        
    alt_refs = list(set(s.alt_operasyon_ref for s in sources))
    parent_cards = list(set(s.parent for s in sources))
    
    ao_data = frappe.db.get_all(
        "Calisma Karti Alt Operasyon Kayitlari",
        filters={"name": ["in", alt_refs]},
        fields=["name", "satir_no"]
    )
    ao_map = {d.name: d.satir_no for d in ao_data}
    
    ck_data = frappe.db.get_all(
        "Calisma Karti",
        filters={"name": ["in", parent_cards]},
        fields=["name", "operasyon"]
    )
    ck_map = {d.name: d.operasyon for d in ck_data}
    
    # Fetch components for these alt_refs to build the rich label
    components = frappe.db.get_all(
        "KTA Calisma Karti Hammadde Kayitlari",
        filters={"alt_operasyon_ref": ["in", alt_refs]},
        fields=["alt_operasyon_ref", "yon", "hammadde", "boyut_mm"]
    )
    comp_map = {}
    for c in components:
        comp_map.setdefault(c.alt_operasyon_ref, []).append(c)

    def format_comp(c, prefix):
        if prefix == "C":
            if c.hammadde and c.boyut_mm:
                return f"C: {c.hammadde} ({c.boyut_mm}mm)"
            elif c.hammadde:
                return f"C: {c.hammadde}"
            return ""
        else:
            if c.hammadde and str(c.hammadde).lower() != "none":
                res = f"{prefix}: {c.hammadde}"
                if c.boyut_mm:
                    res += f" ({c.boyut_mm}mm)"
                res += " (Dolu)"
                return res
            elif c.boyut_mm:
                return f"{prefix}: {c.boyut_mm}mm (Açık)" 
            elif c.boyut_mm:
                return f"{prefix}: {c.boyut_mm}mm (Açık)"
        return ""
    
    def format_satir_no(val):
        if not val: return val
        try:
            parts = str(val).split('.')
            int_part = parts[0].zfill(2)
            dec_part = parts[1].zfill(2) if len(parts) > 1 else ""
            return f"{int_part}.{dec_part}" if dec_part else int_part
        except Exception:
            return val
            
    result = {}
    for s in sources:
        satir_no = ao_map.get(s.alt_operasyon_ref)
        display_ref = format_satir_no(satir_no) if satir_no else s.alt_operasyon_ref
        
        operasyon = ck_map.get(s.parent)
        op_code = operasyon.split(" - ")[0].strip() if operasyon else ""
        
        prefix = f"[{op_code}][{display_ref}]" if op_code else f"[{display_ref}]"
        
        comps = comp_map.get(s.alt_operasyon_ref, [])
        sol_parts = [format_comp(c, "T1") for c in comps if c.yon == "Sol"]
        orta_parts = [format_comp(c, "C") for c in comps if c.yon == "Orta"]
        sag_parts = [format_comp(c, "T2") for c in comps if c.yon == "Sağ"]
        
        all_parts = [p for p in sol_parts + orta_parts + sag_parts if p]
        
        rich_label = " ━ ".join(all_parts) if all_parts else ""
        
        result[s.wip_id] = f"{prefix} {rich_label}"
            
    missing_wips = [wid for wid in wip_ids if wid not in result]
    missing_wips = [wid for wid in wip_ids if wid not in result]

    if missing_wips:
        # Deep lineage tracing for split leftovers
        def trace_origin(wid):
            curr = wid
            visited = set()
            while curr and curr.startswith("WIP-") and curr not in visited:
                visited.add(curr)
                
                # Find the operation that CREATED this WIP
                creator_ops = frappe.db.sql('''
                    SELECT name, satir_no, parent, wip_snapshots 
                    FROM `tabCalisma Karti Alt Operasyon Kayitlari` 
                    WHERE wip_snapshots LIKE %s 
                    ORDER BY creation ASC
                ''', (f'%"{curr}"%',), as_dict=True)
                
                found_creator = False
                import json
                for c in creator_ops:
                    try:
                        snaps = json.loads(c.wip_snapshots or "{}")
                        if curr in snaps.get("created_wips", []):
                            # This is the actual creator!
                            if c.satir_no:
                                return {"satir_no": c.satir_no, "calisma_karti": c.parent}
                            
                            muts = list(snaps.get("mutated_wips", {}).keys())
                            if muts:
                                if len(muts) == 1:
                                    curr = muts[0]
                                    found_creator = True
                                    break
                                else:
                                    # Match graph state Kablo Merkezi hammadde
                                    curr_gs_str = frappe.db.get_value("KTA Sanal Yarimamul", curr, "graph_state")
                                    curr_cable = None
                                    try:
                                        cgs = json.loads(curr_gs_str)
                                        for n in cgs.get("nodes", []):
                                            if n.get("type") == "Kablo Merkezi" and n.get("materials"):
                                                curr_cable = n["materials"][0].get("hammadde")
                                                break
                                    except: pass
                                    
                                    matched_mut = muts[0]
                                    if curr_cable:
                                        for m in muts:
                                            try:
                                                m_gs_str = snaps["mutated_wips"][m].get("graph_state", "{}")
                                                mgs = json.loads(m_gs_str) if isinstance(m_gs_str, str) else m_gs_str
                                                for n in mgs.get("nodes", []):
                                                    if n.get("type") == "Kablo Merkezi" and n.get("materials"):
                                                        if n["materials"][0].get("hammadde") == curr_cable:
                                                            matched_mut = m
                                                            break
                                            except: pass
                                    curr = matched_mut
                                    found_creator = True
                                    break
                    except: pass
                
                if found_creator:
                    continue
                    
                # If no creator operation found, it must be an initial WIP from BOM
                hk = frappe.db.get_value("KTA Calisma Karti Hammadde Kayitlari", {"wip_id": curr}, ["alt_operasyon_ref", "parent"], as_dict=True)
                if hk:
                    op_satir = frappe.db.get_value("Calisma Karti Alt Operasyon Kayitlari", hk.alt_operasyon_ref, "satir_no")
                    return {"satir_no": op_satir, "calisma_karti": hk.parent}
                    
                break
                
            # Fallback to its own calisma_karti if nothing else works
            gw2 = frappe.db.get_value("KTA Sanal Yarimamul", wid, ["calisma_karti"], as_dict=True)
            if gw2:
                return {"satir_no": "", "calisma_karti": gw2.calisma_karti}
                
            return None
                    
        for wid in missing_wips:
            orig_data = trace_origin(wid)
            if orig_data:
                orig_satir = orig_data.get("satir_no") or ""
                orig_ck = orig_data.get("calisma_karti") or (gw.calisma_karti if gw else "")
                
                gw_rec = frappe.db.get_value("KTA Sanal Yarimamul", wid, ["calisma_karti", "graph_state"], as_dict=True)
                if gw_rec and gw_rec.graph_state:
                    try:
                        g = json.loads(gw_rec.graph_state)
                        t1_node = next((n for n in g.get("nodes", []) if n.get("type") == "Uç (T1)"), None)
                        c_nodes = [n for n in g.get("nodes", []) if n.get("type") == "Kablo Merkezi"]
                        c_node = c_nodes[0] if c_nodes else None
                        t2_node = next((n for n in g.get("nodes", []) if n.get("type") == "Uç (T2)"), None)
                        
                        def get_mat_info(n, yon):
                            if n and n.get("materials"):
                                m = next((m for m in n["materials"] if m.get("yon") == yon), None)
                                if not m and n["materials"]: m = n["materials"][0]
                                if m:
                                    ham = m.get('hammadde', '')
                                    boyut = m.get('boyut_mm', '')
                                    return {"hammadde": ham, "boyut": boyut, "status": n.get("status", "")}
                            return None
                        
                        sol_info = get_mat_info(t1_node, "Sol")
                        c_info = get_mat_info(c_node, "Orta")
                        sag_info = get_mat_info(t2_node, "Sağ")
                        
                        def format_terminal(info, prefix):
                            if not info: return ""
                            ham = info.get("hammadde")
                            boyut = info.get("boyut")
                            status = info.get("status")
                            
                            if ham and str(ham).lower() != "none":
                                res = f"{prefix}: {ham}"
                                if boyut:
                                    b = float(boyut)
                                    res += f" ({b:.1f}mm)"
                                res += " (Dolu)"
                                return res
                            elif boyut:
                                b = float(boyut)
                                return f"{prefix}: {b:.1f}mm (Açık)"
                            return ""
                            
                        def format_cable(info, prefix):
                            if not info: return ""
                            ham = info.get("hammadde", "")
                            boyut = info.get("boyut")
                            res = f"{prefix}: {ham}" if ham else prefix
                            if boyut:
                                b = float(boyut)
                                res += f" ({b:.1f}mm)"
                            return res
                        
                        sol = format_terminal(sol_info, "T1")
                        c = format_cable(c_info, "C")
                        sag = format_terminal(sag_info, "T2")
                        
                        parts = []
                        if sol: parts.append(sol)
                        if c: parts.append(c)
                        if sag: parts.append(sag)
                        
                        rich_label = " ━ ".join(parts)
                        
                        operasyon = ""
                        if orig_ck:
                            if orig_ck not in ck_map:
                                ck_map[orig_ck] = frappe.db.get_value("Calisma Karti", orig_ck, "operasyon") or ""
                            operasyon = ck_map[orig_ck]
                        
                        op_code = operasyon.split(" - ")[0].strip() if operasyon else ""
                        formatted_satir = format_satir_no(orig_satir) if orig_satir else ""
                        prefix = f"[{op_code}][{formatted_satir}]" if (op_code and formatted_satir) else (f"[{op_code}]" if op_code else (f"[{formatted_satir}]" if formatted_satir else ""))
                        
                        result[wid] = f"{prefix} {rich_label}".strip()
                    except: pass

        # re-evaluate
        missing_wips = [wid for wid in wip_ids if wid not in result]
        
    if missing_wips:
        graph_wips = frappe.db.get_all("KTA Sanal Yarimamul", filters={"name": ["in", missing_wips]}, fields=["name", "calisma_karti", "graph_state"])
        
        missing_cks = list(set(gw.calisma_karti for gw in graph_wips if gw.calisma_karti))
        if missing_cks:
            extra_ck_data = frappe.db.get_all("Calisma Karti", filters={"name": ["in", missing_cks]}, fields=["name", "operasyon"])
            for d in extra_ck_data:
                ck_map[d.name] = d.operasyon
                
        for gw in graph_wips:
            import json
            try:
                g = json.loads(gw.graph_state or "{}")
                t1_node = next((n for n in g.get("nodes", []) if n.get("type") == "Uç (T1)"), None)
                c_nodes = [n for n in g.get("nodes", []) if n.get("type") == "Kablo Merkezi"]
                c_node = c_nodes[0] if c_nodes else None
                t2_node = next((n for n in g.get("nodes", []) if n.get("type") == "Uç (T2)"), None)
                
                def get_mat(n, yon):
                    if n and n.get("materials"):
                        m = next((m for m in n["materials"] if m.get("yon") == yon), None)
                        if not m and n["materials"]: m = n["materials"][0]
                        if m:
                            res = f"{m.get('hammadde','')}"
                            if m.get("boyut_mm"): res += f" ({m['boyut_mm']}mm)"
                            return res
                    return ""
                
                sol = get_mat(t1_node, "Sol")
                c = get_mat(c_node, "Orta")
                sag = get_mat(t2_node, "Sağ")
                
                parts = []
                if sol: parts.append(f"T1: {sol} (Açık)")
                if c: parts.append(f"C: {c}")
                if sag: parts.append(f"T2: {sag} (Açık)")
                
                rich_label = " ━ ".join(parts)
                
                operasyon = ck_map.get(gw.calisma_karti) if gw.calisma_karti else ""
                op_code = operasyon.split(" - ")[0].strip() if operasyon else ""
                
                prefix = f"[{op_code}]" if op_code else ""
                result[gw.name] = f"{prefix} {rich_label}".strip()
            except Exception:
                result[gw.name] = gw.name
                
    return result
