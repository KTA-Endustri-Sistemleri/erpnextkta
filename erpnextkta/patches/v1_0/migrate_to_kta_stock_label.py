import frappe

def execute():
    # 1. Update Zebra Templates names
    if frappe.db.exists("KTA Zebra Templates", "KTA Depo Etiketleri"):
        frappe.rename_doc("KTA Zebra Templates", "KTA Depo Etiketleri", "Depo Giriş Etiketi", ignore_permissions=True)
    if frappe.db.exists("KTA Zebra Templates", "KTA Is Emri Etiketleri"):
        frappe.rename_doc("KTA Zebra Templates", "KTA Is Emri Etiketleri", "İş Emri Etiketi", ignore_permissions=True)

    # 2. Migrate KTA Depo Etiketleri to KTA Stock Label
    if not frappe.db.table_exists("KTA Depo Etiketleri"):
        return

    frappe.db.sql("""
        INSERT INTO `tabKTA Stock Label` (
            name, creation, modified, modified_by, owner, docstatus, idx,
            label_type, reference_doctype, reference_name,
            item_code, item_name, item_group, qty, uom, batch, sut_barcode,
            quality_ref, supplier_delivery_note, gr_posting_date,
            print_count, last_printed_at, last_printed_by, do_not_split
        )
        SELECT 
            name, creation, modified, modified_by, owner, docstatus, idx,
            'Depo Giriş Etiketi', 'Purchase Receipt', gr_number,
            item_code, item_name, item_group, qty, uom, batch, sut_barcode,
            quality_ref, supplier_delivery_note, gr_posting_date,
            print_count, last_printed_at, last_printed_by, do_not_split
        FROM `tabKTA Depo Etiketleri`
        ON DUPLICATE KEY UPDATE modified=VALUES(modified)
    """)

    # 3. Migrate child table
    if frappe.db.table_exists("KTA Depo Etiketleri Bolme"):
        frappe.db.sql("""
            INSERT INTO `tabKTA Stock Label Split` (
                name, creation, modified, modified_by, owner, docstatus, parent, parentfield, parenttype, idx,
                qty
            )
            SELECT 
                name, creation, modified, modified_by, owner, docstatus, parent, 'splits', 'KTA Stock Label', idx,
                qty
            FROM `tabKTA Depo Etiketleri Bolme`
            ON DUPLICATE KEY UPDATE modified=VALUES(modified)
        """)
        
    # 4. Update Print Log label doctype
    if frappe.db.table_exists("KTA Print Log"):
        frappe.db.sql("""
            UPDATE `tabKTA Print Log`
            SET label_doctype = 'KTA Stock Label'
            WHERE label_doctype = 'KTA Depo Etiketleri'
        """)
