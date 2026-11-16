"""Saf MRP netleştirme hesabı (veritabanına erişmez).

Her hafta (w) için:
    Brüt İhtiyaç        G[w]
    PO Girişi           R[w]
    Net İhtiyaç         N[w] = max(0, G[w] - (B[w-1] + R[w]))   B: önerilen siparişler dahil bakiye
    Önerilen Sipariş    O[w] = lot_size(N[w], MOQ, paket)
    Projeksiyon Bakiye  P[w] = P[w-1] + R[w] - G[w]   (yeni sipariş verilmezse; negatif = eksik)

Başlangıç bakiyesi serbest stoktur (Stok - Rezerve) ve negatif olabilir; bu durumda
ilk hafta "mevcut eksik" olarak net ihtiyaç doğar.
"""

import math
from dataclasses import dataclass, field

from frappe.utils import flt


@dataclass
class NettingResult:
    weeks: list
    gross: dict = field(default_factory=dict)
    receipts: dict = field(default_factory=dict)
    net: dict = field(default_factory=dict)
    planned_orders: dict = field(default_factory=dict)
    projected: dict = field(default_factory=dict)
    planned_orders_by_supplier: dict = field(default_factory=dict)
    first_shortage_week: str | None = None
    surplus_po: float = 0

    @property
    def gross_total(self):
        return sum(self.gross.values())

    @property
    def receipts_total(self):
        return sum(self.receipts.values())

    @property
    def net_total(self):
        return sum(self.net.values())

    @property
    def planned_order_total(self):
        return sum(self.planned_orders.values())

    @property
    def coverage_weeks(self):
        """Stok + PO'nun yeni sipariş gerekmeden karşıladığı hafta sayısı."""
        if self.first_shortage_week is None:
            return len(self.weeks)
        return self.weeks.index(self.first_shortage_week)


def lot_size(qty, moq=0, pack=1):
    """Eksik miktarı paket katına yuvarlar, MOQ'nun altına düşürmez."""
    if qty <= 0:
        return 0
    pack = pack if pack and pack > 0 else 1
    return max(moq or 0, math.ceil(round(qty / pack, 6)) * pack)


def net_material(
    weeks,
    gross,
    free_stock=0,
    receipts=None,
    moq=0,
    pack=1,
    safety_stock=0,
    sourcing_strategy="Varsayılan Tedarikçi (%100)",
    suppliers=None,
):
    receipts = receipts or {}
    result = NettingResult(weeks=list(weeks))
    balance = projected = free_stock
    for week in result.weeks:
        receipt = receipts.get(week, 0)
        projected += receipt - gross.get(week, 0)
        result.projected[week] = projected
        balance = _net_week(
            result,
            week,
            balance,
            gross.get(week, 0),
            receipt,
            moq,
            pack,
            safety_stock=safety_stock,
            sourcing_strategy=sourcing_strategy,
            suppliers=suppliers,
        )
    result.first_shortage_week = next(
        (w for w in result.weeks if result.net[w] > 0), None
    )
    result.surplus_po = _surplus_po(free_stock, result)
    return result


def _net_week(
    result,
    week,
    balance,
    demand,
    receipt,
    moq,
    pack,
    safety_stock=0,
    sourcing_strategy="Varsayılan Tedarikçi (%100)",
    suppliers=None,
):
    available = balance + receipt
    shortage = max(0.0, demand + flt(safety_stock) - available)
    result.gross[week] = demand
    result.receipts[week] = receipt
    result.net[week] = shortage

    if shortage <= 0:
        result.planned_orders[week] = 0
        return available - demand

    order = 0.0
    suppliers = suppliers or []

    if len(suppliers) > 1 and sourcing_strategy == "Kotalı Dağılım (% Paylaşım)":
        total_moq_sum = sum(flt(s.get("moq") or 0) for s in suppliers)
        if total_moq_sum > 0 and shortage < total_moq_sum:
            # Küçük ihtiyaç: Kamçı etkisini ve aşırı stok birikimini önlemek için ana tedarikçide topla
            best_s = max(
                suppliers,
                key=lambda s: (flt(s.get("quota_share") or 0), -(s.get("idx") or 0)),
            )
            sup_name = best_s.get("supplier")
            order = lot_size(
                shortage, moq=best_s.get("moq", 0), pack=best_s.get("pack", 1)
            )
            if sup_name not in result.planned_orders_by_supplier:
                result.planned_orders_by_supplier[sup_name] = {}
            result.planned_orders_by_supplier[sup_name][week] = order
        else:
            for s in suppliers:
                sup_name = s.get("supplier")
                quota = flt(s.get("quota_share") or 0) / 100.0
                s_shortage = shortage * quota
                s_order = lot_size(
                    s_shortage, moq=s.get("moq", 0), pack=s.get("pack", 1)
                )
                if sup_name not in result.planned_orders_by_supplier:
                    result.planned_orders_by_supplier[sup_name] = {}
                result.planned_orders_by_supplier[sup_name][week] = s_order
                order += s_order

    elif len(suppliers) > 1 and sourcing_strategy == "En Düşük Fiyat Öncelikli":
        best_s = min(
            suppliers,
            key=lambda s: (
                flt(s.get("price") or 0) if flt(s.get("price") or 0) > 0 else 999999,
                s.get("idx", 0),
            ),
        )
        sup_name = best_s.get("supplier")
        order = lot_size(shortage, moq=best_s.get("moq", 0), pack=best_s.get("pack", 1))
        if sup_name not in result.planned_orders_by_supplier:
            result.planned_orders_by_supplier[sup_name] = {}
        result.planned_orders_by_supplier[sup_name][week] = order

    elif len(suppliers) > 1 and sourcing_strategy == "Termin Süresi Öncelikli":
        best_s = min(
            suppliers,
            key=lambda s: (
                int(s.get("lead_time_days") or 0)
                if int(s.get("lead_time_days") or 0) > 0
                else 999999,
                s.get("idx", 0),
            ),
        )
        sup_name = best_s.get("supplier")
        order = lot_size(shortage, moq=best_s.get("moq", 0), pack=best_s.get("pack", 1))
        if sup_name not in result.planned_orders_by_supplier:
            result.planned_orders_by_supplier[sup_name] = {}
        result.planned_orders_by_supplier[sup_name][week] = order

    else:
        order = lot_size(shortage, moq, pack)
        if suppliers and len(suppliers) > 0:
            sup_name = suppliers[0].get("supplier")
            if sup_name not in result.planned_orders_by_supplier:
                result.planned_orders_by_supplier[sup_name] = {}
            result.planned_orders_by_supplier[sup_name][week] = order

    result.planned_orders[week] = order
    return available + order - demand


def _surplus_po(free_stock, result):
    """Dönem ihtiyacını (önce stok kullanılarak) aşan PO miktarı."""
    leftover = free_stock + result.receipts_total - result.gross_total
    return min(max(leftover, 0), result.receipts_total)
