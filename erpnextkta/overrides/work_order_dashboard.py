import frappe

def get_dashboard_data(data):
    if not data:
        data = frappe._dict()

    if not data.transactions:
        data.transactions = []

    # Find the 'Transactions' group and append 'Calisma Karti'
    added = False
    for group in data.transactions:
        if group.get("label") == "Transactions":
            if "Calisma Karti" not in group.get("items", []):
                group.setdefault("items", []).append("Calisma Karti")
            added = True
            break

    if not added:
        data.transactions.append({
            "label": "Transactions",
            "items": ["Calisma Karti"]
        })

    # Ensure non_standard_fieldnames exist and set Calisma Karti mapping
    if not data.non_standard_fieldnames:
        data.non_standard_fieldnames = {}
    data.non_standard_fieldnames["Calisma Karti"] = "custom_work_order"

    return data
