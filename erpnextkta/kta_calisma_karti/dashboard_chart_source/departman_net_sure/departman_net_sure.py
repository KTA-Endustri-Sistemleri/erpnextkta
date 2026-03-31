import json
import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime


def _parse_duration_to_minutes(value: str) -> float:
    """HH:MM:SS formatını dakikaya çevirir."""
    if not value or ":" not in str(value):
        return 0.0
    
    parts = str(value).split(":")
    try:
        if len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60.0
        elif len(parts) == 2:  # MM:SS or HH:MM
            return int(parts[0]) + int(parts[1]) / 60.0
        return float(parts[0])
    except Exception:
        return 0.0


@frappe.whitelist()
def get_data(**kwargs):
    """
    Departman bazında toplam net çalışma süresi (son N gün, dakika).
    Otomatik duraklatma süreleri net süre hesabına dahil edilir (duruş sayılmaz).
    Filtreler: days, is_istasyonu
    """
    raw = frappe.form_dict.get("filters") or "{}"
    try:
        filters = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        filters = {}
    if not isinstance(filters, dict):
        filters = {}

    days         = int(filters.get("days", 30))
    is_istasyonu = filters.get("is_istasyonu") or None

    today      = getdate(now_datetime())
    start_date = add_days(today, -days + 1)

    conditions = [
        "DATE(ck.creation) >= %(start)s",
        "DATE(ck.creation) <= %(end)s",
        "ck.docstatus != 2",
        "ck.operator IS NOT NULL",
        "ck.net_calisma_suresi IS NOT NULL",
        "ck.net_calisma_suresi != '0:00:00'"
    ]
    params = {"start": start_date, "end": today}

    # İş İstasyonu filtresi (Multi-select desteğiyle)
    if is_istasyonu:
        if isinstance(is_istasyonu, str):
            is_istasyonu = [s.strip() for s in is_istasyonu.split(",") if s.strip()]
        
        if is_istasyonu:
            conditions.append("ck.is_istasyonu IN %(is_istasyonu)s")
            params["is_istasyonu"] = is_istasyonu

    where_clause = " AND ".join(conditions)

    # Otomatik duraklatma sürelerini ayrıca getirip net süreye ekleyeceğiz
    # Çünkü bu duruşlar kullanıcı talebine göre 'çalışma' sayılmalı.
    rows = frappe.db.sql(
        f"""
        SELECT
            ck.operator              AS operator_id,
            ck.net_calisma_suresi    AS stored_net_sure,
            (
                SELECT IFNULL(SUM(durus_suresi), 0)
                FROM `tabOperasyon Duruslari`
                WHERE parent = ck.name 
                AND durus_nedeni = 'Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı.'
            )                        AS auto_pause_min
        FROM `tabCalisma Karti` ck
        WHERE {where_clause}
        """,
        params,
        as_dict=True,
    )

    if not rows:
        return {"labels": [], "datasets": [{"name": _("Net Çalışma (dk)"), "values": []}]}

    # Operatör → departman eşlemesi
    op_ids = list({r["operator_id"] for r in rows if r.get("operator_id")})
    emp_rows = frappe.get_all(
        "Employee",
        filters={"name": ["in", op_ids]},
        fields=["name", "department"],
        limit_page_length=len(op_ids),
    )
    dept_by_emp = {e["name"]: (e.get("department") or "Bilinmiyor") for e in emp_rows}

    # Departman → toplam dakika
    dept_totals: dict[str, float] = {}
    for row in rows:
        dept = dept_by_emp.get(row.get("operator_id"), "Bilinmiyor")
        
        # Orijinal net süre
        net_dk = _parse_duration_to_minutes(row.get("stored_net_sure"))
        
        # Otomatik duruşları net süreye 'geri ekle' (çünkü bunlar gerçek duruş sayılmıyor)
        auto_dk = float(row.get("auto_pause_min") or 0.0)
        
        total_dk = net_dk + auto_dk
        dept_totals[dept] = dept_totals.get(dept, 0.0) + total_dk

    # Sırala ve formatla
    sorted_items = sorted(dept_totals.items(), key=lambda x: x[1], reverse=True)
    labels = [item[0] for item in sorted_items]
    values = [round(item[1], 1) for item in sorted_items]

    return {
        "labels":   labels,
        "datasets": [{"name": _("Net Çalışma (dk)"), "values": values}],
    }
