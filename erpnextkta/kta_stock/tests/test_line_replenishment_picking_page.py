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

    def test_order_details_walk_order_sorting_role_flags_and_has_batch(self):
        from erpnextkta.tests.test_utils import (
            create_test_company,
            create_test_item_group,
        )

        setup_pda_roles_and_permissions()
        uid = frappe.generate_hash("", 5).upper()
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

        wh_target = ensure_leaf(f"_Test Walk Tgt {uid}")
        wh_w1a_10 = ensure_leaf(f"W1A-10-01-{uid}")
        wh_w1a_02 = ensure_leaf(f"W1A-02-01-{uid}")
        wh_w1b_01 = ensure_leaf(f"W1B-01-01-{uid}")

        item_group = create_test_item_group()
        batch_item = f"_TEST-WALK-BATCH-{uid}"
        non_batch_item = f"_TEST-WALK-NOBATCH-{uid}"
        for code, has_batch in ((batch_item, 1), (non_batch_item, 0)):
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": code,
                    "item_name": code,
                    "item_group": item_group,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": has_batch,
                    "create_new_batch": 0,
                }
            ).insert(ignore_permissions=True)

        b1 = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": f"W{uid}0001",
                "item": batch_item,
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)
        b2 = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": f"W{uid}0002",
                "item": batch_item,
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": wh_target,
                "company": company,
                "items": [
                    {
                        "item_code": batch_item,
                        "deficit_qty": 20.0,
                        "suggested_source_warehouse": wh_w1a_10,
                        "suggested_batch_no": b1.name,
                        "uom": "Nos",
                    },
                    {
                        "item_code": non_batch_item,
                        "deficit_qty": 15.0,
                        "suggested_source_warehouse": wh_w1b_01,
                        "uom": "Nos",
                    },
                    {
                        "item_code": batch_item,
                        "deficit_qty": 10.0,
                        "suggested_source_warehouse": wh_w1a_02,
                        "suggested_batch_no": b2.name,
                        "uom": "Nos",
                    },
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.insert(ignore_permissions=True)

        pda_user = f"walk_pda_{uid.lower()}@example.com"
        stock_user = f"walk_su_{uid.lower()}@example.com"
        mgr_user = f"walk_mgr_{uid.lower()}@example.com"
        for email, role in (
            (pda_user, PDA_ROLE_STOCK_USER),
            (stock_user, "Stock User"),
            (mgr_user, "Stock Manager"),
        ):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": email.split("@")[0],
                    "enabled": 1,
                    "send_welcome_email": 0,
                    "roles": [{"role": role}],
                }
            ).insert(ignore_permissions=True)
            frappe.clear_cache(user=email)

        for user_email in (pda_user, stock_user):
            frappe.set_user(user_email)
            details = get_replenishment_order_details(order.name)
            self.assertFalse(details.get("can_skip_items"))
            self.assertEqual(
                [r["suggested_source_warehouse"] for r in details["items"]],
                [wh_w1a_02, wh_w1a_10, wh_w1b_01],
            )
            self.assertEqual([r["has_batch_no"] for r in details["items"]], [1, 1, 0])
            for r in details["items"]:
                self.assertEqual(r["is_skipped"], 0)
                self.assertIsNone(r["skipped_by"])
                self.assertEqual(r["is_fifo_override"], 0)

        frappe.set_user(mgr_user)
        mgr_details = get_replenishment_order_details(order.name)
        self.assertTrue(mgr_details.get("can_skip_items"))

    def test_resolve_scanned_barcode_returns_live_shelf_and_target_flags(self):
        from erpnextkta.tests.test_utils import (
            create_test_company,
            create_test_item_group,
        )

        uid = frappe.generate_hash("", 5).upper()
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

        wh_source = ensure_leaf(f"_Test Scan Src {uid}")
        wh_target = ensure_leaf(f"_Test Scan Tgt {uid}")

        item_group = create_test_item_group()
        item_code = f"_TEST-SCAN-LIVE-{uid}"
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

        active_batch = f"S{uid}0001"
        disabled_batch = f"S{uid}0002"
        frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": active_batch,
                "item": item_code,
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": disabled_batch,
                "item": item_code,
                "disabled": 1,
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)

        # Receive 45.0 live ledger qty into wh_source
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
                        "t_warehouse": wh_source,
                        "qty": 45.0,
                        "allow_zero_valuation_rate": 1,
                        "batch_no": active_batch,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        receipt.insert(ignore_permissions=True)
        receipt.submit()

        # Create KTA Stock Label with intentionally stale qty (999.0)
        lbl = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "reference_doctype": "Purchase Receipt",
                "reference_name": f"MAT-PRE-{uid}",
                "item_code": item_code,
                "qty": 999.0,
                "uom": "Nos",
                "batch": active_batch,
                "sut_barcode": f"SUT-{active_batch}",
                "target_warehouse": wh_source,
                "quality_ref": "ATLA 5/1",
                "supplier_delivery_note": f"DN-{uid}",
                "gr_posting_date": nowdate(),
            }
        )
        lbl.flags.ignore_links = True
        lbl.insert(ignore_permissions=True)

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": wh_target,
                "company": company,
                "items": [
                    {
                        "item_code": item_code,
                        "deficit_qty": 45.0,
                        "suggested_source_warehouse": wh_source,
                        "suggested_batch_no": active_batch,
                        "uom": "Nos",
                    }
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.insert(ignore_permissions=True)

        # 1. Scanning via Batch returns live shelf & live qty
        res_batch = resolve_scanned_barcode(active_batch, order_name=order.name)
        self.assertEqual(res_batch["item_code"], item_code)
        self.assertEqual(res_batch["batch_no"], active_batch)
        self.assertEqual(res_batch["warehouse"], wh_source)
        self.assertEqual(flt(res_batch["qty"]), 45.0)
        self.assertFalse(res_batch["already_in_target"])
        self.assertFalse(res_batch["batch_disabled"])
        self.assertEqual(res_batch["has_batch_no"], 1)
        self.assertEqual(
            res_batch["available_balances"], [{"warehouse": wh_source, "qty": 45.0}]
        )

        # 2. Scanning via KTA Stock Label SUT barcode returns live qty (45.0), NOT stale 999.0
        res_label = resolve_scanned_barcode(
            f"SUT-{active_batch}", order_name=order.name
        )
        self.assertEqual(res_label["warehouse"], wh_source)
        self.assertEqual(flt(res_label["qty"]), 45.0)

        # 3. Backward-compatible call without order_name
        res_legacy = resolve_scanned_barcode(active_batch)
        self.assertEqual(res_legacy["item_code"], item_code)
        self.assertEqual(res_legacy["batch_no"], active_batch)
        self.assertEqual(res_legacy["warehouse"], wh_source)
        self.assertEqual(flt(res_legacy["qty"]), 45.0)

        # 4. Disabled batch returns batch_disabled=True, qty=0.0, warehouse=None
        res_disabled = resolve_scanned_barcode(disabled_batch, order_name=order.name)
        self.assertTrue(res_disabled["batch_disabled"])
        self.assertIsNone(res_disabled["warehouse"])
        self.assertEqual(flt(res_disabled["qty"]), 0.0)
        self.assertEqual(res_disabled["available_balances"], [])

        # 5. Transfer batch into order.target_warehouse -> already_in_target=True
        transfer = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Transfer",
                "purpose": "Material Transfer",
                "company": company,
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "items": [
                    {
                        "item_code": item_code,
                        "s_warehouse": wh_source,
                        "t_warehouse": wh_target,
                        "qty": 45.0,
                        "batch_no": active_batch,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        transfer.insert(ignore_permissions=True)
        transfer.submit()

        res_in_target = resolve_scanned_barcode(active_batch, order_name=order.name)
        self.assertTrue(res_in_target["already_in_target"])
        self.assertIsNone(res_in_target["warehouse"])
        self.assertEqual(flt(res_in_target["qty"]), 0.0)
        self.assertEqual(res_in_target["available_balances"], [])
