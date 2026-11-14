# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import frappe
from erpnextkta.mrp_simulation.cleaner import clean
from erpnextkta.mrp_simulation.constants import (
	COMPANY,
	CUSTOMERS,
	FINISHED_GOODS,
	ITEM_GROUP_FG,
	ITEM_GROUP_RM,
	OPERATIONS,
	RAW_MATERIALS,
	SUPPLIERS,
	WAREHOUSE_FG,
	WAREHOUSE_RM,
	WAREHOUSE_WIP,
	WORKSTATIONS,
)
from erpnextkta.mrp_simulation.dates import get_simulation_dates
from erpnextkta.kta_mrp.mrp_engine.settings import get_mrp_settings


def ensure_mrp_settings():
	"""Ensures KTA MRP Settings is initialized with expected baseline simulation parameters."""
	if not frappe.db.exists("DocType", "KTA MRP Settings"):
		return
	doc = frappe.get_single("KTA MRP Settings")
	doc.enable_leveling_by_default = 1
	doc.enable_rampup_by_default = 1
	doc.default_rampup_weeks = 3
	doc.rampup_trigger_utilization = 70.0
	doc.rampup_max_capacity_limit = 95.0
	doc.min_smoothing_qty = 10
	doc.planning_horizon_days = 90
	doc.backlog_lookback_days = 270
	doc.default_production_time_days = 14
	doc.default_delivery_time_days = 2
	doc.urgent_shortage_weeks = 4
	doc.available_warehouse_type = "Kullanılabilir Stok"
	doc.default_include_po = 1
	doc.antrepo_clearance_days = 2
	doc.flags.ignore_permissions = True
	doc.save()


def ensure_uom(uom_name: str):
	if not frappe.db.exists("UOM", uom_name):
		doc = frappe.get_doc({"doctype": "UOM", "uom_name": uom_name})
		doc.insert(ignore_permissions=True)


def ensure_item_group(group_name: str, parent: str = "All Item Groups"):
	if not frappe.db.exists("Item Group", group_name):
		doc = frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": group_name,
			"parent_item_group": parent,
			"is_group": 0,
		})
		doc.insert(ignore_permissions=True)


def ensure_ara_malzeme_grubu(name: str):
	if not frappe.db.exists("KTA Ara Malzeme Grubu", name):
		doc = frappe.get_doc({
			"doctype": "KTA Ara Malzeme Grubu",
			"kta_ara_malzeme_grubu": name,
		})
		doc.insert(ignore_permissions=True)


def ensure_fiscal_year(company: str = COMPANY):
	for yr in (2026, 2027):
		year_str = str(yr)
		if not frappe.db.exists("Fiscal Year", year_str):
			fy = frappe.get_doc({
				"doctype": "Fiscal Year",
				"year": year_str,
				"year_start_date": f"{yr}-01-01",
				"year_end_date": f"{yr}-12-31",
				"companies": [{"company": company}],
			})
			fy.insert(ignore_permissions=True)
		else:
			fy = frappe.get_doc("Fiscal Year", year_str)
			existing_companies = [c.company for c in fy.companies]
			if company not in existing_companies:
				fy.append("companies", {"company": company})
				fy.save(ignore_permissions=True)


def ensure_warehouse_account():
	inv_account = frappe.db.get_value("Company", COMPANY, "default_inventory_account")
	mrp_settings = get_mrp_settings()
	w_type = mrp_settings.available_warehouse_type or "Kullanılabilir Stok"

	if not frappe.db.exists("Warehouse Type", w_type):
		frappe.get_doc({"doctype": "Warehouse Type", "name": w_type}).insert(ignore_permissions=True)

	for wh in (WAREHOUSE_RM, WAREHOUSE_FG, WAREHOUSE_WIP):
		if frappe.db.exists("Warehouse", wh):
			updates = {}
			if inv_account and not frappe.db.get_value("Warehouse", wh, "account"):
				updates["account"] = inv_account
			if wh in (WAREHOUSE_RM, WAREHOUSE_FG):
				updates["warehouse_type"] = w_type
			if updates:
				frappe.db.set_value("Warehouse", wh, updates)


