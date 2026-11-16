from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, fmt_money

from erpnextkta.kta_mrp.mrp_engine.service import get_material_requirements
from erpnextkta.kta_mrp.mrp_engine.weeks import week_label

WEEKLY_VIEWS = {
	"Önerilen Sipariş": "planned_orders",
	"Net İhtiyaç": "net",
	"Brüt İhtiyaç": "gross",
	"PO Teslimatları": "receipts",
	"Projeksiyon Bakiye": "projected",
}
from erpnextkta.kta_mrp.mrp_engine.settings import get_mrp_settings

DEFAULT_WEEKLY_VIEW = "Önerilen Sipariş"
GROUP_ONLY_MATERIAL = "Sadece Hammadde"
PRECISION = 3


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("from_date"):
		from erpnextkta.kta_mrp.mrp_engine.capacity import get_monday_of_current_week
		filters.from_date = str(get_monday_of_current_week())
	tree = filters.get("group_by") != GROUP_ONLY_MATERIAL
	if "include_po" in filters and filters.get("include_po") is not None:
		include_po = cint(filters.get("include_po"))
	else:
		include_po = cint(get_mrp_settings().default_include_po)
	result = get_material_requirements(filters, include_po=include_po)
	try:
		frappe.cache().set_value(f"mrp_result_{frappe.session.user}", result, expires_in_sec=1800)
	except Exception:
		pass
	materials = sort_materials(filter_materials(result.materials.values(), filters))
	columns = get_columns(result.weeks, tree)
	data = get_data(materials, result.pegging, get_weekly_view(filters), tree)
	return columns, data, None, None


def get_weekly_view(filters):
	return WEEKLY_VIEWS.get(filters.get("weekly_view"), WEEKLY_VIEWS[DEFAULT_WEEKLY_VIEW])


# ---------------------------------------------------------------- filtreleme


def filter_materials(materials, filters):
	return [m for m in materials if matches_filters(m, filters)]


def matches_filters(material, filters):
	if filters.get("supplier") and material.supplier != filters.supplier:
		return False
	if filters.get("hammadde") and material.item_code != filters.hammadde:
		return False
	return not (cint(filters.get("only_shortages")) and material.netting.net_total <= 0)


def sort_materials(materials):
	"""En acil eksik en üstte; eksiği olmayanlar sonda."""
	return sorted(materials, key=lambda m: (m.netting.coverage_weeks, m.item_code))


# ---------------------------------------------------------------- kolonlar


def get_columns(weeks, tree):
	return get_identity_columns(tree) + get_summary_columns() + get_week_columns(weeks)


def get_identity_columns(tree):
	columns = [
		column("hammadde", _("Hammadde / Ürün") if tree else _("Hammadde"), "Link", 170, "Item"),
		column("urun_aciklamasi", _("Ürün Açıklaması"), "Data", 200),
	]
	if tree:
		columns += [column("bom", _("BOM"), "Link", 130, "BOM"), column("musteri_grubu", _("Müşteri Grubu"), "Data", 120)]
	return columns + [
		column("uom", _("Birim"), "Link", 70, "UOM"),
		column("varsayilan_tedarikci", _("Varsayılan Tedarikçi"), "Link", 150, "Supplier"),
	]


def get_summary_columns():
	return [
		column("stok", _("Stok"), "Float", 100),
		column("rezerve_stok", _("Rezerve Stok"), "Float", 110),
		column("serbest_stok", _("Serbest Stok"), "Float", 110),
		column("po_teslimat", _("Açık PO"), "Float", 100),
		column("brut_ihtiyac", _("Brüt İhtiyaç"), "Float", 110),
		column("net_ihtiyac", _("Net İhtiyaç"), "Float", 110),
		column("onerilen_siparis", _("Önerilen Sipariş"), "Float", 130),
		column("ilk_eksik_hafta", _("İlk Eksik Hafta"), "Data", 120),
		column("kapsama_hafta", _("Kapsama (Hafta)"), "Int", 120),
		column("fazla_po_miktari", _("Fazla PO Miktarı"), "Float", 130),
		column("birim_fiyat", _("Birim Fiyat"), "Currency", 110, "para_birimi"),
		column("para_birimi", _("Para Birimi"), "Link", 90, "Currency"),
		column("onerilen_siparis_tutari", _("Önerilen Sipariş Tutarı"), "Currency", 170, "para_birimi"),
	]


def get_week_columns(weeks):
	return [column(week, week_label(week), "Float", 100) for week in weeks]


def column(fieldname, label, fieldtype, width, options=None):
	col = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "width": width}
	if options:
		col["options"] = options
	return col


# ---------------------------------------------------------------- satırlar


