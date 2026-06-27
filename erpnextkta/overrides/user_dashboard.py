import frappe

def get_dashboard_data(data):
    if not data:
        data = frappe._dict()

    if not data.transactions:
        data.transactions = []

    # Find the 'Activity' group and append 'Calisma Karti'
    added = False
    for group in data.transactions:
        if group.get("label") == "Activity":
            if "Calisma Karti" not in group.get("items", []):
                group.setdefault("items", []).append("Calisma Karti")
            added = True
            break

    if not added:
        data.transactions.append({
            "label": "Activity",
            "items": ["Calisma Karti"]
        })

    # Set custom method for counts
    data.method = "erpnextkta.overrides.user_dashboard.get_open_count"
    
    # We must specify that Calisma Karti is in internal_links
    # so that the dashboard knows to treat it as an internal link
    # (i.e. using 'names' list)
    if not data.internal_links:
        data.internal_links = {}
    data.internal_links["Calisma Karti"] = "name" # dummy field

    return data


@frappe.whitelist()
def get_open_count(doctype, name, items=None):
    # Call standard get_open_count
    from frappe.desk.notifications import _get_linked_document_counts
    res = _get_linked_document_counts(doctype, name, items)
    
    # Now, find Calisma Karti records for the User (name)
    # Find employee(s) for the user
    employee_names = frappe.get_all("Employee", filters={"user_id": name}, pluck="name")
    
    card_names = []
    if employee_names:
        # Find Calisma Karti where operator is in employee_names
        card_names = frappe.get_all("Calisma Karti", filters={"operator": ["in", employee_names]}, pluck="name")
    
    # Remove from external links if present
    ext_links = res.get("count", {}).get("external_links_found", [])
    res["count"]["external_links_found"] = [el for el in ext_links if el.get("doctype") != "Calisma Karti"]
    
    # Add to internal links
    int_links = res.get("count", {}).get("internal_links_found", [])
    # Remove existing Calisma Karti from internal links if any
    int_links = [il for il in int_links if il.get("doctype") != "Calisma Karti"]
    
    int_links.append({
        "doctype": "Calisma Karti",
        "open_count": 0,
        "count": len(card_names),
        "names": card_names
    })
    
    res["count"]["internal_links_found"] = int_links
    
    return res
