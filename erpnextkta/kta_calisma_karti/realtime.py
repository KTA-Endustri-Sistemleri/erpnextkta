import frappe

def publish_calisma_karti_changed(docname: str, reason: str = "updated"):
    payload = {"name": docname, "reason": reason}

    # List ekranları için: herkese
    frappe.publish_realtime(
        "kta_calisma_karti:list_changed",
        payload,
        after_commit=True,
    )

    # Detay ekranı için: sadece o doc'u izleyenler
    frappe.publish_realtime(
        f"kta_calisma_karti:doc_changed:{docname}",
        payload,
        after_commit=True,
    )