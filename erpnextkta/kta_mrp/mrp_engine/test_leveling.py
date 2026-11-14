"""mrp_engine.leveling birim testleri."""

import unittest
from collections import defaultdict

from erpnextkta.kta_mrp.mrp_engine.leveling import (
	distribute_proportional,
	forward_scheduling,
	backward_rampup_smoothing,
)


class TestLeveling(unittest.TestCase):
	def test_distribute_proportional_exact_sum(self):
		weights = {"A": 10, "B": 20, "C": 30}
		res = distribute_proportional(100, weights)
		self.assertEqual(sum(res.values()), 100)
		# 10/60 -> 16.66 (17), 20/60 -> 33.33 (33), 30/60 -> 50.0 (50)
		self.assertEqual(res["A"], 17)
		self.assertEqual(res["B"], 33)
		self.assertEqual(res["C"], 50)

	def test_distribute_proportional_zero_weights_or_qty(self):
		self.assertEqual(distribute_proportional(0, {"A": 10}), {"A": 0})
		self.assertEqual(distribute_proportional(100, {"A": 0, "B": 0}), {"A": 0, "B": 0})

	def test_forward_scheduling_levels_capacity(self):
		weeks = ["2026_w01", "2026_w02"]
		group_items = {"Line1": ["P1"]}
		group_capacity = {"Line1": 100}
		backlog = {"P1": 150}  # Backlog exceeds capacity 100
		demand = defaultdict(lambda: defaultdict(int))
		demand["P1"]["2026_w01"] = 0
		demand["P1"]["2026_w02"] = 0

		plan, _, _ = forward_scheduling(
			weeks, group_items, group_capacity, backlog, demand, leveling_enabled=True
		)
		# Week 1 should take 100 (capacity limit), Week 2 should take remaining 50
		self.assertEqual(plan["P1"]["2026_w01"], 100)
		self.assertEqual(plan["P1"]["2026_w02"], 50)

	def test_forward_scheduling_without_leveling(self):
		weeks = ["2026_w01", "2026_w02"]
		group_items = {"Line1": ["P1"]}
		group_capacity = {"Line1": 100}
		backlog = {"P1": 150}
		demand = defaultdict(lambda: defaultdict(int))
		demand["P1"]["2026_w01"] = 20
		demand["P1"]["2026_w02"] = 30

		plan, _, _ = forward_scheduling(
			weeks, group_items, group_capacity, backlog, demand, leveling_enabled=False
		)
		# Week 1 gets backlog (150) + current (20) = 170
		self.assertEqual(plan["P1"]["2026_w01"], 170)
		# Week 2 gets current (30)
		self.assertEqual(plan["P1"]["2026_w02"], 30)

	def test_backward_rampup_smoothing_diffuses_peaks(self):
		weeks = ["2026_w01", "2026_w02"]
		group_items = {"Line1": ["P1"]}
		group_capacity = {"Line1": 100}

		plan = defaultdict(lambda: defaultdict(int))
		# Week 1 has 0, Week 2 has 90 (> 70% capacity trigger)
		plan["P1"]["2026_w01"] = 0
		plan["P1"]["2026_w02"] = 90
		k_plan = defaultdict(lambda: defaultdict(int))
		w_plan = defaultdict(lambda: defaultdict(int))

		backward_rampup_smoothing(
			weeks,
			group_items,
			group_capacity,
			plan,
			k_plan,
			w_plan,
			ramp_weeks=1,
			trigger_ratio=0.70,
			max_capacity_ratio=0.95,
			min_smoothing_qty=10,
		)
		# Average is (0 + 90) / 2 = 45. 45 moves from w02 to w01.
		self.assertEqual(plan["P1"]["2026_w01"], 45)
		self.assertEqual(plan["P1"]["2026_w02"], 45)

	def test_forward_scheduling_preserves_wo_carry_over_when_capacity_full(self):
		"""Kapasite dolduğunda (remaining_cap <= 0) haftalık iş emirlerinin devredildiğini doğrula."""
		valid_weeks = ["2026_w46", "2026_w47"]
		group_items = {"GRP": ["ITEM1"]}
		group_capacity = {"GRP": 1000}
		# Backlog 46. haftanın 1000 kapasitesini tamamen doldurur
		item_backlog = {"ITEM1": 1000}
		item_backlog_wo = {"ITEM1": 1000}
		# 46. haftada ayrıca 500 adet yeni WO vardır
		item_week_demand = {"ITEM1": {"2026_w46": 500, "2026_w47": 0}}
		item_week_wo = {"ITEM1": {"2026_w46": 500, "2026_w47": 0}}

		plan, kanban, wo_plan = forward_scheduling(
			valid_weeks=valid_weeks,
			group_items=group_items,
			group_capacity=group_capacity,
			item_backlog=item_backlog,
			item_week_demand=item_week_demand,
			item_backlog_wo=item_backlog_wo,
			item_week_wo=item_week_wo,
			leveling_enabled=True,
		)

		# 46. haftada backlog WO (1000) üretilir
		self.assertEqual(wo_plan["ITEM1"]["2026_w46"], 1000)
		# 46. haftaya sığmayan 500 adetlik WO 47. haftaya devretmeli ve üretilmelidir
		self.assertEqual(wo_plan["ITEM1"]["2026_w47"], 500)
		# Toplam WO planı tam olarak 1500 olmalı, 0 kayıp yaşanmalıdır
		self.assertEqual(sum(wo_plan["ITEM1"].values()), 1500)



if __name__ == "__main__":
	unittest.main()