def ensure_customer_address(customer_code: str) -> str:
	addr_title = f"{customer_code} Head Office"
	addr_name = frappe.db.get_value("Address", {"address_title": addr_title}, "name")
	ship_days = CUSTOMERS.get(customer_code, {}).get("custom_shipping_lead_days", 1)
	if not addr_name:
		addr = frappe.get_doc({
			"doctype": "Address",
			"address_title": addr_title,
			"address_type": "Shipping",
			"address_line1": "Sanayi Cad. No: 1",
			"city": "Bursa",
			"country": "Turkey",
			"custom_shipping_lead_days": ship_days,
			"links": [{"link_doctype": "Customer", "link_name": customer_code}],
		})
		addr.insert(ignore_permissions=True)
		addr_name = addr.name
	else:
		frappe.db.set_value("Address", addr_name, "custom_shipping_lead_days", ship_days)
	return addr_name


def seed_master_data():
	"""Seeds Customers, Addresses, Suppliers, Workstations, Operations, Items, Prices, MRP Settings."""
	ensure_mrp_settings()
	ensure_fiscal_year(COMPANY)
	ensure_warehouse_account()
	ensure_uom("Adet")
	ensure_uom("Metre")
	ensure_item_group(ITEM_GROUP_FG)
	ensure_item_group(ITEM_GROUP_RM)
	ensure_ara_malzeme_grubu("ÜRÜN")
	ensure_ara_malzeme_grubu("HAMMADDE")

	# 1. Suppliers
	for code, data in SUPPLIERS.items():
		if not frappe.db.exists("Supplier", code):
			s = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": code,
				"supplier_group": data.get("supplier_group", "Local"),
			})
			s.insert(ignore_permissions=True)

	# 2. Customers & Addresses (with native shipping lead times)
	for code, data in CUSTOMERS.items():
		ship_days = data.get("custom_shipping_lead_days", 1)
		if not frappe.db.exists("Customer", code):
			c = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": code,
				"customer_group": data.get("customer_group", "Commercial"),
				"custom_shipping_lead_days": ship_days,
			})
			c.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Customer", code, "custom_shipping_lead_days", ship_days)

		ensure_customer_address(code)

	# 3. Workstations & Operations
	for ws_name in WORKSTATIONS:
		if not frappe.db.exists("Workstation", ws_name):
			ws = frappe.get_doc({
				"doctype": "Workstation",
				"workstation_name": ws_name,
			})
			ws.insert(ignore_permissions=True)

	for op_name in OPERATIONS:
		if not frappe.db.exists("Operation", op_name):
			op = frappe.get_doc({
				"doctype": "Operation",
				"name": op_name,
				"op_name": op_name,
			})
			op.insert(ignore_permissions=True)

	# 4. Finished Goods
	for code, data in FINISHED_GOODS.items():
		if not frappe.db.exists("Item", code):
			item_dict = {
				"doctype": "Item",
				"item_code": code,
				"item_name": data["item_name"],
				"item_group": data["item_group"],
				"stock_uom": data["stock_uom"],
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"default_warehouse": WAREHOUSE_FG,
				"custom_weekly_production": data["custom_weekly_production"],
				"custom_manufacturing_lead_days": data.get("custom_manufacturing_lead_days", 14),
				"custom_ara_malzeme_grubu": data["custom_ara_malzeme_grubu"],
			}
			if "reorder_level" in data:
				item_dict["reorder_levels"] = [
					{
						"warehouse": WAREHOUSE_FG,
						"warehouse_reorder_level": data["reorder_level"],
						"warehouse_reorder_qty": data["reorder_qty"],
						"material_request_type": "Manufacture",
					}
				]
			item = frappe.get_doc(item_dict)
			item.insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"Item",
				code,
				{
					"default_warehouse": WAREHOUSE_FG,
					"custom_manufacturing_lead_days": data.get("custom_manufacturing_lead_days", 14),
				},
			)
			if "reorder_level" in data:
				item_doc = frappe.get_doc("Item", code)
				item_doc.reorder_levels = []
				item_doc.append("reorder_levels", {
					"warehouse": WAREHOUSE_FG,
					"warehouse_reorder_level": data["reorder_level"],
					"warehouse_reorder_qty": data["reorder_qty"],
					"material_request_type": "Manufacture",
				})
				item_doc.save(ignore_permissions=True)

	# 5. Raw Materials
	for code, data in RAW_MATERIALS.items():
		if not frappe.db.exists("Item", code):
			item_dict = {
				"doctype": "Item",
				"item_code": code,
				"item_name": data["item_name"],
				"item_group": ITEM_GROUP_RM,
				"stock_uom": data["stock_uom"],
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"default_warehouse": WAREHOUSE_RM,
				"custom_ara_malzeme_grubu": data["custom_ara_malzeme_grubu"],
				"custom_sourcing_strategy": "Varsayılan Tedarikçi (%100)",
				"supplier_items": [
					{
						"supplier": data["default_supplier"],
					}
				],
			}
			if "min_order_qty" in data:
				item_dict["min_order_qty"] = data["min_order_qty"]
			if "custom_paket_miktari" in data:
				item_dict["custom_paket_miktari"] = data["custom_paket_miktari"]
			if "lead_time_days" in data:
				item_dict["lead_time_days"] = data["lead_time_days"]

			item = frappe.get_doc(item_dict)
			item.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", code, "default_warehouse", WAREHOUSE_RM)

	# 6. Item Prices (Standard Buying)
	all_sim_items = list(FINISHED_GOODS.keys()) + list(RAW_MATERIALS.keys())
	for item_code in all_sim_items:
		rm_info = RAW_MATERIALS.get(item_code, {})
		price_name = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": "Standard Buying"})
		if not price_name:
			ip = frappe.get_doc({
				"doctype": "Item Price",
				"item_code": item_code,
				"price_list": "Standard Buying",
				"price_list_rate": 1.0,
				"currency": "TRY",
				"supplier": rm_info.get("default_supplier"),
				"custom_minimum_order_quantity": rm_info.get("min_order_qty", 0),
				"custom_minimum_paketleme_miktari": rm_info.get("custom_paket_miktari", 1),
				"lead_time_days": rm_info.get("lead_time_days", 0),
			})
			ip.insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"Item Price",
				price_name,
				{
					"supplier": rm_info.get("default_supplier"),
					"custom_minimum_order_quantity": rm_info.get("min_order_qty", 0),
					"custom_minimum_paketleme_miktari": rm_info.get("custom_paket_miktari", 1),
					"lead_time_days": rm_info.get("lead_time_days", 0),
				},
				update_modified=False,
			)

	frappe.db.commit()


