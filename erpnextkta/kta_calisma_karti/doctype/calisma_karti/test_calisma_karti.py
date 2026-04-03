# Copyright (c) 2025, Framras AS and Contributors
# See license.txt

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import (
	_parse_minsec,
	_shift_name_by_now,
	format_sure,
)


# ---------------------------------------------------------------------------
# Pure-function tests (no DB / Frappe context required)
# ---------------------------------------------------------------------------

class TestShiftNameByNow(unittest.TestCase):
	"""Tests for the _shift_name_by_now() helper."""

	def _dt(self, h, m=0, s=0):
		"""Build a datetime with the given hour/minute/second on an arbitrary date."""
		return datetime(2024, 1, 15, h, m, s)

	# --- boundary times -------------------------------------------------------

	def test_midnight_boundary_is_second_shift_end(self):
		# Exact 00:00 belongs to the ENDING shift (2. Vardiya ends at midnight)
		self.assertEqual(_shift_name_by_now(self._dt(0, 0, 0)), "2. Vardiya")

	def test_08_00_boundary_is_third_shift_end(self):
		# Exact 08:00 belongs to 3. Vardiya (it is its end boundary)
		self.assertEqual(_shift_name_by_now(self._dt(8, 0, 0)), "3. Vardiya")

	def test_16_00_boundary_is_first_shift_end(self):
		# Exact 16:00 belongs to 1. Vardiya (it is its end boundary)
		self.assertEqual(_shift_name_by_now(self._dt(16, 0, 0)), "1. Vardiya")

	# --- mid-shift times ------------------------------------------------------

	def test_00_01_is_third_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(0, 1)), "3. Vardiya")

	def test_04_00_is_third_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(4, 0)), "3. Vardiya")

	def test_07_59_is_third_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(7, 59)), "3. Vardiya")

	def test_08_01_is_first_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(8, 1)), "1. Vardiya")

	def test_12_00_is_first_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(12, 0)), "1. Vardiya")

	def test_15_59_is_first_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(15, 59)), "1. Vardiya")

	def test_16_01_is_second_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(16, 1)), "2. Vardiya")

	def test_20_00_is_second_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(20, 0)), "2. Vardiya")

	def test_23_59_is_second_shift(self):
		self.assertEqual(_shift_name_by_now(self._dt(23, 59)), "2. Vardiya")


class TestParseMinsec(unittest.TestCase):
	"""Tests for the _parse_minsec() helper."""

	def test_hhmmss_format(self):
		self.assertEqual(_parse_minsec("01:30:00"), 5400)

	def test_hhmmss_with_seconds(self):
		self.assertEqual(_parse_minsec("00:02:30"), 150)

	def test_mmss_format(self):
		self.assertEqual(_parse_minsec("2:45"), 165)

	def test_zero_string(self):
		self.assertEqual(_parse_minsec("00:00:00"), 0)

	def test_none_returns_zero(self):
		self.assertEqual(_parse_minsec(None), 0)

	def test_empty_string_returns_zero(self):
		self.assertEqual(_parse_minsec(""), 0)

	def test_no_colon_returns_zero(self):
		self.assertEqual(_parse_minsec("1234"), 0)

	def test_non_string_int_returns_zero(self):
		self.assertEqual(_parse_minsec(120), 0)

	def test_invalid_parts_return_zero(self):
		self.assertEqual(_parse_minsec("ab:cd:ef"), 0)

	def test_large_value(self):
		# 7 hours, 10 minutes, 0 seconds = 430 * 60 = 25800 s
		self.assertEqual(_parse_minsec("07:10:00"), 25800)


class TestFormatSure(unittest.TestCase):
	"""Tests for the format_sure() helper."""

	def test_zero_seconds(self):
		self.assertEqual(format_sure(0), "00:00:00")

	def test_negative_returns_zero(self):
		self.assertEqual(format_sure(-10), "00:00:00")

	def test_none_returns_zero(self):
		self.assertEqual(format_sure(None), "00:00:00")

	def test_one_minute(self):
		self.assertEqual(format_sure(60), "00:01:00")

	def test_one_hour(self):
		self.assertEqual(format_sure(3600), "01:00:00")

	def test_complex_value(self):
		# 2h 15m 30s = 8130 s
		self.assertEqual(format_sure(8130), "02:15:30")

	def test_rounding(self):
		# 0.6 should round to 1 second
		self.assertEqual(format_sure(0.6), "00:00:01")


