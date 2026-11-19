# English comments as requested

"""Work Order Çalışma Kartı & Sub-Operation Analytics Service.

Resolves hierarchical routing checklist (Job Cards -> KTA Operations -> Sub-Operations),
aggregating real-time data from Calisma Karti and child records with quality inspection guards.
Excludes unstarted / empty operations and sub-operations.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt


def validate_work_order_access(work_order: str) -> None:
    """Validate existence and user read permission for a Work Order."""
    if not work_order or not frappe.db.exists("Work Order", work_order):
        frappe.throw(
            _("İş Emri bulunamadı: {0}").format(work_order),
            frappe.DoesNotExistError,
        )
    if not frappe.has_permission("Work Order", "read", work_order):
        frappe.throw(
            _("Bu İş Emri için okuma yetkiniz yok: {0}").format(work_order),
            frappe.PermissionError,
        )


def _resolve_kta_operation(
    erpnext_op: str, production_item: str, work_order: str, jc_name: str
) -> str:
    """Resolve KTA Calisma Karti Operasyonlari name for a given ERPNext operation."""
    if not erpnext_op:
        return ""

    # 1. Specific mapping: operation + production_item
    match = frappe.db.sql(
        """
        SELECT parent FROM `tabKTA Operation ERPNext Mappings`
        WHERE erpnext_operation = %s AND production_item = %s
        LIMIT 1
        """,
        (erpnext_op, production_item),
        as_dict=True,
    )
    if match and match[0].parent:
        return match[0].parent

    # 2. Generic mapping: operation without production_item
    match = frappe.db.sql(
        """
        SELECT parent FROM `tabKTA Operation ERPNext Mappings`
        WHERE erpnext_operation = %s AND (production_item IS NULL OR production_item = '')
        LIMIT 1
        """,
        (erpnext_op,),
        as_dict=True,
    )
    if match and match[0].parent:
        return match[0].parent

    # 3. Direct match by name
    if frappe.db.exists("KTA Calisma Karti Operasyonlari", erpnext_op):
        return erpnext_op

    # 4. Check existing card records
    filters: dict[str, Any] = {"custom_work_order": work_order}
    if jc_name:
        filters["is_karti"] = jc_name
    card_op = frappe.db.get_value("Calisma Karti", filters, "operasyon")
    if card_op:
        return card_op

    return erpnext_op


def _get_item_metadata(
    item_code: str, cache: dict[str, dict[str, str]]
) -> dict[str, str]:
    """Retrieve item name and stock UOM with caching."""
    if not item_code:
        return {"item_name": "", "stock_uom": ""}
    if item_code not in cache:
        res = (
            frappe.db.get_value(
                "Item", item_code, ["item_name", "stock_uom"], as_dict=True
            )
            or {}
        )
        cache[item_code] = {
            "item_name": res.get("item_name") or item_code,
            "stock_uom": res.get("stock_uom") or "",
        }
    return cache[item_code]


def _get_employee_name(emp_id: str, cache: dict[str, str]) -> str:
    """Retrieve employee name with caching."""
    if not emp_id:
        return ""
    if emp_id not in cache:
        emp_name = frappe.db.get_value("Employee", emp_id, "employee_name")
        cache[emp_id] = emp_name or emp_id
    return cache[emp_id]


def _get_kta_op_title(op_code: str, cache: dict[str, str]) -> str:
    """Retrieve KTA operation title with caching."""
    if not op_code:
        return ""
    if op_code not in cache:
        title = frappe.db.get_value(
            "KTA Calisma Karti Operasyonlari", op_code, "calisma_karti_op"
        )
        cache[op_code] = title or op_code
    return cache[op_code]


def _get_sub_op_meta(sub_id: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Retrieve sub-operation metadata with caching."""
    if not sub_id:
        return {}
    if sub_id not in cache:
        res = frappe.db.get_value(
            "KTA Calisma Karti Alt Operasyonlari",
            sub_id,
            ["name", "title", "sequence", "is_tuketim_hesaplanir", "operasyon_tipi"],
            as_dict=True,
        )
        if not res:
            res = {
                "name": sub_id,
                "title": sub_id,
                "sequence": 0,
                "is_tuketim_hesaplanir": 1,
                "operasyon_tipi": "",
            }
        cache[sub_id] = res
    return cache[sub_id]


