# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, nowtime

from erpnextkta.kta_stock.line_replenishment_service import (
    complete_line_replenishment_picking,
)
from erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking import (
    get_context,
    get_open_replenishment_orders,
    get_replenishment_order_details,
    resolve_scanned_barcode,
)
from erpnextkta.kta_stock.setup import (
    PDA_ROLE_STOCK_USER,
    setup_pda_roles_and_permissions,
)


class TestLineReplenishmentPickingPage(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

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
        from erpnextkta.tests.test_utils import create_test_item_group

        company = (
            "_Test Company"
            if frappe.db.exists("Company", "_Test Company")
            else frappe.db.get_value("Company", {}, "name")
        )
        self.assertTrue(company)

        item_group = create_test_item_group()
        item_code = "_TEST-LRO-PICK-BATCH-ITEM"
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": item_code,
                    "item_group": item_group,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                }
            ).insert(ignore_permissions=True)

        parent_wh = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1}, "name"
        )
        abbr = frappe.db.get_value("Company", company, "abbr") or "_TC"

        def ensure_leaf_wh(wh_label: str) -> str:
            wh_name = f"{wh_label} - {abbr}"
            if not frappe.db.exists("Warehouse", wh_name):
                wh_doc = frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": wh_label,
                        "company": company,
                        "parent_warehouse": parent_wh,
                        "is_group": 0,
                    }
                ).insert(ignore_permissions=True)
                return wh_doc.name
            return wh_name

        target_wh = ensure_leaf_wh("_Test LRO Pick Target")
        source_wh = ensure_leaf_wh("_Test LRO Pick Source")

        batch_id = "_TEST-LRO-PICK-BATCH-01"
        if not frappe.db.exists("Batch", batch_id):
            batch_doc = frappe.get_doc(
                {
                    "doctype": "Batch",
                    "batch_id": batch_id,
                    "item": item_code,
                    "batch_qty": 0,
                }
            ).insert(ignore_permissions=True)
            batch_name = batch_doc.name
        else:
            batch_name = batch_id

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": target_wh,
                "company": company,
                "items": [
                    {
                        "item_code": item_code,
                        "deficit_qty": 15.0,
                        "suggested_source_warehouse": source_wh,
                        "suggested_batch_no": batch_name,
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
            self.assertEqual(row["suggested_source_warehouse"], source_wh)
            self.assertEqual(row["suggested_batch_no"], batch_name)
            self.assertEqual(row["deficit_qty"], 15.0)
            self.assertEqual(row["picked_qty"], 15.0)
            self.assertEqual(row["is_picked"], 0)
        finally:
            order.delete(force=True)

    def test_replenishment_picking_rpcs_allow_pda_stock_user_and_reject_guest_or_unauthorized(
        self,
    ):
        from erpnextkta.tests.test_utils import (
            create_test_company,
            create_test_item_group,
        )

        setup_pda_roles_and_permissions()
        non_stock_role = "_Test Non Stock Picking Role"
        if not frappe.db.exists("Role", non_stock_role):
            frappe.get_doc(
                {"doctype": "Role", "role_name": non_stock_role, "desk_access": 0}
            ).insert(ignore_permissions=True)

        uid = frappe.generate_hash("", 5)
        pure_email = f"lro_pure_pda_{uid}@example.com"
        unauth_email = f"lro_unauth_{uid}@example.com"

        frappe.get_doc(
            {
                "doctype": "User",
                "email": pure_email,
                "first_name": f"_Test LRO Pure {uid}",
                "enabled": 1,
                "send_welcome_email": 0,
                "roles": [{"role": PDA_ROLE_STOCK_USER}],
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "User",
                "email": unauth_email,
                "first_name": f"_Test LRO Unauth {uid}",
                "enabled": 1,
                "send_welcome_email": 0,
                "roles": [{"role": non_stock_role}],
            }
        ).insert(ignore_permissions=True)
        self.assertEqual(
            frappe.db.get_value("User", pure_email, "user_type"), "Website User"
        )
        frappe.clear_cache(user=pure_email)
        frappe.clear_cache(user=unauth_email)

        company = frappe.db.get_value(
            "Company", "_Test Company", "name"
        ) or create_test_company("_Test Company")
        abbr = frappe.db.get_value("Company", company, "abbr") or "_TC"
        parent_wh = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1}, "name"
        )

        def ensure_leaf(label: str) -> str:
            wh_name = f"{label} - {abbr}"
            if not frappe.db.exists("Warehouse", wh_name):
                wh_doc = frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": label,
                        "company": company,
                        "parent_warehouse": parent_wh,
                        "is_group": 0,
                    }
                ).insert(ignore_permissions=True)
                return wh_doc.name
            return wh_name

        source_wh = ensure_leaf(f"_Test LRO Src {uid}")
        target_wh = ensure_leaf(f"_Test LRO Tgt {uid}")

        item_group = create_test_item_group()
        item_code = f"_TEST-LRO-AUTH-{uid}"
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_code,
                "item_group": item_group,
                "is_stock_item": 1,
                "stock_uom": "Nos",
                "has_batch_no": 1,
                "create_new_batch": 0,
            }
        ).insert(ignore_permissions=True)

        batch_id = f"Z{frappe.generate_hash('', 6).upper()}0001"
        frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": batch_id,
                "item": item_code,
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)

        receipt = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": company,
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "items": [
                    {
                        "item_code": item_code,
                        "t_warehouse": source_wh,
                        "qty": flt(10.0),
                        "basic_rate": 10.0,
                        "allow_zero_valuation_rate": 0,
                        "batch_no": batch_id,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        receipt.insert(ignore_permissions=True)
        receipt.submit()

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": target_wh,
                "company": company,
                "items": [
                    {
                        "item_code": item_code,
                        "deficit_qty": 10.0,
                        "suggested_source_warehouse": source_wh,
                        "suggested_batch_no": batch_id,
                        "uom": "Nos",
                    }
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.insert(ignore_permissions=True)

        for blocked_user in ("Guest", unauth_email):
            frappe.set_user(blocked_user)
            with self.assertRaises(frappe.PermissionError):
                get_context({})
            with self.assertRaises(frappe.PermissionError):
                get_open_replenishment_orders()
            with self.assertRaises(frappe.PermissionError):
                get_replenishment_order_details(order.name)
            with self.assertRaises(frappe.PermissionError):
                resolve_scanned_barcode(item_code)
            with self.assertRaises(frappe.PermissionError):
                complete_line_replenishment_picking(order.name)

        frappe.set_user(pure_email)
        get_context({})
        open_orders = get_open_replenishment_orders()
        self.assertTrue(any(o["name"] == order.name for o in open_orders))
        details = get_replenishment_order_details(order.name)
        self.assertEqual(details["name"], order.name)
        resolved = resolve_scanned_barcode(item_code)
        self.assertEqual(resolved["item_code"], item_code)

        se_name = complete_line_replenishment_picking(order.name)
        self.assertEqual(
            frappe.db.get_value("Stock Entry", se_name, "owner"), pure_email
        )
