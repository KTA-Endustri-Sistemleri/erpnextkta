"""
Patch: Vardiya sınır değeri (boundary) bugı nedeniyle yanlış hesaplanmış
net_calisma_suresi alanlarını düzeltir.

Bug: _shift_name_by_now() fonksiyonunda time(16,0) ve time(0,0) gibi
tam sınır değerleri [start, end) karşılaştırma ile yanlış vardiyaya
atanıyordu. Bu nedenle shift limiti (430 dk) bazı kartlara uygulanmıyordu.

Fix: Sınır koşulları (start, end] olarak düzeltildi (biten vardiyaya dahil).
Bu patch, etkilenen kartları yeniden hesaplatır.
"""
import frappe
from frappe.utils import get_datetime
from datetime import datetime, time, timedelta
from collections import defaultdict


def _parse_minsec(value):
    if not value or not isinstance(value, str):
        return 0
    s = str(value).strip()
    if ":" not in s:
        return 0
    parts = s.split(":")
    try:
        if len(parts) == 3:
            h, m, sec = parts
            return int(h) * 3600 + int(m) * 60 + int(sec)
        elif len(parts) == 2:
            m, sec = parts
            return int(m) * 60 + int(sec)
    except Exception:
        pass
    return 0


def execute():
    all_cards = frappe.db.sql("""
        SELECT name, operator, baslangic_saati, bitis_saati,
               net_calisma_suresi, kalite_kontrol, docstatus
        FROM `tabCalisma Karti`
        WHERE docstatus != 2
          AND baslangic_saati IS NOT NULL
          AND bitis_saati IS NOT NULL
        ORDER BY operator, baslangic_saati
    """, as_dict=True)

    # Operatör-vardiya gruplama
    groups = defaultdict(list)
    for c in all_cards:
        start = get_datetime(c.baslangic_saati)
        st = start.time()
        d = start.date()

        if time(0, 0) < st <= time(8, 0):
            shift_key = "{op}|3V|{d}".format(op=c.operator, d=d)
        elif st > time(8, 0) or st == time(8, 0):
            if st <= time(16, 0):
                shift_key = "{op}|1V|{d}".format(op=c.operator, d=d)
            else:
                shift_key = "{op}|2V|{d}".format(op=c.operator, d=d)
        elif st == time(0, 0):
            prev_day = d - timedelta(days=1)
            shift_key = "{op}|2V|{d}".format(op=c.operator, d=prev_day)
        else:
            continue

        groups[shift_key].append(c)

    # 430 dk aşımı olan grupları bul
    violations = []
    for key, cards in groups.items():
        total_net_sn = 0
        for c in cards:
            if (c.kalite_kontrol or "").strip() == "Reddedildi":
                continue
            total_net_sn += _parse_minsec(c.net_calisma_suresi)

        if total_net_sn / 60 > 430:
            violations.append(cards)

    if not violations:
        return

    # Etkilenen kartları yeniden hesapla
    updated = 0
    for cards in violations:
        sorted_cards = sorted(cards, key=lambda c: get_datetime(c.baslangic_saati))
        for c in sorted_cards:
            if (c.kalite_kontrol or "").strip() == "Reddedildi":
                continue

            old_net = c.net_calisma_suresi
            doc = frappe.get_doc("Calisma Karti", c.name)
            doc.update_durum()

            if doc.net_calisma_suresi != old_net:
                if doc.docstatus == 1:
                    doc.flags.ignore_validate_update_after_submit = True
                doc.save(ignore_permissions=True)

                frappe.db.set_value("Calisma Karti", doc.name, {
                    "durum": doc.durum,
                    "toplam_sure": doc.toplam_sure,
                    "toplam_durus": doc.toplam_durus,
                    "net_calisma_suresi": doc.net_calisma_suresi,
                }, update_modified=False)

                updated += 1

    if updated:
        frappe.db.commit()

    frappe.logger().info(
        "fix_shift_boundary_net_times: {updated} kart guncellendi".format(updated=updated)
    )
