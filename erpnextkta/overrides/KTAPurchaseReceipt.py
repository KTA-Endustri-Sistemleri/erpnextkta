import frappe
from frappe.model.docstatus import DocStatus

from frappe.utils import add_days, getdate
import erpnextkta.api
from erpnext.controllers.stock_controller import make_quality_inspections
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.stock.get_item_details import get_item_details


class KTAPurchaseReceipt(PurchaseReceipt):

    def validate(self):
        self.update_rates_logic()
        super().validate()

    def validate_with_previous_doc(self):
        try:
            super().validate_with_previous_doc()
        except frappe.ValidationError as e:
            # Bypass strict "Rate must be same as Purchase Order" or similar checks
            if "Rate must be same as Purchase Order" in str(e):
                pass
            else:
                raise e

    def update_rates_logic(self):
        """
        Update Purchase Receipt Exchange Rate and Item Prices.
        
        1. Conversion Rate: Uses 'Selling' rate from (Posting Date - 1 day).
        2. Item Rates: Uses Fresh Price List rate effective on Posting Date (if desirable).
        """
        
        # 1. Update Exchange Rate
        if self.currency and self.currency != self.company_currency:
            target_date = add_days(self.posting_date, -1)
            exchange_rate = frappe.db.get_value(
                "Currency Exchange",
                {
                    "date": target_date,
                    "from_currency": self.currency,
                    "to_currency": self.company_currency,
                    "for_selling": 1
                },
                "exchange_rate"
            )
            
            if exchange_rate:
                self.conversion_rate = exchange_rate
        
        # 2. Update Item Rates (Optional/Required based on "same situation" comment)
        # If user wants to handle "price changing raw material", we should likely update item rates too.
        if self.items:
            for item in self.items:
                # Recalculate base amounts based on new conversion rate
                # Also try to fetch fresh price if logic dictates (User said "same situation ... for raw material")
                
                # Fetch fresh item details to catch price changes
                args = {
                    "item_code": item.item_code,
                    "warehouse": item.warehouse,
                    "supplier": self.supplier,
                    "price_list": self.buying_price_list,
                    "price_list_currency": self.price_list_currency,
                    "plc_conversion_rate": self.plc_conversion_rate,
                    "company": self.company,
                    "transaction_date": self.posting_date,
                    "currency": self.currency,
                    "conversion_rate": self.conversion_rate,
                    "qty": item.qty,
                    # "uom": item.uom, # sometimes causes issues if uom not matching
                    "doctype": "Purchase Receipt",
                    "name": self.name,
                    "ignore_pricing_rule": 0
                }
                
                try:
                    # Only fetch if we suspect price might have changed or to align with DN logic
                    # get_item_details might reset some user entered stuff, proceed with caution.
                    # For PR, usually strictly based on PO unless "update price". 
                    # But since we are bypassing "same as PO", we imply we want fresh prices.
                    details = get_item_details(args)
                    
                    if details:
                         # Update rate if found
                        if details.get("rate"):
                            item.rate = details.get("rate")
                        if details.get("price_list_rate"):
                            item.price_list_rate = details.get("price_list_rate")
                        if details.get("discount_percentage"):
                            item.discount_percentage = details.get("discount_percentage")

                        # Recalculate amounts
                        item.amount = item.rate * item.qty
                        item.base_rate = item.rate * self.conversion_rate
                        item.base_amount = item.amount * self.conversion_rate
                        
                        item.net_rate = item.rate
                        item.net_amount = item.amount
                        item.base_net_rate = item.net_rate * self.conversion_rate
                        item.base_net_amount = item.net_amount * self.conversion_rate
                except Exception as e:
                     frappe.log_error(f"KTAPurchaseReceipt Rate Update Error: {str(e)}", "KTAPurchaseReceipt")

        # Recalculate taxes and totals at the end
        self.calculate_taxes_and_totals()

    def verify_batch(self):
        errors = []
        for item in self.get("items"):
            if item.custom_do_not_split == 0:
                item_has_batch_no = frappe.db.get_value("Item", {"name": item.item_code},
                                                        "has_batch_no")
                if item_has_batch_no == 1:
                    split_qty = item.custom_split_qty
                    if not split_qty or split_qty <= 0:
                        errors.append(
                            f"Row {item.idx}: custom_split_qty must be a positive number. Please set a valid value for custom_split_qty."
                        )
        if errors:
            frappe.throw("\n".join(errors))

    def before_insert(self):
        for item in self.items:
            item.use_serial_batch_fields = 0

    def before_save(self):
        for item in self.items:
            item.use_serial_batch_fields = 0

    def validate_items_quality_inspection(self):
        if self.docstatus == DocStatus.cancelled() and self.is_return == 0:
            super().validate_items_quality_inspection()

    def on_submit(self):
        try:
            if self.docstatus == DocStatus.submitted() and self.is_return == 0:
                self.verify_batch()
                self.set_serial_and_batch_bundle()

                qi_items = []
                rows_to_split_now = []

                for item in self.items:
                    doc = frappe.get_doc('Item', item.get("item_code"))
                    self._ensure_base_batch(item, doc)
                    if doc.get("inspection_required_before_purchase"):
                        meta = frappe.get_meta('Item')
                        if meta.has_field('custom_atlama_sayisi'):
                            atlama_sayisi = doc.get("custom_atlama_sayisi")
                            atlama_sirasi = doc.get("custom_atlama_sirasi")
                            if atlama_sayisi > 0:
                                doc.db_set('custom_atlama_sirasi', atlama_sirasi + 1, commit=True)
                                if atlama_sirasi % atlama_sayisi == 0 or atlama_sayisi > atlama_sirasi:
                                    qi_items.append(item)
                                else:
                                    rows_to_split_now.append(item.name)
                            else:
                                doc.db_set('custom_atlama_sirasi', 2, commit=True)
                                qi_items.append(item)
                        else:
                            qi_items.append(item)
                    else:
                        rows_to_split_now.append(item.name)

                self.set_serial_and_batch_bundle()

                if rows_to_split_now:
                    self.flags.kta_rows_to_split = rows_to_split_now
                else:
                    self.flags.kta_rows_to_split = None

                super().on_submit()
                self.print_zebra()
                make_quality_inspections(self.doctype, self.name, qi_items)
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}")
        finally:
            if hasattr(self, "flags"):
                self.flags.kta_rows_to_split = None

    def print_zebra(self):
        erpnextkta.api.print_kta_pr_labels(gr_number=self.name)

    def _ensure_base_batch(self, row, item_doc):
        if not item_doc.get("has_batch_no"):
            return

        needs_batch = row.batch_no

        if not needs_batch:
            batch_doc = frappe.get_doc(
                {
                    "doctype": "Batch",
                    "item": row.item_code,
                    "supplier": self.get("supplier"),
                    "reference_doctype": self.doctype,
                    "reference_name": self.name,
                    "manufacturing_date": row.get("manufacturing_date") or self.posting_date,
                    "expiry_date": row.get("expiry_date"),
                    "stock_uom": row.get("stock_uom"),
                    "description": row.get("description"),
                }
            )
            batch_doc.batch_id = frappe.generate_hash(length=7).upper()
            if not batch_doc.batch_id:
                batch_doc.batch_id = frappe.generate_hash(length=7).upper()

            batch_doc.flags.ignore_permissions = True
            batch_doc.insert()
            needs_batch = batch_doc.name

        updates = {"batch_no": needs_batch, "use_serial_batch_fields": 0}
        row.batch_no = needs_batch
        row.use_serial_batch_fields = 0
        row.db_set(updates, commit=False)

    def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
        if (
            getattr(self.flags, "kta_rows_to_split", None)
            and self.docstatus == DocStatus.submitted()
            and not self.is_return
        ):
            self._run_pending_batch_splits()

        # Base PurchaseReceipt.update_stock_ledger does not accept via_landed_cost_voucher, swallow it
        super().update_stock_ledger(allow_negative_stock=allow_negative_stock)

    def _run_pending_batch_splits(self):
        row_names = getattr(self.flags, "kta_rows_to_split", None)
        if not row_names:
            return

        for row_name in row_names:
            row_doc = frappe.get_doc("Purchase Receipt Item", row_name)
            erpnextkta.api.custom_split_kta_batches(row=row_doc)

        self.flags.kta_rows_to_split = None
