import frappe
from frappe import scrub
from frappe.utils import getdate, add_days, add_to_date, nowdate
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
        self.append_summary_row()

        if self.missing_rates:
            missing_text = "\n".join([f"{fc} → {tc}" for fc, tc in self.missing_rates])
            frappe.msgprint(f"Aşağıdaki döviz dönüşümleri için kur bilgisi bulunamadı:\n{missing_text}")

        return self.columns, self.data, None, None, None, 1

    def get_exchange_rates(self):
        if not self.filters.target_currency:
            return {}

        exchange_date = (date.today() - timedelta(days=1)).strftime("%d-%m-%Y")

        rates = frappe.get_all(
            "Currency Exchange",
            filters={
                "date": exchange_date,
                "to_currency": "TRY",
                "for_buying": 1
            },
            fields=["from_currency", "to_currency", "exchange_rate"]
        )

        exchange_map = {}

        for r in rates:
            if r.exchange_rate:
                direct = (r.from_currency, "TRY")
                inverse = ("TRY", r.from_currency)
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
                    except KeyError:
                        continue

        return exchange_map

    def convert(self, value, from_currency):
        to_currency = self.filters.target_currency
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

        increment = {"Monthly": 1, "Quarterly": 3, "Weekly": 0}.get(self.filters.range, 1)

        if self.filters.range in ["Monthly", "Quarterly"]:
            from_date = from_date.replace(day=1)
        elif self.filters.range == "Yearly":
            from_date = getdate(f"{from_date.year}-01-01")
        elif self.filters.range == "Weekly":
            from_date = from_date + relativedelta(from_date, weekday=MO(-1))

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
        if self.filters.tree_type == "Müşteri":
            tree_doctype = "Customer"
        elif self.filters.tree_type == "Müşteri Grubu":
            tree_doctype = "Customer Group"
        elif self.filters.tree_type == "Ürün Grubu":
            tree_doctype = "Item Group"
        else:
            tree_doctype = "Customer"

        self.columns = [
            {
                "label": self.filters.tree_type,
                "fieldname": "tree_key",
                "fieldtype": "Link",
                "options": tree_doctype,
                "width": 150,
            },
            {
                "label": "Ürün Kodu",
                "fieldname": "item_code",
                "fieldtype": "Link",
                "options": "Item",
                "width": 120,
            },
            {
                "label": "Ürün Adı",
                "fieldname": "item_name",
                "fieldtype": "Data",
                "width": 180,
            },
            {
                "label": "Adres",
                "fieldname": "shipping_address_name",
                "fieldtype": "Data",
                "width": 180,
            },
        ]

        if self.filters.value_quantity == "Quantity":
            self.columns.append({
                "label": "Birim",
                "fieldname": "uom",
                "fieldtype": "Data",
                "width": 100,
            })
        else:
            self.columns.append({
                "label": "Döviz Kuru",
                "fieldname": "currency",
                "fieldtype": "Data",
                "width": 100,
            })

        column_type = "Int" if self.filters.value_quantity == "Quantity" else "Float"
        for _, end in self.periodic_ranges:
            label = self.get_period_label(end)
            self.columns.append({
                "label": label,
                "fieldname": scrub(label),
                "fieldtype": column_type,
                "width": 120,
            })

        self.columns.append({
            "label": "Toplam",
            "fieldname": "total",
            "fieldtype": column_type,
            "width": 120,
        })

    def get_data(self):
        tree_field = {
            "Müşteri": "customer",
            "Müşteri Grubu": "customer_group",
            "Ürün Grubu": "item_group"
        }.get(self.filters.tree_type, "customer")

        show_pending_only = self.filters.get("show_pending_only")

        value_expr = (
            "GREATEST(soi.qty - soi.delivered_qty, 0)"
            if show_pending_only and self.filters.value_quantity == "Quantity"
            else "soi.amount" if not show_pending_only and self.filters.value_quantity != "Quantity"
            else "GREATEST(soi.qty - soi.delivered_qty, 0) * soi.rate"
            if self.filters.value_quantity != "Quantity" else "soi.qty"
        )

        conditions = "so.docstatus = 1 AND so.status NOT IN ('Closed','Completed','Cancelled')"
        values = []

        if self.filters.from_date and self.filters.to_date:
            conditions += f" AND so.{self.date_field} BETWEEN %s AND %s"
            values += [self.filters.from_date, self.filters.to_date]

        if self.filters.tree_key:
            conditions += f" AND so.{tree_field} = %s"
            values.append(self.filters.tree_key)

        if show_pending_only and self.filters.value_quantity == "Quantity":
            conditions += " AND soi.qty > soi.delivered_qty"

        query = f"""
            SELECT 
                so.{tree_field} AS tree_key,
                soi.item_code,
                soi.item_name,
                so.name as sales_order,
                so.shipping_address_name,
                DATE(so.{self.date_field}) AS posting_date,
                {value_expr} AS value,
                so.currency,
                soi.uom
            FROM `tabSales Order Item` soi
            JOIN `tabSales Order` so ON so.name = soi.parent
            WHERE {conditions}
        """

        raw_data = frappe.db.sql(query, values, as_dict=True)

        grouped = frappe._dict()
        for row in raw_data:
            period_key = self.get_period_key(row.posting_date)
            if not period_key:
                continue

            extra_key = row.currency if self.filters.value_quantity != "Quantity" else row.uom
            group_key = (row.tree_key, row.item_code, row.item_name, row.shipping_address_name, extra_key)

            if group_key not in grouped:
                grouped[group_key] = {}

            converted_value = self.convert(row.value, row.currency) if self.filters.value_quantity != "Quantity" else row.value
            grouped[group_key][period_key] = grouped[group_key].get(period_key, 0) + (converted_value or 0)

        for (tree_key, item_code, item_name, shipping_address_name, extra_value), periods in grouped.items():
            row = {
                "tree_key": tree_key,
                "item_code": item_code,
                "item_name": item_name,
                "shipping_address_name": shipping_address_name,
                "indent": 1,
            }
            if self.filters.value_quantity == "Quantity":
                row["uom"] = extra_value
            else:
                row["currency"] = extra_value

            total = 0
            for _, end in self.periodic_ranges:
                key = scrub(self.get_period_label(end))
                val = periods.get(key)
                if val is not None:
                    row[key] = int(val) if self.filters.value_quantity == "Quantity" else val
                    total += val
            row["total"] = int(total) if self.filters.value_quantity == "Quantity" else total
            self.data.append(row)

    def append_summary_row(self):
        summary_row = {
            "tree_key": frappe._("GENEL TOPLAM"),
            "indent": 0,
        }
        total = 0

        for _, end in self.periodic_ranges:
            key = scrub(self.get_period_label(end))
            column_total = sum(row.get(key, 0) for row in self.data if isinstance(row.get(key), (int, float)))
            summary_row[key] = int(column_total) if self.filters.value_quantity == "Quantity" else column_total
            total += column_total

        summary_row["total"] = int(total) if self.filters.value_quantity == "Quantity" else total
        self.data.append(summary_row)

    def get_period_key(self, date_obj):
        for start, end in self.periodic_ranges:
            if start <= date_obj <= end:
                return scrub(self.get_period_label(end))
        return None

    def get_period_label(self, date):
        if self.filters.range == "Monthly":
            return f"{date.strftime('%b')} {date.year}"
        elif self.filters.range == "Quarterly":
            quarter = (date.month - 1) // 3 + 1
            return f"Q{quarter} {date.year}"
        elif self.filters.range == "Weekly":
            week_number = date.isocalendar()[1]
            return f"W{week_number:02d} {date.year}"
        else:
            return str(date.year)

def execute(filters=None):
    return SatisAnalizi(filters).run()
