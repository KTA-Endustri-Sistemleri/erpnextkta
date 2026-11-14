"""mrp_engine.lead_time birim testleri.

İki eksenli (Two-axis) SAP tarzı lead time çözümleme testleri:
1. Sevk / Yol Süresi ($T_{\\text{transit}}$): Address -> Customer -> Customer Group -> Settings
2. İmalat Süresi ($T_{\\text{prod}}$): Item Customer Detail -> Item -> Settings
3. Geriye Doğru Çizelgeleme (Backward Scheduling):
   - ship_date = delivery_date - shipping_days
   - prod_start_date = ship_date - production_days
"""

from datetime import date
import unittest
from unittest.mock import patch
import frappe

from erpnextkta.kta_mrp.mrp_engine.lead_time import (
	LeadTimeResult,
	resolve_lead_time,
	resolve_production_lead_days,
	resolve_shipping_lead_days,
)
from erpnextkta.kta_mrp.mrp_engine.settings import MrpSettings


class TestLeadTimeEngine(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		if not frappe.db:
			frappe.init("development.localhost")
			frappe.connect()

	def setUp(self):
		self.custom_settings = MrpSettings(
			default_production_time_days=14,
			default_delivery_time_days=2,
		)

	def test_shipping_address_overrides_all(self):
		"""Adres üzerinde tanımlı shipping lead time en yüksek önceliğe sahiptir."""
		with patch.object(frappe.db, "get_value") as mock_db:
			# address -> 5 days
			mock_db.side_effect = lambda dt, name, field: 5 if dt == "Address" and field == "custom_shipping_lead_days" else None
			days, source = resolve_shipping_lead_days(
				address="ADDR-001",
				customer="CUST-001",
				customer_group="Commercial",
				settings=self.custom_settings,
			)
			self.assertEqual(days, 5)
			self.assertEqual(source, "Address")

	def test_shipping_customer_fallback_when_address_empty(self):
		"""Adreste süre yoksa veya adres None ise Müşteri kartındaki süre kullanılır."""
		with patch.object(frappe.db, "get_value") as mock_db:
			def db_mock(dt, name, field):
				if dt == "Address":
					return 0
				if dt == "Customer" and field == "custom_shipping_lead_days":
					return 3
				return None

			mock_db.side_effect = db_mock
			days, source = resolve_shipping_lead_days(
				address="ADDR-001",
				customer="CUST-001",
				customer_group="Commercial",
				settings=self.custom_settings,
			)
			self.assertEqual(days, 3)
			self.assertEqual(source, "Customer")

	def test_shipping_customer_group_fallback_when_customer_empty(self):
		"""Müşteride de süre yoksa Müşteri Grubu kartındaki süre kullanılır."""
		with patch.object(frappe.db, "get_value") as mock_db:
			def db_mock(dt, name, field):
				if dt == "Customer Group" and field == "custom_shipping_lead_days":
					return 4
				return None

			mock_db.side_effect = db_mock
			days, source = resolve_shipping_lead_days(
				address=None,
				customer="CUST-001",
				customer_group="Commercial",
				settings=self.custom_settings,
			)
			self.assertEqual(days, 4)
			self.assertEqual(source, "Customer Group")

	def test_shipping_global_settings_fallback(self):
		"""Hiçbir kademede değer bulunamazsa KTA MRP Settings varsayılanı (2 gün) kullanılır."""
		with patch.object(frappe.db, "get_value", return_value=None):
			days, source = resolve_shipping_lead_days(
				address=None,
				customer=None,
				customer_group=None,
				settings=self.custom_settings,
			)
			self.assertEqual(days, 2)
			self.assertEqual(source, "Default Settings")

	def test_production_item_customer_detail_overrides_item(self):
		"""Müşteriye özel üretim süresi (Item Customer Detail) Item kartındakini ezer."""
		with patch.object(frappe.db, "get_value") as mock_db:
			def db_mock(dt, filters, fieldname=None, as_dict=False):
				if dt == "Item Customer Detail":
					return 21
				if dt == "Item":
					return 10
				return None

			mock_db.side_effect = db_mock
			days, source = resolve_production_lead_days(
				item_code="ITEM-001",
				customer="CUST-001",
				settings=self.custom_settings,
			)
			self.assertEqual(days, 21)
			self.assertEqual(source, "Item Customer Detail")

	def test_production_item_master_fallback_when_no_customer_detail(self):
		"""Müşteriye özel süre yoksa Item.custom_manufacturing_lead_days kullanılır."""
		with patch.object(frappe.db, "get_value") as mock_db:
			def db_mock(dt, filters, fieldname=None, as_dict=False):
				if dt == "Item Customer Detail":
					return 0
				if dt == "Item" and fieldname == "custom_manufacturing_lead_days":
					return 7
				return None

			mock_db.side_effect = db_mock
			days, source = resolve_production_lead_days(
				item_code="ITEM-001",
				customer="CUST-001",
				settings=self.custom_settings,
			)
			self.assertEqual(days, 7)
			self.assertEqual(source, "Item")

	def test_production_global_settings_fallback(self):
		"""Item ve Item Customer Detail'de süre yoksa KTA MRP Settings (14 gün) kullanılır."""
		with patch.object(frappe.db, "get_value", return_value=None):
			days, source = resolve_production_lead_days(
				item_code="ITEM-001",
				customer=None,
				settings=self.custom_settings,
			)
			self.assertEqual(days, 14)
			self.assertEqual(source, "Default Settings")

	def test_backward_scheduling_calculation(self):
		"""Teslim tarihinden geriye doğru sevk ve üretim başlangıç tarihleri hesaplanır."""
		# Teslim tarihi: 2026-06-20
		# Sevk süresi: 3 gün -> ship_date = 2026-06-17
		# Üretim süresi: 7 gün -> prod_start_date = 2026-06-10
		with patch("erpnextkta.kta_mrp.mrp_engine.lead_time.resolve_shipping_lead_days", return_value=(3, "Address")), \
		     patch("erpnextkta.kta_mrp.mrp_engine.lead_time.resolve_production_lead_days", return_value=(7, "Item")):
			
			res = resolve_lead_time(
				delivery_date="2026-06-20",
				item_code="ITEM-001",
				customer="CUST-001",
				address="ADDR-001",
				settings=self.custom_settings,
			)
			self.assertIsInstance(res, LeadTimeResult)
			self.assertEqual(res.shipping_days, 3)
			self.assertEqual(res.production_days, 7)
			self.assertEqual(res.total_days, 10)
			self.assertEqual(str(res.ship_date), "2026-06-17")
			self.assertEqual(str(res.prod_start_date), "2026-06-10")
			self.assertEqual(res.shipping_source, "Address")
			self.assertEqual(res.production_source, "Item")


if __name__ == "__main__":
	unittest.main()
