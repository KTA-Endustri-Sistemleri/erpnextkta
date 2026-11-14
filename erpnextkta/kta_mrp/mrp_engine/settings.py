"""Merkezi MRP Ayarları: KTA MRP Settings okuyucu ve varsayılan yapılandırma."""

from dataclasses import dataclass
import frappe
from frappe.utils import cint, flt


@dataclass(frozen=True)
class MrpSettings:
	# Kapasite & Dengeleme
	enable_leveling_by_default: bool = True
	enable_rampup_by_default: bool = True
	default_rampup_weeks: int = 3
	rampup_trigger_utilization: float = 70.0
	rampup_max_capacity_limit: float = 95.0
	min_smoothing_qty: int = 10

	# Zaman & Ufuk
	planning_horizon_days: int = 90
	backlog_lookback_days: int = 270
	default_production_time_days: int = 14
	default_delivery_time_days: int = 2
	urgent_shortage_weeks: int = 4

	# Depo & Satınalma
	available_warehouse_type: str = "Kullanılabilir Stok"
	default_include_po: bool = True
	antrepo_clearance_days: int = 2


def get_mrp_settings() -> MrpSettings:
	"""KTA MRP Settings Single DocType'ından ayarları çeker; yoksa varsayılanları döner."""
	try:
		if not frappe.db or not frappe.db.exists("DocType", "KTA MRP Settings"):
			return MrpSettings()
		doc = frappe.get_single("KTA MRP Settings")
		return MrpSettings(
			enable_leveling_by_default=bool(cint(doc.get("enable_leveling_by_default", 1))),
			enable_rampup_by_default=bool(cint(doc.get("enable_rampup_by_default", 1))),
			default_rampup_weeks=max(cint(doc.get("default_rampup_weeks") or 3), 1),
			rampup_trigger_utilization=flt(doc.get("rampup_trigger_utilization") or 70.0),
			rampup_max_capacity_limit=flt(doc.get("rampup_max_capacity_limit") or 95.0),
			min_smoothing_qty=max(cint(doc.get("min_smoothing_qty") or 10), 0),
			planning_horizon_days=max(cint(doc.get("planning_horizon_days") or 90), 1),
			backlog_lookback_days=max(cint(doc.get("backlog_lookback_days") or 270), 1),
			default_production_time_days=max(cint(doc.get("default_production_time_days") or 14), 0),
			default_delivery_time_days=max(cint(doc.get("default_delivery_time_days") if doc.get("default_delivery_time_days") is not None else 2), 0),
			urgent_shortage_weeks=max(cint(doc.get("urgent_shortage_weeks") or 4), 1),
			available_warehouse_type=doc.get("available_warehouse_type") or "Kullanılabilir Stok",
			default_include_po=bool(cint(doc.get("default_include_po", 1))),
			antrepo_clearance_days=max(cint(doc.get("antrepo_clearance_days") if doc.get("antrepo_clearance_days") is not None else 2), 0),
		)
	except Exception:
		return MrpSettings()


def resolve_mrp_settings(filters=None) -> MrpSettings:
	"""Rapor filtreleri ile merkezi ayarları harmanlar (Filtreler ayarları ezebilir)."""
	base = get_mrp_settings()
	if not filters:
		return base

	f = frappe._dict(filters)

	# Dengeleme aktif mi?
	leveling = base.enable_leveling_by_default
	if "dengeleme_yapilsin" in f:
		leveling = bool(cint(f.dengeleme_yapilsin))

	# Ramp-up aktif mi?
	rampup = base.enable_rampup_by_default
	if "ramp_up_aktif" in f:
		rampup = bool(cint(f.ramp_up_aktif))

	# Ramp-up hafta sayısı
	ramp_weeks = base.default_rampup_weeks
	if f.get("ramp_up_weeks"):
		ramp_weeks = max(cint(f.ramp_up_weeks), 1)

	# Include PO
	include_po = base.default_include_po
	if "include_po" in f:
		include_po = bool(cint(f.include_po))

	return MrpSettings(
		enable_leveling_by_default=leveling,
		enable_rampup_by_default=rampup,
		default_rampup_weeks=ramp_weeks,
		rampup_trigger_utilization=base.rampup_trigger_utilization,
		rampup_max_capacity_limit=base.rampup_max_capacity_limit,
		min_smoothing_qty=base.min_smoothing_qty,
		planning_horizon_days=base.planning_horizon_days,
		backlog_lookback_days=base.backlog_lookback_days,
		default_production_time_days=base.default_production_time_days,
		urgent_shortage_weeks=base.urgent_shortage_weeks,
		available_warehouse_type=base.available_warehouse_type,
		default_include_po=include_po,
		antrepo_clearance_days=base.antrepo_clearance_days,
	)