def get_data(materials, pegging, view, tree):
	children = group_pegging(pegging) if tree else {}
	data = []
	for material in materials:
		data.append(get_material_row(material, view, tree))
		if tree and material.netting.receipts_total > 0:
			data.append(get_po_receipt_row(material, material.netting.weeks))
		data += [get_pegging_row(p, material.uom) for p in children.get(material.item_code, [])]
	return data


def group_pegging(pegging):
	grouped = defaultdict(list)
	for p in sorted(pegging, key=lambda p: -p.total):
		grouped[p.material].append(p)
	return grouped


def get_po_receipt_row(material, weeks):
	netting = material.netting
	return {
		"hammadde": _("Açık PO Girişleri"),
		"parent_item": material.item_code,
		"urun_aciklamasi": _("Tedarikçiden beklenen açık siparişler"),
		"uom": material.uom,
		"varsayilan_tedarikci": material.supplier,
		"po_teslimat": round(netting.receipts_total, PRECISION),
		"indent": 1,
		"is_po_row": 1,
		**round_weeks(netting.receipts, weeks),
	}


def get_week_details(netting):
	details = {}
	for w in netting.weeks:
		g = netting.gross.get(w, 0)
		r = netting.receipts.get(w, 0)
		n = netting.net.get(w, 0)
		o = netting.planned_orders.get(w, 0)
		p = netting.projected.get(w, 0)
		if g or r or n or o or p != 0:
			details[w] = {
				"gross": round(g, PRECISION),
				"po": round(r, PRECISION),
				"net": round(n, PRECISION),
				"order": round(o, PRECISION),
				"projected": round(p, PRECISION),
			}
	return details


def get_material_row(material, view, tree):
	netting = material.netting
	row = {
		"hammadde": material.item_code,
		"urun_aciklamasi": material.item_name,
		"uom": material.uom,
		"varsayilan_tedarikci": material.supplier,
		"moq": material.moq,
		"pack": material.pack,
		"lead_time": material.lead_time_days,
		**get_stock_values(material),
		**get_result_values(netting),
		**get_amount_values(material),
		**round_weeks(getattr(netting, view), netting.weeks),
		"_week_details": get_week_details(netting),
	}
	if tree:
		row["indent"] = 0
	return row


def get_stock_values(material):
	return {
		"stok": round(material.actual, PRECISION),
		"rezerve_stok": round(material.reserved, PRECISION),
		"serbest_stok": round(material.free_stock, PRECISION),
	}


def get_result_values(netting):
	first = netting.first_shortage_week
	return {
		"po_teslimat": round(netting.receipts_total, PRECISION),
		"brut_ihtiyac": round(netting.gross_total, PRECISION),
		"net_ihtiyac": round(netting.net_total, PRECISION),
		"onerilen_siparis": round(netting.planned_order_total, PRECISION),
		"ilk_eksik_hafta": week_label(first) if first else None,
		"ilk_eksik_sira": netting.coverage_weeks if first else None,
		"kapsama_hafta": netting.coverage_weeks,
		"fazla_po_miktari": round(netting.surplus_po, PRECISION),
	}


def get_amount_values(material):
	if not material.price:
		return {"para_birimi": material.currency}
	return {
		"birim_fiyat": material.price,
		"para_birimi": material.currency,
		"onerilen_siparis_tutari": round(material.order_amount, 2),
	}


def get_pegging_row(pegging, uom):
	return {
		"hammadde": pegging.finished_item,
		"urun_aciklamasi": pegging.item_name,
		"bom": pegging.bom,
		"musteri_grubu": pegging.customer_group,
		"uom": uom,
		"brut_ihtiyac": round(pegging.total, PRECISION),
		"indent": 1,
		**round_weeks(pegging.weeks, pegging.weeks),
	}


def round_weeks(values, weeks):
	return {week: round(values.get(week, 0), PRECISION) for week in weeks}


# ---------------------------------------------------------------- özet ve grafik


def get_summary_cards(materials, include_po=True):
	urgent_weeks = get_mrp_settings().urgent_shortage_weeks
	shortages = [m for m in materials if m.netting.net_total > 0]
	urgent = [m for m in shortages if m.netting.coverage_weeks < urgent_weeks]
	cards = []
	if not include_po:
		cards.append({
			"value": _("Kapalı"),
			"label": _("Açık PO Teslimatları (Ham İhtiyaç Modu)"),
			"indicator": "Orange",
		})
	cards += [
		{"value": len(materials), "label": _("Toplam Kalem"), "indicator": "Blue"},
		{"value": len(shortages), "label": _("Eksik Kalem"), "indicator": "Red"},
		{"value": len(urgent), "label": _("{0} Hafta İçinde Eksik").format(urgent_weeks), "indicator": "Orange"},
		*get_amount_cards(materials),
	]
	return cards


