import frappe
from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import format_sure

def run_dry_run():
    # Bitmiş ve duruşu olan (Taslak veya Submitted) kartları getir
    affected_cards = frappe.get_all("Calisma Karti", 
        filters={
            "docstatus": ["!=", 2],
            "durum": "Bitmiş",
            "toplam_durus": ["!=", "00:00:00"]
        },
        fields=["name", "toplam_durus", "net_calisma_suresi", "baslangic_saati", "bitis_saati"]
    )

    print(f"\n{'Name':<20} | {'Total Pause':<12} | {'Old Net':<10} | {'New Net':<10} | {'Diff (min)':<10}")
    print("-" * 75)

    count = 0
    total_diff_minutes = 0

    for c in affected_cards:
        # Mevcut değer (Saniye cinsinden alalım)
        from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import _parse_minsec
        
        old_net_sec = _parse_minsec(c.net_calisma_suresi)
        pause_sec = _parse_minsec(c.toplam_durus)
        
        # Yeni Mantık: 430dk - Duruş
        max_limit = 430 * 60
        new_net_sec = max(0, max_limit - pause_sec)
        
        diff_sec = old_net_sec - new_net_sec
        diff_min = round(diff_sec / 60, 2)
        total_diff_minutes += abs(diff_min)
        
        if count < 20:
            print(f"{c.name:<20} | {c.toplam_durus:<12} | {c.net_calisma_suresi:<10} | {format_sure(new_net_sec):<10} | {diff_min:<10}")
        
        count += 1

    print("-" * 75)
    print(f"Total Affected Cards: {count}")
    print(f"Sample of 20 shown above.")
    print(f"Approximate total reduction in recorded time: {round(total_diff_minutes, 2)} minutes")

if __name__ == "__main__":
    run_dry_run()
