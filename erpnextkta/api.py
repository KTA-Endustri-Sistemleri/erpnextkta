import frappe

@frappe.whitelist()
def get_customer_income_account(customer, company):
    party_account = frappe.get_value(
        'Party Account',
        {'parent': customer, 'parenttype': 'Customer', 'company': company},
        'customer_income_account'  # Replace with the actual fieldname
    )
    return party_account