import frappe
from datetime import time
from frappe.utils import get_datetime

def _shift_name_by_now(now_dt):
    t = now_dt.time()
    if time(0, 0) < t <= time(8, 0):
        return "3. Vardiya"
    elif time(8, 0) < t <= time(16, 0):
        return "1. Vardiya"
    else:
        return "2. Vardiya"

def find_shift_crossing_impact():
    frappe.connect()
    
    cards = frappe.get_all(
        "Calisma Karti",
        filters={"durum": ["in", ["Bitmiş", "Reddedildi"]]},
        fields=["name", "baslangic_saati", "bitis_saati", "net_calisma_suresi", "operator"]
    )
    
    affected_cards = []
    
    for c in cards:
        if not c.baslangic_saati or not c.bitis_saati: continue
        
        start_dt = get_datetime(c.baslangic_saati)
        end_dt = get_datetime(c.bitis_saati)
        
        shift_at_start = _shift_name_by_now(start_dt)
        shift_at_end = _shift_name_by_now(end_dt)
        
        if shift_at_start != shift_at_end:
            # Shift crossing occurred. Now check impact.
            # We'll need to see if recalculating with start_dt changes the time.
            affected_cards.append({
                "name": c.name,
                "operator": c.operator,
                "start": str(start_dt),
                "end": str(end_dt),
                "shift_start": shift_at_start,
                "shift_end": shift_at_end,
                "old_net": c.net_calisma_suresi
            })
            
    print(f"Total Completed Cards: {len(cards)}")
    print(f"Cards Crossing Shift Boundaries: {len(affected_cards)}")
    
    # Analyze a sample to see how many actually change value
    # For a few operators, we can see if their daily total exceeds 430
    return affected_cards

if __name__ == "__main__":
    find_shift_crossing_impact()
