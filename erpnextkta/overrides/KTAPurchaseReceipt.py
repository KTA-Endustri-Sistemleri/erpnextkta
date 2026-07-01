import frappe
from frappe import _
from frappe.model.docstatus import DocStatus

from frappe.utils import add_days, getdate
from erpnextkta.kta_stock.label_manager import custom_split_kta_batches
from erpnext.controllers.stock_controller import make_quality_inspections
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.stock.get_item_details import get_item_details


class KTAPurchaseReceipt(PurchaseReceipt):

    def validate(self):
        self.update_rates_logic()
        super().validate()
        self._validate_item_rates()

    def validate_with_previous_doc(self):
        try:
            super().validate_with_previous_doc()
        except frappe.ValidationError as e:
            # Bypass strict "Rate must be same as Purchase Order" or similar checks.
            # Kur farkından kaynaklanan sapmalara izin vermek için bu bypass gereklidir.
            # Aynı para birimli sapmalar _validate_item_rates() tarafından yakalanır.
            if "Rate must be same as Purchase Order" in str(e):
                pass
            else:
                raise e

    def _validate_item_rates(self):
        """
        KTA Rate Validation: PR kalemlerinin rate değerlerini kaynak belge (PO/PR) ile karşılaştır.

        Kurallar:
          1. Aynı para birimi (ör. PO EUR → PR EUR):
             PR rate, PO rate'den %MAX_RATE_DEVIATION_PCT üzerinde sapamaz.
             Saparsa kaydet engellenir ve kullanıcıdan düzeltmesi istenir.

          2. Farklı para birimi (ör. PO EUR → PR TRY):
             Kur çevirimi meşru sapma yaratır, bu durum sessizce kabul edilir.
             update_rates_logic() zaten doğru değeri hesaplar.

          3. Kaynak belge (PO/önceki PR) yoksa:
             Doğrulama atlanır (direkt irsaliye senaryosu).
        """
        MAX_RATE_DEVIATION_PCT = 20.0  # %20 tolerans

        for d in self.items:
            po_item_name = d.get("purchase_order_item")
            pr_item_name = d.get("purchase_receipt_item")

            src_rate = None
            src_currency = None

            if po_item_name:
                row = frappe.db.get_value(
                    "Purchase Order Item",
                    po_item_name,
                    ["rate", "parent"],
                    as_dict=True,
                )
                if row and row.rate:
                    src_rate = row.rate
                    src_currency = frappe.db.get_value("Purchase Order", row.parent, "currency")

            elif pr_item_name:
                row = frappe.db.get_value(
                    "Purchase Receipt Item",
                    pr_item_name,
                    ["rate", "parent"],
                    as_dict=True,
                )
                if row and row.rate:
                    src_rate = row.rate
                    src_currency = frappe.db.get_value("Purchase Receipt", row.parent, "currency")

            if not src_rate or not src_currency:
                continue

            if src_currency != self.currency:
                continue

            deviation_pct = abs(d.rate - src_rate) / src_rate * 100
            if deviation_pct > MAX_RATE_DEVIATION_PCT:
                frappe.throw(
                    _("Satır {0} — <b>{1}</b>: Rate değeri <b>{2} {3}</b> kabul edilemez. Kaynak belgeden beklenen: <b>{4} {5}</b> (Sapma: %{6}, izin verilen: %{7}). Fiyatı düzeltin veya önce satın alma siparişini güncelleyin.").format(
                        d.idx, d.item_code, f"{d.rate:.5f}", self.currency, f"{src_rate:.5f}", self.currency, f"{deviation_pct:.1f}", f"{MAX_RATE_DEVIATION_PCT:.0f}"
                    ),
                    title=_("Geçersiz Fiyat"),
                )

    def _get_exchange_rate(self, from_currency, to_currency, date, for_selling, for_buying):
        result = frappe.db.sql("""
            SELECT exchange_rate FROM `tabCurrency Exchange`
            WHERE date <= %s AND from_currency = %s AND to_currency = %s
            AND for_selling = %s AND for_buying = %s
            ORDER BY date DESC LIMIT 1
        """, (date, from_currency, to_currency, for_selling, for_buying))
        return result[0][0] if result else None

    def _update_exchange_rates(self, rate_date, for_selling, for_buying):
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

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

    def update_rates_logic(self):
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

        self._update_exchange_rates(rate_date, for_selling, for_buying)

        if not self.items:
            self.calculate_taxes_and_totals()
            return

        self._update_all_item_rates(rate_date, for_selling, for_buying)
        self.calculate_taxes_and_totals()

    def _update_all_item_rates(self, rate_date, for_selling, for_buying):
        old_doc = None
        old_items_map = {}
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.currency != self.currency:
                old_items_map = {i.name: i for i in old_doc.items}

        existing_item_prices = set()
        if self.buying_price_list and self.supplier:
            rows = frappe.db.sql("""
                SELECT CONCAT(item_code, '|', price_list_rate) FROM `tabItem Price`
                WHERE price_list = %s AND supplier = %s
            """, (self.buying_price_list, self.supplier))
            existing_item_prices = {r[0] for r in rows}

        _po_currency_cache = {}
        _pr_currency_cache = {}
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

        for d in self.items:
            self._update_single_item_rate(d, existing_item_prices, old_doc, old_items_map, company_currency, rate_date, for_selling, for_buying, _po_currency_cache, _pr_currency_cache)

    def _update_single_item_rate(self, d, existing_item_prices, old_doc, old_items_map, company_currency, rate_date, for_selling, for_buying, _po_currency_cache, _pr_currency_cache):
        current_plr = d.price_list_rate or 0.0
        current_rate = d.rate or 0.0

        calc_conversion = 1.0
        if self.price_list_currency and self.currency and self.price_list_currency != self.currency:
            if self.plc_conversion_rate:
                calc_conversion = self.plc_conversion_rate

        discount_factor = 1.0 - ((d.get("discount_percentage") or 0.0) / 100.0)
        expected_rate = current_plr * calc_conversion * discount_factor
        is_detached = abs(current_rate - expected_rate) > 0.01

        is_manual_plr = False
        if not is_detached and current_plr > 0 and self.buying_price_list:
            key = f"{d.item_code}|{current_plr}"
            is_manual_plr = key not in existing_item_prices

        if is_detached or is_manual_plr:
            po_rate = None
            po_currency = None
            pr_orig_rate = None
            pr_orig_currency = None

            if d.get("purchase_order_item"):
                po_item = frappe.db.get_value("Purchase Order Item", d.purchase_order_item, ["rate", "parent"], as_dict=True)
                if po_item:
                    parent = po_item.parent
                    if parent not in _po_currency_cache:
                        _po_currency_cache[parent] = frappe.db.get_value("Purchase Order", parent, "currency")
                    po_currency = _po_currency_cache[parent]
                    if po_currency:
                        po_rate = po_item.rate

            elif d.get("purchase_receipt_item"):
                pr_item = frappe.db.get_value("Purchase Receipt Item", d.purchase_receipt_item, ["rate", "parent"], as_dict=True)
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
                old_item = old_items_map.get(d.name)
                if old_item:
                    old_currency = old_doc.currency
                    old_conversion_rate = old_doc.conversion_rate
                    old_rate = old_item.rate

                    if po_currency and po_rate and old_currency != po_currency and abs(old_rate - po_rate) < 0.001 and self.currency == po_currency:
                        d.rate = po_rate
                        old_rate = None
                    elif pr_orig_currency and pr_orig_rate and old_currency != pr_orig_currency and abs(old_rate - pr_orig_rate) < 0.001 and self.currency == pr_orig_currency:
                        d.rate = pr_orig_rate
                        old_rate = None

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
                difference = abs(d.rate - old_rate)
                difference_converted = abs(d.rate - correct_new_rate)
                difference_bad1 = abs(d.rate - (old_rate / self.conversion_rate))
                if difference < 0.001 or difference_converted < 0.001 or difference_bad1 < 0.001:
                    d.rate = correct_new_rate

            d.amount = d.rate * d.qty
            d.net_rate = d.rate
            d.net_amount = d.amount
            d.base_rate = d.rate * self.conversion_rate
            d.base_amount = d.amount * self.conversion_rate
            d.base_net_rate = d.net_rate * self.conversion_rate
            d.base_net_amount = d.net_amount * self.conversion_rate
            return

        args = {
            "item_code": d.item_code,
            "warehouse": d.warehouse,
            "supplier": self.supplier,
            "price_list": self.buying_price_list,
            "price_list_currency": self.price_list_currency,
            "plc_conversion_rate": self.plc_conversion_rate,
            "company": self.company,
            "transaction_date": rate_date,
            "currency": self.currency,
            "conversion_rate": self.conversion_rate,
            "qty": d.qty,
            "doctype": "Purchase Receipt",
            "name": self.name,
            "ignore_pricing_rule": 0
        }

        try:
            details = get_item_details(args)
            if details:
                if details.get("price_list_rate"):
                    d.price_list_rate = details.get("price_list_rate")
                    d.rate = details.get("rate") or d.price_list_rate
                if details.get("discount_percentage"):
                    d.discount_percentage = details.get("discount_percentage")
                d.amount = d.rate * d.qty
                d.base_rate = d.rate * self.conversion_rate
                d.base_amount = d.amount * self.conversion_rate
                d.net_rate = d.rate
                d.net_amount = d.amount
                d.base_net_rate = d.net_rate * self.conversion_rate
                d.base_net_amount = d.net_amount * self.conversion_rate
        except Exception as e:
            frappe.log_error(f"KTAPurchaseReceipt Rate Update Error: {str(e)}", "KTAPurchaseReceipt")

    def verify_batch(self):
        errors = []
        for d in self.get("items"):
            if d.custom_do_not_split == 0:
                item_has_batch_no = frappe.db.get_value("Item", {"name": d.item_code},
                                                        "has_batch_no")
                if item_has_batch_no == 1:
                    split_qty = d.custom_split_qty
                    if not split_qty or split_qty <= 0:
                        errors.append(
                            _("<b>Satır {0} ({1})</b>: Lütfen bu ürün için geçerli bir <b>Bölme Miktarı (Kutu İçi Adedi)</b> giriniz. Bu değer 0'dan büyük olmalıdır.").format(d.idx, d.item_code)
                        )
        if errors:
            frappe.throw("<br>".join(errors), title=_("Eksik Kutu İçi Adedi Bilgisi"))

    def before_insert(self):
        for d in self.items:
            d.use_serial_batch_fields = 0

    def before_save(self):
        for d in self.items:
            d.use_serial_batch_fields = 0

    def validate_items_quality_inspection(self):
        if self.docstatus == DocStatus.cancelled() and self.is_return == 0:
            super().validate_items_quality_inspection()

    def on_submit(self):
        try:
            if self.docstatus == DocStatus.submitted() and self.is_return == 0:
                self.verify_batch()

                qi_items = []
                rows_to_split_now = []

                for d in self.items:
                    doc = frappe.get_doc('Item', d.get("item_code"))
                    self._ensure_base_batch(d, doc)
                    
                    rows_to_split_now.append(d.name)
                    
                    if doc.get("inspection_required_before_purchase"):
                        meta = frappe.get_meta('Item')
                        if meta.has_field('custom_atlama_sayisi'):
                            atlama_sayisi = doc.get("custom_atlama_sayisi")
                            atlama_sirasi = doc.get("custom_atlama_sirasi")
                            if atlama_sayisi > 0:
                                doc.db_set('custom_atlama_sirasi', atlama_sirasi + 1, commit=True)
                                if atlama_sirasi % atlama_sayisi == 0:
                                    qi_items.append(d)
                            else:
                                doc.db_set('custom_atlama_sirasi', 2, commit=True)
                                qi_items.append(d)
                        else:
                            qi_items.append(d)

                # Bundle'ları tek seferde hazırla (split için SLE gerekliydi)
                self.set_serial_and_batch_bundle()

                submitting_user = frappe.session.user

                super().on_submit()

                # Önce Kalite Kontrollerini oluştur ki satırlardaki quality_inspection alanları dolsun
                make_quality_inspections(self.company, self.doctype, self.name, qi_items)

                # Stok kaydı tamamlandıktan sonra batch split ve etiket basımını başlat
                from erpnextkta.kta_stock.label_manager import custom_split_kta_batches
                
                all_created_labels = []
                for row_name in rows_to_split_now:
                    try:
                        # Database'den güncel satırı çekiyoruz, böylece quality_inspection alanı dolu gelecek
                        row_doc = frappe.get_doc("Purchase Receipt Item", row_name)
                        labels = custom_split_kta_batches(row=row_doc, submitting_user=submitting_user, enqueue_print=False)
                        if labels:
                            all_created_labels.extend(labels)
                    except Exception as split_err:
                        import traceback
                        frappe.log_error(
                            f"Split/Print error for row {row_name}: {traceback.format_exc()}",
                            "KTA Split Error"
                        )
                
                if all_created_labels:
                    frappe.enqueue(
                        "erpnextkta.kta_stock.label_manager._print_pr_labels_by_names",
                        label_names=all_created_labels,
                        user=submitting_user or frappe.session.user,
                        queue="short",
                        timeout=120,
                        now=False,
                        enqueue_after_commit=True,
                    )
            else:
                super().on_submit()
        except frappe.exceptions.ValidationError:
            raise
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            frappe.log_error(f"Purchase Receipt Submit Error {str(e)}\n{error_trace}", "Purchase Receipt Submit Error")
            frappe.throw(_("Beklenmeyen bir hata oluştu, işlem yapılamadı. Hata detayları sistem loglarına kaydedildi."))
        finally:
            # flags cleanup (artık kullanılmıyor ama güvenlik için bırakıldı)
            if hasattr(self, "flags"):
                self.flags.kta_rows_to_split = None
                self.flags.kta_submitting_user = None

    def on_cancel(self):
        super().on_cancel()
        for d in self.items:
            doc = frappe.get_doc('Item', d.item_code)
            if doc.get("inspection_required_before_purchase"):
                meta = frappe.get_meta('Item')
                if meta.has_field('custom_atlama_sayisi'):
                    atlama_sayisi = doc.get("custom_atlama_sayisi")
                    atlama_sirasi = doc.get("custom_atlama_sirasi")
                    if atlama_sayisi and atlama_sayisi > 0 and atlama_sirasi and atlama_sirasi > 0:
                        doc.db_set('custom_atlama_sirasi', atlama_sirasi - 1, commit=True)



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
        # Base PurchaseReceipt.update_stock_ledger does not accept via_landed_cost_voucher, swallow it
        super().update_stock_ledger(allow_negative_stock=allow_negative_stock)

    def set_status(self, update=False, status=None, update_modified=True):
        super().set_status(update=update, status=status, update_modified=update_modified)

        if self.docstatus == 1 and self.status not in ["Cancelled", "Closed"]:
            # Check if there are any draft Quality Inspections
            qi_filters = {
                "reference_type": "Purchase Receipt",
                "reference_name": self.name,
                "docstatus": 0
            }
            if getattr(self.flags, "qi_being_deleted", None):
                qi_filters["name"] = ["!=", self.flags.qi_being_deleted]

            has_draft_qi = frappe.db.exists("Quality Inspection", qi_filters)
            if has_draft_qi:
                self.status = "GKK Bekliyor"
                if update:
                    self.db_set("status", self.status, update_modified=update_modified)