def seed_boms():
	"""Seeds flat BOMs with operations for URUN-01 and URUN-02."""
	# BOM-URUN-01
	if not frappe.db.exists("BOM", {"item": "URUN-01", "is_default": 1, "docstatus": 1}):
		bom1 = frappe.get_doc({
			"doctype": "BOM",
			"item": "URUN-01",
			"quantity": 1.0,
			"is_active": 1,
			"is_default": 1,
			"with_operations": 1,
			"inspection_required": 0,
			"currency": "TRY",
			"company": COMPANY,
			"items": [
				{"item_code": "HAMMADDE-01", "qty": 2.0, "uom": "Metre"},
				{"item_code": "HAMMADDE-02", "qty": 4.0, "uom": "Adet"},
				{"item_code": "HAMMADDE-03", "qty": 1.0, "uom": "Adet"},
				{"item_code": "HAMMADDE-06", "qty": 1.0, "uom": "Adet"},
			],
			"operations": [
				{"operation": "Kablo Kesim", "workstation": "Kesim Hattı", "time_in_mins": 2, "hour_rate": 10},
				{"operation": "Terminal Krimp", "workstation": "Krimp Presi", "time_in_mins": 3, "hour_rate": 10},
				{"operation": "Grup Montaj", "workstation": "Montaj Masası", "time_in_mins": 5, "hour_rate": 10},
			],
		})
		bom1.insert(ignore_permissions=True)
		bom1.submit()

	# BOM-URUN-02
	if not frappe.db.exists("BOM", {"item": "URUN-02", "is_default": 1, "docstatus": 1}):
		bom2 = frappe.get_doc({
			"doctype": "BOM",
			"item": "URUN-02",
			"quantity": 1.0,
			"is_active": 1,
			"is_default": 1,
			"with_operations": 1,
			"inspection_required": 0,
			"currency": "TRY",
			"company": COMPANY,
			"items": [
				{"item_code": "HAMMADDE-01", "qty": 1.5, "uom": "Metre"},
				{"item_code": "HAMMADDE-04", "qty": 2.0, "uom": "Adet"},
				{"item_code": "HAMMADDE-05", "qty": 1.0, "uom": "Adet"},
				{"item_code": "HAMMADDE-07", "qty": 2.0, "uom": "Adet"},
			],
			"operations": [
				{"operation": "Kablo Kesim", "workstation": "Kesim Hattı", "time_in_mins": 2, "hour_rate": 10},
				{"operation": "Terminal Krimp", "workstation": "Krimp Presi", "time_in_mins": 3, "hour_rate": 10},
				{"operation": "Grup Montaj", "workstation": "Montaj Masası", "time_in_mins": 4, "hour_rate": 10},
			],
		})
		bom2.insert(ignore_permissions=True)
		bom2.submit()

	frappe.db.commit()


