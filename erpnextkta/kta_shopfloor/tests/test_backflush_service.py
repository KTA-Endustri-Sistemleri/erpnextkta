# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import flt

from erpnextkta.kta_shopfloor.services.backflush_service import (
    BackflushService,
    calculate_operation_raw_materials,
    create_consumption_entry,
    create_finished_goods_entry,
)
from erpnextkta.tests.test_utils import KTATestCase


class TestBackflushService(KTATestCase):
    def setUp(self):
        super().setUp()
        self.mock_wo = self._build_mock_work_order()

    def _build_mock_work_order(self):
        """Build a mock Work Order with 3 operations and raw materials."""
        wo = frappe._dict(
            {
                "name": "TEST-WO-BF-001",
                "doctype": "Work Order",
                "qty": 100.0,
                "produced_qty": 0.0,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "fg_warehouse": self.wip_warehouse,
                "source_warehouse": self.wip_warehouse,
                "skip_transfer": 1,
                "from_wip_warehouse": 0,
                "bom_no": "BOM-TEST-001",
                "use_multi_level_bom": 0,
                "production_item": self.item,
                "operations": [
                    frappe._dict(
                        {"operation": "0010 Kesim", "sequence_id": 1, "idx": 1}
                    ),
                    frappe._dict(
                        {"operation": "0020 Krimp", "sequence_id": 2, "idx": 2}
                    ),
                    frappe._dict(
                        {"operation": "0030 Test ve Montaj", "sequence_id": 3, "idx": 3}
                    ),
                ],
                "required_items": [
                    # Assigned to intermediate op 1
                    frappe._dict(
                        {
                            "item_code": "_TEST_RM_WIRE",
                            "item_name": "Test Wire",
                            "description": "Wire for cutting",
                            "operation": "0010 Kesim",
                            "required_qty": 100.0,
                            "consumed_qty": 0.0,
                            "stock_uom": "Mtr",
                            "source_warehouse": self.wip_warehouse,
                            "custom_original_item": "_ORIGINAL_WIRE",
                        }
                    ),
                    # Assigned to intermediate op 2
                    frappe._dict(
                        {
                            "item_code": "_TEST_RM_TERMINAL",
                            "item_name": "Test Terminal",
                            "description": "Terminal for crimping",
                            "operation": "0020 Krimp",
                            "required_qty": 200.0,
                            "consumed_qty": 0.0,
                            "stock_uom": "Nos",
                            "source_warehouse": self.wip_warehouse,
                        }
                    ),
                    # Unassigned general consumable (no operation)
                    frappe._dict(
                        {
                            "item_code": "_TEST_RM_TAPE",
                            "item_name": "Test Tape",
                            "description": "General binding tape",
                            "operation": None,
                            "required_qty": 50.0,
                            "consumed_qty": 0.0,
                            "stock_uom": "Roll",
                            "source_warehouse": self.wip_warehouse,
                        }
                    ),
                ],
            }
        )
        return wo

    def test_class_interface_parity(self):
        """BackflushService classmethods mirror module-level function aliases."""
        items = BackflushService.calculate_operation_raw_materials(
            self.mock_wo, "0010 Kesim", yield_qty=40.0, is_final=False
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(flt(items[0]["qty"]), 40.0)

    def test_intermediate_operation_consumes_only_assigned_materials(self):
        """Intermediate operation consumes only raw materials assigned to that operation."""
        # Yield 40 units on Op 1 (0010 Kesim)
        items = calculate_operation_raw_materials(
            self.mock_wo, "0010 Kesim", yield_qty=40.0, is_final=False
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["item_code"], "_TEST_RM_WIRE")
        # (40 / 100) * 100 = 40.0
        self.assertEqual(flt(items[0]["qty"]), 40.0)
        self.assertEqual(items[0]["s_warehouse"], self.wip_warehouse)
        self.assertEqual(items[0]["original_item"], "_ORIGINAL_WIRE")
        self.assertEqual(items[0]["custom_original_item"], "_ORIGINAL_WIRE")

    def test_unassigned_materials_skipped_on_intermediate_consumed_on_final_operation(
        self,
    ):
        """Unassigned materials are skipped on intermediate operations, consumed on final operation."""
        # Op 2 (0020 Krimp) is intermediate -> unassigned Tape must NOT be included
        items_op2 = calculate_operation_raw_materials(
            self.mock_wo, "0020 Krimp", yield_qty=50.0, is_final=False
        )
        self.assertEqual(len(items_op2), 1)
        self.assertEqual(items_op2[0]["item_code"], "_TEST_RM_TERMINAL")
        # (50 / 100) * 200 = 100.0
        self.assertEqual(flt(items_op2[0]["qty"]), 100.0)

        # Senior Review Finding: Even if is_final=True on an intermediate operation,
        # unassigned materials must NOT be consumed!
        items_op2_final = calculate_operation_raw_materials(
            self.mock_wo, "0020 Krimp", yield_qty=50.0, is_final=True
        )
        self.assertEqual(len(items_op2_final), 1)
        self.assertEqual(items_op2_final[0]["item_code"], "_TEST_RM_TERMINAL")

        # Op 3 (0030 Test ve Montaj) is the last operation -> unassigned Tape MUST be included.
        # Assume preceding operations' materials were already proportionally consumed for 50 units.
        self.mock_wo.required_items[0].consumed_qty = 50.0
        self.mock_wo.required_items[1].consumed_qty = 100.0
        items_op3 = calculate_operation_raw_materials(
            self.mock_wo, "0030 Test ve Montaj", yield_qty=50.0, is_final=False
        )
        # Only unassigned Tape is picked up since preceding materials are already consumed
        self.assertEqual(len(items_op3), 1)
        self.assertEqual(items_op3[0]["item_code"], "_TEST_RM_TAPE")
        # (50 / 100) * 50 = 25.0
        self.assertEqual(flt(items_op3[0]["qty"]), 25.0)

    def test_milestone_operation_catches_up_unconsumed_preceding_materials(self):
        """Milestone operation automatically catches up unconsumed raw materials of preceding operations."""
        # Wire: required 100, consumed 20 (deficit: 50 - 20 = 30)
        # Terminal: required 200, consumed 0 (deficit: 100 - 0 = 100)
        # Tape (unassigned): required 50, consumed 0 (proportional: 25)
        self.mock_wo.required_items[0].consumed_qty = 20.0
        self.mock_wo.required_items[1].consumed_qty = 0.0
        self.mock_wo.required_items[2].consumed_qty = 0.0

        items = calculate_operation_raw_materials(
            self.mock_wo, "0030 Test ve Montaj", yield_qty=50.0, is_final=False
        )

        self.assertEqual(len(items), 3)
        item_map = {d["item_code"]: flt(d["qty"]) for d in items}
        self.assertEqual(item_map["_TEST_RM_WIRE"], 30.0)
        self.assertEqual(item_map["_TEST_RM_TERMINAL"], 100.0)
        self.assertEqual(item_map["_TEST_RM_TAPE"], 25.0)

    def test_final_confirmation_closes_rounding_difference(self):
        """When is_final is True, remaining unconsumed balance closes rounding differences."""
        # Suppose required_qty = 10.0, target wo qty = 3.0.
        # Two previous confirmations consumed 3.3333 + 3.3333 = 6.6666
        wo = frappe._dict(
            {
                "name": "TEST-WO-ROUNDING",
                "qty": 3.0,
                "wip_warehouse": self.wip_warehouse,
                "skip_transfer": 1,
                "operations": [
                    frappe._dict(
                        {"operation": "0010 Kesim", "sequence_id": 1, "idx": 1}
                    )
                ],
                "required_items": [
                    frappe._dict(
                        {
                            "item_code": "_TEST_RM_ROUNDING",
                            "operation": "0010 Kesim",
                            "required_qty": 10.0,
                            "consumed_qty": 6.6666,
                            "stock_uom": "Mtr",
                            "source_warehouse": self.wip_warehouse,
                        }
                    )
                ],
            }
        )

        # When is_final=True, remaining balance (10.0 - 6.6666 = 3.3334) should be returned
        items = calculate_operation_raw_materials(
            wo, "0010 Kesim", yield_qty=1.0, is_final=True
        )
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(flt(items[0]["qty"]), 3.3334, places=4)

    def test_zero_material_operation_gracefully_skips_consumption_entry(self):
        """An operation with no raw materials assigned returns None and creates no Stock Entry."""
        wo = frappe._dict(
            {
                "name": "TEST-WO-ZERO-RM",
                "qty": 100.0,
                "wip_warehouse": self.wip_warehouse,
                "skip_transfer": 1,
                "operations": [
                    frappe._dict(
                        {"operation": "0010 Kesim", "sequence_id": 1, "idx": 1}
                    ),
                    frappe._dict(
                        {
                            "operation": "0020 Pure Visual Inspection",
                            "sequence_id": 2,
                            "idx": 2,
                        }
                    ),
                    frappe._dict(
                        {"operation": "0030 Final Packing", "sequence_id": 3, "idx": 3}
                    ),
                ],
                "required_items": [
                    frappe._dict(
                        {
                            "item_code": "_TEST_RM_WIRE",
                            "operation": "0010 Kesim",
                            "required_qty": 100.0,
                            "consumed_qty": 0.0,
                            "stock_uom": "Mtr",
                            "source_warehouse": self.wip_warehouse,
                        }
                    )
                ],
            }
        )

        # Op 2 is intermediate and has 0 raw materials
        result = create_consumption_entry(
            wo, "0020 Pure Visual Inspection", yield_qty=20.0, is_final=False
        )
        self.assertIsNone(result)

    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.get_doc")
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.new_doc")
    def test_create_consumption_entry_payload_and_fifo(
        self, mock_new_doc, mock_get_doc
    ):
        """Consumption entry is constructed with correct purpose, items and confirmation ref."""
        mock_se = MagicMock()
        mock_se.name = "MAT-STE-2026-00001"
        mock_se.items = []
        mock_se.meta.has_field.return_value = True

        def append_item(field, item_dict):
            if field == "items":
                mock_se.items.append(frappe._dict(item_dict))

        mock_se.append.side_effect = append_item
        mock_new_doc.return_value = mock_se
        mock_get_doc.return_value = self.mock_wo

        se_name = create_consumption_entry(
            self.mock_wo,
            "0010 Kesim",
            yield_qty=50.0,
            is_final=False,
            confirmation_name="CONF-2026-0001",
        )

        self.assertEqual(se_name, "MAT-STE-2026-00001")
        self.assertEqual(mock_se.purpose, "Material Consumption for Manufacture")
        self.assertEqual(mock_se.work_order, self.mock_wo.name)
        self.assertEqual(mock_se.fg_completed_qty, 50.0)
        self.assertEqual(mock_se.custom_confirmation, "CONF-2026-0001")
        self.assertIn("CONF-2026-0001", mock_se.remarks)
        self.assertEqual(len(mock_se.items), 1)
        self.assertEqual(mock_se.items[0].item_code, "_TEST_RM_WIRE")
        self.assertEqual(flt(mock_se.items[0].qty), 50.0)
        self.assertEqual(mock_se.items[0].original_item, "_ORIGINAL_WIRE")
        self.assertEqual(mock_se.items[0].custom_original_item, "_ORIGINAL_WIRE")

        # Verified insert and submit were called
        mock_se.insert.assert_called_once()
        mock_se.submit.assert_called_once()

    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.get_doc")
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.new_doc")
    def test_create_finished_goods_entry(self, mock_new_doc, mock_get_doc):
        """Final operation creates Manufacture Stock Entry with finished goods to fg_warehouse."""
        mock_se = MagicMock()
        mock_se.name = "MFG-STE-2026-00001"
        mock_se.meta.has_field.return_value = True
        mock_se.items = []
        mock_new_doc.return_value = mock_se
        mock_get_doc.return_value = self.mock_wo

        se_name = create_finished_goods_entry(
            self.mock_wo,
            yield_qty=100.0,
            is_final=True,
            confirmation_name="CONF-2026-0002",
        )

        self.assertEqual(se_name, "MFG-STE-2026-00001")
        self.assertEqual(mock_se.purpose, "Manufacture")
        self.assertEqual(mock_se.stock_entry_type, "Manufacture")
        self.assertEqual(mock_se.work_order, self.mock_wo.name)
        self.assertEqual(mock_se.fg_completed_qty, 100.0)
        self.assertEqual(mock_se.to_warehouse, self.mock_wo.fg_warehouse)
        self.assertEqual(mock_se.custom_confirmation, "CONF-2026-0002")
        self.assertIs(mock_se.flags.kta_is_final_confirmation, True)
        mock_se.insert.assert_called_once()
        mock_se.submit.assert_called_once()

    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.get_doc")
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.new_doc")
    def test_create_finished_goods_entry_sets_final_confirmation_flag(
        self, mock_new_doc, mock_get_doc
    ):
        """kta_is_final_confirmation flag reflects is_final and is set before get_items()."""
        mock_get_doc.return_value = self.mock_wo

        for expected_flag in (True, False):
            mock_se = MagicMock()
            mock_se.name = f"MFG-STE-FLAG-{int(expected_flag)}"
            mock_se.flags = frappe._dict()
            mock_se.meta.has_field.return_value = True
            mock_se.items = []
            flag_at_get_items = []

            def capture_flag_on_get_items(se_ref=mock_se, captured=flag_at_get_items):
                captured.append(se_ref.flags.get("kta_is_final_confirmation"))

            mock_se.get_items.side_effect = capture_flag_on_get_items
            mock_new_doc.return_value = mock_se

            create_finished_goods_entry(
                self.mock_wo,
                yield_qty=50.0,
                is_final=expected_flag,
                confirmation_name=f"CONF-FLAG-{int(expected_flag)}",
            )

            self.assertIs(mock_se.flags.kta_is_final_confirmation, expected_flag)
            self.assertEqual(flag_at_get_items, [expected_flag])

    def test_milestone_partial_confirmation_computes_target_cumulative_qty(self):
        """When target_op_qty is omitted on a partially completed milestone, target_cumulative_qty
        adds yield_qty on top of completed_qty even when yield_qty <= completed_qty (and closes
        remaining balance when is_final=True).
        """
        wo = frappe._dict(
            {
                "name": "TEST-WO-PARTIAL-MILESTONE",
                "qty": 1800.0,
                "wip_warehouse": self.wip_warehouse,
                "skip_transfer": 1,
                "operations": [
                    frappe._dict(
                        {
                            "operation": "OP10",
                            "sequence_id": 1,
                            "idx": 1,
                            "completed_qty": 990.0,
                        }
                    ),
                    frappe._dict(
                        {
                            "operation": "OP20",
                            "sequence_id": 2,
                            "idx": 2,
                            "completed_qty": 990.0,
                        }
                    ),
                    frappe._dict(
                        {
                            "operation": "OP30",
                            "sequence_id": 3,
                            "idx": 3,
                            "completed_qty": 990.0,
                        }
                    ),
                ],
                "required_items": [
                    frappe._dict(
                        {
                            "item_code": "_TEST_RM_OP10",
                            "operation": "OP10",
                            "required_qty": 1800.0,
                            "consumed_qty": 990.0,
                            "stock_uom": "Nos",
                            "source_warehouse": self.wip_warehouse,
                        }
                    )
                ],
            }
        )

        # Case 1: yield_qty=330.0 (<= 990.0) with target_op_qty=None -> 990 + 330 - 990 = 330.0
        items_330 = calculate_operation_raw_materials(
            wo, "OP30", yield_qty=330.0, is_final=False, target_op_qty=None
        )
        self.assertEqual(len(items_330), 1)
        self.assertEqual(items_330[0]["item_code"], "_TEST_RM_OP10")
        self.assertEqual(flt(items_330[0]["qty"]), 330.0)

        # Case 2: yield_qty=810.0 (<= 990.0) with target_op_qty=None -> 990 + 810 - 990 = 810.0
        items_810 = calculate_operation_raw_materials(
            wo, "OP30", yield_qty=810.0, is_final=False, target_op_qty=None
        )
        self.assertEqual(len(items_810), 1)
        self.assertEqual(items_810[0]["item_code"], "_TEST_RM_OP10")
        self.assertEqual(flt(items_810[0]["qty"]), 810.0)

        # Case 3: yield_qty=100.0 with is_final=True, target_op_qty=None -> remaining 810.0
        items_final = calculate_operation_raw_materials(
            wo, "OP30", yield_qty=100.0, is_final=True, target_op_qty=None
        )
        self.assertEqual(len(items_final), 1)
        self.assertEqual(items_final[0]["item_code"], "_TEST_RM_OP10")
        self.assertEqual(flt(items_final[0]["qty"]), 810.0)

    @patch(
        "erpnextkta.kta_shopfloor.services.backflush_service.get_validated_wip_consumption_account"
    )
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.get_doc")
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.new_doc")
    def test_create_consumption_entry_sets_wip_expense_account_when_configured(
        self, mock_new_doc, mock_get_doc, mock_get_wip
    ):
        """Consumption entry sets expense_account to WIP account when configured, else omits it."""
        mock_get_doc.return_value = self.mock_wo

        # Case 1: WIP account configured
        mock_get_wip.return_value = "151.01.002 - WIP - TKTA"
        mock_se = MagicMock()
        mock_se.name = "MAT-STE-WIP-001"
        mock_se.items = []
        mock_se.meta.has_field.return_value = True
        mock_se.append.side_effect = lambda field, row: mock_se.items.append(
            frappe._dict(row)
        )
        mock_new_doc.return_value = mock_se

        create_consumption_entry(self.mock_wo, "0010 Kesim", yield_qty=50.0)
        self.assertEqual(
            mock_se.items[0].get("expense_account"), "151.01.002 - WIP - TKTA"
        )

        # Case 2: WIP account is None -> expense_account not injected
        mock_get_wip.return_value = None
        mock_se_none = MagicMock()
        mock_se_none.name = "MAT-STE-WIP-002"
        mock_se_none.items = []
        mock_se_none.meta.has_field.return_value = True
        mock_se_none.append.side_effect = lambda field, row: mock_se_none.items.append(
            frappe._dict(row)
        )
        mock_new_doc.return_value = mock_se_none

        create_consumption_entry(self.mock_wo, "0010 Kesim", yield_qty=50.0)
        self.assertNotIn("expense_account", mock_se_none.items[0])

    @patch(
        "erpnextkta.kta_shopfloor.services.backflush_service.get_validated_wip_consumption_account"
    )
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.db.exists")
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.get_doc")
    @patch("erpnextkta.kta_shopfloor.services.backflush_service.frappe.new_doc")
    def test_create_finished_goods_entry_sets_wip_expense_account_for_fg_only(
        self, mock_new_doc, mock_get_doc, mock_exists, mock_get_wip
    ):
        """FG-only Manufacture entry sets expense_account before calculate_rate_and_amount."""
        mock_get_doc.return_value = self.mock_wo
        mock_exists.return_value = "MAT-STE-CONS-001"
        mock_get_wip.return_value = "151.01.002 - WIP - TKTA"

        rm_row = frappe._dict(
            {
                "item_code": "_TEST_RM_WIRE",
                "s_warehouse": self.wip_warehouse,
                "t_warehouse": "",
                "is_finished_item": 0,
                "is_scrap_item": 0,
            }
        )
        fg_row = frappe._dict(
            {
                "item_code": self.item,
                "s_warehouse": "",
                "t_warehouse": self.wip_warehouse,
                "is_finished_item": 1,
                "is_scrap_item": 0,
            }
        )

        mock_se = MagicMock()
        mock_se.name = "MFG-STE-WIP-001"
        mock_se.flags = frappe._dict()
        mock_se.meta.has_field.return_value = True
        mock_se.items = []
        expense_at_calc = []

        def fake_get_items():
            mock_se.items = [rm_row, fg_row]

        def capture_expense_at_calc(**kwargs):
            expense_at_calc.append(mock_se.items[0].get("expense_account"))

        mock_se.get_items.side_effect = fake_get_items
        mock_se.calculate_rate_and_amount.side_effect = capture_expense_at_calc
        mock_new_doc.return_value = mock_se

        create_finished_goods_entry(self.mock_wo, yield_qty=100.0, is_final=True)

        self.assertEqual(len(mock_se.items), 1)
        self.assertEqual(
            mock_se.items[0].get("expense_account"), "151.01.002 - WIP - TKTA"
        )
        self.assertEqual(expense_at_calc, ["151.01.002 - WIP - TKTA"])

        # Fallback manual FG row when get_items() leaves items empty & wip_account is None
        mock_get_wip.return_value = None
        mock_exists.return_value = False
        mock_se_none = MagicMock()
        mock_se_none.name = "MFG-STE-WIP-002"
        mock_se_none.flags = frappe._dict()
        mock_se_none.meta.has_field.return_value = True
        mock_se_none.items = []
        mock_se_none.append.side_effect = lambda field, row: mock_se_none.items.append(
            frappe._dict(row)
        )
        mock_new_doc.return_value = mock_se_none

        create_finished_goods_entry(self.mock_wo, yield_qty=10.0, is_final=True)
        self.assertEqual(len(mock_se_none.items), 1)
        self.assertNotIn("expense_account", mock_se_none.items[0])
