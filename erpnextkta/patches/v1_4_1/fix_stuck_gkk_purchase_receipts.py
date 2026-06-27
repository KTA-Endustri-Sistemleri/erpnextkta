import frappe


def execute():
	# Update draft Purchase Receipts stuck in 'GKK Bekliyor' to 'Mal Giriş'
	frappe.db.sql(
		"""
		UPDATE `tabPurchase Receipt`
		SET workflow_state = 'Mal Giriş'
		WHERE workflow_state = 'GKK Bekliyor' AND docstatus = 0
	"""
	)