def seed_supply_pipeline(sched=None):
	"""Seeds the 7-state raw material supply pipeline.

	1. HAMMADDE-01: Partial Free Stock (500 Mtr) via submitted Stock Entry
	2. HAMMADDE-02: Open PO (1.000 Nos) in W+1
	3. HAMMADDE-03: In-Transit PR (500 Nos, workflow_state='Yolda', ETA in W+2)
	4. HAMMADDE-04: Bonded Warehouse PR (800 Nos, workflow_state='Antrepoda')
	5. HAMMADDE-05: Customs Clearance PR (400 Nos, workflow_state='Gümrüklemede')
	6. HAMMADDE-06: Full Free Stock (2.000 Nos) via submitted Stock Entry
	7. HAMMADDE-07: Critical Deficit (0 Stock, 0 Supply -> MRP generates Recommended PO)
	"""
	if not sched:
		sched = get_simulation_dates()

	# 1 & 6. Stock Entry (Material Receipt) for raw materials consumed by initial WO plus target free stocks
	se = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"purpose": "Material Receipt",
		"company": COMPANY,
		"items": [
			{
				"item_code": "HAMMADDE-01",
				"qty": 700,  # 200 will be consumed by URUN-01 FG stock creation, leaving 500
				"t_warehouse": WAREHOUSE_RM,
				"basic_rate": 1.0,
				"cost_center": "Main - TEST",
			},
			{
				"item_code": "HAMMADDE-02",
				"qty": 400,  # 400 will be consumed by URUN-01 FG stock creation, leaving 0 (open PO has 1.000)
				"t_warehouse": WAREHOUSE_RM,
				"basic_rate": 1.0,
				"cost_center": "Main - TEST",
			},
			{
				"item_code": "HAMMADDE-03",
				"qty": 100,  # 100 will be consumed by URUN-01 FG stock creation, leaving 0 (yolda PR has 500)
				"t_warehouse": WAREHOUSE_RM,
				"basic_rate": 1.0,
				"cost_center": "Main - TEST",
			},
			{
				"item_code": "HAMMADDE-06",
				"qty": 2100,  # 100 will be consumed by URUN-01 FG stock creation, leaving 2000
				"t_warehouse": WAREHOUSE_RM,
				"basic_rate": 1.0,
				"cost_center": "Main - TEST",
			},
		],
	})
	se.insert(ignore_permissions=True)
	se.submit()

	# 2. Open Purchase Order for HAMMADDE-02 in W+1
	po = frappe.get_doc({
		"doctype": "Purchase Order",
		"company": COMPANY,
		"supplier": "TEDARIKCI-YERLI",
		"schedule_date": sched.po_schedule_date,
		"items": [
			{
				"item_code": "HAMMADDE-02",
				"qty": 1000,
				"rate": 1.0,
				"schedule_date": sched.po_schedule_date,
				"warehouse": WAREHOUSE_RM,
			}
		],
	})
	po.insert(ignore_permissions=True)
	po.submit()

	# 2b. In-Transit Purchase Receipt (Yolda) for HAMMADDE-02 in W+1 (Multi-badge verification)
	pr_yolda_m2 = frappe.get_doc({
		"doctype": "Purchase Receipt",
		"company": COMPANY,
		"supplier": "TEDARIKCI-ITHALAT",
		"tahmini_varis_tarihi": sched.po_schedule_date,
		"set_warehouse": WAREHOUSE_RM,
		"items": [
			{
				"item_code": "HAMMADDE-02",
				"qty": 500,
				"rate": 1.0,
				"warehouse": WAREHOUSE_RM,
			}
		],
	})
	pr_yolda_m2.insert(ignore_permissions=True)
	frappe.db.set_value("Purchase Receipt", pr_yolda_m2.name, {
		"workflow_state": "Yolda",
		"is_import_purchase_receipt": 1,
		"tahmini_varis_tarihi": sched.po_schedule_date,
	})

	# 3. In-Transit Purchase Receipt (Yolda) for HAMMADDE-03
	pr_yolda = frappe.get_doc({
		"doctype": "Purchase Receipt",
		"company": COMPANY,
		"supplier": "TEDARIKCI-ITHALAT",
		"tahmini_varis_tarihi": sched.pr_yolda_eta,
		"set_warehouse": WAREHOUSE_RM,
		"items": [
			{
				"item_code": "HAMMADDE-03",
				"qty": 500,
				"rate": 1.0,
				"warehouse": WAREHOUSE_RM,
			}
		],
	})
	pr_yolda.insert(ignore_permissions=True)
	frappe.db.set_value("Purchase Receipt", pr_yolda.name, {
		"workflow_state": "Yolda",
		"is_import_purchase_receipt": 1,
		"tahmini_varis_tarihi": sched.pr_yolda_eta,
	})

	# 4. Bonded Warehouse Purchase Receipt (Antrepoda) for HAMMADDE-04
	pr_antrepo = frappe.get_doc({
		"doctype": "Purchase Receipt",
		"company": COMPANY,
		"supplier": "TEDARIKCI-ITHALAT",
		"set_warehouse": WAREHOUSE_RM,
		"items": [
			{
				"item_code": "HAMMADDE-04",
				"qty": 800,
				"rate": 1.0,
				"warehouse": WAREHOUSE_RM,
			}
		],
	})
	pr_antrepo.insert(ignore_permissions=True)
	frappe.db.set_value("Purchase Receipt", pr_antrepo.name, {
		"workflow_state": "Antrepoda",
		"is_import_purchase_receipt": 1,
		"is_antrepo_purchase_receipt": 1,
	})

	# 5. Customs Clearance Purchase Receipt (Gümrüklemede) for HAMMADDE-05
	pr_gumruk = frappe.get_doc({
		"doctype": "Purchase Receipt",
		"company": COMPANY,
		"supplier": "TEDARIKCI-ITHALAT",
		"custom_gumruk_islem_baslama_tarihi": sched.pr_gumruk_start_date,
		"set_warehouse": WAREHOUSE_RM,
		"items": [
			{
				"item_code": "HAMMADDE-05",
				"qty": 400,
				"rate": 1.0,
				"warehouse": WAREHOUSE_RM,
			}
		],
	})
	pr_gumruk.insert(ignore_permissions=True)
	frappe.db.set_value("Purchase Receipt", pr_gumruk.name, {
		"workflow_state": "Gümrüklemede",
		"is_import_purchase_receipt": 1,
		"is_antrepo_purchase_receipt": 1,
		"custom_gumruk_islem_baslama_tarihi": sched.pr_gumruk_start_date,
	})

	frappe.db.commit()


