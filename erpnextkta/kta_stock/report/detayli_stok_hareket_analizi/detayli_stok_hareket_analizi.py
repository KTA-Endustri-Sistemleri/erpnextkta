import frappe
from dateutil.relativedelta import relativedelta
import datetime

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "kategori", "label": "Kategori", "fieldtype": "Data", "width": 180},
        {"fieldname": "tarih_ay", "label": "Tarih / Ay", "fieldtype": "Data", "width": 120},
        {"fieldname": "belge_tipi", "label": "Belge Tipi", "fieldtype": "Data", "width": 140},
        {"fieldname": "amac", "label": "Amaç", "fieldtype": "Data", "width": 180},
        {"fieldname": "belge_no", "label": "Belge No", "fieldtype": "Dynamic Link", "options": "belge_tipi", "width": 180},
        {"fieldname": "depo", "label": "Depo", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"fieldname": "miktar", "label": "Miktar (Adet)", "fieldtype": "Float", "width": 120},
        {"fieldname": "acilis_stogu", "label": "Açılış Stoğu", "fieldtype": "Float", "width": 120},
        {"fieldname": "kapanis_stogu", "label": "Kapanış Stoğu", "fieldtype": "Float", "width": 120}
    ]

def get_data(filters):
    if not filters or not filters.get("item_code") or not filters.get("from_date") or not filters.get("to_date"):
        return []
        
    item_code = filters.get("item_code")
    start_date = filters.get("from_date")
    end_date = filters.get("to_date")
    
    if isinstance(start_date, str):
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        start_dt = start_date
        
    if isinstance(end_date, str):
        end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        end_dt = end_date
    
    data = []
    
    # 1. Devirler
    month_start = start_dt.replace(day=1)
    
    while month_start <= end_dt:
        opening_bal = frappe.db.sql("""
            SELECT SUM(actual_qty) as qty
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND posting_date < %s
            AND is_cancelled = 0
        """, (item_code, month_start.strftime("%Y-%m-%d")), as_dict=True)
        qty_open = opening_bal[0].qty if opening_bal and opening_bal[0].qty else 0.0
        
        next_month_dt = month_start + relativedelta(months=1)
        closing_bal = frappe.db.sql("""
            SELECT SUM(actual_qty) as qty
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND posting_date < %s
            AND is_cancelled = 0
        """, (item_code, next_month_dt.strftime("%Y-%m-%d")), as_dict=True)
        qty_close = closing_bal[0].qty if closing_bal and closing_bal[0].qty else 0.0
        
        data.append({
            "kategori": "Ay Ay Devirler",
            "tarih_ay": month_start.strftime("%Y-%m"),
            "acilis_stogu": qty_open,
            "kapanis_stogu": qty_close
        })
        month_start = next_month_dt

    # 2. Entries
    entries = frappe.db.sql("""
        SELECT posting_date, voucher_type, voucher_no, actual_qty, warehouse
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s AND posting_date BETWEEN %s AND %s
        AND is_cancelled = 0
        ORDER BY posting_date, posting_time, creation
    """, (item_code, start_date, end_date), as_dict=True)

    for e in entries:
        purpose = ""
        kategori = "Diğer Hareketler"
        
        if e.voucher_type == "Stock Entry":
            se = frappe.db.get_value("Stock Entry", e.voucher_no, "stock_entry_type")
            purpose = se or ""
            
        if purpose == "Manufacture" and e.actual_qty < 0:
            kategori = "Üretim Tüketimleri"
        elif purpose in ["Material Issue", "Scrap for Manufacturing"] and e.actual_qty < 0:
            kategori = "Fireler / Çıkışlar"
        elif purpose in ["Material Receipt", "Manufacture", "Repack", "Material Transfer for Manufacture"] and e.actual_qty > 0:
            kategori = "Malzeme Girişleri"
        elif e.voucher_type == "Purchase Receipt":
            kategori = "Malzeme Girişleri"
            
        data.append({
            "kategori": kategori,
            "tarih_ay": str(e.posting_date),
            "belge_tipi": e.voucher_type,
            "amac": purpose,
            "belge_no": e.voucher_no,
            "depo": e.warehouse,
            "miktar": e.actual_qty
        })
        
    # 3. Stock Reconciliations
    reco_entries = frappe.db.sql("""
        SELECT
            sr.posting_date,
            sr.name as voucher_no,
            sri.warehouse,
            sri.qty as entered_qty
        FROM `tabStock Reconciliation` sr
        JOIN `tabStock Reconciliation Item` sri ON sr.name = sri.parent
        WHERE sri.item_code = %s AND sr.docstatus = 1
        ORDER BY sr.posting_date, sr.posting_time
    """, (item_code,), as_dict=True)
    
    for r in reco_entries:
        data.append({
            "kategori": "Stok Sayım (Tüm Zamanlar)",
            "tarih_ay": str(r.posting_date),
            "belge_tipi": "Stock Reconciliation",
            "belge_no": r.voucher_no,
            "depo": r.warehouse,
            "miktar": r.entered_qty
        })

    return data
