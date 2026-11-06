"""Arz verileri: stok, açık PO teslimatları, varsayılan tedarikçi ve alış koşulları."""

from collections import defaultdict

import frappe
from frappe.utils import add_days, flt, getdate

from erpnextkta.kta_mrp.mrp_engine.weeks import clamp_to_first_week, week_key

from erpnextkta.kta_mrp.mrp_engine.settings import get_mrp_settings

INACTIVE_PO_STATUSES = ("Closed", "On Hold", "Completed", "Delivered")


def get_available_warehouses(warehouse_type=None):
	w_type = warehouse_type or get_mrp_settings().available_warehouse_type
	return frappe.get_all(
		"Warehouse",
		filters={"warehouse_type": w_type, "is_group": 0},
		pluck="name",
	)


def get_stock(item_codes):
	"""Kalem -> {actual, reserved}: sadece 'Kullanılabilir Stok' tipindeki depolardan."""
	warehouses = get_available_warehouses()
	if not item_codes or not warehouses:
		return {}
	rows = frappe.get_all(
		"Bin",
		filters={"item_code": ["in", item_codes], "warehouse": ["in", warehouses]},
		fields=["item_code", "sum(actual_qty) as actual", "sum(reserved_qty_for_production) as reserved"],
		group_by="item_code",
	)
	return {d.item_code: frappe._dict(actual=flt(d.actual), reserved=flt(d.reserved)) for d in rows}


VALID_DRAFT_PR_STATES = ("Yolda", "Antrepoda", "Gümrüklemede", "Mal Giriş", "Mal Girişe Hazır")


def build_open_po_query(item_codes):
	po = frappe.qb.DocType("Purchase Order")
	poi = frappe.qb.DocType("Purchase Order Item")
	return (
		frappe.qb.from_(poi)
		.inner_join(po)
		.on(poi.parent == po.name)
		.select(
			poi.name.as_("po_item_name"),
			poi.item_code,
			po.name.as_("po_name"),
			po.supplier,
			poi.schedule_date,
			poi.stock_qty,
			poi.received_qty,
			poi.conversion_factor,
		)
		.where(
			poi.item_code.isin(item_codes)
			& (po.docstatus == 1)
			& po.status.notin(INACTIVE_PO_STATUSES)
			& (poi.qty > poi.received_qty)
		)
	)


def get_open_po_rows(item_codes):
	return build_open_po_query(item_codes).run(as_dict=True)


def build_open_pr_query(item_codes=None):
	pr = frappe.qb.DocType("Purchase Receipt")
	pri = frappe.qb.DocType("Purchase Receipt Item")
	q = (
		frappe.qb.from_(pri)
		.inner_join(pr)
		.on(pri.parent == pr.name)
		.select(
			pri.name.as_("pr_item_name"),
			pr.name.as_("pr_name"),
			pr.supplier,
			pr.workflow_state,
			pr.posting_date,
			pr.yukleme_tarihi,
			pr.tahmini_varis_tarihi,
			pr.gumruge_gelis_tarihi,
			pr.custom_gumruk_islem_baslama_tarihi,
			pri.item_code,
			pri.stock_qty,
			pri.qty,
			pri.conversion_factor,
			pri.purchase_order,
			pri.purchase_order_item,
		)
		.where(
			(pr.docstatus == 0)
			& pr.workflow_state.isin(VALID_DRAFT_PR_STATES)
			& (pri.qty > 0)
		)
	)
	if item_codes and len(item_codes) <= 50:
		q = q.where(pri.item_code.isin(item_codes))
	return q


def get_open_pr_rows(item_codes=None):
	rows = build_open_pr_query(item_codes).run(as_dict=True)
	if item_codes and len(item_codes) > 50:
		item_set = set(item_codes)
		return [r for r in rows if r.item_code in item_set]
	return rows


def _categorize_pr_state(workflow_state: str) -> str:
	s = (workflow_state or "").lower()
	if "gümrük" in s or "gumruk" in s:
		return "gumruklemede"
	if "giriş" in s or "giris" in s:
		return "gumruklemede"
	if "antrepo" in s:
		return "antrepoda"
	if "yol" in s:
		return "yolda"
	return "antrepoda"


