# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.utils import add_days, cint, flt, getdate

from erpnextkta.kta_shopfloor.services.backflush_service import BackflushService
from erpnextkta.kta_shopfloor.services.work_order_service import (
    check_work_order_material_availability,
    create_draft_work_order,
    get_item_alternatives,
    get_work_order_item_alternatives,
    get_work_order_print_options,
    release_work_order_service,
    resolve_manufacturing_lead_days,
    restore_work_order_item_original,
    set_work_order_item_alternative,
    update_work_order_qty,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_company,
    create_test_item_group,
    create_test_warehouse,
)


class TestWorkOrderService(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        self._setup_bom_and_warehouses()

    def _setup_bom_and_warehouses(self):
        self.company = create_test_company()
        self.item_group = create_test_item_group()
        self.wip_warehouse = create_test_warehouse(self.company)
        self.src_warehouse = self._ensure_warehouse("_Test Source WH")
        self.fg_warehouse = self._ensure_warehouse("_Test FG WH")
        self.central_warehouse = self._ensure_warehouse("_Test Central WH")

        self.fg_item = self._ensure_item("_Test FG Item WO Svc")
        self.rm_item_1 = self._ensure_item("_Test RM Item 1 WO Svc")
        self.rm_item_2 = self._ensure_item("_Test RM Item 2 WO Svc")

        existing_bom = frappe.db.get_value(
            "BOM",
            {"item": self.fg_item, "is_active": 1, "is_default": 1, "docstatus": 1},
            "name",
        )
        if existing_bom:
            self.bom_no = existing_bom
            return

        bom = frappe.get_doc(
            {
                "doctype": "BOM",
                "item": self.fg_item,
                "company": self.company,
                "quantity": 1,
                "is_active": 1,
                "is_default": 1,
                "with_operations": 0,
                "currency": "TRY",
                "conversion_rate": 1.0,
                "items": [
                    {
                        "item_code": self.rm_item_1,
                        "qty": 2,
                        "uom": "Nos",
                        "rate": 10.0,
                        "source_warehouse": self.src_warehouse,
                    },
                    {
                        "item_code": self.rm_item_2,
                        "qty": 4,
                        "uom": "Nos",
                        "rate": 5.0,
                        "source_warehouse": self.src_warehouse,
                    },
                ],
            }
        )
        bom.flags.ignore_permissions = True
        bom.insert(ignore_permissions=True)
        bom.submit()
        self.bom_no = bom.name
        frappe.db.commit()

    def _ensure_warehouse(self, name: str) -> str:
        fullname = f"{name} - TKTA"
        if not frappe.db.exists("Warehouse", fullname):
            frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": name,
                    "company": self.company,
                }
            ).insert(ignore_permissions=True)
        return fullname

    def _ensure_item(self, item_code: str) -> str:
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": item_code,
                    "item_group": self.item_group,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "valuation_rate": 10.0,
                    "allow_alternative_item": 1,
                }
            ).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Item", item_code, "allow_alternative_item", 1)
        return item_code

    def _set_bin_qty(
        self,
        item_code: str,
        warehouse: str,
        qty: float,
        reserved_qty: float = 0.0,
    ):
        bin_name = frappe.db.get_value(
            "Bin", {"item_code": item_code, "warehouse": warehouse}, "name"
        )
        if bin_name:
            frappe.db.set_value(
                "Bin",
                bin_name,
                {
                    "actual_qty": flt(qty),
                    "reserved_qty_for_production": flt(reserved_qty),
                },
            )
        else:
            frappe.get_doc(
                {
                    "doctype": "Bin",
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "actual_qty": flt(qty),
                    "reserved_qty_for_production": flt(reserved_qty),
                }
            ).insert(ignore_permissions=True)

    def test_lead_days_fallback_to_14(self):
        """Missing item or unconfigured lead days safely falls back to 14 days."""
        lead_days = resolve_manufacturing_lead_days("NON_EXISTING_ITEM_X")
        self.assertEqual(lead_days, 14)

    def test_lead_days_hierarchy_customer_over_item_over_fallback(self):
        """Customer-specific lead days override Item lead days, which override 14-day fallback."""
        with (
            patch(
                "erpnextkta.kta_shopfloor.services.work_order_service.frappe.db.has_column",
                return_value=True,
            ),
            patch(
                "erpnextkta.kta_shopfloor.services.work_order_service.frappe.db.get_value"
            ) as mock_get_value,
        ):
            # Case 1: Customer detail returns 7 -> 7 wins
            mock_get_value.side_effect = [7]
            self.assertEqual(
                resolve_manufacturing_lead_days(self.fg_item, customer="CUST-001"), 7
            )

            # Case 2: Customer detail returns None/0, Item returns 10 -> 10 wins
            mock_get_value.side_effect = [None, 10]
            self.assertEqual(
                resolve_manufacturing_lead_days(self.fg_item, customer="CUST-001"), 10
            )

            # Case 3: No customer given, Item returns 21 -> 21 wins
            mock_get_value.side_effect = [21]
            self.assertEqual(resolve_manufacturing_lead_days(self.fg_item), 21)

            # Case 4: Both return 0/None -> 14 fallback
            mock_get_value.side_effect = [0, 0]
            self.assertEqual(
                resolve_manufacturing_lead_days(self.fg_item, customer="CUST-001"), 14
            )

    def test_create_draft_work_order_computes_end_date_and_bom(self):
        """Draft Work Order resolves default BOM and planned_end_date from lead time."""
        start_date = "2026-11-18"
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            planned_start_date=start_date,
            company=self.company,
        )

        self.assertEqual(res["status"], "Draft")
        self.assertEqual(res["docstatus"], 0)
        self.assertEqual(res["bom_no"], self.bom_no)
        self.assertEqual(res["lead_days"], 14)
        self.assertEqual(
            str(getdate(res["planned_end_date"])), add_days(start_date, 14)
        )

        wo = frappe.get_doc("Work Order", res["name"])
        self.assertEqual(wo.docstatus, 0)
        self.assertEqual(flt(wo.qty), 5.0)
        self.assertEqual(len(wo.required_items), 2)

    def test_material_availability_calculation_and_warehouse_fallback(self):
        """Material availability computes coverage %, shortage_qty, and overall readiness."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,  # RM1 requires 10, RM2 requires 20
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        # RM1: 10/10 = 100%, RM2: 5/20 = 25% -> Avg = 62.5%
        self._set_bin_qty(self.rm_item_1, self.central_warehouse, 0.0, 0.0)
        self._set_bin_qty(self.rm_item_2, self.central_warehouse, 0.0, 0.0)
        self._set_bin_qty(self.rm_item_1, self.src_warehouse, 10.0, 0.0)
        self._set_bin_qty(self.rm_item_2, self.src_warehouse, 5.0, 0.0)

        avail = check_work_order_material_availability(wo_name)
        self.assertEqual(avail["work_order"], wo_name)
        self.assertTrue(avail["has_shortage"])
        self.assertTrue(avail["has_line_shortage"])
        self.assertTrue(avail["has_critical_shortage"])
        self.assertFalse(avail["can_fulfill_via_transfer"])
        self.assertEqual(avail["overall_readiness_percent"], 62.5)
        self.assertEqual(len(avail["items"]), 2)

        by_item = {row["item_code"]: row for row in avail["items"]}
        self.assertEqual(by_item[self.rm_item_1]["required_qty"], 10.0)
        self.assertEqual(by_item[self.rm_item_1]["available_qty"], 10.0)
        self.assertEqual(by_item[self.rm_item_1]["line_available_qty"], 10.0)
        self.assertEqual(by_item[self.rm_item_1]["shortage_qty"], 0.0)
        self.assertEqual(by_item[self.rm_item_1]["coverage_percent"], 100.0)
        self.assertEqual(by_item[self.rm_item_1]["availability_status"], "available")

        self.assertEqual(by_item[self.rm_item_2]["required_qty"], 20.0)
        self.assertEqual(by_item[self.rm_item_2]["available_qty"], 5.0)
        self.assertEqual(by_item[self.rm_item_2]["line_available_qty"], 5.0)
        self.assertEqual(by_item[self.rm_item_2]["shortage_qty"], 15.0)
        self.assertEqual(by_item[self.rm_item_2]["coverage_percent"], 25.0)
        self.assertEqual(
            by_item[self.rm_item_2]["availability_status"], "critical_shortage"
        )

        # Verify warehouse fallback when row source_warehouse is empty
        frappe.db.set_value(
            "Work Order Item",
            {"parent": wo_name, "item_code": self.rm_item_2},
            "source_warehouse",
            "",
        )
        avail_fallback = check_work_order_material_availability(wo_name)
        by_item_fb = {row["item_code"]: row for row in avail_fallback["items"]}
        self.assertEqual(by_item_fb[self.rm_item_2]["warehouse"], self.src_warehouse)
        self.assertEqual(by_item_fb[self.rm_item_2]["available_qty"], 5.0)

    def test_material_availability_line_reserved_qty_deduction(self):
        """Reserved qty for production on line warehouse is deducted from actual_qty to compute line_available_qty."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,  # RM1 requires 10, RM2 requires 20
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        # Ensure no stock in central warehouse
        self._set_bin_qty(self.rm_item_1, self.central_warehouse, 0.0, 0.0)
        self._set_bin_qty(self.rm_item_2, self.central_warehouse, 0.0, 0.0)

        # RM1: actual 15, reserved 7 -> line_avail = 8. Required = 10 -> shortage = 2.
        self._set_bin_qty(self.rm_item_1, self.src_warehouse, 15.0, 7.0)
        # RM2: actual 5, reserved 10 -> line_avail = max(0, 5 - 10) = 0. Required = 20 -> shortage = 20.
        self._set_bin_qty(self.rm_item_2, self.src_warehouse, 5.0, 10.0)

        avail = check_work_order_material_availability(wo_name)
        by_item = {row["item_code"]: row for row in avail["items"]}

        # RM1 assertions
        self.assertEqual(by_item[self.rm_item_1]["line_actual_qty"], 15.0)
        self.assertEqual(by_item[self.rm_item_1]["line_reserved_qty"], 7.0)
        self.assertEqual(by_item[self.rm_item_1]["line_available_qty"], 8.0)
        self.assertEqual(by_item[self.rm_item_1]["available_qty"], 8.0)
        self.assertEqual(by_item[self.rm_item_1]["shortage_qty"], 2.0)
        self.assertEqual(by_item[self.rm_item_1]["coverage_percent"], 80.0)
        self.assertEqual(
            by_item[self.rm_item_1]["availability_status"], "critical_shortage"
        )

        # RM2 assertions (clamped to 0)
        self.assertEqual(by_item[self.rm_item_2]["line_actual_qty"], 5.0)
        self.assertEqual(by_item[self.rm_item_2]["line_reserved_qty"], 10.0)
        self.assertEqual(by_item[self.rm_item_2]["line_available_qty"], 0.0)
        self.assertEqual(by_item[self.rm_item_2]["available_qty"], 0.0)
        self.assertEqual(by_item[self.rm_item_2]["shortage_qty"], 20.0)
        self.assertEqual(by_item[self.rm_item_2]["coverage_percent"], 0.0)
        self.assertEqual(
            by_item[self.rm_item_2]["availability_status"], "critical_shortage"
        )

        self.assertTrue(avail["has_shortage"])
        self.assertTrue(avail["has_line_shortage"])
        self.assertTrue(avail["has_critical_shortage"])
        self.assertFalse(avail["can_fulfill_via_transfer"])
        self.assertEqual(avail["critical_shortage_count"], 2)
        self.assertEqual(avail["transfer_required_count"], 0)

    def test_material_availability_multi_warehouse_transfer_status(self):
        """Material availability evaluates 3-tier statuses (available, transfer_required, critical_shortage) and can_fulfill_via_transfer."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,  # RM1 requires 10, RM2 requires 20
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        # Case 1: RM1 has line shortage (4 available < 10), but Central WH has 10 available -> transfer_required.
        # RM2 has full line availability (25 available >= 20) -> available.
        # Overall: has_line_shortage=True, has_critical_shortage=False -> can_fulfill_via_transfer=True!
        self._set_bin_qty(
            self.rm_item_1, self.src_warehouse, 6.0, 2.0
        )  # line_avail = 4
        self._set_bin_qty(
            self.rm_item_1, self.central_warehouse, 12.0, 2.0
        )  # other_avail = 10 -> total 14 >= 10

        self._set_bin_qty(
            self.rm_item_2, self.src_warehouse, 30.0, 5.0
        )  # line_avail = 25 >= 20
        self._set_bin_qty(self.rm_item_2, self.central_warehouse, 0.0, 0.0)

        avail = check_work_order_material_availability(wo_name)
        by_item = {row["item_code"]: row for row in avail["items"]}

        # RM1: transfer_required
        self.assertEqual(
            by_item[self.rm_item_1]["availability_status"], "transfer_required"
        )
        self.assertEqual(by_item[self.rm_item_1]["line_available_qty"], 4.0)
        self.assertEqual(by_item[self.rm_item_1]["other_warehouses_qty"], 10.0)
        self.assertEqual(len(by_item[self.rm_item_1]["other_warehouses"]), 1)
        self.assertEqual(
            by_item[self.rm_item_1]["other_warehouses"][0]["warehouse"],
            self.central_warehouse,
        )
        self.assertEqual(
            by_item[self.rm_item_1]["other_warehouses"][0]["available_qty"], 10.0
        )

        # RM2: available
        self.assertEqual(by_item[self.rm_item_2]["availability_status"], "available")
        self.assertEqual(by_item[self.rm_item_2]["line_available_qty"], 25.0)
        self.assertEqual(by_item[self.rm_item_2]["shortage_qty"], 0.0)

        # Work Order level metrics
        self.assertTrue(avail["has_shortage"])
        self.assertTrue(avail["has_line_shortage"])
        self.assertFalse(avail["has_critical_shortage"])
        self.assertTrue(avail["can_fulfill_via_transfer"])
        self.assertEqual(avail["transfer_required_count"], 1)
        self.assertEqual(avail["critical_shortage_count"], 0)

        # Case 2: RM2 now also lacks stock across all warehouses -> critical_shortage -> can_fulfill_via_transfer becomes False
        self._set_bin_qty(
            self.rm_item_2, self.src_warehouse, 5.0, 0.0
        )  # line_avail = 5
        self._set_bin_qty(
            self.rm_item_2, self.central_warehouse, 2.0, 0.0
        )  # other_avail = 2 -> total 7 < 20

        avail2 = check_work_order_material_availability(wo_name)
        by_item2 = {row["item_code"]: row for row in avail2["items"]}

        self.assertEqual(
            by_item2[self.rm_item_2]["availability_status"], "critical_shortage"
        )
        self.assertTrue(avail2["has_line_shortage"])
        self.assertTrue(avail2["has_critical_shortage"])
        self.assertFalse(avail2["can_fulfill_via_transfer"])
        self.assertEqual(avail2["transfer_required_count"], 1)
        self.assertEqual(avail2["critical_shortage_count"], 1)

    def test_material_availability_other_warehouse_reserved_qty_and_sorting(self):
        """Other warehouses subtract reserved_qty, omit 0-available warehouses, and sort by actual_qty desc."""
        wh_secondary = self._ensure_warehouse("_Test Sec WH")
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        # RM1: Line has 0
        self._set_bin_qty(self.rm_item_1, self.src_warehouse, 0.0, 0.0)
        # Central WH: actual 100, reserved 90 -> net 10 available
        self._set_bin_qty(self.rm_item_1, self.central_warehouse, 100.0, 90.0)
        # Sec WH: actual 20, reserved 20 -> net 0 available (must not appear in other_warehouses)
        self._set_bin_qty(self.rm_item_1, wh_secondary, 20.0, 20.0)

        avail = check_work_order_material_availability(wo_name)
        by_item = {row["item_code"]: row for row in avail["items"]}

        rm1_avail = by_item[self.rm_item_1]
        self.assertEqual(rm1_avail["other_warehouses_qty"], 10.0)
        # Only central_warehouse should be present because wh_secondary has 0 net available
        self.assertEqual(len(rm1_avail["other_warehouses"]), 1)
        self.assertEqual(
            rm1_avail["other_warehouses"][0]["warehouse"], self.central_warehouse
        )
        self.assertEqual(rm1_avail["other_warehouses"][0]["actual_qty"], 100.0)
        self.assertEqual(rm1_avail["other_warehouses"][0]["available_qty"], 10.0)
        # Since line(0) + other(10) >= required(10) -> transfer_required
        self.assertEqual(rm1_avail["availability_status"], "transfer_required")

    def test_release_work_order_blocks_shortage_when_disallowed(self):
        """Releasing with shortage and allow_shortage=0 throws ValidationError."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        self._set_bin_qty(self.rm_item_1, self.src_warehouse, 0.0)
        self._set_bin_qty(self.rm_item_2, self.src_warehouse, 0.0)

        with self.assertRaises(frappe.ValidationError) as ctx:
            release_work_order_service(wo_name, allow_shortage=0)

        expected_prefix = frappe._("Eksik hammadde mevcut: {0}").format("").rstrip(": ")
        self.assertIn(expected_prefix, str(ctx.exception))
        self.assertEqual(frappe.db.get_value("Work Order", wo_name, "docstatus"), 0)

    def test_release_work_order_with_shortage_allowed_adds_comment_and_submits(self):
        """Releasing with allow_shortage=1 sets flag, adds activity comment, and submits."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        self._set_bin_qty(self.rm_item_1, self.src_warehouse, 10.0)
        self._set_bin_qty(self.rm_item_2, self.src_warehouse, 5.0)

        rel = release_work_order_service(wo_name, allow_shortage=1)
        self.assertEqual(rel["name"], wo_name)
        self.assertEqual(rel["docstatus"], 1)
        self.assertEqual(rel["status"], "Not Started")
        self.assertTrue(rel["released_with_shortage"])
        if frappe.db.has_column("Work Order", "custom_released_with_shortage"):
            self.assertEqual(
                cint(
                    frappe.db.get_value(
                        "Work Order", wo_name, "custom_released_with_shortage"
                    )
                ),
                1,
            )

        comments = frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": "Work Order",
                "reference_name": wo_name,
                "comment_type": "Comment",
            },
            pluck="content",
        )
        expected_comment_prefix = (
            frappe._("İş Emri eksik hammadde ile serbest bırakıldı: {0}")
            .format("")
            .rstrip(": ")
        )
        self.assertTrue(any(expected_comment_prefix in c for c in comments))

    def test_release_work_order_full_availability_submits_cleanly(self):
        """Releasing with 100% material availability submits without shortage flag."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        self._set_bin_qty(self.rm_item_1, self.src_warehouse, 20.0)
        self._set_bin_qty(self.rm_item_2, self.src_warehouse, 30.0)

        rel = release_work_order_service(wo_name, allow_shortage=0)
        self.assertEqual(rel["name"], wo_name)
        self.assertEqual(rel["docstatus"], 1)
        self.assertEqual(rel["status"], "Not Started")
        self.assertFalse(rel["released_with_shortage"])
        if frappe.db.has_column("Work Order", "custom_released_with_shortage"):
            self.assertEqual(
                cint(
                    frappe.db.get_value(
                        "Work Order", wo_name, "custom_released_with_shortage"
                    )
                ),
                0,
            )

    def test_reserved_qty_for_production_increases_on_release_and_decreases_on_backflush(
        self,
    ):
        """Bin.reserved_qty_for_production increases on WO submit and decreases on backflush."""
        prev_neg_stock = frappe.db.get_single_value(
            "Stock Settings", "allow_negative_stock"
        )
        frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
        try:
            initial_res_1 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_1, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )
            initial_res_2 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_2, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )

            res = create_draft_work_order(
                item_code=self.fg_item,
                qty=5,  # RM1 requires 10, RM2 requires 20
                source_warehouse=self.src_warehouse,
                wip_warehouse=self.wip_warehouse,
                fg_warehouse=self.fg_warehouse,
                company=self.company,
            )
            wo_name = res["name"]
            frappe.db.set_value("Work Order", wo_name, "skip_transfer", 1)

            self._set_bin_qty(self.rm_item_1, self.src_warehouse, 20.0)
            self._set_bin_qty(self.rm_item_2, self.src_warehouse, 40.0)

            release_work_order_service(wo_name, allow_shortage=0)

            after_submit_res_1 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_1, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )
            after_submit_res_2 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_2, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )
            self.assertEqual(after_submit_res_1, initial_res_1 + 10.0)
            self.assertEqual(after_submit_res_2, initial_res_2 + 20.0)

            # Partial backflush: 2 of 5 units -> consumes 4 of RM1, 8 of RM2
            se_partial = BackflushService.create_consumption_entry(
                wo_name, "Üretim", yield_qty=2.0, is_final=False
            )
            self.assertTrue(se_partial)

            after_partial_res_1 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_1, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )
            after_partial_res_2 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_2, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )
            self.assertEqual(after_partial_res_1, initial_res_1 + 6.0)
            self.assertEqual(after_partial_res_2, initial_res_2 + 12.0)

            # Final backflush: remaining 3 units -> consumes remaining 6 of RM1, 12 of RM2
            se_final = BackflushService.create_consumption_entry(
                wo_name, "Üretim", yield_qty=3.0, is_final=True
            )
            self.assertTrue(se_final)

            after_final_res_1 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_1, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )
            after_final_res_2 = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": self.rm_item_2, "warehouse": self.src_warehouse},
                    "reserved_qty_for_production",
                )
            )
            self.assertEqual(after_final_res_1, initial_res_1)
            self.assertEqual(after_final_res_2, initial_res_2)
        finally:
            frappe.db.set_single_value(
                "Stock Settings", "allow_negative_stock", prev_neg_stock or 0
            )

    def test_create_draft_work_order_auto_normalizes_legacy_sequence_ids(self):
        """BOM with legacy sequence_ids (10, 20) creates a Work Order with sequences (1, 2) without error."""
        ws_name = "_Test WS Step Seq"
        if not frappe.db.exists("Workstation", ws_name):
            frappe.get_doc(
                {"doctype": "Workstation", "workstation_name": ws_name}
            ).insert(ignore_permissions=True)

        op_10 = "_Test Op 10 Step Seq"
        op_20 = "_Test Op 20 Step Seq"
        for op_name in (op_10, op_20):
            if not frappe.db.exists("Operation", op_name):
                frappe.get_doc(
                    {
                        "doctype": "Operation",
                        "name": op_name,
                        "workstation": ws_name,
                    }
                ).insert(ignore_permissions=True)

        fg_seq = self._ensure_item("_Test FG Item Step Seq")
        existing_bom = frappe.db.get_value(
            "BOM", {"item": fg_seq, "is_active": 1, "docstatus": 1}, "name"
        )
        if existing_bom:
            bom = frappe.get_doc("BOM", existing_bom)
        else:
            bom = frappe.get_doc(
                {
                    "doctype": "BOM",
                    "item": fg_seq,
                    "company": self.company,
                    "quantity": 1,
                    "is_active": 1,
                    "is_default": 1,
                    "with_operations": 1,
                    "currency": "TRY",
                    "conversion_rate": 1.0,
                    "operations": [
                        {
                            "operation": op_10,
                            "workstation": ws_name,
                            "sequence_id": 10,
                            "time_in_mins": 10.0,
                        },
                        {
                            "operation": op_20,
                            "workstation": ws_name,
                            "sequence_id": 20,
                            "time_in_mins": 15.0,
                        },
                    ],
                    "items": [
                        {
                            "item_code": self.rm_item_1,
                            "qty": 2,
                            "uom": "Nos",
                            "rate": 10.0,
                            "source_warehouse": self.src_warehouse,
                            "operation": op_10,
                        }
                    ],
                }
            )
            bom.flags.ignore_permissions = True
            bom.insert(ignore_permissions=True)
            # KTAbom.validate() normalizes BOM sequences on validate
            self.assertEqual(
                [op.sequence_id for op in sorted(bom.operations, key=lambda d: d.idx)],
                [1, 2],
            )
            bom.submit()

        # Simulate a legacy BOM in DB still carrying legacy sequence_ids 10 and 20
        for row in sorted(bom.operations, key=lambda d: d.idx):
            frappe.db.set_value("BOM Operation", row.name, "sequence_id", row.idx * 10)
        frappe.clear_document_cache("BOM", bom.name)

        res = create_draft_work_order(
            item_code=fg_seq,
            qty=5,
            bom_no=bom.name,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )

        wo = frappe.get_doc("Work Order", res["name"])
        self.assertEqual(wo.docstatus, 0)
        self.assertEqual(len(wo.operations), 2)
        self.assertEqual(
            [op.sequence_id for op in sorted(wo.operations, key=lambda d: d.idx)],
            [1, 2],
        )

    def _ensure_item_alternative(self, item_code: str, alt_code: str, two_way: int = 0):
        frappe.db.set_value("Item", item_code, "allow_alternative_item", 1)
        frappe.db.set_value("Item", alt_code, "allow_alternative_item", 1)
        existing = frappe.db.get_value(
            "Item Alternative",
            {"item_code": item_code, "alternative_item_code": alt_code},
            "name",
        )
        if existing:
            doc = frappe.get_doc("Item Alternative", existing)
            doc.two_way = two_way
            doc.save(ignore_permissions=True)
            return doc
        doc = frappe.get_doc(
            {
                "doctype": "Item Alternative",
                "item_code": item_code,
                "alternative_item_code": alt_code,
                "two_way": two_way,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc

    def test_get_item_alternatives_bidirectional(self):
        """Item alternatives resolve both one-way and two-way relationships with stock levels."""
        base_item = self._ensure_item("_Test Alt Base Item")
        alt_oneway = self._ensure_item("_Test Alt OneWay Item")
        alt_twoway = self._ensure_item("_Test Alt TwoWay Item")

        self._ensure_item_alternative(base_item, alt_oneway, two_way=0)
        self._ensure_item_alternative(base_item, alt_twoway, two_way=1)

        # Base item should see both alternatives
        base_alts = get_item_alternatives(
            base_item, company=self.company, warehouse=self.src_warehouse
        )
        base_alt_codes = {a["item_code"] for a in base_alts}
        self.assertIn(alt_oneway, base_alt_codes)
        self.assertIn(alt_twoway, base_alt_codes)

        # One-way alternative: checking alt_oneway should NOT include base_item
        oneway_alts = get_item_alternatives(
            alt_oneway, company=self.company, warehouse=self.src_warehouse
        )
        oneway_codes = {a["item_code"] for a in oneway_alts}
        self.assertNotIn(base_item, oneway_codes)

        # Two-way alternative: checking alt_twoway SHOULD include base_item
        twoway_alts = get_item_alternatives(
            alt_twoway, company=self.company, warehouse=self.src_warehouse
        )
        twoway_codes = {a["item_code"] for a in twoway_alts}
        self.assertIn(base_item, twoway_codes)

        # Check two_way flag mapping
        base_entry_in_twoway = next(
            a for a in twoway_alts if a["item_code"] == base_item
        )
        self.assertTrue(base_entry_in_twoway["two_way"])

    def test_set_work_order_item_alternative_success(self):
        """Substituting an approved alternative updates item_code, sets custom_original_item, and adds a comment."""
        alt_item = self._ensure_item("_Test RM Alt 1 Success")
        self._ensure_item_alternative(self.rm_item_1, alt_item, two_way=0)

        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=2,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]
        wo = frappe.get_doc("Work Order", wo_name)
        row = next(d for d in wo.required_items if d.item_code == self.rm_item_1)

        result = set_work_order_item_alternative(wo_name, row.name, alt_item)
        self.assertIsInstance(result, dict)

        wo.reload()
        updated_row = next(d for d in wo.required_items if d.name == row.name)
        self.assertEqual(updated_row.item_code, alt_item)
        self.assertEqual(updated_row.custom_original_item, self.rm_item_1)

        # Verify comment added
        comments = frappe.get_all(
            "Comment",
            filters={
                "comment_type": "Comment",
                "reference_doctype": "Work Order",
                "reference_name": wo_name,
            },
            fields=["content"],
        )
        comment_texts = [c["content"] for c in comments]
        self.assertTrue(
            any(self.rm_item_1 in txt and alt_item in txt for txt in comment_texts)
        )

    def test_set_work_order_item_alternative_unapproved_fails(self):
        """Substituting an unapproved item raises ValidationError."""
        unapproved_item = self._ensure_item("_Test RM Unapproved Item")

        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=1,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]
        wo = frappe.get_doc("Work Order", wo_name)
        row = next(d for d in wo.required_items if d.item_code == self.rm_item_1)

        with self.assertRaises(frappe.ValidationError):
            set_work_order_item_alternative(wo_name, row.name, unapproved_item)

    def test_set_work_order_item_alternative_consumed_fails(self):
        """Attempting to swap an alternative on a row with consumed_qty > 0 raises ValidationError."""
        alt_item = self._ensure_item("_Test RM Alt Consumed Fail")
        self._ensure_item_alternative(self.rm_item_1, alt_item, two_way=0)

        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=1,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]
        wo = frappe.get_doc("Work Order", wo_name)
        row = next(d for d in wo.required_items if d.item_code == self.rm_item_1)

        frappe.db.set_value("Work Order Item", row.name, "consumed_qty", 1.0)
        frappe.clear_document_cache("Work Order", wo_name)

        with self.assertRaises(frappe.ValidationError):
            set_work_order_item_alternative(wo_name, row.name, alt_item)

    def test_restore_work_order_item_original(self):
        """Restoring original item reverts item_code, clears custom_original_item, and logs comment."""
        alt_item = self._ensure_item("_Test RM Alt Restore")
        self._ensure_item_alternative(self.rm_item_1, alt_item, two_way=0)

        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=2,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]
        wo = frappe.get_doc("Work Order", wo_name)
        row = next(d for d in wo.required_items if d.item_code == self.rm_item_1)

        # Step 1: Swap to alternative
        set_work_order_item_alternative(wo_name, row.name, alt_item)
        wo.reload()
        updated_row = next(d for d in wo.required_items if d.name == row.name)
        self.assertEqual(updated_row.item_code, alt_item)

        # Step 2: Restore original
        restore_result = restore_work_order_item_original(wo_name, row.name)
        self.assertIsInstance(restore_result, dict)

        wo.reload()
        restored_row = next(d for d in wo.required_items if d.name == row.name)
        self.assertEqual(restored_row.item_code, self.rm_item_1)
        self.assertFalse(restored_row.custom_original_item)

        # Check comment added for restoration
        comments = frappe.get_all(
            "Comment",
            filters={
                "comment_type": "Comment",
                "reference_doctype": "Work Order",
                "reference_name": wo_name,
            },
            fields=["content"],
        )
        comment_texts = [c["content"] for c in comments]
        expected_comment = frappe._(
            "Satır #{0}: Alternatif '{1}' iptal edilerek orijinal '{2}' geri yüklendi."
        ).format(restored_row.idx or 1, alt_item, self.rm_item_1)
        self.assertTrue(any(expected_comment in txt for txt in comment_texts))

    def test_material_availability_includes_alternative_metadata(self):
        """Material availability returns row_name, is_alternative, has_alternatives, and can_swap flags."""
        alt_item = self._ensure_item("_Test RM Alt Meta")
        self._ensure_item_alternative(self.rm_item_1, alt_item, two_way=0)

        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=2,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        avail = check_work_order_material_availability(wo_name)
        rm1_meta = next(d for d in avail["items"] if d["item_code"] == self.rm_item_1)

        self.assertTrue(rm1_meta["row_name"])
        self.assertFalse(rm1_meta["is_alternative"])
        self.assertTrue(rm1_meta["has_alternatives"])
        self.assertTrue(rm1_meta["can_swap"])
        self.assertIsNone(rm1_meta["custom_original_item"])

        # Also verify get_work_order_item_alternatives
        row_alts = get_work_order_item_alternatives(wo_name, rm1_meta["row_name"])
        self.assertEqual(row_alts["root_item_code"], self.rm_item_1)
        self.assertTrue(row_alts["can_swap"])
        self.assertFalse(row_alts["is_alternative"])
        self.assertTrue(
            any(a["item_code"] == alt_item for a in row_alts["alternatives"])
        )

    def test_update_work_order_qty_proportional_scaling(self):
        """Updating quantity scales required items and operations proportionally while preserving alternatives."""
        ws_name = "_Test WS Scale Seq"
        if not frappe.db.exists("Workstation", ws_name):
            frappe.get_doc(
                {"doctype": "Workstation", "workstation_name": ws_name}
            ).insert(ignore_permissions=True)

        op_name = "_Test Op Scale Seq"
        if not frappe.db.exists("Operation", op_name):
            frappe.get_doc(
                {
                    "doctype": "Operation",
                    "name": op_name,
                    "workstation": ws_name,
                }
            ).insert(ignore_permissions=True)

        fg_scale = self._ensure_item("_Test FG Item Scale")
        alt_item = self._ensure_item("_Test RM Alt Scale Item")
        self._ensure_item_alternative(self.rm_item_1, alt_item, two_way=0)

        existing_bom = frappe.db.get_value(
            "BOM", {"item": fg_scale, "is_active": 1, "docstatus": 1}, "name"
        )
        if existing_bom:
            bom_scale = existing_bom
        else:
            b = frappe.get_doc(
                {
                    "doctype": "BOM",
                    "item": fg_scale,
                    "company": self.company,
                    "quantity": 1,
                    "is_active": 1,
                    "is_default": 1,
                    "with_operations": 1,
                    "currency": "TRY",
                    "conversion_rate": 1.0,
                    "operations": [
                        {
                            "operation": op_name,
                            "workstation": ws_name,
                            "sequence_id": 1,
                            "time_in_mins": 20.0,
                        }
                    ],
                    "items": [
                        {
                            "item_code": self.rm_item_1,
                            "qty": 2,
                            "uom": "Nos",
                            "rate": 10.0,
                            "source_warehouse": self.src_warehouse,
                        },
                        {
                            "item_code": self.rm_item_2,
                            "qty": 3,
                            "uom": "Nos",
                            "rate": 5.0,
                            "source_warehouse": self.src_warehouse,
                        },
                    ],
                }
            )
            b.flags.ignore_permissions = True
            b.insert(ignore_permissions=True)
            b.submit()
            bom_scale = b.name

        # 1. Open 100-qty draft Work Order
        res = create_draft_work_order(
            item_code=fg_scale,
            qty=100,
            bom_no=bom_scale,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]
        wo = frappe.get_doc("Work Order", wo_name)
        self.assertEqual(flt(wo.qty), 100.0)
        self.assertEqual(len(wo.operations), 1)
        self.assertEqual(flt(wo.operations[0].time_in_mins), 2000.0)

        # 2. Swap 1 raw material with alternative (sets custom_original_item)
        rm1_row = next(d for d in wo.required_items if d.item_code == self.rm_item_1)
        orig_req_qty = flt(rm1_row.required_qty)
        self.assertEqual(orig_req_qty, 200.0)
        set_work_order_item_alternative(wo_name, rm1_row.name, alt_item)

        wo.reload()
        alt_row = next(d for d in wo.required_items if d.item_code == alt_item)
        self.assertEqual(alt_row.custom_original_item, self.rm_item_1)
        self.assertEqual(flt(alt_row.required_qty), 200.0)

        # 3. Update quantity to 150
        res_update = update_work_order_qty(wo_name, 150)
        self.assertEqual(res_update["qty"], 150.0)
        self.assertEqual(res_update["old_qty"], 100.0)

        wo.reload()
        self.assertEqual(flt(wo.qty), 150.0)

        # 4. Verify required_qty increased by 50%
        scaled_alt_row = next(d for d in wo.required_items if d.item_code == alt_item)
        self.assertEqual(flt(scaled_alt_row.required_qty), 300.0)
        # Verify custom_original_item is preserved
        self.assertEqual(scaled_alt_row.custom_original_item, self.rm_item_1)

        # Verify second RM item also scaled
        rm2_row = next(d for d in wo.required_items if d.item_code == self.rm_item_2)
        self.assertEqual(flt(rm2_row.required_qty), 450.0)

        # 5. Verify operation qty and time_in_mins scaled
        if hasattr(wo.operations[0], "qty"):
            self.assertEqual(flt(wo.operations[0].qty), 150.0)
        self.assertEqual(flt(wo.operations[0].time_in_mins), 3000.0)

        # 6. Verify activity comment added
        comments = frappe.get_all(
            "Comment",
            filters={
                "comment_type": "Comment",
                "reference_doctype": "Work Order",
                "reference_name": wo_name,
            },
            fields=["content"],
        )
        self.assertTrue(
            any("100" in c["content"] and "150" in c["content"] for c in comments)
        )

    def test_update_work_order_qty_non_draft_fails(self):
        """Updating quantity on a submitted or non-draft Work Order raises ValidationError."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=10,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]
        frappe.db.set_value("Work Order", wo_name, "docstatus", 1)

        with self.assertRaises(frappe.ValidationError):
            update_work_order_qty(wo_name, 20)

    def test_update_work_order_qty_validation_guards(self):
        """Zero or negative quantity raises ValidationError; same quantity is a no-op."""
        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=10,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        with self.assertRaises(frappe.ValidationError):
            update_work_order_qty(wo_name, 0)

        with self.assertRaises(frappe.ValidationError):
            update_work_order_qty(wo_name, -5)

        noop_res = update_work_order_qty(wo_name, 10)
        self.assertEqual(noop_res["qty"], 10.0)
        self.assertEqual(noop_res["old_qty"], 10.0)

    def _create_test_print_format(self, name: str, disabled: int = 0) -> str:
        if frappe.db.exists("Print Format", name):
            frappe.db.set_value(
                "Print Format",
                name,
                {
                    "doc_type": "Work Order",
                    "disabled": disabled,
                    "standard": "No",
                    "custom_format": 1,
                    "print_format_type": "Jinja",
                },
            )
            return name
        pf = frappe.get_doc(
            {
                "doctype": "Print Format",
                "name": name,
                "doc_type": "Work Order",
                "module": "Manufacturing",
                "standard": "No",
                "custom_format": 1,
                "print_format_type": "Jinja",
                "html": "<div>{{ doc.name }}</div>",
                "disabled": disabled,
            }
        )
        pf.flags.ignore_permissions = True
        pf.insert(ignore_permissions=True)
        return pf.name

    def test_get_work_order_print_options_formats_and_default_ordering(self):
        """Active custom Print Formats appear, disabled ones are excluded, Standard is present,
        and configured default_print_format is ordered first (with fallback if disabled).
        """
        uid = frappe.generate_hash(length=6)
        active_pf = self._create_test_print_format(
            f"_Test WO Print Active {uid}", disabled=0
        )
        default_pf = self._create_test_print_format(
            f"_Test WO Print Default {uid}", disabled=0
        )
        disabled_pf = self._create_test_print_format(
            f"_Test WO Print Disabled {uid}", disabled=1
        )
        self.addCleanup(
            lambda: [
                frappe.delete_doc(
                    "Print Format", name, force=1, ignore_permissions=True
                )
                for name in (active_pf, default_pf, disabled_pf)
                if frappe.db.exists("Print Format", name)
            ]
        )

        orig_ps_name = frappe.db.get_value(
            "Property Setter",
            {"doc_type": "Work Order", "property": "default_print_format"},
            "name",
        )
        orig_ps_val = (
            frappe.db.get_value("Property Setter", orig_ps_name, "value")
            if orig_ps_name
            else None
        )

        def restore_default_print_format():
            if orig_ps_name:
                frappe.db.set_value(
                    "Property Setter", orig_ps_name, "value", orig_ps_val
                )
            else:
                frappe.db.delete(
                    "Property Setter",
                    {"doc_type": "Work Order", "property": "default_print_format"},
                )
            frappe.clear_cache(doctype="Work Order")

        self.addCleanup(restore_default_print_format)

        if orig_ps_name:
            frappe.db.set_value("Property Setter", orig_ps_name, "value", default_pf)
        else:
            frappe.make_property_setter(
                {
                    "doctype": "Work Order",
                    "doctype_or_field": "DocType",
                    "property": "default_print_format",
                    "value": default_pf,
                    "property_type": "Data",
                }
            )
        frappe.clear_cache(doctype="Work Order")

        res = get_work_order_print_options()
        names = [pf["name"] for pf in res["print_formats"]]

        self.assertEqual(res["doctype"], "Work Order")
        self.assertIsNone(res["work_order"])
        self.assertIn(active_pf, names)
        self.assertIn(default_pf, names)
        self.assertIn("Standard", names)
        self.assertNotIn(disabled_pf, names)
        self.assertEqual(res["default_print_format"], default_pf)
        self.assertEqual(res["print_formats"][0]["name"], default_pf)
        self.assertTrue(res["print_formats"][0]["is_default"])

        # If configured default format is disabled, first remaining format becomes default
        frappe.db.set_value("Print Format", default_pf, "disabled", 1)
        res_fallback = get_work_order_print_options()
        fallback_names = [pf["name"] for pf in res_fallback["print_formats"]]
        self.assertNotIn(default_pf, fallback_names)
        self.assertEqual(
            res_fallback["default_print_format"],
            res_fallback["print_formats"][0]["name"],
        )
        self.assertTrue(res_fallback["print_formats"][0]["is_default"])

    def test_get_work_order_print_options_draft_setting_and_validation(self):
        """allow_print_for_draft controls can_print on Draft WO, and nonexistent WO raises ValidationError."""
        orig_with_lh = frappe.db.get_single_value("Print Settings", "with_letterhead")
        orig_allow_draft = frappe.db.get_single_value(
            "Print Settings", "allow_print_for_draft"
        )
        orig_allow_cancelled = frappe.db.get_single_value(
            "Print Settings", "allow_print_for_cancelled"
        )
        self.addCleanup(
            frappe.db.set_single_value,
            "Print Settings",
            {
                "with_letterhead": orig_with_lh,
                "allow_print_for_draft": orig_allow_draft,
                "allow_print_for_cancelled": orig_allow_cancelled,
            },
        )

        res = create_draft_work_order(
            item_code=self.fg_item,
            qty=5,
            bom_no=self.bom_no,
            source_warehouse=self.src_warehouse,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=self.fg_warehouse,
            company=self.company,
        )
        wo_name = res["name"]

        frappe.db.set_single_value("Print Settings", "allow_print_for_draft", 0)
        opts_blocked = get_work_order_print_options(wo_name)
        self.assertEqual(opts_blocked["work_order"], wo_name)
        self.assertFalse(opts_blocked["can_print"])
        self.assertEqual(opts_blocked["allow_print_for_draft"], 0)

        frappe.db.set_single_value("Print Settings", "allow_print_for_draft", 1)
        opts_allowed = get_work_order_print_options(wo_name)
        self.assertTrue(opts_allowed["can_print"])
        self.assertEqual(opts_allowed["allow_print_for_draft"], 1)

        with self.assertRaises(frappe.ValidationError):
            get_work_order_print_options("NON-EXISTENT-WO-PRINT-99999")
