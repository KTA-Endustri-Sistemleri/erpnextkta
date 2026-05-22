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
        if isinstance(from_date, str):
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        else:
            from_date_obj = from_date
        if from_date_obj < today_monday:
            frappe.throw(frappe._("Geçmiş tarihler için rapor çalıştırılamaz. {0} sonrası seçiniz.").format(today_monday))
    else: from_date_obj = today_monday
    
    min_to_date = from_date_obj + timedelta(days=90)
    to_date = filters.get("to_date")
    if to_date:
        if isinstance(to_date, str):
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        else:
            to_date_obj = to_date
    else:
        to_date_obj = min_to_date

    from erpnextkta.kta_mrp.report.production_start_week.production_start_week import ProductionStartWeekReport
    today = datetime.today().date()
    psw_filters = {"from_date": (today - timedelta(days=270)).strftime("%Y-%m-%d"), "to_date": to_date_obj.strftime("%Y-%m-%d"), "group_by_item_only": 1}
    if filters.get("item_group"): psw_filters["item_group"] = filters["item_group"]

    psw_report = ProductionStartWeekReport(psw_filters)
    columns_psw, data_psw, *_ = psw_report.run()

    # 1. Başlangıç verilerini hazırla
    item_filters = {"custom_ara_malzeme_grubu": "ÜRÜN"}
    if filters.get("item_group"): item_filters["item_group"] = filters["item_group"]
    if filters.get("custom_musteri_grubu"): item_filters["custom_musteri_grubu"] = filters["custom_musteri_grubu"]
    
    item_meta = frappe.get_all("Item", filters=item_filters, fields=["name", "custom_weekly_production", "item_group"])
    item_groups = {i.name: i.item_group or "Diğer" for i in item_meta}
    
    # Grup bazlı kapasiteyi belirle
    group_capacity = {}
    for i in item_meta:
        group = i.item_group or "Diğer"
        cap = int(float(i.custom_weekly_production or 0))
        if group not in group_capacity or cap > group_capacity[group]:
            group_capacity[group] = cap

    week_fields = [c["fieldname"] for c in columns_psw if c.get("fieldtype") == "Int" and c["fieldname"] not in ("total", "stock_covered", "to_produce")]
    valid_weeks = [f for f in week_fields if iso_week_start(f) and iso_week_start(f) >= from_date_obj]
    
    # 2. Talepleri topla
    item_week_demand = defaultdict(lambda: defaultdict(int))
    item_backlog = defaultdict(int) # Ürün bazlı geçmiş yük

    for row in data_psw:
        item = row.get("item_code")
        if not item or item not in item_groups: continue
        
        for field in week_fields:
            qty = int(row.get(field, 0) or 0)
            ws = iso_week_start(field)
            if ws:
                if ws >= from_date_obj:
                    item_week_demand[item][field] += qty
                else:
                    item_backlog[item] += qty

    # 2.5 Ramp-up (Geriye Dönük Dengeleme / Önden Üretim)
    if filters.get("ramp_up_aktif"):
        ramp_weeks = int(filters.get("ramp_up_weeks") or 3)
        if ramp_weeks < 1: ramp_weeks = 1
        
        for w in reversed(range(1, len(valid_weeks))):
            curr_w = valid_weeks[w]
            prev_w = valid_weeks[w-1]
            
            for group, cap in group_capacity.items():
                if cap <= 0: continue
                items = [it for it, gr in item_groups.items() if gr == group]
                curr_load = sum(item_week_demand[it][curr_w] for it in items)
                prev_load = sum(item_week_demand[it][prev_w] for it in items)
                
                # Gelecek hafta yoğunluğu ile bu hafta arasındaki farkı dengele (Kullanıcı Tanımlı Ramp-up)
                max_step = cap / ramp_weeks # Haftalık artış hızı
                
                if curr_load > prev_load + max_step:
                    # Aradaki farkı kapatmak için önden üretim miktarını hesapla
                    # Sadece bir önceki haftanın kapasitesini (%90) aşmayacak kadar çek
                    move_qty = min(curr_load - (prev_load + max_step), (cap * 0.9) - prev_load)
                    
                    if move_qty > 10:
                        for it in items:
                            if curr_load > 0:
                                share = round(move_qty * (item_week_demand[it][curr_w] / curr_load))
                                item_week_demand[it][curr_w] -= share
                                item_week_demand[it][prev_w] += share

    # 3. Dengeleme Algoritması (Item-Based Forward Planning)
    dengeleme_aktif = filters.get("dengeleme_yapilsin", 0)
    item_final_plan = defaultdict(lambda: defaultdict(int))
    
    # Her ürün için devreden miktar (Backlog ile başlar)
    item_carry_over = item_backlog.copy()

    for week in valid_weeks:
        # Önce grupları grupla (Haftalık kapasite kısıtını uygulamak için)
        processed_groups = set()
        for it, group in item_groups.items():
            if group in processed_groups: continue
            processed_groups.add(group)
            
            cap = group_capacity.get(group, 0)
            items_in_group = [i for i, g in item_groups.items() if g == group]
            
            # Bu gruptaki tüm kalemlerin bu haftaki TOPLAM yükü (Kalan backlog + Bu hafta yeni talep)
            item_total_loads = {}
            total_group_load = 0
            for i in items_in_group:
                load = item_carry_over[i] + item_week_demand[i].get(week, 0)
                item_total_loads[i] = load
                total_group_load += load

            if dengeleme_aktif:
                # --- AKILLI DENGELEME (FIFO + KRİTİKLİK) ---
                remaining_cap = cap
                
                # A. ÖNCE BACKLOG (GEÇMİŞ YÜK) BİTİRİLECEK
                total_item_backlogs = {i: item_carry_over[i] for i in items_in_group if item_carry_over[i] > 0}
                sum_backlog = sum(total_item_backlogs.values())
                
                if sum_backlog > 0 and remaining_cap > 0:
                    backlog_to_produce = min(sum_backlog, remaining_cap)
                    for i in items_in_group:
                        if i in total_item_backlogs:
                            # Backlog dağıtımı (Kritiklik eklenmiş: Çok biriken daha çok pay alır)
                            share = round(backlog_to_produce * (total_item_backlogs[i] / sum_backlog))
                            item_final_plan[i][week] += share
                            item_carry_over[i] -= share
                            remaining_cap -= share
                    
                # B. KALAN KAPASİTE VARSA CARİ HAFTA TALEBİNE GEÇİLECEK
                total_item_current_demands = {i: item_week_demand[i].get(week, 0) for i in items_in_group if item_week_demand[i].get(week, 0) > 0}
                sum_current = sum(total_item_current_demands.values())
                
                if sum_current > 0 and remaining_cap > 0:
                    current_to_produce = min(sum_current, remaining_cap)
                    for i in items_in_group:
                        if i in total_item_current_demands:
                            share = round(current_to_produce * (total_item_current_demands[i] / sum_current))
                            item_final_plan[i][week] += share
                            # Üretilemeyen cari talep bir sonraki haftaya devrolur
                            remaining_current = total_item_current_demands[i] - share
                            item_carry_over[i] += remaining_current
                            remaining_cap -= share
                else:
                    # Kalan tüm cari talepler devrolur
                    for i in items_in_group:
                        item_carry_over[i] += item_week_demand[i].get(week, 0)

            else:
                # Dengeleme kapalıysa backlog'u sadece ilk haftaya ekle ve kapasiteyi aşsa da yaz
                for i in items_in_group:
                    val = item_carry_over[i] + item_week_demand[i].get(week, 0)
                    if week != valid_weeks[0]:
                        val = item_week_demand[i].get(week, 0)
                    item_final_plan[i][week] = val

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