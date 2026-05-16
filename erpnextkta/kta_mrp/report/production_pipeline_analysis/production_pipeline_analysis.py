import frappe
from frappe.utils import getdate, add_days, flt, add_months
from datetime import date, timedelta
from collections import defaultdict
import math

def execute(filters=None):
    filters = frappe._dict(filters or {})
    
    # 1. Tarih Aralığı
    today = date.today()
    from_date = getdate(filters.get("from_date")) or today
    to_date = getdate(filters.get("to_date")) or add_days(today, 90)
    
    first_week_label = normalize_week_label(get_week_label(from_date))

    # 2. Sevk Parametreleri ve Fiziksel Stok
    sevk_map = get_sevk_parametreleri_map()
    physical_stock = get_physical_stock_total(filters)

    # 3. DİNAMİK KAPASİTE TESPİTİ
    item_group = filters.get("item_group")
    defined_cap = get_item_group_capacity(item_group)
    historical_cap = get_historical_capacity(item_group)
    
    # Öncelik: Tanımlı > Geçmiş > Sınırsız
    weekly_capacity_limit = defined_cap or historical_cap or 999999

    # 4. Satış Siparişlerini Getir (Tümü)
    so_items = get_sales_order_items_full(filters)
    
    # 5. Açık İş Emirlerini (WIP) Getir
    wip_items = get_open_work_orders(item_group)

    # 6. Verileri Kategorize Et
    timeline_data = {
        "customer": defaultdict(float),
        "shipment": defaultdict(float),
        "production_theo": defaultdict(float),
        "wip": defaultdict(float),        # Devam Eden Üretim
        "balanced": defaultdict(float),   # Yeni Planlanacak
        "total_in": defaultdict(float),   # Toplam Üretim Girişi
        "stock_evolution": defaultdict(float),
        "ideal_avg": defaultdict(float),
        "delayed": defaultdict(float)
    }
    
    all_weeks = set()
    all_weeks.add(first_week_label)

    total_backlog = 0
    total_future_demand = 0
    packing_cache = {}

    # A. Talep Dağıtımı (SO)
    for item in so_items:
        raw_qty = flt(item.qty)
        customer = item.customer
        item_code = item.item_code
        
        cache_key = (item_code, customer)
        if cache_key not in packing_cache:
            p_val = frappe.db.get_value("Item Customer", 
                {"parent": item_code, "customer_name": customer}, 
                "custom_musteri_paketleme_miktari")
            packing_cache[cache_key] = flt(p_val)
            
        p_qty = packing_cache[cache_key]
        qty = raw_qty
        if p_qty > 0:
            qty = math.ceil(raw_qty / p_qty) * p_qty
        
        delivery_date = getdate(item.delivery_date)
        address = item.shipping_address_name
        params = sevk_map.get((customer, address)) or sevk_map.get((customer, None)) or {"prod": 0, "del": 0}
        
        ship_date = add_days(delivery_date, -params["del"])
        prod_date = add_days(delivery_date, -(params["del"] + params["prod"]))
        
        target_delivery = delivery_date if delivery_date >= from_date else from_date
        target_ship = ship_date if ship_date >= from_date else from_date
        target_prod = prod_date if prod_date >= from_date else from_date
        
        if ship_date < from_date:
            total_backlog += qty
        else:
            total_future_demand += qty

        w_customer = normalize_week_label(get_week_label(target_delivery))
        w_shipment = normalize_week_label(get_week_label(target_ship))
        w_production = normalize_week_label(get_week_label(target_prod))
        
        timeline_data["customer"][w_customer] += qty
        timeline_data["shipment"][w_shipment] += qty
        timeline_data["production_theo"][w_production] += qty
        all_weeks.update([w_customer, w_shipment, w_production])

    # B. Açık İş Emirlerini (WIP) Dağıt
    for wip in wip_items:
        wip_qty = flt(wip.qty) - flt(wip.produced_qty)
        if wip_qty <= 0: continue
        
        end_date = getdate(wip.planned_end_date)
        target_end = end_date if end_date >= from_date else from_date
        w_wip = normalize_week_label(get_week_label(target_end))
        
        timeline_data["wip"][w_wip] += wip_qty
        all_weeks.add(w_wip)

    # 7. Sıralı Hafta Listesi
    report_to_date_label = normalize_week_label(get_week_label(to_date))
    def week_sort_key(w):
        try:
            parts = w.split("-W")
            return (int(parts[0]), int(parts[1]))
        except: return (0, 0)
    sorted_weeks = sorted([w for w in all_weeks if "-W" in w and w >= first_week_label and w <= report_to_date_label], 
        key=week_sort_key)
    if not sorted_weeks: sorted_weeks = [first_week_label]

    # İdeal Ortalama (Açık iş emirlerini ihtiyaçtan düşüyoruz)
    total_wip = sum(timeline_data["wip"].values())
    net_total_need = (total_backlog + total_future_demand) - physical_stock - total_wip
    
    valid_p_qtys = [v for v in packing_cache.values() if v > 0]
    avg_p_qty = sum(valid_p_qtys) / len(valid_p_qtys) if valid_p_qtys else 1
    
    if net_total_need > 0:
        raw_ideal = net_total_need / len(sorted_weeks)
        ideal_avg_val = math.ceil(raw_ideal / avg_p_qty) * avg_p_qty
    else:
        ideal_avg_val = 0

    # C. Dengeleme ve Stok Evrimi
    current_inventory = physical_stock
    chart_data_cust = []
    chart_data_bal = []
    chart_data_stock_evo = []

    for w in sorted_weeks:
        ship_demand = timeline_data["shipment"].get(w, 0)
        theo_prod = timeline_data["production_theo"].get(w, 0)
        wip_qty = timeline_data["wip"].get(w, 0)
        
        # Kalan Kapasite
        available_cap = max(0, weekly_capacity_limit - wip_qty)
        
        projected_without_new_prod = current_inventory + wip_qty - ship_demand
        
        if projected_without_new_prod < 0:
            # Eksik var! Kalan kapasiteyi kullan
            needed_to_clear = abs(projected_without_new_prod)
            in_qty = min(needed_to_clear, available_cap)
            in_qty = math.ceil(in_qty / avg_p_qty) * avg_p_qty
        else:
            # Güvendeyiz, sadece teorik ihtiyaca bak
            in_qty = min(theo_prod, available_cap)
            
        timeline_data["balanced"][w] = in_qty
        timeline_data["total_in"][w] = in_qty + wip_qty
        
        current_inventory = (current_inventory + in_qty + wip_qty) - ship_demand
        timeline_data["stock_evolution"][w] = current_inventory
        timeline_data["ideal_avg"][w] = ideal_avg_val
        
        chart_data_cust.append(ship_demand)
        chart_data_bal.append(in_qty + wip_qty)
        chart_data_stock_evo.append(current_inventory)

    # 8. Rapor Tablo Verisini Oluştur
    columns = [
        {"label": "Aşama", "fieldname": "stage", "fieldtype": "Data", "width": 280},
    ] + [
        {"label": w, "fieldname": frappe.scrub(w), "fieldtype": "Float", "width": 110} for w in sorted_weeks
    ] + [
        {"label": "Toplam", "fieldname": "total", "fieldtype": "Float", "width": 120}
    ]

    stages = [
        ("customer", "1. Müşteri Beklentisi (Teslimat)"),
        ("shipment", "2. Sevkiyat Haftası (Fabrika Çıkış)"),
        ("production_theo", "3. Üretim Başlama (Teorik İhtiyaç)"),
        ("ideal_avg", "4. İdeal Haftalık Üretim (Hedef)"),
        ("wip", "5. Devam Eden Üretim (Açık İş Emirleri)"),
        ("balanced", "6. Yeni Planlanacak Üretim (Ek Kapasite)"),
        ("total_in", "7. Toplam Üretim Girişi (5 + 6)"),
        ("stock_evolution", "8. Beklenen Stok Bakiyesi (Stock Evolution)")
    ]

    data = []
    for key, label in stages:
        row = {"stage": label}
        row_total = 0
        for w in sorted_weeks:
            val = timeline_data[key].get(w, 0)
            row[frappe.scrub(w)] = val
            if key == "stock_evolution": row_total = val 
            else: row_total += val
        row["total"] = row_total
        data.append(row)

    cap_info = f"Geçmiş Veri Kapasitesi: {historical_cap or 'Yok'} | Tanımlı Kapasite: {defined_cap or 'Yok'} | Açık İ.E: {total_wip}"

    chart = {
        "data": {
            "labels": sorted_weeks,
            "datasets": [
                {"name": "Haftalık Sevkiyat", "values": chart_data_cust, "chartType": "bar"},
                {"name": "Haftalık Üretim", "values": chart_data_bal, "chartType": "bar"},
                {"name": "Stok Bakiyesi", "values": chart_data_stock_evo, "chartType": "line"},
                {"name": "Kapasite", "values": [weekly_capacity_limit] * len(sorted_weeks), "chartType": "line"}
            ]
        },
        "type": "axis-mixed",
        "colors": ["#e74c3c", "#27ae60", "#3498db", "#c0392b"]
    }

    return columns, data, f"{cap_info} | Toplam Backlog: {total_backlog}", chart, None

