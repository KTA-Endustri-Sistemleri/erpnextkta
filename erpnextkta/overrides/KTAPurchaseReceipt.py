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

    def _get_exchange_rate(self, from_currency, to_currency, date, for_selling, for_buying):
        result = frappe.db.sql("""
            SELECT exchange_rate FROM `tabCurrency Exchange`
            WHERE date <= %s AND from_currency = %s AND to_currency = %s
            AND for_selling = %s AND for_buying = %s
            ORDER BY date DESC LIMIT 1
        """, (date, from_currency, to_currency, for_selling, for_buying))
        return result[0][0] if result else None

    def update_rates_logic(self):
        """
        Update Purchase Receipt Exchange Rate and Item Prices.

        1. Rate Date: Uses 'gumruk_beyanname_tarihi' or 'irsaliye_tarihi' if available, else Posting Date.
        2. Conversion Rate: Uses 'Selling' rate by default.
           Exception: If 'Gümrüksüz' checkbox is checked, uses 'Buying' rate from Posting Date.
        3. Item Rates: Uses Fresh Price List rate effective on Rate Date.
        """
        use_buying_rate = self.get("custom_gumruksuz")

        if use_buying_rate:
            rate_date = self.posting_date
        elif self.get("gumruk_beyanname_tarihi"):
            rate_date = self.get("gumruk_beyanname_tarihi")
        elif self.get("irsaliye_tarihi"):
            rate_date = self.get("irsaliye_tarihi")
        else:
            rate_date = self.posting_date

        for_selling = 0 if use_buying_rate else 1
        for_buying = 1 if use_buying_rate else 0

        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

        # 1. Update Exchange Rate
        if self.currency and self.currency == company_currency:
            self.conversion_rate = 1.0

        if self.currency and self.currency != company_currency:
            rate = self._get_exchange_rate(self.currency, company_currency, rate_date, for_selling, for_buying)
            if rate:
                self.conversion_rate = rate
                if self.price_list_currency == self.currency:
                    self.plc_conversion_rate = rate

        if self.price_list_currency and self.price_list_currency != company_currency and self.price_list_currency != self.currency:
            rate = self._get_exchange_rate(self.price_list_currency, company_currency, rate_date, for_selling, for_buying)
            if rate:
                self.plc_conversion_rate = rate

        if not self.items:
            self.calculate_taxes_and_totals()
            return

        # Pre-fetch old doc once and build O(1) item lookup map
        old_doc = None
        old_items_map = {}
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.currency != self.currency:
                old_items_map = {i.name: i for i in old_doc.items}

        # Batch query Item Price to avoid N+1 per item
        existing_item_prices = set()
        if self.buying_price_list and self.supplier:
            rows = frappe.db.sql("""
                SELECT CONCAT(item_code, '|', price_list_rate) FROM `tabItem Price`
                WHERE price_list = %s AND supplier = %s
            """, (self.buying_price_list, self.supplier))
            existing_item_prices = {r[0] for r in rows}

        # Per-PR/PO currency cache to avoid N+1 parent lookups
        _po_currency_cache = {}
        _pr_currency_cache = {}

        # 2. Update Item Rates
        for item in self.items:
            current_plr = item.price_list_rate or 0.0
            current_rate = item.rate or 0.0

            calc_conversion = 1.0
            if self.price_list_currency and self.currency and self.price_list_currency != self.currency:
                if self.plc_conversion_rate:
                    calc_conversion = self.plc_conversion_rate

            discount_factor = 1.0 - (item.get("discount_percentage", 0) / 100.0)
            expected_rate = current_plr * calc_conversion * discount_factor
            is_detached = abs(current_rate - expected_rate) > 0.01

            is_manual_plr = False
            if not is_detached and current_plr > 0 and self.buying_price_list:
                key = f"{item.item_code}|{current_plr}"
                is_manual_plr = key not in existing_item_prices

            if is_detached or is_manual_plr:
                # --- KTA Currency Change Fix ---
                po_rate = None
                po_currency = None
                pr_orig_rate = None
                pr_orig_currency = None

                if item.get("purchase_order_item"):
                    po_item = frappe.db.get_value("Purchase Order Item", item.purchase_order_item, ["rate", "parent"], as_dict=True)
                    if po_item:
                        parent = po_item.parent
                        if parent not in _po_currency_cache:
                            _po_currency_cache[parent] = frappe.db.get_value("Purchase Order", parent, "currency")
                        po_currency = _po_currency_cache[parent]
                        if po_currency:
                            po_rate = po_item.rate

                elif item.get("purchase_receipt_item"):
                    pr_item = frappe.db.get_value("Purchase Receipt Item", item.purchase_receipt_item, ["rate", "parent"], as_dict=True)
                    if pr_item:
                        parent = pr_item.parent
                        if parent not in _pr_currency_cache:
                            _pr_currency_cache[parent] = frappe.db.get_value("Purchase Receipt", parent, "currency")
                        pr_orig_currency = _pr_currency_cache[parent]
                        if pr_orig_currency:
                            pr_orig_rate = pr_item.rate

                old_currency = None
                old_conversion_rate = None
                old_rate = None

                if old_items_map:
                    old_item = old_items_map.get(item.name)
                    if old_item:
                        old_currency = old_doc.currency
                        old_conversion_rate = old_doc.conversion_rate
                        old_rate = old_item.rate

                        # Corruption guard: if rate == PO/PR rate but currency doesn't match,
                        # switching back to source currency → restore original rate directly.
                        if po_currency and po_rate and old_currency != po_currency and abs(old_rate - po_rate) < 0.001 and self.currency == po_currency:
                            item.rate = po_rate
                            old_rate = None  # bypass regular calculation
                        elif pr_orig_currency and pr_orig_rate and old_currency != pr_orig_currency and abs(old_rate - pr_orig_rate) < 0.001 and self.currency == pr_orig_currency:
                            item.rate = pr_orig_rate
                            old_rate = None  # bypass regular calculation

                if self.is_new():
                    src_currency = (po_currency if po_currency and po_currency != self.currency
                                    else pr_orig_currency if pr_orig_currency and pr_orig_currency != self.currency
                                    else None)
                    if src_currency:
                        src_rate = po_rate if src_currency == po_currency else pr_orig_rate
                        old_currency = src_currency
                        old_rate = src_rate
                        if src_currency == company_currency:
                            old_conversion_rate = 1.0
                        elif src_currency == self.price_list_currency and self.plc_conversion_rate:
                            old_conversion_rate = self.plc_conversion_rate
                        elif src_currency == self.currency and self.conversion_rate:
                            old_conversion_rate = self.conversion_rate
                        else:
                            old_conversion_rate = self._get_exchange_rate(src_currency, company_currency, rate_date, for_selling, for_buying)

                if old_currency and old_conversion_rate and self.conversion_rate and old_rate is not None:
                    correct_new_rate = (old_rate * old_conversion_rate) / self.conversion_rate
                    difference = abs(item.rate - old_rate)
                    difference_converted = abs(item.rate - correct_new_rate)
                    difference_bad1 = abs(item.rate - (old_rate / self.conversion_rate))
                    if difference < 0.001 or difference_converted < 0.001 or difference_bad1 < 0.001:
                        item.rate = correct_new_rate

                item.amount = item.rate * item.qty
                item.net_rate = item.rate
                item.net_amount = item.amount
                item.base_rate = item.rate * self.conversion_rate
                item.base_amount = item.amount * self.conversion_rate
                item.base_net_rate = item.net_rate * self.conversion_rate
                item.base_net_amount = item.net_amount * self.conversion_rate
                continue

            # Standard path: fetch fresh prices
            args = {
                "item_code": item.item_code,
                "warehouse": item.warehouse,
                "supplier": self.supplier,
                "price_list": self.buying_price_list,
                "price_list_currency": self.price_list_currency,
                "plc_conversion_rate": self.plc_conversion_rate,
                "company": self.company,
                "transaction_date": rate_date,
                "currency": self.currency,
                "conversion_rate": self.conversion_rate,
                "qty": item.qty,
                "doctype": "Purchase Receipt",
                "name": self.name,
                "ignore_pricing_rule": 0
            }

            try:
                details = get_item_details(args)
                if details:
                    if details.get("price_list_rate"):
                        item.price_list_rate = details.get("price_list_rate")
                        item.rate = details.get("rate") or item.price_list_rate
                    if details.get("discount_percentage"):
                        item.discount_percentage = details.get("discount_percentage")
                    item.amount = item.rate * item.qty
                    item.base_rate = item.rate * self.conversion_rate
                    item.base_amount = item.amount * self.conversion_rate
                    item.net_rate = item.rate
                    item.net_amount = item.amount
                    item.base_net_rate = item.net_rate * self.conversion_rate
                    item.base_net_amount = item.net_amount * self.conversion_rate
            except Exception as e:
                frappe.log_error(f"KTAPurchaseReceipt Rate Update Error: {str(e)}", "KTAPurchaseReceipt")

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
            import traceback
            error_trace = traceback.format_exc()
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}\n{error_trace}", "Purchase Receipt Submit Error")
            frappe.throw(f"Purchase Receipt Submit Error {str(e)}\n{error_trace}")
        finally:
            if hasattr(self, "flags"):
                self.flags.kta_rows_to_split = None

    def print_zebra(self):
        try:
            erpnextkta.api.print_kta_pr_labels(gr_number=self.name)
        except Exception as e:
            frappe.log_error(f"Zebra Print Error (Ignored): {str(e)}", "KTAPurchaseReceipt Print Error")
            # User said: "o hata gelsin önemli değil" (Let that error come, it's not important)
            # However, if we raise, it rolls back submit. 
            # So we catch it, log it, and maybe show a non-blocking message.
            frappe.msgprint(f"Zebra Printer Error (Non-blocking): {str(e)}", alert=True)

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
