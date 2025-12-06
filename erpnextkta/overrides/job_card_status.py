import frappe

def update_work_order_status(doc, method):
    """Job Card started olduğunda Work Order durumunu otomatik In Process yapar."""

    # Work Order yoksa çık
    if not doc.work_order:
        return

    # Eğer zaman kaydı varsa, bu Job Card çalışmaya başlamış demektir
    has_started = False
    if doc.time_logs:
        for row in doc.time_logs:
            if row.from_time and not row.to_time:
                has_started = True
                break

    if not has_started:
        return

    # Work Order'ı getir
    wo = frappe.get_doc("Work Order", doc.work_order)

    # Eğer zaten Completed / Cancelled değilse, In Process yap
    if wo.status not in ["Completed", "Cancelled"]:
        wo.db_set("status", "In Process")
        frappe.db.commit()
