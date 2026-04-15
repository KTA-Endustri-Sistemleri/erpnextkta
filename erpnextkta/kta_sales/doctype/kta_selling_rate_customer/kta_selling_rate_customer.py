import frappe
from frappe.model.document import Document

class KTASellingRateCustomer(Document):
	pass


def is_selling_rate_customer(customer: str) -> bool:
	"""Check if a customer is configured to use selling exchange rate."""
	if not customer:
		return False

	customers = frappe.db.get_all(
		"KTA Selling Rate Customer Item",
		filters={"parent": "KTA Selling Rate Customer", "customer": customer},
		limit=1,
	)
	return bool(customers)
