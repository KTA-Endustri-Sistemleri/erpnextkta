import frappe
from frappe import _
from frappe.utils import flt

STRATEGY_DEFAULT = "Varsayılan Tedarikçi (%100)"
STRATEGY_QUOTA = "Kotalı Dağılım (% Paylaşım)"
STRATEGY_LEAST_COST = "En Düşük Fiyat Öncelikli"
STRATEGY_LEAD_TIME = "Termin Süresi Öncelikli"

MULTI_SUPPLIER_STRATEGIES = (
	STRATEGY_QUOTA,
	STRATEGY_LEAST_COST,
	STRATEGY_LEAD_TIME,
)


def validate_item_sourcing_strategy(doc, method=None):
	"""Çoklu tedarikçi stratejisi ve kota toplamı doğrulama kuralı."""
	suppliers = doc.get("supplier_items") or []
	supplier_count = len(suppliers)

	if supplier_count <= 1:
		doc.custom_sourcing_strategy = STRATEGY_DEFAULT
		return

	# 2 veya daha fazla tedarikçi varsa
	strategy = doc.get("custom_sourcing_strategy")
	if not strategy or strategy == STRATEGY_DEFAULT:
		frappe.throw(
			_(
				"Birden Fazla Tedarikçisi Olan Kalemlerde Tedarik Stratejisi Belirlenmelidir. "
				"Lütfen Kotalı Dağılım, En Düşük Fiyat veya Termin Süresi Stratejilerinden Birini Seçiniz."
			)
		)

	if strategy == STRATEGY_QUOTA:
		total_quota = sum(flt(d.get("custom_quota_share") or 0) for d in suppliers)
		if abs(total_quota - 100.0) > 0.01:
			frappe.throw(
				_(
					"Kotalı Dağılım Stratejisinde Tedarikçi Kotaları Toplamı %100 Olmalıdır. "
					"Şu Anki Toplam: %{0}"
				).format(round(total_quota, 2))
			)
