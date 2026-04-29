import frappe
from collections import defaultdict
import re
from datetime import datetime
import math

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

    from erpnextkta.kta_mrp.report.capacity_planning_report.capacity_planning_report import execute as capacity_execute
    capacity_cols, capacity_data, *_ = capacity_execute(filters)

    week_fields = []
    week_labels = {}
    for col in capacity_cols:
        if col["fieldtype"] in ("Int", "Float") and col["fieldname"] not in ("total", "unit", "weekly_capacity"):
            fieldname = col["fieldname"]
            match = re.match(r"(\d{4})_w(\d{1,2})", fieldname)
            if match:
                year = int(match.group(1))
                week_no = int(match.group(2))
                label = f"{year}-W{week_no:02d}"
                week_fields.append((fieldname, week_no, year))
                week_labels[fieldname] = label

    week_fields.sort(key=lambda x: (x[2], x[1]))
    week_fields = [x[0] for x in week_fields]
    sorted_week_labels = [week_labels[w] for w in week_fields]

    finished_items = [row.get("item_code") for row in capacity_data if row.get("item_code")]

    item_customer_group_map = {}
    if finished_items:
        item_meta = frappe.db.get_all(
            "Item",filters={"name": ["in", finished_items]},
            fields=["name", "custom_musteri_grubu"]
        )
        item_customer_group_map = {i.name: i.custom_musteri_grubu for i in item_meta}

    bom_map = {}
    if finished_items:
        bom_data = frappe.db.get_all(
            "BOM", 
            filters={"item": ["in", finished_items], "is_default": 1, "is_active": 1},
            fields=["item", "name"]
        )
        bom_map = {b.item: b.name for b in bom_data}

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

    for row in capacity_data:
        finished_item = row.get("item_code")
        if not finished_item: continue
        bom_name = bom_map.get(finished_item)
        if not bom_name: continue
        bom_items = exploded_items_map.get(bom_name, [])

        for week in week_fields:
            planned_qty = row.get(week)
            if not planned_qty: continue
            for bom_item in bom_items:
                week_label = week_labels[week]
                qty = round(bom_item.stock_qty * planned_qty, 2)
                material_key = (bom_item.item_code, bom_item.stock_uom)
                detailed_key = (bom_item.item_code, bom_item.stock_uom, finished_item, bom_name)
                material_totals[material_key][week_label] += qty
                detailed_data[detailed_key][week_label] += qty

    raw_material_items = list({key[0] for key in material_totals.keys()})
    item_info_map = {}
    default_supplier_map = {}
    item_moq_map = {}
    
    if raw_material_items:
        item_names = frappe.db.get_all("Item", filters={"name": ["in", raw_material_items]}, fields=["name", "item_name"])
        item_info_map = {i.name: i.item_name for i in item_names}
        
        # Varsayılan tedarikçi ve MOQ bilgilerini getir
        for item_code in raw_material_items:
            # Varsayılan tedarikçiyi bul
            default_supplier = frappe.db.get_value("Item Default", {"parent": item_code}, "default_supplier")
            if default_supplier:
                default_supplier_map[item_code] = default_supplier
                # Bu tedarikçiye ait MOQ bilgisini Item Supplier tablosundan çek
                moq = frappe.db.get_value("Item Supplier", 
                    {"parent": item_code, "supplier": default_supplier}, 
                    "custom_moq")
                if moq:
                    item_moq_map[item_code] = float(moq)

    remaining_stock_map = {}
    stock_map = {}
    future_po_map = defaultdict(list)
    po_surplus_map = defaultdict(float)

    if include_stock or include_po:
        item_codes = list({key[0] for key in material_totals.keys()})
        if item_codes:
            stock_data = frappe.db.sql("""
                SELECT bin.item_code, bin.stock_uom, SUM(bin.actual_qty) as total_qty
                FROM `tabBin` bin
                INNER JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
                WHERE bin.item_code IN %s AND wh.warehouse_type = 'Kullanılabilir Stok'
                GROUP BY bin.item_code, bin.stock_uom
            """, [tuple(item_codes)], as_dict=True)
            for d in stock_data:
                key = (d.item_code, d.stock_uom)
                remaining_stock_map[key] = d.total_qty
                stock_map[key] = d.total_qty

        if include_po and item_codes:
            po_items = frappe.db.sql("""
                SELECT poi.item_code, poi.qty, poi.received_qty, poi.schedule_date, poi.stock_uom
                FROM `tabPurchase Order Item` poi
                INNER JOIN `tabPurchase Order` po ON poi.parent = po.name
                WHERE poi.item_code IN %s AND po.docstatus = 1 AND poi.qty > poi.received_qty
            """, [tuple(item_codes)], as_dict=True)

            from_iso_year, from_iso_week, _ = from_date.isocalendar()
            from_label = f"{from_iso_year}-W{from_iso_week:02d}"

            for item in po_items:
                delivery_date = item.schedule_date
                if not delivery_date: continue
                key = (item.item_code, item.stock_uom)
                qty = item.qty - item.received_qty
                if qty <= 0: continue
                if delivery_date < from_date.date():
                    future_po_map[key].append((from_label, qty))
                else:
                    d_iso_year, d_iso_week, _ = delivery_date.isocalendar()
                    week_label = f"{d_iso_year}-W{d_iso_week:02d}"
                    future_po_map[key].append((week_label, qty))

        for key in material_totals:
            item_code = key[0]
            moq = item_moq_map.get(item_code, 0)
            balance = stock_map.get(key, 0)
            
            # Haftalık PO teslimatlarını kolay erişim için grupla
            week_pos = defaultdict(float)
            for w_label, q in future_po_map.get(key, []):
                week_pos[w_label] += q

            for week_label in sorted_week_labels:
                demand = material_totals[key][week_label]
                # Bu haftaki PO teslimatlarını bakiyeye ekle
                balance += week_pos.get(week_label, 0)
                
                if demand > balance:
                    # İhtiyaç var
                    shortfall = demand - balance
                    if moq > 0:
                        # MOQ (Minimum Paketleme) katına tamamla
                        order_qty = math.ceil(shortfall / moq) * moq
                    else:
                        order_qty = shortfall
                    
                    material_totals[key][week_label] = order_qty
                    balance = (balance + order_qty) - demand
                else:
                    # Eldeki stok/PO yeterli
                    balance -= demand
                    material_totals[key][week_label] = 0
            
            # Eğer tüm haftalar bittikten sonra hala elde fazla (PO artığı) varsa po_surplus'a ekle
            if balance > 0:
                # Ancak sadece PO'lardan gelen fazlalığı saymak için başlangıç stokunu düşebiliriz
                # Şimdilik basitçe kalanı fazla olarak işaretleyelim
                po_surplus_map[key] = balance

    columns = get_base_columns() if not group_only_material else [
        {"label": "Hammadde", "fieldname": "hammadde", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "Ürün Açıklaması", "fieldname": "urun_aciklamasi", "fieldtype": "Data", "width": 180},
        {"label": "Birim", "fieldname": "uom", "fieldtype": "Data", "width": 80},
        {"label": "Varsayılan Tedarikçi", "fieldname": "varsayilan_tedarikci", "fieldtype": "Link", "options": "Supplier", "width": 150}
    ]

    if not group_only_material:
        columns.insert(1, {"label": "Müşteri Grubu", "fieldname": "musteri_grubu", "fieldtype": "Data", "width": 140})

    columns += [{"label": label, "fieldname": label, "fieldtype": "Float", "width": 100} for label in sorted_week_labels]
    columns.append({"label": "Satır Toplamı", "fieldname": "satir_toplami", "fieldtype": "Float", "width": 120})
    columns += [{"label": "Toplam İhtiyaç", "fieldname": "toplam_ihtiyac", "fieldtype": "Float", "width": 120}]

    if include_stock or include_po:
        columns += [
            {"label": "Stok", "fieldname": "stok", "fieldtype": "Float", "width": 100},
            {"label": "PO Teslimat", "fieldname": "po_teslimat", "fieldtype": "Float", "width": 100},
            {"label": "Net İhtiyaç", "fieldname": "net_ihtiyac", "fieldtype": "Float", "width": 120},
            {"label": "Fazla PO Miktarı", "fieldname": "fazla_po_miktari", "fieldtype": "Float", "width": 120},
        ]

    data = []
    column_totals = {week_label: 0 for week_label in sorted_week_labels}
    column_totals.update({"satir_toplami": 0, "toplam_ihtiyac": 0, "stok": 0, "po_teslimat": 0, "net_ihtiyac": 0, "fazla_po_miktari": 0})
    
    summary_total_demand = 0
    summary_net_demand = 0

    if group_only_material:
        for (raw_material, uom), week_map in material_totals.items():
            row = {"hammadde": raw_material, "urun_aciklamasi": item_info_map.get(raw_material, ""), "uom": uom, "varsayilan_tedarikci": default_supplier_map.get(raw_material, "")}
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
            summary_total_demand += toplam
            
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
                summary_net_demand += net_total
            data.append(row)
    else:
        for (raw_material, uom, finished_item, bom), week_map in detailed_data.items():
            row = {"bitmis_urun": finished_item, "bom": bom, "hammadde": raw_material, "urun_aciklamasi": item_info_map.get(raw_material, ""), "uom": uom, "varsayilan_tedarikci": default_supplier_map.get(raw_material, ""), "musteri_grubu": item_customer_group_map.get(finished_item, "")}
            toplam = net_total = satir_toplami = 0
            key = (raw_material, uom)
            for week_label in sorted_week_labels:
                raw_value = week_map.get(week_label, 0)
                if include_stock or include_po:
                    denominator = sum(detailed_data[k][week_label] for k in detailed_data if k[:2] == key)
                    if denominator > 0 and raw_value > 0:
                        proportion = raw_value / denominator
                        net_value = material_totals[key][week_label] * proportion
                        row[week_label] = round(net_value, 2)
                        net_total += net_value
                        satir_toplami += net_value
                        column_totals[week_label] += net_value
                    else: row[week_label] = 0
                else:
                    row[week_label] = raw_value
                    satir_toplami += raw_value
                    column_totals[week_label] += raw_value
                toplam += raw_value
            row["satir_toplami"] = round(satir_toplami, 2)
            column_totals["satir_toplami"] += satir_toplami
            row["toplam_ihtiyac"] = toplam
            column_totals["toplam_ihtiyac"] += toplam
            summary_total_demand += toplam
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
                summary_net_demand += net_total
            data.append(row)

    total_row = {}
    if group_only_material: total_row["hammadde"] = "<b>TOPLAM</b>"
    else: total_row["bitmis_urun"] = "<b>TOPLAM</b>"
    for week_label in sorted_week_labels: total_row[week_label] = round(column_totals[week_label], 2)
    total_row["satir_toplami"] = round(column_totals["satir_toplami"], 2)
    total_row["toplam_ihtiyac"] = round(column_totals["toplam_ihtiyac"], 2)
    if include_stock or include_po:
        total_row["stok"] = round(column_totals["stok"], 2)
        total_row["po_teslimat"] = round(column_totals["po_teslimat"], 2)
        total_row["net_ihtiyac"] = round(column_totals["net_ihtiyac"], 2)
        total_row["fazla_po_miktari"] = round(column_totals["fazla_po_miktari"], 2)
    data.append(total_row)

    report_summary = [
        {"value": summary_total_demand, "label": "Toplam Brüt İhtiyaç", "indicator": "Blue"},
        {"value": summary_net_demand, "label": "Toplam Net İhtiyaç", "indicator": "Red"}
    ]

    return columns, data, None, None, report_summary

def get_base_columns():
    return [
        {"label": "Ürün", "fieldname": "bitmis_urun", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "BOM", "fieldname": "bom", "fieldtype": "Link", "options": "BOM", "width": 120},
        {"label": "Hammadde", "fieldname": "hammadde", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "Ürün Açıklaması", "fieldname": "urun_aciklamasi", "fieldtype": "Data", "width": 180},
        {"label": "Birim", "fieldname": "uom", "fieldtype": "Data", "width": 80},
        {"label": "Varsayılan Tedarikçi", "fieldname": "varsayilan_tedarikci", "fieldtype": "Link", "options": "Supplier", "width": 150}
    ]