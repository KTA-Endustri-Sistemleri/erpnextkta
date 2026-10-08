import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "yukleme_tarihi",
            "label": _("Yükleme Tarihi"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "gumruge_gelis_tarihi",
            "label": _("Gümrüğe Geliş Tarihi"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "workflow_state",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "supplier",
            "label": _("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 250
        },
        {
            "fieldname": "item_code",
            "label": _("Item"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "qty",
            "label": _("Qty"),
            "fieldtype": "Float",
            "width": 100
        },
        {
            "fieldname": "uom",
            "label": _("UOM"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "purchase_receipt",
            "label": _("Purchase Receipt"),
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 150
        },

        {
            "fieldname": "rate",
            "label": _("Rate"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120
        },
        {
            "fieldname": "amount",
            "label": _("Amount"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120
        },
        {
            "fieldname": "currency",
            "label": _("Currency"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "grand_total",
            "label": _("Grand Total"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130
        }
    ]

def get_data(filters):
    conditions = ""
    values = {}
    

    if filters and filters.get("supplier"):
        conditions += " AND pr.supplier = %(supplier)s"
        values["supplier"] = filters.get("supplier")
        
    if filters and filters.get("item_code"):
        conditions += " AND pri.item_code = %(item_code)s"
        values["item_code"] = filters.get("item_code")

    query = f"""
        SELECT
            pr.yukleme_tarihi,
            pr.gumruge_gelis_tarihi,
            pr.supplier,
            pr.supplier_name,
            pri.item_code,
            pri.item_name,
            pri.qty,
            pri.uom,
            pri.rate,
            pri.amount,
            pr.name AS purchase_receipt,
            pr.workflow_state,
            pr.grand_total,
            pr.currency
        FROM
            `tabPurchase Receipt` pr
        INNER JOIN
            `tabPurchase Receipt Item` pri ON pri.parent = pr.name
        WHERE
            pr.workflow_state IN ('Yolda', 'Antrepoda')
            AND pr.docstatus = 0
            {conditions}
        ORDER BY
            pr.yukleme_tarihi DESC, pr.name DESC
    """
    
    data = frappe.db.sql(query, values, as_dict=1)
    
    # Translate workflow states so they appear correctly in all languages
    for row in data:
        if row.workflow_state == 'Yolda':
            row.workflow_state = _("Yolda")
        elif row.workflow_state == 'Antrepoda':
            row.workflow_state = _("Antrepoda")
            
    return data
