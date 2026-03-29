"""
Vardiya Net Süre Simülasyonu
Kullanım (bench console):
    %run apps/erpnextkta/erpnextkta/kta_calisma_karti/scripts/vardiya_sim.py
"""
import datetime
import frappe
from collections import defaultdict
from frappe.utils import get_datetime, add_to_date


def _parse_minsec(v):
    if not v or ":" not in str(v):
        return 0
    try:
        m, s = str(v).strip().split(":", 1)
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def shift_window(shift_name, base_date):
    sd = frappe.get_doc("Shift Type", shift_name)
    ss = int(sd.start_time.total_seconds())
    es = int(sd.end_time.total_seconds())
    st = datetime.time(ss // 3600, (ss % 3600) // 60)
    et = datetime.time(es // 3600, (es % 3600) // 60)
    ws = get_datetime(datetime.datetime.combine(base_date, st))
    we = get_datetime(datetime.datetime.combine(base_date, et))
    if we <= ws:
        we = add_to_date(we, days=1)
    return ws, we


today = datetime.date.today()
max_limit = int(
    frappe.db.get_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk") or 430
)

print(f"\n{'='*62}")
print(f"  VARDIYA NET SÜRE ANALİZİ  —  {today}  —  Max: {max_limit} dk")
print(f"{'='*62}")

for shift_name in ["1. Vardiya", "2. Vardiya", "3. Vardiya"]:
    ws, we = shift_window(shift_name, today)
    kartlar = frappe.get_all(
        "Calisma Karti",
        filters={"baslangic_saati": ["between", [ws, we]]},
        fields=["name", "operator", "net_calisma_suresi", "kalite_kontrol"],
        limit_page_length=1000,
    )
    label = f"[{shift_name}] {ws.strftime('%H:%M')} → {we.strftime('%H:%M')} | {len(kartlar)} kart"
    if not kartlar:
        print(f"\n  {label} — kart yok")
        continue

    op_cards = defaultdict(list)
    for k in kartlar:
        op_cards[k.operator].append(k)

    print(f"\n  {label}, {len(op_cards)} operatör")
    print(f"  {'─'*57}")

    for operator, cards in sorted(op_cards.items()):
        total_sn = sum(
            _parse_minsec(c.net_calisma_suresi)
            for c in cards
            if (c.kalite_kontrol or "").strip() != "Reddedildi"
        )
        total_dk = total_sn / 60
        kalan_dk = max(0, max_limit - total_dk)

        if total_dk >= max_limit:
            flag = "[LIMIT ASILDI]"
        elif kalan_dk < 60:
            flag = "[DIKKAT]      "
        else:
            flag = "[OK]          "

        print(
            f"    {flag}  {operator:<32}"
            f"  top={total_dk:5.0f} dk  kalan={kalan_dk:5.0f} dk  ({len(cards)} kart)"
        )

print(f"\n{'='*62}\n")
