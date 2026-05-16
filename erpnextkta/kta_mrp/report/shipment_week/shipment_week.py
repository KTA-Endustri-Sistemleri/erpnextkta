import frappe
from frappe.utils import getdate
from datetime import date, timedelta

def execute(filters=None):
    filters = filters or {}
    today = date.today()

    from_date = getdate(filters.get("from_date")) if filters.get("from_date") else today - timedelta(days=30)
    to_date = getdate(filters.get("to_date")) if filters.get("to_date") else today + timedelta(days=60)

    periodic_filters = {
        "from_date": from_date, "to_date": to_date, "range": "Weekly",
        "value_quantity": "Quantity", "tree_type": "Müşteri", "show_pending_only": 1,
    }

    if filters.get("tree_key"): periodic_filters["tree_key"] = filters.get("tree_key")

    from erpnextkta.kta_mrp.report.periodic_sales_orders.periodic_sales_orders import SatisAnalizi
    base_report = SatisAnalizi(periodic_filters)
    base_report.run()

    week_labels = set()
    shipment_map = {}

    for row in base_report.data:
        if row.get("tree_key") == "<b>GENEL TOPLAM</b>": continue

        # KTA Sevk Parametreleri'ni bulmak için geliştirilmiş mantık
        customer = row.get("tree_key")
        address = row.get("shipping_address_name")
        delivery_time = frappe.db.get_value("KTA Sevk Parametreleri", {"customer_name": customer, "customer_address": address}, "delivery_time") or 0
        if not delivery_time:
            delivery_time = frappe.db.get_value("KTA Sevk Parametreleri", {"customer_name": customer}, "delivery_time") or 0

        for col in base_report.columns:
            label = col.get("label")
            if not label or not label.startswith("202"): continue
            field = frappe.scrub(label)
            quantity = row.get(field)
            if quantity:
                week_end_date = week_end_from_label(label)
                planned_date = week_end_date - timedelta(days=delivery_time)
                iso_year, iso_week, _ = planned_date.isocalendar()
                ship_week = f"{iso_year}-W{iso_week:02d}"
                week_labels.add(ship_week)
                key = (customer, row["item_code"], row["item_name"], address)
                if key not in shipment_map: shipment_map[key] = {}
                shipment_map[key][ship_week] = shipment_map[key].get(ship_week, 0) + quantity

    sorted_weeks = sorted(week_labels, key=week_sort_key)
    columns = [
        {"label": "Müşteri", "fieldname": "tree_key", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": "Ürün Kodu", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Ürün Adı", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "Adres", "fieldname": "shipping_address_name", "fieldtype": "Link", "options": "Address", "width": 180},
    ]
    for week in sorted_weeks:
        columns.append({"label": week, "fieldname": frappe.scrub(week), "fieldtype": "Int", "width": 100})
    columns.append({"label": "Toplam", "fieldname": "total", "fieldtype": "Int", "width": 100})

    data = []
    week_totals = {w: 0 for w in sorted_weeks}
    grand_total = 0
    for key, week_data in shipment_map.items():
        row = {"tree_key": key[0], "item_code": key[1], "item_name": key[2], "shipping_address_name": key[3]}
        total = 0
        for week in sorted_weeks:
            qty = week_data.get(week, 0)
            if qty:
                row[frappe.scrub(week)] = qty
                total += qty
                week_totals[week] += qty
        row["total"] = total
        grand_total += total
        data.append(row)

    total_row = {"tree_key": "<b>TOPLAM</b>", "item_code": "", "item_name": "", "shipping_address_name": ""}
    for w in sorted_weeks: total_row[frappe.scrub(w)] = week_totals[w]
    total_row["total"] = grand_total
    data.append(total_row)

    chart = {
        "data": {"labels": sorted_weeks, "datasets": [{"name": "Sevkiyat", "values": [week_totals[w] for w in sorted_weeks]}]},
        "type": "bar",
        "colors": ["#3498db"]
    }
    
    summary = [
        {"value": grand_total, "label": "Toplam Sevk Miktarı", "indicator": "Blue"},
        {"value": len(data) - 1, "label": "Sevk Edilecek Kalem", "indicator": "Green"}
    ]

    return columns, data, None, chart, summary

def week_end_from_label(label):
    try:
        parts = label.strip().split("-W")
        year, week_num = int(parts[0]), int(parts[1])
        return date.fromisocalendar(year, week_num, 1) + timedelta(days=6)
    except: return date.today()

def week_sort_key(week_str):
    try:
        parts = week_str.strip().split("-W")
        return (int(parts[0]), int(parts[1]))
    except: return (9999, 99)
