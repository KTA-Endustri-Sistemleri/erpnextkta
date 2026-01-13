import frappe
from frappe.utils import getdate, flt
from erpnext.controllers.accounts_controller import get_payment_terms

def validate_purchase_invoice(doc, method):
    if doc.bill_date:
        # User Requirement: due_date must be based on bill_date.
        # Problem: Standard set_payment_schedule might copy stale dates from linked POs if 
        # 'Automatically Fetch Payment Terms' is disabled.
        
        # Strategy: We will force a fresh calculation of payment terms based on the bill_date
        # if a template is available.
        
        if doc.payment_terms_template:
            # We need grand totals for the calculation
            grand_total = doc.get("rounded_total") or doc.grand_total
            base_grand_total = doc.get("base_rounded_total") or doc.base_grand_total
            
            # Fetch fresh terms based on bill_date
            # posting_date argument in get_payment_terms is used as the reference date
            fresh_terms = get_payment_terms(
                doc.payment_terms_template, 
                doc.bill_date, 
                grand_total, 
                base_grand_total
            )
            
            if fresh_terms:
                doc.set("payment_schedule", [])
                for term in fresh_terms:
                    doc.append("payment_schedule", term)
                
                # After setting schedule, set due_date from it
                if hasattr(doc, 'set_due_date'):
                    doc.set_due_date()
        
        elif not doc.get("payment_schedule"):
             # If no template and no schedule, default due_date to bill_date
             if not doc.due_date:
                 doc.due_date = doc.bill_date

        # Fallback: If for some reason we still rely on set_payment_schedule (e.g. no template but complex logic),
        # ensure due_date is at least checked against bill_date? 
        # No, the above covers the template case which is the standard "due date based on" flow.
