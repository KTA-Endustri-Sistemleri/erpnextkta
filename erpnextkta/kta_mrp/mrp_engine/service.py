"""Malzeme ihtiyaç servisi: raporların ortak giriş noktası.

- get_gross_requirements(): sadece brüt ihtiyaç + bitmiş ürün kırılımı (MRP Analysis)
- get_material_requirements(): stok, PO ve lot sizing ile netleştirilmiş ihtiyaç
  (Material Requirement, Recommended Purchase Orders)
"""

from collections import defaultdict
from dataclasses import dataclass, field
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, today

from erpnextkta.kta_mrp.mrp_engine import bom, demand, supply
from erpnextkta.kta_mrp.mrp_engine.netting import NettingResult, net_material
from erpnextkta.kta_mrp.mrp_engine.settings import get_mrp_settings, resolve_mrp_settings
from erpnextkta.kta_mrp.mrp_engine.weeks import clamp_to_first_week, current_week_key, week_key, week_label


@dataclass
class Pegging:
	material: str
	finished_item: str
	bom: str
	item_name: str
	customer_group: str
	weeks: dict

	@property
	def total(self):
		return sum(self.weeks.values())


@dataclass
class GrossRequirements:
	weeks: list
	gross: dict
	uoms: dict
	pegging: list = field(default_factory=list)


@dataclass
class MaterialRequirement:
	item_code: str
	item_name: str
	uom: str
	supplier: str
	actual: float
	reserved: float
	netting: NettingResult
	supply_breakdown: dict = field(default_factory=dict)
	moq: float = 0
	pack: float = 1
	price: float = 0
	currency: str | None = None
	lead_time_days: int = 0
	sourcing_strategy: str = "Varsayılan Tedarikçi (%100)"
	suppliers_quota: list = field(default_factory=list)
	planned_orders_by_supplier: dict = field(default_factory=dict)

	@property
	def free_stock(self):
		return self.actual - self.reserved

	@property
	def order_amount(self):
		if self.planned_orders_by_supplier and self.suppliers_quota:
			sup_price_map = {
				s.get("supplier"): flt(s.get("price"))
				for s in self.suppliers_quota
				if flt(s.get("price")) > 0
			}
			total = 0.0
			for sup, wk_orders in self.planned_orders_by_supplier.items():
				p = sup_price_map.get(sup, self.price)
				total += sum(wk_orders.values()) * p
			return total
		return self.netting.planned_order_total * self.price


@dataclass
class MaterialRequirementResult:
	weeks: list
	materials: dict  # {hammadde: MaterialRequirement}
	pegging: list = field(default_factory=list)


def get_gross_requirements(filters) -> GrossRequirements:
	plan = demand.get_production_plan(filters)
	explosion = bom.explode(plan)
	return GrossRequirements(
		weeks=plan.weeks,
		gross=explosion.gross,
		uoms=explosion.uoms,
		pegging=build_pegging(explosion.pegging),
	)


def build_pegging(pegging_map):
	finished_items = list({finished_item for _, finished_item, _ in pegging_map})
	item_meta = get_item_meta(finished_items, ["item_name", "custom_musteri_grubu"])
	return [
		Pegging(
			material=material,
			finished_item=finished_item,
			bom=bom_name,
			item_name=item_meta.get(finished_item, {}).get("item_name") or "",
			customer_group=item_meta.get(finished_item, {}).get("custom_musteri_grubu") or "",
			weeks=dict(weeks),
		)
		for (material, finished_item, bom_name), weeks in pegging_map.items()
	]



def get_material_requirements(filters, include_po=None) -> MaterialRequirementResult:
	if include_po is None:
		include_po = resolve_mrp_settings(filters).default_include_po
	gross_req = get_gross_requirements(filters)
	item_codes = list(gross_req.gross)
	context = load_supply_context(item_codes, gross_req.weeks, include_po)
	materials = {
		item_code: build_material(item_code, gross_req, context) for item_code in item_codes
	}
	return MaterialRequirementResult(weeks=gross_req.weeks, materials=materials, pegging=gross_req.pegging)


def load_supply_context(item_codes, weeks, include_po):
	sourcing_configs = supply.get_item_sourcing_configs(item_codes)
	suppliers = {code: cfg.default_supplier for code, cfg in sourcing_configs.items()}
	if include_po and weeks:
		receipts, supply_breakdown = supply.get_open_supplies(item_codes, weeks[0])
	else:
		receipts, supply_breakdown = {}, {}
	return frappe._dict(
		item_meta=get_item_meta(item_codes, ["item_name", "stock_uom"]),
		suppliers=suppliers,
		sourcing_configs=sourcing_configs,
		terms=supply.get_buying_terms(item_codes, suppliers),
		stock=supply.get_stock(item_codes),
		receipts=receipts,
		supply_breakdown=supply_breakdown,
	)


