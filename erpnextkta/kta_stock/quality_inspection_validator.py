import frappe

def validate_batch_qi_on_transfer(doc, method=None):
    """
    Called on before_submit of Stock Entry, Delivery Note etc.
    Blocks the transfer of items if they belong to a batch created by a Purchase Receipt
    that has a pending Quality Inspection.
    """
    if doc.doctype == "Stock Entry" and doc.purpose == "Material Receipt":
        return

    for item in doc.items:
        batches = []
        
        bundle_id = item.get("serial_and_batch_bundle")
        if bundle_id:
            entries = frappe.db.get_all("Serial and Batch Entry", filters={"parent": bundle_id}, fields=["batch_no"])
            batches = [e.batch_no for e in entries if e.batch_no]
        
        # Fallback to older batch_no field if bundle is not used
        if not batches and item.get("batch_no"):
            batches = [item.get("batch_no")]

        for batch_no in batches:
            batch = frappe.db.get_value("Batch", batch_no, ["reference_doctype", "reference_name"], as_dict=True)
            if not batch or batch.reference_doctype != "Purchase Receipt":
                continue
                
            # Check if this PR generated a QI for this item
            pending_qi = frappe.db.get_value(
                "Quality Inspection", 
                {
                    "reference_type": "Purchase Receipt",
                    "reference_name": batch.reference_name,
                    "item_code": item.item_code,
                    "status": ["!=", "Accepted"],
                    "docstatus": ["<", 2]
                },
                "name"
            )
            
            if pending_qi:
                frappe.throw(
                    f"<b>HATA:</b> {batch_no} numaralı parti henüz Kalite Kontrol (GKK) onayı almadığı için transfer edilemez! <br>"
                    f"Lütfen önce <b>{pending_qi}</b> numaralı Kalite Kontrol belgesini onaylayın."
                )
