# Copyright (c) 2025, Framras AS and Contributors
# See license.txt

import unittest
import threading
from datetime import datetime
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import (
	_parse_minsec,
	_shift_name_by_now,
	format_sure,
)
from erpnextkta.kta_calisma_karti.api_impl.create import create_calisma_karti


# ---------------------------------------------------------------------------
# Pure-function tests (no DB / Frappe context required)
# ---------------------------------------------------------------------------

class TestShiftNameByNow(unittest.TestCase):
	"""Tests for the _shift_name_by_now() helper."""

	def _dt(self, h, m=0, s=0):
		"""Build a datetime with the given hour/minute/second on an arbitrary date."""
		return datetime(2024, 1, 15, h, m, s)

	def test_midnight_boundary_is_second_shift_end(self):
		self.assertEqual(_shift_name_by_now(self._dt(0, 0, 0)), "2. Vardiya")

	def test_08_00_boundary_is_third_shift_end(self):
		self.assertEqual(_shift_name_by_now(self._dt(8, 0, 0)), "3. Vardiya")

	def test_16_00_boundary_is_first_shift_end(self):
		self.assertEqual(_shift_name_by_now(self._dt(16, 0, 0)), "1. Vardiya")

	def test_00_01_is_third_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(0, 1)), "3. Vardiya")

	def test_08_01_is_first_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(8, 1)), "1. Vardiya")

	def test_16_01_is_second_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(16, 1)), "2. Vardiya")


class TestParseMinsec(unittest.TestCase):
	"""Tests for the _parse_minsec() helper."""

	def test_hhmmss_format(self):
		self.assertEqual(_parse_minsec("01:30:00"), 5400)

	def test_mmss_format(self):
		self.assertEqual(_parse_minsec("2:45"), 165)

	def test_none_returns_zero(self):
		self.assertEqual(_parse_minsec(None), 0)


class TestFormatSure(unittest.TestCase):
	"""Tests for the format_sure() helper."""

	def test_zero_seconds(self):
		self.assertEqual(format_sure(0), "00:00:00")

	def test_one_hour(self):
		self.assertEqual(format_sure(3600), "01:00:00")


# ---------------------------------------------------------------------------
# Document-level tests (use a mock Document to avoid DB dependency)
# ---------------------------------------------------------------------------

def _make_doc(**kwargs):
	"""Build a minimal CalismaKarti-like mock object."""
	from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import CalismaKarti
	doc = CalismaKarti.__new__(CalismaKarti)
	doc.name = kwargs.get("name", "TEST-CK-001")
	doc.doctype = "Calisma Karti"
	doc.duruslar = kwargs.get("duruslar", [])
	doc.baslangic_saati = kwargs.get("baslangic_saati", None)
	doc.bitis_saati = kwargs.get("bitis_saati", None)
	doc.kalite_kontrol = kwargs.get("kalite_kontrol", None)
	doc.operator = kwargs.get("operator", None)
	doc.operasyon = kwargs.get("operasyon", None)
	doc.is_istasyonu = kwargs.get("is_istasyonu", None)
	doc.toplam_sure = kwargs.get("toplam_sure", None)
	doc.toplam_durus = kwargs.get("toplam_durus", None)
	doc.net_calisma_suresi = kwargs.get("net_calisma_suresi", None)
	doc.durum = kwargs.get("durum", None)
	return doc


def _make_durus(durus_baslangic=None, durus_bitis=None, durus_suresi=None):
	row = MagicMock()
	row.durus_baslangic = durus_baslangic
	row.durus_bitis = durus_bitis
	row.durus_suresi = durus_suresi
	return row


class TestGetDurum(unittest.TestCase):
	def test_reddedildi_takes_priority(self):
		doc = _make_doc(kalite_kontrol="Reddedildi", baslangic_saati="2024-01-15 08:00:00")
		self.assertEqual(doc.get_durum(), "reddedildi")

	def test_bitmis_when_bitis_saati_set(self):
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00", bitis_saati="2024-01-15 16:00:00")
		self.assertEqual(doc.get_durum(), "bitmis")

	def test_hazir_when_no_baslangic(self):
		doc = _make_doc()
		self.assertEqual(doc.get_durum(), "hazir")


class TestAktifDurusVarMi(unittest.TestCase):
	def test_empty_duruslar_returns_false(self):
		doc = _make_doc()
		self.assertFalse(doc.aktif_durus_var_mi())

	def test_last_durus_without_bitis_returns_true(self):
		active = _make_durus(durus_baslangic="2024-01-15 10:00:00", durus_bitis=None)
		doc = _make_doc(duruslar=[active])
		self.assertTrue(doc.aktif_durus_var_mi())


