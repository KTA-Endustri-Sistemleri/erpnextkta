import json
import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime


@frappe.whitelist()
def get_data(**kwargs):
    """
    Her KTA operasyonu için toplam tamamlanan_miktar (son N gün, Bitmiş kartlar).
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
        "ck.durum = 'Bitmiş'",
        "ck.tamamlanan_miktar > 0",
    ]
    params = {"start": start_date, "end": today}

    if is_istasyonu:
        conditions.append("ck.is_istasyonu = %(is_istasyonu)s")
        params["is_istasyonu"] = is_istasyonu

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            ck.operasyon          AS operasyon_id,
            op.calisma_karti_op   AS operasyon_label,
            SUM(ck.tamamlanan_miktar) AS toplam_miktar
        FROM `tabCalisma Karti` ck
        LEFT JOIN `tabKTA Calisma Karti Operasyonlari` op
            ON op.name = ck.operasyon
        WHERE {where_clause}
        GROUP BY ck.operasyon
        ORDER BY toplam_miktar DESC
        LIMIT 20
        """,
        params,
        as_dict=True,
    )

    labels  = [r.get("operasyon_label") or r.get("operasyon_id") or "?" for r in rows]
    values  = [int(r.get("toplam_miktar") or 0) for r in rows]

    return {
        "labels":   labels,
        "datasets": [{"name": _("Tamamlanan Miktar"), "values": values}],
    }
