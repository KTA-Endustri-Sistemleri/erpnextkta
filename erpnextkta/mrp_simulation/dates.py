# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class SimulationSchedule:
	w_current_monday: date
	w_next_monday: date
	w_plus_2_monday: date
	so_avrupa_delivery_date: date
	so_yerli_delivery_date: date
	po_schedule_date: date
	pr_yolda_eta: date
	pr_gumruk_start_date: date
	mr_schedule_date: date


def get_simulation_dates(base_date: date | None = None) -> SimulationSchedule:
	"""Calculates aligned simulation dates based on ISO weeks and KTA delivery lead times.

	- Current week Monday is anchor W_CURRENT.
	- MUSTERI-AVRUPA (7d prod + 5d delivery = 12d lead) -> delivery_date = W_CURRENT + 12d.
	- MUSTERI-YERLI (3d prod + 1d delivery = 4d lead) -> delivery_date = W_CURRENT + 4d.
	- Open PO lands in W+1.
	- In-transit PR ETA lands in W+2.
	- Customs clearance start date is W_CURRENT.
	- Material Request (Manufacture) lands in W+1.
	"""
	base = base_date or date.today()
	w_cur_monday = base - timedelta(days=base.weekday())
	w_next_monday = w_cur_monday + timedelta(days=7)
	w_plus_2_monday = w_cur_monday + timedelta(days=14)

	return SimulationSchedule(
		w_current_monday=w_cur_monday,
		w_next_monday=w_next_monday,
		w_plus_2_monday=w_plus_2_monday,
		so_avrupa_delivery_date=w_cur_monday + timedelta(days=12),
		so_yerli_delivery_date=w_cur_monday + timedelta(days=4),
		po_schedule_date=w_next_monday + timedelta(days=2),
		pr_yolda_eta=w_plus_2_monday + timedelta(days=2),
		pr_gumruk_start_date=w_cur_monday,
		mr_schedule_date=w_next_monday + timedelta(days=4),
	)
