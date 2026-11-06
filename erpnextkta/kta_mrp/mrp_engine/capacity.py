"""Kapasite Planlama Çekirdek Servisi: Talep, Sevk, Kapasite ve Multi-Pass Dengeleme."""

from collections import defaultdict
from datetime import datetime, timedelta, date

import frappe
from frappe.utils import getdate, add_days, today

from erpnextkta.kta_mrp.mrp_engine.settings import resolve_mrp_settings
from erpnextkta.kta_mrp.mrp_engine.leveling import forward_scheduling, backward_rampup_smoothing


def get_monday_of_current_week():
	t = datetime.today()
	return (t - timedelta(days=t.weekday())).date()


def iso_week_start(week_str):
	try:
		parts = week_str.lower().replace("w", "").split("_")
		if len(parts) == 2:
			return date.fromisocalendar(int(parts[0]), int(parts[1]), 1)
	except Exception:
		return None


def build_capacity_plan(filters=None, settings=None):
	"""Kapasite planını hesaplar ve rapor formatından bağımsız yapılandırılmış veri döndürür.

	Dönen sözlük: valid_weeks, item_groups, group_capacity, plan, kanban_plan, wo_plan,
	raw_mr_demands, item_week_demand, item_backlog.
	"""
	filters = frappe._dict(filters or {})
	cfg = settings or resolve_mrp_settings(filters)

	today_monday = get_monday_of_current_week()
	from_date = filters.get("from_date")
	if from_date:
		from_date_obj = getdate(from_date)
		if from_date_obj < today_monday:
			frappe.throw(
				frappe._("Geçmiş tarihler için rapor çalıştırılamaz. {0} sonrası seçiniz.").format(
					today_monday
				)
			)
	else:
		from_date_obj = today_monday

	min_to_date = from_date_obj + timedelta(days=cfg.planning_horizon_days)
	to_date = filters.get("to_date")
	to_date_obj = getdate(to_date) if to_date else min_to_date

	# PSW (Production Start Week) taleplerini topla
	from erpnextkta.kta_mrp.report.production_start_week.production_start_week import (
		ProductionStartWeekReport,
	)

	today_date = datetime.today().date()
	psw_filters = {
		"from_date": (today_date - timedelta(days=cfg.backlog_lookback_days)).strftime("%Y-%m-%d"),
		"to_date": to_date_obj.strftime("%Y-%m-%d"),
		"group_by_item_only": 1,
	}
	if filters.get("item_group"):
		psw_filters["item_group"] = filters["item_group"]

	psw_report = ProductionStartWeekReport(psw_filters)
	columns_psw, data_psw, *_ = psw_report.run()

	# 1. Başlangıç verilerini hazırla (Ürünler ve Kapasiteleri)
	item_filters = {"custom_ara_malzeme_grubu": "ÜRÜN"}
	if filters.get("item_group"):
		item_filters["item_group"] = filters["item_group"]
	if filters.get("custom_musteri_grubu"):
		item_filters["custom_musteri_grubu"] = filters["custom_musteri_grubu"]

	item_meta = frappe.get_all(
		"Item", filters=item_filters, fields=["name", "custom_weekly_production", "item_group"]
	)
	item_groups = {i.name: i.item_group or "Diğer" for i in item_meta}

	group_capacity = {}
	for i in item_meta:
		group = i.item_group or "Diğer"
		cap = int(float(i.custom_weekly_production or 0))
		if group not in group_capacity or cap > group_capacity[group]:
			group_capacity[group] = cap

	week_fields = [
		c["fieldname"]
		for c in columns_psw
		if c.get("fieldtype") == "Int" and c["fieldname"] not in ("total", "stock_covered", "to_produce")
	]
	valid_weeks = [
		f for f in week_fields if iso_week_start(f) and iso_week_start(f) >= from_date_obj
	]

	# 2. Talepleri topla
	item_week_demand = defaultdict(lambda: defaultdict(int))
	item_backlog = defaultdict(int)

	item_week_kanban = defaultdict(lambda: defaultdict(int))
	item_backlog_kanban = defaultdict(int)

	for row in data_psw:
		item = row.get("item_code")
		if not item or item not in item_groups:
			continue

		for field in week_fields:
			qty = int(row.get(field, 0) or 0)
			ws = iso_week_start(field)
			if ws:
				if ws >= from_date_obj:
					item_week_demand[item][field] += qty
				else:
					item_backlog[item] += qty

	# 2.1 Kanban / MR Taleplerini Ekle
	mr_data = frappe.db.sql(
		"""
		SELECT mri.item_code, (mri.qty - mri.ordered_qty) as pending_qty, mr.schedule_date
		FROM `tabMaterial Request` mr
		JOIN `tabMaterial Request Item` mri ON mr.name = mri.parent
		WHERE mr.material_request_type = 'Manufacture'
		  AND mr.docstatus = 1
		  AND mr.status NOT IN ('Completed', 'Stopped', 'Cancelled')
		  AND mri.qty > mri.ordered_qty
	""",
		as_dict=True,
	)

	# 2.2 İş Emri (WIP) Taleplerini Ekle
	wo_data = frappe.db.sql(
		"""
		SELECT production_item as item_code, (qty - produced_qty) as pending_qty, planned_start_date as schedule_date
		FROM `tabWork Order`
		WHERE docstatus = 1
		  AND status IN ('Not Started', 'In Process')
		  AND qty > produced_qty
	""",
		as_dict=True,
	)

	raw_mr_demands = defaultdict(lambda: defaultdict(int))
	all_kanban_items = list({d.item_code for d in mr_data} | {d.item_code for d in wo_data})

	missing_items = [item for item in all_kanban_items if item not in item_groups]
	if missing_items:
		mr_item_meta = frappe.get_all(
			"Item",
			filters={"name": ["in", missing_items]},
			fields=["name", "custom_weekly_production", "item_group"],
		)
		for i in mr_item_meta:
			if filters.get("item_group") and i.item_group != filters.get("item_group"):
				continue
			item_groups[i.name] = i.item_group or "Diğer"
			cap = int(float(i.custom_weekly_production or 0))
			if item_groups[i.name] not in group_capacity or cap > group_capacity[item_groups[i.name]]:
				group_capacity[item_groups[i.name]] = cap

	item_customer_map = {}
	if all_kanban_items:
		for d in frappe.get_all(
			"Item Customer Detail",
			filters={"parent": ["in", all_kanban_items]},
			fields=["parent", "customer_name"],
		):
			if d.customer_name:
				item_customer_map.setdefault(d.parent, d.customer_name)
		for d in frappe.get_all(
			"Item",
			filters={"name": ["in", all_kanban_items]},
			fields=["name", "custom_musteri_grubu"],
		):
			if not item_customer_map.get(d.name):
				item_customer_map[d.name] = d.custom_musteri_grubu

	sevk_map = psw_report.sevk_map if hasattr(psw_report, "sevk_map") else {}

	item_week_wo = defaultdict(lambda: defaultdict(int))
	item_backlog_wo = defaultdict(int)

	def process_kanban_data(data, is_work_order=False):
		for d in data:
			item = d.item_code
			if item not in item_groups:
				continue
			qty = int(d.pending_qty)
			s_date = getdate(d.schedule_date or today())

			if is_work_order:
				prod_start = s_date
			else:
				production_time = cfg.default_production_time_days
				customer_name = item_customer_map.get(item)
				if customer_name:
					sevk_params = sevk_map.get(customer_name)
					if sevk_params and sevk_params.get("production_time"):
						production_time = int(sevk_params.get("production_time"))
				prod_start = add_days(s_date, -production_time) if production_time > 0 else s_date

			iso_year, iso_week, _ = prod_start.isocalendar()
			field = f"{iso_year}_w{iso_week:02d}"

			ws = iso_week_start(field)
			if ws:
				raw_mr_demands[item][field] += qty
				if ws >= from_date_obj:
					item_week_demand[item][field] += qty
					if is_work_order:
						item_week_wo[item][field] += qty
					else:
						item_week_kanban[item][field] += qty
					if field not in valid_weeks:
						valid_weeks.append(field)
				else:
					item_backlog[item] += qty
					if is_work_order:
						item_backlog_wo[item] += qty
					else:
						item_backlog_kanban[item] += qty

	process_kanban_data(mr_data, is_work_order=False)
	process_kanban_data(wo_data, is_work_order=True)

	valid_weeks.sort()

	# Grup -> ürün listesi
	group_items = defaultdict(list)
	for it, group in item_groups.items():
		group_items[group].append(it)

	# PASS 1: Forward Scheduling
	item_final_plan, item_final_kanban_plan, item_final_wo_plan = forward_scheduling(
		valid_weeks=valid_weeks,
		group_items=group_items,
		group_capacity=group_capacity,
		item_backlog=item_backlog,
		item_week_demand=item_week_demand,
		item_backlog_kanban=item_backlog_kanban,
		item_week_kanban=item_week_kanban,
		item_backlog_wo=item_backlog_wo,
		item_week_wo=item_week_wo,
		leveling_enabled=cfg.enable_leveling_by_default,
	)

	# PASS 2 & 3: Backward Fill ve Ramp-up (Smoothing)
	if cfg.enable_rampup_by_default:
		backward_rampup_smoothing(
			valid_weeks=valid_weeks,
			group_items=group_items,
			group_capacity=group_capacity,
			item_final_plan=item_final_plan,
			item_final_kanban_plan=item_final_kanban_plan,
			item_final_wo_plan=item_final_wo_plan,
			ramp_weeks=cfg.default_rampup_weeks,
			trigger_ratio=cfg.rampup_trigger_utilization / 100.0,
			max_capacity_ratio=cfg.rampup_max_capacity_limit / 100.0,
			min_smoothing_qty=cfg.min_smoothing_qty,
		)

	return frappe._dict(
		valid_weeks=valid_weeks,
		item_groups=item_groups,
		group_capacity=group_capacity,
		plan=item_final_plan,
		kanban_plan=item_final_kanban_plan,
		wo_plan=item_final_wo_plan,
		raw_mr_demands=raw_mr_demands,
		item_week_demand=item_week_demand,
		item_backlog=item_backlog,
		settings=cfg,
	)
