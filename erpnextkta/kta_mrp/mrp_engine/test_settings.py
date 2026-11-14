"""mrp_engine.settings birim testleri."""

import unittest
from unittest.mock import patch
import frappe

from erpnextkta.kta_mrp.mrp_engine.settings import (
	MrpSettings,
	get_mrp_settings,
	resolve_mrp_settings,
)


class TestMrpSettings(unittest.TestCase):
	def test_default_settings_fallbacks(self):
		s = MrpSettings()
		self.assertTrue(s.enable_leveling_by_default)
		self.assertTrue(s.enable_rampup_by_default)
		self.assertEqual(s.default_rampup_weeks, 3)
		self.assertEqual(s.rampup_trigger_utilization, 70.0)
		self.assertEqual(s.rampup_max_capacity_limit, 95.0)
		self.assertEqual(s.min_smoothing_qty, 10)
		self.assertEqual(s.planning_horizon_days, 90)
		self.assertEqual(s.backlog_lookback_days, 270)
		self.assertEqual(s.default_production_time_days, 14)
		self.assertEqual(s.default_delivery_time_days, 2)
		self.assertEqual(s.available_warehouse_type, "Kullanılabilir Stok")
		self.assertTrue(s.default_include_po)

	def test_resolve_settings_with_no_filters(self):
		s = resolve_mrp_settings()
		self.assertIsInstance(s, MrpSettings)
		self.assertEqual(s.default_rampup_weeks, 3)

	def test_resolve_settings_filters_override(self):
		filters = {
			"dengeleme_yapilsin": 0,
			"ramp_up_aktif": 0,
			"ramp_up_weeks": 5,
			"include_po": 0,
		}
		s = resolve_mrp_settings(filters)
		self.assertFalse(s.enable_leveling_by_default)
		self.assertFalse(s.enable_rampup_by_default)
		self.assertEqual(s.default_rampup_weeks, 5)
		self.assertFalse(s.default_include_po)

	def test_get_mrp_settings_graceful_on_db_exception(self):
		with patch.object(frappe, "get_single", side_effect=Exception("DB Down")):
			s = get_mrp_settings()
			self.assertIsInstance(s, MrpSettings)
			self.assertEqual(s.available_warehouse_type, "Kullanılabilir Stok")


if __name__ == "__main__":
	unittest.main()
