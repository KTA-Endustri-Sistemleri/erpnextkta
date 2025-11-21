import frappe
from datetime import datetime, timedelta
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
    start = today - timedelta(days=today.weekday())  # Pazartesi
    return start.date()

def iso_week_start(week_str):
    try:
        week_parts = week_str.lower().replace("w", "").split("_")
        if len(week_parts) == 2:
            week_number, year = int(week_parts[0]), int(week_parts[1])
            return datetime.strptime(f"{year}-W{week_number}-1", "%Y-W%W-%w").date()
    except:
        return None

def execute(filters=None):
    if not filters:
        filters = {}

    today_monday = get_monday_of_current_week()

    from_date = filters.get("from_date")
    if from_date:
        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        if from_date_obj < today_monday:
            frappe.throw(frappe._(
                "⛔ Geçmiş tarihler için rapor çalıştırılamaz. Lütfen bu haftaya ({0}) veya daha ileri bir tarihe ait bir başlangıç tarihi seçiniz."
            ).format(today_monday.strftime("%d.%m.%Y")))
    else:
        from_date_obj = today_monday
        filters["from_date"] = today_monday.strftime("%Y-%m-%d")

    min_to_date = from_date_obj + timedelta(days=90)

    to_date = filters.get("to_date")
    if to_date:
        to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        if to_date_obj < min_to_date:
            frappe.throw(frappe._(
                "⛔ Bitiş tarihi, başlangıç tarihinden itibaren en az 3 ay (90 gün) ileri olmalıdır.\n\n"
                "Başlangıç: {0} → En erken bitiş: {1}"
            ).format(
                from_date_obj.strftime("%d.%m.%Y"),
                min_to_date.strftime("%d.%m.%Y")
            ))
    else:
        to_date_obj = min_to_date
        filters["to_date"] = min_to_date.strftime("%Y-%m-%d")

    columns = get_columns()
    data = []

    from erpnextkta.kta_mrp.report.production_start_week.production_start_week import ProductionStartWeekReport

    today = datetime.today().date()
    psw_filters = {
        "from_date": (today - timedelta(days=270)).strftime("%Y-%m-%d"),
        "to_date": filters["to_date"],
        "group_by_item_only": 1
    }
    
    # Item group filtresi varsa ekle
    if filters.get("item_group"):
        psw_filters["item_group"] = filters["item_group"]

    psw_report = ProductionStartWeekReport(psw_filters)
    columns_psw, data_psw, *_rest = psw_report.run()

    item_capacity = {}
    item_groups = {}
    
    # Item bilgilerini al - eğer item_group filtresi varsa onu da uygula
    item_filters = {}
    if filters.get("item_group"):
        item_filters["item_group"] = filters["item_group"]
    
    items = frappe.get_all("Item", filters=item_filters, fields=["name", "custom_weekly_production", "item_group"])
    for item in items:
        try:
            item_capacity[item.name] = int(float(item.custom_weekly_production or 0))
        except ValueError:
            item_capacity[item.name] = 0
        item_groups[item.name] = item.item_group or ""

    week_fields = [
        (col["label"], col["fieldname"])
        for col in columns_psw
        if col.get("fieldtype") in ("Int", "Float") and col["fieldname"] not in ("total", "unit")
    ]

    valid_weeks = [(l, f) for l, f in week_fields if iso_week_start(f) and iso_week_start(f) >= from_date_obj]
    week_list = [label for label, _ in valid_weeks]
    week_fieldnames = [fieldname for _, fieldname in valid_weeks]

    cumulative_demand = {}
    past_totals = {}

    for row in data_psw:
        item = row.get("item_code")
        if not item:
            continue

        # Item capacity'de yoksa atla (item_group filtresi zaten uygulanmış olacak)
        if item not in item_capacity:
            continue

        if item not in cumulative_demand:
            cumulative_demand[item] = {f: 0 for f in week_fieldnames}
            past_totals[item] = 0

        for _, fieldname in week_fields:
            qty = int(row.get(fieldname, 0) or 0)
            week_start = iso_week_start(fieldname)
            if week_start:
                if week_start >= from_date_obj:
                    if fieldname in cumulative_demand[item]:
                        cumulative_demand[item][fieldname] += qty
                elif week_start < from_date_obj:
                    past_totals[item] += qty

    planning = {}

    for item, week_qty in cumulative_demand.items():
        capacity = item_capacity.get(item, 0)
        dist = {label: 0 for label in week_list}
        carry = 0

        # 1. Önce orijinal talepleri dist'e yerleştir
        for i, label in enumerate(week_list):
            fieldname = week_fieldnames[i]
            dist[label] = week_qty.get(fieldname, 0)

        # 2. Geriye doğru kapasite kontrolü ve dağıtım (to_date'ten başlayarak)
        for i in reversed(range(len(week_list))):
            label = week_list[i]
            current_demand = dist[label]
            
            if capacity > 0 and current_demand > capacity:
                # Kapasite fazlası miktarı hesapla
                excess = current_demand - capacity
                dist[label] = capacity
                
                # Fazla miktarı bir önceki haftaya aktar
                if i > 0:  # İlk hafta değilse
                    prev_label = week_list[i - 1]
                    dist[prev_label] += excess
                else:  # İlk haftaysa carry'ye ekle
                    carry += excess

        # 3. Kapasite fazlası için akıllı dağıtım fonksiyonu
        def smart_distribute(amount_to_distribute, current_dist, capacity, weeks_to_distribute):
            if amount_to_distribute <= 0:
                return
            
            remaining = amount_to_distribute
            
            # Önce kapasitenin altında kalan haftalarda boşlukları doldur
            if capacity > 0:
                for week in weeks_to_distribute:
                    if remaining <= 0:
                        break
                    current_amount = current_dist.get(week, 0)
                    if current_amount < capacity:
                        gap = capacity - current_amount
                        fill_amount = min(gap, remaining)
                        current_dist[week] += fill_amount
                        remaining -= fill_amount
            
            # Hala fazla miktar varsa eşit dağıt
            if remaining > 0:
                portion = remaining // len(weeks_to_distribute)
                rem = remaining % len(weeks_to_distribute)
                for i, week in enumerate(weeks_to_distribute):
                    current_dist[week] += portion + (1 if i < rem else 0)

        # İlk haftada kalan fazlayı ilk 8 haftaya akıllı dağıt
        first_8 = week_list[:8]
        if carry > 0:
            smart_distribute(carry, dist, capacity, first_8)

        # 4. Geçmiş talepleri de ilk 8 haftaya akıllı dağıt
        past_total = past_totals.get(item, 0)
        if past_total > 0:
            smart_distribute(past_total, dist, capacity, first_8)

        planning[item] = (dist, capacity, item_groups.get(item, ""))

    for item, (dist, capacity, item_group) in planning.items():
        row = {
            "item_group": item_group,
            "item_code": item,
            "weekly_capacity": capacity,
            "_style":{},
        }
        total = 0
        for label in week_list:
            fieldname = scrub(label)
            value = dist[label]
            row[scrub(label)] = value if value else None
            total += value or 0

            color = get_cell_color(value, capacity)
            if color:
                row["_style"][fieldname] = f"background-color: {color}; color: white"

        row["total"] = total
        data.append(row)

    summary_row = {
        "item_group": "TOPLAM",
        "item_code": None,
        "weekly_capacity": None,
        "total": 0
    }
    for label in week_list:
        summary_row[scrub(label)] = sum(row.get(scrub(label), 0) or 0 for row in data)
    summary_row["total"] = sum(summary_row[scrub(label)] or 0 for label in week_list)
    data.append(summary_row)

    dynamic_columns = [
        {"label": label, "fieldname": scrub(label), "fieldtype": "Int", "width": 100}
        for label in week_list
    ]

    total_column = {
        "label": "Toplam", "fieldname": "total", "fieldtype": "Int", "width": 100
    }

    return get_columns() + dynamic_columns + [total_column], data

