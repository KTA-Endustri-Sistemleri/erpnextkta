import frappe
from datetime import datetime
from collections import defaultdict
from erpnextkta.kta_mrp.report.capacity_planning_report.capacity_planning_report import execute as get_capacity_plan


def execute(filters=None):
    if not filters:
        filters = {}

    today = datetime.today().date()

    # Önce filtresiz kapasite planı verisi alalım
    filters_without_item_group = {k: v for k, v in filters.items() if k != "item_group"}
    _, capacity_data = get_capacity_plan(filters_without_item_group)
    
    # Açık iş emirleri - ürün grubu filtresi uygula
    work_order_filters = {"status": ("not in", ["Cancelled", "Completed"])}
    if filters.get("item_group"):
        # Önce o ürün grubundaki ürünleri bul
        items_in_group = frappe.get_all(
            "Item",
            filters={"item_group": filters["item_group"]},
            fields=["name"]
        )
        item_names = [item.name for item in items_in_group]
        if item_names:
            work_order_filters["production_item"] = ("in", item_names)
        else:
            work_order_filters["production_item"] = "non_existent_item"  # Hiç sonuç dönmesin
    
    work_orders = frappe.get_all(
        "Work Order",
        filters=work_order_filters,
        fields=["production_item", "planned_start_date", "qty", "produced_qty"]
    )

    # Tüm item_code'ları topla
    item_codes = {row.get("item_code") for row in capacity_data if row.get("item_code")}
    item_codes.update({wo.get("production_item") for wo in work_orders if wo.get("production_item")})

    # item_code -> item_group eşlemesi
    item_group_map = {}
    if item_codes:
        item_group_data = frappe.get_all(
            "Item",
            filters={"name": ("in", list(item_codes))},
            fields=["name", "item_group"]
        )
        item_group_map = {item.name: item.item_group for item in item_group_data}

    # Planlanan üretim haritası
    planned_map = defaultdict(dict)
    for row in capacity_data:
        item = row.get("item_code")
        if not item:
            continue
        
        # Ürün grubu filtresi varsa burada uygula
        item_group = item_group_map.get(item)
        if filters.get("item_group") and filters["item_group"] != item_group:
            continue
            
        # Tüm hafta sütunlarını kontrol et
        for key, val in row.items():
            if key.startswith("w") and "_" in key:
                planned_map[item][key] = val or 0

    # Açık iş emirleri gruplanıyor
    past_remaining_by_item = defaultdict(int)
    future_remaining_by_item_week = defaultdict(lambda: defaultdict(int))

    for wo in work_orders:
        item = wo.get("production_item")
        remaining = (wo.get("qty") or 0) - (wo.get("produced_qty") or 0)
        if not item or remaining <= 0:
            continue

        start_date = wo.get("planned_start_date")
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()

        if not start_date:
            continue

        if start_date < today:
            past_remaining_by_item[item] += remaining
        else:
            iso_year, iso_week, _ = start_date.isocalendar()
            week_key = f"w{iso_week}_{iso_year}"
            future_remaining_by_item_week[item][week_key] += remaining

    # Rapor satırlarını oluştur
    result = []
    all_items = set(planned_map.keys()) | set(future_remaining_by_item_week.keys()) | set(past_remaining_by_item.keys())

    for item in all_items:
        item_group = item_group_map.get(item)

        past_remaining = past_remaining_by_item.get(item, 0)
        all_weeks = set(planned_map[item].keys()) | set(future_remaining_by_item_week[item].keys())

        for key in sorted(all_weeks):
            if not key.startswith("w") or "_" not in key:
                continue
            try:
                week_number, year = key[1:].split("_")
                if not week_number.isdigit():
                    continue
            except Exception:
                continue

            planned_qty = planned_map[item].get(key, 0)
            future_open = future_remaining_by_item_week[item].get(key, 0)

            # Sadece anlamlı verileri göster
            if planned_qty == 0 and future_open == 0:
                continue

            formatted_week = f"W{int(week_number)} {year}"
            open_qty = future_open

            if past_remaining > 0:
                needed = max(planned_qty - open_qty, 0)
                use_from_past = min(needed, past_remaining)
                open_qty += use_from_past
                past_remaining -= use_from_past

            required_qty = max(planned_qty - open_qty, 0)

            result.append({
                "item_group": item_group,
                "item_code": item,
                "week": formatted_week,
                "planned_qty": planned_qty,
                "open_workorder_qty": open_qty,
                "required_workorder_qty": required_qty
            })

    return get_columns(), result


def get_columns():
    return [
        {"label": "Ürün Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 140},
        {"label": "Ürün", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
        {"label": "Hafta", "fieldname": "week", "fieldtype": "Data", "width": 100},
        {"label": "Planlanan Üretim", "fieldname": "planned_qty", "fieldtype": "Int", "width": 180},
        {"label": "Açık İş Emri Miktarı", "fieldname": "open_workorder_qty", "fieldtype": "Int", "width": 180},
        {"label": "Yeni İş Emri İhtiyacı", "fieldname": "required_workorder_qty", "fieldtype": "Int", "width": 180}
    ]


@frappe.whitelist()
def get_available_item_groups(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)

    # Önce kapasite planından item_group'ları al
    _, capacity_data = get_capacity_plan(filters or {})
    item_codes = {row.get("item_code") for row in capacity_data if row.get("item_code")}
    
    # Açık iş emirlerinden de item_code'ları al
    work_orders = frappe.get_all(
        "Work Order",
        filters={"status": ("not in", ["Cancelled", "Completed"])},
        fields=["production_item"]
    )
    item_codes.update({wo.get("production_item") for wo in work_orders if wo.get("production_item")})
    
    # Tüm item_group'ları getir
    if item_codes:
        item_groups = frappe.get_all(
            "Item",
            filters={"name": ("in", list(item_codes))},
            fields=["item_group"],
            distinct=True
        )
        return sorted([ig.item_group for ig in item_groups if ig.item_group])
    
    return []