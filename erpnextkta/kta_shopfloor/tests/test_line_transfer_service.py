# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from erpnext.stock.doctype.batch.batch import get_batch_qty
from frappe.utils import add_days, flt, today

from erpnextkta.kta_shopfloor.api import (
    check_confirmation_materials,
    execute_shopfloor_line_transfer,
    get_shopfloor_idle_stock,
    get_shopfloor_line_deficits,
    get_shopfloor_production_warehouses,
    search_shopfloor_transfer_items,
    stage_confirmation_materials,
)
from erpnextkta.kta_shopfloor.services.line_transfer_service import (
    execute_line_transfer,
    get_line_idle_stock,
    get_line_transfer_deficits,
    get_production_warehouses,
    is_valid_production_warehouse,
    resolve_lifo_batches,
    search_line_transfer_items,
)
from erpnextkta.kta_shopfloor.services.work_order_service import (
    check_work_order_material_availability,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_company,
    create_test_item_group,
)


class TestLineTransferService(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        self.company = create_test_company()
        self.abbr = frappe.db.get_value("Company", self.company, "abbr") or "TKTA"
        self.item_group = create_test_item_group()
        self.uid = frappe.generate_hash(length=6)

        self.prod_group = self._ensure_warehouse(
            f"_Test Production Group {self.uid}", is_group=1
        )
        self.line_1 = self._ensure_warehouse(
            f"_Test WIP Line 1 {self.uid}", parent=self.prod_group
        )
        self.line_2 = self._ensure_warehouse(
            f"_Test WIP Line 2 {self.uid}", parent=self.prod_group
        )
        self.line_3 = self._ensure_warehouse(
            f"_Test WIP Line 3 {self.uid}", parent=self.prod_group
        )
        self.raw_group = self._ensure_warehouse(
            f"_Test 110 HAMMADDE {self.uid}", is_group=1
        )
        self.raw_leaf = self._ensure_warehouse(
            f"_Test Shelf R1 {self.uid}", parent=self.raw_group
        )
        self.raw_nested_group = self._ensure_warehouse(
            f"_Test W1Z {self.uid}", is_group=1, parent=self.raw_group
        )
        self.raw_nested_leaf = self._ensure_warehouse(
            f"_Test W1Z-01-01 {self.uid}", parent=self.raw_nested_group
        )
        self.disabled_line = self._ensure_warehouse(
            f"_Test WIP Disabled {self.uid}", parent=self.prod_group, disabled=1
        )
        self.fg_wh = self._ensure_warehouse(f"_Test FG Store {self.uid}")

        self.item_plain = self._ensure_item(
            f"_TEST-LT-PLAIN-{self.uid}", has_batch_no=0
        )
        self.item_plain_2 = self._ensure_item(
            f"_TEST-LT-PLAIN2-{self.uid}", has_batch_no=0
        )
        self.item_batch = self._ensure_item(
            f"_TEST-LT-BATCH-{self.uid}", has_batch_no=1
        )

    def _ensure_warehouse(
        self,
        wh_name: str,
        is_group: int = 0,
        parent: str | None = None,
        disabled: int = 0,
    ) -> str:
        full_name = f"{wh_name} - {self.abbr}"
        if not frappe.db.exists("Warehouse", full_name):
            doc = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": wh_name,
                    "company": self.company,
                    "is_group": is_group,
                    "parent_warehouse": parent,
                    "disabled": disabled,
                }
            )
            doc.flags.ignore_permissions = True
            doc.insert()
            return doc.name
        return full_name

    def _ensure_item(self, item_code: str, has_batch_no: int = 0) -> str:
        if not frappe.db.exists("Item", item_code):
            doc = frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": f"Test {item_code}",
                    "item_group": self.item_group,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": has_batch_no,
                    "create_new_batch": 1 if has_batch_no else 0,
                    "valuation_rate": 10.0,
                }
            )
            doc.flags.ignore_permissions = True
            doc.insert()
        return item_code

    def _ensure_batch(
        self,
        batch_no: str,
        item_code: str,
        expiry_date: str | None = None,
        disabled: int = 0,
    ) -> str:
        if not frappe.db.exists("Batch", batch_no):
            b = frappe.new_doc("Batch")
            b.name = batch_no
            b.batch_id = batch_no
            b.item = item_code
            b.expiry_date = expiry_date
            b.disabled = disabled
            b.flags.ignore_permissions = True
            b.insert()
        return batch_no

    def _receive_stock(
        self,
        item_code: str,
        warehouse: str,
        qty: float,
        batch_no: str | None = None,
        posting_date: str | None = None,
        posting_time: str | None = None,
    ) -> str:
        row = {
            "item_code": item_code,
            "t_warehouse": warehouse,
            "qty": qty,
            "basic_rate": 10.0,
            "uom": "Nos",
            "conversion_factor": 1.0,
        }
        if batch_no:
            row["batch_no"] = batch_no
            row["use_serial_batch_fields"] = 1

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = "Material Receipt"
        se.company = self.company
        if posting_date:
            se.set_posting_time = 1
            se.posting_date = posting_date
            se.posting_time = posting_time or "10:00:00"
        se.append("items", row)
        se.flags.ignore_permissions = True
        se.insert()
        se.submit()
        return se.name

    def _set_bin(
        self,
        item_code: str,
        warehouse: str,
        actual_qty: float,
        reserved_qty: float = 0.0,
    ):
        from erpnext.stock.utils import get_bin

        bin_doc = get_bin(item_code, warehouse)
        bin_doc.actual_qty = actual_qty
        bin_doc.reserved_qty_for_production = reserved_qty
        bin_doc.db_update()

    def _set_reserved_qty(self, item_code: str, warehouse: str, reserved_qty: float):
        bin_name = frappe.db.get_value(
            "Bin", {"item_code": item_code, "warehouse": warehouse}, "name"
        )
        if bin_name:
            frappe.db.set_value(
                "Bin", bin_name, "reserved_qty_for_production", flt(reserved_qty)
            )
        else:
            self._set_bin(item_code, warehouse, 0.0, reserved_qty)

    def _extract_se_batches(self, se_name: str) -> list[tuple[str | None, float]]:
        se = frappe.get_doc("Stock Entry", se_name)
        extracted: list[tuple[str | None, float]] = []
        for row in se.items:
            if row.batch_no:
                extracted.append((row.batch_no, flt(row.qty)))
            elif row.serial_and_batch_bundle:
                sbe_rows = frappe.get_all(
                    "Serial and Batch Entry",
                    filters={"parent": row.serial_and_batch_bundle},
                    fields=["batch_no", "qty"],
                    order_by="idx asc",
                )
                for sbe in sbe_rows:
                    extracted.append((sbe.batch_no, abs(flt(sbe.qty))))
            else:
                extracted.append((None, flt(row.qty)))
        return extracted

    def test_warehouse_validation_blocks_raw_material_and_group_warehouses(self):
        """110 HAMMADDE, nested shelves under it, raw/stores/disabled, and group warehouses are rejected."""
        self.assertFalse(is_valid_production_warehouse(None))
        self.assertFalse(is_valid_production_warehouse(""))
        self.assertFalse(is_valid_production_warehouse("NON-EXISTENT-WH"))
        self.assertFalse(is_valid_production_warehouse(self.prod_group))
        self.assertFalse(is_valid_production_warehouse(self.disabled_line))
        self.assertFalse(is_valid_production_warehouse(self.raw_group))
        self.assertFalse(is_valid_production_warehouse(self.raw_leaf))
        self.assertFalse(is_valid_production_warehouse(self.raw_nested_leaf))
        self.assertFalse(
            is_valid_production_warehouse(self.raw_nested_leaf, self.raw_leaf)
        )
        self.assertTrue(is_valid_production_warehouse(self.line_1))
        self.assertTrue(is_valid_production_warehouse(self.line_2, self.line_1))

        if frappe.db.exists("Warehouse", "1501 KESMELER - KTA"):
            self.assertTrue(is_valid_production_warehouse("1501 KESMELER - KTA"))
        if frappe.db.exists("Warehouse", "110 HAMMADDE - KTA"):
            self.assertFalse(is_valid_production_warehouse("110 HAMMADDE - KTA"))
        if frappe.db.exists("Warehouse", "150 ÜRETİM - KTA"):
            self.assertFalse(is_valid_production_warehouse("150 ÜRETİM - KTA"))

        prod_list = get_production_warehouses(company=self.company)
        wh_names = [row["warehouse"] for row in prod_list]
        self.assertIn(self.line_1, wh_names)
        self.assertIn(self.line_2, wh_names)
        self.assertNotIn(self.raw_group, wh_names)
        self.assertNotIn(self.raw_leaf, wh_names)
        self.assertNotIn(self.raw_nested_leaf, wh_names)
        self.assertNotIn(self.disabled_line, wh_names)
        self.assertNotIn(self.prod_group, wh_names)

        # Raw material warehouse rejected as source AND as target in execute_line_transfer
        self._receive_stock(self.item_plain, self.raw_leaf, 50.0)
        self._receive_stock(self.item_plain, self.line_1, 50.0)

        with self.assertRaises(frappe.ValidationError):
            execute_line_transfer(
                [
                    {
                        "item_code": self.item_plain,
                        "qty": 10.0,
                        "source_warehouse": self.raw_leaf,
                        "target_warehouse": self.line_1,
                    }
                ]
            )

        with self.assertRaises(frappe.ValidationError):
            execute_line_transfer(
                [
                    {
                        "item_code": self.item_plain,
                        "qty": 10.0,
                        "source_warehouse": self.line_1,
                        "target_warehouse": self.raw_leaf,
                    }
                ]
            )

        with self.assertRaises(frappe.ValidationError):
            execute_line_transfer(
                [
                    {
                        "item_code": self.item_plain,
                        "qty": 10.0,
                        "source_warehouse": self.prod_group,
                        "target_warehouse": self.line_1,
                    }
                ]
            )

    def test_get_line_transfer_deficits_filtering_and_priority(self):
        """Excludes items without sibling stock, prioritizes free stock, flags reserved-only sources."""
        # Item 1: deficit 20 on line_1.
        # line_2 has actual=100, reserved=95 (free=5)
        # line_3 has actual=30, reserved=5 (free=25) -> line_3 must win!
        self._set_bin(self.item_plain, self.line_1, 0.0, 20.0)
        self._set_bin(self.item_plain, self.line_2, 100.0, 95.0)
        self._set_bin(self.item_plain, self.line_3, 30.0, 5.0)

        # Item 2: deficit 15 on line_1.
        # line_2 has actual=40, reserved=40 (free=0) -> reserved-only source!
        self._set_bin(self.item_plain_2, self.line_1, 5.0, 20.0)
        self._set_bin(self.item_plain_2, self.line_2, 40.0, 40.0)

        # Item 3: deficit 10 on line_1, NO sibling stock (only raw_leaf has stock) -> must be excluded!
        item_no_sibling = self._ensure_item(
            f"_TEST-LT-NOSIB-{self.uid}", has_batch_no=0
        )
        self._set_bin(item_no_sibling, self.line_1, 0.0, 10.0)
        self._set_bin(item_no_sibling, self.raw_leaf, 100.0, 0.0)

        deficits = get_line_transfer_deficits(self.line_1)
        by_item = {row["item_code"]: row for row in deficits}

        self.assertIn(self.item_plain, by_item)
        self.assertIn(self.item_plain_2, by_item)
        self.assertNotIn(item_no_sibling, by_item)

        row1 = by_item[self.item_plain]
        self.assertEqual(row1["deficit_qty"], 20.0)
        self.assertEqual(row1["suggested_source_warehouse"], self.line_3)
        self.assertEqual(row1["suggested_qty"], 20.0)
        self.assertFalse(row1["uses_reserved_stock"])
        self.assertTrue(row1["default_selected"])
        self.assertEqual(len(row1["available_sources"]), 2)
        self.assertEqual(row1["available_sources"][0]["warehouse"], self.line_3)
        self.assertEqual(row1["available_sources"][0]["free_qty"], 25.0)
        self.assertEqual(row1["available_sources"][1]["warehouse"], self.line_2)
        self.assertEqual(row1["available_sources"][1]["free_qty"], 5.0)

        row2 = by_item[self.item_plain_2]
        self.assertEqual(row2["deficit_qty"], 15.0)
        self.assertEqual(row2["suggested_source_warehouse"], self.line_2)
        self.assertEqual(row2["suggested_qty"], 15.0)
        self.assertTrue(row2["uses_reserved_stock"])
        self.assertFalse(row2["default_selected"])

        with self.assertRaises(frappe.ValidationError):
            get_line_transfer_deficits(self.raw_leaf)

    def test_get_line_idle_stock_lists_only_free_and_suggests_deficit_line(self):
        """Lists only items with free_qty > 0 and suggests sibling line with highest deficit."""
        # item_plain: line_2 has actual=50, reserved=10 -> free=40
        # line_1 has deficit=15, line_3 has deficit=25 -> line_3 must be suggested!
        self._set_bin(self.item_plain, self.line_2, 50.0, 10.0)
        self._set_bin(self.item_plain, self.line_1, 5.0, 20.0)
        self._set_bin(self.item_plain, self.line_3, 0.0, 25.0)

        # item_plain_2: line_2 has actual=30, reserved=35 -> free=0 -> must NOT appear!
        self._set_bin(self.item_plain_2, self.line_2, 30.0, 35.0)

        idle = get_line_idle_stock(self.line_2)
        by_item = {row["item_code"]: row for row in idle}

        self.assertIn(self.item_plain, by_item)
        self.assertNotIn(self.item_plain_2, by_item)

        row = by_item[self.item_plain]
        self.assertEqual(row["source_warehouse"], self.line_2)
        self.assertEqual(row["actual_qty"], 50.0)
        self.assertEqual(row["reserved_qty"], 10.0)
        self.assertEqual(row["free_qty"], 40.0)
        self.assertEqual(row["suggested_target_warehouse"], self.line_3)
        self.assertEqual(row["target_deficit_qty"], 25.0)
        self.assertEqual(row["suggested_qty"], 25.0)

        with self.assertRaises(frappe.ValidationError):
            get_line_idle_stock(self.raw_leaf)

    def test_search_line_transfer_items_and_central_guard(self):
        """Searches stocked items in valid production warehouse and blocks central/raw stores."""
        self._set_bin(self.item_plain, self.line_2, 60.0, 20.0)
        self._set_bin(self.item_plain_2, self.line_2, 15.0, 15.0)

        all_items = search_line_transfer_items(self.line_2)
        codes = [r["item_code"] for r in all_items]
        self.assertIn(self.item_plain, codes)
        self.assertIn(self.item_plain_2, codes)

        filtered = search_line_transfer_items(self.line_2, search="PLAIN2")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["item_code"], self.item_plain_2)
        self.assertEqual(filtered[0]["actual_qty"], 15.0)
        self.assertEqual(filtered[0]["reserved_qty"], 15.0)
        self.assertEqual(filtered[0]["free_qty"], 0.0)

        with self.assertRaises(frappe.ValidationError):
            search_line_transfer_items(self.raw_leaf)

    def test_lifo_batch_allocation_and_split_without_spool_rounding(self):
        """LIFO picks newest inward batch first, keeps older batch intact, and splits across batches."""
        batch_old = self._ensure_batch(f"BATCH-OLD-{self.uid}", self.item_batch)
        batch_new = self._ensure_batch(f"BATCH-NEW-{self.uid}", self.item_batch)
        batch_expired = self._ensure_batch(
            f"BATCH-EXP-{self.uid}",
            self.item_batch,
            expiry_date=add_days(today(), 5),
        )

        # Receive OLD first (5 days ago), then NEW (1 day ago), then expired
        self._receive_stock(
            self.item_batch,
            self.line_2,
            40.0,
            batch_no=batch_old,
            posting_date=add_days(today(), -5),
            posting_time="09:00:00",
        )
        self._receive_stock(
            self.item_batch,
            self.line_2,
            30.0,
            batch_no=batch_new,
            posting_date=add_days(today(), -1),
            posting_time="14:00:00",
        )
        self._receive_stock(
            self.item_batch,
            self.line_2,
            50.0,
            batch_no=batch_expired,
            posting_date=today(),
            posting_time="15:00:00",
        )
        frappe.db.set_value(
            "Batch", batch_expired, "expiry_date", add_days(today(), -2)
        )

        # 1. Partial transfer of 20.0 -> must resolve strictly to BATCH-NEW (exact qty 20.0, no full spool rounding)
        alloc_partial = resolve_lifo_batches(self.item_batch, self.line_2, 20.0)
        self.assertEqual(alloc_partial, [{"batch_no": batch_new, "qty": 20.0}])

        res1 = execute_line_transfer(
            [
                {
                    "item_code": self.item_batch,
                    "qty": 20.0,
                    "source_warehouse": self.line_2,
                    "target_warehouse": self.line_1,
                }
            ]
        )
        self.assertTrue(res1["success"])
        se1_batches = self._extract_se_batches(res1["stock_entry"])
        self.assertEqual(se1_batches, [(batch_new, 20.0)])

        # Verify BATCH-OLD untouched (40.0) and BATCH-NEW reduced to 10.0 on line_2
        self.assertEqual(
            flt(
                get_batch_qty(
                    batch_no=batch_old, warehouse=self.line_2, item_code=self.item_batch
                )
            ),
            40.0,
        )
        self.assertEqual(
            flt(
                get_batch_qty(
                    batch_no=batch_new, warehouse=self.line_2, item_code=self.item_batch
                )
            ),
            10.0,
        )

        # 2. Request 25.0 -> must split LIFO: 10.0 from BATCH-NEW + 15.0 from BATCH-OLD (ignoring expired!)
        alloc_split = resolve_lifo_batches(self.item_batch, self.line_2, 25.0)
        self.assertEqual(
            alloc_split,
            [
                {"batch_no": batch_new, "qty": 10.0},
                {"batch_no": batch_old, "qty": 15.0},
            ],
        )

        res2 = execute_line_transfer(
            [
                {
                    "item_code": self.item_batch,
                    "qty": 25.0,
                    "source_warehouse": self.line_2,
                    "target_warehouse": self.line_1,
                }
            ]
        )
        self.assertTrue(res2["success"])
        se2_batches = self._extract_se_batches(res2["stock_entry"])
        self.assertEqual(se2_batches, [(batch_new, 10.0), (batch_old, 15.0)])

        self.assertEqual(
            flt(
                get_batch_qty(
                    batch_no=batch_new, warehouse=self.line_2, item_code=self.item_batch
                )
            ),
            0.0,
        )
        self.assertEqual(
            flt(
                get_batch_qty(
                    batch_no=batch_old, warehouse=self.line_2, item_code=self.item_batch
                )
            ),
            25.0,
        )

        # 3. Requesting more than total valid unexpired stock (25.0 left, expired 50.0 ignored) fails
        with self.assertRaises(frappe.ValidationError):
            resolve_lifo_batches(self.item_batch, self.line_2, 30.0)

        # 4. Non-batch item and non-positive qty checks
        self.assertEqual(
            resolve_lifo_batches(self.item_plain, self.line_2, 12.5),
            [{"batch_no": None, "qty": 12.5}],
        )
        with self.assertRaises(frappe.ValidationError):
            resolve_lifo_batches(self.item_batch, self.line_2, 0)

    def test_reserved_stock_protection_and_override(self):
        """Protects reserved stock unless allow_reserved_override=1, and blocks > actual_qty."""
        # Seed actual=120, reserved=70 -> free=50 on line_2
        self._receive_stock(self.item_plain, self.line_2, 120.0)
        self._set_reserved_qty(self.item_plain, self.line_2, 70.0)

        transfer_60 = [
            {
                "item_code": self.item_plain,
                "qty": 60.0,
                "source_warehouse": self.line_2,
                "target_warehouse": self.line_1,
            }
        ]

        # 1. 60 > free(50) with allow_reserved_override=0 must throw ValidationError
        with self.assertRaises(frappe.ValidationError):
            execute_line_transfer(transfer_60, allow_reserved_override=0)

        # 2. 60 > free(50) with allow_reserved_override=1 succeeds and sets used_reserved_stock=True
        res = execute_line_transfer(transfer_60, allow_reserved_override=1)
        self.assertTrue(res["success"])
        self.assertTrue(res["used_reserved_stock"])
        se_doc = frappe.get_doc("Stock Entry", res["stock_entry"])
        self.assertEqual(se_doc.docstatus, 1)
        self.assertEqual(se_doc.purpose, "Material Transfer")
        self.assertEqual(flt(se_doc.items[0].qty), 60.0)

        # 3. Remaining actual is 60 (reserved still 70 -> free=0). Requesting 65 (> actual 60) fails even with override=1!
        with self.assertRaises(frappe.ValidationError):
            execute_line_transfer(
                [
                    {
                        "item_code": self.item_plain,
                        "qty": 65.0,
                        "source_warehouse": self.line_2,
                        "target_warehouse": self.line_1,
                    }
                ],
                allow_reserved_override=1,
            )

    def test_work_order_availability_and_confirmation_staging_integration(self):
        """Tests has_sibling_line_stock on WO availability and LIFO + override in stage_confirmation_materials."""
        fg_item = self._ensure_item(f"_TEST-LT-FG-{self.uid}", has_batch_no=0)
        wo = frappe.get_doc(
            {
                "doctype": "Work Order",
                "production_item": fg_item,
                "qty": 10.0,
                "company": self.company,
                "source_warehouse": self.line_1,
                "wip_warehouse": self.line_1,
                "fg_warehouse": self.fg_wh,
                "skip_transfer": 1,
            }
        )
        wo.flags.ignore_permissions = True
        wo.flags.ignore_mandatory = True
        wo.insert(ignore_permissions=True)
        wo.required_items = []
        wo.append(
            "required_items",
            {
                "item_code": self.item_batch,
                "required_qty": 10.0,
                "source_warehouse": self.line_1,
            },
        )
        wo.save(ignore_permissions=True)
        wo.submit()

        # Seed stock ONLY in raw_leaf initially -> has_sibling_line_stock must be False
        self._receive_stock(
            self.item_batch,
            self.raw_leaf,
            30.0,
            batch_no=self._ensure_batch(f"BATCH-RAW-{self.uid}", self.item_batch),
        )
        avail_before = check_work_order_material_availability(wo.name)
        self.assertFalse(avail_before["items"][0]["has_sibling_line_stock"])
        self.assertEqual(avail_before["items"][0]["sibling_line_warehouses"], [])

        # Seed two batches on sibling line_2, plus reserve 25 on line_2 (actual=30 -> free=5)
        batch_old = self._ensure_batch(f"BATCH-STG-OLD-{self.uid}", self.item_batch)
        batch_new = self._ensure_batch(f"BATCH-STG-NEW-{self.uid}", self.item_batch)
        self._receive_stock(
            self.item_batch,
            self.line_2,
            20.0,
            batch_no=batch_old,
            posting_date=add_days(today(), -4),
            posting_time="09:00:00",
        )
        self._receive_stock(
            self.item_batch,
            self.line_2,
            10.0,
            batch_no=batch_new,
            posting_date=add_days(today(), -1),
            posting_time="11:00:00",
        )
        self._set_reserved_qty(self.item_batch, self.line_2, 25.0)

        avail_after = check_work_order_material_availability(wo.name)
        self.assertTrue(avail_after["items"][0]["has_sibling_line_stock"])
        self.assertEqual(
            avail_after["items"][0]["sibling_line_warehouses"][0]["warehouse"],
            self.line_2,
        )

        # check_confirmation_materials reports free_qty=5.0 and actual_qty=30.0
        chk = check_confirmation_materials(wo.name, operation="", yield_qty=10.0)
        self.assertTrue(chk["has_shortage"])
        shortage = chk["shortages"][0]
        self.assertEqual(shortage["source_warehouse"], self.line_2)
        self.assertEqual(shortage["source_available_qty"], 5.0)
        self.assertEqual(shortage["source_actual_qty"], 30.0)

        # Staging 10.0 > free(5.0) without override fails; with allow_reserved_override=1 uses LIFO (BATCH-NEW 10.0)
        transfers = [
            {
                "item_code": self.item_batch,
                "qty": 10.0,
                "source_warehouse": self.line_2,
                "target_warehouse": self.line_1,
            }
        ]
        with self.assertRaises(frappe.ValidationError):
            stage_confirmation_materials(wo.name, transfers, allow_reserved_override=0)

        staged = stage_confirmation_materials(
            wo.name, transfers, allow_reserved_override=1
        )
        self.assertTrue(staged["success"])
        self.assertTrue(staged["used_reserved_stock"])
        se_doc = frappe.get_doc("Stock Entry", staged["stock_entry"])
        self.assertEqual(se_doc.docstatus, 1)
        self.assertEqual(se_doc.purpose, "Material Transfer for Manufacture")
        self.assertEqual(se_doc.work_order, wo.name)
        self.assertEqual(self._extract_se_batches(se_doc.name), [(batch_new, 10.0)])

    def test_shopfloor_line_transfer_api_endpoints_and_permissions(self):
        """API wrappers expose production warehouses, deficits, idle stock, search, and transfer with permission checks."""
        self._receive_stock(self.item_plain, self.line_2, 40.0)
        self._set_bin(self.item_plain, self.line_1, 0.0, 15.0)

        warehouses = get_shopfloor_production_warehouses(company=self.company)
        self.assertTrue(any(w["warehouse"] == self.line_1 for w in warehouses))

        deficits = get_shopfloor_line_deficits(self.line_1)
        self.assertTrue(any(d["item_code"] == self.item_plain for d in deficits))

        idle = get_shopfloor_idle_stock(self.line_2)
        self.assertTrue(any(d["item_code"] == self.item_plain for d in idle))

        searched = search_shopfloor_transfer_items(self.line_2, search=self.item_plain)
        self.assertEqual(len(searched), 1)
        self.assertEqual(searched[0]["item_code"], self.item_plain)

        res = execute_shopfloor_line_transfer(
            transfers=[
                {
                    "item_code": self.item_plain,
                    "qty": 15.0,
                    "source_warehouse": self.line_2,
                    "target_warehouse": self.line_1,
                }
            ]
        )
        self.assertTrue(res["success"])
        self.assertEqual(
            frappe.db.get_value("Stock Entry", res["stock_entry"], "docstatus"), 1
        )

        # Permission enforcement on reads and transfer POST
        with (
            patch(
                "erpnextkta.kta_shopfloor.api.frappe.has_permission",
                side_effect=frappe.PermissionError,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            get_shopfloor_production_warehouses(company=self.company)

        with (
            patch(
                "erpnextkta.kta_shopfloor.api.frappe.has_permission",
                return_value=False,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            execute_shopfloor_line_transfer(
                transfers=[
                    {
                        "item_code": self.item_plain,
                        "qty": 5.0,
                        "source_warehouse": self.line_2,
                        "target_warehouse": self.line_1,
                    }
                ]
            )
