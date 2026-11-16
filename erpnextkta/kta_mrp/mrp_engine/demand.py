"""Talep: Kapasite Planlama raporunun haftalık bitmiş ürün üretim planı."""

from dataclasses import dataclass, field

from erpnextkta.kta_mrp.mrp_engine.weeks import sort_weeks


@dataclass
class ProductionPlan:
	weeks: list
	planned: dict = field(default_factory=dict)  # {ürün: {hafta: miktar}}
	work_orders: dict = field(default_factory=dict)  # {ürün: {hafta: açık iş emri miktarı}}
	capacity_leveled: bool = False

	def material_driving_qty(self, item_code, week, capacity_leveled: bool | None = None):
		"""Hammadde talebi doğuran miktar.

		Açık iş emirleri planın içinde görünür ama hammaddeleri zaten Bin üzerinde
		rezerve edildiği için tekrar talep olarak sayılmaz (çift sayım engeli).
		'Kapasiteye Dağıtılmış Tüketim' modunda ise iş emirleri ambar stokunu peşin kilitlemez;
		fabrikanın haftalık kapasite planındaki üretim hızına göre zaman fazlı tüketilir.
		"""
		is_capacity = self.capacity_leveled if capacity_leveled is None else capacity_leveled
		planned = self.planned.get(item_code, {}).get(week, 0) or 0
		if planned <= 0:
			return 0
		if is_capacity:
			return planned
		return max(0, planned - (self.work_orders.get(item_code, {}).get(week, 0) or 0))


def get_production_plan(filters, settings=None) -> ProductionPlan:
	from erpnextkta.kta_mrp.mrp_engine.capacity import build_capacity_plan
	from erpnextkta.kta_mrp.mrp_engine.settings import resolve_mrp_settings

	if settings is None:
		settings = resolve_mrp_settings(filters)

	capacity = build_capacity_plan(dict(filters))
	return ProductionPlan(
		weeks=sort_weeks(capacity.valid_weeks),
		planned={item: dict(weeks) for item, weeks in capacity.plan.items()},
		work_orders={item: dict(weeks) for item, weeks in capacity.wo_plan.items()},
		capacity_leveled=settings.is_capacity_leveled_consumption,
	)