def seed_demand_and_wip(sched=None):
	"""Seeds demand, WIP, stock-covered FG stock, and carry-over data.

	1. URUN-01 FG Stock: 100 Nos via completed Work Order & Stock Entry (Manufacture)
	   -> In PSW: 500 SO - 100 Stock = 400 To Produce (stock_covered = 100)
	2. MUSTERI-AVRUPA Sales Order: 500 Nos URUN-01, PSW lands on W_CURRENT
	3. MUSTERI-YERLI Sales Order: 300 Nos URUN-02, PSW lands on W_CURRENT
	4. URUN-02 Open Work Order: 150 Nos (skip_transfer=1)
	   -> WIP covered = 150, To Produce = 150, WO load = 150 -> Total = 300
	   -> Total W1 Demand = 400 + 300 = 700. Group Cap = 500. Carry-over = 200!
	5. URUN-02 Approved Material Request (Manufacture): 100 Nos in W_NEXT (W+1)
	   -> Appears as Internal Demand in Week 2.
	"""
	if not sched:
		sched = get_simulation_dates()

	# 1. Finished Goods Stock Creation for URUN-01 (100 Nos)
	bom_urun_01 = frappe.db.get_value("BOM", {"item": "URUN-01", "is_default": 1})
	wo_fg = frappe.get_doc({
		"doctype": "Work Order",
		"production_item": "URUN-01",
		"bom_no": bom_urun_01,
		"qty": 100,
		"company": COMPANY,
		"source_warehouse": WAREHOUSE_RM,
		"fg_warehouse": WAREHOUSE_FG,
		"wip_warehouse": WAREHOUSE_WIP,
		"skip_transfer": 1,
		"planned_start_date": sched.w_current_monday,
	})
	wo_fg.insert(ignore_permissions=True)
	wo_fg.submit()

	orig_neg = frappe.db.get_single_value("Stock Settings", "allow_negative_stock")
	frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
	try:
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		se_dict = make_stock_entry(wo_fg.name, "Manufacture", 100)
		se_doc = frappe.get_doc(se_dict)
		se_doc.inspection_required = 0
		se_doc.additional_costs = []
		adj_account = frappe.db.get_value("Company", COMPANY, "stock_adjustment_account")
		for item_row in se_doc.items:
			if not item_row.expense_account:
				item_row.expense_account = adj_account
			if not item_row.cost_center:
				item_row.cost_center = "Main - TEST"
			if item_row.item_code == "URUN-01":
				item_row.t_warehouse = WAREHOUSE_FG
			else:
				item_row.s_warehouse = WAREHOUSE_RM
		se_doc.insert(ignore_permissions=True)
		se_doc.submit()
	finally:
		frappe.db.set_single_value("Stock Settings", "allow_negative_stock", orig_neg)

	# 2. Sales Orders (Week 1 Demand)
	addr_avrupa = ensure_customer_address("MUSTERI-AVRUPA")
	so_avrupa = frappe.get_doc({
		"doctype": "Sales Order",
		"company": COMPANY,
		"customer": "MUSTERI-AVRUPA",
		"customer_address": addr_avrupa,
		"shipping_address_name": addr_avrupa,
		"transaction_date": sched.w_current_monday,
		"delivery_date": sched.so_avrupa_delivery_date,
		"items": [
			{
				"item_code": "URUN-01",
				"qty": 500,
				"rate": 100.0,
				"delivery_date": sched.so_avrupa_delivery_date,
				"warehouse": WAREHOUSE_FG,
			}
		],
	})
	so_avrupa.insert(ignore_permissions=True)
	so_avrupa.submit()

	addr_yerli = ensure_customer_address("MUSTERI-YERLI")
	so_yerli = frappe.get_doc({
		"doctype": "Sales Order",
		"company": COMPANY,
		"customer": "MUSTERI-YERLI",
		"customer_address": addr_yerli,
		"shipping_address_name": addr_yerli,
		"transaction_date": sched.w_current_monday,
		"delivery_date": sched.so_yerli_delivery_date,
		"items": [
			{
				"item_code": "URUN-02",
				"qty": 300,
				"rate": 100.0,
				"delivery_date": sched.so_yerli_delivery_date,
				"warehouse": WAREHOUSE_FG,
			}
		],
	})
	so_yerli.insert(ignore_permissions=True)
	so_yerli.submit()

	# 3. Open Work Order (WIP for URUN-02, 150 Nos)
	bom_urun_02 = frappe.db.get_value("BOM", {"item": "URUN-02", "is_default": 1})
	wo_open = frappe.get_doc({
		"doctype": "Work Order",
		"production_item": "URUN-02",
		"bom_no": bom_urun_02,
		"qty": 150,
		"company": COMPANY,
		"source_warehouse": WAREHOUSE_RM,
		"fg_warehouse": WAREHOUSE_FG,
		"wip_warehouse": WAREHOUSE_WIP,
		"skip_transfer": 1,
		"planned_start_date": sched.w_current_monday,
	})
	wo_open.insert(ignore_permissions=True)
	wo_open.submit()

	# 4. Internal Demand Material Request (Week 2 for URUN-02, 100 Nos)
	mr = frappe.get_doc({
		"doctype": "Material Request",
		"company": COMPANY,
		"material_request_type": "Manufacture",
		"schedule_date": sched.mr_schedule_date,
		"items": [
			{
				"item_code": "URUN-02",
				"qty": 100,
				"schedule_date": sched.mr_schedule_date,
				"warehouse": WAREHOUSE_FG,
			}
		],
	})
	mr.insert(ignore_permissions=True)
	mr.submit()

	frappe.db.commit()