def resolve_pr_receipt_info(
	pr,
	po_schedule_date=None,
	default_transit_days=7,
	clearance_days=None,
):
	"""Taslak irsaliyenin durumuna göre gerçekçi varış ve kullanılabilirlik tarihini çözer.

	1. Gümrüklemede (Çekim / Millileştirme Sürecinde):
	   Dış ticaret/satınalma 'İşlem Başlat' demiştir.
	   gumruk_islem_baslama_tarihi + antrepo_clearance_days (varsayılan 2 gün) kesin varış tarihidir.
	2. Mal Giriş / Mal Girişe Hazır:
	   Malzeme fabrika kapısına ulaşmıştır. posting_date veya bugün.
	3. Yolda (In Transit):
	   Malzeme sevk halindedir.
	   - tahmini_varis_tarihi (Zorunlu ETA) birincil önceliktir.
	   - Beklenmeyen/istisnai eksiklik durumunda güvenlik ağı (Fallback):
	     a. po_schedule_date (PO üzerindeki termin tarihi)
	     b. yukleme_tarihi + 7 gün (standart nakliye süresi)
	     c. posting_date
	4. Antrepoda (Henüz İşlem Başlatılmamış Bekleme Havuzu):
	   Malzeme antrepoda beklemektedir. Henüz 'İşlem Başlat' denmediği için
	   kesin bir geliş tarihi yoktur. Sabit bir haftaya zorlanmaz (None döner),
	   böylece haftalık teslimat takvimine yapay olarak yığılmaz;
	   ancak breakdown'da 'antrepoda' rezervi olarak plancıya gösterilir.
	"""
	if clearance_days is None:
		clearance_days = get_mrp_settings().antrepo_clearance_days

	state = (getattr(pr, "workflow_state", None) or "").lower()

	# 1. GÜMRÜKLEMEDE (ÇEKİM/MİLLİLEŞTİRME İŞLEMİ BAŞLATILDI)
	if "gümrükleme" in state or "gumrukleme" in state:
		start_date = (
			getattr(pr, "custom_gumruk_islem_baslama_tarihi", None)
			or getattr(pr, "gumruk_beyanname_tarihi", None)
			or getattr(pr, "modified", None)
			or frappe.utils.today()
		)
		base_date = getdate(start_date)
		res_date = getdate(add_days(base_date, clearance_days)) if clearance_days > 0 else base_date
		label = f"Gümrüklemede (+{clearance_days}g)" if clearance_days > 0 else "Gümrüklemede"
		return res_date, False, label

	# 2. MAL GİRİŞİNDE (FABRİKAYA ULAŞTI)
	if "giriş" in state:
		base_date = getattr(pr, "posting_date", None) or frappe.utils.today()
		return getdate(base_date), False, "Fabrika Mal Girişi"

	# 3. YOLDA (IN TRANSIT)
	if "yol" in state:
		if getattr(pr, "tahmini_varis_tarihi", None):
			return getdate(pr.tahmini_varis_tarihi), False, "Tahmini Varış (ETA)"
		if po_schedule_date:
			return getdate(po_schedule_date), True, "PO Termini (ETA Eksik)"
		if getattr(pr, "yukleme_tarihi", None):
			transit_days = default_transit_days if default_transit_days is not None else 7
			res_date = getdate(add_days(pr.yukleme_tarihi, transit_days))
			return res_date, True, f"Tahmini Varış (+{transit_days}g Transit)"
		return (getdate(pr.posting_date) if getattr(pr, "posting_date", None) else None), True, "Kayıt Tarihi"

	# 4. ANTREPODA (HENÜZ İŞLEM BAŞLATILMAMIŞ BEKLEME HAVUZU)
	if "antrepo" in state:
		# Henüz çekim işlemi başlatılmadı; haftalık teslimata zorlanmaz
		return None, False, "Antrepoda Bekliyor (İşlem Başlatılmadı)"

	# 5. DİĞER DURUMLAR
	if getattr(pr, "tahmini_varis_tarihi", None):
		return getdate(pr.tahmini_varis_tarihi), False, "Tahmini Varış"
	if po_schedule_date:
		return getdate(po_schedule_date), False, "Termin Tarihi"
	return (getdate(pr.posting_date) if getattr(pr, "posting_date", None) else None), False, "Kayıt Tarihi"


