import json
import frappe
from frappe import _
from frappe.utils import (
    add_days,
    getdate,
    now_datetime,
)
from datetime import timedelta

@frappe.whitelist()
def get_data(**kwargs):
    """
    Son N günün her günü için Calisma Karti durumlarını sayar.
    Filtreler: days, operasyon, is_istasyonu
    Durum grupları: Hazır, Çalışıyor, Duruşta, Bitmiş, Reddedildi
    """
    # Read directly from request form_dict to bypass Frappe typing wrappers
    raw = frappe.form_dict.get("filters") or "{}"
    try:
        filters = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        filters = {}
    if not isinstance(filters, dict):
        filters = {}

    days        = int(filters.get("days", 30))
    operasyon   = filters.get("operasyon") or None
    is_istasyonu = filters.get("is_istasyonu") or None

    today      = getdate(now_datetime())
    start_date = add_days(today, -days + 1)

    statuses = ["Hazır", "Çalışıyor", "Duruşta", "Bitmiş", "Reddedildi"]

    # Build date labels and date_list
    labels    = []
    date_list = []
    d = getdate(start_date)
    for i in range(days):
        labels.append(d.strftime("%d %b"))
        date_list.append(d)
        d = d + timedelta(days=1)

    # Build SQL with optional filters
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
            DATE(creation) AS day,
            durum,
            COUNT(*) AS cnt
        FROM `tabCalisma Karti`
        WHERE {where_clause}
        GROUP BY DATE(creation), durum
        ORDER BY day
        """,
        params,
        as_dict=True,
    )

    # Build lookup: {date_str: {status: count}}
    day_map = {dt.strftime("%Y-%m-%d"): {} for dt in date_list}
    for row in rows:
        day_str = str(row.day)
        if day_str in day_map:
            day_map[day_str][row.durum] = int(row.cnt)

    # Build datasets (one per status)
    datasets = []
    for status in statuses:
        values = []
        for dt in date_list:
            day_str = dt.strftime("%Y-%m-%d")
            values.append(day_map.get(day_str, {}).get(status, 0))
        datasets.append({
            "name":      _(status),
            "values":    values,
            "chartType": "bar",
        })

    return {
        "labels":   labels,
        "datasets": datasets,
    }
