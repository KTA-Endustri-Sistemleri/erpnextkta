import frappe


def execute():
	# Update historical cancelled Calisma Karti records to have durum = 'İptal Edildi'
	frappe.db.sql(
		"""
		UPDATE `tabCalisma Karti`
		SET durum = 'İptal Edildi'
		WHERE docstatus = 2 AND durum != 'İptal Edildi'
		"""
	)
