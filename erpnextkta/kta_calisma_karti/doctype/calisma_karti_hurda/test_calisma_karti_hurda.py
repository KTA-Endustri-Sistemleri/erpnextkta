# Copyright (c) 2025, Framras AS and Contributors
# See license.txt

import frappe
from unittest.mock import patch
from erpnextkta.tests.test_utils import KTATestCase

class TestCalismaKartiHurda(KTATestCase):
	def test_scrap_sync_to_stock_entry(self):
		"""Hurda satırlarının otomatik olarak Stok Kaydı (Stock Entry) ile senkronize edildiğini doğrular."""
		from erpnextkta.kta_calisma_karti.api_impl.hurda import add_hurda, update_hurda
		
		# 1. Create card
		doc = frappe.get_doc({
			"doctype": "Calisma Karti",
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"operator": "test@kta.com",
			"custom_work_order": self.wo_name
		}).insert(ignore_permissions=True, ignore_links=True)
		
		# 1. Setup Scrap Synchronization environment
		# Mock settings for sync
		frappe.db.set_single_value("KTA Calisma Karti Settings", "hurda_gider_hesabi", self.expense_account)
		
		# Root CC for this company
		root_cc = f"{self.company} - TKTA"
		
		# Monkeypatch HURDA_PARENT_COST_CENTER to use our root
		from erpnextkta.kta_calisma_karti.api_impl import hurda, _helpers
		with patch.object(hurda, "HURDA_PARENT_COST_CENTER", root_cc), \
			 patch.object(_helpers, "HURDA_PARENT_COST_CENTER", root_cc), \
			 patch("erpnextkta.kta_calisma_karti.api_impl.hurda.get_allowed_items_with_groups", return_value=[self.item]), \
			 patch("erpnextkta.kta_calisma_karti.api_impl.hurda._get_item_wo_defaults", return_value=(self.wip_warehouse, "Nos")):
			
			reason = "Test Scrap CC - TKTA"
			if not frappe.db.exists("Cost Center", reason):
				frappe.get_doc({
					"doctype": "Cost Center", 
					"cost_center_name": "Test Scrap CC", 
					"company": self.company, 
					"is_group": 0,
					"parent_cost_center": root_cc
				}).insert(ignore_permissions=True, ignore_links=True)

			# 2. Add hurda via API
			add_hurda(doc.name, self.item, reason, 5.0, "Some Comment")
			
			doc.reload()
			se_name = doc.scrap_stock_entry
			self.assertTrue(se_name)
			
			# 3. Verify Stock Entry
			se_doc = frappe.get_doc("Stock Entry", se_name)
			self.assertEqual(se_doc.purpose, "Material Issue")
			self.assertEqual(len(se_doc.items), 1)
			
			# 4. Update row in Card and verify sync
			row_name = doc.hurdalar[0].name
			update_hurda(doc.name, row_name, self.item, reason, 10.0, "Updated")
			
			se_doc.reload()
			matched = next((d for d in se_doc.items if d.item_code == self.item), None)
			self.assertEqual(float(matched.qty), 10.0)
