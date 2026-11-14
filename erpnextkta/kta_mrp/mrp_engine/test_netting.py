# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
from datetime import date

from erpnextkta.kta_mrp.mrp_engine.netting import lot_size, net_material
from erpnextkta.kta_mrp.mrp_engine.weeks import (
	clamp_to_first_week,
	sort_weeks,
	week_key,
	week_label,
	week_start,
)

WEEKS = ["2026_w45", "2026_w46", "2026_w47", "2026_w48"]


def weekly(*values):
	return dict(zip(WEEKS, values, strict=False))


class TestLotSize(unittest.TestCase):
	def test_no_shortage_means_no_order(self):
		self.assertEqual(lot_size(0, moq=500, pack=100), 0)

	def test_rounds_up_to_pack_multiple(self):
		self.assertEqual(lot_size(101, moq=0, pack=50), 150)

	def test_never_below_moq(self):
		self.assertEqual(lot_size(40, moq=500, pack=100), 500)

	def test_zero_pack_is_treated_as_one(self):
		self.assertEqual(lot_size(3.2, moq=0, pack=0), 4)

	def test_float_noise_does_not_add_extra_pack(self):
		self.assertAlmostEqual(lot_size(0.3, moq=0, pack=0.1), 0.3)


class TestNetMaterial(unittest.TestCase):
	def test_plan_example(self):
		"""Plan belgesindeki örnek: serbest stok 100, MOQ 500, paket 100, W47'de 300 PO."""
		result = net_material(
			WEEKS, weekly(60, 80, 0, 200), free_stock=100, receipts={"2026_w47": 300}, moq=500, pack=100
		)
		self.assertEqual(result.net, weekly(0, 40, 0, 0))
		self.assertEqual(result.planned_orders, weekly(0, 500, 0, 0))
		self.assertEqual(result.projected, weekly(40, -40, 260, 60))
		self.assertEqual(result.first_shortage_week, "2026_w46")
		self.assertEqual(result.coverage_weeks, 1)
		self.assertEqual(result.surplus_po, 60)

	def test_sufficient_stock(self):
		result = net_material(WEEKS, weekly(100, 100, 100, 100), free_stock=1000)
		self.assertEqual(result.planned_order_total, 0)
		self.assertIsNone(result.first_shortage_week)
		self.assertEqual(result.coverage_weeks, len(WEEKS))
		self.assertEqual(result.projected["2026_w48"], 600)

	def test_reserved_above_stock_is_current_shortage(self):
		"""Rezerve > Stok: ilk hafta talep olmasa bile eksik kapatılmalı."""
		result = net_material(WEEKS, weekly(0, 10, 0, 0), free_stock=-50)
		self.assertEqual(result.net, weekly(50, 10, 0, 0))
		self.assertEqual(result.planned_orders, weekly(50, 10, 0, 0))
		self.assertEqual(result.coverage_weeks, 0)

	def test_late_po_does_not_cover_earlier_week(self):
		result = net_material(WEEKS, weekly(100, 0, 0, 0), free_stock=0, receipts={"2026_w46": 100})
		self.assertEqual(result.net["2026_w45"], 100)
		self.assertEqual(result.projected, weekly(-100, 0, 0, 0))

	def test_po_in_need_week_covers_demand(self):
		result = net_material(WEEKS, weekly(0, 100, 0, 0), free_stock=0, receipts={"2026_w46": 100})
		self.assertEqual(result.net_total, 0)
		self.assertEqual(result.surplus_po, 0)

	def test_moq_surplus_covers_following_weeks(self):
		result = net_material(WEEKS, weekly(10, 10, 10, 0), free_stock=0, moq=25, pack=1)
		self.assertEqual(result.planned_orders, weekly(25, 0, 25, 0))

	def test_surplus_po_excludes_initial_stock(self):
		"""Fazla PO, başlangıç stoğunu değil sadece ihtiyaç fazlası PO'yu göstermeli."""
		result = net_material(WEEKS, weekly(50, 0, 0, 0), free_stock=500, receipts={"2026_w46": 100})
		self.assertEqual(result.surplus_po, 100)

	def test_net_material_respects_safety_stock(self):
		"""Emniyet stoğu tanımlandığında stok emniyet seviyesinin altına inmeden açık doğmalıdır."""
		weeks = ["2026_w46", "2026_w47"]
		gross = {"2026_w46": 50, "2026_w47": 50}
		# Serbest stok 80, emniyet stoğu 40. 46. haftada talep 50 -> kalan 30 < 40 emniyet stoğu!
		res = net_material(weeks, gross, free_stock=80, safety_stock=40, pack=1)
		# 46. haftadaki açık: (50 + 40) - 80 = 10 olmalıdır
		self.assertEqual(res.net["2026_w46"], 10)
		self.assertEqual(res.planned_orders["2026_w46"], 10)



