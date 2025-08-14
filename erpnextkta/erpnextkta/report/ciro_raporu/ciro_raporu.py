import frappe

def execute(filters=None):
    columns = [
        {"label": "Satış Siparişi", "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 200},
        {"label": "Ürün Kodu", "fieldname": "item_code", "fieldtype": "Data", "width": 150},
        {"label": "Malzeme Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 150},
        {"label": "Müşteri", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
        {"label": "Müşteri Grubu", "fieldname": "customer_group", "fieldtype": "Data", "width": 150},
        {"label": "Teslimat Tarihi", "fieldname": "delivery_date", "fieldtype": "Date", "width": 130},
        {"label": "İrsaliye Tarihi", "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": "Sipariş Miktarı", "fieldname": "qty", "fieldtype": "Int", "width": 130},
        {"label": "Teslim Edilen Miktar", "fieldname": "delivered_qty", "fieldtype": "Int", "width": 130},
        {"label": "İrsaliye Miktarı", "fieldname": "dn_qty", "fieldtype": "Int", "width": 130},
        {"label": "Durum", "fieldname": "status", "fieldtype": "Data", "width": 110},
        {"label": "Fiyat", "fieldname": "price", "fieldtype": "Currency", "width": 110},
        {"label": "Para Birimi", "fieldname": "currency", "fieldtype": "Data", "width": 110},
        {"label": "İrsaliye Bazlı Tutar", "fieldname": "dn_total", "fieldtype": "Currency", "width": 150},
        {"label": "Kalan Sipariş Tutarı", "fieldname": "remaining_total", "fieldtype": "Currency", "width": 150},
        {"label": "Lead Time (Gün)", "fieldname": "lead_time_days", "fieldtype": "Int", "width": 110},
        {"label": "Sevk İrsaliyesi", "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 200},
    ]

    data = frappe.db.sql("""
        SELECT
            so.name AS sales_order,
            soi.item_code,
            i.item_group,
            so.customer,
            c.customer_group,
            soi.delivery_date,
            dn.posting_date,
            soi.qty,
            soi.delivered_qty,
            dni.qty AS dn_qty,
            so.status,
            CONCAT(
                CASE so.currency
                    WHEN 'USD' THEN '$'
                    WHEN 'EUR' THEN '€'
                    WHEN 'TRY' THEN '₺'
                    ELSE so.currency
                END, ' ',
                FORMAT(soi.price_list_rate, 6)
            ) AS price,
            so.currency,
            CONCAT(
                CASE so.currency
                    WHEN 'USD' THEN '$'
                    WHEN 'EUR' THEN '€'
                    WHEN 'TRY' THEN '₺'
                    ELSE so.currency
                END, ' ',
                FORMAT(IFNULL(dni.qty, 0) * soi.price_list_rate, 6)
            ) AS dn_total,
            CONCAT(
                CASE so.currency
                    WHEN 'USD' THEN '$'
                    WHEN 'EUR' THEN '€'
                    WHEN 'TRY' THEN '₺'
                    ELSE so.currency
                END, ' ',
                FORMAT((soi.qty - soi.delivered_qty) * soi.price_list_rate, 6)
            ) AS remaining_total,
            ip.lead_time_days,
            dn.name AS delivery_note
        FROM
            `tabSales Order` so
        JOIN
            `tabSales Order Item` soi ON soi.parent = so.name
        LEFT JOIN
            `tabItem` i ON i.name = soi.item_code
        LEFT JOIN
            `tabCustomer` c ON c.name = so.customer
        LEFT JOIN
            `tabItem Price` ip ON ip.item_code = soi.item_code
                              AND ip.customer = so.customer
                              AND ip.price_list = so.selling_price_list
                              AND (ip.valid_upto IS NULL OR ip.valid_upto >= CURDATE())
        LEFT JOIN
            `tabDelivery Note Item` dni ON dni.so_detail = soi.name
        LEFT JOIN
            `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE
            so.docstatus = 1
            AND so.status != 'Closed'
    """, as_dict=True)

    return columns, data
