import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 120
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
            "fieldtype": "Link",
            "options": "UOM",
            "width": 100
        },
        {
            "fieldname": "stock_entry",
            "label": _("Stock Entry"),
            "fieldtype": "Link",
            "options": "Stock Entry",
            "width": 150
        },
        {
            "fieldname": "customer_group",
            "label": _("Customer Group"),
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):
    conditions = ""
    values = {}
    
    if filters.get("from_date") and filters.get("to_date"):
        conditions += " AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s"
        values["from_date"] = filters.get("from_date")
        values["to_date"] = filters.get("to_date")
        
    if filters.get("item_code"):
        conditions += " AND sed.item_code = %(item_code)s"
        values["item_code"] = filters.get("item_code")

    query = f"""
        SELECT
            se.name AS stock_entry,
            se.posting_date,
            sed.item_code,
            sed.item_name,
            sed.qty,
            sed.uom,
            IFNULL((SELECT customer_group FROM `tabItem Customer Detail` WHERE parent = sed.item_code LIMIT 1), 'Undefined') AS customer_group
        FROM
            `tabStock Entry` se
        INNER JOIN
            `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE
            se.docstatus = 1
            AND se.stock_entry_type = 'Manufacture'
            AND sed.is_finished_item = 1
            {conditions}
        ORDER BY
            se.posting_date DESC, se.name DESC
    """
    
    data = frappe.db.sql(query, values, as_dict=1)
    for row in data:
        if row.customer_group == 'Undefined':
            row.customer_group = _("Undefined")
            
    return data
