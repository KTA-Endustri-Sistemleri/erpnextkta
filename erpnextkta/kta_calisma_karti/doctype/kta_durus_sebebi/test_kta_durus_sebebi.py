# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from erpnextkta.tests.test_utils import KTATestCase

class TestKTADurusSebebi(KTATestCase):
	def test_normal_downtime_reason_deletion(self):
		"""Normal bir duruş sebebinin sorunsuz silinebildiğini doğrular."""
		reason_name = "_Test Normal Durus"
		if frappe.db.exists("KTA Durus Sebebi", reason_name):
			frappe.db.delete("KTA Durus Sebebi", {"reason": reason_name})
			frappe.db.commit()
		
		doc = frappe.get_doc({
			"doctype": "KTA Durus Sebebi",
			"reason": reason_name,
			"durus_tipi": "Plansız",
			"is_system": 0
		}).insert()
		
		# Proaktif silme
		doc.delete()
		self.assertFalse(frappe.db.exists("KTA Durus Sebebi", doc.name))

	def test_system_downtime_reason_deletion_raises(self):
		"""Sistem kaydı olarak işaretlenmiş (is_system=1) duruş sebeplerinin silinmesinin engellendiğini doğrular."""
		reason_name = "_Test System Durus"
		
		# Temizlik (bypass için db.delete)
		frappe.db.delete("KTA Durus Sebebi", {"reason": reason_name})
		frappe.db.commit()

		doc = frappe.get_doc({
			"doctype": "KTA Durus Sebebi",
			"reason": reason_name,
			"durus_tipi": "Plansız",
			"is_system": 1
		}).insert()
		
		# Silmeye çalışıldığında ValidationError fırlatmalı
		with self.assertRaises(frappe.ValidationError):
			doc.delete()
		
		self.assertTrue(frappe.db.exists("KTA Durus Sebebi", doc.name))
