# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import json
import os
import unittest
from unittest.mock import patch

from erpnextkta.kta_mrp.report.mrp_analysis import mrp_analysis
from erpnextkta.kta_mrp.report_utils import get_period_dates

START = "2026-11-02"


class TestGetPeriodDates(unittest.TestCase):
	def test_yillik_is_rolling_twelve_months(self):
		"""Yıllık periyot yıl sonunda değil, bugünden itibaren 12 ay sonra bitmeli."""
		self.assertEqual(get_period_dates("Yıllık", start_date=START), (START, "2027-11-02"))

	def test_yillik_is_longest_fixed_period(self):
		"""Yıllık periyot 3 ve 6 aylık periyotlardan kısa olamaz."""
		ends = [get_period_dates(p, start_date=START)[1] for p in ("3 Aylık", "6 Aylık", "Yıllık")]
		self.assertEqual(ends, sorted(ends))

	def test_three_and_six_months(self):
		self.assertEqual(get_period_dates("3 Aylık", start_date=START)[1], "2027-02-02")
		self.assertEqual(get_period_dates("6 Aylık", start_date=START)[1], "2027-05-02")

	def test_suresiz(self):
		self.assertEqual(get_period_dates("Süresiz", start_date=START)[1], "2099-12-31")

	def test_ozel_uses_given_dates(self):
		filters = {"from_date": "2027-01-01", "to_date": "2027-03-31"}
		self.assertEqual(get_period_dates("Özel", filters, start_date=START), ("2027-01-01", "2027-03-31"))


class TestMrpAnalysisReportConfig(unittest.TestCase):
	def test_report_is_not_prepared_report(self):
		"""Filtre değişiminde rapor anında yenilenmeli (arka plan raporu olmamalı)."""
		path = os.path.join(os.path.dirname(__file__), "mrp_analysis.json")
		with open(path) as f:
			self.assertEqual(json.load(f)["prepared_report"], 0)


class TestZeroConsumptionItems(unittest.TestCase):
	def test_only_hammadde_and_obs_groups_are_queried(self):
		"""Sıfır tüketimi göster sadece HAMMADDE ve OBS* ara malzeme gruplarını eklemeli."""
		with patch.object(mrp_analysis.frappe.db, "sql_list", return_value=["RM-1"]) as sql_list:
			self.assertEqual(mrp_analysis.get_zero_consumption_items(), ["RM-1"])
		query = sql_list.call_args[0][0]
		self.assertIn("custom_ara_malzeme_grubu = 'HAMMADDE'", query)
		self.assertIn("LIKE 'OBS%%'", query)
