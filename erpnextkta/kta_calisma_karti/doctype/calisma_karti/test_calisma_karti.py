# Copyright (c) 2025, Framras AS and Contributors
# See license.txt

import unittest
from datetime import datetime
from unittest.mock import patch

import frappe
from erpnextkta.tests.test_utils import (
	KTATestCase, 
	make_mock_calisma_karti, 
	make_mock_durus
)

from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import (
	_parse_minsec,
	_shift_name_by_now,
	format_sure as local_format_sure
)


# ---------------------------------------------------------------------------
# Pure-function tests (no DB / Frappe context required)
# ---------------------------------------------------------------------------

class TestShiftNameByNow(KTATestCase):
	"""_shift_name_by_now() yardımcı fonksiyonu için testler."""

	def _dt(self, h, m=0, s=0):
		return datetime(2024, 1, 15, h, m, s)

	def test_midnight_boundary_is_second_shift_end(self):
		"""Saat 00:00:00'ın 2. Vardiya sonu olarak kabul edildiğini doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(0, 0, 0)), "2. Vardiya")

	def test_08_00_boundary_is_third_shift_end(self):
		"""Saat 08:00:00'ın 3. Vardiya sonu olarak kabul edildiğini doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(8, 0, 0)), "3. Vardiya")

	def test_16_00_boundary_is_first_shift_end(self):
		"""Saat 16:00:00'ın 1. Vardiya sonu olarak kabul edildiğini doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(16, 0, 0)), "1. Vardiya")

	def test_00_01_is_third_shift(self):
		"""00:01:00'da 3. Vardiya'nın aktif olduğunu doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(0, 1)), "3. Vardiya")


class TestParseMinsec(KTATestCase):
	"""_parse_minsec() fonksiyonu süre formatı çevrim testleri."""
	
	def test_hhmmss_format(self):
		"""'SS:DD:sn' formatındaki sürenin saniyeye doğru çevrildiğini test eder."""
		self.assertEqual(_parse_minsec("01:30:00"), 5400)

	def test_mmss_format(self):
		"""'DD:sn' formatındaki sürenin saniyeye doğru çevrildiğini test eder."""
		self.assertEqual(_parse_minsec("2:45"), 165)


class TestFormatSure(KTATestCase):
	"""Süre formatlama yardımcı fonksiyonu testleri."""
	def test_one_hour(self):
		"""3600 saniyenin '01:00:00' formatına çevrildiğini doğrular."""
		self.assertEqual(local_format_sure(3600), "01:00:00")


# ---------------------------------------------------------------------------
# Document-level tests (Mock-based)
# ---------------------------------------------------------------------------

class TestGetDurum(KTATestCase):
	"""Çalışma Kartı durum (get_durum) mantığı testleri."""
	def test_reddedildi_takes_priority(self):
		"""Kalite kontrol reddedildiğinde durumun 'reddedildi' olduğunu doğrular."""
		doc = make_mock_calisma_karti(kalite_kontrol="Reddedildi", baslangic_saati="2024-01-15 08:00:00")
		self.assertEqual(doc.get_durum(), "reddedildi")

	def test_bitmis_when_bitis_saati_set(self):
		"""Bitiş saati varsa durumun 'bitmis' olduğunu doğrular."""
		doc = make_mock_calisma_karti(baslangic_saati="2024-01-15 08:00:00", bitis_saati="2024-01-15 16:00:00")
		self.assertEqual(doc.get_durum(), "bitmis")


class TestAktifDurusVarMi(KTATestCase):
	"""Duruş listesi kontrol testleri."""
	def test_last_durus_without_bitis_returns_true(self):
		"""Bitiş saati olmayan bir duruş satırı varken aktif duruş olduğunu doğrular (aktif_durus_var_mi)."""
		active = make_mock_durus(durus_baslangic="2024-01-15 10:00:00", durus_bitis=None)
		doc = make_mock_calisma_karti(duruslar=[active])
		self.assertTrue(doc.aktif_durus_var_mi())


class TestValidate(KTATestCase):
	"""Doküman doğrulama (validate) mantığı testleri."""
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
		"""Yeni kayıtta kalite kontrol durumunun varsayılan olarak 'Onay Bekliyor' geldiğini doğrular."""
		doc = make_mock_calisma_karti(kalite_kontrol=None)
		self._call_validate(doc)
		self.assertEqual(doc.kalite_kontrol, "Onay Bekliyor")

	def test_warn_limit_exceeded_triggers_msgprint(self):
		"""Kart süresi uyarı limitini aştığında msgprint ile ikaz verildiğini test eder."""
		# Start at 08:00, warn at 400 mins (14:40), now is 15:00
		doc = make_mock_calisma_karti(baslangic_saati="2024-01-15 08:00:00")
		msgs = self._call_validate(doc)
		self.assertTrue(any("dakikayı aştı!" in m for m in msgs))


# ---------------------------------------------------------------------------
# Integration Tests (Database-backed)
# ---------------------------------------------------------------------------

