import frappe


def execute():
	"""Backfill tahmini_varis_tarihi for existing transit (Yolda) Purchase Receipts

	that were created before ETA was made mandatory.
	"""
	frappe.db.sql(
		"""
		UPDATE `tabPurchase Receipt`
		SET tahmini_varis_tarihi = DATE_ADD(yukleme_tarihi, INTERVAL 7 DAY)
		WHERE workflow_state = 'Yolda'
		  AND docstatus < 2
		  AND tahmini_varis_tarihi IS NULL
		  AND yukleme_tarihi IS NOT NULL
		"""
	)
