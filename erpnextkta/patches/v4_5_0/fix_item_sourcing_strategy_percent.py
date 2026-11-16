import frappe


def execute():
	"""tabItem tablosundaki 'Varsayılan Tedarikçi (%%100)' değerlerini '%100' olarak düzeltir."""
	if not frappe.db.has_column("Item", "custom_sourcing_strategy"):
		return

	frappe.db.sql("""
		UPDATE `tabItem`
		SET custom_sourcing_strategy = 'Varsayılan Tedarikçi (%100)'
		WHERE custom_sourcing_strategy = 'Varsayılan Tedarikçi (%%100)'
	""")
