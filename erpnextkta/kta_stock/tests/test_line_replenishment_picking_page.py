# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking import (
    get_context,
    get_open_replenishment_orders,
    get_replenishment_order_details,
    resolve_scanned_barcode,
)


class TestLineReplenishmentPickingPage(FrappeTestCase):
    def _get_page_path(self, filename: str) -> str:
        app_path = frappe.get_app_path("erpnextkta")
        return os.path.join(
            app_path, "kta_stock", "page", "line_replenishment_picking", filename
        )

    def test_picking_page_json_exists(self):
        json_path = self._get_page_path("line_replenishment_picking.json")
        self.assertTrue(os.path.exists(json_path), f"{json_path} must exist")
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("page_name"), "line-replenishment-picking")
        self.assertEqual(data.get("title"), "Line Replenishment Picking")
        self.assertEqual(data.get("module"), "kta_stock")
        self.assertEqual(data.get("standard"), "Yes")
        roles = [r.get("role") for r in data.get("roles", [])]
        self.assertIn("Stock User", roles)
        self.assertIn("Stock Manager", roles)
        self.assertIn("System Manager", roles)

    def test_picking_page_js_exists(self):
        js_path = self._get_page_path("line_replenishment_picking.js")
        self.assertTrue(os.path.exists(js_path), f"{js_path} must exist")
        with open(js_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('frappe.pages["line-replenishment-picking"]', content)
        self.assertIn('frappe.require("line-replenishment-pda.bundle.js")', content)
        self.assertIn("frappe.ui.setup_line_replenishment_pda_vue", content)
        self.assertIn(".layout-main-section", content)
        self.assertIn(".page-head", content)
        self.assertIn(".hide()", content)

    def test_picking_bundle_source_exists(self):
        app_path = frappe.get_app_path("erpnextkta")
        bundle_path = os.path.join(
            app_path,
            "public",
            "line-replenishment-pda",
            "line-replenishment-pda.bundle.js",
        )
        self.assertTrue(os.path.exists(bundle_path), f"{bundle_path} must exist")
        with open(bundle_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("setup_line_replenishment_pda_vue", content)

    def test_picking_page_py_context(self):
        ctx = {}
        get_context(ctx)

    def test_resolve_scanned_barcode_empty(self):
        result = resolve_scanned_barcode("")
        self.assertIsNone(result.get("item_code"))

    def test_resolve_scanned_barcode_direct_item(self):
        item_name = frappe.db.get_value("Item", {}, "name")
        if item_name:
            res = resolve_scanned_barcode(item_name)
            self.assertEqual(res.get("item_code"), item_name)

    def test_get_open_replenishment_orders(self):
        orders = get_open_replenishment_orders()
        self.assertIsInstance(orders, list)

    def test_get_replenishment_order_details(self):
        none_res = get_replenishment_order_details(None)
        self.assertIsNone(none_res)

    def test_get_replenishment_order_details_with_shelf_and_batch(self):
        item_code = frappe.db.get_value("Item", {}, "name")
        warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
        company = frappe.db.get_value("Company", {}, "name")
        if not (item_code and warehouse and company):
            return

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": warehouse,
                "company": company,
                "items": [
                    {
                        "item_code": item_code,
                        "deficit_qty": 15.0,
                        "suggested_source_warehouse": "W1A-01-01 - KTA",
                        "suggested_batch_no": "0000000070",
                        "uom": "Nos",
                    }
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.flags.ignore_permissions = True
        order.insert()

        try:
            open_orders = get_open_replenishment_orders()
            matching = [o for o in open_orders if o["name"] == order.name]
            self.assertEqual(len(matching), 1)
            self.assertNotIn("sourcing_strategy", matching[0])

            details = get_replenishment_order_details(order.name)
            self.assertIsNotNone(details)
            self.assertNotIn("sourcing_strategy", details)
            self.assertEqual(len(details["items"]), 1)
            row = details["items"][0]
            self.assertNotIn("sourcing_type", row)
            self.assertEqual(row["suggested_source_warehouse"], "W1A-01-01 - KTA")
            self.assertEqual(row["suggested_batch_no"], "0000000070")
            self.assertEqual(row["deficit_qty"], 15.0)
            self.assertEqual(row["picked_qty"], 15.0)
            self.assertEqual(row["is_picked"], 0)
        finally:
            order.delete(force=True)
