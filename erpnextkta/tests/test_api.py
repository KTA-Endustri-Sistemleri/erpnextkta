# API Tests for KTA Calisma Karti

import frappe
from erpnextkta.tests.test_utils import KTATestCase
from erpnextkta.kta_calisma_karti.api_impl.create import create_calisma_karti
from erpnextkta.kta_calisma_karti.api_impl.cards import islem_yap
from erpnextkta.kta_calisma_karti.api_impl.qc import submit_kta_quality_inspection
from erpnextkta.kta_calisma_karti.api_impl.hurda import add_hurda, delete_hurda
from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import add_alt_operasyon_kaydi

class TestCalismaKartiAPI(KTATestCase):
	def setUp(self):
		super().setUp()
		# Seed extra employees for isolated tests
		from erpnextkta.tests.test_utils import create_test_operator
		for emp_email in ["workflow@kta.com", "qc@kta.com", "scrap@kta.com", "altop@kta.com"]:
			create_test_operator(emp_email, emp_email.split("@")[0].capitalize())

		# Ensure a clean slate for this specific test case payload across runs
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": "test@kta.com"})
		
		# Ensure Work Order has source_warehouse (for scrap sync)
		frappe.db.set_value("Work Order", self.wo_name, "source_warehouse", self.wip_warehouse)
		# Ensure KTA Settings has expense account
		frappe.db.set_single_value("KTA Calisma Karti Settings", "hurda_gider_hesabi", self.expense_account)
		
		frappe.db.commit()

	def test_create_calisma_karti_double_click_protection(self):
		"""Kısa aralıklarla yapılan mükerrer oluşturma isteklerinin aynı dokümanı döndürdüğünü doğrular."""
		payload = {
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"operator": "test@kta.com"
		}
		
		# First call creates the card
		doc1 = create_calisma_karti(**payload)
		
		# Second call (immediate) should return the SAME card
		doc2 = create_calisma_karti(**payload)
		
		self.assertEqual(doc1.get("name"), doc2.get("name"), "Should return the same card on second click")
		
		# Verify only one record exists in DB
		count = frappe.db.count("Calisma Karti", {
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"operator": "test@kta.com"
		})
		self.assertEqual(count, 1, "Duplicate record should NOT be created")

	def test_islem_yap_workflow(self):
		"""İş akış adımlarının (Başlat, Duruş, Devam, Bitiş) API üzerinden doğru çalıştığını doğrular."""
		payload = {
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"operator": "workflow@kta.com"
		}
		doc = create_calisma_karti(**payload)
		docname = doc.get("name")

		# 1. Başlat
		res = islem_yap(docname, "Baslat")
		self.assertEqual(res["durum"], "calisiyor")
		
		# 2. Duruş
		res = islem_yap(docname, "Durus", durus_nedeni="Diğer", aciklama="Test durusu")
		self.assertEqual(res["durum"], "durusta")
		
		# 3. Devam Et
		res = islem_yap(docname, "DevamEt")
		self.assertEqual(res["durum"], "calisiyor")
		
		# 4. Bitiş
		res = islem_yap(docname, "Bitis", tamamlanan_miktar=10)
		self.assertEqual(res["durum"], "bitmis")
		
		# Veritabanında submit edildiğini doğrula
		self.assertEqual(frappe.db.get_value("Calisma Karti", docname, "docstatus"), 1)

	def test_qc_submission_via_api(self):
		"""API üzerinden Kalite Kontrol gönderimini ve kart üzerindeki etkisini doğrular."""
		# Setup template
		template_name = "TEST-API-QC-TEMPLATE"
		if not frappe.db.exists("Quality Inspection Template", template_name):
			frappe.get_doc({
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": template_name,
				"item_quality_inspection_parameter": [
					{"specification": "Test Spec", "numeric": 0, "value": "OK"}
				]
			}).insert(ignore_permissions=True)

		doc = create_calisma_karti(is_karti=self.jc_name, operasyon=self.kta_op, is_istasyonu=self.ws_name, operator="qc@kta.com")
		docname = doc.get("name")

		readings = [{"specification": "Test Spec", "numeric": 0, "reading_value": "OK", "status": "Accepted"}]
		
		# Submit QC
		res = submit_kta_quality_inspection(docname, template_name, readings, intent="approve")
		qi_name = res["quality_inspection"]
		
		# Kart üzerindeki etkileri kontrol et
		ck_doc = frappe.get_doc("Calisma Karti", docname)
		self.assertEqual(ck_doc.quality_inspection, qi_name)
		self.assertEqual(ck_doc.kalite_kontrol, "Onaylandı")
		
		# QI'nın draft olduğunu doğrula (Bitis'e kadar draft kalmalı)
		self.assertEqual(frappe.db.get_value("Quality Inspection", qi_name, "docstatus"), 0)

	def test_scrap_synchronization_via_api(self):
		"""Hurda ekleme ve silme işlemlerinin Stok Girişi ile senkronize olduğunu doğrular."""
		import erpnextkta.kta_calisma_karti.api_impl.hurda as hurda_module
		import erpnextkta.kta_calisma_karti.api_impl._helpers as helpers_module

		doc = create_calisma_karti(is_karti=self.jc_name, operasyon=self.kta_op, is_istasyonu=self.ws_name, operator="scrap@kta.com")
		docname = doc.get("name")

		# FIND any group cost center for the company to use as parent for monkeypatching
		any_group_cc = frappe.db.get_value("Cost Center", {"is_group": 1, "company": self.company}, "name")
		
		# Update Settings so that future calls (if they read from DB) see this
		frappe.db.set_single_value("KTA Calisma Karti Settings", "hurda_ust_masraf_merkezi", any_group_cc)

		# MONKEYPATCH: Use a valid group parent CC from the environment
		orig_hurda_cc = hurda_module.HURDA_PARENT_COST_CENTER
		hurda_module.HURDA_PARENT_COST_CENTER = any_group_cc
		helpers_module.HURDA_PARENT_COST_CENTER = any_group_cc

		# MONKEYPATCH: Disable BOM based item validation for this test
		orig_validate_item = hurda_module._assert_hurda_item_allowed_for_operation
		hurda_module._assert_hurda_item_allowed_for_operation = lambda doc, item: True

		try:
			# Hurda Nedeni (Cost Center) kur - MUST be a child of our monkeypatched parent
			cc_name = "TEST-SCRAP-CC"
			if not frappe.db.exists("Cost Center", f"{cc_name} - TKTA"):
				cc_doc = frappe.get_doc({
					"doctype": "Cost Center",
					"cost_center_name": cc_name,
					"parent_cost_center": any_group_cc,
					"is_group": 0,
					"company": self.company
				}).insert(ignore_permissions=True, ignore_links=True)
				cc_name = cc_doc.name
			else:
				cc_name = f"{cc_name} - TKTA"

			# 1. Hurda Ekle
			res = add_hurda(docname, parca_no=self.item, hurda_nedeni=cc_name, miktar=5)
			se_name = res["stock_entry"]
			
			# Stok Girişi oluştu mu?
			self.assertTrue(frappe.db.exists("Stock Entry", se_name))
			se_doc = frappe.get_doc("Stock Entry", se_name)
			self.assertEqual(len(se_doc.items), 1)
			self.assertEqual(se_doc.items[0].qty, 5)
			
			# 2. Hurda Sil
			ck_doc = frappe.get_doc("Calisma Karti", docname)
			rowname = ck_doc.hurdalar[0].name
			delete_hurda(docname, rowname)
			
			self.assertFalse(frappe.db.exists("Stock Entry", se_name))
		finally:
			# Restore monkeypatched values
			hurda_module.HURDA_PARENT_COST_CENTER = orig_hurda_cc
			helpers_module.HURDA_PARENT_COST_CENTER = orig_hurda_cc
			hurda_module._assert_hurda_item_allowed_for_operation = orig_validate_item

	def test_alt_operasyon_crud_via_api(self):
		"""Alt operasyon kayıtlarının API üzerinden eklenip silinebildiğini doğrular."""
		# Master alt op kur (autoname includes title, so make title unique)
		unique_title = f"Test Alt Op {frappe.generate_hash(length=8)}"
		master_doc = frappe.get_doc({
			"doctype": "KTA Calisma Karti Alt Operasyonlari",
			"title": unique_title,
			"parent_operation": self.kta_op,
			"sequence": 10
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)
		master_alt_op = master_doc.name

		doc = create_calisma_karti(is_karti=self.jc_name, operasyon=self.kta_op, is_istasyonu=self.ws_name, operator="altop@kta.com")
		docname = doc.get("name")

		# Ekle
		add_alt_operasyon_kaydi(docname, master_alt_op)
		
		ck_doc = frappe.get_doc("Calisma Karti", docname)
		self.assertEqual(len(ck_doc.alt_operasyon_kayitlari), 1)
		self.assertEqual(ck_doc.alt_operasyon_kayitlari[0].alt_operasyon, master_alt_op)