class TestValidate(FrappeTestCase):
	"""Tests for CalismaKarti.validate() with mocks."""

	def _call_validate(self, doc):
		messages = []
		with (
			patch("erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings", return_value=(430, 400)),
			patch.object(doc, "update_durum"),
			patch.object(doc, "get_durum", return_value="calisiyor"),
			patch("erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.frappe.msgprint", side_effect=lambda msg, **kw: messages.append(msg)),
			patch("erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.now_datetime", return_value=datetime(2024, 1, 15, 15, 0, 0)),
		):
			doc.validate()
		return messages

	def test_kalite_kontrol_defaults_to_onay_bekliyor(self):
		doc = _make_doc(kalite_kontrol=None)
		self._call_validate(doc)
		self.assertEqual(doc.kalite_kontrol, "Onay Bekliyor")

	def test_warn_limit_exceeded_triggers_msgprint(self):
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00")
		messages = self._call_validate(doc)
		self.assertEqual(len(messages), 1)
		self.assertIn("400", messages[0])


# ---------------------------------------------------------------------------
# Integration Tests (requires DB / FrappeTestCase)
# ---------------------------------------------------------------------------

class TestCalismaKartiIntegration(FrappeTestCase):
	"""
	Database-level tests starting with an empty database environment.
	Creates all necessary master data (Company, Item, Warehouse, etc.) in setUp.
	"""

	def setUp(self):
		super().setUp()
		
		# 0. Clean start
		frappe.db.rollback()
		frappe.clear_cache()
		
		# 1. KTA Settings
		frappe.db.set_single_value("KTA Calisma Karti Settings", "mukerrer_kalite_kontrolu_yap", 1)
		frappe.db.set_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk", 430)
		frappe.db.set_single_value("KTA Calisma Karti Settings", "kart_uyari_suresi_dk", 400)

		# 1. KTA Settings
		self.company = "_Test Company KTA"
		if not frappe.db.exists("Company", self.company):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": self.company,
				"abbr": "TKTA",
				"default_currency": "TRY",
				"country": "Turkey"
			}).insert(ignore_permissions=True)
		
		frappe.db.commit()

		self.item_group = "_Test Item Group KTA"
		if not frappe.db.exists("Item Group", self.item_group):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": self.item_group,
				"is_group": 0,
				"parent_item_group": "All Item Groups"
			}).insert(ignore_permissions=True)

		self.item = "_Test Item KTA"
		if not frappe.db.exists("Item", self.item):
			frappe.get_doc({
				"doctype": "Item",
				"item_code": self.item,
				"item_group": self.item_group,
				"is_stock_item": 1,
				"stock_uom": "Nos"
			}).insert(ignore_permissions=True)

		self.wip_warehouse = "_Test WIP - TKTA"
		if not frappe.db.exists("Warehouse", self.wip_warehouse):
			try:
				frappe.get_doc({
					"doctype": "Warehouse",
					"warehouse_name": "_Test WIP",
					"company": self.company
				}).insert(ignore_permissions=True)
			except Exception:
				pass

		# 3. KTA Operations
		if not frappe.db.exists("Plant Floor", "L-1"):
			try:
				frappe.get_doc({
					"doctype": "Plant Floor",
					"name": "L-1",
					"plant_name": "L-1"
				}).insert(ignore_permissions=True)
			except Exception:
				pass

		self.kta_op = "KTA-OP-001-TEST"
		if not frappe.db.exists("KTA Calisma Karti Operasyonlari", self.kta_op):
			frappe.get_doc({
				"doctype": "KTA Calisma Karti Operasyonlari",
				"name": self.kta_op,
				"calisma_karti_op": "Test Operasyon",
				"miktar_zorunlu_mu": 1,
				"customer_group": "",
				"plant_floor": "L-1" # Correct fieldname
			}).insert(ignore_permissions=True, ignore_links=True)

		# 3.5 Missing Workstation & Operation dependencies
		if not frappe.db.exists("Workstation", "_Test KTA Workstation"):
			frappe.get_doc({
				"doctype": "Workstation",
				"workstation_name": "_Test KTA Workstation"
			}).insert(ignore_permissions=True)

		# 3.6 Shifts
		if not frappe.db.exists("Shift Type", "1. Vardiya"):
			try:
				frappe.get_doc({"doctype": "Shift Type", "name": "1. Vardiya", "start_time": "08:00:00", "end_time": "16:00:00"}).insert(ignore_permissions=True, ignore_links=True)
			except Exception: pass
			
		if not frappe.db.exists("Shift Type", "2. Vardiya"):
			try:
				frappe.get_doc({"doctype": "Shift Type", "name": "2. Vardiya", "start_time": "16:00:00", "end_time": "00:00:00"}).insert(ignore_permissions=True, ignore_links=True)
			except Exception: pass
			
		# 3.7 Operator
		if not frappe.db.exists("Employee", "test@kta.com"):
			try:
				frappe.db.sql("""
					INSERT INTO `tabEmployee` (name, employee_name, first_name, status, creation, modified, modified_by)
					VALUES ('test@kta.com', 'Test Operator', 'Test', 'Active', NOW(), NOW(), 'Administrator')
				""")
			except Exception: pass
			
		if not frappe.db.exists("Operation", "_Test ERPNext Op"):
			frappe.get_doc({
				"doctype": "Operation",
				"name": "_Test ERPNext Op",
				"workstation": "_Test KTA Workstation"
			}).insert(ignore_permissions=True)

		# 4. Work Order (Direct SQL bypass to avoid BO, routing, and warehouse validations)
		self.wo_name = "TEST-WO-KTA-001"
		if not frappe.db.exists("Work Order", self.wo_name):
			frappe.db.sql("""
				INSERT INTO `tabWork Order` (name, production_item, qty, company, wip_warehouse, fg_warehouse, docstatus, status, creation, modified, modified_by)
				VALUES (%s, %s, 100, %s, %s, %s, 1, 'Not Started', NOW(), NOW(), 'Administrator')
			""", (self.wo_name, self.item, self.company, self.wip_warehouse, self.wip_warehouse))
		else:
			frappe.db.set_value("Work Order", self.wo_name, "docstatus", 1)
			frappe.db.set_value("Work Order", self.wo_name, "status", "Not Started")

		# 5. Job Card (Direct SQL bypass)
		self.jc_name = "TEST-JC-KTA-001"
		if not frappe.db.exists("Job Card", self.jc_name):
			frappe.db.sql("""
				INSERT INTO `tabJob Card` (name, work_order, wip_warehouse, operation, workstation, production_item, for_quantity, company, docstatus, creation, modified, modified_by)
				VALUES (%s, %s, %s, %s, %s, %s, 100, %s, 1, NOW(), NOW(), 'Administrator')
			""", (self.jc_name, self.wo_name, self.wip_warehouse, "_Test ERPNext Op", "_Test KTA Workstation", self.item, self.company))
		else:
			frappe.db.set_value("Job Card", self.jc_name, "docstatus", 1)

		frappe.db.commit()

	def test_create_calisma_karti_double_click_protection(self):
		"""Calling create twice quickly should return the same document."""
		# Ensure a clean slate for this specific test case payload across runs
		frappe.db.delete("Calisma Karti", {"is_karti": self.jc_name, "operator": "test@kta.com"})
		frappe.db.commit()

		payload = {
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": "_Test KTA Workstation",
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

	def test_race_condition_duplicate_quality_inspection(self):
		"""Two cards trying to use the same Quality Inspection simultaneously."""
		
		# Create a QI record
		qi_name = "TEST-QI-KTA-001"
		if not frappe.db.exists("Quality Inspection", qi_name):
			qi = frappe.get_doc({
				"doctype": "Quality Inspection",
				"name": qi_name,
				"inspection_type": "In Process",
				"reference_type": "Job Card",
				"reference_name": self.jc_name,
				"item_code": self.item,
				"sample_size": 1,
				"inspected_by": "Administrator",
				"status": "Accepted",
				"report_date": frappe.utils.nowdate()
			}).insert(ignore_permissions=True, ignore_links=True)
		
		results = []
		site = frappe.local.site

		def try_save_card(card_id):
			try:
				# Initialize frappe local variables for this new thread
				frappe.init(site=site)
				frappe.connect() 
				
				doc = frappe.get_doc({
					"doctype": "Calisma Karti",
					"is_karti": self.jc_name,
					"operasyon": self.kta_op,
					"quality_inspection": qi_name,
					"operator": f"worker-{card_id}@kta.com"
				})
				doc.insert(ignore_permissions=True)
				# Commit to ensure the lock is actually released/tested
				frappe.db.commit() 
				results.append("SUCCESS")
			except Exception as e:
				if "LockTimeoutError" in str(e) or "FOR UPDATE" in str(e) or "Zaten" in str(e) or "Another Card" in str(e) or " Duplicate" in str(e) or "aynı Kalite" in str(e):
					results.append("BLOCKED")
				else:
					results.append(f"EXCEPTION: {str(e)}")
			finally:
				try:
					frappe.destroy()
				except Exception:
					pass

		# Run two threads
		t1 = threading.Thread(target=try_save_card, args=("A",))
		t2 = threading.Thread(target=try_save_card, args=("B",))
		
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		
		self.assertIn("SUCCESS", results, "At least one card must be saved")
		self.assertIn("BLOCKED", results, "FOR UPDATE lock must block the second concurrent card")

	def test_shift_boundary_integration(self):
		"""Verify that boundary logic correctly assigns shifts at 16:00:00 vs 16:00:01."""
		from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import _shift_window
		from frappe.utils import get_datetime
		
		# 16:00:00 -> Shift 1 (Biten vardiya sınırı)
		ws1, we1 = _shift_window(get_datetime("2024-01-15 16:00:00"))
		self.assertEqual(ws1.strftime("%H:%M"), "08:00")
		self.assertEqual(we1.strftime("%H:%M"), "16:00")
		
		# 16:00:01 -> Shift 2 (Yeni vardiya)
		ws2, we2 = _shift_window(get_datetime("2024-01-15 16:00:01"))
		self.assertEqual(ws2.strftime("%H:%M"), "16:00")
		self.assertEqual(we2.strftime("%H:%M"), "00:00")