class TestCalismaKartiIntegration(KTATestCase):
	"""Gerçek veritabanı üzerinde Çalışma Kartı süreç testleri."""

	def test_duplicate_quality_inspection_raises(self):
		"""Aynı kalite kontrol kaydına bağlı birden fazla kart oluşturulmasının engellendiğini doğrular."""
		qi_name = "TEST-QI-DUP-001"

		if not frappe.db.exists("Quality Inspection", qi_name):
			frappe.get_doc({
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

		frappe.db.delete("Calisma Karti", {"quality_inspection": qi_name})
		frappe.db.commit()

		doc1 = frappe.get_doc({
			"doctype": "Calisma Karti",
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"quality_inspection": qi_name,
			"operator": "test@kta.com"
		})
		doc1.insert(ignore_permissions=True, ignore_links=True)
		frappe.db.commit()

		doc2 = frappe.get_doc({
			"doctype": "Calisma Karti",
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"quality_inspection": qi_name,
			"operator": "test@kta.com"
		})

		with self.assertRaises((frappe.ValidationError, frappe.UniqueValidationError, Exception)):
			doc2.insert(ignore_permissions=True, ignore_links=True)

	def test_total_duration_multiple_downtimes(self):
		"""Birden fazla duruş içeren bir kartta toplam duruş ve net çalışma süresinin doğru hesaplandığını doğrular."""
		from frappe.utils import get_datetime, add_to_date
		
		# Create a card starting 2 hours ago
		start = add_to_date(None, hours=-2)
		doc = frappe.get_doc({
			"doctype": "Calisma Karti",
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"operator": "test@kta.com",
			"baslangic_saati": start
		}).insert(ignore_permissions=True, ignore_links=True)
		
		# Add 2 finished downtimes of 10 mins each
		d1_start = add_to_date(start, minutes=10)
		d1_end = add_to_date(d1_start, minutes=10)
		d2_start = add_to_date(start, minutes=30)
		d2_end = add_to_date(d2_start, minutes=10)
		
		doc.append("duruslar", {"durus_baslangic": d1_start, "durus_bitis": d1_end, "durus_nedeni": "Diger"})
		doc.append("duruslar", {"durus_baslangic": d2_start, "durus_bitis": d2_end, "durus_nedeni": "Diger"})
		doc.save()
		
		# Active downtime row (started 10 mins ago)
		d3_start = add_to_date(None, minutes=-10)
		doc.append("duruslar", {"durus_baslangic": d3_start, "durus_nedeni": "Diger"})
		doc.save()
		
		doc.hesapla_toplam_sure()
		self.assertGreaterEqual(_parse_minsec(doc.toplam_durus), 1200)
		
		# Finish card now
		end = frappe.utils.now_datetime()
		doc.bitis_saati = end
		doc.save()
		self.assertAlmostEqual(_parse_minsec(doc.net_calisma_suresi), 5400, delta=20)

	def test_shift_capacity_cap(self):
		"""Net çalışma süresinin vardiya kapasitesiyle (Örn: 430 dk) sınırlandırıldığını doğrular."""
		# Create a card with 60 mins duration
		doc = frappe.get_doc({
			"doctype": "Calisma Karti",
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"operator": "test@kta.com",
			"baslangic_saati": "2024-01-15 15:00:00",
			"bitis_saati": "2024-01-15 16:00:00"
		})
		
		# Mock other cards: Used 400, limit 430 -> only 30 mins (1800s) remaining.
		with (
			patch("erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti._other_cards_net_seconds_in_shift", return_value=24000),
			patch("erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings", return_value=(430, 400))
		):
			doc.hesapla_toplam_sure()
			self.assertEqual(doc.net_calisma_suresi, local_format_sure(1800))

	def test_different_quality_inspections_allowed(self):
		"""Farklı kalite kontrol kayıtları kullanan iki farklı kartın kaydedilebildiğini doğrular."""
		for qi_suffix in ("QI-A", "QI-B"):
			qi_name = f"TEST-QI-{qi_suffix}"
			if not frappe.db.exists("Quality Inspection", qi_name):
				frappe.get_doc({
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

			frappe.db.delete("Calisma Karti", {"quality_inspection": qi_name})
		frappe.db.commit()

		emp_b = "worker-diff@kta.com"
		if not frappe.db.exists("Employee", emp_b):
			try:
				frappe.db.sql("""
					INSERT INTO `tabEmployee` (name, employee_name, first_name, status, creation, modified, modified_by)
					VALUES (%s, 'Worker Diff', 'Worker', 'Active', NOW(), NOW(), 'Administrator')
				""", (emp_b,))
				frappe.db.commit()
			except Exception:
				pass

		doc_a = frappe.get_doc({
			"doctype": "Calisma Karti",
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"quality_inspection": "TEST-QI-QI-A",
			"operator": "test@kta.com"
		})
		doc_a.insert(ignore_permissions=True, ignore_links=True)

		doc_b = frappe.get_doc({
			"doctype": "Calisma Karti",
			"is_karti": self.jc_name,
			"operasyon": self.kta_op,
			"is_istasyonu": self.ws_name,
			"quality_inspection": "TEST-QI-QI-B",
			"operator": emp_b
		})
		doc_b.insert(ignore_permissions=True, ignore_links=True)

		frappe.db.commit()

		self.assertTrue(frappe.db.exists("Calisma Karti", doc_a.name))
		self.assertTrue(frappe.db.exists("Calisma Karti", doc_b.name))

	def test_shift_boundary_integration(self):
		"""Vardiya sınırı mantığının (16:00:00 vs 16:00:01) doğru çalıştığını doğrular."""
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