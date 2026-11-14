"""mrp_engine.psw birim testleri.

Pure PSW (Production Start Week) talep netleştirme ve motor testleri:
1. Geriye doğru çizelgeleme (resolve_lead_time entegrasyonu)
2. Satış siparişi (Sales Order) taleplerinin haftalık kovalara (week buckets) dağıtımı
3. Dahili üretim taleplerinin (Manufacture Material Request) üretim süresi düşülerek dağıtımı
4. Stok ve WIP (İş Emri) karşılama ve emniyet stoğu izolasyonu
5. PswResult veri yapısının tutarlılığı
"""

from datetime import date, timedelta
import unittest
from unittest.mock import patch
import frappe

from erpnextkta.kta_mrp.mrp_engine.psw import (
	PswResult,
	calculate_psw_demand,
	get_iso_week_label,
)
from erpnextkta.kta_mrp.mrp_engine.settings import MrpSettings


class TestPswEngine(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		if not frappe.db:
			frappe.init("development.localhost")
			frappe.connect()

	def setUp(self):
		self.settings = MrpSettings(
			default_production_time_days=14,
			default_delivery_time_days=2,
		)

	def test_get_iso_week_label(self):
		"""Tarih nesnesi ISO hafta etiketine dönüştürülür."""
		label = get_iso_week_label("2026-06-15")
		self.assertEqual(label, "2026-W25")

	def test_calculate_psw_demand_structure(self):
		"""calculate_psw_demand PswResult döndürür ve gerekli alanlara sahiptir."""
		filters = {
			"from_date": "2026-06-01",
			"to_date": "2026-06-30",
			"range": "Weekly",
		}
		with patch.object(frappe, "get_all", return_value=[]), patch.object(frappe.db, "sql", return_value=[]):
			result = calculate_psw_demand(filters, settings=self.settings)
			self.assertIsInstance(result, PswResult)
			self.assertTrue(len(result.periodic_ranges) > 0)
			self.assertTrue(len(result.period_labels) > 0)
			self.assertEqual(len(result.rows), 0)
			self.assertEqual(result.summary["total_to_produce"], 0)

	def test_psw_netting_with_stock_and_wip(self):
		"""Stok ve WIP talepten sırasıyla düşülür, kalan miktar to_produce olur."""
		# Senaryo:
		# Talep: 100 Adet (W25)
		# Stok: 40 Adet
		# Emniyet Stoğu: 10 Adet -> Kullanılabilir Stok: 30 Adet
		# WIP (İş Emri): 20 Adet
		# Beklenen:
		# Stok Karşılanan: 30
		# WIP Karşılanan: 20
		# Üretilecek (to_produce): 100 - 30 - 20 = 50 Adet
		from erpnextkta.kta_mrp.mrp_engine.psw import apply_stock_wip_netting

		demands = {"2026-W25": 100}
		stock = 40
		safety_stock = 10
		wip = 20

		netted = apply_stock_wip_netting(
			demands=demands,
			stock=stock,
			safety_stock=safety_stock,
			wip=wip,
			period_labels=["2026-W25"],
		)

		self.assertEqual(netted.stock_covered, 30)
		self.assertEqual(netted.wip_covered, 20)
		self.assertEqual(netted.to_produce["2026-W25"], 50)
		self.assertEqual(netted.total_to_produce, 50)

	def test_packing_multiplier_rounding(self):
		"""Müşteri paketleme katı varsa üretilecek miktar yukarı yuvarlanır."""
		from erpnextkta.kta_mrp.mrp_engine.psw import apply_stock_wip_netting

		demands = {"2026-W25": 12}
		netted = apply_stock_wip_netting(
			demands=demands,
			stock=0,
			safety_stock=0,
			wip=0,
			period_labels=["2026-W25"],
			packing=10.0,
		)
		# 12 adet talep, paket katı 10 -> 20 adede yuvarlanmalı
		self.assertEqual(netted.to_produce["2026-W25"], 20)
		self.assertEqual(netted.total_to_produce, 20)


if __name__ == "__main__":
	unittest.main()
