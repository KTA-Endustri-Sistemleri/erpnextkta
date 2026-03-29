import json
import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime


def _parse_minsec_to_minutes(value: str) -> float:
    """'M:SS' formatını dakikaya çevirir."""
    if not value:
        return 0.0
    s = str(value).strip()
    if ":" not in s:
        return 0.0
    parts = s.split(":", 1)
    try:
        return int(parts[0]) + int(parts[1]) / 60.0
    except Exception:
        return 0.0


@frappe.whitelist()
def get_data(**kwargs):
    """
    Departman bazında toplam net çalışma süresi (son N gün, dakika).
    Employee.department bilgisi join ile getirilir.
    Filtreler: days
    """
    raw = frappe.form_dict.get("filters") or "{}"
    try:
        filters = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        filters = {}
    if not isinstance(filters, dict):
        filters = {}

    days = int(filters.get("days", 30))

    today      = getdate(now_datetime())
    start_date = add_days(today, -days + 1)

    # Bitmiş kartları getir (net_calisma_suresi dolu olanlar)
    rows = frappe.db.sql(
        """
        SELECT
            ck.operator              AS operator_id,
            ck.net_calisma_suresi    AS net_sure
        FROM `tabCalisma Karti` ck
        WHERE
            DATE(ck.creation) >= %(start)s
            AND DATE(ck.creation) <= %(end)s
            AND ck.docstatus != 2
            AND ck.net_calisma_suresi IS NOT NULL
            AND ck.net_calisma_suresi != ''
            AND ck.net_calisma_suresi != '0:00'
            AND ck.operator IS NOT NULL
        """,
        {"start": start_date, "end": today},
        as_dict=True,
    )

    if not rows:
        return {"labels": [], "datasets": [{"name": _("Net Çalışma (dk)"), "values": []}]}

    # Operatör → departman eşlemesi (tek sorgu)
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
        dk = _parse_minsec_to_minutes(row.get("net_sure"))
        dept_totals[dept] = dept_totals.get(dept, 0.0) + dk

    # Büyükten küçüğe sırala
    sorted_items = sorted(dept_totals.items(), key=lambda x: x[1], reverse=True)

    labels = [item[0] for item in sorted_items]
    values = [round(item[1], 1) for item in sorted_items]

    return {
        "labels":   labels,
        "datasets": [{"name": _("Net Çalışma (dk)"), "values": values}],
    }
