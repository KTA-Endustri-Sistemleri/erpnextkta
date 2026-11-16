# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

"""mrp_engine.settings birim testleri."""

from unittest.mock import patch

import frappe

from erpnextkta.kta_mrp.mrp_engine.settings import (
    MrpSettings,
    get_mrp_settings,
    resolve_mrp_settings,
)
from erpnextkta.tests.test_utils import KTAUnitTestCase


class TestMrpSettings(KTAUnitTestCase):
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
        self.assertEqual(s.wo_consumption_strategy, "Anlık Stok Rezervasyonu (Klasik)")
        self.assertFalse(s.is_capacity_leveled_consumption)
        self.assertTrue(s.deduct_work_order_reservations)

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
            "wo_consumption_strategy": "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)",
        }
        s = resolve_mrp_settings(filters)
        self.assertFalse(s.enable_leveling_by_default)
        self.assertFalse(s.enable_rampup_by_default)
        self.assertEqual(s.default_rampup_weeks, 5)
        self.assertFalse(s.default_include_po)
        self.assertEqual(s.wo_consumption_strategy, "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)")
        self.assertTrue(s.is_capacity_leveled_consumption)
        self.assertFalse(s.deduct_work_order_reservations)
        self.assertEqual(s.default_delivery_time_days, 2)

    def test_get_mrp_settings_from_doctype(self):
        fake_doc = {
            "enable_leveling_by_default": 1,
            "enable_rampup_by_default": 1,
            "default_rampup_weeks": 4,
            "rampup_trigger_utilization": 80.0,
            "rampup_max_capacity_limit": 90.0,
            "min_smoothing_qty": 15,
            "planning_horizon_days": 120,
            "backlog_lookback_days": 180,
            "default_production_time_days": 10,
            "default_delivery_time_days": 3,
            "urgent_shortage_weeks": 2,
            "available_warehouse_type": "Kullanılabilir Stok",
            "default_include_po": 1,
            "wo_consumption_strategy": "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)",
            "antrepo_clearance_days": 5,
        }
        with (
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_single", return_value=fake_doc),
        ):
            s = get_mrp_settings()
            self.assertTrue(s.is_capacity_leveled_consumption)
            self.assertFalse(s.deduct_work_order_reservations)
            self.assertEqual(s.default_delivery_time_days, 3)
            self.assertEqual(s.antrepo_clearance_days, 5)

    def test_get_mrp_settings_graceful_on_db_exception(self):
        with patch.object(frappe, "get_single", side_effect=Exception("DB Down")):
            s = get_mrp_settings()
            self.assertIsInstance(s, MrpSettings)
            self.assertEqual(s.available_warehouse_type, "Kullanılabilir Stok")

    def test_wo_consumption_strategy_default(self):
        with patch.object(frappe, "get_single", return_value={}):
            settings = get_mrp_settings()
            self.assertEqual(settings.wo_consumption_strategy, "Anlık Stok Rezervasyonu (Klasik)")
            self.assertFalse(settings.is_capacity_leveled_consumption)

    def test_wo_consumption_strategy_capacity_leveled(self):
        filters = {"wo_consumption_strategy": "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)"}
        settings = resolve_mrp_settings(filters)
        self.assertEqual(settings.wo_consumption_strategy, "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)")
        self.assertTrue(settings.is_capacity_leveled_consumption)
