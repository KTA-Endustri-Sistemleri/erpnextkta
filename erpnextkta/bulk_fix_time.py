import frappe
import json
from frappe.utils import get_datetime

def run_bulk_fix(dry_run=True, start_date=None, operator_limit=None, log_file="bulk_fix_results.json"):
    frappe.connect()
    
    filters = {"durum": ["in", ["Bitmiş", "Reddedildi"]]}
    if start_date:
        filters["baslangic_saati"] = [">=", start_date]

    # Get unique operators to process them one by one (to avoid overlaps in shift windows during processing)
    operators = frappe.get_all("Calisma Karti", filters=filters, fields=["operator"], distinct=True)
    if operator_limit:
        operators = operators[:operator_limit]

    stats = {
        "total_processed": 0,
        "total_changed": 0,
        "total_time_diff_seconds": 0,
        "changes": []
    }

    print(f"Starting {'DRY RUN' if dry_run else 'ACTUAL FIX'}...")
    print(f"Found {len(operators)} operators to process.")

    for op_row in operators:
        operator = op_row.operator
        if not operator: continue
        
        # Get cards for this operator in chronological order
        cards = frappe.get_all(
            "Calisma Karti",
            filters={**filters, "operator": operator},
            fields=["name", "net_calisma_suresi", "toplam_sure"],
            order_by="baslangic_saati asc"
        )
        
        print(f"Processing operator: {operator} ({len(cards)} cards)")
        
        for c in cards:
            stats["total_processed"] += 1
            doc = frappe.get_doc("Calisma Karti", c.name)
            
            old_net = doc.net_calisma_suresi
            
            # Recalculate
            doc.update_durum()
            
            new_net = doc.net_calisma_suresi
            
            if old_net != new_net:
                stats["total_changed"] += 1
                
                # Calculate diff
                def to_sec(s):
                    if not s or ":" not in s: return 0
                    p = s.split(':')
                    return int(p[0])*3600 + int(p[1])*60 + int(p[2])
                
                diff = to_sec(new_net) - to_sec(old_net)
                stats["total_time_diff_seconds"] += diff
                
                if len(stats["changes"]) < 100: # Log first 100 changes
                    stats["changes"].append({
                        "name": doc.name,
                        "old": old_net,
                        "new": new_net,
                        "diff_min": round(diff/60, 2)
                    })
                
                if not dry_run:
                    # Update only time fields and durum to be safe
                    frappe.db.set_value("Calisma Karti", doc.name, {
                        "net_calisma_suresi": doc.net_calisma_suresi,
                        "toplam_sure": doc.toplam_sure,
                        "toplam_durus": doc.toplam_durus,
                        "durum": doc.durum
                    }, update_modified=False)
        
        if not dry_run:
            frappe.db.commit()

    print("\n" + "="*50)
    print(f"Results ({'DRY RUN' if dry_run else 'ACTUAL FIX'}):")
    print(f"Total Processed: {stats['total_processed']}")
    print(f"Total Changed:   {stats['total_changed']}")
    print(f"Total Time Gain: {stats['total_time_diff_seconds']/3600:.2f} hours")
    print("="*50)
    
    with open(log_file, "w") as f:
        json.dump(stats, f, indent=4)
    
    return stats

if __name__ == "__main__":
    # Site check
    import os
    site = open("sites/current_site.txt").read().strip() if os.path.exists("sites/current_site.txt") else None
    if site:
        frappe.init(site=site)
        run_bulk_fix(dry_run=True)
