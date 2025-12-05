import frappe
from datetime import datetime, timedelta
from collections import defaultdict
import math

def execute(filters=None):
    if not filters:
        filters = {}

    from erpnextkta.kta_mrp.report.material_requirement import material_requirement

    _, raw_data = material_requirement.execute({
        "stage": "Stokları Düş + PO Teslimatlarını Düş",
        "group_by": "Sadece Hammadde",
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date")
    })

    item_needs_by_week = defaultdict(lambda: defaultdict(float))

    for row in raw_data:
        item = row["hammadde"]
        uom = row["uom"]
        for key, val in row.items():
            if key.startswith("W") and isinstance(val, (int, float)):
                item_needs_by_week[(item, uom)][key] += val

    result_map = defaultdict(lambda: defaultdict(float))
    metadata_map = {}

    for (item_code, uom), weekly_needs in item_needs_by_week.items():
        default_supplier = frappe.db.get_value("Item Default", {"parent": item_code}, "default_supplier")
        if not default_supplier:
            continue

        item_price = frappe.get_value("Item Price", {
            "item_code": item_code,
            "supplier": default_supplier,
            "buying": 1
        }, [
            "lead_time_days",
            "custom_minimum_order_quantity",
            "custom_minimum_paketleme_miktari"
        ], as_dict=True)

        if not item_price:
            continue

        lead_time = item_price.lead_time_days or 0
        moq = item_price.custom_minimum_order_quantity or 1
        paket = item_price.custom_minimum_paketleme_miktari or 1

        metadata_map[(item_code, uom, default_supplier)] = {
            "lead_time_days": lead_time,
            "moq": moq,
            "paket": paket
        }

        weeks = sorted(weekly_needs.keys(), key=lambda w: datetime.strptime(w + "-1", "W%W %Y-%w"))
        remaining = dict(weekly_needs)
        last_week_in_scope = weeks[-1]

        i = 0
        while i < len(weeks):
            w = weeks[i]
            qty = remaining.get(w, 0)
            if qty <= 0:
                i += 1
                continue

            # MOQ altıysa tamamlamaya çalış
            if qty < moq and w != last_week_in_scope:
                j = i + 1
                while qty < moq and j < len(weeks):
                    next_w = weeks[j]
                    next_qty = remaining.get(next_w, 0)
                    ek = min(next_qty, moq - qty)
                    qty += ek
                    remaining[next_w] = max(0, next_qty - ek)
                    j += 1

            order_qty = max(moq, math.ceil(qty / paket) * paket)

            # Paketleme tamamlaması
            if order_qty > qty and w != last_week_in_scope:
                difference = order_qty - qty
                j = i + 1
                while difference > 0 and j < len(weeks):
                    next_w = weeks[j]
                    next_qty = remaining.get(next_w, 0)
                    ek = min(next_qty, difference)
                    difference -= ek
                    remaining[next_w] = max(0, next_qty - ek)
                    j += 1

            # Zorlama MOQ tamamlama (sonraki haftalarda veri yoksa)
            if qty < moq and order_qty == qty and w != last_week_in_scope:
                order_qty = moq

            need_week = datetime.strptime(w + "-1", "W%W %Y-%w")
            order_date = need_week - timedelta(days=lead_time)
            week_num = f"{order_date.isocalendar()[1]:02d}"
            order_week = f"W{week_num} {order_date.isocalendar()[0]}"

            result_map[(item_code, uom, default_supplier)][order_week] += order_qty
            remaining[w] = 0
            i += 1

    def week_sort_key(week_str):
        try:
            week_part, year_part = week_str.split()
            week_num = int(week_part[1:])
            year_num = int(year_part)
            return (year_num, week_num)
        except:
            return (9999, 9999)

    all_weeks = sorted({week for item in result_map for week in result_map[item]}, key=week_sort_key)

    columns = [
        {"label": "Hammadde", "fieldname": "hammadde", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "Tedarikçi", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
        {"label": "Birim", "fieldname": "uom", "fieldtype": "Data", "width": 80},
        {"label": "Lead Time (Gün)", "fieldname": "lead_time_days", "fieldtype": "Int", "width": 100},
        {"label": "MOQ", "fieldname": "moq", "fieldtype": "Float", "width": 80},
        {"label": "Paket Miktarı", "fieldname": "paket", "fieldtype": "Float", "width": 100},
    ] + [
        {"label": week, "fieldname": week, "fieldtype": "Float", "width": 100}
        for week in all_weeks
    ] + [
        {"label": "Satır Toplamı", "fieldname": "row_total", "fieldtype": "Float", "width": 120}
    ]

    # Dip toplam için haftalık toplamları hesapla
    week_totals = {week: 0 for week in all_weeks}
    grand_total = 0

    data = []
    for (item, uom, supplier), week_map in result_map.items():
        meta = metadata_map.get((item, uom, supplier), {})
        row = {
            "hammadde": item,
            "uom": uom,
            "supplier": supplier,
            "lead_time_days": meta.get("lead_time_days", 0),
            "moq": meta.get("moq", 0),
            "paket": meta.get("paket", 0)
        }
        
        # Satır toplamını hesapla
        row_total = 0
        for week in all_weeks:
            week_value = round(week_map.get(week, 0), 2)
            row[week] = week_value
            row_total += week_value
            week_totals[week] += week_value
        
        row["row_total"] = round(row_total, 2)
        grand_total += row_total
        data.append(row)

    # Dip toplam satırını ekle
    total_row = {
        "hammadde": "<b>TOPLAM</b>",
        "supplier": "",
        "uom": "",
        "lead_time_days": "",
        "moq": "",
        "paket": ""
    }
    
    for week in all_weeks:
        total_row[week] = round(week_totals[week], 2)
    
    total_row["row_total"] = round(grand_total, 2)
    data.append(total_row)

    return columns, data