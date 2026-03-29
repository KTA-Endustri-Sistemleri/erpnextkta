import json
import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime


@frappe.whitelist()
def get_data(**kwargs):
    """
    Kalite Kontrol durumlarına göre kart sayısı (son N gün).
    Filtreler: days, operasyon, is_istasyonu
    """
    raw = frappe.form_dict.get("filters") or "{}"
    try:
        filters = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        filters = {}
    if not isinstance(filters, dict):
        filters = {}

    days         = int(filters.get("days", 30))
    operasyon    = filters.get("operasyon") or None
    is_istasyonu = filters.get("is_istasyonu") or None

    today      = getdate(now_datetime())
    start_date = add_days(today, -days + 1)

    conditions = [
        "DATE(creation) >= %(start)s",
        "DATE(creation) <= %(end)s",
        "docstatus != 2",
    ]
    params = {"start": start_date, "end": today}

    if operasyon:
        conditions.append("operasyon = %(operasyon)s")
        params["operasyon"] = operasyon

    if is_istasyonu:
        conditions.append("is_istasyonu = %(is_istasyonu)s")
        params["is_istasyonu"] = is_istasyonu

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(kalite_kontrol), ''), 'Onay Bekliyor') AS kk,
            COUNT(*) AS cnt
        FROM `tabCalisma Karti`
        WHERE {where_clause}
        GROUP BY kk
        ORDER BY cnt DESC
        """,
        params,
        as_dict=True,
    )

    # Sabit sıra: Onay Bekliyor → Onaylandı → Reddedildi
    order = ["Onay Bekliyor", "Onaylandı", "Reddedildi"]
    row_map = {r["kk"]: int(r["cnt"]) for r in rows}

    labels = []
    values = []
    for kk in order:
        if kk in row_map:
            labels.append(_(kk))
            values.append(row_map[kk])
    # Bilinmeyen değerler varsa ekle
    for kk, cnt in row_map.items():
        if kk not in order:
            labels.append(kk)
            values.append(cnt)

    return {
        "labels":   labels,
        "datasets": [{"name": _("Kart Sayısı"), "values": values}],
    }