def get_open_work_orders(item_group):
    if not item_group: return []
    return frappe.db.sql("""
        SELECT wo.qty, wo.produced_qty, wo.planned_end_date, wo.production_item
        FROM `tabWork Order` wo
        JOIN `tabItem` item ON wo.production_item = item.name
        WHERE item.item_group = %s 
          AND wo.docstatus = 1 
          AND wo.status IN ('Not Started', 'In Process')
    """, (item_group,), as_dict=True)

def get_historical_capacity(item_group):
    if not item_group: return 0
    three_months_ago = add_months(date.today(), -3)
    res = frappe.db.sql("""
        SELECT SUM(produced_qty) as total_qty, COUNT(DISTINCT YEARWEEK(actual_end_date, 1)) as week_count
        FROM `tabWork Order` wo
        JOIN `tabItem` item ON wo.production_item = item.name
        WHERE item.item_group = %s AND wo.status = 'Completed' AND wo.docstatus = 1 AND wo.actual_end_date >= %s
    """, (item_group, three_months_ago), as_dict=True)
    if res and res[0].total_qty and res[0].week_count:
        return math.ceil(flt(res[0].total_qty) / flt(res[0].week_count))
    return 0

def get_item_group_capacity(item_group):
    if not item_group: return 0
    res = frappe.db.sql("""
        SELECT MAX(CAST(custom_weekly_production AS DECIMAL))
        FROM `tabItem` WHERE item_group = %s AND custom_weekly_production IS NOT NULL
    """, (item_group,))
    return flt(res[0][0]) if res else 0

