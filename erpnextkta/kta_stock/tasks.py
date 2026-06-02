import frappe

@frappe.whitelist()
def retry_failed_print_jobs():
    """Scheduled: Her 30 dakikada bir Failed print log'larını yeniden dene."""
    failed_logs = frappe.get_all(
        "KTA Print Log",
        filters={"status": "Failed", "attempted_at": [">", frappe.utils.add_hours(frappe.utils.now(), -2)]},
        fields=["name", "label_doctype", "label_name", "user", "zpl_payload"]
    )
    for log in failed_logs:
        if log.label_doctype == "KTA Depo Etiketleri":
            frappe.enqueue(
                "erpnextkta.kta_stock.label_manager._print_pr_labels_by_names",
                label_names=[log.label_name],
                user=log.user,
                queue="short"
            )
        # Diğer label tipleri varsa eklenebilir
