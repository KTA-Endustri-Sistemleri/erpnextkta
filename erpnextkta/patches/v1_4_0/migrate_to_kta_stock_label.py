import frappe

def execute():
    # Migrate KTA Depo Etiketleri to KTA Stock Label
    if frappe.db.exists("DocType", "KTA Depo Etiketleri") and frappe.db.exists("DocType", "KTA Stock Label"):
        depo_etiketleri = frappe.get_all("KTA Depo Etiketleri", fields=["*"])
        for etiket in depo_etiketleri:
            # Create KTA Stock Label
            new_label = frappe.new_doc("KTA Stock Label")
            new_label.label_type = "Depo Giriş Etiketi"
            new_label.reference_doctype = "Purchase Receipt"
            new_label.reference_name = etiket.gr_number
            
            # Copy matching fields
            fields_to_copy = [
                "item_code", "item_name", "item_group", "qty", "uom", 
                "batch", "sut_barcode", "quality_ref", "supplier_delivery_note",
                "gr_posting_date", "print_count", "last_printed_at", 
                "last_printed_by", "do_not_split"
            ]
            for field in fields_to_copy:
                if etiket.get(field) is not None:
                    new_label.set(field, etiket.get(field))
            
            new_label.flags.ignore_permissions = True
            new_label.flags.ignore_mandatory = True
            new_label.flags.ignore_validate = True
            new_label.flags.ignore_links = True
            new_label.insert()
            
            # Migrate child table KTA Depo Etiketleri Bolme
            splits = frappe.get_all("KTA Depo Etiketleri Bolme", filters={"parent": etiket.name}, fields=["*"])
            for split in splits:
                new_label.append("splits", {
                    "qty": split.qty,
                    "uom": split.uom,
                    "sut_barcode": split.sut_barcode
                })
            
            if splits:
                new_label.save()

    # Rename Zebra Templates using SQL to bypass missing module ImportErrors
    if frappe.db.exists("DocType", "KTA Zebra Templates"):
        if frappe.db.exists("KTA Zebra Templates", "KTA Depo Etiketleri"):
            frappe.db.sql("""UPDATE `tabKTA Zebra Templates` SET name = 'Depo Giriş Etiketi' WHERE name = 'KTA Depo Etiketleri'""")
        if frappe.db.exists("KTA Zebra Templates", "KTA Is Emri Etiketleri"):
            frappe.db.sql("""UPDATE `tabKTA Zebra Templates` SET name = 'İş Emri Etiketi' WHERE name = 'KTA Is Emri Etiketleri'""")

    # Update old Print Logs to new DocType
    if frappe.db.exists("DocType", "KTA Print Log"):
        frappe.db.sql("""
            UPDATE `tabKTA Print Log`
            SET label_doctype = 'KTA Stock Label'
            WHERE label_doctype IN ('KTA Depo Etiketleri', 'KTA Is Emri Etiketleri')
        """)

    # Fix existing DocType Link to prevent DuplicateEntryError during sync_customizations
    frappe.db.sql("""
        UPDATE `tabDocType Link`
        SET link_fieldname = 'reference_name'
        WHERE name = 'kta_pr_stock_label' AND link_fieldname = 'gr_number'
    """)