def get_columns():
    return [
        {
            "label": frappe._("Ürün Grubu"),
            "fieldname": "item_group",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": frappe._("Ürün"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 180
        },
        {
            "label": frappe._("Haftalık Kapasite"),
            "fieldname": "weekly_capacity",
            "fieldtype": "Int",
            "width": 150
        }
    ]

@frappe.whitelist()
def get_item_groups():
    from erpnextkta.kta_mrp.report.production_start_week.production_start_week import ProductionStartWeekReport
    psw_filters = {
        "from_date": f"{datetime.today().year}-01-01",
        "to_date": datetime.today().strftime("%Y-%m-%d"),
        "group_by_item_only": 1
    }
    psw_report = ProductionStartWeekReport(psw_filters)
    columns_psw, data_psw, *_rest = psw_report.run()

    item_codes = {row["item_code"] for row in data_psw if row.get("item_code")}
    if not item_codes:
        return []

    res = frappe.get_all("Item", filters={"name": ["in", list(item_codes)]}, fields=["item_group"])
    return sorted({r.item_group for r in res if r.item_group})

def get_cell_color(value, weekly_capacity):
    if weekly_capacity == 0 or value is None:
        return None

    try:
        value = int(value)
        capacity = int(weekly_capacity)
    except (ValueError, TypeError):
        return None

    if value > capacity:
        return "#4B4B4B"  # Koyu gri (kapasiteyi aştıysa)
    elif value > 0:
        ratio = min(value / capacity, 1.0)
        return hex_blend("#90EE90", "#006400", ratio)  # Açık yeşilden koyuya geç
    else:
        return None