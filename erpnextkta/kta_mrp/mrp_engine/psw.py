"""KTA MRP Merkezi PSW (Production Start Week) Talep Netleştirme Motoru.

İki eksenli (Two-axis) geriye doğru çizelgeleme:
- Satış Siparişleri (Sales Order): Teslim Tarihi - (Sevk Süresi + Üretim Süresi)
- Dahili Talepler (Manufacture Material Request): Termin Tarihi - Üretim Süresi
- Stok ve WIP (İş Emri) karşılama ve emniyet stoğu izolasyonu
- Müşteriye özel paketleme katları (Packing Multipliers)

Bu modül saf bir çekirdek servis olup sunum/rapor katmanından (HTML, JS, Chart)
tamamen bağımsızdır. Hem Production Start Week raporu hem de Kapasite Planlama
motoru (capacity.py) bu modülü kullanır.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import frappe
from dateutil.relativedelta import MO, relativedelta
from frappe import scrub
from frappe.utils import add_days, cint, flt, getdate

from erpnextkta.kta_mrp.mrp_engine.lead_time import (
	resolve_lead_time,
	resolve_production_lead_days,
)
from erpnextkta.kta_mrp.mrp_engine.settings import MrpSettings, get_mrp_settings


@dataclass
class NettedResult:
	"""Stok ve WIP netleştirme sonucu."""

	stock_covered: int = 0
	wip_covered: int = 0
	to_produce: Dict[str, int] = field(default_factory=dict)
	total_to_produce: int = 0


@dataclass
class PswResult:
	"""PSW motorunun döngü ve planlama sonucu."""

	periodic_ranges: List[Tuple[date, date]]
	period_labels: List[str]
	period_fieldnames: List[str]
	rows: List[Dict[str, Any]]
	item_week_demand: Dict[str, Dict[str, int]]
	item_backlog: Dict[str, int]
	summary: Dict[str, int]


def get_iso_week_label(date_val: Union[date, str]) -> str:
	"""Tarih nesnesini 'YYYY-Www' ISO hafta formatına çevirir."""
	if not date_val:
		return ""
	d = getdate(date_val)
	iso_year, iso_week, _ = d.isocalendar()
	return f"{iso_year}-W{iso_week:02d}"


def get_period_ranges(
	from_date_val: Union[date, str],
	to_date_val: Union[date, str],
	period_type: str = "Weekly",
) -> List[Tuple[date, date]]:
	"""Belirtilen tarih aralığını haftalık periyotlara böler."""
	from_d = getdate(from_date_val)
	to_d = getdate(to_date_val)

	ranges = []
	if period_type == "Weekly":
		# Pazartesiye hizala
		from_d = from_d + relativedelta(from_d, weekday=MO(-1))

	current = from_d
	while current <= to_d:
		period_end = add_days(current, 6)
		if period_end > to_d:
			period_end = to_d
		ranges.append((getdate(current), getdate(period_end)))
		current = add_days(period_end, 1)

	return ranges


def apply_stock_wip_netting(
	demands: Dict[str, int],
	stock: float,
	safety_stock: float,
	wip: float,
	period_labels: List[str],
	packing: float = 1.0,
) -> NettedResult:
	"""Stok, emniyet stoğu ve açık iş emirlerini (WIP) talepten düşer."""
	usable_stock = max(0.0, flt(stock) - flt(safety_stock))
	safety_deficit = max(0.0, flt(safety_stock) - flt(stock))
	usable_wip = max(0.0, flt(wip) - safety_deficit)

	stock_covered_total = 0
	wip_covered_total = 0
	to_produce_map = {}
	total_produce = 0

	for label in period_labels:
		demand = demands.get(label, 0)
		if demand <= 0:
			to_produce_map[label] = 0
			continue

		# 1. Stok karşılama
		stock_used = min(usable_stock, demand)
		usable_stock -= stock_used
		stock_covered_total += int(stock_used)

		rem_after_stock = demand - stock_used

		# 2. WIP karşılama
		wip_used = min(usable_wip, rem_after_stock)
		usable_wip -= wip_used
		wip_covered_total += int(wip_used)

		prod = rem_after_stock - wip_used

		# 3. Paketleme yuvarlaması
		if prod > 0 and packing > 1.0:
			prod = math.ceil(prod / packing) * packing

		prod_int = int(prod)
		to_produce_map[label] = prod_int
		total_produce += prod_int

	return NettedResult(
		stock_covered=stock_covered_total,
		wip_covered=wip_covered_total,
		to_produce=to_produce_map,
		total_to_produce=total_produce,
	)


def calculate_psw_demand(
	filters: Optional[Dict[str, Any]] = None,
	settings: Optional[MrpSettings] = None,
) -> PswResult:
	"""Satış Siparişleri ve Malzeme Taleplerinden geriye doğru çizelgelenmiş net ihtiyacı hesaplar.

	Args:
	  filters:
	    from_date, to_date, range, tree_type, tree_key, item_group,
	    group_by_item_only, warehouses
	  settings:
	    MrpSettings nesnesi (None ise KTA MRP Settings'den okunur)
	"""
	active_settings = settings or get_mrp_settings()
	f = frappe._dict(filters or {})

	today = date.today()
	from_date = getdate(f.from_date or date(today.year, 1, 1))
	to_date = getdate(f.to_date or date(today.year, 12, 31))
	range_type = f.range or "Weekly"
	tree_type = f.tree_type or "Müşteri"
	group_by_item_only = bool(cint(f.group_by_item_only or 0))
	item_group_filter = f.item_group

	# Periyotları oluştur
	periodic_ranges = get_period_ranges(from_date, to_date, range_type)
	period_labels = [get_iso_week_label(end) for _, end in periodic_ranges]
	period_fieldnames = [scrub(l) for l in period_labels]
	label_to_fieldname = {l: scrub(l) for l in period_labels}

	if not periodic_ranges:
		return PswResult(
			periodic_ranges=[],
			period_labels=[],
			period_fieldnames=[],
			rows=[],
			item_week_demand={},
			item_backlog={},
			summary={"total_to_produce": 0, "total_stock_covered": 0, "total_wip_covered": 0},
		)

	# 1. Ürün ve Müşteri Paketleme Meta Verilerini Topla
	all_items = frappe.get_all("Item", fields=["name", "item_group", "item_name"])
	item_group_map = {i.name: (i.item_group or "") for i in all_items}
	item_name_map = {i.name: (i.item_name or i.name) for i in all_items}

	packing_cache = {}
	packing_records = frappe.db.sql(
		"""
		SELECT parent as item_code, customer_name, custom_musteri_paketleme_miktari as packing
		FROM `tabItem Customer Detail`
		WHERE custom_musteri_paketleme_miktari > 1
	""",
		as_dict=True,
	)
	for pr in packing_records:
		packing_cache[(pr.item_code, pr.customer_name)] = flt(pr.packing)

	# 2. Stok, Emniyet Stoğu ve WIP Bakiyelerini Topla
	warehouses = f.get("warehouses")
	if warehouses:
		stock_data = frappe.db.sql(
			"""
			SELECT bin.item_code, SUM(bin.actual_qty) as total_qty
			FROM `tabBin` bin
			JOIN `tabWarehouse` w ON w.name = bin.warehouse
			WHERE bin.warehouse IN %s AND w.is_rejected_warehouse = 0
			GROUP BY bin.item_code
		""",
			[tuple(warehouses)],
			as_dict=True,
		)
	else:
		stock_data = frappe.db.sql(
			"""
			SELECT bin.item_code, SUM(bin.actual_qty) as total_qty
			FROM `tabBin` bin
			JOIN `tabWarehouse` w ON w.name = bin.warehouse
			WHERE w.is_rejected_warehouse = 0
			GROUP BY bin.item_code
		""",
			as_dict=True,
		)
	stock_map = {d.item_code: flt(d.total_qty or 0) for d in stock_data}

	safety_data = frappe.db.sql(
		"""
		SELECT parent as item_code, SUM(warehouse_reorder_level) as safety_stock
		FROM `tabItem Reorder`
		GROUP BY parent
	""",
		as_dict=True,
	)
	safety_map = {d.item_code: flt(d.safety_stock or 0) for d in safety_data}

	wip_data = frappe.db.sql(
		"""
		SELECT production_item as item_code, SUM(qty - produced_qty) as wip_qty
		FROM `tabWork Order`
		WHERE docstatus = 1
		  AND status IN ('In Process', 'Not Started')
		  AND qty > produced_qty
		GROUP BY production_item
	""",
		as_dict=True,
	)
	wip_map = {d.item_code: flt(d.wip_qty or 0) for d in wip_data}

	# 3. Satış Siparişleri Taleplerini Çek ve Geriye Doğru Çizelgele
	so_conditions = [
		"so.docstatus = 1",
		"so.status NOT IN ('Closed', 'Completed', 'Cancelled')",
		"soi.qty > soi.delivered_qty",
	]
	so_values = []

	if f.tree_key:
		if tree_type == "Müşteri":
			so_conditions.append("so.customer = %s")
			so_values.append(f.tree_key)
		elif tree_type == "Müşteri Grubu":
			so_conditions.append("so.customer_group = %s")
			so_values.append(f.tree_key)

	so_query = f"""
		SELECT
			so.name as sales_order,
			so.customer,
			so.customer_group,
			so.shipping_address_name,
			so.delivery_date,
			soi.item_code,
			soi.item_name,
			(soi.qty - soi.delivered_qty) as pending_qty
		FROM `tabSales Order Item` soi
		JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE {" AND ".join(so_conditions)}
	"""
	so_rows = frappe.db.sql(so_query, so_values, as_dict=True)

	weekly_demand_by_item = defaultdict(lambda: defaultdict(int))
	sales_order_demand_by_item = defaultdict(int)
	internal_demand_by_item = defaultdict(int)

	for row in so_rows:
		item_code = row.item_code
		if not item_code:
			continue
		item_group = item_group_map.get(item_code, "")
		if item_group_filter and item_group != item_group_filter:
			continue

		pending = int(row.pending_qty or 0)
		if pending <= 0:
			continue

		# İki eksenli lead time çözümlemesi
		delivery_d = row.delivery_date or today
		lt = resolve_lead_time(
			delivery_date=delivery_d,
			item_code=item_code,
			customer=row.customer,
			address=row.shipping_address_name,
			customer_group=row.customer_group,
			settings=active_settings,
		)

		prod_label = get_iso_week_label(lt.prod_start_date)

		tree_key = "Genel"
		if not group_by_item_only:
			if tree_type == "Müşteri Grubu":
				tree_key = row.customer_group or "Genel"
			else:
				tree_key = row.customer or "Genel"

		group_key = (
			None if group_by_item_only else tree_key,
			item_code,
			row.item_name or item_name_map.get(item_code, item_code),
			item_group,
		)

		weekly_demand_by_item[group_key][prod_label] += pending
		sales_order_demand_by_item[group_key] += pending

	# 4. Dahili Üretim Taleplerini (Manufacture Material Request) Ekle
	mr_query = """
		SELECT
			mr.name,
			mri.item_code,
			(mri.qty - mri.ordered_qty) as pending_qty,
			mr.schedule_date
		FROM `tabMaterial Request` mr
		JOIN `tabMaterial Request Item` mri ON mr.name = mri.parent
		WHERE mr.docstatus = 1
		  AND mr.material_request_type = 'Manufacture'
		  AND mr.status NOT IN ('Stopped', 'Cancelled', 'Transferred', 'Manufactured')
		  AND mri.qty > mri.ordered_qty
	"""
	mr_rows = frappe.db.sql(mr_query, as_dict=True)

	item_customer_cache = {}
	for row in mr_rows:
		item_code = row.item_code
		if not item_code:
			continue
		item_group = item_group_map.get(item_code, "")
		if item_group_filter and item_group != item_group_filter:
			continue

		pending = int(row.pending_qty or 0)
		if pending <= 0:
			continue

		if item_code not in item_customer_cache:
			cust = frappe.db.get_value("Item Customer Detail", {"parent": item_code}, "customer_name")
			item_customer_cache[item_code] = cust

		customer_name = item_customer_cache.get(item_code)

		# Dahili talepte sevk süresi yoktur; sadece dahili üretim süresi düşülür
		prod_days, _ = resolve_production_lead_days(
			item_code=item_code,
			customer=customer_name,
			settings=active_settings,
		)

		sched_date = getdate(row.schedule_date or today)
		prod_start = add_days(sched_date, -prod_days) if prod_days > 0 else sched_date
		prod_label = get_iso_week_label(prod_start)

		tree_key = customer_name or "Genel"
		if customer_name and tree_type == "Müşteri Grubu":
			c_group = frappe.db.get_value("Customer", customer_name, "customer_group")
			if c_group:
				tree_key = c_group

		group_key = (
			None if group_by_item_only else tree_key,
			item_code,
			item_name_map.get(item_code, item_code),
			item_group,
		)

		weekly_demand_by_item[group_key][prod_label] += pending
		internal_demand_by_item[group_key] += pending

	# 5. Stok, WIP ve Netleştirme Tüketimini Gerçekleştir
	item_rows = defaultdict(list)
	for group_key, week_map in weekly_demand_by_item.items():
		item_rows[group_key[1]].append((group_key, week_map))

	result_rows = []
	item_week_demand = defaultdict(lambda: defaultdict(int))
	item_backlog = defaultdict(int)

	total_all_produce = 0
	total_all_stock = 0
	total_all_wip = 0
	min_first_week_date = periodic_ranges[0][0]

	for item_code, rows_for_item in item_rows.items():
		item_stock = stock_map.get(item_code, 0.0)
		item_safety = safety_map.get(item_code, 0.0)
		item_wip = wip_map.get(item_code, 0.0)

		# Toplam talebi haftalara göre birleştir
		aggregated_week_demands = defaultdict(int)
		for _, week_map in rows_for_item:
			for w_label, val in week_map.items():
				aggregated_week_demands[w_label] += val

		# Tüm periyot etiketleri (ve periyot öncesi backlog haftaları)
		all_labels = list(period_labels)
		# Backlog veya ufuk dışı haftaları periyot başına ekle
		extra_labels = [l for l in aggregated_week_demands if l not in all_labels]
		extra_labels.sort()
		sorted_process_labels = extra_labels + all_labels

		# İlk genel netleştirme
		netted = apply_stock_wip_netting(
			demands=aggregated_week_demands,
			stock=item_stock,
			safety_stock=item_safety,
			wip=item_wip,
			period_labels=sorted_process_labels,
		)

		total_all_stock += netted.stock_covered
		total_all_wip += netted.wip_covered

		# Satır bazında dağıtım
		for (tree_key, _, item_name, item_group), week_map in rows_for_item:
			current_group_key = (
				None if group_by_item_only else tree_key,
				item_code,
				item_name,
				item_group,
			)
			customer_for_pack = tree_key if tree_key and tree_key != "Genel" else None
			packing = packing_cache.get((item_code, customer_for_pack), 1.0)

			# Bu müşteri/satır için netleştirme
			row_netted = apply_stock_wip_netting(
				demands=week_map,
				stock=item_stock,
				safety_stock=item_safety,
				wip=item_wip,
				period_labels=sorted_process_labels,
				packing=packing,
			)

			row_dict = {
				"item_group": item_group,
				"tree_key": tree_key or "Genel",
				"item_code": item_code,
				"item_name": item_name,
				"unit": "Adet",
				"indent": 1,
				"stock_covered": row_netted.stock_covered,
				"wip_covered": row_netted.wip_covered,
				"to_produce": row_netted.total_to_produce,
				"sales_order_demand": sales_order_demand_by_item.get(current_group_key, 0),
				"internal_demand": internal_demand_by_item.get(current_group_key, 0),
				"total": sum(week_map.values()),
			}

			# Haftalık sütun değerlerini ata
			for p_label in period_labels:
				f_name = label_to_fieldname[p_label]
				qty = row_netted.to_produce.get(p_label, 0)
				if qty > 0:
					row_dict[f_name] = qty
					item_week_demand[item_code][f_name] += qty

			# Periyot dışı / geçmiş backlog haftaları
			for ex_l in extra_labels:
				qty = row_netted.to_produce.get(ex_l, 0)
				if qty > 0:
					item_backlog[item_code] += qty

			total_all_produce += row_netted.total_to_produce

			if row_dict["total"] or row_dict["internal_demand"]:
				result_rows.append(row_dict)

	summary = {
		"total_to_produce": total_all_produce,
		"total_stock_covered": total_all_stock,
		"total_wip_covered": total_all_wip,
		"total_sales_order_demand": sum(sales_order_demand_by_item.values()),
		"total_internal_demand": sum(internal_demand_by_item.values()),
	}

	return PswResult(
		periodic_ranges=periodic_ranges,
		period_labels=period_labels,
		period_fieldnames=period_fieldnames,
		rows=result_rows,
		item_week_demand=dict(item_week_demand),
		item_backlog=dict(item_backlog),
		summary=summary,
	)
