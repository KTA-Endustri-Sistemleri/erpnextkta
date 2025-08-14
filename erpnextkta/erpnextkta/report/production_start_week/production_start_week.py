import frappe
from frappe import _, scrub
from frappe.utils import getdate, add_days
from datetime import date
from dateutil.relativedelta import MO, relativedelta
from collections import defaultdict

from erpnextkta.erpnextkta.report.periodic_sales_orders import periodic_sales_orders


class ProductionStartWeekReport:
    def __init__(self, filters):
        self.filters = frappe._dict(filters or {})
        today = date.today()

        self.filters.from_date = self.filters.get("from_date") or date(today.year, 1, 1)
        self.filters.to_date = self.filters.get("to_date") or date(today.year, 12, 31)
        self.filters.range = self.filters.get("range", "Weekly")
        self.filters.tree_type = self.filters.get("tree_type", "Müşteri")
        self.filters.group_by_item_only = int(self.filters.get("group_by_item_only", 0))
        self.filters.doc_type = "Sales Order"

        self.set_period_ranges()
        self.columns = []
        self.data = []
        self.grouped = frappe._dict()
        self.sevk_map = self.get_sevk_parametreleri_map()
        self.stock_map = self.get_initial_stock_balance()
        self.weekly_demand_by_item = defaultdict(lambda: defaultdict(int))
        self.eşleşmeyen_müşteriler = set()
        self.debug_info = []

    def run(self):
        self.build_columns()
        self.get_data()
        self.apply_stock_consumption()

        if self.debug_info:
            # debug_msg = "<br>".join(self.debug_info[:50])
            # frappe.msgprint(f"Debug Bilgileri:<br>{debug_msg}")
            pass

        if self.eşleşmeyen_müşteriler:
            example_list = list(self.eşleşmeyen_müşteriler)[:10]
            frappe.msgprint(
                f"KTA Sevk Parametreleri'nde eşleşmeyen müşteriler (ilk 10):<br><br>"
                + "<br>".join(example_list)
            )

        return self.columns, self.data, None, None, None, 1

    def set_period_ranges(self):
        from_date = getdate(self.filters.from_date)
        to_date = getdate(self.filters.to_date)
        self.periodic_ranges = []

        if self.filters.range == "Weekly":
            from_date = from_date + relativedelta(from_date, weekday=MO(-1))

        while from_date <= to_date:
            period_end = add_days(from_date, 6)
            if period_end > to_date:
                period_end = to_date
            self.periodic_ranges.append((from_date, period_end))
            from_date = add_days(period_end, 1)

    def build_columns(self):
        tree_doctype = {
            "Müşteri": "Customer",
            "Müşteri Grubu": "Customer Group"
        }.get(self.filters.tree_type, "Customer")

        self.columns = [
            {"label": "Ürün Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 120},
            {"label": "Ürün Kodu", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
            {"label": "Ürün Adı", "fieldname": "item_name", "fieldtype": "Data", "width": 180}
        ]

        if not self.filters.group_by_item_only:
            self.columns.insert(1, {
                "label": self.filters.tree_type,
                "fieldname": "tree_key",
                "fieldtype": "Link",
                "options": tree_doctype,
                "width": 150
            })

        for _, end in self.periodic_ranges:
            label = self.get_period_label(end)
            self.columns.append({
                "label": label,
                "fieldname": scrub(label),
                "fieldtype": "Int",
                "width": 120
            })

        self.columns += [
            {"label": "Stok Karşılanan", "fieldname": "stock_covered", "fieldtype": "Int", "width": 100},
            {"label": "Üretilecek", "fieldname": "to_produce", "fieldtype": "Int", "width": 100},
            {"label": "Toplam", "fieldname": "total", "fieldtype": "Int", "width": 120},
            {"label": "Birim", "fieldname": "unit", "fieldtype": "Data", "width": 80}
        ]

    def get_data(self):
        all_items = frappe.get_all("Item", fields=["name", "item_group"])
        item_group_map = {item.name: item.item_group or "" for item in all_items}
        item_group_filter = self.filters.get("item_group")

        periodic_filters = {
            "from_date": self.filters.from_date,
            "to_date": self.filters.to_date,
            "range": self.filters.range,
            "tree_type": self.filters.tree_type,
            "tree_key": self.filters.get("tree_key"),
            "item_group": self.filters.get("item_group"),
            "show_pending_only": 1,
            "value_quantity": "Quantity"
        }

        report_instance = periodic_sales_orders.SatisAnalizi(periodic_filters)
        _, source_data, *_ = report_instance.run()

        if not source_data:
            frappe.msgprint("periodic_sales_orders raporundan hiç veri gelmedi.")
            return

        for row in source_data:
            item_code = row.get("item_code")
            if not item_code:
                continue

            item_group = item_group_map.get(item_code, "")
            if item_group_filter and item_group != item_group_filter:
                continue

            tree_key = row.get("tree_key") or "Genel"
            item_name = row.get("item_name")
            group_key = (
                None if self.filters.group_by_item_only else tree_key,
                item_code, item_name, item_group
            )

            for _, end in self.periodic_ranges:
                label = self.get_period_label(end)
                key = scrub(label)
                val = row.get(key, 0)
                if val:
                    self.weekly_demand_by_item[group_key][label] += int(val)

    def apply_stock_consumption(self):
        if self.filters.group_by_item_only:
            for (tree_key, item_code, item_name, item_group), week_map in self.weekly_demand_by_item.items():
                stock = self.stock_map.get(item_code, 0)
                row = {
                    "item_group": item_group,
                    "tree_key": tree_key if tree_key else "Genel",
                    "item_code": item_code,
                    "item_name": item_name,
                    "unit": "Adet",
                    "indent": 1
                }
                total = 0
                stock_used = 0
                to_produce = 0
                for _, end in self.periodic_ranges:
                    label = self.get_period_label(end)
                    key = scrub(label)
                    demand = week_map.get(label, 0)
                    if not demand:
                        continue
                    covered = min(stock, demand)
                    stock -= covered
                    stock_used += covered
                    need_production = demand - covered
                    to_produce += need_production
                    row[key] = need_production
                    total += demand
                row["stock_covered"] = stock_used
                row["to_produce"] = to_produce
                row["total"] = total
                if total:
                    self.data.append(row)
            return

        grouped_rows = defaultdict(list)
        for group_key, week_map in self.weekly_demand_by_item.items():
            grouped_rows[group_key[1]].append((group_key, week_map))

        for item_code, rows in grouped_rows.items():
            stock = self.stock_map.get(item_code, 0)
            total_demand_by_week = defaultdict(int)
            for _, week_map in rows:
                for label, val in week_map.items():
                    total_demand_by_week[label] += val

            stock_coverage_by_week = {}
            for _, end in self.periodic_ranges:
                label = self.get_period_label(end)
                demand = total_demand_by_week.get(label, 0)
                covered = min(stock, demand)
                stock_coverage_by_week[label] = covered
                stock -= covered
                if stock <= 0:
                    break

            for (tree_key, _, item_name, item_group), week_map in rows:
                row = {
                    "item_group": item_group,
                    "tree_key": tree_key or "Genel",
                    "item_code": item_code,
                    "item_name": item_name,
                    "unit": "Adet",
                    "indent": 1
                }
                total = 0
                stock_used = 0
                to_produce = 0
                for _, end in self.periodic_ranges:
                    label = self.get_period_label(end)
                    key = scrub(label)
                    demand = week_map.get(label, 0)
                    if not demand:
                        continue
                    available = stock_coverage_by_week.get(label, 0)
                    covered = min(demand, available)
                    stock_coverage_by_week[label] = max(0, available - covered)
                    stock_used += covered
                    production = demand - covered
                    to_produce += production
                    total += demand
                    row[key] = production
                row["stock_covered"] = stock_used
                row["to_produce"] = to_produce
                row["total"] = total
                if total:
                    self.data.append(row)

    def get_initial_stock_balance(self):
        from erpnext.stock.report.stock_balance.stock_balance import execute as stock_balance_execute

        stock_filters = frappe._dict({
            "from_date": self.filters.from_date,
            "to_date": self.filters.to_date,
            "company": self.filters.get("company") or "KTA ENDÜSTRİ SİSTEMLERİ SANAYİ VE TİCARET LİMİTED ŞİRKETİ"
        })

        columns, data = stock_balance_execute(stock_filters)[:2]
        item_stock = frappe._dict()
        for row in data:
            item_code = row.get("item_code")
            balance_qty = row.get("bal_qty", 0)
            if item_code:
                item_stock[item_code] = item_stock.get(item_code, 0) + balance_qty
        return item_stock

    def get_sevk_parametreleri_map(self):
        records = frappe.get_all(
            "KTA Sevk Parametreleri",
            fields=["name", "production_time", "delivery_time"]
        )

        sevk_map = {}
        for r in records:
            sevk_map[r.name] = {
                "production_time": r.production_time or 0,
                "delivery_time": r.delivery_time or 0
            }
        return sevk_map

    def get_period_label(self, date_obj):
        if not date_obj:
            return None
        try:
            if isinstance(date_obj, str):
                date_obj = getdate(date_obj)
            return f"W{date_obj.isocalendar()[1]:02d} {date_obj.year}"
        except Exception as e:
            frappe.log_error(f"Period label error: {e}")
            return None

    def get_week_end_from_label(self, label):
        try:
            if not label or not isinstance(label, str):
                return None
            parts = label.split()
            if len(parts) < 2:
                return None
            week = int(parts[0].lstrip("W"))
            year = int(parts[1])
            monday = date.fromisocalendar(year, week, 1)
            return add_days(monday, 6)
        except Exception as e:
            frappe.log_error(f"Week end parsing error: {e} for label: {label}")
            return None


def execute(filters=None):
    return ProductionStartWeekReport(filters).run()


@frappe.whitelist()
def get_item_groups(from_date=None, to_date=None):
    from frappe.utils import getdate

    if frappe.form_dict.get("group_by_item_only") == "1":
        return []

    from_date = getdate(from_date)
    to_date = getdate(to_date)

    query = """
        SELECT DISTINCT soi.item_group
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE so.docstatus = 1
          AND soi.delivery_date BETWEEN %s AND %s
          AND soi.qty > IFNULL(soi.delivered_qty, 0)
    """
    results = frappe.db.sql(query, (from_date, to_date), as_dict=True)
    return sorted({r.item_group for r in results if r.item_group})
