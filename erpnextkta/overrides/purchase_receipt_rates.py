import frappe
from frappe.utils import add_days, getdate

def update_purchase_receipt_rates(doc, method):
    """
    Update Purchase Receipt Exchange Rate.
    
    1. Conversion Rate: Uses 'Selling' rate from (Posting Date - 1 day).
    """
    
    # 1. Update Exchange Rate
    if doc.currency and doc.currency != doc.company_currency:
        target_date = add_days(doc.posting_date, -1)
        exchange_rate = frappe.db.get_value(
            "Currency Exchange",
            {
                "date": target_date,
                "from_currency": doc.currency,
                "to_currency": doc.company_currency,
                "for_selling": 1
            },
            "exchange_rate"
        )
        
        if exchange_rate:
            doc.conversion_rate = exchange_rate
            
            # Recalculate base amounts for items since conversion rate changed
            if doc.items:
                for item in doc.items:
                    item.base_rate = item.rate * doc.conversion_rate
                    item.base_amount = item.amount * doc.conversion_rate
                    item.base_net_rate = item.net_rate * doc.conversion_rate
                    item.base_net_amount = item.net_amount * doc.conversion_rate

            # Recalculate taxes and totals
            doc.run_method("calculate_taxes_and_totals")
