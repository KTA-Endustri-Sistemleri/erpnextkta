# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnextkta.kta_stock.line_replenishment_service import (
    complete_line_replenishment_picking,
    create_line_replenishment_order,
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
