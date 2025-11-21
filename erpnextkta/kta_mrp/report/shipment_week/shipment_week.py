import frappe
from frappe.utils import getdate
from datetime import date, timedelta

def execute(filters=None):
    filters = filters or {}
    today = date.today()

    from_date = getdate(filters.get("from_date")) if filters.get("from_date") else today - timedelta(days=30)
    to_date = getdate(filters.get("to_date")) if filters.get("to_date") else today + timedelta(days=60)

    periodic_filters = {
        "from_date": from_date,
        "to_date": to_date,
        "range": "Weekly",
        "value_quantity": "Quantity",
        "tree_type": "Müşteri",
        "show_pending_only": 1,
    }

    if filters.get("tree_key"):
        periodic_filters["tree_key"] = filters.get("tree_key")

    from erpnextkta.erpnextkta.report.periodic_sales_orders.periodic_sales_orders import SatisAnalizi
    base_report = SatisAnalizi(periodic_filters)
    base_report.run()

    week_labels = set()
    shipment_map = {}

    for row in base_report.data:
        if row.get("tree_key") == "GENEL TOPLAM":
            continue

        parameter_id = f"{row['tree_key']} - {row['shipping_address_name']}"
        delivery_time = frappe.db.get_value("KTA Sevk Parametreleri", parameter_id, "delivery_time") or 0

        for col in base_report.columns:
            label = col.get("label")
            field = frappe.scrub(label)

            if label.startswith("W") and row.get(field):
                quantity = row.get(field)
                if not quantity:
                    continue

                week_end_date = week_end_from_label(label)
                planned_date = week_end_date - timedelta(days=delivery_time)
                shipment_week = f"W{planned_date.isocalendar()[1]:02d} {planned_date.year}"
                week_labels.add(shipment_week)

                key = (row["tree_key"], row["item_code"], row["item_name"], row["shipping_address_name"])
                if key not in shipment_map:
                    shipment_map[key] = {}

                shipment_map[key][shipment_week] = shipment_map[key].get(shipment_week, 0) + quantity

    # Sıralı haftalar
    sorted_weeks = sorted(week_labels, key=lambda w: week_sort_key(w))

    columns = [
        {"label": "Müşteri", "fieldname": "tree_key", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": "Ürün Kodu", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Ürün Adı", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "Adres", "fieldname": "shipping_address_name", "fieldtype": "Link", "options": "Address", "width": 180},
    ]

    for week in sorted_weeks:
        columns.append({
            "label": week,
            "fieldname": frappe.scrub(week),
            "fieldtype": "Int",
            "width": 100,
        })

    columns.append({
        "label": "Toplam",
        "fieldname": "total",
        "fieldtype": "Int",
        "width": 100,
    })

    data = []
    for key, week_data in shipment_map.items():
        row = {
            "tree_key": key[0],
            "item_code": key[1],
            "item_name": key[2],
            "shipping_address_name": key[3],
        }
        total = 0
        for week in sorted_weeks:
            qty = week_data.get(week, 0)
            if qty:  # 0 olanlar eklenmesin
                row[frappe.scrub(week)] = qty
                total += qty
        row["total"] = total
        data.append(row)

    return columns, data

def week_end_from_label(label):
    """'W26 2025' → haftanın son günü (Pazar)"""
    try:
        parts = label.strip().split()
        week_num = int(parts[0][1:])
        year = int(parts[1])
        start = date.fromisocalendar(year, week_num, 1)
        return start + timedelta(days=6)
    except:
        return date.today()

def week_sort_key(week_str):
    """W26 2025 → (2025, 26) sıralamak için"""
    try:
        parts = week_str.strip().split()
        week = int(parts[0][1:])
        year = int(parts[1])
        return (year, week)
    except:
        return (9999, 99)
