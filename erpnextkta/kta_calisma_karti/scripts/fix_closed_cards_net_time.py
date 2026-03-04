"""
Önceden kapanmış ama net çalışma süresi limitin üzerinde (örn: 3748 dk) kalmış
eski kartların net çalışma sürelerini limit değerine (örn: 430 dk) göre doğru şekilde düzeltilir.

Kullanım (bench console içinden):
    %run apps/erpnextkta/erpnextkta/kta_calisma_karti/scripts/fix_closed_cards_net_time.py
"""

import frappe
from frappe.utils import get_datetime

def _parse_minsec(v):
    if not v or ":" not in str(v): return 0
    try:
        m, s = str(v).strip().split(":", 1)
        return int(m) * 60 + int(s)
    except Exception: return 0

def format_sure(seconds):
    if not seconds or seconds < 0: return "0:00"
    return f"{int(seconds//60)}:{int(seconds%60):02d}"

def fix_cards():
    max_limit = int(frappe.db.get_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk") or 430)
    max_sn = max_limit * 60

    print(f"Başlıyor... Max limit: {max_limit} dk")

    kartlar = frappe.get_all("Calisma Karti",
        filters={
            "bitis_saati": ["is", "set"],
            "kalite_kontrol": ["!=", "Reddedildi"],
            "docstatus": ["!=", 2],
        },
        fields=["name", "baslangic_saati", "bitis_saati", "toplam_durus", "net_calisma_suresi"],
        limit_page_length=5000)

    duzeltilen = 0
    for k in kartlar:
        net_sn = _parse_minsec(k.net_calisma_suresi)
        if net_sn <= max_sn:
            continue  # Zaten limit altında

        try:
            start_dt = get_datetime(k.baslangic_saati)
            bitis_dt = get_datetime(k.bitis_saati)
            toplam_sn = (bitis_dt - start_dt).total_seconds()
            durus_sn  = _parse_minsec(k.toplam_durus or "0:00")
            
            # Formül: gerçek net süre (toplam - durus), ancak max limiti geçemez
            gercek_net = max(0, min(toplam_sn - durus_sn, max_sn))

            frappe.db.set_value("Calisma Karti", k.name,
                {"net_calisma_suresi": format_sure(gercek_net)},
                update_modified=False)
            duzeltilen += 1
            print(f"  Düzeltildi: {k.name} ({k.net_calisma_suresi} -> {format_sure(gercek_net)})")
        except Exception as e:
            print(f"  ❌ {k.name}: {e}")

    frappe.db.commit()
    print(f"✅ net_calisma_suresi düzeltilen eski kart sayısı: {duzeltilen}")

if __name__ == "__main__":
    fix_cards()