def get_sales_order_items_full(filters):
    conditions = ["so.docstatus = 1", "soi.qty > soi.delivered_qty"]
    params = []
    if filters.get("item_group"):
        conditions.append("item.item_group = %s")
        params.append(filters.item_group)
    if filters.get("customer"):
        conditions.append("so.customer = %s")
        params.append(filters.customer)
    where_clause = " AND ".join(conditions)
    return frappe.db.sql(f"""
        SELECT soi.item_code, (soi.qty - soi.delivered_qty) as qty, soi.delivery_date, 
               so.customer, so.shipping_address_name
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON soi.parent = so.name
        JOIN `tabItem` item ON soi.item_code = item.name
        WHERE {where_clause}
    """, tuple(params), as_dict=True)

def get_physical_stock_total(filters):
    warehouse_list = filters.get("warehouses")
    item_group = filters.get("item_group")
    if not warehouse_list: return 0
    conditions = []
    params = []
    if item_group:
        conditions.append("item.item_group = %s")
        params.append(item_group)
    if warehouse_list:
        wh_placeholders = ", ".join(["%s"] * len(warehouse_list))
        conditions.append(f"bin.warehouse IN ({wh_placeholders})")
        params.extend(warehouse_list)
    where_clause = " AND ".join(conditions)
    res = frappe.db.sql(f"SELECT SUM(bin.actual_qty) FROM `tabBin` bin JOIN `tabItem` item ON bin.item_code = item.name WHERE {where_clause}", tuple(params))
    return flt(res[0][0]) if res else 0

def get_sevk_parametreleri_map():
    records = frappe.get_all("KTA Sevk Parametreleri", fields=["customer_name", "customer_address", "production_time", "delivery_time"])
    sevk_map = {}
    for r in records:
        key = (r.customer_name, r.customer_address)
        sevk_map[key] = {"prod": r.production_time or 0, "del": r.delivery_time or 0}
    return sevk_map

def normalize_week_label(label):
    if not label: return label
    label = label.replace("_", "-").upper()
    if "-W" in label:
        parts = label.split("-W")
        if len(parts) == 2:
            try: return f"{parts[0]}-W{int(parts[1]):02d}"
            except: pass
    return label

def get_week_label(date_obj):
    if not date_obj: return "N/A"
    date_obj = getdate(date_obj)
    iso_year, iso_week, _ = date_obj.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"
