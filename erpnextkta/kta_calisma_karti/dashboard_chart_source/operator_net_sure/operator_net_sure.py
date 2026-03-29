import json
import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime


@frappe.whitelist()
def get_data(**kwargs):
    """
    Son N günde her operatörün toplam net çalışma süresi (dakika).
    Filtreler: days, is_istasyonu, top_n
    net_calisma_suresi alanı 'M:SS' formatında saklanıyor.
    """
    # Read directly from request form_dict to bypass Frappe typing wrappers
    raw = frappe.form_dict.get("filters") or "{}"
    try:
        filters = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        filters = {}
    if not isinstance(filters, dict):
        filters = {}

    days         = int(filters.get("days", 30))
    is_istasyonu = filters.get("is_istasyonu") or None
    top_n        = int(filters.get("top_n", 15))

    today      = getdate(now_datetime())
    start_date = add_days(today, -days + 1)

    # Build SQL with optional filters
    conditions = [
        "DATE(ck.creation) >= %(start)s",
        "DATE(ck.creation) <= %(end)s",
        "ck.docstatus != 2",
        "ck.net_calisma_suresi IS NOT NULL",
        "ck.net_calisma_suresi != ''",
    ]
    params = {"start": start_date, "end": today}

    if is_istasyonu:
        conditions.append("ck.is_istasyonu = %(is_istasyonu)s")
        params["is_istasyonu"] = is_istasyonu

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            ck.operator,
            COALESCE(emp.employee_name, ck.operator) AS operator_label,
            ck.net_calisma_suresi
        FROM `tabCalisma Karti` ck
        LEFT JOIN `tabEmployee` emp ON emp.name = ck.operator
        WHERE {where_clause}
        ORDER BY ck.operator
        """,
        params,
        as_dict=True,
    )

    # Parse 'M:SS' -> total minutes per operator
    totals     = {}
    labels_map = {}
    for row in rows:
        op = row.operator or _("Bilinmiyor")
        labels_map[op] = row.operator_label or op
        raw_dur  = (row.net_calisma_suresi or "").strip()
        minutes  = _parse_minsec_to_minutes(raw_dur)
        totals[op] = totals.get(op, 0) + minutes

    if not totals:
        return {"labels": [], "datasets": [{"name": _("Net Dakika"), "values": []}]}

    # Sort by total minutes desc, take top N
    sorted_ops = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:top_n]
    labels = [labels_map[op] for op, _ in sorted_ops]
    values = [round(mins, 1) for _, mins in sorted_ops]

    return {
        "labels": labels,
        "datasets": [
            {
                "name":      _("Net Çalışma (dk)"),
                "values":    values,
                "chartType": "bar",
            }
        ],
    }


def _parse_minsec_to_minutes(value: str) -> float:
    """Convert 'M:SS' string to total minutes as a float."""
    if not value:
        return 0.0
    try:
        parts = value.split(":")
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60.0
        elif len(parts) == 1:
            return float(parts[0])
    except (ValueError, IndexError):
        pass
    return 0.0
