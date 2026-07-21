import frappe
from frappe import _, scrub
from frappe.utils import getdate, add_days, add_to_date
from datetime import date, timedelta
from dateutil.relativedelta import MO, relativedelta

class SatisAnalizi:
    def __init__(self, filters):
        self.filters = frappe._dict(filters or {})

        today = date.today()
        year_start = date(today.year, 1, 1)
        year_end = date(today.year, 12, 31)

        self.filters.from_date = self.filters.get("from_date") or year_start
        self.filters.to_date = self.filters.get("to_date") or year_end
        self.filters.range = self.filters.get("range", "Weekly")
        self.filters.tree_type = self.filters.get("tree_type", "Müşteri")
        self.filters.value_quantity = self.filters.get("value_quantity", "Quantity")
        self.filters.target_currency = self.filters.get("target_currency")
        self.filters.doc_type = "Sales Order"

        self.date_field = "delivery_date"
        self.missing_rates = set()
        self.exchange_rates = self.get_exchange_rates()
        self.set_period_ranges()
        self.columns = []
        self.data = []

    def run(self):
        self.build_columns()
        self.get_data()
        self.calculate_summary_row()

        if self.missing_rates:
            missing_text = "\n".join([f"{fc} → {tc}" for fc, tc in self.missing_rates])
            frappe.msgprint(_("Aşağıdaki döviz dönüşümleri için kur bilgisi bulunamadı:\n{0}").format(missing_text))

        chart = self.get_chart()
        html_summary = self.get_modern_summary_html()
        
        self.append_ui_summary_rows()

        return self.columns, self.data, html_summary, chart, None

    def get_exchange_rates(self):
        if not self.filters.target_currency:
            return {}
            
        rates = frappe.db.sql("""
            SELECT from_currency, to_currency, exchange_rate 
            FROM `tabCurrency Exchange` 
            WHERE to_currency = 'TRY'
            ORDER BY date DESC
        """, as_dict=True)
        
        exchange_map = {}
        for r in rates:
            if r.exchange_rate:
                direct = (r.from_currency, "TRY")
                inverse = ("TRY", r.from_currency)
                if direct not in exchange_map:
                    exchange_map[direct] = r.exchange_rate
                    exchange_map[inverse] = 1 / r.exchange_rate
                    
        from_currencies = list(set(r.from_currency for r in rates))
        for from_cur in from_currencies:
            for to_cur in from_currencies:
                if from_cur != to_cur:
                    try:
                        fx_from = exchange_map[(from_cur, "TRY")]
                        fx_to = exchange_map[(to_cur, "TRY")]
                        exchange_map[(from_cur, to_cur)] = fx_from / fx_to
                    except KeyError: continue
        return exchange_map

    def convert(self, value, from_currency, to_currency=None):
        to_currency = to_currency or self.filters.target_currency
        if not to_currency or from_currency == to_currency:
            return value
        rate = self.exchange_rates.get((from_currency, to_currency))
        if not rate:
            try:
                fx_from = self.exchange_rates[(from_currency, "TRY")]
                fx_to = self.exchange_rates[(to_currency, "TRY")]
                rate = fx_from / fx_to
                self.exchange_rates[(from_currency, to_currency)] = rate
            except KeyError:
                self.missing_rates.add((from_currency, to_currency))
                return 0
        return value * rate

    def set_period_ranges(self):
        from_date = getdate(self.filters.from_date)
        to_date = getdate(self.filters.to_date)
        self.periodic_ranges = []
        increment = {"Monthly": 1, "Quarterly": 3, "Yearly": 12, "Weekly": 0}.get(self.filters.range, 1)
        if self.filters.range == "Monthly":
            from_date = from_date.replace(day=1)
        elif self.filters.range == "Quarterly":
            quarter_start_month = ((from_date.month - 1) // 3) * 3 + 1
            from_date = from_date.replace(month=quarter_start_month, day=1)
        elif self.filters.range == "Yearly":
            from_date = getdate(f"{from_date.year}-01-01")
        elif self.filters.range == "Weekly":
            from_date = from_date + relativedelta(weekday=MO(-1))
        while from_date <= to_date:
            if self.filters.range == "Weekly":
                period_end = add_days(from_date, 6)
            else:
                period_end = add_to_date(from_date, months=increment, days=-1)
            if period_end > to_date:
                period_end = to_date
            self.periodic_ranges.append((from_date, period_end))
            from_date = add_days(period_end, 1)

    def build_columns(self):
        tree_doctype = "Customer" if self.filters.tree_type == "Müşteri" else "Customer Group" if self.filters.tree_type == "Müşteri Grubu" else "Item Group"
        self.columns = [
            {"label": self.filters.tree_type, "fieldname": "tree_key", "fieldtype": "Link", "options": tree_doctype, "width": 150},
            {"label": "Ürün Kodu", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
            {"label": "Ürün Adı", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
            {"label": "Adres", "fieldname": "shipping_address_name", "fieldtype": "Data", "width": 180},
        ]
        self.columns.append({"label": "Birim Fiyat", "fieldname": "rate", "fieldtype": "Currency", "options": "currency", "width": 120})

        if self.filters.value_quantity == "Quantity":
            self.columns.append({"label": "Birim", "fieldname": "uom", "fieldtype": "Data", "width": 100})
            self.columns.append({"label": "Döviz Kuru", "fieldname": "currency", "fieldtype": "Data", "width": 100, "hidden": 1})
        else:
            self.columns.append({"label": "Döviz Kuru", "fieldname": "currency", "fieldtype": "Data", "width": 100})
        column_type = "Float"
        for _, end in self.periodic_ranges:
            label = self.get_period_label(end)
            self.columns.append({"label": label, "fieldname": scrub(label), "fieldtype": column_type, "width": 120})
        self.columns.append({"label": "Toplam", "fieldname": "total", "fieldtype": column_type, "width": 120})

    def get_data(self):
        tree_field = {"Müşteri": "customer", "Müşteri Grubu": "customer_group", "Ürün Grubu": "item_group"}.get(self.filters.tree_type, "customer")
        show_pending_only = self.filters.get("show_pending_only")
        conditions = "so.docstatus = 1 AND so.status NOT IN ('Closed','Completed')"
        values = []
        if self.filters.from_date and self.filters.to_date:
            conditions += f" AND so.{self.date_field} BETWEEN %s AND %s"
            values += [self.filters.from_date, self.filters.to_date]
        if self.filters.tree_key:
            conditions += f" AND so.{tree_field} = %s"
            values.append(self.filters.tree_key)
        if show_pending_only and self.filters.value_quantity == "Quantity":
            conditions += " AND soi.qty > soi.delivered_qty"
        query = f"SELECT so.{tree_field} AS tree_key, so.customer, soi.item_code, soi.item_name, so.name as sales_order, so.shipping_address_name, DATE(so.{self.date_field}) AS posting_date, so.currency, soi.uom, soi.rate, soi.qty, soi.delivered_qty, soi.amount FROM `tabSales Order Item` soi JOIN `tabSales Order` so ON so.name = soi.parent WHERE {conditions}"
        raw_data = frappe.db.sql(query, values, as_dict=True)

        item_prices_data = frappe.db.sql("""
            SELECT `tabItem Price`.item_code, `tabItem Price`.currency, `tabItem Price`.price_list_rate, IFNULL(`tabItem Price`.customer, '') as customer
            FROM `tabItem Price`
            JOIN `tabPrice List` ON `tabPrice List`.name = `tabItem Price`.price_list
            WHERE `tabPrice List`.selling = 1
            ORDER BY IFNULL(`tabItem Price`.valid_from, '1900-01-01') DESC, `tabItem Price`.modified DESC
        """, as_dict=True)
        item_prices = {}
        for ip in item_prices_data:
            if ip.customer:
                key_specific = (ip.item_code, ip.customer)
                if key_specific not in item_prices:
                    item_prices[key_specific] = {"rate": ip.price_list_rate, "currency": ip.currency}
            else:
                key_general = (ip.item_code, '')
                if key_general not in item_prices:
                    item_prices[key_general] = {"rate": ip.price_list_rate, "currency": ip.currency}

        grouped = frappe._dict()
        for row in raw_data:
            period_key = self.get_period_key(row.posting_date)
            if not period_key: continue
            
            delivered_qty = row.delivered_qty or 0
            qty = row.qty or 0
            pending_qty = max(qty - delivered_qty, 0)
            
            parts = []
            
            if not show_pending_only and delivered_qty > 0:
                del_rate = row.rate
                del_currency = row.currency
                if self.filters.target_currency and del_currency != self.filters.target_currency:
                    del_rate = self.convert(del_rate, del_currency, self.filters.target_currency)
                    del_currency = self.filters.target_currency
                    
                parts.append({
                    'rate': del_rate,
                    'qty': delivered_qty,
                    'amount': delivered_qty * del_rate,
                    'currency': del_currency
                })
                
            if pending_qty > 0:
                specific = item_prices.get((row.item_code, row.customer))
                general = item_prices.get((row.item_code, ''))
                
                if specific is not None:
                    current_rate = specific['rate']
                    part_currency = specific['currency']
                elif general is not None:
                    current_rate = general['rate']
                    part_currency = general['currency']
                else:
                    current_rate = row.rate
                    part_currency = row.currency
                    
                if self.filters.target_currency and part_currency != self.filters.target_currency:
                    current_rate = self.convert(current_rate, part_currency, self.filters.target_currency)
                    part_currency = self.filters.target_currency
                    
                parts.append({
                    'rate': current_rate,
                    'qty': pending_qty,
                    'amount': pending_qty * current_rate,
                    'currency': part_currency
                })
                
            for part in parts:
                val = part['qty'] if self.filters.value_quantity == "Quantity" else part['amount']
                group_key = (row.tree_key, row.item_code, row.item_name, row.shipping_address_name, row.uom, part['currency'], part['rate'])
                if group_key not in grouped: grouped[group_key] = {}
                converted_value = val
                grouped[group_key][period_key] = grouped[group_key].get(period_key, 0) + (converted_value or 0)
            
        for (tree_key, item_code, item_name, shipping_address_name, uom, currency, rate), periods in grouped.items():
            row = {"tree_key": tree_key, "item_code": item_code, "item_name": item_name, "shipping_address_name": shipping_address_name, "uom": uom, "currency": currency, "rate": rate, "indent": 1}
            total = 0
            for _, end in self.periodic_ranges:
                key = scrub(self.get_period_label(end))
                val = periods.get(key)
                if val is not None:
                    row[key] = val
                    total += val
            row["total"] = total
            if self.filters.value_quantity == "Quantity":
                row["total_amount"] = total * (rate or 0)
            else:
                row["total_amount"] = total
            self.data.append(row)

    def calculate_summary_row(self):
        self.summary_row = {"tree_key": "Genel Toplam", "indent": 0}
        total = 0
        for _, end in self.periodic_ranges:
            key = scrub(self.get_period_label(end))
            column_total = sum(row.get(key, 0) for row in self.data if isinstance(row.get(key), (int, float)))
            self.summary_row[key] = column_total
            total += column_total
        self.summary_row["total"] = total
        self.summary_row["total_amount"] = sum(row.get("total_amount", 0) for row in self.data if isinstance(row.get("total_amount"), (int, float)))

    def append_ui_summary_rows(self):
        if not self.data: return
        
        if self.filters.value_quantity == "Quantity":
            row = {"tree_key": "Genel Toplam (Miktar)", "indent": 0}
            total = 0
            for _, end in self.periodic_ranges:
                key = scrub(self.get_period_label(end))
                col_tot = sum(r.get(key, 0) for r in self.data if isinstance(r.get(key), (int, float)))
                row[key] = col_tot
                total += col_tot
            row["total"] = total
            self.data.append(row)
        else:
            currencies = set(r.get("currency", "TRY") for r in self.data)
            sorted_cur = sorted(list(currencies), key=lambda c: (0 if c == "TRY" else 1, c))
            
            for cur in sorted_cur:
                row = {"tree_key": f"Genel Toplam ({cur})", "indent": 0, "currency": cur}
                total = 0
                for _, end in self.periodic_ranges:
                    key = scrub(self.get_period_label(end))
                    col_tot = sum(r.get(key, 0) for r in self.data if isinstance(r.get(key), (int, float)) and r.get("currency", "TRY") == cur)
                    row[key] = col_tot
                    total += col_tot
                row["total"] = total
                self.data.append(row)

    def get_chart(self):
        if not self.data or len(self.data) < 2: return None
        
        labels = []
        for _, end in self.periodic_ranges:
            labels.append(self.get_period_label(end))
            
        datasets = []
        colors = ["#ea580c", "#0284c7", "#16a34a", "#9333ea", "#eab308"]
        
        if self.filters.value_quantity == "Quantity":
            values = []
            for label in labels:
                val = getattr(self, "summary_row", {}).get(scrub(label), 0)
                values.append(round(val, 2) if isinstance(val, (int, float)) else val)
            datasets.append({"name": "Miktar", "values": values})
        else:
            currency_series = {}
            for row in self.data:
                cur = row.get("currency") or "TRY"
                if cur not in currency_series:
                    currency_series[cur] = {}
                for label in labels:
                    period_key = scrub(label)
                    val = row.get(period_key, 0)
                    if isinstance(val, (int, float)):
                        currency_series[cur][period_key] = currency_series[cur].get(period_key, 0) + val
                        
            if not currency_series:
                currency_series["TRY"] = {}
                
            sorted_currencies = sorted(currency_series.keys(), key=lambda c: (0 if c == "TRY" else 1, c))
            for cur in sorted_currencies:
                values = []
                for label in labels:
                    val = currency_series[cur].get(scrub(label), 0)
                    values.append(round(val, 2) if isinstance(val, (int, float)) else val)
                datasets.append({"name": f"Tutar ({cur})", "values": values})
                
        return {
            "data": {"labels": labels, "datasets": datasets},
            "type": "line",
            "colors": colors[:len(datasets)] if datasets else colors
        }

    def get_modern_summary_html(self):
        if not self.data: return None
        
        summary_row = getattr(self, "summary_row", {})
        cards_html = ""
        
        def format_currency(val, cur):
            formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            symbol = "₺" if cur == "TRY" else ("€" if cur == "EUR" else ("$" if cur == "USD" else cur))
            return f"{symbol} {formatted}"

        def format_qty(val):
            formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if formatted.endswith(",00"): formatted = formatted[:-3]
            return formatted

        # Card 1: Toplam Miktar
        if self.filters.value_quantity == "Quantity":
            total_qty = summary_row.get("total", 0)
            cards_html += f"""
                <div class="mrp-summary-card">
                    <div class="mrp-card-icon qty-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
                    </div>
                    <div class="mrp-card-content">
                        <div class="mrp-card-label">TOPLAM MİKTAR</div>
                        <div class="mrp-card-value qty-value">{format_qty(total_qty)}</div>
                    </div>
                </div>
            """
            
        currency_totals = {}
        for row in self.data:
            cur = row.get("currency") or "TRY"
            amt = row.get("total_amount", 0) if self.filters.value_quantity == "Quantity" else row.get("total", 0)
            if isinstance(amt, (int, float)):
                currency_totals[cur] = currency_totals.get(cur, 0) + amt
                
        if not currency_totals:
            cards_html += f"""
                <div class="mrp-summary-card">
                    <div class="mrp-card-icon icon-try">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"></rect><circle cx="12" cy="12" r="2"></circle><path d="M6 12h.01M18 12h.01"></path></svg>
                    </div>
                    <div class="mrp-card-content">
                        <div class="mrp-card-label">TOPLAM TUTAR (TRY)</div>
                        <div class="mrp-card-value currency-value-try">₺ 0,00</div>
                    </div>
                </div>
            """
        else:
            sorted_currencies = sorted(currency_totals.keys(), key=lambda c: (0 if c == "TRY" else 1, c))
            for cur in sorted_currencies:
                amt = currency_totals[cur]
                is_try = cur == "TRY"
                css_class = "currency-value-try" if is_try else "currency-value-foreign"
                cards_html += f"""
                    <div class="mrp-summary-card">
                        <div class="mrp-card-icon {'icon-try' if is_try else 'icon-foreign'}">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"></rect><circle cx="12" cy="12" r="2"></circle><path d="M6 12h.01M18 12h.01"></path></svg>
                        </div>
                        <div class="mrp-card-content">
                            <div class="mrp-card-label">TOPLAM TUTAR ({cur})</div>
                            <div class="mrp-card-value {css_class}">{format_currency(amt, cur)}</div>
                        </div>
                    </div>
                """
                
        row_count = len(self.data)
        cards_html += f"""
            <div class="mrp-summary-card">
                <div class="mrp-card-icon count-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                </div>
                <div class="mrp-card-content">
                    <div class="mrp-card-label">SATIR SAYISI</div>
                    <div class="mrp-card-value count-value">{row_count}</div>
                </div>
            </div>
        """
        
        style = """
        <style>
            .mrp-summary-container {
                display: flex;
                flex-wrap: wrap;
                gap: 16px;
                margin-bottom: 24px;
                padding: 4px 0;
            }
            .mrp-summary-card {
                flex: 1;
                min-width: 240px;
                background: linear-gradient(145deg, #ffffff, #f8fafc);
                border: 1px solid rgba(226, 232, 240, 0.8);
                border-radius: 12px;
                padding: 16px;
                display: flex;
                align-items: center;
                gap: 16px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03), 0 1px 2px rgba(0, 0, 0, 0.02);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }
            .mrp-summary-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06), 0 2px 4px rgba(0, 0, 0, 0.04);
            }
            .mrp-card-icon {
                width: 48px;
                height: 48px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }
            .qty-icon { background: #dcfce7; color: #16a34a; }
            .count-icon { background: #f3e8ff; color: #9333ea; }
            .icon-try { background: #ffedd5; color: #ea580c; }
            .icon-foreign { background: #e0f2fe; color: #0284c7; }
            
            .mrp-card-content {
                display: flex;
                flex-direction: column;
                gap: 2px;
            }
            .mrp-card-label {
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                color: #64748b;
                text-transform: uppercase;
            }
            .mrp-card-value {
                font-size: 20px;
                font-weight: 800;
                line-height: 1.2;
                letter-spacing: -0.5px;
            }
            .qty-value { color: #16a34a; }
            .count-value { color: #9333ea; }
            .currency-value-try { color: #ea580c; }
            .currency-value-foreign { color: #0284c7; }
        </style>
        """
        
        return f"{style}<div class='mrp-summary-container'>{cards_html}</div>"


    def get_period_key(self, date_obj):
        for start, end in self.periodic_ranges:
            if start <= date_obj <= end: return scrub(self.get_period_label(end))
        return None

    def get_period_label(self, date):
        if self.filters.range == "Monthly": return f"{date.strftime('%b')} {date.year}"
        elif self.filters.range == "Quarterly": return f"Q{(date.month - 1) // 3 + 1} {date.year}"
        elif self.filters.range == "Weekly":
            iso_year, iso_week, _ = date.isocalendar()
            return f"{iso_year}-W{iso_week:02d}"
        else: return str(date.year)

def execute(filters=None):
    return SatisAnalizi(filters).run()