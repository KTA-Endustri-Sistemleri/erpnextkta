# Copyright (c) 2025, Framras AS and Contributors
# See license.txt

import frappe
from erpnextkta.tests.test_utils import KTATestCase

class TestKTACalismaKartiOperasyonlari(KTATestCase):
	def test_plant_floor_required_if_customer_group_set(self):
		"""Müşteri Grubu seçildiğinde Üretim Sahası (Plant Floor) bilgisinin zorunlu olduğunu doğrular."""
		op = frappe.new_doc("KTA Calisma Karti Operasyonlari")
		op.calisma_karti_op = "Test Validation Op"
		op.customer_group = "_Test Customer Group"
		op.plant_floor = None
		
		with self.assertRaises(frappe.ValidationError):
			op.insert()

	def test_duplicate_combination_raises(self):
		"""Aynı (Operasyon, Müşteri Grubu, Üretim Sahası) kombinasyonuyla mükerrer kayıt oluşturulmasını engellediğini doğrular."""
		# First creation (should pass)
		name = "Test Unique Op"
		frappe.db.delete("KTA Calisma Karti Operasyonlari", {"calisma_karti_op": name})
		frappe.db.commit()
		
		op1 = frappe.get_doc({
			"doctype": "KTA Calisma Karti Operasyonlari",
			"calisma_karti_op": name,
			"plant_floor": "L-1"
		}).insert()
		
		# Second creation with same data (should fail)
		op2 = frappe.get_doc({
			"doctype": "KTA Calisma Karti Operasyonlari",
			"calisma_karti_op": name,
			"plant_floor": "L-1"
		})
		
		with self.assertRaises(frappe.DuplicateEntryError):
			op2.insert()
