import frappe
from dateutil.relativedelta import relativedelta
import datetime
import re

def execute(filters=None):
    if not filters or not filters.get("from_date") or not filters.get("to_date"):
        return [], []

    conditions = ""
    if filters.get("item_group"):
        conditions += " AND i.item_group = %(item_group)s"
    if filters.get("item_code"):
        conditions += " AND sle.item_code = %(item_code)s"
        
    # Get opening balances
    opening_balances = frappe.db.sql(f"""
        SELECT
            sle.item_code,
            i.item_name,
            SUM(sle.actual_qty) as opening_qty
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON sle.item_code = i.name
        WHERE sle.is_cancelled = 0
          AND sle.posting_date < %(from_date)s
          {{conditions}}
        GROUP BY sle.item_code
    """.format(conditions=conditions), filters, as_dict=True)

    # Get movements with actual voucher types
    monthly_movements = frappe.db.sql(f"""
        SELECT
            sle.item_code,
            i.item_name,
            DATE_FORMAT(sle.posting_date, '%%Y-%%m') as month,
            sle.voucher_type,
            se.stock_entry_type,
            SUM(sle.actual_qty) as qty
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON sle.item_code = i.name
        LEFT JOIN `tabStock Entry` se ON sle.voucher_type = 'Stock Entry' AND sle.voucher_no = se.name
        WHERE sle.is_cancelled = 0
          AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
          {{conditions}}
        GROUP BY sle.item_code, DATE_FORMAT(sle.posting_date, '%%Y-%%m'), sle.voucher_type, se.stock_entry_type
    """.format(conditions=conditions), filters, as_dict=True)

    # Find unique movement types to create dynamic columns
    movement_types = set()
    
    # Structure data
    item_data = {}
    for ob in opening_balances:
        item_data[ob.item_code] = {
            "opening": ob.opening_qty,
            "item_name": ob.item_name,
            "months": {}
        }
        
    for row in monthly_movements:
        if row.item_code not in item_data:
            item_data[row.item_code] = {
                "opening": 0.0,
                "item_name": row.item_name,
                "months": {}
            }
        
        # Determine the key for this movement
        mov_type = row.voucher_type
        if row.voucher_type == 'Stock Entry' and row.stock_entry_type:
            mov_type = f"Stock Entry - {row.stock_entry_type}"
            
        movement_types.add(mov_type)
        
        month_key = row.month
        if month_key not in item_data[row.item_code]["months"]:
            item_data[row.item_code]["months"][month_key] = {}
            
        if mov_type not in item_data[row.item_code]["months"][month_key]:
            item_data[row.item_code]["months"][month_key][mov_type] = 0.0
            
        item_data[row.item_code]["months"][month_key][mov_type] += row.qty
        
    # Sort movement types for consistent columns
    movement_types = sorted(list(movement_types))
    
    # Build dynamic columns
    columns = [
        {"fieldname": "item_code", "label": "Ürün Kodu", "fieldtype": "Link", "options": "Item", "width": 140},
        {"fieldname": "item_name", "label": "Ürün Adı", "fieldtype": "Data", "width": 250},
        {"fieldname": "ay", "label": "Ay", "fieldtype": "Data", "width": 100},
        {"fieldname": "acilis_stogu", "label": "Açılış Stoğu", "fieldtype": "Float", "width": 120}
    ]
    
    for mt in movement_types:
        # Create a safe fieldname
        fieldname = re.sub(r'[^a-zA-Z0-9_]', '_', mt.lower())
        fieldname = re.sub(r'_+', '_', fieldname).strip('_')
        columns.append({
            "fieldname": fieldname,
            "label": mt,
            "fieldtype": "Float",
            "width": 160
        })
        
    columns.append({"fieldname": "kapanis_stogu", "label": "Kapanış Stoğu", "fieldtype": "Float", "width": 120})
    columns.append({"fieldname": "fire_orani", "label": "Fire Oranı (%)", "fieldtype": "Percent", "width": 120})

    # Build rows
    data = []
    
    start_date = filters.get("from_date")
    end_date = filters.get("to_date")
    if isinstance(start_date, str):
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        
    month_list = []
    cur = start_date.replace(day=1)
    while cur <= end_date:
        month_list.append(cur.strftime("%Y-%m"))
        cur += relativedelta(months=1)
        
    for item_code, item_info in item_data.items():
        running_bal = item_info["opening"]
        
        # Skip if no movements and zero balance
        if running_bal == 0 and not item_info["months"]:
            continue
            
        for m in month_list:
            movs = item_info["months"].get(m, {})
            
            # Show row if there are movements or if running_bal is non-zero
            if movs or running_bal != 0:
                row_dict = {
                    "item_code": item_code,
                    "item_name": item_info["item_name"],
                    "ay": m,
                    "acilis_stogu": running_bal
                }
                
                net_change = 0.0
                for mt in movement_types:
                    fieldname = re.sub(r'[^a-zA-Z0-9_]', '_', mt.lower())
                    fieldname = re.sub(r'_+', '_', fieldname).strip('_')
                    val = movs.get(mt, 0.0)
                    row_dict[fieldname] = val
                    net_change += val
                    
                kapanis = running_bal + net_change
                row_dict["kapanis_stogu"] = kapanis
                
                # Calculate Fire Oranı (%)
                tuketim = abs(row_dict.get("stock_entry_manufacture", 0.0))
                fire = abs(row_dict.get("stock_entry_material_issue", 0.0)) + abs(row_dict.get("stock_entry_scrap_for_manufacturing", 0.0))
                
                if tuketim > 0:
                    row_dict["fire_orani"] = round((fire / tuketim) * 100, 2)
                elif fire > 0:
                    row_dict["fire_orani"] = 100.0
                else:
                    row_dict["fire_orani"] = 0.0
                
                data.append(row_dict)
                running_bal = kapanis

    # Sort data by item_code then ay
    data = sorted(data, key=lambda x: (x["item_code"], x["ay"]))
    
    return columns, data