import json
import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime


@frappe.whitelist()
def get_data(**kwargs):
    """
    Son N günde en az çalışan operatörlerin toplam net çalışma süresi (dakika).
    Filtreler: days, is_istasyonu, top_n
    net_calisma_suresi alanı 'M:SS' formatında veya benzer saklanıyor.
    """
    filters = kwargs.get("filters") or {}
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except Exception:
            filters = {}

    date_range   = filters.get("date_range")
    is_istasyonu = filters.get("is_istasyonu") or None


    if date_range and len(date_range) == 2:
        start_date = getdate(date_range[0])
        end_date   = getdate(date_range[1])
    else:
        days       = int(filters.get("days", 30))
        end_date   = getdate(now_datetime())
        start_date = add_days(end_date, -days + 1)

    # Build SQL with optional filters
    conditions = [
        "DATE(ck.baslangic_saati) >= %(start)s",
        "DATE(ck.baslangic_saati) <= %(end)s",
        "ck.docstatus != 2",
        "ck.net_calisma_suresi IS NOT NULL",
        "ck.net_calisma_suresi != ''",
    ]
    params = {"start": start_date, "end": end_date}

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
            ck.operator,
            COALESCE(emp.employee_name, ck.operator) AS operator_label,
            ck.net_calisma_suresi
        FROM `tabCalisma Karti` ck
        LEFT JOIN `tabEmployee` emp ON emp.employee_name = ck.operator
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
        minutes  = _parse_duration_to_minutes(raw_dur)
        totals[op] = totals.get(op, 0) + minutes

    # Filter out operators with <= 0 total minutes to focus on active ones who worked less
    totals = {op: mins for op, mins in totals.items() if mins > 0}

    if not totals:
        return {"labels": [], "datasets": [{"name": _("Net Dakika"), "values": []}]}

    # Sort by total minutes DESCENDING (highest minutes first)
    sorted_ops = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    labels = [labels_map[op] for op, _ in sorted_ops]
    values = [round(mins, 1) for _, mins in sorted_ops]

    avg_val = sum(values) / len(values) if values else 0

    return {
        "labels": labels,
        "datasets": [
            {
                "name":      _("Net Çalışma (dk)"),
                "values":    values,
                "chartType": "bar",
            }
        ],
        "yMarkers": [
            {
                "label": _("Ortalama ({0})").format(round(avg_val, 1)),
                "value": round(avg_val, 1),
                "lineType": "dashed",
                "options": { "labelPos": "left" }
            }
        ],
        "colors": ["#e74c3c"]
    }


def _parse_duration_to_minutes(value: str) -> float:
    """
    Convert duration string to total minutes as a float.
    Supported formats: 'HH:MM:SS', 'M:SS', 'S'.
    """
    if not value:
        return 0.0
    try:
        parts = value.split(":")
        if len(parts) == 3:
            # HH:MM:SS
            return int(parts[0]) * 60.0 + int(parts[1]) + int(parts[2]) / 60.0
        elif len(parts) == 2:
            # M:SS
            return int(parts[0]) + int(parts[1]) / 60.0
        elif len(parts) == 1:
            # Simple integer or float (e.g. minutes)
            return float(parts[0])
    except (ValueError, IndexError):
        pass
    return 0.0