# ---------------------------------------------------------------------------
# Document-level tests (use a mock Document to avoid DB dependency)
# ---------------------------------------------------------------------------

def _make_doc(**kwargs):
	"""
	Build a minimal CalismaKarti-like mock object so we can call document
	methods without hitting the database.
	"""
	from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import CalismaKarti

	doc = CalismaKarti.__new__(CalismaKarti)
	# Required Document attributes
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
	"""Tests for CalismaKarti.get_durum()."""

	def test_reddedildi_takes_priority(self):
		doc = _make_doc(kalite_kontrol="Reddedildi", baslangic_saati="2024-01-15 08:00:00")
		self.assertEqual(doc.get_durum(), "reddedildi")

	def test_bitmis_when_bitis_saati_set(self):
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00", bitis_saati="2024-01-15 16:00:00")
		self.assertEqual(doc.get_durum(), "bitmis")

	def test_hazir_when_no_baslangic(self):
		doc = _make_doc()
		self.assertEqual(doc.get_durum(), "hazir")

	def test_durusta_when_active_durus(self):
		active_row = _make_durus(durus_baslangic="2024-01-15 10:00:00", durus_bitis=None)
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00", duruslar=[active_row])
		self.assertEqual(doc.get_durum(), "durusta")

	def test_calisiyor_when_running(self):
		finished_row = _make_durus(
			durus_baslangic="2024-01-15 09:00:00",
			durus_bitis="2024-01-15 09:30:00",
		)
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00", duruslar=[finished_row])
		self.assertEqual(doc.get_durum(), "calisiyor")

	def test_calisiyor_no_duruslar(self):
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00")
		self.assertEqual(doc.get_durum(), "calisiyor")


class TestAktifDurusVarMi(unittest.TestCase):
	"""Tests for CalismaKarti.aktif_durus_var_mi()."""

	def test_empty_duruslar_returns_false(self):
		doc = _make_doc()
		self.assertFalse(doc.aktif_durus_var_mi())

	def test_last_durus_without_bitis_returns_true(self):
		active = _make_durus(durus_baslangic="2024-01-15 10:00:00", durus_bitis=None)
		doc = _make_doc(duruslar=[active])
		self.assertTrue(doc.aktif_durus_var_mi())

	def test_last_durus_with_bitis_returns_false(self):
		closed = _make_durus(
			durus_baslangic="2024-01-15 10:00:00",
			durus_bitis="2024-01-15 10:30:00",
		)
		doc = _make_doc(duruslar=[closed])
		self.assertFalse(doc.aktif_durus_var_mi())

	def test_mixed_duruslar_last_open(self):
		closed = _make_durus(
			durus_baslangic="2024-01-15 09:00:00",
			durus_bitis="2024-01-15 09:30:00",
		)
		active = _make_durus(durus_baslangic="2024-01-15 10:00:00", durus_bitis=None)
		doc = _make_doc(duruslar=[closed, active])
		self.assertTrue(doc.aktif_durus_var_mi())


# ---------------------------------------------------------------------------
# Validate method tests
# ---------------------------------------------------------------------------

