# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.utils import flt

from erpnextkta.kta_shopfloor.api import get_shopfloor_hub_context
from erpnextkta.kta_shopfloor.services.confirmation_service import (
    ConfirmationService,
    confirm_operation,
)
from erpnextkta.kta_shopfloor.services.reversal_service import ReversalService
from erpnextkta.tests.test_utils import KTATestCase


class TestConfirmationService(KTATestCase):
    def setUp(self):
        super().setUp()
        self._setup_test_work_order_and_job_cards()

    def _setup_test_work_order_and_job_cards(self):
        """Prepare a Work Order with 2 operations and draft (docstatus=0) Job Cards."""
        self.op1 = "0010 Kesim"
        self.op2 = "0020 Test ve Montaj"

        # Ensure Operation records exist
        for op in [self.op1, self.op2]:
            if not frappe.db.exists("Operation", op):
                frappe.get_doc(
                    {"doctype": "Operation", "name": op, "workstation": self.ws_name}
                ).insert(ignore_permissions=True)

        frappe.db.delete("Work Order Operation", {"parent": self.wo_name})
        frappe.db.delete("Stock Entry", {"work_order": self.wo_name})
        frappe.db.delete("KTA Production Confirmation", {"work_order": self.wo_name})
        frappe.db.set_value("Item", self.item, "valuation_rate", 10.0)
        frappe.get_doc(
            {
                "doctype": "Work Order Operation",
                "parent": self.wo_name,
                "parenttype": "Work Order",
                "parentfield": "operations",
                "operation": self.op1,
                "workstation": self.ws_name,
                "sequence_id": 1,
                "idx": 1,
                "completed_qty": 0.0,
                "time_in_mins": 60.0,
                "status": "Pending",
            }
        ).insert(ignore_permissions=True)

        frappe.get_doc(
            {
                "doctype": "Work Order Operation",
                "parent": self.wo_name,
                "parenttype": "Work Order",
                "parentfield": "operations",
                "operation": self.op2,
                "workstation": self.ws_name,
                "sequence_id": 2,
                "idx": 2,
                "completed_qty": 0.0,
                "time_in_mins": 60.0,
                "status": "Pending",
            }
        ).insert(ignore_permissions=True)

        frappe.db.set_value(
            "Work Order",
            self.wo_name,
            {
                "docstatus": 1,
                "status": "Not Started",
                "produced_qty": 0.0,
            },
        )
        self.wo = frappe.get_doc("Work Order", self.wo_name)

        # Create or update Job Cards with docstatus = 0 (open/draft container)
        self.jc1 = self._get_or_create_draft_job_card("TEST-JC-CO11N-001", self.op1)
        self.jc2 = self._get_or_create_draft_job_card("TEST-JC-CO11N-002", self.op2)
        frappe.db.commit()

    def _get_or_create_draft_job_card(self, name: str, operation: str) -> str:
        if frappe.db.exists("Job Card", name):
            frappe.db.set_value(
                "Job Card",
                name,
                {
                    "work_order": self.wo_name,
                    "operation": operation,
                    "docstatus": 0,
                    "status": "Open",
                    "total_completed_qty": 0.0,
                    "for_quantity": 100.0,
                },
            )
            return name

        jc = frappe.get_doc(
            {
                "doctype": "Job Card",
                "name": name,
                "work_order": self.wo_name,
                "operation": operation,
                "workstation": self.ws_name,
                "production_item": self.item,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "for_quantity": 100.0,
                "total_completed_qty": 0.0,
                "status": "Open",
                "docstatus": 0,
            }
        )
        jc.flags.ignore_permissions = True
        jc.flags.ignore_mandatory = True
        jc.insert(ignore_permissions=True)
        return jc.name

    def test_validation_errors(self):
        """Test validation of required inputs and positive yield_qty."""
        # Missing work_order
        with self.assertRaises(frappe.ValidationError):
            confirm_operation(
                {"work_order": "", "operation": self.op1, "yield_qty": 10.0}
            )

        # Missing operation
        with self.assertRaises(frappe.ValidationError):
            confirm_operation(
                {"work_order": self.wo_name, "operation": "", "yield_qty": 10.0}
            )

        # Non-positive yield_qty
        with self.assertRaises(frappe.ValidationError):
            confirm_operation(
                {"work_order": self.wo_name, "operation": self.op1, "yield_qty": 0.0}
            )

        with self.assertRaises(frappe.ValidationError):
            confirm_operation(
                {"work_order": self.wo_name, "operation": self.op1, "yield_qty": -5.0}
            )

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
    )
    def test_intermediate_operation_confirmation(
        self, mock_fg_entry, mock_consumption_entry
    ):
        """Intermediate operation triggers consumption entry only, increments completed_qty, keeps JC docstatus=0."""
        mock_consumption_entry.return_value = "STE-CONSUMPTION-0001"

        payload = {
            "work_order": self.wo_name,
            "operation": self.op1,
            "job_card": self.jc1,
            "yield_qty": 25.0,
            "is_final_confirmation": 0,
        }

        res = confirm_operation(payload)

        self.assertTrue(res.get("success"))
        conf_name = res.get("confirmation")
        self.assertTrue(conf_name)
        self.assertEqual(res.get("stock_entry"), "STE-CONSUMPTION-0001")
        self.assertFalse(res.get("is_final"))

        # Verify KTA Production Confirmation document
        conf_doc = frappe.get_doc("KTA Production Confirmation", conf_name)
        self.assertEqual(conf_doc.docstatus, 1)
        self.assertEqual(conf_doc.work_order, self.wo_name)
        self.assertEqual(conf_doc.operation, self.op1)
        self.assertEqual(flt(conf_doc.yield_qty), 25.0)
        self.assertEqual(conf_doc.stock_entry, "STE-CONSUMPTION-0001")

        # Verify BackflushService calls: consumption called, finished goods NOT called
        mock_consumption_entry.assert_called_once()
        mock_fg_entry.assert_not_called()

        # Verify Work Order Operation row completed_qty incremented
        wo = frappe.get_doc("Work Order", self.wo_name)
        op_row = next(d for d in wo.operations if d.operation == self.op1)
        self.assertEqual(flt(op_row.completed_qty), 25.0)

        # Verify Job Card total_completed_qty incremented, docstatus remains 0 (Draft)
        jc = frappe.get_doc("Job Card", self.jc1)
        self.assertEqual(flt(jc.total_completed_qty), 25.0)
        self.assertEqual(jc.docstatus, 0)
        self.assertNotEqual(jc.status, "Completed")

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
    )
    def test_milestone_operation_triggers_finished_goods_entry(
        self, mock_fg_entry, mock_consumption_entry
    ):
        """Milestone (last) operation triggers both consumption and finished goods entry, updates WO produced_qty."""
        mock_consumption_entry.return_value = "STE-CONSUMPTION-0002"
        mock_fg_entry.return_value = "STE-MANUFACTURE-0001"

        payload = {
            "work_order": self.wo_name,
            "operation": self.op2,  # Last operation
            "yield_qty": 40.0,
            "is_final_confirmation": 0,
        }

        res = ConfirmationService.confirm_operation(payload)

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("stock_entry"), "STE-MANUFACTURE-0001")

        mock_consumption_entry.assert_called_once()
        mock_fg_entry.assert_called_once()

        # Job Card docstatus must remain 0
        jc = frappe.get_doc("Job Card", self.jc2)
        self.assertEqual(flt(jc.total_completed_qty), 40.0)
        self.assertEqual(jc.docstatus, 0)

        # Work Order produced_qty updated
        wo = frappe.get_doc("Work Order", self.wo_name)
        self.assertEqual(flt(wo.produced_qty), 40.0)

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
    )
    def test_final_confirmation_flag_closes_job_card_and_work_order(
        self, mock_fg_entry, mock_consumption_entry
    ):
        """When is_final_confirmation=True, JC is Completed (docstatus=0) and WO is Completed."""
        mock_consumption_entry.return_value = "STE-CONSUMPTION-0003"
        mock_fg_entry.return_value = "STE-MANUFACTURE-0002"

        payload = {
            "work_order": self.wo_name,
            "operation": self.op2,
            "yield_qty": 30.0,
            "is_final_confirmation": 1,
        }

        res = confirm_operation(payload)

        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("is_final"))

        jc = frappe.get_doc("Job Card", self.jc2)
        self.assertEqual(jc.docstatus, 0)
        self.assertEqual(jc.status, "Completed")

        wo = frappe.get_doc("Work Order", self.wo_name)
        self.assertEqual(wo.status, "Completed")

    def test_job_card_auto_resolution(self):
        """When job_card is omitted from payload, it resolves to the open Job Card."""
        with (
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
            ) as mock_se,
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
            ),
        ):
            mock_se.return_value = "STE-RESOLVE-0001"

            res = confirm_operation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op1,
                    # No job_card provided
                    "yield_qty": 10.0,
                }
            )

            conf_doc = frappe.get_doc(
                "KTA Production Confirmation", res["confirmation"]
            )
            self.assertEqual(conf_doc.job_card, self.jc1)

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    def test_atomic_rollback_on_failure(self, mock_consumption_entry):
        """If BackflushService fails, transaction rolls back; no confirmation doc or progress is persisted."""
        mock_consumption_entry.side_effect = frappe.ValidationError(
            "Insufficient raw material stock"
        )

        before_confs = frappe.db.count(
            "KTA Production Confirmation", {"work_order": self.wo_name}
        )

        payload = {
            "work_order": self.wo_name,
            "operation": self.op1,
            "yield_qty": 15.0,
        }

        with self.assertRaises(frappe.ValidationError):
            confirm_operation(payload)

        after_confs = frappe.db.count(
            "KTA Production Confirmation", {"work_order": self.wo_name}
        )
        self.assertEqual(before_confs, after_confs)

        jc = frappe.get_doc("Job Card", self.jc1)
        self.assertEqual(flt(jc.total_completed_qty), 0.0)

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    def test_json_string_and_kwargs_payload_normalization(self, mock_consumption_entry):
        """Service properly handles stringified JSON and kwargs arguments."""
        import json

        mock_consumption_entry.return_value = "STE-NORMALIZED-0001"

        # Case 1: JSON string payload
        json_payload = json.dumps(
            {
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 5.0,
            }
        )
        res1 = confirm_operation(json_payload)
        self.assertTrue(res1.get("success"))

        # Case 2: Direct kwargs
        res2 = confirm_operation(
            work_order=self.wo_name,
            operation=self.op1,
            job_card=self.jc1,
            yield_qty=5.0,
        )
        self.assertTrue(res2.get("success"))

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    def test_sequential_partial_confirmations_accumulate_qty(
        self, mock_consumption_entry
    ):
        """Sequential partial confirmations accumulate completed_qty on WO and JC."""
        mock_consumption_entry.return_value = "STE-SEQ-0001"

        confirm_operation(
            {
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 10.0,
            }
        )
        confirm_operation(
            {
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 15.0,
            }
        )

        jc = frappe.get_doc("Job Card", self.jc1)
        self.assertEqual(flt(jc.total_completed_qty), 25.0)
        self.assertEqual(jc.docstatus, 0)
        self.assertEqual(jc.status, "Work In Progress")

        wo = frappe.get_doc("Work Order", self.wo_name)
        op_row = next(d for d in wo.operations if d.operation == self.op1)
        self.assertEqual(flt(op_row.completed_qty), 25.0)
        self.assertEqual(wo.status, "In Process")

    def test_unmocked_milestone_confirmation_end_to_end(self):
        """End-to-end milestone confirmation with actual unmocked create_finished_goods_entry

        execution, verifying KTAStockEntry check_if_operations_completed passes cleanly.
        """
        # Step 1: Intermediate operation confirmation (Op 1)
        res1 = confirm_operation(
            {
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 20.0,
                "is_final_confirmation": 0,
            }
        )
        self.assertTrue(res1.get("success"))

        # Verify Op 1 completed_qty in DB
        op1_completed = frappe.db.get_value(
            "Work Order Operation",
            {"parent": self.wo_name, "operation": self.op1},
            "completed_qty",
        )
        self.assertEqual(flt(op1_completed), 20.0)

        # Step 2: Milestone operation confirmation (Op 2) - completely unmocked!
        res2 = confirm_operation(
            {
                "work_order": self.wo_name,
                "operation": self.op2,
                "job_card": self.jc2,
                "yield_qty": 20.0,
                "is_final_confirmation": 0,
            }
        )
        self.assertTrue(res2.get("success"))
        fg_se_name = res2.get("stock_entry")
        self.assertTrue(fg_se_name)

        # Verify Stock Entry created is a submitted Manufacture entry
        se_doc = frappe.get_doc("Stock Entry", fg_se_name)
        self.assertEqual(se_doc.docstatus, 1)
        self.assertEqual(se_doc.purpose, "Manufacture")
        self.assertEqual(flt(se_doc.fg_completed_qty), 20.0)
        self.assertEqual(se_doc.work_order, self.wo_name)

        # Verify Work Order and Operations state
        wo = frappe.get_doc("Work Order", self.wo_name)
        self.assertEqual(flt(wo.produced_qty), 20.0)
        for op in wo.operations:
            self.assertEqual(flt(op.completed_qty), 20.0)

    def _create_4_op_work_order(self, wo_name="TEST-WO-4OP-001", qty=5000.0):
        op_names = ["0010 Kesim", "0020 Krimp", "0030 Montaj", "0040 Test"]
        for op in op_names:
            if not frappe.db.exists("Operation", op):
                frappe.get_doc(
                    {"doctype": "Operation", "name": op, "workstation": self.ws_name}
                ).insert(ignore_permissions=True)

        rm_items = [
            "_TEST_RM_KABLO",
            "_TEST_RM_TERMINAL",
            "_TEST_RM_KONNEKTOR",
            "_TEST_RM_ETIKET",
        ]
        for rm in rm_items:
            if not frappe.db.exists("Item", rm):
                frappe.get_doc(
                    {
                        "doctype": "Item",
                        "item_code": rm,
                        "item_name": rm,
                        "item_group": self.item_group,
                        "is_stock_item": 1,
                        "stock_uom": "Nos",
                        "valuation_rate": 1.0,
                    }
                ).insert(ignore_permissions=True)
            else:
                frappe.db.set_value("Item", rm, "valuation_rate", 1.0)

        if frappe.db.exists("Work Order", wo_name):
            frappe.db.delete("KTA Production Confirmation", {"work_order": wo_name})
            frappe.db.delete("Stock Entry", {"work_order": wo_name})
            frappe.db.delete("Job Card", {"work_order": wo_name})
            frappe.db.delete("Work Order Operation", {"parent": wo_name})
            frappe.db.delete("Work Order Item", {"parent": wo_name})
            frappe.delete_doc("Work Order", wo_name, force=1)

        wo = frappe.get_doc(
            {
                "doctype": "Work Order",
                "naming_series": "MFG-WO-.YYYY.-",
                "production_item": self.item,
                "qty": qty,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "fg_warehouse": self.wip_warehouse,
                "source_warehouse": self.wip_warehouse,
                "skip_transfer": 1,
                "status": "Not Started",
                "produced_qty": 0.0,
                "operations": [
                    {
                        "operation": op_names[0],
                        "workstation": self.ws_name,
                        "sequence_id": 1,
                        "idx": 1,
                        "completed_qty": 0.0,
                        "status": "Pending",
                        "time_in_mins": 60.0,
                    },
                    {
                        "operation": op_names[1],
                        "workstation": self.ws_name,
                        "sequence_id": 2,
                        "idx": 2,
                        "completed_qty": 0.0,
                        "status": "Pending",
                        "time_in_mins": 60.0,
                    },
                    {
                        "operation": op_names[2],
                        "workstation": self.ws_name,
                        "sequence_id": 3,
                        "idx": 3,
                        "completed_qty": 0.0,
                        "status": "Pending",
                        "time_in_mins": 60.0,
                    },
                    {
                        "operation": op_names[3],
                        "workstation": self.ws_name,
                        "sequence_id": 4,
                        "idx": 4,
                        "completed_qty": 0.0,
                        "status": "Pending",
                        "time_in_mins": 60.0,
                    },
                ],
                "required_items": [
                    {
                        "item_code": rm_items[0],
                        "operation": op_names[0],
                        "required_qty": qty,
                        "consumed_qty": 0.0,
                        "source_warehouse": self.wip_warehouse,
                    },
                    {
                        "item_code": rm_items[1],
                        "operation": op_names[1],
                        "required_qty": qty * 2,
                        "consumed_qty": 0.0,
                        "source_warehouse": self.wip_warehouse,
                    },
                    {
                        "item_code": rm_items[2],
                        "operation": op_names[2],
                        "required_qty": qty,
                        "consumed_qty": 0.0,
                        "source_warehouse": self.wip_warehouse,
                    },
                    {
                        "item_code": rm_items[3],
                        "operation": op_names[3],
                        "required_qty": qty,
                        "consumed_qty": 0.0,
                        "source_warehouse": self.wip_warehouse,
                    },
                ],
            }
        )
        wo.flags.ignore_permissions = True
        wo.flags.ignore_mandatory = True
        wo.flags.ignore_links = True
        wo.insert(ignore_permissions=True)
        wo.db_set("docstatus", 1)

        for idx, op in enumerate(op_names):
            jc_name = f"TEST-JC-4OP-{wo.name}-{idx + 1}"
            if frappe.db.exists("Job Card", jc_name):
                frappe.db.set_value(
                    "Job Card",
                    jc_name,
                    {
                        "work_order": wo.name,
                        "operation": op,
                        "docstatus": 0,
                        "status": "Open",
                        "total_completed_qty": 0.0,
                        "for_quantity": qty,
                    },
                )
            else:
                jc = frappe.get_doc(
                    {
                        "doctype": "Job Card",
                        "name": jc_name,
                        "work_order": wo.name,
                        "operation": op,
                        "workstation": self.ws_name,
                        "production_item": self.item,
                        "company": self.company,
                        "wip_warehouse": self.wip_warehouse,
                        "for_quantity": qty,
                        "total_completed_qty": 0.0,
                        "status": "Open",
                        "docstatus": 0,
                    }
                )
                jc.flags.ignore_permissions = True
                jc.flags.ignore_mandatory = True
                jc.flags.ignore_links = True
                jc.insert(ignore_permissions=True)

        frappe.db.commit()
        return wo

    def test_milestone_confirmation_auto_catchup_preceding_operations(self):
        """4-operation Work Order auto-catchup test:

        Confirming 8 units on milestone (Op 4) when Op 1 had only 5 units confirmed
        automatically catches up preceding operations (Op 1, 2, 3) to 8 units, consumes
        the remaining deficit raw materials (e.g. 3 cable), and produces 8 finished goods
        without failing KTAStockEntry check_if_operations_completed.
        """
        prev_neg_stock = frappe.db.get_single_value(
            "Stock Settings", "allow_negative_stock"
        )
        frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)

        try:
            wo = self._create_4_op_work_order("TEST-WO-CATCHUP-001", qty=5000.0)

            # 1. Partial confirmation on Op 1: 5 units
            res1 = confirm_operation(
                {
                    "work_order": wo.name,
                    "operation": "0010 Kesim",
                    "yield_qty": 5.0,
                    "is_final_confirmation": 0,
                }
            )
            self.assertTrue(res1.get("success"))
            op1_completed = frappe.db.get_value(
                "Work Order Operation",
                {"parent": wo.name, "operation": "0010 Kesim"},
                "completed_qty",
            )
            self.assertEqual(flt(op1_completed), 5.0)

            # 2. Confirmation on Op 4 (Milestone): 8 units
            # Preceding ops had only 5.0 (Op 1) and 0.0 (Op 2, 3).
            # Auto-catchup should update all preceding ops to 8.0 and consume deficit materials.
            res2 = confirm_operation(
                {
                    "work_order": wo.name,
                    "operation": "0040 Test",
                    "yield_qty": 8.0,
                    "is_final_confirmation": 0,
                }
            )
            self.assertTrue(res2.get("success"))

            # 3. Verify Op 1 completed_qty is caught up to 8.0
            op1_after = frappe.db.get_value(
                "Work Order Operation",
                {"parent": wo.name, "operation": "0010 Kesim"},
                "completed_qty",
            )
            self.assertEqual(flt(op1_after), 8.0)

            # Verify Op 2 and Op 3 completed_qty are also caught up to 8.0
            for op in ["0020 Krimp", "0030 Montaj", "0040 Test"]:
                op_qty = frappe.db.get_value(
                    "Work Order Operation",
                    {"parent": wo.name, "operation": op},
                    "completed_qty",
                )
                self.assertEqual(flt(op_qty), 8.0)

            # 4. Verify consumption stock entry caught up remaining 3 cable for Op 1
            cons_se_name = res2.get("consumption_stock_entry")
            self.assertTrue(cons_se_name)
            cons_se = frappe.get_doc("Stock Entry", cons_se_name)
            self.assertEqual(cons_se.docstatus, 1)

            consumed_items = {d.item_code: flt(d.qty) for d in cons_se.items}
            # Cable: target 8 - already 5 = 3
            self.assertEqual(consumed_items.get("_TEST_RM_KABLO"), 3.0)
            # Terminal: target (8/5000)*10000 = 16 - already 0 = 16
            self.assertEqual(consumed_items.get("_TEST_RM_TERMINAL"), 16.0)
            # Connector: target (8/5000)*5000 = 8 - already 0 = 8
            self.assertEqual(consumed_items.get("_TEST_RM_KONNEKTOR"), 8.0)
            # Label (Op 4): (8/5000)*5000 = 8
            self.assertEqual(consumed_items.get("_TEST_RM_ETIKET"), 8.0)

            # 5. Verify finished goods entry produced 8 units
            fg_se_name = res2.get("stock_entry")
            self.assertTrue(fg_se_name)
            fg_se = frappe.get_doc("Stock Entry", fg_se_name)
            self.assertEqual(fg_se.docstatus, 1)
            self.assertEqual(fg_se.purpose, "Manufacture")
            self.assertEqual(flt(fg_se.fg_completed_qty), 8.0)

            # Work Order produced_qty is updated to 8.0
            wo_produced = frappe.db.get_value("Work Order", wo.name, "produced_qty")
            self.assertEqual(flt(wo_produced), 8.0)

            # 6. Verify ConfirmationService.get_operation_quantities and get_shopfloor_hub_context
            for op in ["0010 Kesim", "0020 Krimp", "0030 Montaj", "0040 Test"]:
                op_qtys = ConfirmationService.get_operation_quantities(wo.name, op)
                self.assertEqual(flt(op_qtys["completed_qty"]), 8.0)

            ctx = get_shopfloor_hub_context(wo.name)
            for op_data in ctx["operations"]:
                self.assertEqual(flt(op_data["completed_qty"]), 8.0)

            # 7. Verify catchup confirmation documents created and linked to consumption stock entry
            catchup_confs = res2.get("catchup_confirmations") or []
            self.assertEqual(len(catchup_confs), 3)
            # Catchup confirmations must be created in chronological sequence BEFORE milestone
            self.assertLess(catchup_confs[0], catchup_confs[1])
            self.assertLess(catchup_confs[1], catchup_confs[2])
            self.assertLess(catchup_confs[2], res2["confirmation"])

            for c_name in catchup_confs:
                c_doc = frappe.get_doc("KTA Production Confirmation", c_name)
                self.assertEqual(c_doc.docstatus, 1)
                self.assertEqual(c_doc.stock_entry, cons_se_name)
                self.assertEqual(c_doc.milestone_confirmation, res2["confirmation"])
                self.assertLess(c_doc.name, res2["confirmation"])

            # 8. Reversal test: cancel milestone confirmation
            cancel_res = ReversalService.cancel_confirmation(
                res2["confirmation"], user="Administrator"
            )
            self.assertTrue(cancel_res.get("success"))

            # Op 1 should roll back to initial 5.0
            op1_reverted = ConfirmationService.get_operation_quantities(
                wo.name, "0010 Kesim"
            )
            self.assertEqual(flt(op1_reverted["completed_qty"]), 5.0)

            # Op 2, 3, 4 should roll back to 0.0
            for op in ["0020 Krimp", "0030 Montaj", "0040 Test"]:
                op_reverted = ConfirmationService.get_operation_quantities(wo.name, op)
                self.assertEqual(flt(op_reverted["completed_qty"]), 0.0)

            # Shopfloor Hub context reflects reverted quantities
            ctx_reverted = get_shopfloor_hub_context(wo.name)
            ctx_ops = {
                d["operation"]: flt(d["completed_qty"])
                for d in ctx_reverted["operations"]
            }
            self.assertEqual(ctx_ops.get("0010 Kesim"), 5.0)
            self.assertEqual(ctx_ops.get("0020 Krimp"), 0.0)
            self.assertEqual(ctx_ops.get("0030 Montaj"), 0.0)
            self.assertEqual(ctx_ops.get("0040 Test"), 0.0)

            # Catchup confirmations are cancelled (docstatus=2)
            for c_name in catchup_confs:
                self.assertEqual(
                    frappe.db.get_value(
                        "KTA Production Confirmation", c_name, "docstatus"
                    ),
                    2,
                )

            # Stock entries are cancelled (docstatus=2)
            self.assertEqual(
                frappe.db.get_value("Stock Entry", cons_se_name, "docstatus"), 2
            )
            self.assertEqual(
                frappe.db.get_value("Stock Entry", fg_se_name, "docstatus"), 2
            )

            # Work Order produced_qty reverted to 0.0
            self.assertEqual(
                flt(frappe.db.get_value("Work Order", wo.name, "produced_qty")), 0.0
            )

        finally:
            frappe.db.set_single_value(
                "Stock Settings", "allow_negative_stock", prev_neg_stock or 0
            )

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
    )
    def test_two_operation_milestone_catchup_and_reversal(
        self, mock_fg_entry, mock_consumption_entry
    ):
        """User scenario: 2-operation WO (Op 1 & Op 2).

        Op 1 confirmed with 5 units.
        Op 2 (milestone) confirmed with 6 units.
        Verifies:
        1. Op 1 gets a catchup confirmation of 1 unit.
        2. get_operation_quantities and get_shopfloor_hub_context return 6.0 for Op 1.
        3. Both confirmations link to stock entry.
        4. Reversing Op 2 cancels catchup confirmation and reverts Op 1 to 5.0.
        """
        mock_consumption_entry.return_value = "STE-CONS-TWO-OP"
        mock_fg_entry.return_value = "STE-FG-TWO-OP"

        # 1. Partial confirmation on Op 1: 5 units
        res1 = confirm_operation(
            {
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 5.0,
                "is_final_confirmation": 0,
            }
        )
        self.assertTrue(res1.get("success"))
        qtys1 = ConfirmationService.get_operation_quantities(self.wo_name, self.op1)
        self.assertEqual(flt(qtys1["completed_qty"]), 5.0)

        # 2. Confirmation on Op 2 (Milestone): 6 units
        res2 = confirm_operation(
            {
                "work_order": self.wo_name,
                "operation": self.op2,
                "job_card": self.jc2,
                "yield_qty": 6.0,
                "is_final_confirmation": 0,
            }
        )
        self.assertTrue(res2.get("success"))

        # Verify catchup confirmation was created for Op 1
        catchups = res2.get("catchup_confirmations") or []
        self.assertEqual(len(catchups), 1)
        catchup_doc = frappe.get_doc("KTA Production Confirmation", catchups[0])
        self.assertEqual(catchup_doc.operation, self.op1)
        self.assertEqual(flt(catchup_doc.yield_qty), 1.0)
        self.assertEqual(catchup_doc.docstatus, 1)
        self.assertEqual(catchup_doc.stock_entry, "STE-CONS-TWO-OP")
        self.assertEqual(catchup_doc.milestone_confirmation, res2["confirmation"])
        # Catchup confirmation must precede milestone confirmation chronologically
        self.assertLess(catchup_doc.name, res2["confirmation"])

        # Verify Op 1 completed_qty is 6.0 in get_operation_quantities
        qtys_after = ConfirmationService.get_operation_quantities(
            self.wo_name, self.op1
        )
        self.assertEqual(flt(qtys_after["completed_qty"]), 6.0)

        # Verify Op 1 completed_qty is 6.0 in get_shopfloor_hub_context
        ctx = get_shopfloor_hub_context(self.wo_name)
        ctx_ops = {d["operation"]: flt(d["completed_qty"]) for d in ctx["operations"]}
        self.assertEqual(ctx_ops.get(self.op1), 6.0)
        self.assertEqual(ctx_ops.get(self.op2), 6.0)

        # 3. Reversal: Cancel milestone confirmation
        cancel_res = ReversalService.cancel_confirmation(
            res2["confirmation"], user="Administrator"
        )
        self.assertTrue(cancel_res.get("success"))

        # Verify catchup confirmation is cancelled
        self.assertEqual(
            frappe.db.get_value(
                "KTA Production Confirmation", catchups[0], "docstatus"
            ),
            2,
        )

        # Op 1 rolls back to 5.0 in get_operation_quantities and get_shopfloor_hub_context
        qtys_rev = ConfirmationService.get_operation_quantities(self.wo_name, self.op1)
        self.assertEqual(flt(qtys_rev["completed_qty"]), 5.0)

        ctx_rev = get_shopfloor_hub_context(self.wo_name)
        ctx_rev_ops = {
            d["operation"]: flt(d["completed_qty"]) for d in ctx_rev["operations"]
        }
        self.assertEqual(ctx_rev_ops.get(self.op1), 5.0)
        self.assertEqual(ctx_rev_ops.get(self.op2), 0.0)

    def _create_legacy_work_order(
        self, qty: float = 5000.0, legacy_mfg_qty: float = 720.0
    ) -> str:
        wo = frappe.get_doc(
            {
                "doctype": "Work Order",
                "naming_series": "MFG-WO-.YYYY.-",
                "production_item": self.item,
                "qty": qty,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "fg_warehouse": getattr(self.wo, "fg_warehouse", self.wip_warehouse),
                "status": "In Process",
                "produced_qty": legacy_mfg_qty,
                "operations": [
                    {
                        "operation": self.op1,
                        "workstation": self.ws_name,
                        "sequence_id": 1,
                        "idx": 1,
                        "completed_qty": qty,
                        "status": "Completed",
                        "time_in_mins": 60.0,
                    }
                ],
            }
        )
        wo.flags.ignore_permissions = True
        wo.flags.ignore_mandatory = True
        wo.insert(ignore_permissions=True)
        frappe.db.set_value("Work Order", wo.name, "docstatus", 1)

        # Legacy Job Card submitted for full qty (docstatus=1)
        jc = frappe.get_doc(
            {
                "doctype": "Job Card",
                "work_order": wo.name,
                "operation": self.op1,
                "workstation": self.ws_name,
                "production_item": self.item,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "for_quantity": qty,
                "total_completed_qty": qty,
                "process_loss_qty": 0.0,
                "status": "Completed",
                "docstatus": 0,
            }
        )
        jc.flags.ignore_permissions = True
        jc.flags.ignore_mandatory = True
        jc.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Job Card", jc.name, {"docstatus": 1, "status": "Completed"}
        )

        # Create legacy Stock Entry (Manufacture) of 720 units (not tied to any KTA Production Confirmation)
        se_name = f"TEST-SE-LEGACY-{frappe.generate_hash(length=6)}"
        frappe.db.sql(
            """
            INSERT INTO `tabStock Entry` (
                name, docstatus, purpose, stock_entry_type, work_order, company,
                fg_completed_qty, creation, modified, modified_by
            ) VALUES (%s, 1, 'Manufacture', 'Manufacture', %s, %s, %s, NOW(), NOW(), 'Administrator')
            """,
            (se_name, wo.name, self.company, legacy_mfg_qty),
        )
        frappe.db.commit()
        return wo.name

    def test_legacy_work_order_operation_quantities_normalization(self):
        """Legacy Work Order with 5000 qty and artificial completed_qty=5000 normalizes to 720."""
        legacy_wo = self._create_legacy_work_order(qty=5000.0, legacy_mfg_qty=720.0)

        # Check raw DB state has artificial 5000 before calculation
        initial_db_qty = frappe.db.get_value(
            "Work Order Operation",
            {"parent": legacy_wo, "operation": self.op1},
            "completed_qty",
        )
        self.assertEqual(flt(initial_db_qty), 5000.0)

        # ConfirmationService.get_operation_quantities computes normalized quantities
        qtys = ConfirmationService.get_operation_quantities(legacy_wo, self.op1)
        self.assertEqual(qtys["completed_qty"], 720.0)
        self.assertEqual(qtys["pending_qty"], 4280.0)
        self.assertEqual(qtys["status"], "Work In Progress")
        self.assertEqual(qtys["legacy_manufacture_qty"], 720.0)
        self.assertEqual(qtys["co11n_qty"], 0.0)

    def test_legacy_work_order_subsequent_confirmation(self):
        """Confirming 100 units on a legacy Work Order accumulates to 720 + 100 = 820."""
        legacy_wo = self._create_legacy_work_order(qty=5000.0, legacy_mfg_qty=720.0)

        with patch(
            "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
        ) as mock_se:
            mock_se.return_value = None
            res = confirm_operation(
                {
                    "work_order": legacy_wo,
                    "operation": self.op1,
                    "yield_qty": 100.0,
                    "is_final_confirmation": 0,
                }
            )
            self.assertTrue(res.get("success"))

        qtys = ConfirmationService.get_operation_quantities(legacy_wo, self.op1)
        self.assertEqual(qtys["completed_qty"], 820.0)
        self.assertEqual(qtys["pending_qty"], 4180.0)
        self.assertEqual(qtys["status"], "Work In Progress")
        self.assertEqual(qtys["legacy_manufacture_qty"], 720.0)
        self.assertEqual(qtys["co11n_qty"], 100.0)

        # Work Order Operation table has been updated to 820.0
        db_completed = frappe.db.get_value(
            "Work Order Operation",
            {"parent": legacy_wo, "operation": self.op1},
            "completed_qty",
        )
        self.assertEqual(flt(db_completed), 820.0)

    def test_legacy_work_order_reversal(self):
        """Cancelling the 100-unit confirmation rolls back completed_qty to 720 and pending_qty to 4280."""
        legacy_wo = self._create_legacy_work_order(qty=5000.0, legacy_mfg_qty=720.0)

        with patch(
            "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
        ) as mock_se:
            mock_se.return_value = None
            res = confirm_operation(
                {
                    "work_order": legacy_wo,
                    "operation": self.op1,
                    "yield_qty": 100.0,
                    "is_final_confirmation": 0,
                }
            )
            self.assertTrue(res.get("success"))
            conf_name = res["confirmation"]

        # Cancel confirmation
        cancel_res = ReversalService.cancel_confirmation(
            conf_name, user="Administrator"
        )
        self.assertTrue(cancel_res.get("success"))

        qtys = ConfirmationService.get_operation_quantities(legacy_wo, self.op1)
        self.assertEqual(qtys["completed_qty"], 720.0)
        self.assertEqual(qtys["pending_qty"], 4280.0)
        self.assertEqual(qtys["status"], "Work In Progress")
        self.assertEqual(qtys["legacy_manufacture_qty"], 720.0)
        self.assertEqual(qtys["co11n_qty"], 0.0)

        db_completed = frappe.db.get_value(
            "Work Order Operation",
            {"parent": legacy_wo, "operation": self.op1},
            "completed_qty",
        )
        self.assertEqual(flt(db_completed), 720.0)