def build_material(item_code, gross_req, context):
	stock = context.stock.get(item_code) or frappe._dict(actual=0, reserved=0)
	terms = context.terms.get(item_code) or frappe._dict(moq=0, pack=1, price=0, currency=None, lead_time_days=0)
	meta = context.item_meta.get(item_code, {})
	breakdown = (
		context.supply_breakdown.get(item_code)
		if context.get("supply_breakdown")
		else frappe._dict(antrepoda=0.0, yolda=0.0, po_kalan=0.0, total=0.0, details=[])
	)
	sourcing_cfg = (
		context.sourcing_configs.get(item_code)
		if context.get("sourcing_configs")
		else None
	) or frappe._dict(
		strategy="Varsayılan Tedarikçi (%100)",
		default_supplier=context.suppliers.get(item_code),
		suppliers=[],
	)

	netting = net_material(
		gross_req.weeks,
		gross_req.gross[item_code],
		free_stock=stock.actual - stock.reserved,
		receipts=context.receipts.get(item_code, {}),
		moq=terms.moq,
		pack=terms.pack,
		sourcing_strategy=sourcing_cfg.strategy,
		suppliers=sourcing_cfg.suppliers,
	)
	return MaterialRequirement(
		item_code=item_code,
		item_name=meta.get("item_name") or "",
		uom=gross_req.uoms.get(item_code) or meta.get("stock_uom"),
		supplier=context.suppliers.get(item_code) or "",
		actual=stock.actual,
		reserved=stock.reserved,
		netting=netting,
		supply_breakdown=breakdown,
		sourcing_strategy=sourcing_cfg.strategy,
		suppliers_quota=sourcing_cfg.suppliers,
		planned_orders_by_supplier=netting.planned_orders_by_supplier,
		**{k: terms[k] for k in ("moq", "pack", "price", "currency", "lead_time_days")},
	)


def get_item_meta(item_codes, fields):
	if not item_codes:
		return {}
	rows = frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=["name", *fields])
	return {d.name: d for d in rows}


# ---------------------------------------------------------------- Web API & Export