def resolve_pr_receipt_date(pr, po_schedule_date=None, default_transit_days=None, clearance_days=None):
	"""Geriye dönük uyumluluk: Sadece çözümlenen tarihi döndürür."""
	date_val, _, _ = resolve_pr_receipt_info(pr, po_schedule_date, default_transit_days, clearance_days)
	return date_val


def get_open_supplies(item_codes, first_week):
	"""Kalem -> {hafta: stok biriminde bekleyen miktar} ve kırılım detayları.

	KTA Mal Giriş Süreci'ndeki taslak irsaliyeler (Antrepoda, Gümrüklemede, Yolda, Mal Giriş) ile
	açık satınalma siparişlerini (PO) uzlaştırır. Çifte sayımı engeller ve
	kullanıcının PO üzerindeki miktar düşürme hatalarını tolere eder.
	"""
	receipts = defaultdict(lambda: defaultdict(float))
	breakdown = defaultdict(
		lambda: frappe._dict(
			antrepoda=0.0,
			gumruklemede=0.0,
			yolda=0.0,
			po_kalan=0.0,
			total=0.0,
			details=[],
		)
	)
	if not item_codes:
		return receipts, breakdown

	po_rows = get_open_po_rows(item_codes)
	pr_rows = get_open_pr_rows(item_codes)

	pr_by_poi = defaultdict(list)
	for pr in pr_rows:
		if pr.purchase_order_item:
			pr_by_poi[pr.purchase_order_item].append(pr)
		else:
			pr_qty = flt(pr.stock_qty) or (flt(pr.qty) * flt(pr.conversion_factor or 1))
			pr_date, is_estimated, date_label = resolve_pr_receipt_info(pr, None)
			cat = _categorize_pr_state(pr.workflow_state)
			breakdown[pr.item_code][cat] += pr_qty
			breakdown[pr.item_code].total += pr_qty

			w = clamp_to_first_week(week_key(pr_date), first_week) if pr_date else None
			if pr_qty > 0 and pr_date:
				receipts[pr.item_code][w] += pr_qty

			breakdown[pr.item_code].details.append(
				frappe._dict(
					type="PR",
					name=pr.pr_name,
					supplier=pr.supplier,
					state=pr.workflow_state,
					qty=pr_qty,
					date=pr_date,
					week=w,
					date_label=date_label,
					is_estimated=is_estimated,
					loading_date=getattr(pr, "yukleme_tarihi", None),
					eta_date=getattr(pr, "tahmini_varis_tarihi", None),
					customs_date=getattr(pr, "gumruge_gelis_tarihi", None),
					clearance_start_date=getattr(pr, "custom_gumruk_islem_baslama_tarihi", None),
				)
			)

	handled_poi_names = set()
	for po in po_rows:
		poi_name = po.po_item_name
		handled_poi_names.add(poi_name)
		factor = flt(po.conversion_factor or 1)
		po_pending = max(0.0, flt(po.stock_qty) - flt(po.received_qty) * factor)

		linked_prs = pr_by_poi.get(poi_name, [])
		total_pr_qty = 0.0

		for pr in linked_prs:
			pr_qty = flt(pr.stock_qty) or (flt(pr.qty) * flt(pr.conversion_factor or 1))
			if pr_qty <= 0:
				continue
			total_pr_qty += pr_qty
			pr_date, is_estimated, date_label = resolve_pr_receipt_info(pr, po.schedule_date)
			cat = _categorize_pr_state(pr.workflow_state)
			breakdown[pr.item_code][cat] += pr_qty
			breakdown[pr.item_code].total += pr_qty

			w = clamp_to_first_week(week_key(pr_date), first_week) if pr_date else None
			if pr_date:
				receipts[pr.item_code][w] += pr_qty

			breakdown[pr.item_code].details.append(
				frappe._dict(
					type="PR",
					name=pr.pr_name,
					po_name=po.po_name,
					supplier=pr.supplier or po.supplier,
					state=pr.workflow_state,
					qty=pr_qty,
					date=pr_date,
					week=w,
					date_label=date_label,
					is_estimated=is_estimated,
					loading_date=getattr(pr, "yukleme_tarihi", None),
					eta_date=getattr(pr, "tahmini_varis_tarihi", None),
					customs_date=getattr(pr, "gumruge_gelis_tarihi", None),
					clearance_start_date=getattr(pr, "custom_gumruk_islem_baslama_tarihi", None),
				)
			)

		remaining_po = max(0.0, po_pending - total_pr_qty)
		if remaining_po > 0 and po.schedule_date:
			w = clamp_to_first_week(week_key(po.schedule_date), first_week)
			receipts[po.item_code][w] += remaining_po
			breakdown[po.item_code].po_kalan += remaining_po
			breakdown[po.item_code].total += remaining_po
			breakdown[po.item_code].details.append(
				frappe._dict(
					type="PO",
					name=po.po_name,
					supplier=po.supplier,
					state="Açık Sipariş",
					qty=remaining_po,
					date=po.schedule_date,
					week=w,
					date_label="Termin (PO)",
					is_estimated=False,
					loading_date=None,
					eta_date=None,
					customs_date=None,
					clearance_start_date=None,
				)
			)

	# PO'su kapalı veya listede olmayan ancak taslak PR'ı bulunan kalemler
	for poi_name, pr_list in pr_by_poi.items():
		if poi_name not in handled_poi_names:
			for pr in pr_list:
				pr_qty = flt(pr.stock_qty) or (flt(pr.qty) * flt(pr.conversion_factor or 1))
				pr_date, is_estimated, date_label = resolve_pr_receipt_info(pr, None)
				cat = _categorize_pr_state(pr.workflow_state)
				breakdown[pr.item_code][cat] += pr_qty
				breakdown[pr.item_code].total += pr_qty

				w = clamp_to_first_week(week_key(pr_date), first_week) if pr_date else None
				if pr_qty > 0 and pr_date:
					receipts[pr.item_code][w] += pr_qty

				breakdown[pr.item_code].details.append(
					frappe._dict(
						type="PR",
						name=pr.pr_name,
						supplier=pr.supplier,
						state=pr.workflow_state,
						qty=pr_qty,
						date=pr_date,
						week=w,
						date_label=date_label,
						is_estimated=is_estimated,
						loading_date=getattr(pr, "yukleme_tarihi", None),
						eta_date=getattr(pr, "tahmini_varis_tarihi", None),
						customs_date=getattr(pr, "gumruge_gelis_tarihi", None),
						clearance_start_date=getattr(pr, "custom_gumruk_islem_baslama_tarihi", None),
					)
				)

	return receipts, breakdown


