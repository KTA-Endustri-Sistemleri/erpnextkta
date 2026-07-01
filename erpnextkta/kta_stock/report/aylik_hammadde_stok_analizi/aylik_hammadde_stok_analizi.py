import frappe
from dateutil.relativedelta import relativedelta
import datetime

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "item_code", "label": "Ürün Kodu", "fieldtype": "Link", "options": "Item", "width": 140},
        {"fieldname": "item_name", "label": "Ürün Adı", "fieldtype": "Data", "width": 250},
        {"fieldname": "ay", "label": "Ay", "fieldtype": "Data", "width": 100},
        {"fieldname": "acilis_stogu", "label": "Açılış Stoğu", "fieldtype": "Float", "width": 110},
        {"fieldname": "uretim_tuketimi", "label": "Üretim Tüketimi", "fieldtype": "Float", "width": 130},
        {"fieldname": "fire_cikis", "label": "Fire / Çıkış", "fieldtype": "Float", "width": 110},
        {"fieldname": "malzeme_girisi", "label": "Malzeme Girişi", "fieldtype": "Float", "width": 120},
        {"fieldname": "sayim_farki", "label": "Sayım Farkı", "fieldtype": "Float", "width": 110},
        {"fieldname": "diger_hareketler", "label": "Diğer Hareketler", "fieldtype": "Float", "width": 130},
        {"fieldname": "kapanis_stogu", "label": "Kapanış Stoğu", "fieldtype": "Float", "width": 110}
    ]

def get_data(filters):
    if not filters or not filters.get("from_date") or not filters.get("to_date"):
        return []

    conditions = ""
    if filters.get("item_group"):
        conditions += " AND i.item_group = %(item_group)s"
    if filters.get("item_code"):
        conditions += " AND sle.item_code = %(item_code)s"
        
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

    monthly_movements = frappe.db.sql(f"""
        SELECT
            sle.item_code,
            i.item_name,
            DATE_FORMAT(sle.posting_date, '%%Y-%%m') as month,
            SUM(CASE 
                WHEN se.stock_entry_type = 'Manufacture' AND sle.actual_qty < 0 THEN sle.actual_qty
                ELSE 0 END) as uretim_tuketimi,
            SUM(CASE 
                WHEN se.stock_entry_type IN ('Material Issue', 'Scrap for Manufacturing') AND sle.actual_qty < 0 THEN sle.actual_qty
                ELSE 0 END) as fire_cikis,
            SUM(CASE 
                WHEN (se.stock_entry_type IN ('Material Receipt', 'Manufacture', 'Repack', 'Material Transfer for Manufacture') AND sle.actual_qty > 0) 
                      OR sle.voucher_type = 'Purchase Receipt' THEN sle.actual_qty
                ELSE 0 END) as malzeme_girisi,
            SUM(CASE 
                WHEN sle.voucher_type = 'Stock Reconciliation' THEN sle.actual_qty
                ELSE 0 END) as sayim_farki,
            SUM(CASE
                WHEN (se.stock_entry_type NOT IN ('Manufacture', 'Material Issue', 'Scrap for Manufacturing', 'Material Receipt', 'Repack', 'Material Transfer for Manufacture') OR se.stock_entry_type IS NULL) 
                     AND sle.voucher_type NOT IN ('Purchase Receipt', 'Stock Reconciliation') THEN sle.actual_qty
                ELSE 0 END) as diger_hareketler
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON sle.item_code = i.name
        LEFT JOIN `tabStock Entry` se ON sle.voucher_type = 'Stock Entry' AND sle.voucher_no = se.name
        WHERE sle.is_cancelled = 0
          AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
          {{conditions}}
        GROUP BY sle.item_code, DATE_FORMAT(sle.posting_date, '%%Y-%%m')
    """.format(conditions=conditions), filters, as_dict=True)

    # Process into data structure
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
        item_data[row.item_code]["months"][row.month] = row

    # Build the final output row by row
    data = []
    
    start_date = filters.get("from_date")
    end_date = filters.get("to_date")
    if isinstance(start_date, str):
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        
    # generate list of month strings
    month_list = []
    cur = start_date.replace(day=1)
    while cur <= end_date:
        month_list.append(cur.strftime("%Y-%m"))
        cur += relativedelta(months=1)
        
    for item_code, item_info in item_data.items():
        running_bal = item_info["opening"]
        
        # If opening bal is 0 and there are no movements in this period, skip the item entirely.
        if running_bal == 0 and not item_info["months"]:
            continue
            
        for m in month_list:
            mov = item_info["months"].get(m)
            
            # Show row if there are movements or if running_bal is non-zero
            if mov:
                kapanis = running_bal + mov.uretim_tuketimi + mov.fire_cikis + mov.malzeme_girisi + mov.sayim_farki + mov.diger_hareketler
                data.append({
                    "item_code": item_code,
                    "item_name": item_info["item_name"],
                    "ay": m,
                    "acilis_stogu": running_bal,
                    "uretim_tuketimi": mov.uretim_tuketimi,
                    "fire_cikis": mov.fire_cikis,
                    "malzeme_girisi": mov.malzeme_girisi,
                    "sayim_farki": mov.sayim_farki,
                    "diger_hareketler": mov.diger_hareketler,
                    "kapanis_stogu": kapanis
                })
                running_bal = kapanis
            else:
                # no movements this month
                if running_bal != 0:
                    data.append({
                        "item_code": item_code,
                        "item_name": item_info["item_name"],
                        "ay": m,
                        "acilis_stogu": running_bal,
                        "uretim_tuketimi": 0,
                        "fire_cikis": 0,
                        "malzeme_girisi": 0,
                        "sayim_farki": 0,
                        "diger_hareketler": 0,
                        "kapanis_stogu": running_bal
                    })

    # Sort data by item_code then ay
    data = sorted(data, key=lambda x: (x["item_code"], x["ay"]))
    
    return data
