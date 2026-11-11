# Copyright (c) 2024, KTA Endüstri Sistemleri and contributors
# See license.txt

import unittest
from datetime import datetime
from unittest.mock import patch
import frappe
from frappe.utils import get_datetime
from erpnextkta.tests.test_utils import KTATestCase, make_mock_calisma_karti, make_mock_durus
from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import (
	_shift_name_by_now,
	_parse_minsec,
	format_sure
)

class TestShiftNameByNow(unittest.TestCase):
	def _dt(self, h, m=0, s=0):
		return datetime(2024, 1, 15, h, m, s)

	def test_midnight_boundary_is_second_shift_end(self):
		"""Saat tam 00:00 iken 2. Vardiya'nın bitişi olarak kabul edildiğini doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(0, 0, 0)), "2. Vardiya")
	
	def test_08_00_boundary_is_third_shift_end(self):
		"""Saat tam 08:00 iken 3. Vardiya'nın bitişi olarak kabul edildiğini doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(8, 0, 0)), "3. Vardiya")

	def test_16_00_boundary_is_first_shift_end(self):
		"""Saat tam 16:00 iken 1. Vardiya'nın bitişi olarak kabul edildiğini doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(16, 0, 0)), "1. Vardiya")

	def test_00_01_is_third_shift(self):
		"""Gece yarısından 1 saniye sonra 3. Vardiya'nın başladığını doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(0, 0, 1)), "3. Vardiya")

	def test_08_01_is_first_shift(self):
		"""Sabah 08:01'de 1. Vardiya'nın başladığını doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(8, 0, 1)), "1. Vardiya")

	def test_16_01_is_second_shift(self):
		"""Öğleden sonra 16:01'de 2. Vardiya'nın başladığını doğrular."""
		self.assertEqual(_shift_name_by_now(self._dt(16, 0, 1)), "2. Vardiya")

class TestParseMinsec(unittest.TestCase):
	def test_hhmmss_format(self):
		"""'SS:DD:sn' formatındaki sürenin saniyeye doğru çevrildiğini test eder."""
		self.assertEqual(_parse_minsec("01:30:00"), 5400)
	
	def test_mmss_format(self):
		"""'DD:sn' formatındaki sürenin saniyeye doğru çevrildiğini test eder."""
		self.assertEqual(_parse_minsec("10:30"), 630)

	def test_none_returns_zero(self):
		"""Boş değer girildiğinde 0 saniye döndüğünü doğrular."""
		self.assertEqual(_parse_minsec(None), 0)

class TestFormatSure(unittest.TestCase):
	def test_zero_seconds(self):
		"""0 saniyenin '00:00:00' şeklinde formatlandığını test eder."""
		self.assertEqual(format_sure(0), "00:00:00")
	
	def test_one_hour(self):
		"""3600 saniyenin '01:00:00' şeklinde formatlandığını test eder."""
		self.assertEqual(format_sure(3600), "01:00:00")

class TestGetDurum(unittest.TestCase):
	def test_reddedildi_takes_priority(self):
		"""Kalite kontrol reddedildiğinde kart durumunun 'reddedildi' olduğunu doğrular."""
		doc = make_mock_calisma_karti(kalite_kontrol="Reddedildi", baslangic_saati="2024-01-15 08:00:00")
		self.assertEqual(doc.get_durum(), "reddedildi")
	
	def test_bitmis_when_bitis_saati_set(self):
		"""Bitiş saati set edildiğinde kart durumunun 'bitmis' olduğunu doğrular."""
		doc = make_mock_calisma_karti(baslangic_saati="2024-01-15 08:00:00", bitis_saati="2024-01-15 16:00:00")
		self.assertEqual(doc.get_durum(), "bitmis")

	def test_hazir_when_no_baslangic(self):
		"""Başlangıç saati yoksa kartın 'hazir' (başlatılmamış) olduğunu doğrular."""
		doc = make_mock_calisma_karti(baslangic_saati=None)
		self.assertEqual(doc.get_durum(), "hazir")

class TestAktifDurusVarMi(unittest.TestCase):
	def test_empty_duruslar_returns_false(self):
		"""Duruş listesi boşsa aktif duruş olmadığını doğrular."""
		doc = make_mock_calisma_karti(duruslar=[])
		self.assertFalse(doc.aktif_durus_var_mi())
	
	def test_last_durus_without_bitis_returns_true(self):
		"""Bitiş saati olmayan bir duruş satırı varsa aktif duruş olduğunu doğrular."""
		active = make_mock_durus(durus_baslangic="2024-01-15 10:00:00", durus_bitis=None)
		doc = make_mock_calisma_karti(duruslar=[active])
		self.assertTrue(doc.aktif_durus_var_mi())


class TestValidateSubOpQcForSubmission(unittest.TestCase):
	def test_100_percent_qc_with_pending_throws(self):
		"""%100 kalite kontrolde açıkta 'Onay Bekliyor' alt işlem varken hata fırlatıldığını doğrular."""
		doc = make_mock_calisma_karti(
			operasyon="TEST-OP",
			alt_operasyon_kayitlari=[
				{"quality_inspection_status": "Onaylandı"},
				{"quality_inspection_status": "Onay Bekliyor"}
			]
		)
		with patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 1, "yuzde_yuz_kalite_kontrol": 1}):
			with self.assertRaises(frappe.ValidationError) as cm:
				doc.validate_sub_op_qc_for_submission()
			msg = str(cm.exception)
			self.assertTrue("%100" in msg or "100%" in msg)

	def test_100_percent_qc_all_rejected_allowed(self):
		"""Tüm alt işlemler reddedildiğinde kartın kapanışına (reddedildi olarak) izin verildiğini doğrular."""
		doc = make_mock_calisma_karti(
			operasyon="TEST-OP",
			alt_operasyon_kayitlari=[
				{"quality_inspection_status": "Reddedildi"},
				{"quality_inspection_status": "Reddedildi"}
			]
		)
		with patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 1, "yuzde_yuz_kalite_kontrol": 1}):
			doc.validate_sub_op_qc_for_submission()

	def test_sample_qc_without_approvals_throws(self):
		"""Örnekleme muayenesinde hiç onaylı satır yoksa onaysız kapatmanın engellendiğini doğrular."""
		doc = make_mock_calisma_karti(
			operasyon="TEST-OP",
			alt_operasyon_kayitlari=[
				{"quality_inspection_status": "Onay Bekliyor"},
				{"quality_inspection_status": "Onay Bekliyor"}
			]
		)
		with patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 1, "yuzde_yuz_kalite_kontrol": 0}):
			with self.assertRaises(frappe.ValidationError) as cm:
				doc.validate_sub_op_qc_for_submission()
			msg = str(cm.exception).lower()
			self.assertTrue("en az bir alt işlem" in msg or "at least one sub-operation" in msg)

	def test_sample_qc_with_one_approval_and_pending_allowed(self):
		"""Örnekleme muayenesinde en az 1 onaylı satır varsa bekleyen satırlara rağmen izin verildiğini doğrular."""
		doc = make_mock_calisma_karti(
			operasyon="TEST-OP",
			alt_operasyon_kayitlari=[
				{"quality_inspection_status": "Onaylandı"},
				{"quality_inspection_status": "Onay Bekliyor"}
			]
		)
		with patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 1, "yuzde_yuz_kalite_kontrol": 0}):
			doc.validate_sub_op_qc_for_submission()

	def test_100_percent_qc_with_english_accepted(self):
		"""İngilizce 'Accepted' durumunun %100 kontrolde geçerli onay sayıldığını doğrular."""
		doc = make_mock_calisma_karti(
			operasyon="TEST-OP",
			alt_operasyon_kayitlari=[
				{"quality_inspection_status": "Accepted"},
				{"quality_inspection_status": "Accepted"}
			]
		)
		with patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 1, "yuzde_yuz_kalite_kontrol": 1}):
			doc.validate_sub_op_qc_for_submission()

	def test_100_percent_qc_all_english_rejected_allowed(self):
		"""Tüm alt işlemler İngilizce 'Rejected' olduğunda reddedildi olarak kapanışa izin verildiğini doğrular."""
		doc = make_mock_calisma_karti(
			operasyon="TEST-OP",
			alt_operasyon_kayitlari=[
				{"quality_inspection_status": "Rejected"},
				{"quality_inspection_status": "Rejected"}
			]
		)
		with patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 1, "yuzde_yuz_kalite_kontrol": 1}):
			doc.validate_sub_op_qc_for_submission()


class TestQcHelpers(unittest.TestCase):
	def test_is_qc_approved(self):
		from erpnextkta.kta_calisma_karti.api_impl._helpers import is_qc_approved
		self.assertTrue(is_qc_approved("Onaylandı"))
		self.assertTrue(is_qc_approved("onaylandı"))
		self.assertTrue(is_qc_approved("Accepted"))
		self.assertTrue(is_qc_approved("accepted"))
		self.assertFalse(is_qc_approved("Reddedildi"))
		self.assertFalse(is_qc_approved("Onay Bekliyor"))
		self.assertFalse(is_qc_approved(None))
		self.assertFalse(is_qc_approved(""))

	def test_is_qc_rejected(self):
		from erpnextkta.kta_calisma_karti.api_impl._helpers import is_qc_rejected
		self.assertTrue(is_qc_rejected("Reddedildi"))
		self.assertTrue(is_qc_rejected("reddedildi"))
		self.assertTrue(is_qc_rejected("Rejected"))
		self.assertTrue(is_qc_rejected("rejected"))
		self.assertTrue(is_qc_rejected("Red"))
		self.assertTrue(is_qc_rejected("red"))
		self.assertFalse(is_qc_rejected("Onaylandı"))
		self.assertFalse(is_qc_rejected("Onay Bekliyor"))
		self.assertFalse(is_qc_rejected(None))
		self.assertFalse(is_qc_rejected(""))

	def test_is_qc_pending(self):
		from erpnextkta.kta_calisma_karti.api_impl._helpers import is_qc_pending
		self.assertTrue(is_qc_pending("Onay Bekliyor"))
		self.assertTrue(is_qc_pending("onay bekliyor"))
		self.assertTrue(is_qc_pending("Pending"))
		self.assertTrue(is_qc_pending(None))
		self.assertTrue(is_qc_pending(""))
		self.assertFalse(is_qc_pending("Onaylandı"))
		self.assertFalse(is_qc_pending("Reddedildi"))


class TestDoubleFinishProtection(unittest.TestCase):
	def test_handle_bitis_on_already_finished_card_throws(self):
		"""Zaten bitiş saati atanmış veya bitmiş bir kartta _handle_bitis'in hata fırlattığını doğrular."""
		from erpnextkta.kta_calisma_karti.api_impl.cards import _handle_bitis
		doc = make_mock_calisma_karti(bitis_saati="2024-01-15 16:00:00")
		with self.assertRaises(frappe.ValidationError) as cm:
			_handle_bitis(doc, "2024-01-15 17:00:00", "", 10)
		msg = str(cm.exception)
		self.assertTrue("Bu kart zaten bitmiş" in msg or "This card is already finished" in msg)

	def test_handle_bitis_on_rejected_card_throws(self):
		"""Tüm alt işlemleri reddedilmiş bir kartta mükerrer _handle_bitis çağrısının engellendiğini doğrular."""
		from erpnextkta.kta_calisma_karti.api_impl.cards import _handle_bitis
		doc = make_mock_calisma_karti(kalite_kontrol="Reddedildi", bitis_saati="2024-01-15 16:00:00")
		with self.assertRaises(frappe.ValidationError) as cm:
			_handle_bitis(doc, "2024-01-15 17:00:00", "", 10)
		msg = str(cm.exception)
		self.assertTrue("Bu kart zaten bitmiş" in msg or "This card is already finished" in msg)


