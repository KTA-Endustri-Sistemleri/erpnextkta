# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from erpnextkta.kta_shopfloor.api import get_line_deficits
from erpnextkta.kta_shopfloor.services.reservation_deficit_service import (
    get_line_reservation_deficits,
)
from erpnextkta.tests.test_utils import create_test_item_group


class TestReservationDeficitService(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = "_Test Company"
        cls.abbr = frappe.db.get_value("Company", cls.company, "abbr") or "_TC"

        cls.parent_wh = f"_Test Line Group - {cls.abbr}"
        cls.target_wh = f"_Test Line 1 - {cls.abbr}"
        cls.sibling_wh = f"_Test Line 2 - {cls.abbr}"
        cls.central_wh = "110 HAMMADDE - KTA"

        cls._ensure_warehouses()
        cls._ensure_items()

    @classmethod
    def _ensure_warehouses(cls):
        suffix = f" - {cls.abbr}"
        if not frappe.db.exists("Warehouse", cls.parent_wh):
            p_wh = frappe.new_doc("Warehouse")
            p_wh.warehouse_name = cls.parent_wh.removesuffix(suffix)
            p_wh.company = cls.company
            p_wh.is_group = 1
            p_wh.flags.ignore_permissions = True
            p_wh.insert()

        for wh_name in [cls.target_wh, cls.sibling_wh]:
            if not frappe.db.exists("Warehouse", wh_name):
                wh = frappe.new_doc("Warehouse")
                wh.warehouse_name = wh_name.removesuffix(suffix)
                wh.company = cls.company
                wh.parent_warehouse = cls.parent_wh
                wh.is_group = 0
                wh.flags.ignore_permissions = True
                wh.insert()

        if frappe.db.exists("Warehouse", "110 HAMMADDE - KTA"):
            cls.central_wh = "110 HAMMADDE - KTA"
        else:
            company_central = f"110 HAMMADDE{suffix}"
            if not frappe.db.exists("Warehouse", company_central):
                c_wh = frappe.new_doc("Warehouse")
                c_wh.warehouse_name = "110 HAMMADDE"
                c_wh.company = cls.company
                c_wh.is_group = 0
                c_wh.flags.ignore_permissions = True
                c_wh.insert()
                cls.central_wh = c_wh.name
            else:
                cls.central_wh = company_central

    @classmethod
    def _ensure_items(cls):
        item_group = create_test_item_group()
        for code in ["_TEST-DEF-ITEM-A", "_TEST-DEF-ITEM-B", "_TEST-DEF-ITEM-C"]:
            if not frappe.db.exists("Item", code):
                item = frappe.new_doc("Item")
                item.item_code = code
                item.item_name = f"Test Item {code}"
                item.item_group = item_group
                item.stock_uom = "Nos"
                item.is_stock_item = 1
                item.flags.ignore_permissions = True
                item.insert()

    def _set_bin_quantities(
        self, item_code: str, warehouse: str, actual_qty: float, reserved_qty: float
    ):
        from erpnext.stock.utils import get_bin

        bin_doc = get_bin(item_code, warehouse)
        bin_doc.actual_qty = actual_qty
        bin_doc.reserved_qty_for_production = reserved_qty
        bin_doc.db_update()

    def tearDown(self):
        super().tearDown()
        for code in ["_TEST-DEF-ITEM-A", "_TEST-DEF-ITEM-B", "_TEST-DEF-ITEM-C"]:
            self._set_bin_quantities(code, self.target_wh, 0.0, 0.0)
            self._set_bin_quantities(code, self.sibling_wh, 0.0, 0.0)
        orders = frappe.get_all(
            "KTA Line Replenishment Order",
            filters={"target_warehouse": self.target_wh},
            pluck="name",
        )
        if orders:
            frappe.db.delete(
                "KTA Line Replenishment Item",
                {"parent": ["in", orders]},
            )
            frappe.db.delete("KTA Line Replenishment Order", {"name": ["in", orders]})

    def test_target_warehouse_mandatory_validation(self):
        """Empty or whitespace target warehouse must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            get_line_reservation_deficits("")

        with self.assertRaises(frappe.ValidationError):
            get_line_reservation_deficits(None)

        with self.assertRaises(frappe.ValidationError):
            get_line_reservation_deficits("   ")

    def test_group_warehouse_validation(self):
        """Group warehouse cannot be selected as target WIP warehouse."""
        with self.assertRaises(frappe.ValidationError):
            get_line_reservation_deficits(self.parent_wh)

    def test_zero_deficit_excluded(self):
        """Items where reserved <= actual must be excluded from deficit list."""
        item_code = "_TEST-DEF-ITEM-C"
        # actual 20, reserved 20 (deficit 0)
        self._set_bin_quantities(item_code, self.target_wh, 20.0, 20.0)

        res = get_line_reservation_deficits(self.target_wh)
        item_codes = [d["item_code"] for d in res]
        self.assertNotIn(item_code, item_codes)

        # actual 30, reserved 20 (excess 10)
        self._set_bin_quantities(item_code, self.target_wh, 30.0, 20.0)
        res = get_line_reservation_deficits(self.target_wh)
        item_codes = [d["item_code"] for d in res]
        self.assertNotIn(item_code, item_codes)

    def test_sibling_stock_ignored_central_warehouse_only(self):
        """Even when sibling line has free stock, deficits source strictly from central_wh."""
        item_a = "_TEST-DEF-ITEM-A"
        item_b = "_TEST-DEF-ITEM-B"

        # Item A: Deficit on target (actual 5, reserved 20 -> deficit 15)
        # Sibling has free stock (actual 50, reserved 10 -> free 40), must be ignored
        self._set_bin_quantities(item_a, self.target_wh, 5.0, 20.0)
        self._set_bin_quantities(item_a, self.sibling_wh, 50.0, 10.0)

        # Item B: Deficit on target (actual 2, reserved 10 -> deficit 8)
        self._set_bin_quantities(item_b, self.target_wh, 2.0, 10.0)
        self._set_bin_quantities(item_b, self.sibling_wh, 0.0, 0.0)

        with patch(
            "erpnextkta.kta_stock.line_replenishment_service.allocate_fifo_batches",
            return_value=[],
        ) as mock_alloc:
            results = get_line_reservation_deficits(self.target_wh)

        res_map = {d["item_code"]: d for d in results}

        self.assertIn(item_a, res_map)
        row_a = res_map[item_a]
        self.assertEqual(row_a["deficit_qty"], 15.0)
        self.assertEqual(row_a["suggested_source_warehouse"], self.central_wh)
        self.assertNotIn("sourcing_type", row_a)
        self.assertNotIn("free_stock_qty", row_a)
        self.assertFalse(row_a["has_stock"])
        self.assertEqual(row_a["available_stock"], 0.0)
        self.assertFalse(row_a["selectable"])
        self.assertFalse(row_a["covered_by_draft"])
        self.assertEqual(row_a["draft_covered_qty"], 0.0)

        self.assertIn(item_b, res_map)
        row_b = res_map[item_b]
        self.assertEqual(row_b["deficit_qty"], 8.0)
        self.assertEqual(row_b["suggested_source_warehouse"], self.central_wh)
        self.assertNotIn("sourcing_type", row_b)
        self.assertNotIn("free_stock_qty", row_b)
        self.assertFalse(row_b["has_stock"])
        self.assertEqual(row_b["available_stock"], 0.0)
        self.assertFalse(row_b["selectable"])

        # Every allocation call targeted central_wh exclusively
        for call in mock_alloc.call_args_list:
            self.assertEqual(call.kwargs.get("parent_warehouse"), self.central_wh)

    def test_legacy_sourcing_strategy_kwarg_ignored(self):
        """Legacy sourcing_strategy kwarg is silently accepted and always routes to central_wh."""
        item_a = "_TEST-DEF-ITEM-A"
        self._set_bin_quantities(item_a, self.target_wh, 5.0, 20.0)
        self._set_bin_quantities(item_a, self.sibling_wh, 50.0, 10.0)

        mock_batches = [
            {
                "warehouse": "W1A-01-01 - KTA",
                "batch_no": "BATCH-CENTRAL-001",
                "allocated_qty": 15.0,
            }
        ]
        with patch(
            "erpnextkta.kta_stock.line_replenishment_service.allocate_fifo_batches",
            return_value=mock_batches,
        ) as mock_alloc:
            results = get_line_reservation_deficits(
                self.target_wh, sourcing_strategy="Smart Sourcing (WIP First)"
            )

        res_map = {d["item_code"]: d for d in results}
        self.assertIn(item_a, res_map)
        row_a = res_map[item_a]
        self.assertEqual(row_a["deficit_qty"], 15.0)
        self.assertEqual(row_a["suggested_source_warehouse"], "W1A-01-01 - KTA")
        self.assertNotIn("sourcing_type", row_a)
        self.assertNotIn("free_stock_qty", row_a)
        self.assertTrue(row_a["has_stock"])
        self.assertTrue(row_a["selectable"])
        mock_alloc.assert_called_once_with(
            item_code=item_a,
            parent_warehouse=self.central_wh,
            required_qty=15.0,
            target_warehouse=self.target_wh,
        )

    def test_api_endpoint_get_line_deficits(self):
        """API endpoint wraps get_line_reservation_deficits and ignores legacy strategy."""
        frappe.set_user("Administrator")
        item_a = "_TEST-DEF-ITEM-A"
        self._set_bin_quantities(item_a, self.target_wh, 5.0, 20.0)
        self._set_bin_quantities(item_a, self.sibling_wh, 50.0, 10.0)

        res = get_line_deficits(
            self.target_wh, sourcing_strategy="Smart Sourcing (WIP First)"
        )
        self.assertIsInstance(res, list)
        self.assertTrue(len(res) > 0)
        self.assertIn("item_code", res[0])
        self.assertIn("deficit_qty", res[0])
        self.assertIn("suggested_source_warehouse", res[0])
        self.assertNotIn("sourcing_type", res[0])
        self.assertNotIn("free_stock_qty", res[0])

    def test_central_warehouse_batch_shelf_allocation(self):
        """When central warehouse has stock/batches, suggested_source_warehouse is leaf shelf."""
        item_b = "_TEST-DEF-ITEM-B"
        self._set_bin_quantities(item_b, self.target_wh, 2.0, 10.0)
        self._set_bin_quantities(item_b, self.sibling_wh, 0.0, 0.0)

        mock_batches = [
            {
                "warehouse": "W1A-01-01 - KTA",
                "batch_no": "BATCH-2026-001",
                "allocated_qty": 5.0,
            },
            {
                "warehouse": "W1A-01-02 - KTA",
                "batch_no": "BATCH-2026-002",
                "allocated_qty": 3.0,
            },
        ]
        with patch(
            "erpnextkta.kta_stock.line_replenishment_service.allocate_fifo_batches",
            return_value=mock_batches,
        ):
            results = get_line_reservation_deficits(self.target_wh)
            res_map = {d["item_code"]: d for d in results}
            self.assertIn(item_b, res_map)
            row = res_map[item_b]
            self.assertEqual(row["suggested_source_warehouse"], "W1A-01-01 - KTA")
            self.assertEqual(row["suggested_batch_no"], "BATCH-2026-001")
            self.assertEqual(row["allocated_batches"], mock_batches)
            self.assertTrue(row["has_stock"])
            self.assertEqual(row["available_stock"], 8.0)
            self.assertTrue(row["selectable"])

    def test_out_of_stock_has_stock_false(self):
        """When central warehouse has no stock, has_stock=False, selectable=False, available_stock=0.0."""
        item_b = "_TEST-DEF-ITEM-B"
        self._set_bin_quantities(item_b, self.target_wh, 2.0, 10.0)
        self._set_bin_quantities(item_b, self.sibling_wh, 100.0, 0.0)

        with patch(
            "erpnextkta.kta_stock.line_replenishment_service.allocate_fifo_batches",
            return_value=[],
        ):
            results = get_line_reservation_deficits(self.target_wh)
            res_map = {d["item_code"]: d for d in results}
            self.assertIn(item_b, res_map)
            row = res_map[item_b]
            self.assertFalse(row["has_stock"])
            self.assertFalse(row["selectable"])
            self.assertEqual(row["available_stock"], 0.0)
            self.assertEqual(row["suggested_source_warehouse"], self.central_wh)
            self.assertIsNone(row["suggested_batch_no"])

    def test_draft_order_fully_covers_deficit_dedup(self):
        """When an in-flight draft replenishment order covers the deficit, deficit becomes 0 and unselectable."""
        item_code = "_TEST-DEF-ITEM-A"
        self._set_bin_quantities(item_code, self.target_wh, 5.0, 20.0)

        draft_order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": self.target_wh,
                "company": self.company,
                "status": "Draft",
                "items": [
                    {
                        "item_code": item_code,
                        "item_name": "Test Item _TEST-DEF-ITEM-A",
                        "uom": "Nos",
                        "reserved_qty": 20.0,
                        "line_actual_qty": 5.0,
                        "deficit_qty": 15.0,
                    }
                ],
            }
        )
        draft_order.flags.ignore_permissions = True
        draft_order.insert()

        try:
            results = get_line_reservation_deficits(self.target_wh)
            res_map = {d["item_code"]: d for d in results}

            self.assertIn(item_code, res_map)
            row = res_map[item_code]
            self.assertTrue(row["covered_by_draft"])
            self.assertEqual(row["draft_covered_qty"], 15.0)
            self.assertIn(draft_order.name, row["draft_orders"])
            self.assertEqual(row["deficit_qty"], 0.0)
            self.assertFalse(row["selectable"])
            self.assertFalse(row["has_stock"])
            self.assertEqual(row["available_stock"], 0.0)
        finally:
            draft_order.delete(force=True)

    def test_draft_order_partially_covers_deficit_delta(self):
        """When draft replenishment partially covers deficit, remaining net deficit is allocated from central_wh."""
        item_code = "_TEST-DEF-ITEM-A"
        self._set_bin_quantities(item_code, self.target_wh, 5.0, 20.0)
        self._set_bin_quantities(item_code, self.sibling_wh, 50.0, 10.0)

        draft_order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": self.target_wh,
                "company": self.company,
                "status": "Draft",
                "items": [
                    {
                        "item_code": item_code,
                        "item_name": "Test Item _TEST-DEF-ITEM-A",
                        "uom": "Nos",
                        "reserved_qty": 20.0,
                        "line_actual_qty": 5.0,
                        "deficit_qty": 5.0,
                    }
                ],
            }
        )
        draft_order.flags.ignore_permissions = True
        draft_order.insert()

        mock_batches = [
            {
                "warehouse": "W1A-01-01 - KTA",
                "batch_no": None,
                "allocated_qty": 10.0,
            }
        ]
        try:
            with patch(
                "erpnextkta.kta_stock.line_replenishment_service.allocate_fifo_batches",
                return_value=mock_batches,
            ) as mock_alloc:
                results = get_line_reservation_deficits(self.target_wh)
            res_map = {d["item_code"]: d for d in results}

            self.assertIn(item_code, res_map)
            row = res_map[item_code]
            self.assertFalse(row["covered_by_draft"])
            self.assertEqual(row["draft_covered_qty"], 5.0)
            self.assertIn(draft_order.name, row["draft_orders"])
            self.assertEqual(row["deficit_qty"], 10.0)
            self.assertTrue(row["selectable"])
            self.assertTrue(row["has_stock"])
            self.assertEqual(row["available_stock"], 10.0)
            self.assertEqual(row["suggested_source_warehouse"], "W1A-01-01 - KTA")
            mock_alloc.assert_called_once_with(
                item_code=item_code,
                parent_warehouse=self.central_wh,
                required_qty=10.0,
                target_warehouse=self.target_wh,
            )
        finally:
            draft_order.delete(force=True)

    def test_get_central_warehouse_clean_ci_without_company_custom_field(self):
        """get_central_warehouse resolves company warehouse safely when Company lacks custom field."""
        from erpnextkta.kta_shopfloor.services.reservation_deficit_service import (
            get_central_warehouse,
        )

        # Should never raise OperationalError 1054 for default_raw_material_warehouse
        resolved = get_central_warehouse(self.company)
        self.assertTrue(resolved)
        self.assertTrue(frappe.db.exists("Warehouse", resolved))

        # Verify company-scoped resolution creates/uses 110 HAMMADDE - <abbr> cleanly
        suffix = f" - {self.abbr}"
        company_central = f"110 HAMMADDE{suffix}"
        created_temp = False
        if not frappe.db.exists("Warehouse", company_central):
            wh = frappe.new_doc("Warehouse")
            wh.warehouse_name = "110 HAMMADDE"
            wh.company = self.company
            wh.is_group = 0
            wh.flags.ignore_permissions = True
            wh.insert()
            company_central = wh.name
            created_temp = True

        try:
            self.assertEqual(get_central_warehouse(self.company), company_central)
        finally:
            if created_temp and frappe.db.exists("Warehouse", company_central):
                frappe.delete_doc("Warehouse", company_central, force=True)

    def test_multi_shelf_multi_box_deficit_contract_clean_ci(self):
        """Net deficit spanning 2 boxes across 2 leaf shelves returns parent, box_count=2, and both boxes."""
        uid = frappe.generate_hash(length=6)
        item_group = create_test_item_group()
        item_code = f"_TEST-DEF-MS-{uid}"
        central_group_name = f"_Test Central MultiShelf {uid}"
        shelf_1_name = f"_Test Central Shelf 1 {uid}"
        shelf_2_name = f"_Test Central Shelf 2 {uid}"
        batch_1 = f"_TEST-MS-BATCH-1-{uid}"
        batch_2 = f"_TEST-MS-BATCH-2-{uid}"

        central_wh_doc = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": central_group_name,
                "company": self.company,
                "is_group": 1,
            }
        )
        central_wh_doc.flags.ignore_permissions = True
        central_wh_doc.insert()
        central_group_wh = central_wh_doc.name

        shelf_1_doc = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": shelf_1_name,
                "company": self.company,
                "parent_warehouse": central_group_wh,
                "is_group": 0,
            }
        )
        shelf_1_doc.flags.ignore_permissions = True
        shelf_1_doc.insert()
        shelf_1_wh = shelf_1_doc.name

        shelf_2_doc = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": shelf_2_name,
                "company": self.company,
                "parent_warehouse": central_group_wh,
                "is_group": 0,
            }
        )
        shelf_2_doc.flags.ignore_permissions = True
        shelf_2_doc.insert()
        shelf_2_wh = shelf_2_doc.name

        item_doc = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": f"Test Multi Shelf Item {uid}",
                "item_group": item_group,
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "has_batch_no": 1,
                "create_new_batch": 1,
                "valuation_rate": 10.0,
            }
        )
        item_doc.flags.ignore_permissions = True
        item_doc.insert()

        for b_no, exp_date in [
            (batch_1, add_days(nowdate(), 30)),
            (batch_2, add_days(nowdate(), 60)),
        ]:
            b_doc = frappe.new_doc("Batch")
            b_doc.name = b_no
            b_doc.batch_id = b_no
            b_doc.item = item_code
            b_doc.expiry_date = exp_date
            b_doc.flags.ignore_permissions = True
            b_doc.insert()

        for wh, b_no, qty in [
            (shelf_1_wh, batch_1, 4.0),
            (shelf_2_wh, batch_2, 6.0),
        ]:
            se = frappe.new_doc("Stock Entry")
            se.purpose = "Material Receipt"
            se.stock_entry_type = "Material Receipt"
            se.company = self.company
            se.append(
                "items",
                {
                    "item_code": item_code,
                    "t_warehouse": wh,
                    "qty": qty,
                    "basic_rate": 10.0,
                    "uom": "Nos",
                    "conversion_factor": 1.0,
                    "batch_no": b_no,
                    "use_serial_batch_fields": 1,
                },
            )
            se.flags.ignore_permissions = True
            se.insert()
            se.submit()

        self._set_bin_quantities(item_code, self.target_wh, 0.0, 10.0)

        with patch(
            "erpnextkta.kta_shopfloor.services.reservation_deficit_service.get_central_warehouse",
            return_value=central_group_wh,
        ):
            results = get_line_reservation_deficits(self.target_wh)

        res_map = {d["item_code"]: d for d in results}
        self.assertIn(item_code, res_map)
        row = res_map[item_code]

        self.assertEqual(row["source_parent_warehouse"], central_group_wh)
        self.assertEqual(row["box_count"], 2)
        self.assertEqual(row["deficit_qty"], 10.0)
        self.assertEqual(row["available_stock"], 10.0)
        self.assertTrue(row["has_stock"])
        self.assertTrue(row["selectable"])

        allocated = row["allocated_batches"]
        self.assertEqual(len(allocated), 2)
        self.assertEqual(
            {(b["warehouse"], b["batch_no"], b["allocated_qty"]) for b in allocated},
            {
                (shelf_1_wh, batch_1, 4.0),
                (shelf_2_wh, batch_2, 6.0),
            },
        )
        self.assertEqual(row["suggested_source_warehouse"], shelf_1_wh)
        self.assertEqual(row["suggested_batch_no"], batch_1)

    def test_in_progress_order_deducts_deficit_and_skipped_items_are_ignored(self):
        """In Progress orders deduct non-skipped rows from d_net and ignore is_skipped=1 rows."""
        item_active = "_TEST-DEF-ITEM-A"
        item_skipped = "_TEST-DEF-ITEM-B"
        self._set_bin_quantities(item_active, self.target_wh, 5.0, 20.0)
        self._set_bin_quantities(item_skipped, self.target_wh, 2.0, 10.0)

        in_progress_order = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": self.target_wh,
                "company": self.company,
                "status": "In Progress",
                "items": [
                    {
                        "item_code": item_active,
                        "item_name": f"Test Item {item_active}",
                        "uom": "Nos",
                        "reserved_qty": 20.0,
                        "line_actual_qty": 5.0,
                        "deficit_qty": 10.0,
                        "is_skipped": 0,
                    },
                    {
                        "item_code": item_skipped,
                        "item_name": f"Test Item {item_skipped}",
                        "uom": "Nos",
                        "reserved_qty": 10.0,
                        "line_actual_qty": 2.0,
                        "deficit_qty": 8.0,
                        "is_skipped": 1,
                    },
                ],
            }
        )
        in_progress_order.flags.ignore_permissions = True
        in_progress_order.insert()

        try:
            with patch(
                "erpnextkta.kta_stock.line_replenishment_service.allocate_fifo_batches",
                return_value=[],
            ):
                results = get_line_reservation_deficits(self.target_wh)

            res_map = {d["item_code"]: d for d in results}

            self.assertIn(item_active, res_map)
            active_row = res_map[item_active]
            self.assertFalse(active_row["covered_by_draft"])
            self.assertEqual(active_row["draft_covered_qty"], 10.0)
            self.assertEqual(active_row["deficit_qty"], 5.0)
            self.assertIn(in_progress_order.name, active_row["draft_orders"])

            self.assertIn(item_skipped, res_map)
            skipped_row = res_map[item_skipped]
            self.assertFalse(skipped_row["covered_by_draft"])
            self.assertEqual(skipped_row["draft_covered_qty"], 0.0)
            self.assertEqual(skipped_row["deficit_qty"], 8.0)
            self.assertEqual(skipped_row["draft_orders"], [])
        finally:
            if frappe.db.exists("KTA Line Replenishment Order", in_progress_order.name):
                in_progress_order.delete(force=True)

    def test_partial_draft_excludes_already_reserved_batch_and_suggests_next_fifo_batch(
        self,
    ):
        """Partial draft covering B1 excludes B1 from FIFO allocation and suggests B2."""
        from erpnextkta.kta_stock.line_replenishment_service import get_leaf_warehouses

        uid = frappe.generate_hash(length=6)
        item_group = create_test_item_group()
        item_code = f"_TEST-DEF-PARTIAL-{uid}"
        batch_1 = f"_TEST-PARTIAL-B1-{uid}"
        batch_2 = f"_TEST-PARTIAL-B2-{uid}"

        leaf_whs = get_leaf_warehouses(self.central_wh)
        self.assertTrue(leaf_whs)
        shelf_wh = "W1A-01-01 - KTA" if "W1A-01-01 - KTA" in leaf_whs else leaf_whs[0]
        se_company = (
            frappe.db.get_value("Warehouse", shelf_wh, "company") or self.company
        )

        created_stock_entries = []
        draft_order = None

        try:
            item_doc = frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": f"Test Partial Draft Item {uid}",
                    "item_group": item_group,
                    "stock_uom": "Nos",
                    "is_stock_item": 1,
                    "has_batch_no": 1,
                    "create_new_batch": 1,
                    "valuation_rate": 10.0,
                }
            )
            item_doc.flags.ignore_permissions = True
            item_doc.insert()

            for b_no, exp_date in [
                (batch_1, add_days(nowdate(), 30)),
                (batch_2, add_days(nowdate(), 60)),
            ]:
                b_doc = frappe.new_doc("Batch")
                b_doc.name = b_no
                b_doc.batch_id = b_no
                b_doc.item = item_code
                b_doc.expiry_date = exp_date
                b_doc.flags.ignore_permissions = True
                b_doc.insert()

            for b_no, qty in [(batch_1, 250.0), (batch_2, 200.0)]:
                se = frappe.new_doc("Stock Entry")
                se.purpose = "Material Receipt"
                se.stock_entry_type = "Material Receipt"
                se.company = se_company
                se.append(
                    "items",
                    {
                        "item_code": item_code,
                        "t_warehouse": shelf_wh,
                        "qty": qty,
                        "basic_rate": 10.0,
                        "uom": "Nos",
                        "conversion_factor": 1.0,
                        "batch_no": b_no,
                        "use_serial_batch_fields": 1,
                    },
                )
                se.flags.ignore_permissions = True
                se.insert()
                se.submit()
                created_stock_entries.append(se)

            self._set_bin_quantities(item_code, self.target_wh, 0.0, 413.0)

            draft_order = frappe.get_doc(
                {
                    "doctype": "KTA Line Replenishment Order",
                    "target_warehouse": self.target_wh,
                    "company": self.company,
                    "status": "Draft",
                    "items": [
                        {
                            "item_code": item_code,
                            "item_name": f"Test Partial Draft Item {uid}",
                            "uom": "Nos",
                            "reserved_qty": 413.0,
                            "line_actual_qty": 0.0,
                            "deficit_qty": 250.0,
                            "suggested_source_warehouse": shelf_wh,
                            "suggested_batch_no": batch_1,
                        }
                    ],
                }
            )
            draft_order.flags.ignore_permissions = True
            draft_order.insert()

            results = get_line_reservation_deficits(self.target_wh)
            res_map = {d["item_code"]: d for d in results}

            self.assertIn(item_code, res_map)
            row = res_map[item_code]
            self.assertFalse(row["covered_by_draft"])
            self.assertEqual(row["deficit_qty"], 163.0)
            self.assertIn(draft_order.name, row["draft_orders"])
            self.assertEqual(row["suggested_batch_no"], batch_2)
            self.assertNotEqual(row["suggested_batch_no"], batch_1)
        finally:
            if draft_order and frappe.db.exists(
                "KTA Line Replenishment Order", draft_order.name
            ):
                draft_order.delete(force=True)
            for se in reversed(created_stock_entries):
                if frappe.db.exists("Stock Entry", se.name):
                    se_doc = frappe.get_doc("Stock Entry", se.name)
                    if se_doc.docstatus == 1:
                        se_doc.cancel()
                    se_doc.delete(force=True)
            frappe.db.delete("Stock Ledger Entry", {"item_code": item_code})
            frappe.db.delete(
                "Serial and Batch Entry", {"batch_no": ["in", [batch_1, batch_2]]}
            )
            frappe.db.delete("Bin", {"item_code": item_code})
            for b_no in [batch_1, batch_2]:
                if frappe.db.exists("Batch", b_no):
                    frappe.delete_doc("Batch", b_no, force=True)
            if frappe.db.exists("Item", item_code):
                frappe.delete_doc("Item", item_code, force=True)
