# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import frappe
from erpnextkta.mrp_simulation.constants import (
	CUSTOMERS,
	FINISHED_GOODS,
	OPERATIONS,
	RAW_MATERIALS,
	SUPPLIERS,
	WORKSTATIONS,
)


def _cancel_and_delete(doctype: str, filters: dict) -> int:
	"""Safely cancel submitted docs and delete them."""
	docs = frappe.get_all(doctype, filters=filters, fields=["name", "docstatus"])
	count = 0
	for d in docs:
		try:
			doc = frappe.get_doc(doctype, d.name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				doc.cancel()
			frappe.delete_doc(doctype, d.name, force=True, ignore_permissions=True)
			count += 1
		except Exception as e:
			frappe.log_error(f"Error cleaning {doctype} {d.name}: {e}")
			# Direct DB fallback if ORM delete hits soft locks
			try:
				frappe.db.delete(doctype, {"name": d.name})
				count += 1
			except Exception:
				pass
	return count


def clean() -> dict:
	"""Completely removes all simulation data in reverse-dependency order.

	Idempotent and safe: can be run repeatedly without errors.
	"""
	frappe.flags.ignore_permissions = True
	summary = {}

	fg_codes = list(FINISHED_GOODS.keys())
	rm_codes = list(RAW_MATERIALS.keys())
	all_sim_items = fg_codes + rm_codes
	customer_names = list(CUSTOMERS.keys())
	supplier_names = list(SUPPLIERS.keys())

	# 1. Stock Entries (Manufacture & Material Receipt for simulation items)
	se_items = frappe.db.sql_list(
		"""
		SELECT DISTINCT parent FROM `tabStock Entry Detail`
		WHERE item_code IN %s
	""",
		[tuple(all_sim_items)],
	)
	if se_items:
		summary["Stock Entry"] = _cancel_and_delete("Stock Entry", {"name": ["in", se_items]})
	else:
		summary["Stock Entry"] = 0

	# 2. Work Orders (for URUN-01, URUN-02)
	summary["Work Order"] = _cancel_and_delete(
		"Work Order", {"production_item": ["in", fg_codes]}
	)

	# 3. Purchase Receipts (for simulation suppliers)
	summary["Purchase Receipt"] = _cancel_and_delete(
		"Purchase Receipt", {"supplier": ["in", supplier_names]}
	)

	# 4. Purchase Orders (for simulation suppliers)
	summary["Purchase Order"] = _cancel_and_delete(
		"Purchase Order", {"supplier": ["in", supplier_names]}
	)

	# 5. Sales Orders (for simulation customers)
	summary["Sales Order"] = _cancel_and_delete(
		"Sales Order", {"customer": ["in", customer_names]}
	)

	# 6. Material Requests (Manufacture type for simulation items)
	mr_items = frappe.db.sql_list(
		"""
		SELECT DISTINCT parent FROM `tabMaterial Request Item`
		WHERE item_code IN %s
	""",
		[tuple(all_sim_items)],
	)
	if mr_items:
		summary["Material Request"] = _cancel_and_delete(
			"Material Request", {"name": ["in", mr_items]}
		)
	else:
		summary["Material Request"] = 0

	# 7. Clean residual SLE & Bins for simulation items to avoid link locks on Item deletion
	frappe.db.delete("Bin", {"item_code": ["in", all_sim_items]})
	frappe.db.delete("Stock Ledger Entry", {"item_code": ["in", all_sim_items]})

	# 8. BOMs (for URUN-01, URUN-02)
	boms = frappe.get_all("BOM", filters={"item": ["in", fg_codes]}, fields=["name", "docstatus"])
	summary["BOM"] = 0
	for b in boms:
		try:
			frappe.db.set_value("BOM", b.name, {"is_default": 0, "is_active": 0})
			if b.docstatus == 1:
				b_doc = frappe.get_doc("BOM", b.name)
				b_doc.flags.ignore_permissions = True
				b_doc.cancel()
			frappe.delete_doc("BOM", b.name, force=True, ignore_permissions=True)
			summary["BOM"] += 1
		except Exception:
			frappe.db.delete("BOM", {"name": b.name})
			frappe.db.delete("BOM Item", {"parent": b.name})
			frappe.db.delete("BOM Operation", {"parent": b.name})
			summary["BOM"] += 1

	# 9. Item Prices for simulation items
	prices = frappe.get_all("Item Price", filters={"item_code": ["in", all_sim_items]}, pluck="name")
	for p in prices:
		frappe.delete_doc("Item Price", p, force=True, ignore_permissions=True)
	summary["Item Price"] = len(prices)

	# 10. Items (Finished Goods & Raw Materials)
	summary["Item"] = 0
	for item_code in all_sim_items:
		if frappe.db.exists("Item", item_code):
			try:
				frappe.delete_doc("Item", item_code, force=True, ignore_permissions=True)
			except Exception:
				frappe.db.delete("Item Supplier", {"parent": item_code})
				frappe.db.delete("Item Customer Detail", {"parent": item_code})
				frappe.db.delete("Item Reorder", {"parent": item_code})
				frappe.db.delete("Item", {"name": item_code})
			summary["Item"] += 1

	# 11. Workstations & Operations
	summary["Workstation"] = 0
	for ws in WORKSTATIONS:
		if frappe.db.exists("Workstation", ws):
			frappe.delete_doc("Workstation", ws, force=True, ignore_permissions=True)
			summary["Workstation"] += 1

	summary["Operation"] = 0
	for op in OPERATIONS:
		if frappe.db.exists("Operation", op):
			frappe.delete_doc("Operation", op, force=True, ignore_permissions=True)
			summary["Operation"] += 1

	# 12. KTA Sevk Parametreleri
	sevk_records = frappe.get_all(
		"KTA Sevk Parametreleri",
		filters={"customer_name": ["in", customer_names]},
		pluck="name",
	)
	for s in sevk_records:
		frappe.delete_doc("KTA Sevk Parametreleri", s, force=True, ignore_permissions=True)
	summary["KTA Sevk Parametreleri"] = len(sevk_records)

	# 13. Dynamic Links and Addresses for Customers & Suppliers
	for parenttype, names in [("Customer", customer_names), ("Supplier", supplier_names)]:
		links = frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": parenttype, "link_name": ["in", names]},
			fields=["parent"],
		)
		for lk in links:
			frappe.delete_doc("Address", lk.parent, force=True, ignore_permissions=True)

	# 14. Customers & Suppliers
	summary["Customer"] = 0
	for c in customer_names:
		if frappe.db.exists("Customer", c):
			frappe.delete_doc("Customer", c, force=True, ignore_permissions=True)
			summary["Customer"] += 1

	summary["Supplier"] = 0
	for s in supplier_names:
		if frappe.db.exists("Supplier", s):
			frappe.delete_doc("Supplier", s, force=True, ignore_permissions=True)
			summary["Supplier"] += 1

	frappe.db.commit()
	return summary
