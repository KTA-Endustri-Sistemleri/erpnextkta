"""BOM patlatma: bitmiş ürün planını hammadde brüt ihtiyacına ve pegging kırılımına çevirir."""

from collections import defaultdict
from dataclasses import dataclass, field

import frappe
from frappe.utils import flt


@dataclass
class BomExplosion:
	gross: dict = field(default_factory=dict)  # {hammadde: {hafta: miktar}}
	pegging: dict = field(default_factory=dict)  # {(hammadde, bitmiş ürün, bom): {hafta: miktar}}
	uoms: dict = field(default_factory=dict)  # {hammadde: stok birimi}


def get_default_boms(item_codes):
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"BOM",
		filters={"item": ["in", item_codes], "is_default": 1, "is_active": 1},
		fields=["item", "name"],
	)
	return {d.item: d.name for d in rows}


def get_explosion_items(bom_names):
	items = defaultdict(list)
	if not bom_names:
		return items
	rows = frappe.get_all(
		"BOM Explosion Item",
		filters={"parent": ["in", bom_names]},
		fields=["parent", "item_code", "stock_qty", "stock_uom"],
	)
	for d in rows:
		items[d.parent].append(d)
	return items


def explode(plan) -> BomExplosion:
	"""plan: demand.ProductionPlan"""
	bom_map = get_default_boms(list(plan.planned))
	explosion_items = get_explosion_items(list(set(bom_map.values())))
	gross = defaultdict(lambda: defaultdict(float))
	pegging = defaultdict(lambda: defaultdict(float))
	uoms = {}
	for finished_item, bom in bom_map.items():
		for week in plan.weeks:
			qty = plan.material_driving_qty(finished_item, week)
			if qty <= 0:
				continue
			for d in explosion_items.get(bom, []):
				material_qty = flt(d.stock_qty) * qty
				gross[d.item_code][week] += material_qty
				pegging[(d.item_code, finished_item, bom)][week] += material_qty
				uoms.setdefault(d.item_code, d.stock_uom)
	return BomExplosion(gross=gross, pegging=pegging, uoms=uoms)