def seed():
	"""Main simulation seeder entrypoint.

	Cleans previous simulation data, seeds master data, flat BOMs,
	7-state supply pipeline, demand, WIP, stock-covered FG stock, and
	prints a clear narrative walkthrough for the user.
	"""
	sched = get_simulation_dates()
	clean()
	seed_master_data()
	seed_boms()
	seed_supply_pipeline(sched)
	seed_demand_and_wip(sched)

	narrative = """
================================================================================
🎉 KTA MRP GÖRSEL SİMÜLASYON SENARYOSU BAŞARIYLA KURULDU!
================================================================================

📖 SENARYONUN HİKAYESİ:
--------------------------------------------------------------------------------
1. MÜŞTERİLER VE SEVK SÜRELERİ:
   - MUSTERI-AVRUPA (İhracat): 7 gün üretim + 5 gün yol ister (Toplam 12 gün önce).
   - MUSTERI-YERLI (Yurtiçi): 3 gün üretim + 1 gün yol ister (Toplam 4 gün önce).

2. FABRİKA KAPASİTESİ VE DEVİR (CARRY-OVER):
   - Haftalık tavan kapasitemiz: 500 Adet (KABLO GRUBU).
   - Bu hafta gelen toplam talep: 720 Adet (420 URUN-01 net + 300 URUN-02 brüt).
   - SONUÇ: Fabrika 500 adedi bu hafta üretir (%100 doluluk), sarkan 220 adet sonraki haftaya devreder!

3. STOKTAN DÜŞME & RE-ORDER / EMNİYET STOĞU (STOCK COVERED):
   - URUN-01 için 500 adet sipariş ve depoda 100 adet hazır mamul var.
   - URUN-01 altına 20 adet Re-order / Emniyet Stoğu (safety_stock) tanımlanmıştır!
   - SONUÇ: Motor 20 adedi emniyet stoğu olarak kilitler, 80 adedi siparişe ayırır (stock_covered = 80).
   - Net üretim ihtiyacı 420 adettir (500 - 80). Sistem hammaddeyi net 420 adet üzerinden hesaplar!

4. HAMMADDELERİMİZ NEREDE? (Material Requirement Ekranını Açınız):
   - HAMMADDE-01 (Kablo): Ortak malzeme, iki ürün birden tüketiyor (Pegging rekabeti).
   - HAMMADDE-02 (Terminal): W+1 haftasında hem Açık PO (1.000 Adet) hem de Yolda (500 Adet) var -> Aynı haftada İkili Rozet (İndigo PO + Amber Yolda).
   - HAMMADDE-03 (Konnektör): Gemide / Yolda! ETA tarihi W+2 haftasına ayarlandı.
   - HAMMADDE-04 (Kauçuk): Antrepoda bekliyor (henüz çekim emri verilmedi).
   - HAMMADDE-05 (Sigorta): Gümrükte çekim işlemi başladı (+2 gün sonra depoda).
   - HAMMADDE-06 (Bant): Depoda bolca var (2.000 Adet) -> Net İhtiyaç Sıfır (Yeşil hücreler).
   - HAMMADDE-07 (Erkek Terminal): Kimsede yok! Sıfır stok! (Kırmızı satır -> Önerilen PO çıkacak).

👉 ŞİMDİ NE YAPMALISINIZ?
   1. ERPNext'e girip "Kapasite Planlama Raporu"nu açın -> %100 doluluğu ve sonraki haftaya devri görün.
   2. "Material Requirement" ekranını açın -> 7 hammaddenin farklı renk ve akordeonlarını canlı inceleyin!
================================================================================
"""
	print(narrative)
	return {
		"status": "success",
		"so_count": frappe.db.count("Sales Order", {"customer": ["in", ["MUSTERI-AVRUPA", "MUSTERI-YERLI"]]}),
		"wo_count": frappe.db.count("Work Order", {"production_item": ["in", ["URUN-01", "URUN-02"]]}),
		"po_count": frappe.db.count("Purchase Order", {"supplier": ["in", ["TEDARIKCI-ITHALAT", "TEDARIKCI-YERLI"]]}),
		"pr_count": frappe.db.count("Purchase Receipt", {"supplier": ["in", ["TEDARIKCI-ITHALAT", "TEDARIKCI-YERLI"]]}),
		"mr_count": frappe.db.count("Material Request", {"material_request_type": "Manufacture"}),
	}