def get_open_po_receipts(item_codes, first_week):
	"""Kalem -> {hafta: stok biriminde bekleyen miktar}. Gecikmiş PO'lar ilk haftaya yazılır."""
	receipts, _ = get_open_supplies(item_codes, first_week)
	return receipts


def get_default_suppliers(item_codes):
	"""Kalem -> varsayılan tedarikçi (Item Default), tek sorguda."""
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"Item Default",
		filters={"parent": ["in", item_codes], "default_supplier": ["is", "set"]},
		fields=["parent", "default_supplier"],
	)
	supplier_map = {}
	for d in rows:
		supplier_map.setdefault(d.parent, d.default_supplier)
	return supplier_map


def get_item_sourcing_configs(item_codes):
	"""Kalem -> {strategy, default_supplier, suppliers: [{supplier, quota_share, moq, pack, price, currency, lead_time_days, idx, is_default}]}.

	Kalem kartındaki custom_sourcing_strategy ve Item Supplier tablosundaki kotaları / fiyat listesindeki şartları derler.
	"""
	if not item_codes:
		return {}

	item_rows = frappe.get_all(
		"Item",
		filters={"name": ["in", item_codes]},
		fields=["name", "custom_sourcing_strategy"],
	)
	strategy_map = {
		d.name: (d.custom_sourcing_strategy or "Varsayılan Tedarikçi (%100)")
		for d in item_rows
	}

	default_sup_map = get_default_suppliers(item_codes)

	supplier_rows = frappe.get_all(
		"Item Supplier",
		filters={"parent": ["in", item_codes]},
		fields=["parent", "supplier", "custom_quota_share", "custom_moq", "custom_min_pak_mik", "idx"],
		order_by="parent, idx asc",
	)
	item_suppliers_map = defaultdict(list)
	for s in supplier_rows:
		item_suppliers_map[s.parent].append(s)

	prices = frappe.get_all(
		"Item Price",
		filters={"item_code": ["in", item_codes], "buying": 1},
		fields=[
			"item_code",
			"supplier",
			"price_list_rate",
			"currency",
			"lead_time_days",
			"custom_minimum_order_quantity",
			"custom_minimum_paketleme_miktari",
		],
		order_by="valid_from desc, creation desc",
	)
	price_map = {}
	for p in prices:
		key = (p.item_code, p.supplier)
		if key not in price_map:
			price_map[key] = p

	configs = {}
	for code in item_codes:
		def_sup = default_sup_map.get(code)
		sup_entries = item_suppliers_map.get(code) or []
		strategy = strategy_map.get(code, "Varsayılan Tedarikçi (%100)")

		if not sup_entries and def_sup:
			sup_entries = [frappe._dict(parent=code, supplier=def_sup, custom_quota_share=100.0, custom_moq=0, custom_min_pak_mik=0, idx=1)]

		compiled_suppliers = []
		for s in sup_entries:
			sup_name = s.supplier
			p_rec = price_map.get((code, sup_name))
			moq = flt(s.custom_moq) or (flt(p_rec.custom_minimum_order_quantity) if p_rec else 0.0)
			pack = flt(s.custom_min_pak_mik) or (flt(p_rec.custom_minimum_paketleme_miktari) if p_rec else 1.0) or 1.0
			price = flt(p_rec.price_list_rate) if p_rec else 0.0
			currency = p_rec.currency if p_rec else None
			lead_time_days = int(p_rec.lead_time_days or 0) if p_rec else 0
			quota_share = flt(s.custom_quota_share) or 0.0

			compiled_suppliers.append(
				frappe._dict(
					supplier=sup_name,
					quota_share=quota_share,
					moq=moq,
					pack=pack,
					price=price,
					currency=currency,
					lead_time_days=lead_time_days,
					idx=s.get("idx", 1),
					is_default=(sup_name == def_sup),
				)
			)

		if len(compiled_suppliers) <= 1:
			strategy = "Varsayılan Tedarikçi (%100)"
			if compiled_suppliers:
				compiled_suppliers[0].quota_share = 100.0

		configs[code] = frappe._dict(
			strategy=strategy,
			default_supplier=def_sup,
			suppliers=compiled_suppliers,
		)

	return configs


