# API Tests for KTA Calisma Karti

import frappe
from erpnextkta.tests.test_utils import KTATestCase
from erpnextkta.kta_calisma_karti.api_impl.create import create_calisma_karti
from erpnextkta.kta_calisma_karti.api_impl.cards import islem_yap
from erpnextkta.kta_calisma_karti.api_impl.qc import submit_kta_quality_inspection
from erpnextkta.kta_calisma_karti.api_impl.hurda import add_hurda, delete_hurda
from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import add_alt_operasyon_kaydi, delete_alt_operasyon_kaydi

class TestCalismaKartiAPI(KTATestCase):
	def setUp(self):
		super().setUp()
		# Seed extra employees for isolated tests
		from erpnextkta.tests.test_utils import create_test_operator
		for emp_email in ["workflow@kta.com", "qc@kta.com", "scrap@kta.com", "altop@kta.com"]:
			create_test_operator(emp_email, emp_email.split("@")[0].capitalize())

		# Ensure a clean slate for this specific test case payload across runs
		for operator in ["test@kta.com", "workflow@kta.com", "qc@kta.com", "scrap@kta.com", "altop@kta.com"]:
			frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": operator})
		
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
		
		# 4. Bitiş (artık alt operasyon zorunlu)
		unique_title = f"Test Alt Op {frappe.generate_hash(length=8)}"
		master_doc = frappe.get_doc({
			"doctype": "KTA Calisma Karti Alt Operasyonlari",
			"title": unique_title,
			"parent_operation": self.kta_op,
			"sequence": 10
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)
		add_alt_operasyon_kaydi(docname, master_doc.name)
		
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
		from unittest.mock import patch

		doc = create_calisma_karti(is_karti=self.jc_name, operasyon=self.kta_op, is_istasyonu=self.ws_name, operator="scrap@kta.com")
		docname = doc.get("name")

		# FIND any group cost center for the company to use as parent for monkeypatching
		any_group_cc = frappe.db.get_value("Cost Center", {"is_group": 1, "company": self.company}, "name")
		
		# Update Settings so that future calls (if they read from DB) see this
		frappe.db.set_single_value("KTA Calisma Karti Settings", "hurda_ust_masraf_merkezi", any_group_cc)

		# Use mock.patch context managers to safely monkeypatch values and restore them automatically
		with patch("erpnextkta.kta_calisma_karti.api_impl.hurda.HURDA_PARENT_COST_CENTER", any_group_cc), \
		     patch("erpnextkta.kta_calisma_karti.api_impl._helpers.HURDA_PARENT_COST_CENTER", any_group_cc), \
		     patch("erpnextkta.kta_calisma_karti.api_impl.hurda._assert_hurda_item_allowed_for_operation", lambda doc, item: True):

			# Hurda Nedeni (Cost Center) kur - MUST be a child of our mocked parent
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

	def test_rejected_card_allows_new_card_creation(self):
		"""Reddedilmiş kart taslak olarak kalsa bile, aynı iş için yeni kart açılabilmeli."""
		payload = {
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"operator": "test@kta.com",
		}

		# 1. İlk kart oluştur
		doc1 = create_calisma_karti(**payload)
		docname1 = doc1.get("name")

		# 2. Kartı doğrudan reddedilmiş olarak işaretle (Faz 3 öncesi senaryoyu simüle et)
		frappe.db.set_value("Calisma Karti", docname1, "kalite_kontrol", "Reddedildi")
		frappe.db.set_value("Calisma Karti", docname1, "durum", "Reddedildi")
		frappe.db.commit()

		# Kart hâlâ taslak + bitis_saati yok -> orijinal bug senaryosu
		ck = frappe.db.get_value(
			"Calisma Karti", docname1,
			["docstatus", "bitis_saati", "kalite_kontrol"], as_dict=True
		)
		self.assertEqual(ck.docstatus, 0)
		self.assertIsNone(ck.bitis_saati)
		self.assertEqual(ck.kalite_kontrol, "Reddedildi")

		# 3. Aynı payload ile yeni kart oluştur — FARKLI kart dönmeli
		doc2 = create_calisma_karti(**payload)
		docname2 = doc2.get("name")

		self.assertNotEqual(
			docname1, docname2,
			"Reddedilmiş kart mevcutken yeni kart oluşturulabilmeli"
		)

	def test_reject_flow_qi_is_submitted(self):
		"""Red kararında Quality Inspection'ın hemen submit edildiğini doğrular (orphan önleme)."""
		# QC Template kur
		template_name = "TEST-REJECT-QC-TEMPLATE"
		if not frappe.db.exists("Quality Inspection Template", template_name):
			frappe.get_doc({
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": template_name,
				"item_quality_inspection_parameter": [
					{"specification": "Görsel Kontrol", "numeric": 0, "value": "OK"}
				]
			}).insert(ignore_permissions=True)

		# Kart oluştur
		from erpnextkta.tests.test_utils import create_test_operator
		create_test_operator("reject_qi@kta.com", "Reject QI Test")
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": "reject_qi@kta.com"})
		frappe.db.commit()

		doc = create_calisma_karti(
			is_karti=self.jc_name, operasyon=self.kta_op,
			is_istasyonu=self.ws_name, operator="reject_qi@kta.com"
		)
		docname = doc.get("name")

		readings = [{"specification": "Görsel Kontrol", "numeric": 0,
					 "reading_value": "NOK", "status": "Rejected"}]

		# Red kararı ver
		res = submit_kta_quality_inspection(docname, template_name, readings, intent="reject")
		qi_name = res["quality_inspection"]

		# QI hemen submit edilmiş olmalı (docstatus=1)
		qi_docstatus = frappe.db.get_value("Quality Inspection", qi_name, "docstatus")
		self.assertEqual(qi_docstatus, 1, "Red kararında QI hemen submit edilmeli (orphan kalmamalı)")

		# Kart QC durumu doğru
		ck = frappe.db.get_value(
			"Calisma Karti", docname, ["kalite_kontrol", "durum"], as_dict=True
		)
		self.assertEqual(ck.kalite_kontrol, "Reddedildi")
		self.assertEqual(ck.durum, "Reddedildi")

	def test_reject_flow_card_is_auto_submitted(self):
		"""Red kararında kartın otomatik olarak submit edildiğini doğrular (Faz 3)."""
		template_name = "TEST-AUTOSUB-QC-TEMPLATE"
		if not frappe.db.exists("Quality Inspection Template", template_name):
			frappe.get_doc({
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": template_name,
				"item_quality_inspection_parameter": [
					{"specification": "Boyut Kontrolü", "numeric": 0, "value": "OK"}
				]
			}).insert(ignore_permissions=True)

		from erpnextkta.tests.test_utils import create_test_operator
		create_test_operator("autosub@kta.com", "Autosub Test")
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": "autosub@kta.com"})
		frappe.db.commit()

		# Kart oluştur ve başlat
		doc = create_calisma_karti(
			is_karti=self.jc_name, operasyon=self.kta_op,
			is_istasyonu=self.ws_name, operator="autosub@kta.com"
		)
		docname = doc.get("name")
		islem_yap(docname, "Baslat")

		readings = [{"specification": "Boyut Kontrolü", "numeric": 0,
					 "reading_value": "NOK", "status": "Rejected"}]

		# Red kararı ver
		submit_kta_quality_inspection(docname, template_name, readings, intent="reject")

		# Kart otomatik submit edilmiş olmalı
		ck = frappe.get_doc("Calisma Karti", docname)
		self.assertEqual(ck.docstatus, 1, "Red kararında kart otomatik submit edilmeli")
		self.assertIsNotNone(ck.bitis_saati, "bitis_saati red anında set edilmeli")
		self.assertEqual(ck.kalite_kontrol, "Reddedildi")
		self.assertEqual(ck.durum, "Reddedildi")

		# Submit sonrası tüm islem_yap çağrıları bloklanmalı
		with self.assertRaises(Exception):
			islem_yap(docname, "Durus", durus_nedeni="Diğer")

	def test_user_dashboard_override(self):
		"""User dashboard override'ının Calisma Karti'nı Activity grubuna eklediğini doğrular."""
		meta = frappe.get_meta("User")
		data = meta.get_dashboard_data()
		
		# Activity grubunu bul
		activity_group = None
		for group in data.transactions:
			if group.get("label") == "Activity":
				activity_group = group
				break
		
		self.assertIsNotNone(activity_group, "Activity group should exist in User dashboard data")
		self.assertIn("Calisma Karti", activity_group.get("items", []), "Calisma Karti should be in Activity group items")
		self.assertEqual(data.get("method"), "erpnextkta.overrides.user_dashboard.get_open_count")
		self.assertEqual(data.get("internal_links", {}).get("Calisma Karti"), "name")
		
		# Test calling get_open_count
		from erpnextkta.overrides.user_dashboard import get_open_count
		res = get_open_count("User", "Administrator")
		self.assertIn("count", res)
		self.assertIn("internal_links_found", res["count"])
		
		# Verify Calisma Karti is in the response list
		ck_link = None
		for il in res["count"]["internal_links_found"]:
			if il["doctype"] == "Calisma Karti":
				ck_link = il
				break
		self.assertIsNotNone(ck_link, "Calisma Karti should be returned in get_open_count internal links")

	def test_sub_op_reject_and_partial_accept(self):
		"""Alt operasyonlu operasyonda bir satır onaylanıp bir satır reddedildiğinde
		kartın 'Kısmi Kabul Edildi' olduğunu, kartın kapatılmadığını ve bitirilebildiğini doğrular.
		"""
		op_name = "TEST-SUB-QC-OP"
		if not frappe.db.exists("KTA Calisma Karti Operasyonlari", op_name):
			frappe.get_doc({
				"doctype": "KTA Calisma Karti Operasyonlari",
				"name": op_name,
				"calisma_karti_op": op_name,
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 1,
				"plant_floor": "L-1"
			}).insert(ignore_permissions=True, ignore_mandatory=True)
		else:
			frappe.db.set_value("KTA Calisma Karti Operasyonlari", op_name, {
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 1,
				"plant_floor": "L-1"
			})

		template_name = "TEST-SUB-QC-TEMPLATE"
		if not frappe.db.exists("Quality Inspection Template", template_name):
			frappe.get_doc({
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": template_name,
				"item_quality_inspection_parameter": [
					{"specification": "Görsel Kontrol", "numeric": 0, "value": "OK"}
				]
			}).insert(ignore_permissions=True)

		from erpnextkta.tests.test_utils import create_test_operator
		create_test_operator("sub_qc@kta.com", "Sub QC Operator")
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": "sub_qc@kta.com"})
		frappe.db.commit()

		doc = create_calisma_karti(
			is_karti=self.jc_name, operasyon=op_name,
			is_istasyonu=self.ws_name, operator="sub_qc@kta.com"
		)
		docname = doc.get("name")

		# Alt operasyon master oluştur
		master_doc = frappe.get_doc({
			"doctype": "KTA Calisma Karti Alt Operasyonlari",
			"title": "SubOp Master 1",
			"parent_operation": op_name,
			"sequence": 10
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

		# 2 alt operasyon satırı ekle
		row1_id = add_alt_operasyon_kaydi(docname, master_doc.name)
		row2_id = add_alt_operasyon_kaydi(docname, master_doc.name)

		# Kartı Başlat
		islem_yap(docname, "Baslat")

		# Row 1 Onayla
		readings_ok = [{"specification": "Görsel Kontrol", "numeric": 0, "reading_value": "OK", "status": "Accepted"}]
		res1 = submit_kta_quality_inspection(docname, template_name, readings_ok, intent="approve", rowname=row1_id)
		qi1_name = res1["quality_inspection"]

		# Row 1 onaylandı, Row 2 henüz onay bekliyor -> Kart genel QC: Onay Bekliyor
		ck = frappe.get_doc("Calisma Karti", docname)
		self.assertEqual(ck.kalite_kontrol, "Onay Bekliyor")
		self.assertEqual(ck.docstatus, 0)
		self.assertEqual(ck.get_durum(), "calisiyor")

		# Row 2 Reddet
		readings_nok = [{"specification": "Görsel Kontrol", "numeric": 0, "reading_value": "NOK", "status": "Rejected"}]
		res2 = submit_kta_quality_inspection(docname, template_name, readings_nok, intent="reject", rowname=row2_id)
		qi2_name = res2["quality_inspection"]

		# Row 2 reddedildi, QI hemen submit edilmiş olmalı ama KART AÇIK KALMALI
		qi2_docstatus = frappe.db.get_value("Quality Inspection", qi2_name, "docstatus")
		self.assertEqual(qi2_docstatus, 1)

		ck.reload()
		self.assertEqual(ck.docstatus, 0, "Alt operasyon reddinde kart otomatik submit edilmemeli!")
		self.assertEqual(ck.kalite_kontrol, "Kısmi Kabul Edildi")
		self.assertEqual(ck.get_durum(), "calisiyor", "Alt operasyon reddinde kart durumu reddedildi kilitlenmemeli!")
		self.assertIsNone(ck.bitis_saati)

		# Kartı Bitir
		islem_yap(docname, "Bitis")

		ck.reload()
		self.assertEqual(ck.docstatus, 1)
		self.assertEqual(ck.durum, "Bitmiş")
		self.assertEqual(ck.kalite_kontrol, "Kısmi Kabul Edildi")

		# Row 1'in draft QI'si de bitiş anında submit edilmiş olmalı
		qi1_docstatus = frappe.db.get_value("Quality Inspection", qi1_name, "docstatus")
		self.assertEqual(qi1_docstatus, 1, "Bitiş anında taslak alt operasyon QI'si submit edilmiş olmalı")

	def test_sub_op_qc_locked_for_operator(self):
		"""Operatörün kalite belgesi bağlanmış (onaylı veya redli) alt operasyonu silemediğini,
		kalite yetkilisinin ise silebildiğini ve bağlı QI'nin iptal edildiğini doğrular."""
		from erpnextkta.tests.test_utils import create_test_operator

		op_name = "TEST-LOCK-QC-OP"
		if not frappe.db.exists("KTA Calisma Karti Operasyonlari", op_name):
			frappe.get_doc({
				"doctype": "KTA Calisma Karti Operasyonlari",
				"name": op_name,
				"calisma_karti_op": op_name,
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 1,
				"plant_floor": "L-1"
			}).insert(ignore_permissions=True, ignore_mandatory=True)

		template_name = "TEST-LOCK-QC-TEMPLATE"
		if not frappe.db.exists("Quality Inspection Template", template_name):
			frappe.get_doc({
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": template_name,
				"item_quality_inspection_parameter": [
					{"specification": "Görsel Kontrol", "numeric": 0, "value": "OK"}
				]
			}).insert(ignore_permissions=True)

		operator_email = "lock_op@kta.com"
		if not frappe.db.exists("User", operator_email):
			frappe.get_doc({
				"doctype": "User",
				"email": operator_email,
				"first_name": "Lock",
				"last_name": "Operator",
				"enabled": 1,
				"roles": [
					{"role": "Manufacturing User"},
					{"role": "KTA Çalışma Kartı Kullanıcısı"}
				]
			}).insert(ignore_permissions=True)
		else:
			frappe.get_doc("User", operator_email).add_roles("Manufacturing User", "KTA Çalışma Kartı Kullanıcısı")

		create_test_operator(operator_email, "Lock Operator")
		frappe.db.set_value("Employee", operator_email, "user_id", operator_email)
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": operator_email})
		frappe.db.commit()

		doc = create_calisma_karti(
			is_karti=self.jc_name, operasyon=op_name,
			is_istasyonu=self.ws_name, operator=operator_email
		)
		docname = doc.get("name")

		master_doc = frappe.get_doc({
			"doctype": "KTA Calisma Karti Alt Operasyonlari",
			"title": "SubOp Lock Master",
			"parent_operation": op_name,
			"sequence": 10
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

		# 2 satır ekle: 1'ine QI bağlanacak, diğeri serbest kalacak
		row1_id = add_alt_operasyon_kaydi(docname, master_doc.name)
		row2_id = add_alt_operasyon_kaydi(docname, master_doc.name)

		# Serbest olan row2 operatör tarafından silinebilmeli
		delete_alt_operasyon_kaydi(docname, row2_id)
		ck = frappe.get_doc("Calisma Karti", docname)
		self.assertEqual(len(ck.alt_operasyon_kayitlari), 1)

		# Row 1'e kalite onayı ver (QI bağla)
		readings = [{"specification": "Görsel Kontrol", "numeric": 0, "reading_value": "OK", "status": "Accepted"}]
		res = submit_kta_quality_inspection(docname, template_name, readings, intent="approve", rowname=row1_id)
		qi_name = res["quality_inspection"]

		# Operatör olarak silmeye çalış -> Hata fırlatmalı
		orig_user = frappe.session.user
		try:
			frappe.set_user(operator_email)
			with self.assertRaises(frappe.ValidationError):
				delete_alt_operasyon_kaydi(docname, row1_id)
		finally:
			frappe.set_user(orig_user)

		# Kalite yetkilisi (Administrator) olarak sil -> Silinebilmeli ve QI iptal edilmeli
		delete_alt_operasyon_kaydi(docname, row1_id)

		ck.reload()
		self.assertEqual(len(ck.alt_operasyon_kayitlari), 0)
		self.assertFalse(frappe.db.exists("Quality Inspection", qi_name))

	def test_sub_op_all_rejected_allows_durus_and_devam_et(self):
		"""Alt operasyonlu açık kartta tüm satırlar reddedilse bile (kalite_kontrol=Reddedildi),
		kartın açık kalıp Duruş/Devam işlemlerine devam edebildiğini doğrular."""
		from erpnextkta.tests.test_utils import create_test_operator

		op_name = "TEST-RESUME-QC-OP"
		if not frappe.db.exists("KTA Calisma Karti Operasyonlari", op_name):
			frappe.get_doc({
				"doctype": "KTA Calisma Karti Operasyonlari",
				"name": op_name,
				"calisma_karti_op": op_name,
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 1,
				"plant_floor": "L-1"
			}).insert(ignore_permissions=True, ignore_mandatory=True)

		template_name = "TEST-RESUME-QC-TEMPLATE"
		if not frappe.db.exists("Quality Inspection Template", template_name):
			frappe.get_doc({
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": template_name,
				"item_quality_inspection_parameter": [
					{"specification": "Görsel Kontrol", "numeric": 0, "value": "OK"}
				]
			}).insert(ignore_permissions=True)

		operator_email = "resume_op@kta.com"
		if not frappe.db.exists("User", operator_email):
			frappe.get_doc({
				"doctype": "User",
				"email": operator_email,
				"first_name": "Resume",
				"last_name": "Operator",
				"enabled": 1,
				"roles": [
					{"role": "Manufacturing User"},
					{"role": "KTA Çalışma Kartı Kullanıcısı"}
				]
			}).insert(ignore_permissions=True)
		else:
			frappe.get_doc("User", operator_email).add_roles("Manufacturing User", "KTA Çalışma Kartı Kullanıcısı")

		create_test_operator(operator_email, "Resume Operator")
		frappe.db.set_value("Employee", operator_email, "user_id", operator_email)
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": operator_email})
		frappe.db.commit()

		doc = create_calisma_karti(
			is_karti=self.jc_name, operasyon=op_name,
			is_istasyonu=self.ws_name, operator=operator_email
		)
		docname = doc.get("name")

		master_doc = frappe.get_doc({
			"doctype": "KTA Calisma Karti Alt Operasyonlari",
			"title": "SubOp Resume Master",
			"parent_operation": op_name,
			"sequence": 10
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

		row_id = add_alt_operasyon_kaydi(docname, master_doc.name)

		# Kartı Başlat
		islem_yap(docname, "Baslat")

		# Kartı Duruşa al
		islem_yap(docname, "Durus", durus_nedeni="Diğer", aciklama="Yemek Molası")
		ck = frappe.get_doc("Calisma Karti", docname)
		self.assertEqual(ck.get_durum(), "durusta")

		# Tek satırı Reddet -> kartın kalite_kontrol değeri 'Reddedildi' olur
		readings_nok = [{"specification": "Görsel Kontrol", "numeric": 0, "reading_value": "NOK", "status": "Rejected"}]
		submit_kta_quality_inspection(docname, template_name, readings_nok, intent="reject", rowname=row_id)

		ck.reload()
		self.assertEqual(ck.kalite_kontrol, "Reddedildi")
		# Kart açık olduğu için durumu hâlâ 'durusta' olmalı
		self.assertEqual(ck.get_durum(), "durusta")

		# Duruştaki kart 'DevamEt' yapabilmeli (kalite_kontrol=Reddedildi olmasına rağmen kart açık olduğu için izin verilmeli)
		islem_yap(docname, "DevamEt")

		ck.reload()
		self.assertEqual(ck.get_durum(), "calisiyor")

		# Tekrar Duruşa alabilmeli
		islem_yap(docname, "Durus", durus_nedeni="Diğer", aciklama="Çay Molası")
		ck.reload()
		self.assertEqual(ck.get_durum(), "durusta")

		# Bitiş yapılabilmeli -> Bitiş yapıldığında tüm satırlar ret olduğu için durum 'reddedildi' olmalı
		islem_yap(docname, "Bitis")
		ck.reload()
		self.assertEqual(ck.docstatus, 1)
		self.assertEqual(ck.durum, "Reddedildi")
		self.assertEqual(ck.get_durum(), "reddedildi")

		# Bitmiş ve reddedilmiş kartta artık DevamEt yapılamamalı
		with self.assertRaises(frappe.ValidationError):
			islem_yap(docname, "DevamEt")

	def test_sub_op_finish_qc_rules(self):
		"""%100 kalite kontrolü seçili olduğunda açıkta onay bekleyen varken kartın bitirilemediğini,
		seçili olmadığında ise en az 1 onay olmadan kartın bitirilemediğini doğrular."""
		from erpnextkta.tests.test_utils import create_test_operator
		op_no_100 = "TEST-QC-NO-100-OP"
		if not frappe.db.exists("KTA Calisma Karti Operasyonlari", op_no_100):
			frappe.get_doc({
				"doctype": "KTA Calisma Karti Operasyonlari",
				"name": op_no_100,
				"calisma_karti_op": op_no_100,
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 0,
				"plant_floor": "L-1"
			}).insert(ignore_permissions=True, ignore_mandatory=True)
		else:
			frappe.db.set_value("KTA Calisma Karti Operasyonlari", op_no_100, {
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 0
			})

		template_name = "TEST-RULES-QC-TEMPLATE"
		if not frappe.db.exists("Quality Inspection Template", template_name):
			frappe.get_doc({
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": template_name,
				"item_quality_inspection_parameter": [
					{"specification": "Görsel Kontrol", "numeric": 0, "value": "OK"}
				]
			}).insert(ignore_permissions=True)

		operator_email = "rules_op@kta.com"
		create_test_operator(operator_email, "Rules Operator")
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": operator_email})
		frappe.db.commit()

		# ─── CASE 1: yuzde_yuz_kalite_kontrol = 0 ───
		doc1 = create_calisma_karti(
			is_karti=self.jc_name, operasyon=op_no_100,
			is_istasyonu=self.ws_name, operator=operator_email
		)
		docname1 = doc1.get("name")
		master_doc = frappe.get_doc({
			"doctype": "KTA Calisma Karti Alt Operasyonlari",
			"title": "SubOp Rules Master",
			"parent_operation": op_no_100,
			"sequence": 10
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

		row1 = add_alt_operasyon_kaydi(docname1, master_doc.name)
		add_alt_operasyon_kaydi(docname1, master_doc.name)
		islem_yap(docname1, "Baslat")

		# 0 onay varken bitirmeye çalış -> ValidationError
		with self.assertRaises(frappe.ValidationError):
			islem_yap(docname1, "Bitis")

		# 1 onay ver (row1)
		readings_ok = [{"specification": "Görsel Kontrol", "numeric": 0, "reading_value": "OK", "status": "Accepted"}]
		submit_kta_quality_inspection(docname1, template_name, readings_ok, intent="approve", rowname=row1)

		# 2. satır hâlâ bekliyor olsa da yuzde_yuz_kalite_kontrol=0 olduğu için artık bitirilebilmeli
		islem_yap(docname1, "Bitis")
		ck1 = frappe.get_doc("Calisma Karti", docname1)
		self.assertEqual(ck1.durum, "Bitmiş")
		self.assertEqual(ck1.kalite_kontrol, "Kısmi Kabul Edildi")
		self.assertEqual(ck1.docstatus, 1)

		# ─── CASE 2: yuzde_yuz_kalite_kontrol = 1 ───
		op_100 = "TEST-QC-100-OP"
		if not frappe.db.exists("KTA Calisma Karti Operasyonlari", op_100):
			frappe.get_doc({
				"doctype": "KTA Calisma Karti Operasyonlari",
				"name": op_100,
				"calisma_karti_op": op_100,
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 1,
				"plant_floor": "L-1"
			}).insert(ignore_permissions=True, ignore_mandatory=True)
		else:
			frappe.db.set_value("KTA Calisma Karti Operasyonlari", op_100, {
				"alt_operasyon_bazli_kalite": 1,
				"yuzde_yuz_kalite_kontrol": 1
			})

		master_doc2 = frappe.get_doc({
			"doctype": "KTA Calisma Karti Alt Operasyonlari",
			"title": "SubOp Rules Master 2",
			"parent_operation": op_100,
			"sequence": 10
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

		doc2 = create_calisma_karti(
			is_karti=self.jc_name, operasyon=op_100,
			is_istasyonu=self.ws_name, operator=operator_email
		)
		docname2 = doc2.get("name")
		r1 = add_alt_operasyon_kaydi(docname2, master_doc2.name)
		r2 = add_alt_operasyon_kaydi(docname2, master_doc2.name)
		islem_yap(docname2, "Baslat")

		# r1'i onayla
		submit_kta_quality_inspection(docname2, template_name, readings_ok, intent="approve", rowname=r1)

		# r2 hâlâ bekliyor -> yuzde_yuz_kalite_kontrol=1 olduğu için bitirilememeli
		with self.assertRaises(frappe.ValidationError):
			islem_yap(docname2, "Bitis")

		# r2'ye ret kararı ver (açıkta bekleyen satır kalmadı, kısmi kabul durumu)
		readings_nok = [{"specification": "Görsel Kontrol", "numeric": 0, "reading_value": "NOK", "status": "Rejected"}]
		submit_kta_quality_inspection(docname2, template_name, readings_nok, intent="reject", rowname=r2)

		# Açıkta bekleyen kalmadığı için artık Kısmi Kabul ile bitirilebilmeli
		islem_yap(docname2, "Bitis")
		ck2 = frappe.get_doc("Calisma Karti", docname2)
		self.assertEqual(ck2.durum, "Bitmiş")
		self.assertEqual(ck2.kalite_kontrol, "Kısmi Kabul Edildi")
		self.assertEqual(ck2.docstatus, 1)



