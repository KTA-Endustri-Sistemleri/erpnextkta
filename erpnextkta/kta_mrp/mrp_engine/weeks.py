"""ISO hafta yardımcıları.

Tek format kullanılır:
- anahtar (fieldname): ``2026_w45`` (Kapasite Planlama raporuyla aynı)
- etiket (görünen ad): ``2026-W45``
"""

from datetime import date

from frappe.utils import getdate


def week_key(value) -> str:
	iso_year, iso_week, _ = getdate(value).isocalendar()
	return f"{iso_year}_w{iso_week:02d}"


def parse_week_key(key: str) -> tuple[int, int]:
	year, week = key.lower().split("_w")
	return int(year), int(week)


def week_label(key: str) -> str:
	year, week = parse_week_key(key)
	return f"{year}-W{week:02d}"


def week_start(key: str) -> date:
	year, week = parse_week_key(key)
	return date.fromisocalendar(year, week, 1)


def sort_weeks(keys) -> list[str]:
	return sorted(set(keys), key=parse_week_key)


def clamp_to_first_week(key: str, first_week: str) -> str:
	"""Geçmiş haftaları (ör. gecikmiş PO) dönemin ilk haftasına çeker."""
	return max(key, first_week, key=parse_week_key)


def current_week_key() -> str:
	from frappe.utils import today
	return week_key(today())