def get_amount_cards(materials):
	"""Para birimi başına ayrı toplam; kur çevrimi yapılmaz."""
	totals, unpriced = defaultdict(float), 0
	for m in materials:
		if not m.netting.planned_order_total:
			continue
		if m.price and m.currency:
			totals[m.currency] += m.order_amount
		else:
			unpriced += 1
	cards = [amount_card(currency, total) for currency, total in sorted(totals.items())]
	return [*cards, {"value": unpriced, "label": _("Fiyatı Olmayan Kalem"), "indicator": "Purple"}]


def amount_card(currency, total):
	return {
		"value": fmt_money(total, currency=currency),
		"label": _("Önerilen Sipariş Tutarı ({0})").format(currency),
		"indicator": "Green",
	}


# ---------------------------------------------------------------- dialog API


@frappe.whitelist()
def get_week_netting_dialog(item_code, week, from_date=None, to_date=None, include_po=1):
	from frappe.utils import flt, today
	from erpnextkta.kta_mrp.mrp_engine.supply import INACTIVE_PO_STATUSES
	from erpnextkta.kta_mrp.mrp_engine.weeks import clamp_to_first_week, week_key

	include_po = cint(include_po)
	cache_key = f"mrp_result_{frappe.session.user}"
	res = None
	try:
		res = frappe.cache().get_value(cache_key)
	except Exception:
		pass

	if not res or item_code not in res.materials:
		from erpnextkta.kta_mrp.mrp_engine.capacity import get_monday_of_current_week
		filters = {"from_date": from_date or str(get_monday_of_current_week()), "to_date": to_date}
		res = get_material_requirements(filters, include_po=include_po)
		try:
			frappe.cache().set_value(cache_key, res, expires_in_sec=1800)
		except Exception:
			pass

	mat = res.materials.get(item_code)
	if not mat:
		return {"error": _("Hammadde bulunamadı.")}

	# Matching demands (Pegging)
	demands = [
		{
			"finished_item": p.finished_item,
			"item_name": p.item_name,
			"bom": p.bom,
			"customer_group": p.customer_group,
			"qty": p.weeks.get(week, 0),
		}
		for p in res.pegging
		if p.material == item_code and p.weeks.get(week, 0) > 0
	]

	# Matching open POs
	pos = []
	if include_po and res.weeks:
		first_week = res.weeks[0]
		po = frappe.qb.DocType("Purchase Order")
		poi = frappe.qb.DocType("Purchase Order Item")
		rows = (
			frappe.qb.from_(poi)
			.inner_join(po)
			.on(poi.parent == po.name)
			.select(poi.parent.as_("po_name"), po.supplier, poi.schedule_date, poi.stock_qty, poi.received_qty, poi.conversion_factor)
			.where(
				(poi.item_code == item_code)
				& (po.docstatus == 1)
				& po.status.notin(INACTIVE_PO_STATUSES)
				& (poi.qty > poi.received_qty)
			)
		).run(as_dict=True)

		for d in rows:
			pending = flt(d.stock_qty) - flt(d.received_qty) * flt(d.conversion_factor or 1)
			if pending <= 0 or not d.schedule_date:
				continue
			wk = clamp_to_first_week(week_key(d.schedule_date), first_week)
			if wk == week:
				pos.append({
					"po_name": d.po_name,
					"supplier": d.supplier,
					"schedule_date": str(d.schedule_date),
					"pending": pending,
				})

	# Balance calculation up to this week
	balance_before = mat.free_stock
	for w in res.weeks:
		if w == week:
			break
		g = mat.netting.gross.get(w, 0)
		r = mat.netting.receipts.get(w, 0)
		o = mat.netting.planned_orders.get(w, 0)
		balance_before = balance_before + r + o - g

	gross = mat.netting.gross.get(week, 0)
	receipts = mat.netting.receipts.get(week, 0)
	net = mat.netting.net.get(week, 0)
	order = mat.netting.planned_orders.get(week, 0)
	projected = mat.netting.projected.get(week, 0)

	return {
		"item_code": mat.item_code,
		"item_name": mat.item_name,
		"uom": mat.uom,
		"supplier": mat.supplier,
		"moq": mat.moq,
		"pack": mat.pack,
		"lead_time": mat.lead_time_days,
		"actual": mat.actual,
		"reserved": mat.reserved,
		"free_stock": mat.free_stock,
		"week": week,
		"week_label": week_label(week),
		"balance_before": balance_before,
		"gross": gross,
		"receipts": receipts,
		"net": net,
		"order": order,
		"projected": projected,
		"include_po": include_po,
		"pos": pos,
		"demands": demands,
	}