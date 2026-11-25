# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_stock.line_replenishment_service import (
    allocate_fifo_batch,
    allocate_fifo_batches,
    bulk_allocate_fifo_batches,
    create_line_replenishment_order,
    get_warehouse_leaf_stock,
    override_item_source,
)
from erpnextkta.tests.test_utils import create_test_item_group


class TestLineReplenishmentService(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = "_Test Company"

        if frappe.db.exists("Warehouse", "1501 KESMELER - KTA"):
            cls.target_wh = "1501 KESMELER - KTA"
            cls.sibling_wh = "1503 RATIONAL - KTA"
            cls.parent_wh = "150 ÜRETİM - KTA"
        else:
            cls.parent_wh = "_Test Line Replenish Group - _TC"
            cls.target_wh = "_Test Line Replenish 1 - _TC"
            cls.sibling_wh = "_Test Line Replenish 2 - _TC"

        if frappe.db.exists("Warehouse", "110 HAMMADDE - KTA"):
            cls.central_wh = "110 HAMMADDE - KTA"
            cls.shelf_1 = "W1A-01-01 - KTA"
            cls.shelf_2 = "W1A-01-02 - KTA"
            cls.shelf_3 = "W1A-01-03 - KTA"
        else:
            cls.central_wh = "110 HAMMADDE - _TC"
            cls.shelf_1 = "W1A-01-01 - _TC"
            cls.shelf_2 = "W1A-01-02 - _TC"
            cls.shelf_3 = "W1A-01-03 - _TC"

        cls._ensure_warehouses()
        cls._ensure_items()
        cls._ensure_stock()

    @classmethod
    def _ensure_stock(cls):
        stock_entries = [
            ("_TEST-LRO-NO-BATCH", cls.shelf_1, 150.0),
            ("_TEST-LRO-ITEM-2", cls.shelf_2, 100.0),
        ]
        for item_code, wh, qty in stock_entries:
            has_stock = frappe.db.get_value(
                "Stock Ledger Entry",
                {"item_code": item_code, "warehouse": wh, "is_cancelled": 0},
                "name",
            )
            if not has_stock:
                frappe.get_doc(
                    {
                        "doctype": "Stock Ledger Entry",
                        "item_code": item_code,
                        "warehouse": wh,
                        "actual_qty": qty,
                        "posting_date": "2026-01-01",
                        "posting_time": "10:00:00",
                        "voucher_type": "Stock Entry",
                        "voucher_no": f"TEST-SE-INIT-{item_code}-{wh}",
                        "company": cls.company,
                    }
                ).db_insert()

    @classmethod
    def _ensure_warehouses(cls):
        if not frappe.db.exists("Warehouse", cls.parent_wh):
            p_wh = frappe.new_doc("Warehouse")
            p_wh.warehouse_name = cls.parent_wh.replace(" - _TC", "")
            p_wh.company = cls.company
            p_wh.is_group = 1
            p_wh.flags.ignore_permissions = True
            p_wh.insert()
            cls.parent_wh = p_wh.name

        for attr in ("target_wh", "sibling_wh"):
            wh_name = getattr(cls, attr)
            if not frappe.db.exists("Warehouse", wh_name):
                wh = frappe.new_doc("Warehouse")
                wh.warehouse_name = wh_name.replace(" - _TC", "")
                wh.company = cls.company
                wh.parent_warehouse = cls.parent_wh
                wh.is_group = 0
                wh.flags.ignore_permissions = True
                wh.insert()
                setattr(cls, attr, wh.name)

        if not frappe.db.exists("Warehouse", cls.central_wh):
            c_wh = frappe.new_doc("Warehouse")
            c_wh.warehouse_name = "110 HAMMADDE"
            c_wh.company = cls.company
            c_wh.is_group = 1
            c_wh.flags.ignore_permissions = True
            c_wh.insert()
            cls.central_wh = c_wh.name

        for attr in ("shelf_1", "shelf_2", "shelf_3"):
            s_wh = getattr(cls, attr)
            if not frappe.db.exists("Warehouse", s_wh):
                wh = frappe.new_doc("Warehouse")
                wh.warehouse_name = s_wh.replace(" - KTA", "").replace(" - _TC", "")
                wh.company = cls.company
                wh.parent_warehouse = cls.central_wh
                wh.is_group = 0
                wh.flags.ignore_permissions = True
                wh.insert()
                setattr(cls, attr, wh.name)

        abbr = frappe.db.get_value("Company", cls.company, "abbr") or "_TC"
        root_wh = frappe.db.get_value(
            "Warehouse",
            {
                "company": cls.company,
                "is_group": 1,
                "parent_warehouse": ["in", ["", None]],
            },
            "name",
        ) or frappe.db.get_value(
            "Warehouse", {"company": cls.company, "is_group": 1}, "name"
        )

        cls.fifo_group_wh = f"_Test Line FIFO Group - {abbr}"
        cls.fifo_shelf_a = f"_Test Line FIFO Shelf A - {abbr}"
        cls.fifo_shelf_b = f"_Test Line FIFO Shelf B - {abbr}"
        cls.fifo_target_wh = f"_Test Line FIFO Target - {abbr}"

        if not frappe.db.exists("Warehouse", cls.fifo_group_wh):
            fifo_grp = frappe.new_doc("Warehouse")
            fifo_grp.warehouse_name = "_Test Line FIFO Group"
            fifo_grp.company = cls.company
            if root_wh:
                fifo_grp.parent_warehouse = root_wh
            fifo_grp.is_group = 1
            fifo_grp.flags.ignore_permissions = True
            fifo_grp.insert()
            cls.fifo_group_wh = fifo_grp.name

        for attr, wh_label, parent_wh in (
            ("fifo_shelf_a", "_Test Line FIFO Shelf A", cls.fifo_group_wh),
            ("fifo_shelf_b", "_Test Line FIFO Shelf B", cls.fifo_group_wh),
            ("fifo_target_wh", "_Test Line FIFO Target", root_wh),
        ):
            wh_name = getattr(cls, attr)
            if not frappe.db.exists("Warehouse", wh_name):
                wh = frappe.new_doc("Warehouse")
                wh.warehouse_name = wh_label
                wh.company = cls.company
                if parent_wh:
                    wh.parent_warehouse = parent_wh
                wh.is_group = 0
                wh.flags.ignore_permissions = True
                wh.insert()
                setattr(cls, attr, wh.name)

    @classmethod
    def _ensure_items(cls):
        item_group = create_test_item_group()

        # Non-batch item
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

        # Batch item
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

        # Deficit item 2
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

    def test_create_order_without_target_warehouse_fails(self):
        """Empty target warehouse must raise ValidationError."""
        items = [{"item_code": "_TEST-LRO-NO-BATCH", "deficit_qty": 50.0}]

        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order("", items)

        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order("   ", items)

        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order(None, items)

    def test_create_order_empty_items_fails(self):
        """Empty items list or zero deficit items must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order(self.target_wh, [])

        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order(
                self.target_wh,
                [{"item_code": "_TEST-LRO-NO-BATCH", "deficit_qty": 0.0}],
            )

        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order(
                self.target_wh,
                [{"item_code": "_TEST-LRO-NO-BATCH", "deficit_qty": -10.0}],
            )

    def test_create_order_rejects_zero_stock_items(self):
        """Order creation rejects zero stock items and throws ValidationError if all zero."""
        zero_item = "_TEST-LRO-ZERO-STOCK"
        if not frappe.db.exists("Item", zero_item):
            item = frappe.new_doc("Item")
            item.item_code = zero_item
            item.item_name = "Test Zero Stock Item"
            item.item_group = create_test_item_group()
            item.stock_uom = "Nos"
            item.is_stock_item = 1
            item.flags.ignore_permissions = True
            item.insert()

        frappe.db.delete("Bin", {"item_code": zero_item})
        frappe.db.delete("Stock Ledger Entry", {"item_code": zero_item})

        # 1. When all requested items have zero stock, ValidationError must be raised
        with self.assertRaises(frappe.ValidationError) as cm:
            create_line_replenishment_order(
                target_warehouse=self.target_wh,
                items=[
                    {
                        "item_code": zero_item,
                        "deficit_qty": 20.0,
                        "suggested_source_warehouse": self.central_wh,
                    }
                ],
                company=self.company,
            )

        self.assertTrue(
            "Seçilen hammaddelerin hiçbirinde" in str(cm.exception)
            or "None of the selected items have available stock" in str(cm.exception)
        )

        # 2. When mixed, zero-stock item is skipped and only item with stock is included
        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": zero_item,
                    "deficit_qty": 20.0,
                    "suggested_source_warehouse": self.central_wh,
                },
                {
                    "item_code": "_TEST-LRO-NO-BATCH",
                    "deficit_qty": 15.0,
                    "suggested_source_warehouse": self.central_wh,
                },
            ],
            company=self.company,
        )

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        item_codes = [d.item_code for d in doc.items]
        self.assertNotIn(zero_item, item_codes)
        self.assertIn("_TEST-LRO-NO-BATCH", item_codes)
        self.assertEqual(doc.total_deficit_qty, 15.0)

    def test_get_warehouse_leaf_stock(self):
        """get_warehouse_leaf_stock accurately calculates leaf warehouse stock balances."""
        stock = get_warehouse_leaf_stock(
            item_code="_TEST-LRO-NO-BATCH",
            warehouse=self.central_wh,
            target_warehouse=self.target_wh,
        )
        self.assertGreaterEqual(stock, 50.0)

        zero_stock = get_warehouse_leaf_stock(
            item_code="_NON_EXISTENT_ITEM_",
            warehouse=self.central_wh,
        )
        self.assertEqual(zero_stock, 0.0)

    def test_order_creation_calculates_total_deficit(self):
        """Line Replenishment Order calculates total_deficit_qty accurately."""
        items = [
            {
                "item_code": "_TEST-LRO-NO-BATCH",
                "item_name": "Test Non-Batch Item",
                "uom": "Nos",
                "reserved_qty": 100.0,
                "line_actual_qty": 55.0,
                "deficit_qty": 45.0,
                "suggested_source_warehouse": self.central_wh,
            },
            {
                "item_code": "_TEST-LRO-ITEM-2",
                "item_name": "Test Item 2",
                "uom": "Nos",
                "reserved_qty": 80.0,
                "line_actual_qty": 25.0,
                "deficit_qty": 55.0,
                "suggested_source_warehouse": self.central_wh,
            },
        ]

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=items,
            company=self.company,
        )

        self.assertTrue(order_name)
        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)

        self.assertEqual(doc.status, "Draft")
        self.assertEqual(doc.target_warehouse, self.target_wh)
        self.assertEqual(doc.company, self.company)
        self.assertEqual(doc.total_deficit_qty, 100.0)
        self.assertEqual(len(doc.items), 2)
        self.assertEqual(doc.items[0].deficit_qty, 45.0)
        self.assertEqual(doc.items[1].deficit_qty, 55.0)

    def test_create_order_ignores_legacy_sourcing_kwargs(self):
        """Legacy sourcing kwargs and removed item keys are safely ignored."""
        items = [
            {
                "item_code": "_TEST-LRO-NO-BATCH",
                "deficit_qty": 20.0,
                "sourcing_type": "Line Transfer",
                "free_stock_qty": 25.0,
                "suggested_source_warehouse": self.central_wh,
            }
        ]

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=items,
            company=self.company,
            sourcing_strategy="Smart Sourcing (WIP First)",
        )

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertFalse(doc.meta.has_field("sourcing_strategy"))
        item_meta = frappe.get_meta("KTA Line Replenishment Item")
        self.assertFalse(item_meta.has_field("sourcing_type"))
        self.assertFalse(item_meta.has_field("free_stock_qty"))
        self.assertEqual(doc.total_deficit_qty, 20.0)

    def test_allocate_fifo_batch(self):
        """allocate_fifo_batch returns None for non-batch item, and oldest batch for batch item."""
        # 1. Non-batch item returns None
        non_batch = allocate_fifo_batch("_TEST-LRO-NO-BATCH", self.central_wh)
        self.assertIsNone(non_batch)

        # 2. Batch item setup: 2 batches with stock in central_wh
        batch_item = "_TEST-LRO-BATCH"
        batch_1_name = "BATCH-LRO-TEST-001"
        batch_2_name = "BATCH-LRO-TEST-002"

        if not frappe.db.exists("Batch", batch_1_name):
            b1 = frappe.new_doc("Batch")
            b1.name = batch_1_name
            b1.batch_id = batch_1_name
            b1.item = batch_item
            b1.manufacturing_date = "2026-01-01"
            b1.expiry_date = "2026-05-01"
            b1.flags.ignore_permissions = True
            b1.insert()
        else:
            b1 = frappe.get_doc("Batch", batch_1_name)
            b1.manufacturing_date = "2026-01-01"
            b1.expiry_date = "2026-05-01"
            b1.disabled = 0
            b1.save(ignore_permissions=True)

        if not frappe.db.exists("Batch", batch_2_name):
            b2 = frappe.new_doc("Batch")
            b2.name = batch_2_name
            b2.batch_id = batch_2_name
            b2.item = batch_item
            b2.manufacturing_date = "2026-01-01"
            b2.expiry_date = "2026-08-01"
            b2.flags.ignore_permissions = True
            b2.insert()
        else:
            b2 = frappe.get_doc("Batch", batch_2_name)
            b2.manufacturing_date = "2026-01-01"
            b2.expiry_date = "2026-08-01"
            b2.disabled = 0
            b2.save(ignore_permissions=True)

        # Insert Stock Ledger Entries directly to simulate available batch balances
        frappe.db.sql(
            """
            DELETE FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND warehouse = %s
            """,
            (batch_item, self.central_wh),
        )

        frappe.get_doc(
            {
                "doctype": "Stock Ledger Entry",
                "item_code": batch_item,
                "warehouse": self.central_wh,
                "batch_no": batch_1_name,
                "actual_qty": 30.0,
                "posting_date": "2026-01-01",
                "posting_time": "10:00:00",
                "voucher_type": "Stock Entry",
                "voucher_no": "TEST-LRO-SE-1",
                "company": self.company,
            }
        ).db_insert()

        frappe.get_doc(
            {
                "doctype": "Stock Ledger Entry",
                "item_code": batch_item,
                "warehouse": self.central_wh,
                "batch_no": batch_2_name,
                "actual_qty": 50.0,
                "posting_date": "2026-01-02",
                "posting_time": "10:00:00",
                "voucher_type": "Stock Entry",
                "voucher_no": "TEST-LRO-SE-2",
                "company": self.company,
            }
        ).db_insert()

        allocated = allocate_fifo_batch(batch_item, self.central_wh)
        self.assertEqual(allocated, batch_1_name)

    def test_override_item_source(self):
        """Source warehouse can be overridden on draft orders, re-allocating batch."""
        items = [
            {
                "item_code": "_TEST-LRO-NO-BATCH",
                "deficit_qty": 20.0,
                "suggested_source_warehouse": self.shelf_1,
            }
        ]

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=items,
            company=self.company,
        )

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertEqual(doc.items[0].suggested_source_warehouse, self.shelf_1)

        override_item_source(
            order_name=order_name,
            item_code="_TEST-LRO-NO-BATCH",
            new_source_warehouse=self.central_wh,
        )

        doc.reload()
        self.assertEqual(doc.items[0].suggested_source_warehouse, self.central_wh)

        # Non-draft order cannot be overridden
        doc.status = "Completed"
        doc.save(ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            override_item_source(
                order_name=order_name,
                item_code="_TEST-LRO-NO-BATCH",
                new_source_warehouse=self.shelf_1,
            )

    def _setup_fifo_batches(self):
        batch_item = "_TEST-LRO-BATCH"
        batches_data = [
            ("BATCH-FIFO-001", "2026-06-01", self.shelf_1, 15.0),
            ("BATCH-FIFO-002", "2026-07-01", self.shelf_2, 15.0),
            ("BATCH-FIFO-003", "2026-08-01", self.shelf_3, 20.0),
        ]

        frappe.db.sql(
            """
            DELETE FROM `tabStock Ledger Entry`
            WHERE item_code = %s
            """,
            (batch_item,),
        )

        for b_name, exp_date, wh, qty in batches_data:
            if not frappe.db.exists("Batch", b_name):
                b = frappe.new_doc("Batch")
                b.name = b_name
                b.batch_id = b_name
                b.item = batch_item
                b.manufacturing_date = "2026-01-01"
                b.expiry_date = exp_date
                b.flags.ignore_permissions = True
                b.insert()
            else:
                b = frappe.get_doc("Batch", b_name)
                b.manufacturing_date = "2026-01-01"
                b.expiry_date = exp_date
                b.disabled = 0
                b.save(ignore_permissions=True)

            frappe.get_doc(
                {
                    "doctype": "Stock Ledger Entry",
                    "item_code": batch_item,
                    "warehouse": wh,
                    "batch_no": b_name,
                    "actual_qty": qty,
                    "posting_date": "2026-01-01",
                    "posting_time": "10:00:00",
                    "voucher_type": "Stock Entry",
                    "voucher_no": f"TEST-SE-{b_name}",
                    "company": self.company,
                }
            ).db_insert()

    def test_allocate_fifo_batches_multi_batch_full_batch_no_splitting(self):
        """FIFO multi-batch allocation returns full batches without splitting until qty met."""
        self._setup_fifo_batches()

        # Required 29m: Batch 1 (15m) + Batch 2 (15m) = 30m full batches
        allocations = allocate_fifo_batches(
            item_code="_TEST-LRO-BATCH",
            parent_warehouse=self.central_wh,
            required_qty=29.0,
        )

        self.assertEqual(len(allocations), 2)
        self.assertEqual(allocations[0]["warehouse"], self.shelf_1)
        self.assertEqual(allocations[0]["batch_no"], "BATCH-FIFO-001")
        self.assertEqual(allocations[0]["allocated_qty"], 15.0)

        self.assertEqual(allocations[1]["warehouse"], self.shelf_2)
        self.assertEqual(allocations[1]["batch_no"], "BATCH-FIFO-002")
        self.assertEqual(allocations[1]["allocated_qty"], 15.0)

        total_allocated = sum(a["allocated_qty"] for a in allocations)
        self.assertEqual(total_allocated, 30.0)

    def test_allocate_fifo_batches_non_batch_leaf_warehouse(self):
        """Non-batch items allocate available stock from leaf shelves."""
        non_batch_item = "_TEST-LRO-NO-BATCH"
        frappe.db.sql(
            """
            DELETE FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND warehouse = %s
            """,
            (non_batch_item, self.shelf_1),
        )
        frappe.get_doc(
            {
                "doctype": "Stock Ledger Entry",
                "item_code": non_batch_item,
                "warehouse": self.shelf_1,
                "actual_qty": 50.0,
                "posting_date": "2026-01-01",
                "posting_time": "10:00:00",
                "voucher_type": "Stock Entry",
                "voucher_no": "TEST-SE-NON-BATCH-1",
                "company": self.company,
            }
        ).db_insert()

        allocations = allocate_fifo_batches(
            item_code=non_batch_item,
            parent_warehouse=self.central_wh,
            required_qty=20.0,
        )

        self.assertTrue(allocations)
        self.assertEqual(allocations[0]["warehouse"], self.shelf_1)
        self.assertIsNone(allocations[0]["batch_no"])
        self.assertEqual(allocations[0]["allocated_qty"], 20.0)

    def test_create_order_multi_batch_allocates_separate_rows_and_picked_qty(self):
        """Orders created with multiple batches create separate rows with exact shelves."""
        self._setup_fifo_batches()

        order_name = create_line_replenishment_order(
            target_warehouse=self.target_wh,
            items=[
                {
                    "item_code": "_TEST-LRO-BATCH",
                    "deficit_qty": 29.0,
                    "suggested_source_warehouse": self.central_wh,
                }
            ],
            company=self.company,
        )

        doc = frappe.get_doc("KTA Line Replenishment Order", order_name)
        self.assertEqual(len(doc.items), 2)

        # Row 1: Shelf 1, Batch 1, full 15.0
        self.assertEqual(doc.items[0].suggested_source_warehouse, self.shelf_1)
        self.assertEqual(doc.items[0].suggested_batch_no, "BATCH-FIFO-001")
        self.assertEqual(doc.items[0].deficit_qty, 15.0)
        self.assertEqual(doc.items[0].picked_qty, 15.0)

        # Row 2: Shelf 2, Batch 2, full 15.0
        self.assertEqual(doc.items[1].suggested_source_warehouse, self.shelf_2)
        self.assertEqual(doc.items[1].suggested_batch_no, "BATCH-FIFO-002")
        self.assertEqual(doc.items[1].deficit_qty, 15.0)
        self.assertEqual(doc.items[1].picked_qty, 15.0)

        # Total deficit and picked are 30.0
        self.assertEqual(doc.total_deficit_qty, 30.0)
        self.assertEqual(doc.total_picked_qty, 30.0)

    def test_fifo_prioritizes_manufacturing_date_over_creation_and_preserves_after_shelf_transfer(
        self,
    ):
        """Older manufacturing_date wins over newer creation, and survives shelf Material Transfer."""
        from frappe.utils import nowdate, nowtime

        uid = frappe.generate_hash("", 5).upper()
        grp_wh = self.fifo_group_wh
        shelf_a = self.fifo_shelf_a
        shelf_b = self.fifo_shelf_b
        target_line_wh = self.fifo_target_wh

        item_code = f"_TEST-LRO-MFG-FIFO-{uid}"
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_code,
                "item_group": create_test_item_group(),
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "has_batch_no": 1,
                "create_new_batch": 0,
            }
        ).insert(ignore_permissions=True)

        batch_newer_mfg = f"BNEW{uid}0001"
        batch_older_mfg = f"BOLD{uid}0001"

        # Insert newer-mfg batch first so it has an earlier creation timestamp
        b_new = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": batch_newer_mfg,
                "item": item_code,
                "manufacturing_date": "2026-02-15",
                "expiry_date": None,
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)

        b_old = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": batch_older_mfg,
                "item": item_code,
                "manufacturing_date": "2026-01-05",
                "expiry_date": None,
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)

        # Ensure creation timestamp of b_old is strictly later than b_new
        frappe.db.set_value(
            "Batch",
            b_new.name,
            "creation",
            "2026-02-15 08:00:00",
            update_modified=False,
        )
        frappe.db.set_value(
            "Batch",
            b_old.name,
            "creation",
            "2026-02-20 12:00:00",
            update_modified=False,
        )

        # Receive both batches into shelf_a via Material Receipt
        for batch_name, qty in ((b_new.name, 50.0), (b_old.name, 40.0)):
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
                            "t_warehouse": shelf_a,
                            "qty": qty,
                            "allow_zero_valuation_rate": 1,
                            "batch_no": batch_name,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            )
            se.insert(ignore_permissions=True)
            se.submit()

        single_alloc = allocate_fifo_batches(
            item_code=item_code,
            parent_warehouse=grp_wh,
            required_qty=30.0,
            target_warehouse=target_line_wh,
        )
        self.assertEqual(len(single_alloc), 1)
        self.assertEqual(single_alloc[0]["batch_no"], b_old.name)
        self.assertEqual(single_alloc[0]["warehouse"], shelf_a)

        bulk_alloc = bulk_allocate_fifo_batches(
            [
                {
                    "item_code": item_code,
                    "parent_warehouse": grp_wh,
                    "required_qty": 30.0,
                }
            ],
            target_warehouse=target_line_wh,
        )
        self.assertEqual(len(bulk_alloc[item_code]), 1)
        self.assertEqual(bulk_alloc[item_code][0]["batch_no"], b_old.name)
        self.assertEqual(bulk_alloc[item_code][0]["warehouse"], shelf_a)

        # Execute real Material Transfer moving older-mfg batch from shelf_a to shelf_b
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
                        "s_warehouse": shelf_a,
                        "t_warehouse": shelf_b,
                        "qty": 40.0,
                        "batch_no": b_old.name,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        move_se.insert(ignore_permissions=True)
        move_se.submit()

        single_after = allocate_fifo_batches(
            item_code=item_code,
            parent_warehouse=grp_wh,
            required_qty=30.0,
            target_warehouse=target_line_wh,
        )
        self.assertEqual(len(single_after), 1)
        self.assertEqual(single_after[0]["batch_no"], b_old.name)
        self.assertEqual(single_after[0]["warehouse"], shelf_b)

        bulk_after = bulk_allocate_fifo_batches(
            [
                {
                    "item_code": item_code,
                    "parent_warehouse": grp_wh,
                    "required_qty": 30.0,
                }
            ],
            target_warehouse=target_line_wh,
        )
        self.assertEqual(len(bulk_after[item_code]), 1)
        self.assertEqual(bulk_after[item_code][0]["batch_no"], b_old.name)
        self.assertEqual(bulk_after[item_code][0]["warehouse"], shelf_b)

    def test_create_order_multi_shelf_hub_payload_allocates_all_boxes(self):
        """Hub payload spanning multiple shelves allocates all FIFO boxes across shelves."""
        from frappe.utils import add_days, nowdate, nowtime

        uid = frappe.generate_hash("", 5).upper()
        item_code = f"_TEST-LRO-MULTI-SHELF-{uid}"
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_code,
                "item_group": create_test_item_group(),
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "has_batch_no": 1,
                "create_new_batch": 0,
            }
        ).insert(ignore_permissions=True)

        b1 = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": f"BMS1-{uid}",
                "item": item_code,
                "manufacturing_date": "2026-01-10",
                "expiry_date": add_days(nowdate(), 60),
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)

        b2 = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": f"BMS2-{uid}",
                "item": item_code,
                "manufacturing_date": "2026-02-10",
                "expiry_date": add_days(nowdate(), 120),
                "batch_qty": 0,
            }
        ).insert(ignore_permissions=True)

        for batch_name, shelf_wh, qty in (
            (b1.name, self.fifo_shelf_a, 50.0),
            (b2.name, self.fifo_shelf_b, 100.0),
        ):
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
                            "t_warehouse": shelf_wh,
                            "qty": qty,
                            "allow_zero_valuation_rate": 1,
                            "batch_no": batch_name,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            )
            se.insert(ignore_permissions=True)
            se.submit()

        allocated_payload = [
            {
                "warehouse": self.fifo_shelf_a,
                "batch_no": b1.name,
                "allocated_qty": 50.0,
            },
            {
                "warehouse": self.fifo_shelf_b,
                "batch_no": b2.name,
                "allocated_qty": 100.0,
            },
        ]

        # Test Case A: explicit source_parent_warehouse with leaf suggested_source_warehouse
        order_a_name = create_line_replenishment_order(
            target_warehouse=self.fifo_target_wh,
            items=[
                {
                    "item_code": item_code,
                    "deficit_qty": 120.0,
                    "source_parent_warehouse": self.fifo_group_wh,
                    "suggested_source_warehouse": self.fifo_shelf_a,
                    "allocated_batches": allocated_payload,
                }
            ],
            company=self.company,
        )
        doc_a = frappe.get_doc("KTA Line Replenishment Order", order_a_name)
        self.assertEqual(len(doc_a.items), 2)
        self.assertEqual(doc_a.items[0].suggested_source_warehouse, self.fifo_shelf_a)
        self.assertEqual(doc_a.items[0].suggested_batch_no, b1.name)
        self.assertEqual(doc_a.items[0].deficit_qty, 50.0)
        self.assertEqual(doc_a.items[1].suggested_source_warehouse, self.fifo_shelf_b)
        self.assertEqual(doc_a.items[1].suggested_batch_no, b2.name)
        self.assertEqual(doc_a.items[1].deficit_qty, 100.0)
        self.assertEqual(doc_a.total_deficit_qty, 150.0)

        # Test Case B: omitted source_parent_warehouse falls back via allocated_batches LCA
        order_b_name = create_line_replenishment_order(
            target_warehouse=self.fifo_target_wh,
            items=[
                {
                    "item_code": item_code,
                    "deficit_qty": 120.0,
                    "suggested_source_warehouse": self.fifo_shelf_a,
                    "allocated_batches": allocated_payload,
                }
            ],
            company=self.company,
        )
        doc_b = frappe.get_doc("KTA Line Replenishment Order", order_b_name)
        self.assertEqual(len(doc_b.items), 2)
        self.assertEqual(doc_b.items[0].suggested_source_warehouse, self.fifo_shelf_a)
        self.assertEqual(doc_b.items[0].suggested_batch_no, b1.name)
        self.assertEqual(doc_b.items[0].deficit_qty, 50.0)
        self.assertEqual(doc_b.items[1].suggested_source_warehouse, self.fifo_shelf_b)
        self.assertEqual(doc_b.items[1].suggested_batch_no, b2.name)
        self.assertEqual(doc_b.items[1].deficit_qty, 100.0)
        self.assertEqual(doc_b.total_deficit_qty, 150.0)
