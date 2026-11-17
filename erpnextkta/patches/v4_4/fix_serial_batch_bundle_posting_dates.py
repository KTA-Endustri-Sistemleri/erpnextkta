import frappe


def execute():
    """
    Backfill posting_date and posting_time on Serial and Batch Bundle
    from parent vouchers to fix ERPNext v15 BatchNoValuation negative stock errors.
    """
    # 1. Stock Entry
    frappe.db.sql("""
		UPDATE `tabSerial and Batch Bundle` sabb
		JOIN `tabStock Entry` se ON sabb.voucher_no = se.name
		SET sabb.posting_date = se.posting_date,
			sabb.posting_time = COALESCE(se.posting_time, '00:00:00')
		WHERE sabb.voucher_type = 'Stock Entry'
		  AND sabb.posting_date IS NULL
	""")

    # 2. Purchase Receipt
    frappe.db.sql("""
		UPDATE `tabSerial and Batch Bundle` sabb
		JOIN `tabPurchase Receipt` pr ON sabb.voucher_no = pr.name
		SET sabb.posting_date = pr.posting_date,
			sabb.posting_time = COALESCE(pr.posting_time, '00:00:00')
		WHERE sabb.voucher_type = 'Purchase Receipt'
		  AND sabb.posting_date IS NULL
	""")

    # 3. Delivery Note
    frappe.db.sql("""
		UPDATE `tabSerial and Batch Bundle` sabb
		JOIN `tabDelivery Note` dn ON sabb.voucher_no = dn.name
		SET sabb.posting_date = dn.posting_date,
			sabb.posting_time = COALESCE(dn.posting_time, '00:00:00')
		WHERE sabb.voucher_type = 'Delivery Note'
		  AND sabb.posting_date IS NULL
	""")

    # 4. Other vouchers
    for dt in ["Purchase Invoice", "Sales Invoice", "Stock Reconciliation"]:
        if frappe.db.exists("DocType", dt):
            frappe.db.sql(f"""
				UPDATE `tabSerial and Batch Bundle` sabb
				JOIN `tab{dt}` v ON sabb.voucher_no = v.name
				SET sabb.posting_date = v.posting_date,
					sabb.posting_time = COALESCE(v.posting_time, '00:00:00')
				WHERE sabb.voucher_type = '{dt}'
				  AND sabb.posting_date IS NULL
			""")
