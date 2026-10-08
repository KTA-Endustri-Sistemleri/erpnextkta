import frappe
from datetime import datetime
from collections import defaultdict
from erpnextkta.kta_mrp.report.capacity_planning_report.capacity_planning_report import execute as get_capacity_plan

def execute(filters=None):
    if not filters: filters = {}
    today = datetime.today().date()
    
    capacity_result = get_capacity_plan(filters)
    capacity_data = capacity_result[1]
    
    extra_data = capacity_result[5] if len(capacity_result) > 5 else None
    if isinstance(extra_data, tuple) and len(extra_data) >= 3:
        planned_kanban_map, raw_mr_demands, wo_plan = extra_data[:3]
    elif isinstance(extra_data, tuple) and len(extra_data) == 2:
        planned_kanban_map, raw_mr_demands = extra_data
        wo_plan = {}
    else:
        planned_kanban_map = extra_data if extra_data else defaultdict(dict)
        raw_mr_demands = defaultdict(dict)
        wo_plan = {}

    if not raw_mr_demands: raw_mr_demands = defaultdict(dict)
    
    wo_filters = {"docstatus": 1, "status": ("in", ["In Process", "Not Started"])}
    item_filters = {"custom_ara_malzeme_grubu": "ÜRÜN"}
    if filters.get("item_group"): item_filters["item_group"] = filters["item_group"]
    if filters.get("custom_musteri_grubu"): item_filters["custom_musteri_grubu"] = filters["custom_musteri_grubu"]

    if item_filters:
        items = frappe.get_all("Item", filters=item_filters, pluck="name")
        wo_filters["production_item"] = ("in", items) if items else "non_existent"
    
    work_orders = frappe.get_all("Work Order", filters=wo_filters, fields=["production_item", "planned_start_date", "qty", "produced_qty"])
    item_codes = {r.get("item_code") for r in capacity_data if r.get("item_code")}
    item_codes.update({wo.production_item for wo in work_orders})
    item_codes.update(raw_mr_demands.keys())
    
    item_group_map = {i.name: i.item_group for i in frappe.get_all("Item", filters={"name": ("in", list(item_codes))}, fields=["name", "item_group"])} if item_codes else {}

    planned_map = defaultdict(dict)
    for row in capacity_data:
        item = row.get("item_code")
        if not item: continue
        for k, v in row.items():
            if "_w" in k: planned_map[item][k] = v or 0

    past_rem = defaultdict(int)
    future_rem = defaultdict(lambda: defaultdict(int))
    for wo in work_orders:
        rem = (wo.qty or 0) - (wo.produced_qty or 0)
        if rem <= 0 or not wo.planned_start_date: continue
        sd = getdate(wo.planned_start_date)
        if sd < today: past_rem[wo.production_item] += rem
        else:
            iso_year, iso_week, _ = sd.isocalendar()
            future_rem[wo.production_item][f"{iso_year}_w{iso_week:02d}"] += rem

    data = []
    all_items = set(planned_map.keys()) | set(future_rem.keys()) | set(past_rem.keys()) | set(planned_kanban_map.keys())
    week_agg = defaultdict(lambda: {"p": 0, "k": 0, "o": 0, "r": 0})

    for item in all_items:
        ig = item_group_map.get(item)
        p_rem = past_rem.get(item, 0)
        all_w = set(planned_map[item].keys()) | set(future_rem[item].keys()) | set(planned_kanban_map.get(item, {}).keys())
        for k in sorted(all_w):
            if "_w" not in k: continue
            p_qty, f_open = planned_map[item].get(k, 0), future_rem[item].get(k, 0)
            kanban_qty = planned_kanban_map.get(item, {}).get(k, 0)
            
            if p_qty == 0 and f_open == 0 and kanban_qty == 0: continue
            
            # Since p_qty includes kanban_qty and wo_qty (from capacity report), we can separate them for display
            wo_qty = wo_plan.get(item, {}).get(k, 0) if wo_plan else 0
            sales_qty = max(0, p_qty - kanban_qty - wo_qty)
            
            o_qty = f_open
            if p_rem > 0:
                use = min(max(p_qty - o_qty, 0), p_rem)
                o_qty += use
                p_rem -= use
            
            r_qty = max(p_qty - o_qty, 0)
            fmt_w = k.replace("_w", "-W").upper()
            data.append({"item_group": ig, "item_code": item, "week": fmt_w, "planned_qty": sales_qty, "kanban_qty": kanban_qty, "open_workorder_qty": o_qty, "required_workorder_qty": r_qty})
            week_agg[fmt_w]["p"] += sales_qty
            week_agg[fmt_w]["k"] += kanban_qty
            week_agg[fmt_w]["o"] += o_qty
            week_agg[fmt_w]["r"] += r_qty

    sorted_w = sorted(week_agg.keys())
    chart = {
        "data": {"labels": sorted_w, "datasets": [
            {"name": "Planlanan Satış", "values": [week_agg[w]["p"] for w in sorted_w]},
            {"name": "Kanban (MR)", "values": [week_agg[w]["k"] for w in sorted_w]},
            {"name": "Açık İş Emri", "values": [week_agg[w]["o"] for w in sorted_w]},
            {"name": "Yeni İhtiyaç", "values": [week_agg[w]["r"] for w in sorted_w]}
        ]},
        "type": "bar", "colors": ["#27ae60", "#f39c12", "#3498db", "#e74c3c"]
    }
    
    total_req = sum(w["r"] for w in week_agg.values())
    summary = [{"value": total_req, "label": "Toplam Yeni İş Emri İhtiyacı", "indicator": "Red"}, {"value": len(data), "label": "Planlama Satırı", "indicator": "Blue"}]

    from erpnextkta.kta_mrp.report.report_utils import get_modern_summary_html
    html_summary = get_modern_summary_html(summary)

    return get_columns(), data, html_summary, chart, None

def get_columns():
    return [{"label": "Ürün Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 140}, {"label": "Ürün", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180}, {"label": "Hafta", "fieldname": "week", "fieldtype": "Data", "width": 100}, {"label": "Planlanan Satış", "fieldname": "planned_qty", "fieldtype": "Int", "width": 130}, {"label": "Kanban Talebi (MR)", "fieldname": "kanban_qty", "fieldtype": "Int", "width": 150}, {"label": "Açık İş Emri Miktarı", "fieldname": "open_workorder_qty", "fieldtype": "Int", "width": 150}, {"label": "Yeni İş Emri İhtiyacı", "fieldname": "required_workorder_qty", "fieldtype": "Int", "width": 160}]

def getdate(d):
    if isinstance(d, str): return datetime.strptime(d, "%Y-%m-%d").date()
    if isinstance(d, datetime): return d.date()
    return d