import frappe


def on_update(doc, method=None):
    # Only care about draft docs for dashboard
    if doc.docstatus != 0:
        return

    frappe.publish_realtime(
        event="stock_reco_dashboard_update",
        message={
            "doctype": doc.doctype,
            "name": doc.name,
            "posting_date": doc.posting_date,
        },
        # Optional: limit to role
        # room="stock_reco_dashboard"
    )