def test_seed_demand():
	clean()
	seed_master_data()
	seed_boms()
	seed_supply_pipeline()
	seed_demand_and_wip()
	return {
		"status": "success",
		"so": frappe.db.count("Sales Order", {"customer": ["in", ["MUSTERI-AVRUPA", "MUSTERI-YERLI"]]}),
		"wo": frappe.db.count("Work Order", {"production_item": ["in", ["URUN-01", "URUN-02"]]}),
		"mr": frappe.db.count("Material Request", {"material_request_type": "Manufacture"}),
		"fg_stock": frappe.db.get_value("Bin", {"item_code": "URUN-01", "warehouse": WAREHOUSE_FG}, "actual_qty"),
	}


def test_seed_supply():
	clean()
	seed_master_data()
	seed_boms()
	seed_supply_pipeline()
	return {
		"status": "success",
		"se": frappe.db.count("Stock Entry", {"purpose": "Material Receipt"}),
		"po": frappe.db.count("Purchase Order", {"supplier": ["in", ["TEDARIKCI-ITHALAT", "TEDARIKCI-YERLI"]]}),
		"pr": frappe.db.count("Purchase Receipt", {"supplier": ["in", ["TEDARIKCI-ITHALAT", "TEDARIKCI-YERLI"]]}),
	}


def test_seed_master():
	clean()
	seed_master_data()
	seed_boms()
	return {
		"status": "success",
		"boms": frappe.get_all("BOM", filters={"item": ["in", ["URUN-01", "URUN-02"]]}, pluck="name"),
	}
