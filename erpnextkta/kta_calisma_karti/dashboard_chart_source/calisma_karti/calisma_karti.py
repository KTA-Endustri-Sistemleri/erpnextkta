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

    date_range  = filters.get("date_range")
    operasyon   = filters.get("operasyon") or None
    is_istasyonu = filters.get("is_istasyonu") or None

    if date_range and len(date_range) == 2:
        start_date = getdate(date_range[0])
        end_date   = getdate(date_range[1])
    else:
        days       = int(filters.get("days", 30))
        end_date   = getdate(now_datetime())
        start_date = add_days(end_date, -days + 1)

    statuses = ["Hazır", "Çalışıyor", "Duruşta", "Bitmiş", "Reddedildi"]

    # Build date labels and date_list
    labels    = []
    date_list = []
    curr_date = start_date
    while curr_date <= end_date:
        labels.append(curr_date.strftime("%d %b"))
        date_list.append(curr_date)
        curr_date = add_days(curr_date, 1)

    # Build SQL with optional filters
    conditions = [
        "DATE(creation) >= %(start)s",
        "DATE(creation) <= %(end)s",
        "docstatus != 2",
    ]
    params = {"start": start_date, "end": end_date}

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