@frappe.whitelist()
def get_material_requirements_data(filters=None):
	if isinstance(filters, str):
		filters = json.loads(filters)
	filters = frappe._dict(filters or {})

	mrp_settings = get_mrp_settings()
	include_po = cint(filters.include_po) if "include_po" in filters else cint(mrp_settings.default_include_po)
	urgent_weeks = mrp_settings.urgent_shortage_weeks

	result = get_material_requirements(filters, include_po=include_po)
	curr_wk = current_week_key()

	weeks = [
		{"key": w, "label": week_label(w), "is_current": (w == curr_wk)}
		for w in result.weeks
	]

	pegging_by_mat = defaultdict(list)
	for p in result.pegging:
		pegging_by_mat[p.material].append({
			"finished_item": p.finished_item,
			"item_name": p.item_name,
			"bom": p.bom,
			"customer_group": p.customer_group,
			"total": round(p.total, 3),
			"weeks": {w: round(p.weeks.get(w, 0), 3) for w in result.weeks},
		})

	materials_list = []
	for item_code, mat in result.materials.items():
		netting = mat.netting
		first_shortage = netting.first_shortage_week
		is_shortage = netting.net_total > 0
		is_urgent = (netting.coverage_weeks < urgent_weeks) if (first_shortage and is_shortage) else False
		has_po = netting.receipts_total > 0

		mat_weeks = {}
		for w in result.weeks:
			mat_weeks[w] = {
				"gross": round(netting.gross.get(w, 0), 3),
				"po": round(netting.receipts.get(w, 0), 3),
				"net": round(netting.net.get(w, 0), 3),
				"order": round(netting.planned_orders.get(w, 0), 3),
				"projected": round(netting.projected.get(w, 0), 3),
			}

		bd = mat.supply_breakdown or frappe._dict(antrepoda=0.0, gumruklemede=0.0, yolda=0.0, po_kalan=0.0, total=0.0, details=[])
		open_supplies = [
			{
				"type": d.get("type", "PO"),
				"name": d.get("name", ""),
				"po_name": d.get("po_name", ""),
				"supplier": d.get("supplier") or mat.supplier,
				"state": d.get("state", "Açık Sipariş"),
				"qty": round(flt(d.get("qty")), 3),
				"date": str(d.get("date")) if d.get("date") else "",
				"week": d.get("week") or "",
				"date_label": d.get("date_label", ""),
				"is_estimated": bool(d.get("is_estimated")),
				"loading_date": str(d.get("loading_date")) if d.get("loading_date") else "",
				"eta_date": str(d.get("eta_date")) if d.get("eta_date") else "",
				"customs_date": str(d.get("customs_date")) if d.get("customs_date") else "",
				"clearance_start_date": str(d.get("clearance_start_date")) if d.get("clearance_start_date") else "",
			}
			for d in bd.get("details", [])
		]

		materials_list.append({
			"item_code": mat.item_code,
			"item_name": mat.item_name,
			"uom": mat.uom,
			"supplier": mat.supplier,
			"sourcing_strategy": mat.sourcing_strategy,
			"suppliers_quota": [
				{
					"supplier": s.get("supplier"),
					"quota_share": s.get("quota_share", 0),
					"moq": s.get("moq", 0),
					"pack": s.get("pack", 1),
					"price": s.get("price", 0),
					"currency": s.get("currency", ""),
					"lead_time_days": s.get("lead_time_days", 0),
					"is_default": bool(s.get("is_default")),
				}
				for s in (mat.suppliers_quota or [])
			],
			"planned_orders_by_supplier": {
				sup: {w: round(qty, 3) for w, qty in wk_map.items()}
				for sup, wk_map in (mat.planned_orders_by_supplier or {}).items()
			},
			"actual_stock": round(mat.actual, 3),
			"reserved_stock": round(mat.reserved, 3),
			"free_stock": round(mat.free_stock, 3),
			"lead_time_days": mat.lead_time_days,
			"moq": mat.moq,
			"pack": mat.pack,
			"unit_price": mat.price or 0,
			"currency": mat.currency or "",
			"planned_order_total": round(netting.planned_order_total, 3),
			"gross_total": round(netting.gross_total, 3),
			"net_total": round(netting.net_total, 3),
			"po_total": round(netting.receipts_total, 3),
			"antrepoda_total": round(flt(bd.get("antrepoda", 0)), 3),
			"gumruklemede_total": round(flt(bd.get("gumruklemede", 0)), 3),
			"yolda_total": round(flt(bd.get("yolda", 0)), 3),
			"po_kalan_total": round(flt(bd.get("po_kalan", 0)), 3),
			"projected_total": round(netting.projected.get(result.weeks[-1], 0) if result.weeks else 0, 3),
			"order_amount": round(mat.order_amount, 2),
			"first_shortage_week": week_label(first_shortage) if first_shortage else None,
			"coverage_weeks": netting.coverage_weeks,
			"is_urgent": is_urgent,
			"is_shortage": is_shortage,
			"has_po": has_po,
			"weeks": mat_weeks,
			"pegging": pegging_by_mat.get(mat.item_code, []),
			"open_pos": open_supplies,
			"open_supplies": open_supplies,
		})

	materials_list.sort(
		key=lambda m: (
			0 if m["is_shortage"] else 1,
			999 if m["coverage_weeks"] is None else m["coverage_weeks"],
			-flt(m["order_amount"]),
			-flt(m["net_total"]),
			m["item_code"],
		)
	)

	totals_by_curr = defaultdict(float)
	for m in materials_list:
		if m["planned_order_total"] > 0 and m["currency"]:
			totals_by_curr[m["currency"]] += m["order_amount"]

	return {
		"weeks": weeks,
		"materials": materials_list,
		"summary": {
			"total_items": len(materials_list),
			"shortage_count": sum(1 for m in materials_list if m["is_shortage"]),
			"urgent_count": sum(1 for m in materials_list if m["is_urgent"]),
			"po_count": sum(1 for m in materials_list if m["has_po"]),
			"antrepo_count": sum(1 for m in materials_list if m.get("antrepoda_total", 0) > 0),
			"gumruk_count": sum(1 for m in materials_list if m.get("gumruklemede_total", 0) > 0),
			"yolda_count": sum(1 for m in materials_list if m.get("yolda_total", 0) > 0),
			"sufficient_count": sum(1 for m in materials_list if not m["is_shortage"]),
			"order_amount_by_currency": dict(totals_by_curr),
		},
		"settings": {
			"urgent_weeks": urgent_weeks,
			"default_include_po": mrp_settings.default_include_po,
			"planning_horizon_days": mrp_settings.planning_horizon_days,
		},
	}


