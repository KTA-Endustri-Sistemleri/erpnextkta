# Copyright (c) 2025, KTA Endüstri Sistemleri and contributors
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

	def test_no_duplicate_se_created_after_scrap_se_submitted(self):
		"""Onaylanmış (docstatus=1) veya iptal edilmiş (docstatus=2) hurda Stock Entry'si olan kart güncellendiğinde/onaylandığında mükerrer SE oluşturulmamalı."""
		from types import SimpleNamespace
		from erpnextkta.kta_calisma_karti.api_impl import hurda

		hurda_row = SimpleNamespace(
			name="HRD-ROW-1",
			parca_no="10020436",
			miktar=50.0,
			hurda_nedeni="Test CC",
			aciklama="",
			birim="Adet",
			depo="1501 KESMELER - KTA",
			stock_entry_detail_id="SED-SUBMITTED-1",
		)
		ck_doc = SimpleNamespace(
			name="TEST-CK-001",
			custom_work_order="MFG-WO-TEST-001",
			get=lambda field: [hurda_row] if field == "hurdalar" else None,
		)

		def fake_get_value(doctype, name, fieldname, *args, **kwargs):
			if doctype == "Calisma Karti" and fieldname == "scrap_stock_entry":
				return "MAT-STE-SUBMITTED-1"
			if doctype == "Stock Entry" and fieldname == "docstatus":
				return 1
			return None

		with patch.object(hurda, "get_child_table_fieldname", return_value="hurdalar"), \
			 patch.object(hurda, "_get_finalized_scrap_detail_ids", return_value={"SED-SUBMITTED-1"}), \
			 patch.object(hurda.frappe.db, "get_value", side_effect=fake_get_value), \
			 patch.object(hurda, "_get_or_create_scrap_se") as mock_get_or_create:
			hurda.sync_calisma_karti_hurdalar_to_se(ck_doc)
			mock_get_or_create.assert_not_called()

	def test_only_new_hurda_rows_synced_when_previous_se_submitted(self):
		"""Önceki hurda satırı onaylanmış SE'deyken yeni satır eklenirse, yeni taslak SE'ye yalnızca yeni satır eklenmeli."""
		from types import SimpleNamespace
		from erpnextkta.kta_calisma_karti.api_impl import hurda

		old_row = SimpleNamespace(
			name="HRD-ROW-OLD",
			parca_no="10020436",
			miktar=50.0,
			hurda_nedeni="Test CC",
			aciklama="",
			birim="Adet",
			depo="1501 KESMELER - KTA",
			stock_entry_detail_id="SED-SUBMITTED-1",
		)
		new_row = SimpleNamespace(
			name="HRD-ROW-NEW",
			parca_no="10020436",
			miktar=15.0,
			hurda_nedeni="Test CC",
			aciklama="",
			birim="Adet",
			depo="1501 KESMELER - KTA",
			stock_entry_detail_id=None,
		)
		ck_doc = SimpleNamespace(
			name="TEST-CK-002",
			custom_work_order="MFG-WO-TEST-002",
			get=lambda field: [old_row, new_row] if field == "hurdalar" else None,
		)

		class FakeSE:
			def __init__(self):
				self.name = "MAT-STE-NEW-DRAFT"
				self.docstatus = 0
				self.items = []
				self.inserted = False

			def append(self, field, row_dict):
				item = SimpleNamespace(name=f"SED-NEW-{len(self.items) + 1}", **row_dict)
				self.items.append(item)
				return item

			def insert(self, ignore_permissions=False):
				self.inserted = True

			def reload(self):
				pass

		fake_se = FakeSE()

		def fake_get_value(doctype, name, fieldname, *args, **kwargs):
			if doctype == "Calisma Karti" and fieldname == "scrap_stock_entry":
				return "MAT-STE-SUBMITTED-1"
			if doctype == "Stock Entry" and fieldname == "docstatus":
				return 1
			return None

		with patch.object(hurda, "get_child_table_fieldname", return_value="hurdalar"), \
			 patch.object(hurda, "_get_finalized_scrap_detail_ids", return_value={"SED-SUBMITTED-1"}), \
			 patch.object(hurda.frappe.db, "get_value", side_effect=fake_get_value), \
			 patch.object(hurda, "_get_or_create_scrap_se", return_value=(fake_se, None, True)), \
			 patch.object(hurda, "_get_expense_account", return_value="689 - Hurda"), \
			 patch.object(hurda, "_get_item_wo_defaults", return_value=("1501 KESMELER - KTA", "Adet")), \
			 patch.object(hurda.frappe.db, "set_value") as mock_set_value, \
			 patch.object(hurda.frappe.db, "commit"):
			hurda.sync_calisma_karti_hurdalar_to_se(ck_doc)

			self.assertTrue(fake_se.inserted)
			self.assertEqual(len(fake_se.items), 1)
			self.assertEqual(fake_se.items[0].qty, 15.0)
			# Ensure stock_entry_detail_id was written back for the new row
			mock_set_value.assert_any_call(
				"Calisma Karti Hurda", "HRD-ROW-NEW", "stock_entry_detail_id", "SED-NEW-1", update_modified=False
			)