class TestValidate(FrappeTestCase):
	"""
	Tests for CalismaKarti.validate().

	We patch the external collaborators (get_kta_settings, frappe.msgprint,
	update_durum) so these tests remain fast and self-contained.
	"""

	def _call_validate(self, doc):
		"""
		Invoke validate() with external side-effects patched out.
		Returns the list of msgprint calls recorded during the call.
		"""
		messages = []

		with (
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings",
				return_value=(430, 400),
			),
			patch.object(doc, "update_durum"),
			patch.object(doc, "get_durum", return_value="calisiyor"),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.frappe.msgprint",
				side_effect=lambda msg, **kw: messages.append(msg),
			),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.now_datetime",
				return_value=datetime(2024, 1, 15, 15, 0, 0),
			),
		):
			doc.validate()

		return messages

	# -----------------------------------------------------------------------
	# kalite_kontrol default
	# -----------------------------------------------------------------------

	def test_kalite_kontrol_defaults_to_onay_bekliyor_when_none(self):
		doc = _make_doc(kalite_kontrol=None)
		self._call_validate(doc)
		self.assertEqual(doc.kalite_kontrol, "Onay Bekliyor")

	def test_kalite_kontrol_defaults_to_onay_bekliyor_when_empty_string(self):
		doc = _make_doc(kalite_kontrol="")
		self._call_validate(doc)
		self.assertEqual(doc.kalite_kontrol, "Onay Bekliyor")

	def test_kalite_kontrol_preserved_when_already_set(self):
		doc = _make_doc(kalite_kontrol="Onaylandı")
		self._call_validate(doc)
		self.assertEqual(doc.kalite_kontrol, "Onaylandı")

	def test_kalite_kontrol_reddedildi_preserved(self):
		doc = _make_doc(kalite_kontrol="Reddedildi")
		with (
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings",
				return_value=(430, 400),
			),
			patch.object(doc, "update_durum"),
			patch.object(doc, "get_durum", return_value="reddedildi"),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.frappe.msgprint",
			),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.now_datetime",
				return_value=datetime(2024, 1, 15, 15, 0, 0),
			),
		):
			doc.validate()
		self.assertEqual(doc.kalite_kontrol, "Reddedildi")

	# -----------------------------------------------------------------------
	# Warn-limit warning
	# -----------------------------------------------------------------------

	def test_warn_limit_exceeded_triggers_msgprint(self):
		# Card started >400 minutes before "now"
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00")

		messages = []
		with (
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings",
				return_value=(430, 400),
			),
			patch.object(doc, "update_durum"),
			patch.object(doc, "get_durum", return_value="calisiyor"),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.frappe.msgprint",
				side_effect=lambda msg, **kw: messages.append(msg),
			),
			# "now" is 420 minutes after card start → exceeds warn_limit of 400
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.now_datetime",
				return_value=datetime(2024, 1, 15, 15, 0, 0),
			),
		):
			doc.validate()

		self.assertEqual(len(messages), 1)
		self.assertIn("400", messages[0])

	def test_warn_limit_not_exceeded_no_msgprint(self):
		# Card started only 30 minutes ago → below warn_limit of 400
		doc = _make_doc(baslangic_saati="2024-01-15 14:30:00")

		messages = []
		with (
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings",
				return_value=(430, 400),
			),
			patch.object(doc, "update_durum"),
			patch.object(doc, "get_durum", return_value="calisiyor"),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.frappe.msgprint",
				side_effect=lambda msg, **kw: messages.append(msg),
			),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.now_datetime",
				return_value=datetime(2024, 1, 15, 15, 0, 0),
			),
		):
			doc.validate()

		self.assertEqual(len(messages), 0)

	def test_warn_limit_not_checked_when_card_finished(self):
		# Finished card (get_durum returns 'bitmis') must never emit a warning
		doc = _make_doc(
			baslangic_saati="2024-01-15 08:00:00",
			bitis_saati="2024-01-15 15:00:00",
		)

		messages = []
		with (
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings",
				return_value=(430, 400),
			),
			patch.object(doc, "update_durum"),
			patch.object(doc, "get_durum", return_value="bitmis"),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.frappe.msgprint",
				side_effect=lambda msg, **kw: messages.append(msg),
			),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.now_datetime",
				return_value=datetime(2024, 1, 15, 15, 0, 0),
			),
		):
			doc.validate()

		self.assertEqual(len(messages), 0)

	def test_warn_limit_durusta_triggers_msgprint(self):
		# A card 'durusta' that has been running for >400 min should also warn
		doc = _make_doc(baslangic_saati="2024-01-15 08:00:00")

		messages = []
		with (
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_kta_settings",
				return_value=(430, 400),
			),
			patch.object(doc, "update_durum"),
			patch.object(doc, "get_durum", return_value="durusta"),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.frappe.msgprint",
				side_effect=lambda msg, **kw: messages.append(msg),
			),
			patch(
				"erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.now_datetime",
				return_value=datetime(2024, 1, 15, 15, 0, 0),
			),
		):
			doc.validate()

		self.assertEqual(len(messages), 1)
