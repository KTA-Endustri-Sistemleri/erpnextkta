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
                
            # Check if item requires quality inspection
            req_qi = frappe.db.get_value("Item", item.item_code, "inspection_required_before_purchase")
            if req_qi:
                qi_docs = frappe.db.get_all(
                    "Quality Inspection",
                    filters={
                        "reference_type": "Purchase Receipt",
                        "reference_name": batch.reference_name,
                        "item_code": item.item_code,
                        "docstatus": ["<", 2]
                    },
                    fields=["name", "status", "docstatus"]
                )

                if not qi_docs:
                    atlama_sayisi = frappe.db.get_value("Item", item.item_code, "custom_atlama_sayisi") or 0
                    if atlama_sayisi > 0:
                        continue
                    frappe.throw(
                        f"<b>HATA:</b> {batch_no} numaralı parti için henüz bir Kalite Kontrol (GKK) belgesi oluşturulmamıştır! <br>"
                        f"Lütfen önce <b>{batch.reference_name}</b> irsaliyesi üzerinden Kalite Kontrol belgesi oluşturup onaylayın."
                    )
                else:
                    qi_doc = qi_docs[0]
                    if qi_doc.status != "Accepted" or qi_doc.docstatus != 1:
                        # Allow transfer to rejected warehouse only if the QI is submitted and rejected
                        if qi_doc.docstatus == 1 and qi_doc.status == "Rejected":
                            target_wh = item.get("t_warehouse") or item.get("target_warehouse") or item.get("to_warehouse")
                            if target_wh and frappe.db.get_value("Warehouse", target_wh, "is_rejected_warehouse"):
                                continue

                        frappe.throw(
                            f"<b>HATA:</b> {batch_no} numaralı parti henüz Kalite Kontrol (GKK) onayı almadığı için transfer edilemez! <br>"
                            f"Lütfen önce <b>{qi_doc.name}</b> numaralı Kalite Kontrol belgesini onaylayın."
                        )

