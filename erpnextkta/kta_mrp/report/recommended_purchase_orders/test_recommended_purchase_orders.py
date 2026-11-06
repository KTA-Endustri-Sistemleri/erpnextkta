# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
from unittest.mock import patch

from erpnextkta.kta_mrp.mrp_engine.netting import net_material
from erpnextkta.kta_mrp.mrp_engine.service import MaterialRequirement, MaterialRequirementResult
from erpnextkta.kta_mrp.report.recommended_purchase_orders import recommended_purchase_orders as rpo

WEEKS = ["2026_w46", "2026_w47"]


def material(item_code, gross, moq=0, pack=1, lead_time_days=0):
	return MaterialRequirement(
		item_code=item_code,
		item_name=item_code,
		uom="Nos",
		supplier="SUP-A",
		actual=0,
		reserved=0,
		netting=net_material(WEEKS, dict(zip(WEEKS, gross, strict=False)), moq=moq, pack=pack),
		moq=moq,
		pack=pack,
		lead_time_days=lead_time_days,
	)


def run(materials):
	result = MaterialRequirementResult(weeks=WEEKS, materials={m.item_code: m for m in materials})
	with patch.object(rpo, "get_material_requirements", return_value=result) as service:
		output = rpo.execute({"from_date": "2026-11-09", "to_date": "2027-02-09"})
	return output, service


class TestRecommendedPurchaseOrders(unittest.TestCase):
	def test_orders_are_shifted_by_lead_time(self):
		(columns, data, *_), _service = run([material("RM-1", [40, 0], lead_time_days=14)])
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
