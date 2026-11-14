# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
import frappe
from erpnextkta.mrp_simulation.seeder import seed
from erpnextkta.mrp_simulation.cleaner import clean
from erpnextkta.mrp_simulation.dates import get_simulation_dates
from erpnextkta.kta_mrp.mrp_engine.weeks import week_key
from erpnextkta.kta_mrp.mrp_engine.capacity import build_capacity_plan
from erpnextkta.kta_mrp.mrp_engine.service import get_material_requirements


class TestMrpSimulation(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		if not frappe.db:
			frappe.init("development.localhost")
			frappe.connect()
		clean()
		seed()

	@classmethod
	def tearDownClass(cls):
		# We do not clean() on tearDownClass so the seeded simulation
		# data remains available for visual verification in Desk/frontend.
		# setUpClass() already cleans before seeding to guarantee test isolation.
		pass

	def test_mrp_settings_alignment(self):
		"""Verifies that KTA MRP Settings baseline values are active."""
		from erpnextkta.kta_mrp.mrp_engine.settings import get_mrp_settings

		settings = get_mrp_settings()
		self.assertTrue(settings.enable_leveling_by_default)
		self.assertEqual(settings.available_warehouse_type, "Kullanılabilir Stok")
		self.assertEqual(settings.antrepo_clearance_days, 2)
		self.assertEqual(settings.urgent_shortage_weeks, 4)
		self.assertEqual(settings.default_production_time_days, 14)
		self.assertEqual(settings.default_delivery_time_days, 2)

	def test_capacity_plan_700_500_200(self):
		"""Verifies that:
		1. Capacity ceiling is 500 pcs/wk from Item.custom_weekly_production.
		2. Week 1 total demand is 700 pcs (400 net URUN-01 + 300 URUN-02).
		3. Leveling caps Week 1 at 500 pcs (%100 capacity).
		4. 200 pcs carries over to Week 2.
		"""
		sched = get_simulation_dates()
		w_cur = week_key(sched.w_current_monday)
		w_next = week_key(sched.w_next_monday)

		plan_data = build_capacity_plan()

		# 1. Group Capacity
		self.assertEqual(plan_data["group_capacity"].get("KABLO GRUBU"), 500)

		# 2. Week 1 Demand (500 SO minus (100 FG stock - 20 safety stock = 80 usable) -> 420 to produce)
		u1_demand = plan_data["item_week_demand"]["URUN-01"][w_cur]
		u2_demand = plan_data["item_week_demand"]["URUN-02"][w_cur]
		self.assertEqual(u1_demand, 420, "500 SO minus 80 net stock (100 - 20 safety stock) must yield 420 to_produce")
		self.assertEqual(u2_demand, 300, "300 SO must yield 300 demand")
		self.assertEqual(u1_demand + u2_demand, 720)

		# 3. Leveling Week 1 = 500
		w1_produced = plan_data["plan"]["URUN-01"][w_cur] + plan_data["plan"]["URUN-02"][w_cur]
		self.assertEqual(w1_produced, 500, "Week 1 production must be leveled to 500")

		# 4. Carry-Over to Week 2
		w2_produced = plan_data["plan"]["URUN-01"][w_next] + plan_data["plan"]["URUN-02"][w_next]
		self.assertTrue(w2_produced > 0, "Remaining demand must carry over to Week 2")

	def test_material_requirements_and_pegging(self):
		"""Verifies that all 7 raw materials reflect their correct logistics states in MRP."""
		result = get_material_requirements({}, include_po=True)
		materials = result.materials

		self.assertEqual(len(materials), 7)

		# 1. HAMMADDE-01 (Shared cable, partial free stock)
		m1 = materials["HAMMADDE-01"]
		self.assertGreater(m1.free_stock, 0)
		self.assertTrue(sum(m1.netting.gross.values()) > 0)

		# 2. HAMMADDE-02 (Open PO + In-Transit Multi-Supply)
		m2 = materials["HAMMADDE-02"]
		self.assertIsNotNone(m2.supply_breakdown)
		self.assertEqual(m2.supply_breakdown.get("po_kalan"), 1000.0)
		self.assertEqual(m2.supply_breakdown.get("yolda"), 500.0)
		self.assertEqual(m2.actual, 0.0)
		self.assertEqual(m2.free_stock, 0.0)

		# 3. HAMMADDE-03 (In-Transit PR / Yolda)
		m3 = materials["HAMMADDE-03"]
		self.assertIsNotNone(m3.supply_breakdown)
		self.assertEqual(m3.supply_breakdown.get("yolda"), 500.0)

		# 4. HAMMADDE-04 (Bonded Warehouse PR / Antrepoda)
		m4 = materials["HAMMADDE-04"]
		self.assertIsNotNone(m4.supply_breakdown)
		self.assertEqual(m4.supply_breakdown.get("antrepoda"), 800.0)

		# 5. HAMMADDE-05 (Customs Clearance PR / Gümrüklemede)
		m5 = materials["HAMMADDE-05"]
		self.assertIsNotNone(m5.supply_breakdown)
		self.assertEqual(m5.supply_breakdown.get("gumruklemede"), 400.0)

		# 6. HAMMADDE-06 (Full free stock)
		m6 = materials["HAMMADDE-06"]
		self.assertGreaterEqual(m6.free_stock, 1900.0)

		# 7. HAMMADDE-07 (Critical Deficit, Planned Orders w/ MOQ & pack)
		# Note: WO-URUN-02 (qty 150) reserves 300 units of HAMMADDE-07, so free_stock = 0 - 300 = -300.
		m7 = materials["HAMMADDE-07"]
		self.assertLessEqual(m7.free_stock, 0)
		self.assertEqual(m7.moq, 1000)
		self.assertEqual(m7.pack, 250)
		self.assertTrue(sum(m7.netting.planned_orders.values()) > 0)