@frappe.whitelist()
def get_week_netting_details(item_code, week, from_date=None, to_date=None, include_po=1):
	include_po = cint(include_po)
	filters = {"from_date": from_date or today(), "to_date": to_date}
	res = get_material_requirements(filters, include_po=include_po)

	mat = res.materials.get(item_code)
	if not mat:
		return {"error": _("Hammadde bulunamadı.")}

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

	pos = []
	if include_po and res.weeks:
		first_week = res.weeks[0]
		for d in supply.get_open_po_rows([item_code]):
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

	balance_before = mat.free_stock
	for w in res.weeks:
		if w == week:
			break
		g = mat.netting.gross.get(w, 0)
		r = mat.netting.receipts.get(w, 0)
		o = mat.netting.planned_orders.get(w, 0)
		balance_before = balance_before + r + o - g

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
		"gross": mat.netting.gross.get(week, 0),
		"receipts": mat.netting.receipts.get(week, 0),
		"net": mat.netting.net.get(week, 0),
		"order": mat.netting.planned_orders.get(week, 0),
		"projected": mat.netting.projected.get(week, 0),
		"include_po": include_po,
		"pos": pos,
		"demands": demands,
	}


@frappe.whitelist()
def export_material_requirements_excel(filters=None):
	import io
	import openpyxl
	from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
	from openpyxl.utils import get_column_letter

	data = get_material_requirements_data(filters)
	weeks = data["weeks"]
	materials = data["materials"]
	raw_filters = json.loads(filters) if isinstance(filters, str) else (filters or {})
	view = raw_filters.get("weekly_view") or "Önerilen Sipariş"

	view_field_map = {
		"Önerilen Sipariş": "order",
		"Net İhtiyaç": "net",
		"Brüt İhtiyaç": "gross",
		"Projeksiyon Bakiye": "projected",
	}
	metric_key = view_field_map.get(view, "order")

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = _("Hammadde İhtiyaç Planlama")

	header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
	header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
	center_align = Alignment(horizontal="center", vertical="center")

	headers = [
		_("Hammadde Kodu"),
		_("Ürün Açıklaması"),
		_("Birim"),
		_("Varsayılan Tedarikçi"),
		_("Stok"),
		_("Rezerve Stok"),
		_("Serbest Stok"),
		_("Temin Süresi (Gün)"),
		_("Min. Sipariş Miktarı (MOQ)"),
		_("Paketleme Katı"),
		_("Birim Fiyat"),
		_("Para Birimi"),
		_("Önerilen Sipariş Tutarı"),
	]
	for w in weeks:
		headers.append(w["label"])

	ws.append(headers)

	for col_idx in range(1, len(headers) + 1):
		cell = ws.cell(row=1, column=col_idx)
		cell.fill = header_fill
		cell.font = header_font
		cell.alignment = center_align

	for m in materials:
		row = [
			m["item_code"],
			m["item_name"],
			m["uom"],
			m["supplier"],
			m["actual_stock"],
			m["reserved_stock"],
			m["free_stock"],
			m["lead_time_days"],
			m["moq"],
			m["pack"],
			m["unit_price"],
			m["currency"],
			m["order_amount"],
		]
		for w in weeks:
			val = m["weeks"].get(w["key"], {}).get(metric_key, 0)
			row.append(val)
		ws.append(row)

	num_format = "#,##0.00"
	for row_idx in range(2, ws.max_row + 1):
		for col_idx in range(5, 8):
			ws.cell(row=row_idx, column=col_idx).number_format = num_format
		ws.cell(row=row_idx, column=11).number_format = num_format
		ws.cell(row=row_idx, column=13).number_format = num_format
		for col_idx in range(14, len(headers) + 1):
			ws.cell(row=row_idx, column=col_idx).number_format = num_format

	for col in ws.columns:
		max_len = max(len(str(cell.value or "")) for cell in col)
		col_letter = get_column_letter(col[0].column)
		ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

	output = io.BytesIO()
	wb.save(output)
	output.seek(0)

	filename = f"Hammadde_Ihtiyac_Planlama_{today()}.xlsx"
	frappe.response["filename"] = filename
	frappe.response["filecontent"] = output.getvalue()
	frappe.response["type"] = "binary"
