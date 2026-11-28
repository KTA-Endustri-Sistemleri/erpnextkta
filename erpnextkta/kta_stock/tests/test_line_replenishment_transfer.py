# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, nowtime

from erpnextkta.kta_shopfloor.services.reservation_deficit_service import (
    _get_drafts_by_item,
)
from erpnextkta.kta_stock.line_replenishment_service import (
    complete_line_replenishment_picking,
    create_line_replenishment_order,
)
from erpnextkta.kta_stock.setup import (
    PDA_ROLE_STOCK_USER,
    setup_pda_roles_and_permissions,
)
from erpnextkta.tests.test_utils import create_test_item_group


class TestLineReplenishmentTransfer(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = "_Test Company"
        cls.parent_wh = "_Test Line Replenish Group - _TC"
        cls.target_wh = "_Test Line Replenish 1 - _TC"
        cls.sibling_wh = "_Test Line Replenish 2 - _TC"
        cls.central_wh = "_Test Line Central - _TC"
        cls.shelf_1 = "_Test Shelf 1 - _TC"
        cls.shelf_2 = "_Test Shelf 2 - _TC"

        cls._ensure_warehouses()
        cls._ensure_items()

    @classmethod
    def _ensure_warehouses(cls):
        if not frappe.db.exists("Warehouse", cls.parent_wh):
            p_wh = frappe.new_doc("Warehouse")
            p_wh.warehouse_name = cls.parent_wh.replace(" - _TC", "")
            p_wh.company = cls.company
            p_wh.is_group = 1
            p_wh.flags.ignore_permissions = True
            p_wh.insert()

        for wh_name in [
            cls.target_wh,
            cls.sibling_wh,
            cls.central_wh,
            cls.shelf_1,
            cls.shelf_2,
        ]:
            if not frappe.db.exists("Warehouse", wh_name):
                wh = frappe.new_doc("Warehouse")
                wh.warehouse_name = wh_name.replace(" - _TC", "")
                wh.company = cls.company
                wh.parent_warehouse = cls.parent_wh
                wh.is_group = 0
                wh.flags.ignore_permissions = True
                wh.insert()

    @classmethod
    def _ensure_items(cls):
        item_group = create_test_item_group()

        if not frappe.db.exists("Item", "_TEST-LRO-NO-BATCH"):
            item = frappe.new_doc("Item")
            item.item_code = "_TEST-LRO-NO-BATCH"
            item.item_name = "Test Non-Batch Item"
            item.item_group = item_group
            item.stock_uom = "Nos"
            item.is_stock_item = 1
            item.has_batch_no = 0
            item.flags.ignore_permissions = True
            item.insert()

        if not frappe.db.exists("Item", "_TEST-LRO-ITEM-2"):
            item = frappe.new_doc("Item")
            item.item_code = "_TEST-LRO-ITEM-2"
            item.item_name = "Test Item 2"
            item.item_group = item_group
            item.stock_uom = "Nos"
            item.is_stock_item = 1
            item.has_batch_no = 0
            item.flags.ignore_permissions = True
            item.insert()

        if not frappe.db.exists("Item", "_TEST-LRO-BATCH"):
            item = frappe.new_doc("Item")
            item.item_code = "_TEST-LRO-BATCH"
            item.item_name = "Test Batch Item"
            item.item_group = item_group
            item.stock_uom = "Nos"
            item.is_stock_item = 1
            item.has_batch_no = 1
            item.create_new_batch = 1
            item.flags.ignore_permissions = True
            item.insert()

    def _ensure_stock(
        self,
        item_code: str,
        warehouse: str,
        required_qty: float = 200.0,
        batch_no: str | None = None,
    ):
        current_qty = flt(
            frappe.db.get_value(
                "Bin",
                {"item_code": item_code, "warehouse": warehouse},
                "actual_qty",
            )
            or 0
        )
        if current_qty < required_qty:
            needed = (required_qty - current_qty) + 100.0
            item_row = {
                "item_code": item_code,
                "t_warehouse": warehouse,
                "qty": needed,
                "basic_rate": 10.0,
                "uom": "Nos",
                "conversion_factor": 1.0,
            }
            if batch_no:
                if not frappe.db.exists("Batch", batch_no):
                    b = frappe.new_doc("Batch")
                    b.name = batch_no
                    b.batch_id = batch_no
                    b.item = item_code
                    b.flags.ignore_permissions = True
                    b.insert()
                item_row["batch_no"] = batch_no
                item_row["use_serial_batch_fields"] = 1

            se = frappe.new_doc("Stock Entry")
            se.stock_entry_type = "Material Receipt"
            se.purpose = "Material Receipt"
            se.company = self.company
            se.append("items", item_row)
            se.flags.ignore_permissions = True
            se.insert()
            se.submit()

    def test_over_picking_within_tolerance_accepted(self):
        """Picking up to 15% over deficit is accepted and creates transfer."""
        self._ensure_stock("_TEST-LRO-NO-BATCH", self.central_wh, 200.0)

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": "_TEST-LRO-NO-BATCH",
                    "deficit_qty": 100.0,
                    "suggested_source_warehouse": self.central_wh,
                }
            ],
            company=self.company,
        )

        picked_items = [
            {
                "item_code": "_TEST-LRO-NO-BATCH",
                "picked_qty": 110.0,
                "picked_source_warehouse": self.central_wh,
            }
        ]

        se_name = complete_line_replenishment_picking(order_name, picked_items)
        self.assertTrue(se_name)

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertEqual(doc.status, "Completed")
        self.assertEqual(doc.total_picked_qty, 110.0)
        self.assertEqual(doc.stock_entry, se_name)

        se = frappe.get_doc("Stock Entry", se_name)
        self.assertEqual(se.docstatus, 1)
        self.assertEqual(se.purpose, "Material Transfer")
        self.assertEqual(flt(se.items[0].qty), 110.0)

    def test_over_picking_beyond_tolerance_rejected(self):
        """Picking more than 15% over deficit raises ValidationError."""
        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": "_TEST-LRO-NO-BATCH",
                    "deficit_qty": 100.0,
                    "suggested_source_warehouse": self.central_wh,
                }
            ],
            company=self.company,
        )

        picked_items = [
            {
                "item_code": "_TEST-LRO-NO-BATCH",
                "picked_qty": 130.0,
                "picked_source_warehouse": self.central_wh,
            }
        ]

        with self.assertRaises(frappe.ValidationError):
            complete_line_replenishment_picking(order_name, picked_items)

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertEqual(doc.status, "Draft")
        self.assertFalse(doc.stock_entry)
        frappe.delete_doc("KTA Line Replenishment Order", order_name, force=True)

    def test_transfer_creates_and_submits_stock_entry(self):
        """Completing picking creates Material Transfer Stock Entry and marks order Completed."""
        self._ensure_stock("_TEST-LRO-ITEM-2", self.central_wh, 100.0)

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": "_TEST-LRO-ITEM-2",
                    "deficit_qty": 35.0,
                    "suggested_source_warehouse": self.central_wh,
                }
            ],
            company=self.company,
        )

        se_name = complete_line_replenishment_picking(order_name)
        self.assertTrue(se_name)

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertEqual(doc.status, "Completed")
        self.assertEqual(doc.total_picked_qty, 35.0)
        self.assertEqual(doc.stock_entry, se_name)

        se = frappe.get_doc("Stock Entry", se_name)
        self.assertEqual(se.docstatus, 1)
        self.assertEqual(se.purpose, "Material Transfer")
        self.assertEqual(se.items[0].s_warehouse, self.central_wh)
        self.assertEqual(se.items[0].t_warehouse, self.target_wh)
        self.assertEqual(flt(se.items[0].qty), 35.0)

    def test_order_cancellation_cancels_stock_entry(self):
        """Cancelling replenishment order cancels linked submitted Stock Entry."""
        self._ensure_stock("_TEST-LRO-NO-BATCH", self.central_wh, 100.0)

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": "_TEST-LRO-NO-BATCH",
                    "deficit_qty": 25.0,
                    "suggested_source_warehouse": self.central_wh,
                }
            ],
            company=self.company,
        )

        se_name = complete_line_replenishment_picking(order_name)
        order = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertEqual(order.stock_entry, se_name)

        se = frappe.get_doc("Stock Entry", se_name)
        self.assertEqual(se.docstatus, 1)

        order.cancel()

        se.reload()
        self.assertEqual(se.docstatus, 2)

    def test_transfer_with_exact_leaf_warehouse_and_full_batch_quantities(self):
        """Material Transfer executes with exact shelf warehouses and full batch quantities."""
        item_code = "_TEST-LRO-NO-BATCH"
        self._ensure_stock(item_code, self.shelf_1, 50.0)
        self._ensure_stock(item_code, self.shelf_2, 50.0)

        # Order with multiple shelf rows (full batch rounding simulation)
        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": item_code,
                    "deficit_qty": 15.0,
                    "suggested_source_warehouse": self.shelf_1,
                },
                {
                    "item_code": item_code,
                    "deficit_qty": 15.0,
                    "suggested_source_warehouse": self.shelf_2,
                },
            ],
            company=self.company,
        )

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertEqual(len(doc.items), 2)
        self.assertEqual(doc.total_deficit_qty, 30.0)

        # Complete picking without manual modification (defaults picked_qty = deficit_qty)
        se_name = complete_line_replenishment_picking(order_name)
        self.assertTrue(se_name)

        doc.reload()
        self.assertEqual(doc.status, "Completed")
        self.assertEqual(doc.total_picked_qty, 30.0)
        self.assertEqual(doc.stock_entry, se_name)

        se = frappe.get_doc("Stock Entry", se_name)
        self.assertEqual(se.docstatus, 1)
        self.assertEqual(len(se.items), 2)

        # Verify exact leaf shelf warehouses are used
        self.assertEqual(se.items[0].s_warehouse, self.shelf_1)
        self.assertEqual(flt(se.items[0].qty), 15.0)
        self.assertEqual(
            frappe.db.get_value("Warehouse", se.items[0].s_warehouse, "is_group"),
            0,
        )

        self.assertEqual(se.items[1].s_warehouse, self.shelf_2)
        self.assertEqual(flt(se.items[1].qty), 15.0)
        self.assertEqual(
            frappe.db.get_value("Warehouse", se.items[1].s_warehouse, "is_group"),
            0,
        )

    def test_transfer_group_warehouse_resolved_to_leaf_shelf(self):
        """If source warehouse is a group warehouse, it is resolved to a leaf shelf."""
        item_code = "_TEST-LRO-NO-BATCH"
        # Ensure stock in a leaf warehouse under parent_wh
        self._ensure_stock(item_code, self.central_wh, 50.0)

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": item_code,
                    "deficit_qty": 20.0,
                    "suggested_source_warehouse": self.parent_wh,
                }
            ],
            company=self.company,
        )

        se_name = complete_line_replenishment_picking(order_name)
        self.assertTrue(se_name)

        se = frappe.get_doc("Stock Entry", se_name)
        self.assertEqual(se.docstatus, 1)

        # Source warehouse must NOT be the group warehouse
        self.assertNotEqual(se.items[0].s_warehouse, self.parent_wh)
        self.assertEqual(
            frappe.db.get_value("Warehouse", se.items[0].s_warehouse, "is_group"),
            0,
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _create_batch_item_and_receive(
        self,
        item_code: str,
        warehouse: str,
        batch_id: str,
        qty: float,
    ) -> str:
        item_group = create_test_item_group()
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": item_code,
                    "item_group": item_group,
                    "stock_uom": "Nos",
                    "is_stock_item": 1,
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                }
            ).insert(ignore_permissions=True)

        if not frappe.db.exists("Batch", batch_id):
            frappe.get_doc(
                {
                    "doctype": "Batch",
                    "batch_id": batch_id,
                    "item": item_code,
                    "batch_qty": 0,
                }
            ).insert(ignore_permissions=True)

        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": self.company,
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "items": [
                    {
                        "item_code": item_code,
                        "t_warehouse": warehouse,
                        "qty": flt(qty),
                        "allow_zero_valuation_rate": 1,
                        "batch_no": batch_id,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return batch_id

    def test_fifo_override_full_box_over_15_percent_accepted_and_logged_to_remarks(
        self,
    ):
        """Intact box >15% over deficit is accepted on FIFO override and logged to remarks."""
        uid = frappe.generate_hash("", 5).upper()
        item_code = f"_TEST-LRO-FOV-{uid}"
        batch_a = f"FA{uid}0001"
        batch_b = f"FB{uid}0001"

        self._create_batch_item_and_receive(item_code, self.shelf_1, batch_a, 100.0)
        self._create_batch_item_and_receive(item_code, self.shelf_2, batch_b, 140.0)

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": self.target_wh,
                "company": self.company,
                "items": [
                    {
                        "item_code": item_code,
                        "deficit_qty": 100.0,
                        "suggested_source_warehouse": self.shelf_1,
                        "suggested_batch_no": batch_a,
                        "uom": "Nos",
                    }
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.insert(ignore_permissions=True)

        picked_items = [
            {
                "name": order.items[0].name,
                "item_code": item_code,
                "is_picked": 1,
                "is_skipped": 0,
                "picked_batch_no": batch_b,
                "picked_source_warehouse": self.shelf_2,
                "picked_qty": 140.0,
            }
        ]
        se_name = complete_line_replenishment_picking(order.name, picked_items)
        self.assertTrue(se_name)

        order.reload()
        self.assertEqual(order.status, "Completed")
        self.assertEqual(order.items[0].is_fifo_override, 1)
        self.assertEqual(order.items[0].picked_batch_no, batch_b)
        self.assertEqual(order.items[0].picked_source_warehouse, self.shelf_2)
        self.assertEqual(flt(order.items[0].picked_qty), 140.0)
        self.assertIn("[FIFO SAPMASI]", order.remarks or "")
        self.assertIn(batch_a, order.remarks or "")
        self.assertIn(batch_b, order.remarks or "")
        self.assertIn(self.shelf_1, order.remarks or "")
        self.assertIn(self.shelf_2, order.remarks or "")

        se = frappe.get_doc("Stock Entry", se_name)
        self.assertEqual(se.docstatus, 1)
        self.assertEqual(se.items[0].s_warehouse, self.shelf_2)
        self.assertEqual(se.items[0].batch_no, batch_b)
        self.assertEqual(flt(se.items[0].qty), 140.0)
        self.assertIn("[FIFO SAPMASI]", se.remarks or "")
        self.assertIn(batch_a, se.remarks or "")
        self.assertIn(batch_b, se.remarks or "")

    def test_picked_items_rejects_partial_box_duplicate_batch_stale_balance_and_incomplete_rows(
        self,
    ):
        """Reject partial box, duplicate batch consumption, stale moved box, and incomplete rows."""
        uid = frappe.generate_hash("", 5).upper()
        item_code = f"_TEST-LRO-VAL-{uid}"
        batch_1 = f"VA{uid}0001"
        batch_2 = f"VB{uid}0001"

        self._create_batch_item_and_receive(item_code, self.shelf_1, batch_1, 80.0)
        self._create_batch_item_and_receive(item_code, self.shelf_2, batch_2, 60.0)

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": self.target_wh,
                "company": self.company,
                "items": [
                    {
                        "item_code": item_code,
                        "deficit_qty": 80.0,
                        "suggested_source_warehouse": self.shelf_1,
                        "suggested_batch_no": batch_1,
                        "uom": "Nos",
                    },
                    {
                        "item_code": item_code,
                        "deficit_qty": 60.0,
                        "suggested_source_warehouse": self.shelf_2,
                        "suggested_batch_no": batch_2,
                        "uom": "Nos",
                    },
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.insert(ignore_permissions=True)

        # (a) Partial box qty (< live_qty 80.0)
        with self.assertRaises(frappe.ValidationError):
            complete_line_replenishment_picking(
                order.name,
                [
                    {
                        "name": order.items[0].name,
                        "item_code": item_code,
                        "is_picked": 1,
                        "picked_batch_no": batch_1,
                        "picked_source_warehouse": self.shelf_1,
                        "picked_qty": 50.0,
                    },
                    {
                        "name": order.items[1].name,
                        "item_code": item_code,
                        "is_picked": 1,
                        "picked_batch_no": batch_2,
                        "picked_source_warehouse": self.shelf_2,
                        "picked_qty": 60.0,
                    },
                ],
            )

        # (b) Duplicate batch consumption across two rows
        with self.assertRaises(frappe.ValidationError):
            complete_line_replenishment_picking(
                order.name,
                [
                    {
                        "name": order.items[0].name,
                        "item_code": item_code,
                        "is_picked": 1,
                        "picked_batch_no": batch_1,
                        "picked_source_warehouse": self.shelf_1,
                        "picked_qty": 80.0,
                    },
                    {
                        "name": order.items[1].name,
                        "item_code": item_code,
                        "is_picked": 1,
                        "picked_batch_no": batch_1,
                        "picked_source_warehouse": self.shelf_1,
                        "picked_qty": 80.0,
                    },
                ],
            )

        # (d) Incomplete rows (only 1 of 2 rows supplied)
        with self.assertRaises(frappe.ValidationError):
            complete_line_replenishment_picking(
                order.name,
                [
                    {
                        "name": order.items[0].name,
                        "item_code": item_code,
                        "is_picked": 1,
                        "picked_batch_no": batch_1,
                        "picked_source_warehouse": self.shelf_1,
                        "picked_qty": 80.0,
                    }
                ],
            )

        # (c) Stale balance: move batch_1 out of shelf_1 before submit
        move_se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Transfer",
                "purpose": "Material Transfer",
                "company": self.company,
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "items": [
                    {
                        "item_code": item_code,
                        "s_warehouse": self.shelf_1,
                        "t_warehouse": self.sibling_wh,
                        "qty": 80.0,
                        "batch_no": batch_1,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        move_se.insert(ignore_permissions=True)
        move_se.submit()

        with self.assertRaises(frappe.ValidationError):
            complete_line_replenishment_picking(
                order.name,
                [
                    {
                        "name": order.items[0].name,
                        "item_code": item_code,
                        "is_picked": 1,
                        "picked_batch_no": batch_1,
                        "picked_source_warehouse": self.shelf_1,
                        "picked_qty": 80.0,
                    },
                    {
                        "name": order.items[1].name,
                        "item_code": item_code,
                        "is_picked": 1,
                        "picked_batch_no": batch_2,
                        "picked_source_warehouse": self.shelf_2,
                        "picked_qty": 60.0,
                    },
                ],
            )

    def test_skip_item_rejected_for_stock_user_and_allowed_for_stock_manager_with_deficit_reappearance(
        self,
    ):
        """Skip requires Stock Manager; partial skip logs remarks and releases skipped deficit."""
        setup_pda_roles_and_permissions()
        uid = frappe.generate_hash("", 5).upper()
        item_1 = f"_TEST-LRO-SKP1-{uid}"
        item_2 = f"_TEST-LRO-SKP2-{uid}"
        batch_1 = f"K1{uid}0001"
        batch_2 = f"K2{uid}0001"

        self._create_batch_item_and_receive(item_1, self.shelf_1, batch_1, 30.0)
        self._create_batch_item_and_receive(item_2, self.shelf_2, batch_2, 25.0)

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": self.target_wh,
                "company": self.company,
                "items": [
                    {
                        "item_code": item_1,
                        "deficit_qty": 30.0,
                        "suggested_source_warehouse": self.shelf_1,
                        "suggested_batch_no": batch_1,
                        "uom": "Nos",
                    },
                    {
                        "item_code": item_2,
                        "deficit_qty": 25.0,
                        "suggested_source_warehouse": self.shelf_2,
                        "suggested_batch_no": batch_2,
                        "uom": "Nos",
                    },
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.insert(ignore_permissions=True)

        # While Draft, both items are deducted as in-flight drafts
        drafts_before = _get_drafts_by_item(self.target_wh)
        self.assertIn(item_1, drafts_before)
        self.assertIn(item_2, drafts_before)

        pda_user = f"skip_pda_{uid.lower()}@example.com"
        mgr_user = f"skip_mgr_{uid.lower()}@example.com"
        for email, role in (
            (pda_user, PDA_ROLE_STOCK_USER),
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

        payload = [
            {
                "name": order.items[0].name,
                "item_code": item_1,
                "is_picked": 1,
                "is_skipped": 0,
                "picked_batch_no": batch_1,
                "picked_source_warehouse": self.shelf_1,
                "picked_qty": 30.0,
            },
            {
                "name": order.items[1].name,
                "item_code": item_2,
                "is_picked": 0,
                "is_skipped": 1,
            },
        ]

        # PDA Stock User cannot skip
        frappe.set_user(pda_user)
        with self.assertRaises(frappe.PermissionError):
            complete_line_replenishment_picking(order.name, payload)

        # Stock Manager can skip Row 2 and pick Row 1
        frappe.set_user(mgr_user)
        se_name = complete_line_replenishment_picking(order.name, payload)
        self.assertTrue(se_name)

        order.reload()
        self.assertEqual(order.status, "Completed")
        self.assertEqual(order.stock_entry, se_name)
        self.assertEqual(flt(order.total_picked_qty), 30.0)
        self.assertEqual(order.items[1].is_skipped, 1)
        self.assertEqual(order.items[1].skipped_by, mgr_user)
        self.assertEqual(order.items[1].is_picked, 0)
        self.assertEqual(flt(order.items[1].picked_qty), 0.0)
        self.assertIn("[ATLANAN KALEMLER]", order.remarks or "")
        self.assertIn(item_2, order.remarks or "")

        se = frappe.get_doc("Stock Entry", se_name)
        self.assertEqual(len(se.items), 1)
        self.assertEqual(se.items[0].item_code, item_1)
        self.assertIn("[ATLANAN KALEMLER]", se.remarks or "")

        # Order is now Completed, so item_2 is no longer suppressed by _get_drafts_by_item
        drafts_after = _get_drafts_by_item(self.target_wh)
        self.assertFalse(
            any(r["parent"] == order.name for r in drafts_after.get(item_2, []))
        )

    def test_all_items_skipped_cancels_order_without_empty_stock_entry(self):
        """Skipping all items cancels order with no Stock Entry and releases deficits."""
        uid = frappe.generate_hash("", 5).upper()
        item_1 = f"_TEST-LRO-ALLSKP1-{uid}"
        item_2 = f"_TEST-LRO-ALLSKP2-{uid}"
        batch_1 = f"A1{uid}0001"
        batch_2 = f"A2{uid}0001"

        self._create_batch_item_and_receive(item_1, self.shelf_1, batch_1, 20.0)
        self._create_batch_item_and_receive(item_2, self.shelf_2, batch_2, 15.0)

        order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": self.target_wh,
                "company": self.company,
                "items": [
                    {
                        "item_code": item_1,
                        "deficit_qty": 20.0,
                        "suggested_source_warehouse": self.shelf_1,
                        "suggested_batch_no": batch_1,
                        "uom": "Nos",
                    },
                    {
                        "item_code": item_2,
                        "deficit_qty": 15.0,
                        "suggested_source_warehouse": self.shelf_2,
                        "suggested_batch_no": batch_2,
                        "uom": "Nos",
                    },
                ],
            }
        )
        order.flags.ignore_mandatory = True
        order.insert(ignore_permissions=True)

        mgr_user = f"allskip_mgr_{uid.lower()}@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": mgr_user,
                "first_name": mgr_user.split("@")[0],
                "enabled": 1,
                "send_welcome_email": 0,
                "roles": [{"role": "Stock Manager"}],
            }
        ).insert(ignore_permissions=True)
        frappe.clear_cache(user=mgr_user)
        frappe.set_user(mgr_user)

        se_name = complete_line_replenishment_picking(
            order.name,
            [
                {"name": order.items[0].name, "item_code": item_1, "is_skipped": 1},
                {"name": order.items[1].name, "item_code": item_2, "is_skipped": 1},
            ],
        )
        self.assertEqual(se_name, "")

        order.reload()
        self.assertEqual(order.status, "Cancelled")
        self.assertFalse(order.stock_entry)
        self.assertEqual(flt(order.total_picked_qty), 0.0)
        self.assertIn("[ATLANAN KALEMLER]", order.remarks or "")
        self.assertIn(item_1, order.remarks or "")
        self.assertIn(item_2, order.remarks or "")

        drafts_after = _get_drafts_by_item(self.target_wh)
        self.assertFalse(
            any(r["parent"] == order.name for r in drafts_after.get(item_1, []))
        )
        self.assertFalse(
            any(r["parent"] == order.name for r in drafts_after.get(item_2, []))
        )
