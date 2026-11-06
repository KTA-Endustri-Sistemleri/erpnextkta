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
    return build_report_output(filters, build_capacity_plan(filters))


from erpnextkta.kta_mrp.mrp_engine.capacity import build_capacity_plan



def build_report_output(filters, plan):
    valid_weeks, item_groups, group_capacity = plan.valid_weeks, plan.item_groups, plan.group_capacity
    item_final_plan, item_week_demand, item_backlog = plan.plan, plan.item_week_demand, plan.item_backlog

    # 4. Verileri tablo formatına dönüştür
    data = []
    week_totals = {f: 0 for f in valid_weeks}
    for it in sorted(item_groups.keys()):
        group = item_groups[it]
        cap = group_capacity.get(group, 0)
        row = {"item_group": group, "item_code": it, "weekly_capacity": cap, "_style": {}}
        row_total = 0
        for f in valid_weeks:
            val = item_final_plan[it].get(f, 0)
            row[f] = val if val > 0 else None
            row_total += val
            week_totals[f] += val
            
            # Renklendirme
            color = get_cell_color(val, cap)
            if color: row["_style"][f] = f"background-color: {color}; color: white"
            
        row["total"] = row_total
        data.append(row)

    total_row = {"item_group": "<b>TOPLAM</b>", "item_code": None, "weekly_capacity": None}
    for f in valid_weeks: total_row[f] = week_totals[f]
    total_row["total"] = sum(week_totals.values())
    if data: data.append(total_row)

    datasets = [{"name": "Planlanan", "values": [week_totals[f] for f in valid_weeks]}]
    colors = ["#27ae60"]
    
    cfg = plan.get("settings")
    if not cfg:
        from erpnextkta.kta_mrp.mrp_engine.settings import resolve_mrp_settings
        cfg = resolve_mrp_settings(filters)

    if cfg.enable_leveling_by_default or cfg.enable_rampup_by_default:
        datasets[0]["name"] = "Planlanan (Dengelenmiş)"
        raw_week_totals = {f: 0 for f in valid_weeks}
        for it in item_groups.keys():
            for i, f in enumerate(valid_weeks):
                val = item_week_demand[it].get(f, 0)
                if i == 0:
                    val += item_backlog[it]
                raw_week_totals[f] += val
        
        datasets.append({"name": "Ham Talep (Dengelenmemiş)", "values": [raw_week_totals[f] for f in valid_weeks]})
        colors.append("#e74c3c")

    chart = {
        "data": {"labels": [f.replace("_", "-W") for f in valid_weeks], "datasets": datasets},
        "type": "line", "colors": colors
    }
    
    summary = [{"value": total_row["total"], "label": "Toplam Planlanan", "indicator": "Green"}, {"value": len(data)-1, "label": "Ürün Sayısı", "indicator": "Blue"}]

    from erpnextkta.kta_mrp.report.report_utils import get_modern_summary_html
    html_summary = get_modern_summary_html(summary)

    cols = get_columns() + [{"label": f.replace("_", "-").upper(), "fieldname": f, "fieldtype": "Int", "width": 100} for f in valid_weeks] + [{"label": "Toplam", "fieldname": "total", "fieldtype": "Int", "width": 100}]
    
    # Return exactly 6 elements to satisfy Frappe's ljust_list(res, 6)
    return cols, data, html_summary, chart, None, (plan.kanban_plan, plan.raw_mr_demands, plan.wo_plan)

def get_columns():
    return [{"label": "Ürün Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 140}, {"label": "Ürün", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180}, {"label": "Haftalık Kapasite", "fieldname": "weekly_capacity", "fieldtype": "Int", "width": 150}]

def get_cell_color(value, cap):
    if not cap or not value: return None
    if value > cap: return "#4B4B4B"
    ratio = min(value / cap, 1.0)
    return hex_blend("#90EE90", "#006400", ratio)