class TestWeeks(unittest.TestCase):
	def test_week_key_and_label(self):
		self.assertEqual(week_key(date(2026, 11, 4)), "2026_w45")
		self.assertEqual(week_label("2026_w05"), "2026-W05")

	def test_week_start_is_monday(self):
		self.assertEqual(week_start("2026_w45"), date(2026, 11, 2))

	def test_sort_across_year_boundary(self):
		self.assertEqual(sort_weeks(["2027_w01", "2026_w52", "2026_w52"]), ["2026_w52", "2027_w01"])

	def test_clamp_past_week_to_first_week(self):
		self.assertEqual(clamp_to_first_week("2026_w30", "2026_w45"), "2026_w45")
		self.assertEqual(clamp_to_first_week("2026_w50", "2026_w45"), "2026_w50")


class TestSourcingNetting(unittest.TestCase):
	def setUp(self):
		self.suppliers = [
			{
				"supplier": "Lumberg",
				"quota_share": 50.0,
				"moq": 3600,
				"pack": 1800,
				"price": 0.1327,
				"lead_time_days": 77,
				"idx": 1,
			},
			{
				"supplier": "GMS",
				"quota_share": 50.0,
				"moq": 3600,
				"pack": 1800,
				"price": 0.1079,
				"lead_time_days": 77,
				"idx": 2,
			},
		]

	def test_quota_split(self):
		result = net_material(
			WEEKS,
			weekly(10000, 0, 0, 0),
			free_stock=0,
			sourcing_strategy="Kotalı Dağılım (% Paylaşım)",
			suppliers=self.suppliers,
		)
		self.assertEqual(result.net["2026_w45"], 10000)
		self.assertEqual(result.planned_orders_by_supplier["Lumberg"]["2026_w45"], 5400)
		self.assertEqual(result.planned_orders_by_supplier["GMS"]["2026_w45"], 5400)
		self.assertEqual(result.planned_orders["2026_w45"], 10800)

	def test_least_cost(self):
		result = net_material(
			WEEKS,
			weekly(10000, 0, 0, 0),
			free_stock=0,
			sourcing_strategy="En Düşük Fiyat Öncelikli",
			suppliers=self.suppliers,
		)
		self.assertEqual(result.planned_orders_by_supplier["GMS"]["2026_w45"], 10800)
		self.assertNotIn("Lumberg", result.planned_orders_by_supplier)
		self.assertEqual(result.planned_orders["2026_w45"], 10800)

	def test_lead_time_priority(self):
		fast_suppliers = [
			{"supplier": "Prysmian", "quota_share": 70, "moq": 1000, "pack": 100, "price": 0.05, "lead_time_days": 84, "idx": 1},
			{"supplier": "Sipro", "quota_share": 30, "moq": 1000, "pack": 100, "price": 0.055, "lead_time_days": 15, "idx": 2},
		]
		result = net_material(
			WEEKS,
			weekly(5000, 0, 0, 0),
			free_stock=0,
			sourcing_strategy="Termin Süresi Öncelikli",
			suppliers=fast_suppliers,
		)
		self.assertEqual(result.planned_orders_by_supplier["Sipro"]["2026_w45"], 5000)
		self.assertNotIn("Prysmian", result.planned_orders_by_supplier)

	def test_quota_small_shortage_consolidates_to_primary_supplier(self):
		"""Net açık tedarikçilerin MOQ toplamından küçükse, kamçı etkisini önlemek için ana tedarikçide toplanır."""
		weeks = ["2026_w46"]
		gross = {"2026_w46": 100}
		suppliers = [
			{"supplier": "SupA", "quota_share": 60, "moq": 500, "pack": 100, "idx": 1},
			{"supplier": "SupB", "quota_share": 40, "moq": 500, "pack": 100, "idx": 2},
		]
		res = net_material(
			weeks,
			gross,
			free_stock=0,
			sourcing_strategy="Kotalı Dağılım (% Paylaşım)",
			suppliers=suppliers,
		)
		# A'dan 500 ve B'den 500 (toplam 1000) açmak yerine, ana tedarikçi SupA'dan tek 500 açılmalıdır
		self.assertEqual(res.planned_orders["2026_w46"], 500)
		self.assertEqual(res.planned_orders_by_supplier["SupA"]["2026_w46"], 500)
		self.assertEqual(res.planned_orders_by_supplier.get("SupB", {}).get("2026_w46", 0), 0)


