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
    filters = kwargs.get("filters") or {}
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}

    days         = int(filters.get("days", 30))
    is_istasyonu = filters.get("is_istasyonu") or None

    today      = getdate(now_datetime())
    start_date = add_days(today, -days + 1)

    conditions = [
        "DATE(ck.creation) >= %(start)s",
        "DATE(ck.creation) <= %(end)s",
        "ck.docstatus != 2",
        "aok.adet > 0",
    ]
    params = {"start": start_date, "end": today}

    if is_istasyonu:
        if isinstance(is_istasyonu, str):
            is_istasyonu = [s.strip() for s in is_istasyonu.split(",") if s.strip()]
        if is_istasyonu:
            conditions.append("ck.is_istasyonu IN %(is_istasyonu)s")
            params["is_istasyonu"] = is_istasyonu

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            aok.alt_operasyon    AS alt_op_id,
            ao.title             AS alt_op_label,
            SUM(aok.adet)        AS toplam_miktar
        FROM `tabCalisma Karti Alt Operasyon Kayitlari` aok
        JOIN `tabCalisma Karti` ck ON ck.name = aok.parent
        JOIN `tabKTA Calisma Karti Alt Operasyonlari` ao ON ao.name = aok.alt_operasyon
        WHERE {where_clause}
        GROUP BY aok.alt_operasyon
        ORDER BY toplam_miktar DESC
        LIMIT 20
        """,
        params,
        as_dict=True,
    )

    labels  = [r.get("alt_op_label") or r.get("alt_op_id") or "?" for r in rows]
    values  = [int(r.get("toplam_miktar") or 0) for r in rows]

    return {
        "labels":   labels,
        "datasets": [{"name": _("Tamamlanan Miktar"), "values": values}],
    }
