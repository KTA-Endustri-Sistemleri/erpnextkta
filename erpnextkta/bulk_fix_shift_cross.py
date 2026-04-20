import frappe
import json
from frappe.utils import get_datetime

def run_recalculation(dry_run=True, log_file="shift_fix_results.json"):
    frappe.connect()
    
    # Process by operator to respect shift capacity logic
    operators = frappe.get_all("Calisma Karti", filters={"durum": ["in", ["Bitmiş", "Reddedildi"]]}, fields=["operator"], distinct=True)
    
    stats = {
        "total_processed": 0,
        "total_changed": 0,
        "total_time_diff_seconds": 0,
        "changes": []
    }
    
    print(f"Starting SHIFT RECALCULATION ({'DRY RUN' if dry_run else 'ACTUAL FIX'})")
    
    for op_row in operators:
        operator = op_row.operator
        if not operator: continue
        
        # Chronological order is vital for shift remaining capacity to calculate correctly
        cards = frappe.get_all(
            "Calisma Karti",
            filters={"operator": operator, "durum": ["in", ["Bitmiş", "Reddedildi"]]},
            fields=["name", "net_calisma_suresi"],
            order_by="baslangic_saati asc"
        )
        
        for c in cards:
            stats["total_processed"] += 1
            doc = frappe.get_doc("Calisma Karti", c.name)
            
            old_net = doc.net_calisma_suresi
            
            # This triggers the updated logic in the DocType (which now uses start_dt for shift window)
            doc.update_durum()
            
            new_net = doc.net_calisma_suresi
            
            if old_net != new_net:
                stats["total_changed"] += 1
                
                def to_sec(s):
                    if not s or ":" not in s: return 0
                    p = s.split(':')
                    return int(p[0])*3600 + int(p[1])*60 + int(p[2])
                
                diff = to_sec(new_net) - to_sec(old_net)
                stats["total_time_diff_seconds"] += diff
                
                stats["changes"].append({
                    "name": doc.name,
                    "operator": operator,
                    "old": old_net,
                    "new": new_net,
                    "diff_min": round(diff/60, 2)
                })
                
                if not dry_run:
                    # Commit change to database
                    frappe.db.set_value("Calisma Karti", doc.name, {
                        "net_calisma_suresi": doc.net_calisma_suresi,
                        "toplam_sure": doc.toplam_sure,
                        "toplam_durus": doc.toplam_durus,
                        "durum": doc.durum
                    }, update_modified=False)
        
        if not dry_run:
            frappe.db.commit()

    print("\nRecalculation Finished.")
    print(f"Total Processed: {stats['total_processed']}")
    print(f"Total Changed: {stats['total_changed']}")
    print(f"Total Time Diff: {stats['total_time_diff_seconds']/60:.2f} minutes")
    
    # Use a more reliable path for logging
    with open(f"bulk_fix_shift_results.json", "w") as f:
        json.dump(stats, f, indent=4)
        
    return stats

if __name__ == "__main__":
    run_recalculation(dry_run=True)
