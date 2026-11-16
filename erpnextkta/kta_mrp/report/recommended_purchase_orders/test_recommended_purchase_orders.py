# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
from unittest.mock import patch

import frappe
from erpnextkta.kta_mrp.mrp_engine.netting import net_material
from erpnextkta.kta_mrp.mrp_engine.service import MaterialRequirement, MaterialRequirementResult
from erpnextkta.kta_mrp.report.recommended_purchase_orders import recommended_purchase_orders as rpo

WEEKS = ["2026_w46", "2026_w47"]


def material(
	item_code,
	gross,
	moq=0,
	pack=1,
	lead_time_days=0,
	supplier="SUP-A",
	suppliers_quota=None,
	planned_orders_by_supplier=None,
):
	netting = net_material(WEEKS, dict(zip(WEEKS, gross, strict=False)), moq=moq, pack=pack)
	if planned_orders_by_supplier is not None:
		netting.planned_orders_by_supplier = planned_orders_by_supplier
	return MaterialRequirement(
		item_code=item_code,
		item_name=item_code,
		uom="Nos",
		supplier=supplier,
		actual=0,
		reserved=0,
		netting=netting,
		moq=moq,
		pack=pack,
		lead_time_days=lead_time_days,
		suppliers_quota=suppliers_quota or [],
		planned_orders_by_supplier=netting.planned_orders_by_supplier,
	)


def run(materials, from_date="2026-11-09"):
	result = MaterialRequirementResult(weeks=WEEKS, materials={m.item_code: m for m in materials})
	with patch.object(rpo, "get_material_requirements", return_value=result) as service:
		output = rpo.execute({"from_date": from_date, "to_date": "2027-02-09"})
	return output, service


class TestRecommendedPurchaseOrders(unittest.TestCase):
	def test_orders_are_shifted_by_lead_time(self):
		(columns, data, *_), _service = run([material("RM-1", [40, 0], lead_time_days=14)], from_date="2026-10-26")
		self.assertEqual(data[0]["2026_w44"], 40)
		self.assertIn("2026_w44", [c["fieldname"] for c in columns])

	def test_moq_is_not_applied_twice(self):
		"""MR siparişi 500'e yuvarladı; RPO bunu tekrar MOQ ile birleştirmemeli."""
		(_columns, data, *_), _service = run([material("RM-1", [40, 40], moq=500, pack=100)])
		self.assertEqual(data[0]["row_total"], 500)
		self.assertEqual(data[0]["2026_w46"], 500)

	def test_materials_without_orders_are_excluded(self):
		(_columns, data, *_), _service = run([material("RM-1", [0, 0]), material("RM-2", [5, 0])])
		self.assertEqual([row["hammadde"] for row in data[:-1]], ["RM-2"])

	def test_demand_filters_are_forwarded(self):
		_output, service = run([])
		self.assertEqual(service.call_args.args[0], {"from_date": "2026-11-09", "to_date": "2027-02-09"})
		self.assertTrue(service.call_args.kwargs["include_po"])

	def test_past_due_order_clamps_to_first_valid_week(self):
		"""Teslim süresi başlangıç haftasını aşan siparişler ilk geçerli haftaya sabitlenir ve acil işaretlenir."""
		(columns, data, *_), _service = run([material("RM-1", [40, 0], lead_time_days=14)])
		# from_date 2026-11-09 -> W46. 14 gün önce W44'e düşer ama W46'ya sabitlenir.
		self.assertEqual(data[0]["2026_w46"], 40)
		self.assertNotIn("2026_w44", [c["fieldname"] for c in columns])
		self.assertEqual(data[0]["is_past_due"], 1)
		self.assertIn("Acil", data[0]["status"])

	def test_rpo_expands_multi_supplier_and_individual_lead_times(self):
		"""Çoklu tedarikçisi olan hammadde her tedarikçi için ayrı satır ve kendi lead time'ı ile ötelenir."""
		mat = material(
			"RM-1",
			[0, 100],
			suppliers_quota=[
				frappe._dict(supplier="SUP-A", moq=50, pack=10, lead_time_days=7),
				frappe._dict(supplier="SUP-B", moq=50, pack=10, lead_time_days=21),
			],
			planned_orders_by_supplier={
				"SUP-A": {"2026_w47": 60},
				"SUP-B": {"2026_w47": 40},
			},
		)
		(columns, data, *_), _service = run([mat])
		rows = [r for r in data if r["hammadde"] == "RM-1"]
		self.assertEqual(len(rows), 2)

		row_a = next(r for r in rows if r["supplier"] == "SUP-A")
		row_b = next(r for r in rows if r["supplier"] == "SUP-B")

		# SUP-A: W47 - 7 gün = W46 >= W46
		self.assertEqual(row_a["2026_w46"], 60)
		self.assertEqual(row_a["lead_time_days"], 7)
		self.assertEqual(row_a["is_past_due"], 0)

		# SUP-B: W47 - 21 gün = W44 < W46 -> W46'ya clamp edilir ve is_past_due=1
		self.assertEqual(row_b["2026_w46"], 40)
		self.assertEqual(row_b["lead_time_days"], 21)
		self.assertEqual(row_b["is_past_due"], 1)

