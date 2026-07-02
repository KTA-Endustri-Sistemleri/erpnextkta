import frappe
from frappe import _, scrub
from frappe.utils import getdate, add_days
from datetime import date
from dateutil.relativedelta import MO, relativedelta
from collections import defaultdict

from erpnextkta.kta_mrp.report.periodic_sales_orders import periodic_sales_orders

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

    def run(self):
        self.build_columns()
        self.get_data()
        self.apply_stock_consumption()

        if self.eşleşmeyen_müşteriler:
            example_list = list(self.eşleşmeyen_müşteriler)[:10]
            frappe.msgprint(_("KTA Sevk Parametreleri'nde eşleşmeyen müşteri/adres kayıtları (ilk 10):<br><br>{0}").format("<br>".join(example_list)))

        chart = self.get_chart()
        summary = self.get_summary()

        return self.columns, self.data, None, chart, summary

    def set_period_ranges(self):
        from_date = getdate(self.filters.from_date)
        to_date = getdate(self.filters.to_date)
        self.periodic_ranges = []
        if self.filters.range == "Weekly":
            from_date = from_date + relativedelta(from_date, weekday=MO(-1))
        while from_date <= to_date:
            period_end = add_days(from_date, 6)
            if period_end > to_date: period_end = to_date
            self.periodic_ranges.append((from_date, period_end))
            from_date = add_days(period_end, 1)

    def build_columns(self):
        tree_doctype = {"Müşteri": "Customer", "Müşteri Grubu": "Customer Group"}.get(self.filters.tree_type, "Customer")
        self.columns = [
            {"label": "Ürün Grubu", "fieldname": "item_group", "fieldtype": "Data", "width": 120},
            {"label": "Ürün Kodu", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
            {"label": "Ürün Adı", "fieldname": "item_name", "fieldtype": "Data", "width": 180}
        ]
        if not self.filters.group_by_item_only:
            self.columns.insert(1, {"label": self.filters.tree_type, "fieldname": "tree_key", "fieldtype": "Link", "options": tree_doctype, "width": 150})
        for _, end in self.periodic_ranges:
            label = self.get_period_label(end)
            self.columns.append({"label": label, "fieldname": scrub(label), "fieldtype": "Int", "width": 120})
        self.columns += [
            {"label": "Stok Karşılanan", "fieldname": "stock_covered", "fieldtype": "Int", "width": 100},
            {"label": "Üretilecek", "fieldname": "to_produce", "fieldtype": "Int", "width": 100},
            {"label": "Toplam", "fieldname": "total", "fieldtype": "Int", "width": 120},
            {"label": "Birim", "fieldname": "unit", "fieldtype": "Data", "width": 80}
        ]

    def get_production_start_date(self, delivery_date, customer_name, shipping_address=None):
        if not delivery_date: return delivery_date
        delivery_date = getdate(delivery_date)
        sevk_params = self.sevk_map.get(customer_name) or self.sevk_map.get(shipping_address)
        if not sevk_params:
            key_for_log = shipping_address or customer_name
            if key_for_log: self.eşleşmeyen_müşteriler.add(key_for_log)
            return delivery_date
        total_days = int(sevk_params.get("production_time") or 0) + int(sevk_params.get("delivery_time") or 0)
        return add_days(delivery_date, -total_days) if total_days > 0 else delivery_date

    def get_data(self):
        all_items = frappe.get_all("Item", fields=["name", "item_group"])
        item_group_map = {item.name: item.item_group or "" for item in all_items}
        item_group_filter = self.filters.get("item_group")
        periodic_filters = {
            "from_date": self.filters.from_date, "to_date": self.filters.to_date, "range": self.filters.range,
            "tree_type": self.filters.tree_type, "tree_key": self.filters.get("tree_key"), "item_group": self.filters.get("item_group"),
            "show_pending_only": 1, "value_quantity": "Quantity"
        }
        report_instance = periodic_sales_orders.SatisAnalizi(periodic_filters)
        _, source_data, *_ = report_instance.run()
        if not source_data: return
        for row in source_data:
            item_code = row.get("item_code")
            if not item_code: continue
            item_group = item_group_map.get(item_code, "")
            if item_group_filter and item_group != item_group_filter: continue
            tree_key = row.get("tree_key") or "Genel"
            group_key = (None if self.filters.group_by_item_only else tree_key, item_code, row.get("item_name"), item_group)
            for _, end in self.periodic_ranges:
                label = self.get_period_label(end)
                val = row.get(scrub(label), 0)
                if val:
                    prod_start = self.get_production_start_date(end, tree_key, row.get("shipping_address_name"))
                    prod_label = self.get_period_label(prod_start)
                    self.weekly_demand_by_item[group_key][prod_label or label] += int(val)

    def apply_stock_consumption(self):
        item_rows = defaultdict(list)
        for group_key, week_map in self.weekly_demand_by_item.items():
            item_rows[group_key[1]].append((group_key, week_map))

        for item_code, rows in item_rows.items():
            stock = self.stock_map.get(item_code, 0)
            total_by_week = defaultdict(int)
            for _, week_map in rows:
                for label, val in week_map.items(): total_by_week[label] += val
            
            coverage_by_week = {}
            for _, end in self.periodic_ranges:
                label = self.get_period_label(end)
                demand = total_by_week.get(label, 0)
                covered = min(stock, demand)
                coverage_by_week[label] = covered
                stock -= covered

            for (tree_key, _, item_name, item_group), week_map in rows:
                row = {"item_group": item_group, "tree_key": tree_key or "Genel", "item_code": item_code, "item_name": item_name, "unit": "Adet", "indent": 1}
                total = stock_used = to_produce = 0
                for _, end in self.periodic_ranges:
                    label = self.get_period_label(end)
                    demand = week_map.get(label, 0)
                    if not demand: continue
                    available = coverage_by_week.get(label, 0)
                    covered = min(demand, available)
                    coverage_by_week[label] -= covered
                    stock_used += covered
                    production = demand - covered
                    
                    # Müşteriye özel paketleme yuvarlaması
                    if production > 0:
                        packing = self.get_customer_packing(item_code, tree_key)
                        if packing > 1:
                            import math
                            rounded_production = math.ceil(production / packing) * packing
                            surplus = rounded_production - production
                            # Fazlalığı bir sonraki haftalarda kullanılmak üzere mevcut stoğa ekle
                            available += surplus 
                            production = rounded_production
                            
                    to_produce += production
                    total += demand # Orijinal talebi koruyoruz
                    row[scrub(label)] = production
                row["stock_covered"] = stock_used
                row["to_produce"] = to_produce
                row["total"] = total
                if total: self.data.append(row)

    def get_chart(self):
        labels = [self.get_period_label(end) for _, end in self.periodic_ranges]
        to_produce_vals = []
        stock_covered_vals = []
        for l in labels:
            key = scrub(l)
            to_produce_vals.append(sum(row.get(key, 0) for row in self.data))
            stock_covered_vals.append(sum(row.get("stock_covered", 0) for row in self.data if l == self.get_period_label(row.get("some_date_field")))) # Simplified
        
        # More accurate chart values
        prod_totals = {l: 0 for l in labels}
        for row in self.data:
            for l in labels: prod_totals[l] += row.get(scrub(l), 0)
            
        return {
            "data": {"labels": labels, "datasets": [{"name": "Üretilecek", "values": [prod_totals[l] for l in labels]}]},
            "type": "bar",
            "colors": ["#e67e22"]
        }

    def get_summary(self):
        total_prod = sum(row.get("to_produce", 0) for row in self.data)
        total_stock = sum(row.get("stock_covered", 0) for row in self.data)
        return [
            {"value": total_prod, "label": "Toplam Üretilecek", "indicator": "Orange"},
            {"value": total_stock, "label": "Stoktan Karşılanan", "indicator": "Green"}
        ]

    def get_initial_stock_balance(self):
        # Eğer filtrelerde depo seçilmişse onları kullan
        warehouses = self.filters.get("warehouses")
        
        if not warehouses:
            # Seçim yoksa eski mantıkla 'Kullanılabilir Stok' tipindeki depoları bul
            warehouses = frappe.get_all("Warehouse", filters={"warehouse_type": "Kullanılabilir Stok"}, pluck="name")
        
        if not warehouses: return {}
        
        # SQL sorgusunu seçili depolara göre çalıştır
        stock_data = frappe.db.sql("""
            SELECT 
                bin.item_code, 
                SUM(bin.actual_qty) as total_qty 
            FROM `tabBin` bin 
            WHERE bin.warehouse IN %s 
            GROUP BY bin.item_code
        """, [tuple(warehouses)], as_dict=True)
        
        return {d.item_code: d.total_qty for d in stock_data}

    def get_customer_packing(self, item_code, customer):
        if not hasattr(self, "_packing_cache"): self._packing_cache = {}
        key = (item_code, customer)
        if key in self._packing_cache: return self._packing_cache[key]
        
        packing = frappe.db.get_value("Item Customer", 
            {"parent": item_code, "customer_name": customer}, 
            "custom_musteri_paketleme_miktari") or 1
            
        self._packing_cache[key] = float(packing)
        return self._packing_cache[key]

    def get_sevk_parametreleri_map(self):
        records = frappe.get_all("KTA Sevk Parametreleri", fields=["customer_name", "customer_address", "production_time", "delivery_time"])
        sevk_map = {}
        for r in records:
            val = {"production_time": r.production_time or 0, "delivery_time": r.delivery_time or 0}
            if r.customer_name: sevk_map[r.customer_name] = val
            if r.customer_address: sevk_map[r.customer_address] = val
        return sevk_map

    def get_period_label(self, date_obj):
        if not date_obj: return None
        date_obj = getdate(date_obj)
        iso_year, iso_week, _ = date_obj.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

def execute(filters=None):
    return ProductionStartWeekReport(filters).run()
