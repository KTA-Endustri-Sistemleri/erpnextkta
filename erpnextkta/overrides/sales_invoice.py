import frappe
from frappe import _
from frappe.utils import add_days, getdate
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.stock.get_item_details import get_item_details
from erpnextkta.kta_sales.doctype.kta_selling_rate_customer.kta_selling_rate_customer import is_selling_rate_customer

class KTASalesInvoice(SalesInvoice):
    def validate(self):
        self.update_rates_logic()
        super().validate()

    def update_rates_logic(self):
        """
        Update Sales Invoice Exchange Rate and Item Prices.
        
        1. Conversion Rate: Uses 'Buying' rate from (Posting Date - 1 day) or simply Posting Date based on existing logic preference.
        2. Item Rates: Uses Fresh Price List rate effective on Posting Date.
        """
        
        # 1. Update Exchange Rate
        if self.currency and self.currency != self.company_currency:
            target_date = self.posting_date
            
            # Determine if we should use Buying or Selling rate
            use_selling = is_selling_rate_customer(self.customer)
            use_buying_rate = 0 if use_selling else 1

            exchange_rate = frappe.db.get_value(
                "Currency Exchange",
                {
                    "date": target_date,
                    "from_currency": self.currency,
                    "to_currency": self.company_currency,
                    "for_buying": use_buying_rate,
                    "for_selling": 1 if not use_buying_rate else 0
                },
                "exchange_rate"
            )
            
            if exchange_rate:
                self.conversion_rate = exchange_rate
                # Ensure Price List Exchange Rate matches if currencies are the same
                if self.price_list_currency == self.currency:
                    self.plc_conversion_rate = exchange_rate

        # Ensure plc_conversion_rate is set if Price List Currency differs from Company Currency
        # AND if it hasn't been manually set (or is 0)
        if not self.plc_conversion_rate and self.price_list_currency and self.price_list_currency != self.company_currency and self.price_list_currency != self.currency:
            target_date = self.posting_date
            
            use_selling = is_selling_rate_customer(self.customer)
            use_buying_rate = 0 if use_selling else 1

            # Fetch latest available Exchange Rate on or before posting_date
            # We explicitly check for_buying or for_selling
            plc_rate_info = frappe.db.sql("""
                SELECT exchange_rate 
                FROM `tabCurrency Exchange`
                WHERE date <= %s
                AND from_currency = %s
                AND to_currency = %s
                AND for_buying = %s
                AND for_selling = %s
                ORDER BY date DESC
                LIMIT 1
            """, (target_date, self.price_list_currency, self.company_currency, use_buying_rate, 1 if not use_buying_rate else 0), as_dict=True)
            
            if plc_rate_info:
                self.plc_conversion_rate = plc_rate_info[0].exchange_rate

        # 2. Update Item Rates
        if self.items:
            for item in self.items:
                # Calculate new rates
                # We strictly want the price valid for this Customer on the Posting Date
                
                # Fetch fresh item details
                # args for get_item_details
                args = {
                    "item_code": item.item_code,
                    "warehouse": item.warehouse,
                    "customer": self.customer,
                    "selling_price_list": self.selling_price_list,
                    "price_list_currency": self.price_list_currency,
                    "plc_conversion_rate": self.plc_conversion_rate,
                    "company": self.company,
                    "transaction_date": self.posting_date, # Critical for Valid From/To check
                    "currency": self.currency,
                    "conversion_rate": self.conversion_rate,
                    "price_list": self.selling_price_list,
                    "qty": item.qty,
                    "uom": item.uom,
                    "doctype": "Sales Invoice",
                    "name": self.name,
                    "ignore_pricing_rule": 0
                }
                
                try:
                    # Generic fetch first
                    details = get_item_details(args)
                    
                    # User requested STRICT lookup for "Valid From - Valid To" and "Customer" match.
                    # get_item_details might return a general price list rate if no specific customer price exists.
                    # Let's verify if a specific Item Price exists for this customer to be sure we are prioritizing it.
                    specific_price = frappe.db.sql("""
                        SELECT price_list_rate, currency 
                        FROM `tabItem Price` 
                        WHERE item_code = %s 
                        AND price_list = %s 
                        AND customer = %s
                        AND valid_from <= %s 
                        AND (valid_upto IS NULL OR valid_upto >= %s)
                        ORDER BY valid_from DESC LIMIT 1
                    """, (item.item_code, self.selling_price_list, self.customer, self.posting_date, self.posting_date), as_dict=True)
                    
                    if specific_price:
                        # If a specific price exists, use it.
                        rate = specific_price[0].price_list_rate
                        # If currency differs, we might need conversion, but usually Item Price is in Price List Currency
                        # details['price_list_rate'] should already be this, but let's trust our SQL if we want to be paranoid about "Customer" match.
                        
                        if details:
                             details["price_list_rate"] = rate
                             
                             conversion_factor = 1.0
                             if self.price_list_currency != self.currency and self.plc_conversion_rate:
                                 conversion_factor = self.plc_conversion_rate
                                 
                             details["rate"] = details["price_list_rate"] * conversion_factor * (1 - (details.get("discount_percentage", 0) / 100))
                    
                    if details:
                        # Update the item with the fresh details
                        item.price_list_rate = details.get("price_list_rate")
                        item.discount_percentage = details.get("discount_percentage")
                        
                        # Explicitly update 'rate'
                        item.rate = details.get("rate") or item.price_list_rate
                        
                        # Recalculate amounts
                        item.amount = item.rate * item.qty
                        item.base_rate = item.rate * self.conversion_rate
                        item.base_amount = item.amount * self.conversion_rate
                        
                        item.net_rate = item.rate
                        item.net_amount = item.amount
                except Exception as e:
                    # Force reload check
                    frappe.log_error(f"Error fetching details: {str(e)[:100]}", "KTASalesInvoice Error")
        
        # Recalculate taxes and totals at the end of custom logic
        self.calculate_taxes_and_totals()