class TestShiftAutoCloseRejectedCards(unittest.TestCase):
	def test_shift_closer_skips_classic_rejected_card(self):
		"""Klasik kalite reddi almış kartların vardiya kapanışında atlandığını doğrular."""
		from erpnextkta.tasks import auto_close_timed_out_cards
		doc = make_mock_calisma_karti(
			name="CK-CLASSIC-REJ",
			operasyon="CLASSIC-OP",
			baslangic_saati="2024-01-15 08:00:00",
			bitis_saati=None,
			kalite_kontrol="Reddedildi",
			duruslar=[]
		)
		orig_get_doc = frappe.get_doc
		with patch("frappe.logger"), \
		     patch("erpnextkta.tasks.now_datetime", return_value=datetime(2024, 1, 15, 16, 15)), \
		     patch("erpnextkta.tasks.get_datetime", side_effect=str), \
		     patch("frappe.get_all", return_value=[frappe._dict(name="CK-CLASSIC-REJ")]), \
		     patch("frappe.get_doc", side_effect=lambda *a, **k: doc if a and a[0] == "Calisma Karti" else orig_get_doc(*a, **k)), \
		     patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 0}):
			auto_close_timed_out_cards()
			self.assertIsNone(doc.bitis_saati)

	def test_shift_closer_processes_sub_op_rejected_card(self):
		"""Alt operasyonları ret almış açık kartların vardiya kapanışında kapatıldığını doğrular."""
		from unittest.mock import MagicMock
		from erpnextkta.tasks import auto_close_timed_out_cards
		doc = make_mock_calisma_karti(
			name="CK-SUBOP-REJ",
			operasyon="SUBOP-OP",
			baslangic_saati="2024-01-15 08:00:00",
			bitis_saati=None,
			kalite_kontrol="Reddedildi",
			duruslar=[]
		)
		doc.save = MagicMock()
		doc.update_durum = MagicMock()
		doc.append = MagicMock()
		orig_get_doc = frappe.get_doc
		with patch("frappe.logger"), \
		     patch("erpnextkta.tasks.now_datetime", return_value=datetime(2024, 1, 15, 16, 15)), \
		     patch("erpnextkta.tasks.get_datetime", side_effect=str), \
		     patch("frappe.get_all", return_value=[frappe._dict(name="CK-SUBOP-REJ")]), \
		     patch("frappe.get_doc", side_effect=lambda *a, **k: doc if a and a[0] == "Calisma Karti" else orig_get_doc(*a, **k)), \
		     patch("frappe.db.get_value", return_value={"alt_operasyon_bazli_kalite": 1}), \
		     patch("frappe.db.get_single_value", return_value="Zaman Aşımı"), \
		     patch("frappe.db.set_value"), \
		     patch("erpnextkta.tasks._submit_linked_quality_inspection"), \
		     patch("erpnextkta.kta_calisma_karti.api_impl.job_card_sync.sync_time_log_to_job_card"):
			auto_close_timed_out_cards()
			self.assertIsNotNone(doc.bitis_saati)

