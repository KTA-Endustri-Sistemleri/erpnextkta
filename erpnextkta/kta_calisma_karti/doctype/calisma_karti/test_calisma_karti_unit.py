# Copyright (c) 2024, Framras AS and Contributors
# See license.txt

import unittest
from datetime import datetime
from frappe.utils import get_datetime
from erpnextkta.tests.test_utils import KTATestCase, make_mock_calisma_karti, make_mock_durus
from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import (
	_shift_name_by_now,
	_parse_minsec,
	format_sure
)

class TestShiftNameByNow(KTATestCase):
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

class TestParseMinsec(KTATestCase):
	def test_hhmmss_format(self):
		"""'SS:DD:sn' formatındaki sürenin saniyeye doğru çevrildiğini test eder."""
		self.assertEqual(_parse_minsec("01:30:00"), 5400)
	
	def test_mmss_format(self):
		"""'DD:sn' formatındaki sürenin saniyeye doğru çevrildiğini test eder."""
		self.assertEqual(_parse_minsec("10:30"), 630)

	def test_none_returns_zero(self):
		"""Boş değer girildiğinde 0 saniye döndüğünü doğrular."""
		self.assertEqual(_parse_minsec(None), 0)

class TestFormatSure(KTATestCase):
	def test_zero_seconds(self):
		"""0 saniyenin '00:00:00' şeklinde formatlandığını test eder."""
		self.assertEqual(format_sure(0), "00:00:00")
	
	def test_one_hour(self):
		"""3600 saniyenin '01:00:00' şeklinde formatlandığını test eder."""
		self.assertEqual(format_sure(3600), "01:00:00")

class TestGetDurum(KTATestCase):
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

class TestAktifDurusVarMi(KTATestCase):
	def test_empty_duruslar_returns_false(self):
		"""Duruş listesi boşsa aktif duruş olmadığını doğrular."""
		doc = make_mock_calisma_karti(duruslar=[])
		self.assertFalse(doc.aktif_durus_var_mi())
	
	def test_last_durus_without_bitis_returns_true(self):
		"""Bitiş saati olmayan bir duruş satırı varsa aktif duruş olduğunu doğrular."""
		active = make_mock_durus(durus_baslangic="2024-01-15 10:00:00", durus_bitis=None)
		doc = make_mock_calisma_karti(duruslar=[active])
		self.assertTrue(doc.aktif_durus_var_mi())
