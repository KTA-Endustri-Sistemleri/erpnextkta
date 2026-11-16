import frappe
from frappe.utils import cint


def execute():
	"""KTA Sevk Parametreleri kayıtlarını Address ve Customer üzerindeki

	custom_shipping_lead_days alanlarına taşır.
	"""
	if not frappe.db.table_exists("KTA Sevk Parametreleri"):
		return

	if not frappe.db.has_column("Address", "custom_shipping_lead_days"):
		frappe.db.sql("ALTER TABLE `tabAddress` ADD COLUMN IF NOT EXISTS `custom_shipping_lead_days` INT DEFAULT 0")

	if not frappe.db.has_column("Customer", "custom_shipping_lead_days"):
		frappe.db.sql("ALTER TABLE `tabCustomer` ADD COLUMN IF NOT EXISTS `custom_shipping_lead_days` INT DEFAULT 0")

	records = frappe.get_all(
		"KTA Sevk Parametreleri",
		fields=["name", "customer_name", "customer_address", "production_time", "delivery_time"],
	)

	migrated_addresses = 0
	migrated_customers = 0

	for r in records:
		delivery_days = cint(r.delivery_time or 0)
		if delivery_days <= 0:
			continue

		# 1. Adres bazlı taşıma (Plant)
		if r.customer_address and frappe.db.exists("Address", r.customer_address):
			current_val = frappe.db.get_value("Address", r.customer_address, "custom_shipping_lead_days")
			if not current_val:
				frappe.db.set_value(
					"Address",
					r.customer_address,
					"custom_shipping_lead_days",
					delivery_days,
					update_modified=False,
				)
				migrated_addresses += 1

		# 2. Müşteri bazlı taşıma (Genel müşteri varsayılanı)
		if r.customer_name and frappe.db.exists("Customer", r.customer_name):
			current_val = frappe.db.get_value("Customer", r.customer_name, "custom_shipping_lead_days")
			if not current_val:
				frappe.db.set_value(
					"Customer",
					r.customer_name,
					"custom_shipping_lead_days",
					delivery_days,
					update_modified=False,
				)
				migrated_customers += 1

	frappe.db.commit()
	print(
		f"Migrated KTA Sevk Parametreleri: {migrated_addresses} addresses, {migrated_customers} customers."
	)
