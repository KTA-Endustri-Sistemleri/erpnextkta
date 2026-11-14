"""KTA MRP Merkezi Lead Time Çözümleme Motoru.

İki eksenli (Two-axis) SAP standardı lead time mimarisi:
1. Üretim Süresi ($T_{\\text{prod}}$):
   "Ne üretildiği" ile ilgilidir. Fabrika içi imalat süresidir.
   Kademeli Çözümleme Hiyerarşisi:
     Item Customer Detail.custom_production_time_days
       -> Item.custom_manufacturing_lead_days
       -> KTA MRP Settings.default_production_time_days (14 gün)
   NOT: Item.lead_time_days Purchasing sekmesinde olup hammadde tedarik süresidir;
   asla dahili üretim süresi olarak kullanılmaz.

2. Sevk / Transit Süresi ($T_{\\text{transit}}$):
   "Nereye gittiği" (Coğrafya/Müşteri/Tesis) ile ilgilidir.
   Kademeli Çözümleme Hiyerarşisi:
     Address.custom_shipping_lead_days (Tesis/Plant adresi)
       -> Customer.custom_shipping_lead_days
       -> Customer Group.custom_shipping_lead_days
       -> KTA MRP Settings.default_delivery_time_days (2 gün)

3. Geriye Doğru Çizelgeleme (Backward Scheduling):
   ship_date = delivery_date - shipping_days
   prod_start_date = ship_date - production_days
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple, Union

import frappe
from frappe.utils import add_days, cint, getdate

from erpnextkta.kta_mrp.mrp_engine.settings import MrpSettings, get_mrp_settings


@dataclass
class LeadTimeResult:
	"""İki eksenli lead time çözümleme sonucu."""

	production_days: int
	shipping_days: int
	total_days: int
	ship_date: date
	prod_start_date: date
	shipping_source: str
	production_source: str


def resolve_shipping_lead_days(
	address: Optional[str] = None,
	customer: Optional[str] = None,
	customer_group: Optional[str] = None,
	settings: Optional[MrpSettings] = None,
) -> Tuple[int, str]:
	"""Sevk / Transit süresini kademeli hiyerarşiye göre çözer.

	Hiyerarşi:
	  1. Address.custom_shipping_lead_days (Müşteri Teslim Tesisi / Plant)
	  2. Customer.custom_shipping_lead_days (Müşteri Genel Varsayılanı)
	  3. Customer Group.custom_shipping_lead_days (Müşteri Grubu)
	  4. KTA MRP Settings.default_delivery_time_days (Merkezi Güvenlik Ağı, varsayılan 2 gün)

	Returns:
	  (shipping_days: int, source: str)
	"""
	active_settings = settings or get_mrp_settings()

	# 1. Address kademesi (Plant)
	if address:
		try:
			val = frappe.db.get_value("Address", address, "custom_shipping_lead_days")
			if cint(val or 0) > 0:
				return cint(val), "Address"
		except Exception:
			pass

	# 2. Customer kademesi
	if customer:
		try:
			val = frappe.db.get_value("Customer", customer, "custom_shipping_lead_days")
			if cint(val or 0) > 0:
				return cint(val), "Customer"
			if not customer_group:
				customer_group = frappe.db.get_value("Customer", customer, "customer_group")
		except Exception:
			pass

	# 3. Customer Group kademesi
	if customer_group:
		try:
			val = frappe.db.get_value("Customer Group", customer_group, "custom_shipping_lead_days")
			if cint(val or 0) > 0:
				return cint(val), "Customer Group"
		except Exception:
			pass

	# 4. KTA MRP Settings fallback
	fallback = active_settings.default_delivery_time_days if active_settings else 2
	return max(cint(fallback or 2), 0), "Default Settings"


def resolve_production_lead_days(
	item_code: str,
	customer: Optional[str] = None,
	settings: Optional[MrpSettings] = None,
) -> Tuple[int, str]:
	"""Dahili fabrika üretim süresini kademeli hiyerarşiye göre çözer.

	Hiyerarşi:
	  1. Item Customer Detail.custom_production_time_days (Müşteriye özel süre)
	  2. Item.custom_manufacturing_lead_days (Ürün genel fabrika üretim süresi)
	  3. KTA MRP Settings.default_production_time_days (Merkezi Güvenlik Ağı, varsayılan 14 gün)

	NOT: Item.lead_time_days Purchasing sekmesinde olup hammadde satınalma süresidir,
	asla dahili üretim süresi olarak kullanılmaz.

	Returns:
	  (production_days: int, source: str)
	"""
	active_settings = settings or get_mrp_settings()

	# 1. Müşteriye özel üretim süresi (Item Customer Detail child tablosu)
	if customer and item_code:
		try:
			val = frappe.db.get_value(
				"Item Customer Detail",
				{"parent": item_code, "customer_name": customer},
				"custom_production_time_days",
			)
			if cint(val or 0) > 0:
				return cint(val), "Item Customer Detail"
		except Exception:
			pass

	# 2. Ürün genel fabrika üretim süresi
	if item_code:
		try:
			val = frappe.db.get_value("Item", item_code, "custom_manufacturing_lead_days")
			if cint(val or 0) > 0:
				return cint(val), "Item"
		except Exception:
			pass

	# 3. KTA MRP Settings fallback
	fallback = active_settings.default_production_time_days if active_settings else 14
	return max(cint(fallback or 14), 0), "Default Settings"


def resolve_lead_time(
	delivery_date: Union[date, str],
	item_code: str,
	customer: Optional[str] = None,
	address: Optional[str] = None,
	customer_group: Optional[str] = None,
	settings: Optional[MrpSettings] = None,
) -> LeadTimeResult:
	"""Teslim tarihi, ürün ve müşteri/adres bilgisine göre geriye doğru çizelgeleme yapar.

	Backward Scheduling:
	  ship_date = delivery_date - shipping_days
	  prod_start_date = ship_date - production_days
	"""
	parsed_delivery_date = getdate(delivery_date)
	active_settings = settings or get_mrp_settings()

	shipping_days, shipping_source = resolve_shipping_lead_days(
		address=address,
		customer=customer,
		customer_group=customer_group,
		settings=active_settings,
	)

	production_days, production_source = resolve_production_lead_days(
		item_code=item_code,
		customer=customer,
		settings=active_settings,
	)

	total_days = shipping_days + production_days
	ship_date = getdate(add_days(parsed_delivery_date, -shipping_days))
	prod_start_date = getdate(add_days(ship_date, -production_days))

	return LeadTimeResult(
		production_days=production_days,
		shipping_days=shipping_days,
		total_days=total_days,
		ship_date=ship_date,
		prod_start_date=prod_start_date,
		shipping_source=shipping_source,
		production_source=production_source,
	)
