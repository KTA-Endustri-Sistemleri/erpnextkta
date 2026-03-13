import json
import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime


@frappe.whitelist()
def get_data(**kwargs):
    """
    Duruş nedeni bazında toplam duruş dakikası (son N gün).
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
        "od.durus_suresi > 0",
        "od.durus_nedeni IS NOT NULL",
        "od.durus_nedeni != ''",
    ]
    params = {"start": start_date, "end": today}

    if is_istasyonu:
        conditions.append("ck.is_istasyonu = %(is_istasyonu)s")
        params["is_istasyonu"] = is_istasyonu

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            od.durus_nedeni            AS neden,
            SUM(od.durus_suresi)       AS toplam_dk
        FROM `tabOperasyon Duruslari` od
        INNER JOIN `tabCalisma Karti` ck ON ck.name = od.parent
        WHERE {where_clause}
        GROUP BY od.durus_nedeni
        ORDER BY toplam_dk DESC
        """,
        params,
        as_dict=True,
    )

    labels = [r.get("neden") or "Diğer" for r in rows]
    values = [round(float(r.get("toplam_dk") or 0), 1) for r in rows]

    return {
        "labels":   labels,
        "datasets": [{"name": _("Duruş Süresi (dk)"), "values": values}],
    }
