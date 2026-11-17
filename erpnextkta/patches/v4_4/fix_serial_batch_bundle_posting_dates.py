import frappe


def execute():
    """
    Backfill posting_datetime and/or posting_date/posting_time on Serial and Batch Bundle
    from parent vouchers to fix ERPNext v15 BatchNoValuation negative stock errors.
    Supports both legacy (posting_date/posting_time) and modern (posting_datetime) schemas.
    """
    has_posting_datetime = frappe.db.has_column(
        "Serial and Batch Bundle", "posting_datetime"
    )
    has_posting_date = frappe.db.has_column("Serial and Batch Bundle", "posting_date")
    has_posting_time = frappe.db.has_column("Serial and Batch Bundle", "posting_time")

    if not has_posting_datetime and not has_posting_date:
        return

    set_clauses = []
    where_clauses = []

    if has_posting_datetime:
        set_clauses.append(
            "sabb.posting_datetime = TIMESTAMP(CONCAT(v.posting_date, ' ', COALESCE(v.posting_time, '00:00:00')))"
        )
        where_clauses.append("sabb.posting_datetime IS NULL")

    if has_posting_date:
        set_clauses.append("sabb.posting_date = v.posting_date")
        where_clauses.append("sabb.posting_date IS NULL")

    if has_posting_time:
        set_clauses.append("sabb.posting_time = COALESCE(v.posting_time, '00:00:00')")

    set_sql = ", ".join(set_clauses)
    where_sql = " OR ".join(where_clauses)

    voucher_types = [
        "Stock Entry",
        "Purchase Receipt",
        "Delivery Note",
        "Purchase Invoice",
        "Sales Invoice",
        "Stock Reconciliation",
    ]

    for dt in voucher_types:
        if frappe.db.exists("DocType", dt):
            frappe.db.sql(f"""
				UPDATE `tabSerial and Batch Bundle` sabb
				STRAIGHT_JOIN `tab{dt}` v ON sabb.voucher_no = v.name
				SET {set_sql}
				WHERE sabb.voucher_type = '{dt}'
				  AND ({where_sql})
			""")
