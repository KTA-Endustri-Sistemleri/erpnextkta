import frappe
from collections import defaultdict
import re
from datetime import datetime

def execute(filters=None):
    if not filters:
        filters = {}

    stage = filters.get("stage", "")
    include_stock = "Stokları Düş" in stage
    include_po = "PO Teslimatlarını Düş" in stage
    group_by = filters.get("group_by", "Bitmiş Ürün + Hammadde")
    group_only_material = group_by == "Sadece Hammadde"

    from_date = filters.get("from_date")
    if isinstance(from_date, str):
        from_date = datetime.strptime(from_date, "%Y-%m-%d")

    from erpnextkta.erpnextkta.report.capacity_planning_report.capacity_planning_report import execute as capacity_execute
    capacity_cols, capacity_data = capacity_execute(filters)

    week_fields = []
    week_labels = {}
    for col in capacity_cols:
        if col["fieldtype"] in ("Int", "Float") and col["fieldname"] not in ("total", "unit", "weekly_capacity"):
            fieldname = col["fieldname"]
            match = re.match(r"w(\d{1,2})_(\d{4})", fieldname)
            if match:
                week_no = int(match.group(1))
                year = int(match.group(2))
                label = f"W{week_no} {year}"
                week_fields.append((fieldname, week_no, year))
                week_labels[fieldname] = label

    week_fields.sort(key=lambda x: (x[2], x[1]))
    week_fields = [x[0] for x in week_fields]
    sorted_week_labels = [week_labels[w] for w in week_fields]

    # 1. OPTIMIZE: Tek seferde tüm gerekli BOMs ve items'ları al
    finished_items = [row.get("item_code") for row in capacity_data if row.get("item_code")]

    item_customer_group_map = {}
    if finished_items:
        item_meta = frappe.db.get_all(
            "Item",filters={"name": ["in", finished_items]},
            fields=["name", "kta_musteri_grubu"]
        )
        item_customer_group_map = {i.name: i.kta_musteri_grubu for i in item_meta}

    
    # BOM'ları toplu al
    bom_map = {}
    if finished_items:
        bom_data = frappe.db.get_all(
            "BOM", 
            filters={"item": ["in", finished_items], "is_default": 1, "is_active": 1},
            fields=["item", "name"]
        )
        bom_map = {b.item: b.name for b in bom_data}

    # 2. OPTIMIZE: BOM exploded items'ları toplu al
    bom_names = list(bom_map.values())
    exploded_items_map = {}
    if bom_names:
        exploded_items = frappe.db.get_all(
            "BOM Explosion Item",
            filters={"parent": ["in", bom_names]},
            fields=["parent", "item_code", "stock_qty", "stock_uom"]
        )
        
        for item in exploded_items:
            if item.parent not in exploded_items_map:
                exploded_items_map[item.parent] = []
            exploded_items_map[item.parent].append(item)

    material_totals = defaultdict(lambda: defaultdict(float))
    detailed_data = defaultdict(lambda: defaultdict(float))

    # 3. OPTIMIZE: Döngü içinde frappe.get_doc kullanımını kaldır
    for row in capacity_data:
        finished_item = row.get("item_code")
        if not finished_item:
            continue

        bom_name = bom_map.get(finished_item)
        if not bom_name:
            continue

        bom_items = exploded_items_map.get(bom_name, [])

        for week in week_fields:
            planned_qty = row.get(week)
            if not planned_qty:
                continue

            for bom_item in bom_items:
                week_label = week_labels[week]
                qty = round(bom_item.stock_qty * planned_qty, 2)

                material_key = (bom_item.item_code, bom_item.stock_uom)
                detailed_key = (bom_item.item_code, bom_item.stock_uom, finished_item, bom_name)

                material_totals[material_key][week_label] += qty
                detailed_data[detailed_key][week_label] += qty

    # 4. OPTIMIZE: Stock ve PO verilerini tek seferde al
    remaining_stock_map = {}
    stock_map = {}
    future_po_map = defaultdict(list)
    po_surplus_map = defaultdict(float)

    if include_stock or include_po:
        item_codes = list({key[0] for key in material_totals.keys()})
        
        # Stock verilerini GROUP BY ile toplu al
        if item_codes:
            stock_data = frappe.db.sql("""
                SELECT item_code, stock_uom, SUM(actual_qty) as total_qty
                FROM `tabBin` 
                WHERE item_code IN %s
                GROUP BY item_code, stock_uom
            """, [tuple(item_codes)], as_dict=True)
            
            for d in stock_data:
                key = (d.item_code, d.stock_uom)
                remaining_stock_map[key] = d.total_qty
                stock_map[key] = d.total_qty

        # 5. OPTIMIZE: PO verilerini tek query ile al
        if include_po and item_codes:
            po_items = frappe.db.sql("""
                SELECT poi.item_code, poi.qty, poi.received_qty, poi.schedule_date, poi.stock_uom
                FROM `tabPurchase Order Item` poi
                INNER JOIN `tabPurchase Order` po ON poi.parent = po.name
                WHERE poi.item_code IN %s AND po.docstatus = 1
                AND poi.qty > poi.received_qty
            """, [tuple(item_codes)], as_dict=True)

            from_week = from_date.isocalendar().week
            from_year = from_date.isocalendar().year
            from_label = f"W{from_week} {from_year}"

            for item in po_items:
                delivery_date = item.schedule_date
                if not delivery_date:
                    continue

                key = (item.item_code, item.stock_uom)
                qty = item.qty - item.received_qty
                if qty <= 0:
                    continue

                if delivery_date < from_date.date():
                    future_po_map[key].append((from_label, qty))
                else:
                    week_label = f"W{delivery_date.isocalendar().week} {delivery_date.year}"
                    future_po_map[key].append((week_label, qty))

        # 6. OPTIMIZE: Stock düşme işlemini optimize et
        for key in material_totals:
            current_stock = remaining_stock_map.get(key, 0)
            for week_label in sorted_week_labels:
                value = material_totals[key][week_label]
                if value > 0 and current_stock > 0:
                    used_from_stock = min(current_stock, value)
                    current_stock -= used_from_stock
                    material_totals[key][week_label] = value - used_from_stock
            remaining_stock_map[key] = current_stock

        # PO düşme işlemi
        for key, po_entries in future_po_map.items():
            for start_week_label, qty in sorted(po_entries, key=lambda x: sorted_week_labels.index(x[0]) if x[0] in sorted_week_labels else float('inf')):
                remaining = qty
                started = False
                for week_label in sorted_week_labels:
                    if not started:
                        if week_label != start_week_label:
                            continue
                        started = True

                    need = material_totals[key][week_label]
                    if need > 0:
                        used = min(need, remaining)
                        material_totals[key][week_label] -= used
                        remaining -= used
                        if remaining <= 0:
                            break
                if remaining > 0:
                    po_surplus_map[key] += remaining

    # Kolon tanımlamaları
    columns = get_base_columns() if not group_only_material else [
        {"label": "Hammadde", "fieldname": "hammadde", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "Birim", "fieldname": "uom", "fieldtype": "Data", "width": 80}
    ]

    if not group_only_material:
        columns.insert(1, {
            "label": "Müşteri Grubu",
            "fieldname": "musteri_grubu",
            "fieldtype": "Data",
            "width": 140
        })

    columns += [{"label": label, "fieldname": label, "fieldtype": "Float", "width": 100} for label in sorted_week_labels]
    columns.append({"label": "Satır Toplamı", "fieldname": "satir_toplami", "fieldtype": "Float", "width": 120})

    if include_stock or include_po:
        columns += [
            {"label": "Toplam İhtiyaç", "fieldname": "toplam_ihtiyac", "fieldtype": "Float", "width": 120},
            {"label": "Stok", "fieldname": "stok", "fieldtype": "Float", "width": 100},
            {"label": "PO Teslimat", "fieldname": "po_teslimat", "fieldtype": "Float", "width": 100},
            {"label": "Net İhtiyaç", "fieldname": "net_ihtiyac", "fieldtype": "Float", "width": 120},
            {"label": "Fazla PO Miktarı", "fieldname": "fazla_po_miktari", "fieldtype": "Float", "width": 120},
        ]

    # 7. OPTIMIZE: Veri hazırlama işlemini optimize et
    data = []
    column_totals = {week_label: 0 for week_label in sorted_week_labels}
    column_totals.update({
        "satir_toplami": 0, "toplam_ihtiyac": 0, "stok": 0, 
        "po_teslimat": 0, "net_ihtiyac": 0, "fazla_po_miktari": 0
    })

    if group_only_material:
        for (raw_material, uom), week_map in material_totals.items():
            row = {"hammadde": raw_material, "uom": uom}
            toplam = net_total = satir_toplami = 0
            
            for week_label in sorted_week_labels:
                value = week_map.get(week_label, 0)
                row[week_label] = round(value, 2)
                toplam += value
                net_total += value
                satir_toplami += value
                column_totals[week_label] += value

            row["satir_toplami"] = round(satir_toplami, 2)
            column_totals["satir_toplami"] += satir_toplami
            row["toplam_ihtiyac"] = toplam
            column_totals["toplam_ihtiyac"] += toplam
            
            if include_stock or include_po:
                stok_value = stock_map.get((raw_material, uom), 0)
                row["stok"] = stok_value
                column_totals["stok"] += stok_value
                
                if include_po:
                    po_teslimat_value = sum(q for w, q in future_po_map[(raw_material, uom)])
                    fazla_po_value = po_surplus_map.get((raw_material, uom), 0)
                    row["po_teslimat"] = po_teslimat_value
                    row["fazla_po_miktari"] = fazla_po_value
                    column_totals["po_teslimat"] += po_teslimat_value
                    column_totals["fazla_po_miktari"] += fazla_po_value
                    
                row["net_ihtiyac"] = round(net_total, 2)
                column_totals["net_ihtiyac"] += net_total
                
            data.append(row)
    else:
        for (raw_material, uom, finished_item, bom), week_map in detailed_data.items():
            row = {"bitmis_urun": finished_item, "bom": bom, "hammadde": raw_material, "uom": uom, "musteri_grubu": item_customer_group_map.get(finished_item, "")}
            toplam = net_total = satir_toplami = 0
            key = (raw_material, uom)
            
            for week_label in sorted_week_labels:
                raw_value = week_map.get(week_label, 0)
                if include_stock or include_po:
                    # Paylaşım hesaplama optimizasyonu
                    denominator = sum(detailed_data[k][week_label] for k in detailed_data if k[:2] == key and week_label in detailed_data[k])
                    if denominator > 0 and raw_value > 0:
                        proportion = raw_value / denominator
                        net_value = material_totals[key][week_label] * proportion
                        row[week_label] = round(net_value, 2)
                        net_total += net_value
                        satir_toplami += net_value
                        column_totals[week_label] += net_value
                    else:
                        row[week_label] = 0
                else:
                    row[week_label] = raw_value
                    satir_toplami += raw_value
                    column_totals[week_label] += raw_value
                toplam += raw_value
                
            row["satir_toplami"] = round(satir_toplami, 2)
            column_totals["satir_toplami"] += satir_toplami
            row["toplam_ihtiyac"] = toplam
            column_totals["toplam_ihtiyac"] += toplam
            
            if include_stock or include_po:
                stok_value = stock_map.get(key, 0)
                row["stok"] = stok_value
                column_totals["stok"] += stok_value
                
                if include_po:
                    po_teslimat_value = sum(q for w, q in future_po_map[key])
                    fazla_po_value = po_surplus_map.get(key, 0)
                    row["po_teslimat"] = po_teslimat_value
                    row["fazla_po_miktari"] = fazla_po_value
                    column_totals["po_teslimat"] += po_teslimat_value
                    column_totals["fazla_po_miktari"] += fazla_po_value
                    
                row["net_ihtiyac"] = round(net_total, 2)
                column_totals["net_ihtiyac"] += net_total
                
            data.append(row)

    # Toplam satırı
    total_row = {}
    if group_only_material:
        total_row["hammadde"] = "<b>TOPLAM</b>"
        total_row["uom"] = ""
    else:
        total_row["bitmis_urun"] = "<b>TOPLAM</b>"
        total_row["bom"] = ""
        total_row["hammadde"] = ""
        total_row["uom"] = ""
    
    for week_label in sorted_week_labels:
        total_row[week_label] = round(column_totals[week_label], 2)
    
    total_row["satir_toplami"] = round(column_totals["satir_toplami"], 2)
    total_row["toplam_ihtiyac"] = round(column_totals["toplam_ihtiyac"], 2)
    
    if include_stock or include_po:
        total_row["stok"] = round(column_totals["stok"], 2)
        total_row["po_teslimat"] = round(column_totals["po_teslimat"], 2)
        total_row["net_ihtiyac"] = round(column_totals["net_ihtiyac"], 2)
        total_row["fazla_po_miktari"] = round(column_totals["fazla_po_miktari"], 2)
    
    data.append(total_row)

    return columns, data

def get_base_columns():
    return [
        {"label": "Ürün", "fieldname": "bitmis_urun", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "BOM", "fieldname": "bom", "fieldtype": "Link", "options": "BOM", "width": 120},
        {"label": "Hammadde", "fieldname": "hammadde", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "Birim", "fieldname": "uom", "fieldtype": "Data", "width": 80}
    ]