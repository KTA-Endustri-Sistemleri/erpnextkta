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

		self.wip_warehouse = "_Test WIP - KTA"
		if not frappe.db.exists("Warehouse", self.wip_warehouse):
			frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": "_Test WIP",
				"company": self.company
			}).insert(ignore_permissions=True)

		# 3. KTA Operations
		self.kta_op = "KTA-OP-001-TEST"
		if not frappe.db.exists("KTA Calisma Karti Operasyonlari", self.kta_op):
			frappe.get_doc({
				"doctype": "KTA Calisma Karti Operasyonlari",
				"name": self.kta_op,
				"calisma_karti_op": "Test Operasyon",
				"miktar_zorunlu_mu": 1
			}).insert(ignore_permissions=True)

		# 4. Work Order & Job Card (Manual mock names to avoid complex BOM creation)
		# We check if they exist in DB so create_calisma_karti() doesn't fail.
		self.jc_name = "TEST-JC-KTA-001"
		if not frappe.db.exists("Job Card", self.jc_name):
			# Minimal Job Card that satisfies api_impl.create validation
			frappe.get_doc({
				"doctype": "Job Card",
				"name": self.jc_name,
				"operation": "_Test ERPNext Op",
				"workstation": "_Test KTA Workstation",
				"production_item": self.item,
				"for_quantity": 100,
				"company": self.company
			}).insert(ignore_permissions=True)

		# The create_calisma_karti function expects a real Work Order if jc.work_order is set.
		# To keep it simple, we ensure the Job Card has no work_order OR we mock one.
		# In this test, we'll bypass the WO requirement by keeping it empty in Job Card 
		# OR providing a dummy name that we create if needed.
		self.wo_name = "TEST-WO-KTA-001"
		if not frappe.db.exists("Work Order", self.wo_name):
			frappe.get_doc({
				"doctype": "Work Order",
				"name": self.wo_name,
				"production_item": self.item,
				"qty": 100,
				"company": self.company,
				"wip_warehouse": self.wip_warehouse,
				"fg_warehouse": self.wip_warehouse,
				"docstatus": 1
			}).insert(ignore_permissions=True)
			# Link them
			frappe.db.set_value("Job Card", self.jc_name, "work_order", self.wo_name)

		frappe.db.commit()

	def test_create_calisma_karti_double_click_protection(self):
		"""Calling create twice quickly should return the same document."""
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
				"inspection_type": "Incoming",
				"reference_type": "Job Card",
				"reference_name": self.jc_name,
				"status": "Accepted",
				"report_date": frappe.utils.nowdate()
			}).insert(ignore_permissions=True)
		
		results = []
		def try_save_card(card_id):
			try:
				# New connection to simulate isolated transaction
				frappe.db.connect() 
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
			except frappe.ValidationError as e:
				if "başka bir Çalışma Kartı" in str(e):
					results.append("BLOCKED")
				else:
					results.append(f"ERROR: {str(e)}")
			except Exception as e:
				results.append(f"EXCEPTION: {str(e)}")
			finally:
				frappe.db.close()

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