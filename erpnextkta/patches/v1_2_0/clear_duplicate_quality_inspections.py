import frappe

def execute():
    """
    Clears duplicate links in the quality_inspection field of Calisma Karti.
    This patch is intended to run before model sync to allow the addition of a 
    unique constraint on this field.
    
    Rule: Keep the earliest (first created) record, clear the link for all others.
    """
    # Find all duplicate quality_inspection values
    duplicates = frappe.db.sql("""
        SELECT quality_inspection, COUNT(*) as count
        FROM `tabCalisma Karti`
        WHERE quality_inspection IS NOT NULL 
          AND quality_inspection != ''
        GROUP BY quality_inspection
        HAVING count > 1
    """, as_dict=True)

    if not duplicates:
        return

    updated_count = 0
    for d in duplicates:
        # Get all records for this inspection, ordered by creation (earliest first)
        # We process ALL records regardless of docstatus because database uniqueness 
        # constraints apply to the whole table.
        cards = frappe.get_all("Calisma Karti",
            filters={"quality_inspection": d.quality_inspection},
            fields=["name", "creation"],
            order_by="creation ASC"
        )

        if len(cards) <= 1:
            continue
        
        # Keep the first one (index 0), clear the rest
        to_clear = [c.name for c in cards[1:]]
        
        for docname in to_clear:
            # Update database directly to avoid triggering validatons or changing modified timestamps
            frappe.db.set_value("Calisma Karti", docname, "quality_inspection", None, update_modified=False)
            updated_count += 1

    if updated_count:
        frappe.db.commit()
        frappe.logger().info(f"clear_duplicate_quality_inspections: Cleared {updated_count} duplicate links in tabCalisma Karti.")