def get_buying_terms(item_codes_or_suppliers, default_supplier_map=None):
	"""Kalem -> {moq, pack, price, currency, lead_time_days}.

	Item Price (buying=1) tablosundan okunur.
	Varsayılan tedarikçisi eşleşen kayıt önceliklidir; yoksa en güncel alış fiyatı alınır.
	"""
	if not item_codes_or_suppliers:
		return {}
	if isinstance(item_codes_or_suppliers, dict):
		supplier_map = item_codes_or_suppliers
		item_codes = list(supplier_map.keys())
	else:
		item_codes = list(item_codes_or_suppliers)
		supplier_map = default_supplier_map or {}

	prices = frappe.get_all(
		"Item Price",
		filters={
			"item_code": ["in", item_codes],
			"buying": 1,
		},
		fields=[
			"item_code",
			"supplier",
			"price_list_rate",
			"currency",
			"lead_time_days",
			"custom_minimum_order_quantity",
			"custom_minimum_paketleme_miktari",
		],
		order_by="valid_from desc, creation desc",
	)
	terms = {}
	for d in prices:
		if d.item_code not in terms and d.supplier and supplier_map.get(d.item_code) == d.supplier:
			terms[d.item_code] = _to_terms(d)
	for d in prices:
		if d.item_code not in terms:
			terms[d.item_code] = _to_terms(d)
	return terms


def _to_terms(price):
	return frappe._dict(
		moq=flt(price.custom_minimum_order_quantity),
		pack=flt(price.custom_minimum_paketleme_miktari) or 1,
		price=flt(price.price_list_rate),
		currency=price.currency,
		lead_time_days=int(price.lead_time_days or 0),
	)