def _calculate_slot_consumption(
    boyut_mm: float,
    islem_adedi: float,
    adet: float,
    uom: str,
) -> float:
    """Calculate consumed material qty based on dimensions and unit of measure."""
    uom_lower = (uom or "").lower().strip()
    if uom_lower in ("m", "metre", "meter"):
        if flt(boyut_mm) > 0 and flt(islem_adedi) > 0:
            return (flt(boyut_mm) * flt(islem_adedi)) / 1000.0
        return flt(adet or 0)
    return flt(adet or 0)


def _parse_duration_minutes(val: Any) -> float:
    """Parse card duration into minutes from string (HH:MM:SS / M:SS) or numeric."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return round(flt(val), 2)
    s = str(val).strip()
    if not s:
        return 0.0
    if ":" in s:
        parts = s.split(":")
        try:
            if len(parts) == 3:
                return round(
                    flt(parts[0]) * 60.0 + flt(parts[1]) + flt(parts[2]) / 60.0, 2
                )
            if len(parts) == 2:
                return round(flt(parts[0]) + flt(parts[1]) / 60.0, 2)
        except (ValueError, TypeError):
            return 0.0
    try:
        return round(flt(s), 2)
    except (ValueError, TypeError):
        return 0.0


def _build_operator_breakdown(
    item_code: str,
    total_consumed: float,
    item_op_accum: dict[str, dict[str, dict[str, Any]]],
    emp_cache: dict[str, str],
) -> list[dict[str, Any]]:
    """Build operator breakdown list sorted by consumed_qty desc."""
    op_data_map = item_op_accum.get(item_code, {})
    operators: list[dict[str, Any]] = []

    for op, data in op_data_map.items():
        op_qty = data["qty"]
        op_cards = data["cards"]
        emp_name = _get_employee_name(op, emp_cache)
        percentage = (
            round((op_qty / total_consumed) * 100, 1) if total_consumed > 0 else 0.0
        )
        operators.append(
            {
                "operator": op,
                "operator_name": emp_name or op,
                "consumed_qty": round(op_qty, 4),
                "card_count": len(op_cards),
                "percentage": percentage,
            }
        )

    operators.sort(key=lambda x: (-x["consumed_qty"], x["operator"]))
    return operators


def _compute_material_reconciliation(
    work_order: str,
    aok_rows: list[Any],
    scraps: list[Any],
    item_cache: dict[str, dict[str, str]],
    emp_cache: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Compute BOM vs actual consumption and scrap reconciliation for a Work Order."""
    if emp_cache is None:
        emp_cache = {}

    consumed_by_item: dict[str, float] = {}
    item_op_accum: dict[str, dict[str, dict[str, Any]]] = {}
    card_op_cache: dict[str, str] = {}

    for r in aok_rows:
        r_dict = frappe._dict(r) if isinstance(r, dict) else r
        card_name = getattr(r_dict, "parent", None) or ""
        op = getattr(r_dict, "operator", None)
        if op is None and isinstance(r_dict, dict):
            op = r_dict.get("operator")
        if not op and card_name:
            if card_name not in card_op_cache:
                card_op_cache[card_name] = (
                    frappe.db.get_value("Calisma Karti", card_name, "operator") or ""
                )
            op = card_op_cache[card_name]
        op = op or ""

        slots = [
            (
                r_dict.hammadde,
                r_dict.boyut_1_mm,
                r_dict.islem_adedi_1,
                r_dict.adet,
                r_dict.uom,
            ),
            (
                r_dict.hammadde_2,
                r_dict.boyut_2_mm,
                r_dict.islem_adedi_2,
                r_dict.adet_2,
                r_dict.uom_2,
            ),
            (
                r_dict.hammadde_3,
                r_dict.boyut_3_mm,
                r_dict.islem_adedi_3,
                r_dict.adet_3,
                r_dict.uom_3,
            ),
        ]
        for h_mat, b_mm, islem_q, ad_q, slot_uom in slots:
            mat = (h_mat or "").strip()
            if not mat:
                continue
            meta = _get_item_metadata(mat, item_cache)
            actual_uom = slot_uom or meta.get("stock_uom") or ""
            consumed_q = _calculate_slot_consumption(b_mm, islem_q, ad_q, actual_uom)
            consumed_by_item[mat] = consumed_by_item.get(mat, 0.0) + consumed_q

            if mat not in item_op_accum:
                item_op_accum[mat] = {}
            if op not in item_op_accum[mat]:
                item_op_accum[mat][op] = {"qty": 0.0, "cards": set()}
            item_op_accum[mat][op]["qty"] += consumed_q
            if card_name:
                item_op_accum[mat][op]["cards"].add(card_name)

    scrap_by_item: dict[str, float] = {}
    for h in scraps:
        if isinstance(h, dict):
            parca = (h.get("parca_no") or "").strip()
            qty = flt(h.get("miktar") or 0)
        else:
            parca = (getattr(h, "parca_no", None) or "").strip()
            qty = flt(getattr(h, "miktar", 0) or 0)
        if parca:
            scrap_by_item[parca] = scrap_by_item.get(parca, 0.0) + qty

    wo_items = frappe.db.sql(
        """
        SELECT
            item_code,
            item_name,
            required_qty,
            stock_uom,
            operation
        FROM `tabWork Order Item`
        WHERE parent = %s
        ORDER BY idx ASC
        """,
        (work_order,),
        as_dict=True,
    )

    reconciliation: list[dict[str, Any]] = []
    planned_item_codes: set[str] = set()

    for row in wo_items:
        code = (row.get("item_code") or "").strip()
        if not code:
            continue
        planned_item_codes.add(code)
        meta = _get_item_metadata(code, item_cache)
        name = row.get("item_name") or meta.get("item_name") or code
        uom = row.get("stock_uom") or meta.get("stock_uom") or ""
        op = row.get("operation") or ""

        planned_q = round(flt(row.get("required_qty") or 0), 4)
        consumed_q = round(consumed_by_item.get(code, 0.0), 4)
        scrap_q = round(scrap_by_item.get(code, 0.0), 4)
        total_spent = round(consumed_q + scrap_q, 4)
        variance = round(consumed_q - planned_q, 4)

        if consumed_q == 0:
            status = "Tüketim Yok"
            badge = "⚪ Tüketim Yok"
        elif consumed_q < planned_q:
            status = "Devam Ediyor"
            badge = "🟡 Devam Ediyor"
        elif consumed_q == planned_q:
            status = "Tamamlandı"
            badge = "🟢 %100 Eşleşti"
        else:
            status = "Plan Aşımı"
            badge = "🔴 Plan Aşımı"

        ops_list = _build_operator_breakdown(code, consumed_q, item_op_accum, emp_cache)

        reconciliation.append(
            {
                "item_code": code,
                "item_name": name,
                "operation": op,
                "stock_uom": uom,
                "uom": uom,
                "planned_qty": planned_q,
                "consumed_qty": consumed_q,
                "scrap_qty": scrap_q,
                "total_spent": total_spent,
                "variance": variance,
                "status": status,
                "status_badge": badge,
                "operators": ops_list,
            }
        )

    all_actual_codes = sorted(set(consumed_by_item.keys()) | set(scrap_by_item.keys()))
    for code in all_actual_codes:
        if code in planned_item_codes:
            continue
        meta = _get_item_metadata(code, item_cache)
        name = meta.get("item_name") or code
        uom = meta.get("stock_uom") or ""
        consumed_q = round(consumed_by_item.get(code, 0.0), 4)
        scrap_q = round(scrap_by_item.get(code, 0.0), 4)
        total_spent = round(consumed_q + scrap_q, 4)
        variance = consumed_q

        ops_list = _build_operator_breakdown(code, consumed_q, item_op_accum, emp_cache)

        reconciliation.append(
            {
                "item_code": code,
                "item_name": name,
                "operation": "",
                "stock_uom": uom,
                "uom": uom,
                "planned_qty": 0.0,
                "consumed_qty": consumed_q,
                "scrap_qty": scrap_q,
                "total_spent": total_spent,
                "variance": variance,
                "status": "Reçete Dışı",
                "status_badge": "🟣 Reçete Dışı",
                "operators": ops_list,
            }
        )

    reconciliation.sort(
        key=lambda x: (x.get("operation") or "", x.get("item_code") or "")
    )
    return reconciliation


