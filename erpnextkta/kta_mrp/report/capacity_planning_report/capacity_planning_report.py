import frappe
from datetime import datetime, timedelta, date
from collections import defaultdict
from frappe.utils import cstr

def scrub(txt):
    return txt.lower().replace(' ', '_').replace('-', '_').replace('.', '_')

def hex_blend(color1, color2, ratio):
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16)for i in (0, 2, 4))
    def rgb_to_hex(rgb):
        return '#{:02x}{:02x}{:02x}'.format(*rgb)
    rgb1= hex_to_rgb(color1)
    rgb2= hex_to_rgb(color2)
    blended = tuple(int((1 - ratio) * c1 + ratio * c2) for c1, c2 in zip(rgb1, rgb2))
    return rgb_to_hex(blended)

def get_monday_of_current_week():
    today = datetime.today()
    return (today - timedelta(days=today.weekday())).date()

def iso_week_start(week_str):
    try:
        parts = week_str.lower().replace("w", "").split("_")
        if len(parts) == 2:
            return date.fromisocalendar(int(parts[0]), int(parts[1]), 1)
    except: return None

def execute(filters=None):
    if not filters: filters = {}
    today_monday = get_monday_of_current_week()
    from_date = filters.get("from_date")
    if from_date:
        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        if from_date_obj < today_monday:
            frappe.throw(frappe._("Geçmiş tarihler için rapor çalıştırılamaz. {0} sonrası seçiniz.").format(today_monday))
    else: from_date_obj = today_monday
    
    min_to_date = from_date_obj + timedelta(days=90)
    to_date = filters.get("to_date")
    to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date() if to_date else min_to_date

    from erpnextkta.kta_mrp.report.production_start_week.production_start_week import ProductionStartWeekReport
    today = datetime.today().date()
    psw_filters = {"from_date": (today - timedelta(days=270)).strftime("%Y-%m-%d"), "to_date": to_date_obj.strftime("%Y-%m-%d"), "group_by_item_only": 1}
    if filters.get("item_group"): psw_filters["item_group"] = filters["item_group"]

    psw_report = ProductionStartWeekReport(psw_filters)
    columns_psw, data_psw, *_ = psw_report.run()

    item_filters = {"custom_ara_malzeme_grubu": "ÜRÜN"}
    if filters.get("item_group"): item_filters["item_group"] = filters["item_group"]
    if filters.get("custom_musteri_grubu"): item_filters["custom_musteri_grubu"] = filters["custom_musteri_grubu"]
    
    item_meta = frappe.get_all("Item", filters=item_filters, fields=["name", "custom_weekly_production", "item_group", "custom_musteri_grubu"])
    item_capacity = {i.name: int(float(i.custom_weekly_production or 0)) for i in item_meta}
    item_groups = {i.name: i.item_group or "" for i in item_meta}

    week_fields = [c["fieldname"] for c in columns_psw if c.get("fieldtype") == "Int" and c["fieldname"] not in ("total", "stock_covered", "to_produce")]
    valid_weeks = [f for f in week_fields if iso_week_start(f) and iso_week_start(f) >= from_date_obj]
    
    cumulative_demand = defaultdict(lambda: defaultdict(int))
    past_totals = defaultdict(int)

    for row in data_psw:
        item = row.get("item_code")
        if not item or item not in item_capacity: continue
        for field in week_fields:
            qty = int(row.get(field, 0) or 0)
            ws = iso_week_start(field)
            if ws:
                if ws >= from_date_obj: cumulative_demand[item][field] += qty
                else: past_totals[item] += qty

    data = []
    week_totals = {f: 0 for f in valid_weeks}
    
    for item, week_qty in cumulative_demand.items():
        cap = item_capacity.get(item, 0)
        dist = {f: week_qty.get(f, 0) for f in valid_weeks}
        carry = 0
        for i in reversed(range(len(valid_weeks))):
            f = valid_weeks[i]
            if cap > 0 and dist[f] > cap:
                excess = dist[f] - cap
                dist[f] = cap
                if i > 0: dist[valid_weeks[i-1]] += excess
                else: carry += excess
        
        # Simple distribution for carry and past
        extra = carry + past_totals.get(item, 0)
        if extra > 0:
            for f in valid_weeks[:8]:
                if cap > 0 and dist[f] < cap:
                    fill = min(cap - dist[f], extra)
                    dist[f] += fill
                    extra -= fill
                if extra <= 0: break
            if extra > 0: dist[valid_weeks[0]] += extra

        row = {"item_group": item_groups.get(item), "item_code": item, "weekly_capacity": cap, "_style": {}}
        row_total = 0
        for f in valid_weeks:
            val = dist.get(f, 0)
            row[f] = val if val else None
            row_total += val
            week_totals[f] += val
            color = get_cell_color(val, cap)
            if color: row["_style"][f] = f"background-color: {color}; color: white"
        row["total"] = row_total
        data.append(row)

    total_row = {"item_group": "<b>TOPLAM</b>", "item_code": None, "weekly_capacity": None}
    for f in valid_weeks: total_row[f] = week_totals[f]
    total_row["total"] = sum(week_totals.values())
    if data: data.append(total_row)

    chart = {
        "data": {"labels": [f.replace("_", "-W") for f in valid_weeks], "datasets": [{"name": "Planlanan", "values": [week_totals[f] for f in valid_weeks]}]},
        "type": "line", "colors": ["#27ae60"]
    }
    summary = [{"value": total_row["total"], "label": "Toplam Planlanan", "indicator": "Green"}, {"value": len(data)-1, "label": "Ürün Sayısı", "indicator": "Blue"}]

    cols = get_columns() + [{"label": f.replace("_", "-W").upper(), "fieldname": f, "fieldtype": "Int", "width": 100} for f in valid_weeks] + [{"label": "Toplam", "fieldname": "total", "fieldtype": "Int", "width": 100}]
    return cols, data, None, chart, summary

def get_columns():
    return [{"label": "Ürün Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 140}, {"label": "Ürün", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180}, {"label": "Haftalık Kapasite", "fieldname": "weekly_capacity", "fieldtype": "Int", "width": 150}]

def get_cell_color(value, cap):
    if not cap or not value: return None
    if value > cap: return "#4B4B4B"
    ratio = min(value / cap, 1.0)
    return hex_blend("#90EE90", "#006400", ratio)