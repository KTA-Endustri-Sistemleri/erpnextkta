import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from erpnextkta.kta_mrp.api_impl import stock_requirements_list as srl


class TestStockRequirementsList(FrappeTestCase):
	def _base_elements(self, stock, safety):
		from_date = getdate(today())
		item_info = {"item_code": "_Test Item", "safety_stock": safety, "reorder_level": safety}
		elements = [srl._make_element(from_date, "Stock", "Stock", receipt_qty=stock)]
		safety_element = srl._get_safety_stock_element(item_info, from_date)
		if safety_element:
			elements.append(safety_element)
		return elements

	def test_no_safety_element_without_safety_stock(self):
		item_info = {"item_code": "_Test Item", "safety_stock": 0, "reorder_level": 0}
		self.assertIsNone(srl._get_safety_stock_element(item_info, getdate(today())))

	def test_reorder_level_is_shown_as_requirement_after_stock(self):
		elements = self._base_elements(stock=200, safety=500)
		elements.append(srl._make_element(add_days(today(), 7), "CustOrd", "SO", requirement_qty=50))
		elements = srl._sort_and_calculate_running_balance(elements)

		self.assertEqual([d["mrp_element_type"] for d in elements], ["Stock", "SafeSt", "CustOrd"])
		self.assertEqual(elements[1]["requirement_qty"], 500)
		self.assertEqual(elements[1]["available_qty"], -300)

	def test_exceptions_respect_net_balance(self):
		elements = self._base_elements(stock=200, safety=100)
		elements.append(srl._make_element(add_days(today(), 1), "CustOrd", "SO", requirement_qty=150))
		elements.append(srl._make_element(add_days(today(), 2), "CustOrd", "SO", requirement_qty=100))
		elements = srl._sort_and_calculate_running_balance(elements)
		elements = srl._detect_exceptions(elements, 100)

		# 200 - 100 - 150 = -50 -> emniyet altı, -150 -> fiziksel açık
		self.assertIsNone(elements[1]["exception_code"])
		self.assertEqual(elements[2]["exception_code"], "BELOW_SAFETY")
		self.assertEqual(elements[3]["exception_code"], "SHORTAGE")

	def test_safety_element_survives_date_filter(self):
		elements = self._base_elements(stock=10, safety=5)
		filtered = srl._filter_by_date(elements, getdate(today()), add_days(today(), -30))
		self.assertEqual(len(filtered), 2)

	def _so_lines(self, *qtys):
		return [frappe._dict(sales_order=f"SO-{i}", pending_qty=q) for i, q in enumerate(qtys)]

	def test_fg_supply_covers_earliest_orders_first(self):
		# stok + iş emri − emniyet = 150 → ilk sipariş tam, ikinci 50 karşılanır
		allocations = srl._allocate_fg_demand(self._so_lines(100, 100, 100), 150)
		self.assertEqual([(d.sales_order, q) for d, q in allocations], [("SO-1", 50), ("SO-2", 100)])

	def test_fg_below_safety_creates_replenishment(self):
		# stok 50, emniyet 200 → bugüne 150 tamamlama + tüm siparişler
		allocations = srl._allocate_fg_demand(self._so_lines(80), 50 - 200)
		self.assertIsNone(allocations[0][0])
		self.assertEqual(allocations[0][1], 150)
		self.assertEqual(allocations[1][1], 80)

	def test_fully_covered_orders_create_no_requirement(self):
		self.assertEqual(srl._allocate_fg_demand(self._so_lines(40, 60), 100), [])

	def _set_sevk_lookup(self):
		times = frappe._dict
		frappe.flags.kta_sevk_lookup = (
			{("CUST", "CUST-Depo"): times(production_time=14, delivery_time=7)},
			{"CUST": times(production_time=14, delivery_time=21)},
		)
		self.addCleanup(setattr, frappe.flags, "kta_sevk_lookup", None)

	def test_sevk_times_prefer_address_then_customer(self):
		self._set_sevk_lookup()
		by_addr = srl._get_sevk_times(frappe._dict(customer="CUST", shipping_address_name="CUST-Depo"))
		fallback = srl._get_sevk_times(frappe._dict(customer="CUST", shipping_address_name="X"))
		self.assertEqual(by_addr.delivery_time, 7)
		self.assertEqual(fallback.delivery_time, 21)

	def test_customer_order_date_is_factory_ship_date(self):
		self._set_sevk_lookup()
		row = frappe._dict(
			customer="CUST", customer_address="X", delivery_date=getdate("2026-11-27"),
			pending_qty=10, voucher_no="SO-1",
		)
		self.assertEqual(srl._make_customer_order_element(row)["date"], "2026-11-06")

	def test_calc_wo_capacity_end_date(self):
		# 7.000 / 6 = 1.166,66 adet/gün -> 80 adet için 1 iş günü gerekir
		wo_in_process = frappe._dict(status="In Process", pending_qty=80)
		end_date = srl._calc_wo_capacity_end_date(wo_in_process, 7000)
		self.assertTrue(getdate(end_date) >= getdate(today()))

		# Başlamamış iş emrinde planned_start_date (Perşembe) + 5 iş günü (Pazar atlanır) -> Çarşamba (6 gün sonra)
		wo_not_started = frappe._dict(
			status="Not Started",
			planned_start_date="2026-10-15",
			pending_qty=5000,
		)
		# 5.000 / 1166.66 = 5 iş günü.
		# Perşembe 15 -> Cuma 16 (1), Cmt 17 (2), Paz 18 (atla), Pzt 19 (3), Salı 20 (4), Çar 21 (5)
		end_date_5000 = srl._calc_wo_capacity_end_date(wo_not_started, 7000)
		self.assertEqual(end_date_5000, "2026-10-21")

	def test_receipts_sorted_before_requirements_on_same_date(self):
		target_date = "2026-10-23"
		elements = [
			srl._make_element(target_date, "CustOrd", "SO", requirement_qty=580),
			srl._make_element(target_date, "PldOrd", "Planlı Sipariş", receipt_qty=580),
		]
		sorted_elements = srl._sort_and_calculate_running_balance(elements)
		self.assertEqual(sorted_elements[0]["mrp_element_type"], "PldOrd")
		self.assertEqual(sorted_elements[0]["available_qty"], 580)
		self.assertEqual(sorted_elements[1]["mrp_element_type"], "CustOrd")
		self.assertEqual(sorted_elements[1]["available_qty"], 0)

	def test_backward_capacity_leveling_caps_weekly_pldord(self):
		# Sipariş 2027-02-28 (2027-W08) için 13.248 adet ve haftalık kapasite 7.000
		allocations = [(
			frappe._dict(
				sales_order="SO-TEST",
				delivery_date=getdate("2027-02-28"),
				shipping_address_name=None,
				customer_address=None,
				customer="Test",
			),
			13248.0,
		)]
		# BOM ve SO mock'lamadan doğrudan backward leveling döngüsünü test etmek için
		# stock_requirements_list'teki mantığı izole çağırıyoruz
		item_info = {"weekly_production": 7000}
		orig_get_value = frappe.db.get_value
		def fake_get_value(*args, **kwargs):
			dt = args[0] if args else kwargs.get("doctype")
			if dt == "BOM":
				return "BOM-ITEM"
			return orig_get_value(*args, **kwargs)

		with unittest.mock.patch.object(srl, "_get_open_so_lines", return_value={"ITEM": [allocations[0][0]]}), \
		     unittest.mock.patch.object(srl, "_get_fg_stock_map", return_value={"ITEM": 0}), \
		     unittest.mock.patch.object(srl, "_get_fg_open_wo_map", return_value={"ITEM": 0}), \
		     unittest.mock.patch.object(srl, "_get_fg_reorder_map", return_value={"ITEM": 0}), \
		     unittest.mock.patch.object(srl, "_allocate_fg_demand", return_value=allocations), \
		     unittest.mock.patch.object(srl, "_get_sevk_times", return_value=frappe._dict(production_time=0, delivery_time=0)), \
		     unittest.mock.patch("frappe.db.get_value", side_effect=fake_get_value):
			pld_elements = srl._get_planned_order_elements("ITEM", item_info)

		from collections import defaultdict
		by_week = defaultdict(float)
		for el in pld_elements:
			by_week[el["week_label"]] += el["receipt_qty"]

		# Hiçbir hafta 7.000'i aşmamalı
		for w, total in by_week.items():
			self.assertLessEqual(total, 7000.0)

		# 2027-W08'de 7000, 2027-W07'de kalan 6248 olmalı
		self.assertEqual(by_week["2027-W08"], 7000.0)
		self.assertEqual(by_week["2027-W07"], 6248.0)
		self.assertEqual(sum(by_week.values()), 13248.0)

	def test_simulated_requirement_elements_uses_pld_order_leveling(self):
		# Hammadde RAW-1, FG mamulü için birim tüketim 2.0
		# FG mamulü PldOrd olarak W08'de 7000, W07'de 6248 planlandı
		pld_orders = [
			srl._make_element("2027-02-19", "PldOrd", "Pld-W07", receipt_qty=6248, start_date="2027-02-15"),
			srl._make_element("2027-02-28", "PldOrd", "Pld-W08", receipt_qty=7000, start_date="2027-02-22"),
		]
		with unittest.mock.patch.object(srl, "_get_where_used", return_value={"FG": 2.0}), \
		     unittest.mock.patch.object(srl, "_get_open_so_lines", return_value={"FG": []}), \
		     unittest.mock.patch.object(srl, "_get_fg_stock_map", return_value={"FG": 0}), \
		     unittest.mock.patch.object(srl, "_get_fg_open_wo_map", return_value={"FG": 0}), \
		     unittest.mock.patch.object(srl, "_get_fg_reorder_map", return_value={"FG": 0}), \
		     unittest.mock.patch("frappe.get_all", return_value=[frappe._dict(name="FG", custom_weekly_production=7000)]), \
		     unittest.mock.patch.object(srl, "_get_planned_order_elements", return_value=pld_orders):
			sim_elements = srl._get_simulated_requirement_elements("RAW-1")

		self.assertEqual(len(sim_elements), 2)
		# W07 için SimReq miktarı: 6248 * 2 = 12496, tarihi Pazartesi 2027-02-15
		self.assertEqual(sim_elements[0]["date"], "2027-02-15")
		self.assertEqual(sim_elements[0]["requirement_qty"], 12496.0)
		self.assertEqual(sim_elements[0]["mrp_element_type"], "SimReq")

		# W08 için SimReq miktarı: 7000 * 2 = 14000, tarihi Pazartesi 2027-02-22
		self.assertEqual(sim_elements[1]["date"], "2027-02-22")
		self.assertEqual(sim_elements[1]["requirement_qty"], 14000.0)

	def test_purchase_receipt_intrnst_and_bonded_deducts_from_po(self):
		pr_rows = [
			frappe._dict(
				pr_item_name="PR-ITEM-1",
				voucher_no="PREC-RET-01",
				purchase_order="PO-01",
				purchase_order_item="PO-ITEM-1",
				qty=900.0,
				supplier="Supplier A",
				workflow_state="Antrepoda",
				posting_date="2026-10-12",
				gumruge_gelis_tarihi="2026-10-12",
				tahmini_varis_tarihi=None,
			),
			frappe._dict(
				pr_item_name="PR-ITEM-2",
				voucher_no="PREC-RET-02",
				purchase_order="PO-02",
				purchase_order_item="PO-ITEM-2",
				qty=2000.0,
				supplier="Supplier B",
				workflow_state="Yolda",
				posting_date="2026-10-15",
				gumruge_gelis_tarihi=None,
				tahmini_varis_tarihi="2026-10-20",
			),
		]
		po_rows = [
			frappe._dict(
				po_item_name="PO-ITEM-1",
				schedule_date="2026-11-09",
				voucher_no="PO-01",
				pending_qty=10000.0,
				supplier="Supplier A",
				idx=1,
			),
			frappe._dict(
				po_item_name="PO-ITEM-2",
				schedule_date="2026-10-25",
				voucher_no="PO-02",
				pending_qty=2000.0,
				supplier="Supplier B",
				idx=1,
			),
		]
		with unittest.mock.patch("frappe.db.sql", side_effect=[pr_rows, po_rows]):
			elements = srl._get_purchase_order_elements("ITEM-X")

		# 1. Antrepoda: 900
		self.assertEqual(elements[0]["mrp_element_type"], "Bonded")
		self.assertEqual(elements[0]["receipt_qty"], 900.0)
		self.assertEqual(elements[0]["date"], "2026-10-12")

		# 2. Yolda: 2000
		self.assertEqual(elements[1]["mrp_element_type"], "InTrnst")
		self.assertEqual(elements[1]["receipt_qty"], 2000.0)
		self.assertEqual(elements[1]["date"], "2026-10-20")

		# 3. PO-ITEM-1: 10000 - 900 = 9100
		self.assertEqual(elements[2]["mrp_element_type"], "PO")
		self.assertEqual(elements[2]["receipt_qty"], 9100.0)

		# PO-ITEM-2: 2000 - 2000 = 0 (tamamen Yolda tarafından karşılandı, PO oluşturulmamalı)
		self.assertEqual(len(elements), 3)

	def test_purchase_proposal_elements_weekly_consolidation_and_rounding(self):
		item_info = {
			"current_stock": 1000.0,
			"default_supplier": "Lumberg",
			"default_warehouse": "GKK DEPOSU",
			"primary_supplier": {
				"supplier": "Lumberg",
				"rate": 0.35,
				"currency": "EUR",
				"lead_time_days": 70,
				"moq": 2352.0,
				"paket": 1176.0,
				"is_default": True,
			},
			"suppliers": [
				{
					"supplier": "Lumberg",
					"rate": 0.35,
					"currency": "EUR",
					"lead_time_days": 70,
					"moq": 2352.0,
					"paket": 1176.0,
					"is_default": True,
				}
			],
		}
		# 2027-W13 talep 2500 -> bakiye 1000 - 2500 = -1500 (açık: 1500)
		# ceil(1500 / 1176) * 1176 = 2352 -> max(2352, 2352) = 2352 öneri
		# Kalan bakiye: -1500 + 2352 = +852 sonraki haftaya devreder!
		# 2027-W14 talep 500 -> +852 bakiyesi 500'ü karşılar (+352 bakiye kalır), yeni öneri açılmaz!
		current_elements = [
			srl._make_element("2027-03-29", "DepReq", "DepReq-1", requirement_qty=2500),
			srl._make_element("2027-04-05", "DepReq", "DepReq-2", requirement_qty=500),
		]
		proposals = srl._get_purchase_proposal_elements("RAW-ITEM", item_info, current_elements)
		self.assertEqual(len(proposals), 1)
		self.assertEqual(proposals[0]["mrp_element_type"], "PurRqs")
		self.assertEqual(proposals[0]["receipt_qty"], 2352.0)
		self.assertEqual(proposals[0]["date"], "2027-03-29")
		self.assertEqual(proposals[0]["start_date"], "2027-01-18")
		self.assertEqual(proposals[0]["deficit_qty"], 1500.0)

	def test_purchase_receipt_intrnst_arrival_date_calculated_from_lead_time(self):
		pr_rows = [
			frappe._dict(
				pr_item_name="PR-ITEM-ELESUN",
				voucher_no="PREC-RET-05483",
				purchase_order="PUR-ORD-2026-03780",
				purchase_order_item="akh58chqhu",
				qty=7020.0,
				supplier="Jiangsu Elesun Cable Co.,Ltd",
				workflow_state="Yolda",
				posting_date="2026-10-02",
				yukleme_tarihi="2026-10-02",
				gumruge_gelis_tarihi=None,
				tahmini_varis_tarihi=None,
				po_schedule_date="2026-11-09",
			),
		]
		ip_rows = [
			frappe._dict(
				supplier="Jiangsu Elesun Cable Co.,Ltd",
				lead_time_days=42,
			)
		]
		po_rows = []

		with unittest.mock.patch("frappe.db.sql", side_effect=[pr_rows, ip_rows, po_rows]):
			elements = srl._get_purchase_order_elements("10023266")

		self.assertEqual(len(elements), 1)
		self.assertEqual(elements[0]["mrp_element_type"], "InTrnst")
		# 2026-10-02 + 42 gun = 2026-11-13 (Hafta: 2026-W46)
		self.assertEqual(elements[0]["date"], "2026-11-13")
		self.assertEqual(elements[0]["week_label"], "2026-W46")
		self.assertEqual(elements[0]["receipt_qty"], 7020.0)

	def test_weekly_aggregation_uses_opening_stock_and_excludes_stock_from_week_receipts(self):
		elements = [
			srl._make_element("2026-10-16", "Stock", "Mevcut Stok", receipt_qty=1000.0),
			srl._make_element("2026-09-01", "DepReq", "DepReq W36", requirement_qty=200.0),
			srl._make_element("2026-10-12", "DepReq", "DepReq W42", requirement_qty=300.0),
			srl._make_element("2026-10-12", "PurRqs", "PurRqs W42", receipt_qty=500.0),
		]
		weekly = srl._aggregate_weekly(elements)
		self.assertEqual(len(weekly), 2)

		# W36
		self.assertEqual(weekly[0]["week_label"], "2026-W36")
		self.assertEqual(weekly[0]["receipt_qty"], 0.0)
		self.assertEqual(weekly[0]["requirement_qty"], 200.0)
		# Açılış stoğundan (1000) düşer: 1000 - 200 = 800 (negatife düşmez!)
		self.assertEqual(weekly[0]["available_qty"], 800.0)

		# W42
		self.assertEqual(weekly[1]["week_label"], "2026-W42")
		# Mevcut Stok (1000) bu haftanın girişine dahil edilmez, sadece gerçek PurRqs (500) giriştir!
		self.assertEqual(weekly[1]["receipt_qty"], 500.0)
		self.assertEqual(weekly[1]["requirement_qty"], 300.0)
		self.assertEqual(weekly[1]["available_qty"], 1000.0)

	def test_purchase_proposal_forward_scheduling_when_order_date_in_past(self):
		item_info = {
			"current_stock": 0.0,
			"default_supplier": "Supplier A",
			"default_warehouse": "Stores",
			"primary_supplier": {
				"supplier": "Supplier A",
				"lead_time_days": 42,
				"moq": 1000.0,
				"paket": 500.0,
			},
			"suppliers": [],
		}
		# Talep bugünden 7 gün sonra (W+1). Lead time 42 gün olduğu için sipariş tarihi geçmişe düşer.
		demand_date = add_days(today(), 7)
		current_elements = [
			srl._make_element(demand_date, "DepReq", "DepReq-PastOrder", requirement_qty=1200.0),
		]
		proposals = srl._get_purchase_proposal_elements("RAW-TEST", item_info, current_elements)
		self.assertEqual(len(proposals), 1)
		p = proposals[0]
		self.assertEqual(p["mrp_element_type"], "PurRqs")
		# Miktar: ceil(1200 / 500) * 500 = 1500
		self.assertEqual(p["receipt_qty"], 1500.0)
		# Forward scheduling: Sipariş bugün verilir, varış bugün + 42 gündür
		expected_deliv = str(getdate(add_days(today(), 42)))
		self.assertEqual(p["date"], expected_deliv)
		self.assertEqual(p["start_date"], str(getdate(today())))
		self.assertEqual(p["exception_code"], "OVERDUE")

	def test_planned_order_forward_scheduling_when_production_start_in_past(self):
		# Satış siparişi teslim tarihi bugün + 2 gün, üretim süresi 10 gün -> başlangıç geçmişe düşer
		so_line = frappe._dict(
			sales_order="SO-OVERDUE",
			delivery_date=add_days(today(), 2),
			shipping_address_name=None,
			customer_address=None,
			customer="Test Customer",
			pending_qty=100.0,
		)
		allocations = [(so_line, 100.0)]
		item_info = {"weekly_production": 0}

		with unittest.mock.patch.object(srl, "_get_open_so_lines", return_value={"FG-TEST": [so_line]}), \
		     unittest.mock.patch.object(srl, "_get_fg_stock_map", return_value={"FG-TEST": 0}), \
		     unittest.mock.patch.object(srl, "_get_fg_open_wo_map", return_value={"FG-TEST": 0}), \
		     unittest.mock.patch.object(srl, "_get_fg_reorder_map", return_value={"FG-TEST": 0}), \
		     unittest.mock.patch.object(srl, "_allocate_fg_demand", return_value=allocations), \
		     unittest.mock.patch.object(srl, "_get_sevk_times", return_value=frappe._dict(production_time=10, delivery_time=0)), \
		     unittest.mock.patch("frappe.db.get_value", return_value="BOM-TEST"):
			pld_elements = srl._get_planned_order_elements("FG-TEST", item_info)

		self.assertEqual(len(pld_elements), 1)
		p = pld_elements[0]
		self.assertEqual(p["mrp_element_type"], "PldOrd")
		self.assertEqual(p["receipt_qty"], 100.0)
		# Forward scheduling: başlangıç bugün, bitiş bugün + 10 gün
		self.assertEqual(p["start_date"], str(getdate(today())))
		self.assertEqual(p["date"], str(getdate(add_days(today(), 10))))
		self.assertEqual(p["exception_code"], "OVERDUE")