def get_work_order_card_analytics(work_order: str) -> dict[str, Any]:
    """Fetch hierarchical Job Card and Calisma Karti analytics for a Work Order."""
    validate_work_order_access(work_order)

    wo = (
        frappe.db.get_value(
            "Work Order",
            work_order,
            ["name", "production_item", "item_name", "qty"],
            as_dict=True,
        )
        or {}
    )
    production_item = wo.get("production_item") or ""
    item_name = wo.get("item_name") or production_item
    target_qty = flt(wo.get("qty") or 0)

    # 1. Fetch all cards for this Work Order
    cards = frappe.db.sql(
        """
        SELECT
            name,
            operator,
            is_karti,
            operasyon,
            durum,
            net_calisma_suresi,
            tamamlanan_miktar,
            creation,
            docstatus,
            bitis_saati
        FROM `tabCalisma Karti`
        WHERE custom_work_order = %s AND docstatus != 2
        ORDER BY creation ASC
        """,
        (work_order,),
        as_dict=True,
    )

    empty_summary = {
        "total_cards": 0,
        "completed_cards": 0,
        "in_progress_cards": 0,
        "total_duration_mins": 0.0,
        "total_scrap_qty": 0.0,
    }

    item_cache: dict[str, dict[str, str]] = {}
    emp_cache: dict[str, str] = {}

    # If no cards opened at all, exclude all unstarted steps
    if not cards:
        material_rec = _compute_material_reconciliation(
            work_order, [], [], item_cache, emp_cache
        )
        return {
            "work_order": work_order,
            "production_item": production_item,
            "item_name": item_name,
            "qty": target_qty,
            "summary": empty_summary,
            "operations": [],
            "material_reconciliation": material_rec,
        }

    # 2. Fetch all alt operasyon entries
    aok_rows = frappe.db.sql(
        """
        SELECT
            aok.name,
            aok.parent,
            ck.operator,
            aok.alt_operasyon,
            aok.satir_no,
            aok.kalip_no,
            aok.hammadde,   aok.adet,   aok.uom,   aok.boyut_1_mm, aok.islem_adedi_1,
            aok.hammadde_2, aok.adet_2, aok.uom_2, aok.boyut_2_mm, aok.islem_adedi_2,
            aok.hammadde_3, aok.adet_3, aok.uom_3, aok.boyut_3_mm, aok.islem_adedi_3,
            aok.quality_inspection_status
        FROM `tabCalisma Karti Alt Operasyon Kayitlari` aok
        JOIN `tabCalisma Karti` ck ON ck.name = aok.parent
        WHERE ck.custom_work_order = %s
          AND ck.docstatus != 2
          AND IFNULL(aok.quality_inspection_status, '') NOT IN ('Reddedildi', 'Rejected', 'Red')
        ORDER BY aok.idx ASC
        """,
        (work_order,),
        as_dict=True,
    )

    # 3. Fetch all scraps
    scraps = frappe.db.sql(
        """
        SELECT
            h.name,
            h.parent,
            h.parca_no,
            h.hurda_nedeni,
            h.miktar,
            h.birim,
            h.aciklama,
            ck.is_karti,
            ck.operasyon
        FROM `tabCalisma Karti Hurda` h
        JOIN `tabCalisma Karti` ck ON ck.name = h.parent
        WHERE ck.custom_work_order = %s AND ck.docstatus != 2
        ORDER BY h.idx ASC
        """,
        (work_order,),
        as_dict=True,
    )
    kta_op_cache: dict[str, str] = {}
    sub_op_cache: dict[str, dict[str, Any]] = {}

    total_cards = len(cards)
    completed_cards = sum(
        1 for c in cards if c.durum == "Bitmiş" or c.bitis_saati or c.docstatus == 1
    )
    in_progress_cards = total_cards - completed_cards
    total_duration_mins = round(
        sum(_parse_duration_minutes(c.net_calisma_suresi) for c in cards), 2
    )
    total_scrap_qty = round(sum(flt(h.miktar or 0) for h in scraps), 4)

    cards_by_name = {c.name: c for c in cards}

    # Group cards by Job Card
    cards_by_jc: dict[str, list[dict[str, Any]]] = {}
    for c in cards:
        jc_key = c.is_karti or ""
        cards_by_jc.setdefault(jc_key, []).append(c)

    # Resolve Job Card descriptors
    planned_jcs = frappe.get_all(
        "Job Card",
        filters={"work_order": work_order, "docstatus": ["!=", 2]},
        fields=["name", "operation", "workstation", "status", "sequence_id"],
        order_by="sequence_id asc, creation asc",
    )
    jc_info_map = {jc.name: jc for jc in planned_jcs}

    # Collect only Job Cards that have actual cards opened
    active_jcs: list[dict[str, Any]] = []
    seen_jc_keys = set()

    # Preserve sequence_id order from planned Job Cards first
    for jc in planned_jcs:
        if jc.name in cards_by_jc:
            seen_jc_keys.add(jc.name)
            active_jcs.append(
                {
                    "name": jc.name,
                    "operation": jc.operation or jc.name,
                    "sequence_id": cint(jc.sequence_id or 0),
                    "status": jc.status or "Open",
                }
            )

    # Add cards that reference Job Cards not in planned_jcs or orphan cards
    for jc_key in cards_by_jc:
        if jc_key not in seen_jc_keys:
            seen_jc_keys.add(jc_key)
            if jc_key:
                jc_row = jc_info_map.get(jc_key) or frappe.db.get_value(
                    "Job Card",
                    jc_key,
                    ["name", "operation", "workstation", "status", "sequence_id"],
                    as_dict=True,
                )
                if jc_row:
                    active_jcs.append(
                        {
                            "name": jc_row.get("name") or jc_key,
                            "operation": jc_row.get("operation") or jc_key,
                            "sequence_id": cint(jc_row.get("sequence_id") or 0),
                            "status": jc_row.get("status") or "Open",
                        }
                    )
                    continue
            fallback_op = cards_by_jc[jc_key][0].operasyon or ""
            active_jcs.append(
                {
                    "name": jc_key,
                    "operation": fallback_op,
                    "sequence_id": 9999,
                    "status": "In Process",
                }
            )

    # Sort active Job Cards by sequence_id asc, then name asc
    active_jcs.sort(key=lambda x: (x["sequence_id"], x["name"]))

    operations_output: list[dict[str, Any]] = []

    for ajc in active_jcs:
        jc_name = ajc["name"]
        jc_op_name = ajc["operation"]
        jc_seq = ajc["sequence_id"]
        jc_status = ajc["status"]

        jc_cards = cards_by_jc.get(jc_name, [])
        if not jc_cards:
            continue

        jc_card_names = {c.name for c in jc_cards}
        jc_duration = round(
            sum(_parse_duration_minutes(c.net_calisma_suresi) for c in jc_cards), 2
        )

        jc_aok_rows = [r for r in aok_rows if r.parent in jc_card_names]
        jc_scraps = [
            h
            for h in scraps
            if (jc_name and h.is_karti == jc_name) or h.parent in jc_card_names
        ]

        # Build material mapping for scrap matching within this Job Card
        sub_op_materials: dict[str, set[str]] = {}
        for r in jc_aok_rows:
            sub_id = r.alt_operasyon
            if not sub_id:
                continue
            if sub_id not in sub_op_materials:
                sub_op_materials[sub_id] = set()
            if r.hammadde:
                sub_op_materials[sub_id].add(r.hammadde)
            if r.hammadde_2:
                sub_op_materials[sub_id].add(r.hammadde_2)
            if r.hammadde_3:
                sub_op_materials[sub_id].add(r.hammadde_3)

        # Distribute scraps between sub-operations and unmatched
        sub_op_scraps_map: dict[str, list[dict[str, Any]]] = {}
        unmatched_scraps: list[dict[str, Any]] = []

        for h in jc_scraps:
            item_meta = _get_item_metadata(h.parca_no, item_cache)
            sc_uom = h.birim or item_meta["stock_uom"] or ""
            sc_reason = h.hurda_nedeni or h.aciklama or ""
            scrap_entry = {
                "item_code": h.parca_no,
                "qty": round(flt(h.miktar or 0), 4),
                "uom": sc_uom,
                "reason": sc_reason,
            }

            matched_sub_id = None
            parent_aoks = [r for r in jc_aok_rows if r.parent == h.parent]
            for pa in parent_aoks:
                if h.parca_no in (pa.hammadde, pa.hammadde_2, pa.hammadde_3):
                    matched_sub_id = pa.alt_operasyon
                    break

            if not matched_sub_id:
                for sub_id, mats in sub_op_materials.items():
                    if h.parca_no in mats:
                        matched_sub_id = sub_id
                        break

            if matched_sub_id:
                sub_op_scraps_map.setdefault(matched_sub_id, []).append(scrap_entry)
            else:
                unmatched_scraps.append(scrap_entry)

        # Group cards by actual KTA operation (tabCalisma Karti.operasyon)
        raw_op_codes = {
            (
                (c.operasyon or "").strip()
                or _resolve_kta_operation(
                    jc_op_name, production_item, work_order, jc_name
                )
                or jc_op_name
                or ""
            )
            for c in jc_cards
        }
        op_codes = sorted([code for code in raw_op_codes if code] or [""])

        kta_operations_list: list[dict[str, Any]] = []
        all_sub_ops_for_jc: list[dict[str, Any]] = []

        for op_code in op_codes:
            op_cards = [
                c
                for c in jc_cards
                if (
                    (c.operasyon or "").strip()
                    or _resolve_kta_operation(
                        jc_op_name, production_item, work_order, jc_name
                    )
                    or jc_op_name
                    or ""
                )
                == op_code
            ]
            op_card_names = {c.name for c in op_cards}
            kta_op_duration = round(
                sum(_parse_duration_minutes(c.net_calisma_suresi) for c in op_cards),
                2,
            )
            op_title = _get_kta_op_title(op_code, kta_op_cache)

            op_aok_rows = [r for r in jc_aok_rows if r.parent in op_card_names]

            # Only include sub-operations that have actual Calisma Karti / aok records
            distinct_sub_ids = sorted(
                {r.alt_operasyon for r in op_aok_rows if r.alt_operasyon}
            )

            kta_sub_ops: list[dict[str, Any]] = []

            for sub_id in distinct_sub_ids:
                sdef = _get_sub_op_meta(sub_id, sub_op_cache)
                title = sdef.get("title") or sub_id
                seq = cint(sdef.get("sequence") or 0)
                is_tuketim = (
                    1
                    if sdef.get("is_tuketim_hesaplanir") is None
                    else cint(sdef.get("is_tuketim_hesaplanir"))
                )

                sub_aoks = [r for r in op_aok_rows if r.alt_operasyon == sub_id]

                card_process_qty: dict[str, float] = {}
                consumptions_map: dict[str, dict[str, Any]] = {}

                for r in sub_aoks:
                    c_name = r.parent
                    row_qty = max(
                        flt(r.islem_adedi_1 or 0),
                        flt(r.islem_adedi_2 or 0),
                        flt(r.islem_adedi_3 or 0),
                    )
                    if row_qty == 0:
                        row_qty = flt(r.adet or 0)
                    card_process_qty[c_name] = (
                        card_process_qty.get(c_name, 0.0) + row_qty
                    )

                    if is_tuketim:
                        slots = [
                            (
                                r.hammadde,
                                r.boyut_1_mm,
                                r.islem_adedi_1,
                                r.adet,
                                r.uom,
                            ),
                            (
                                r.hammadde_2,
                                r.boyut_2_mm,
                                r.islem_adedi_2,
                                r.adet_2,
                                r.uom_2,
                            ),
                            (
                                r.hammadde_3,
                                r.boyut_3_mm,
                                r.islem_adedi_3,
                                r.adet_3,
                                r.uom_3,
                            ),
                        ]
                        for h_mat, b_mm, islem_q, ad_q, slot_uom in slots:
                            if not h_mat:
                                continue
                            meta = _get_item_metadata(h_mat, item_cache)
                            actual_uom = slot_uom or meta["stock_uom"]
                            consumed_q = _calculate_slot_consumption(
                                b_mm, islem_q, ad_q, actual_uom
                            )
                            if h_mat not in consumptions_map:
                                consumptions_map[h_mat] = {
                                    "item_code": h_mat,
                                    "item_name": meta["item_name"],
                                    "total_qty": 0.0,
                                    "uom": actual_uom,
                                }
                            consumptions_map[h_mat]["total_qty"] += consumed_q

                consumptions_list = [
                    {
                        "item_code": c["item_code"],
                        "item_name": c["item_name"],
                        "total_qty": round(c["total_qty"], 4),
                        "uom": c["uom"],
                    }
                    for c in consumptions_map.values()
                ]

                sub_cards: list[dict[str, Any]] = []
                sub_duration = 0.0
                all_cards_finished = True

                for c_name, p_qty in card_process_qty.items():
                    cdoc = cards_by_name.get(c_name)
                    if not cdoc:
                        continue
                    c_dur = _parse_duration_minutes(cdoc.net_calisma_suresi)
                    sub_duration += c_dur
                    is_fin = bool(
                        cdoc.durum == "Bitmiş"
                        or cdoc.bitis_saati
                        or cdoc.docstatus == 1
                    )
                    if not is_fin:
                        all_cards_finished = False

                    sub_cards.append(
                        {
                            "card_name": c_name,
                            "operator": _get_employee_name(cdoc.operator, emp_cache),
                            "durum": cdoc.durum or "Hazır",
                            "net_calisma_suresi": c_dur,
                            "islem_adedi": round(p_qty, 2),
                            "creation": str(cdoc.creation or ""),
                        }
                    )

                total_sub_process_qty = round(sum(card_process_qty.values()), 2)
                sub_duration = round(sub_duration, 2)

                qty_satisfied = (
                    total_sub_process_qty >= target_qty if target_qty > 0 else True
                )
                if all_cards_finished and qty_satisfied:
                    sub_status = "Tamamlandı"
                    sub_badge = "🟢 Tamamlandı"
                else:
                    sub_status = "Devam Ediyor"
                    sub_badge = "🔵 Devam Ediyor"

                sub_item = {
                    "sub_op_id": sub_id,
                    "title": title,
                    "sequence": seq,
                    "status": sub_status,
                    "status_badge": sub_badge,
                    "is_tuketim_hesaplanir": is_tuketim,
                    "total_process_qty": total_sub_process_qty,
                    "total_duration_mins": sub_duration,
                    "consumptions": consumptions_list if is_tuketim else [],
                    "scraps": sub_op_scraps_map.get(sub_id, []),
                    "cards": sub_cards,
                }
                kta_sub_ops.append(sub_item)

            kta_operations_list.append(
                {
                    "op_code": op_code,
                    "op_title": op_title,
                    "total_duration_mins": kta_op_duration,
                    "sub_operations": kta_sub_ops,
                }
            )
            all_sub_ops_for_jc.extend(kta_sub_ops)

        operations_output.append(
            {
                "job_card": jc_name,
                "operation_name": jc_op_name,
                "sequence_id": jc_seq,
                "status": jc_status,
                "total_duration_mins": jc_duration,
                "unmatched_scraps": unmatched_scraps,
                "kta_operations": kta_operations_list,
                "sub_operations": all_sub_ops_for_jc,
            }
        )

    material_reconciliation = _compute_material_reconciliation(
        work_order, aok_rows, scraps, item_cache, emp_cache
    )

    return {
        "work_order": work_order,
        "production_item": production_item,
        "item_name": item_name,
        "qty": target_qty,
        "summary": {
            "total_cards": total_cards,
            "completed_cards": completed_cards,
            "in_progress_cards": in_progress_cards,
            "total_duration_mins": total_duration_mins,
            "total_scrap_qty": total_scrap_qty,
        },
        "operations": operations_output,
        "material_reconciliation": material_reconciliation,
    }
