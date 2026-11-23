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
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    KTATestCase,
    create_test_company,
    create_test_erpnext_operation,
    create_test_item_group,
    create_test_warehouse,
    create_test_workstation,
)


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


class TestShopfloorPartialManufactureCostingE2E(KTABaseTestCase):
    """Unmocked E2E tests for Shopfloor partial Manufacture, consumption pool costing,
    legacy Work Order continuation, ahead-of-schedule op isolation, short close, and CORS reversal.
    """

    def setUp(self):
        super().setUp()
        orig_material_consumption = frappe.db.get_single_value(
            "Manufacturing Settings", "material_consumption"
        )
        orig_get_rm_cost = frappe.db.get_single_value(
            "Manufacturing Settings", "get_rm_cost_from_consumption_entry"
        )
        orig_make_batch_from_wo = frappe.db.get_single_value(
            "Manufacturing Settings", "make_serial_no_batch_from_work_order"
        )
        orig_neg_stock = frappe.db.get_single_value(
            "Stock Settings", "allow_negative_stock"
        )

        self.addCleanup(
            frappe.db.set_single_value,
            "Manufacturing Settings",
            {
                "material_consumption": orig_material_consumption,
                "get_rm_cost_from_consumption_entry": orig_get_rm_cost,
                "make_serial_no_batch_from_work_order": orig_make_batch_from_wo,
            },
        )
        self.addCleanup(
            frappe.db.set_single_value,
            "Stock Settings",
            "allow_negative_stock",
            orig_neg_stock or 0,
        )

        frappe.db.set_single_value(
            "Manufacturing Settings",
            {
                "material_consumption": 1,
                "get_rm_cost_from_consumption_entry": 1,
                "make_serial_no_batch_from_work_order": 0,
            },
        )
        frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 0)

        self.company = create_test_company()
        self.item_group = create_test_item_group()
        self.src_warehouse = create_test_warehouse(self.company, "_Test SF E2E Source")
        self.wip_warehouse = create_test_warehouse(self.company, "_Test SF E2E WIP")
        self.fg_warehouse = create_test_warehouse(self.company, "_Test SF E2E FG")
        self.workstation = create_test_workstation("_Test SF E2E Workstation")
        frappe.db.set_value("Workstation", self.workstation, "hour_rate", 0.0)
        self.op_10 = create_test_erpnext_operation("0010 Kesim", self.workstation)
        self.op_20 = create_test_erpnext_operation("0020 Krimp", self.workstation)
        self.op_30 = create_test_erpnext_operation("0030 Test", self.workstation)
        self._tag = frappe.generate_hash(length=6)

    def _make_stock_item(
        self, label: str, valuation_method: str = "Moving Average"
    ) -> str:
        code = f"_Test SFE2E {label} {self._tag}"
        doc = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": code,
                "item_name": code,
                "item_group": self.item_group,
                "is_stock_item": 1,
                "stock_uom": "Nos",
                "has_batch_no": 0,
                "has_serial_no": 0,
                "valuation_method": valuation_method,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _receive_stock(
        self, item_code: str, qty: float, rate: float, warehouse: str | None = None
    ):
        wh = warehouse or self.src_warehouse
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = "Material Receipt"
        se.company = self.company
        se.to_warehouse = wh
        se.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": wh,
                "basic_rate": rate,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_bom(
        self, fg_item: str, raw_items_spec: list[dict], operations: list[str]
    ):
        currency = (
            frappe.db.get_value("Company", self.company, "default_currency") or "TRY"
        )
        bom = frappe.new_doc("BOM")
        bom.item = fg_item
        bom.quantity = 1.0
        bom.company = self.company
        bom.currency = currency
        bom.conversion_rate = 1.0
        bom.rm_cost_as_per = "Valuation Rate"
        bom.with_operations = 1
        bom.inspection_required = 0
        for op in operations:
            bom.append(
                "operations",
                {
                    "operation": op,
                    "workstation": self.workstation,
                    "time_in_mins": 10,
                    "hour_rate": 0.0,
                },
            )
        for spec in raw_items_spec:
            bom.append(
                "items",
                {
                    "item_code": spec["item_code"],
                    "qty": spec["qty"],
                    "uom": "Nos",
                    "stock_uom": "Nos",
                    "rate": spec["rate"],
                    "operation": spec.get("operation"),
                    "source_warehouse": self.src_warehouse,
                },
            )
        bom.insert(ignore_permissions=True)
        bom.submit()
        return bom

    def _create_work_order(self, fg_item: str, bom_no: str, qty: float = 1000.0):
        wo = frappe.new_doc("Work Order")
        wo.production_item = fg_item
        wo.bom_no = bom_no
        wo.qty = qty
        wo.company = self.company
        wo.source_warehouse = self.src_warehouse
        wo.wip_warehouse = self.wip_warehouse
        wo.fg_warehouse = self.fg_warehouse
        wo.use_multi_level_bom = 0
        wo.skip_transfer = 1
        wo.set_work_order_operations()
        wo.set_required_items()
        for row in wo.required_items:
            row.source_warehouse = self.src_warehouse
        wo.insert(ignore_permissions=True)
        wo.submit()
        return wo

    def _get_wo_stock_entries(
        self, wo_name: str, purpose: str, docstatus: int = 1
    ) -> list:
        names = frappe.get_all(
            "Stock Entry",
            filters={
                "work_order": wo_name,
                "purpose": purpose,
                "docstatus": docstatus,
            },
            order_by="creation asc",
            pluck="name",
        )
        return [frappe.get_doc("Stock Entry", name) for name in names]

    def test_e2e_multiple_partial_manufacture_costing_300_300_400(self):
        """Scenario 1: Unmocked 300 + 300 + Final 400 confirmations produce 3 consumption
        and 3 Manufacture entries at actual RM rate without batch cost inflation.
        """
        fg_item = self._make_stock_item("FG-MULTI")
        rm1 = self._make_stock_item("RM1-MULTI")
        rm2 = self._make_stock_item("RM2-MULTI")
        rm3 = self._make_stock_item("RM3-MULTI")

        # Initial receipt before BOM (BOM captures RM1=10.0, RM2=5.0, RM3=6.0 -> BOM cost = 26.0)
        self._receive_stock(rm1, 500.0, 10.0)
        self._receive_stock(rm2, 2000.0, 5.0)
        self._receive_stock(rm3, 1000.0, 6.0)

        bom = self._create_bom(
            fg_item,
            [
                {"item_code": rm1, "qty": 1.0, "rate": 10.0, "operation": self.op_10},
                {"item_code": rm2, "qty": 2.0, "rate": 5.0, "operation": self.op_20},
                {"item_code": rm3, "qty": 1.0, "rate": 6.0, "operation": self.op_30},
            ],
            [self.op_10, self.op_20, self.op_30],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        # Second receipt after BOM: Moving Average RM1 = (500*10 + 500*18)/1000 = 14.0
        # Actual FG unit cost = 1*14.0 + 2*5.0 + 1*6.0 = 30.0 (!= BOM 26.0)
        self._receive_stock(rm1, 500.0, 18.0)

        batches = [
            (300.0, 0),
            (300.0, 0),
            (400.0, 1),
        ]
        mfg_docs = []
        cons_docs = []

        for batch_qty, is_final in batches:
            res = ConfirmationService.confirm_operation(
                {
                    "work_order": wo.name,
                    "operation": self.op_30,
                    "yield_qty": batch_qty,
                    "is_final_confirmation": is_final,
                }
            )
            self.assertTrue(res.get("success"))
            self.assertTrue(res.get("consumption_stock_entry"))
            self.assertTrue(res.get("stock_entry"))

            cons_se = frappe.get_doc("Stock Entry", res["consumption_stock_entry"])
            mfg_se = frappe.get_doc("Stock Entry", res["stock_entry"])
            self.assertEqual(cons_se.docstatus, 1)
            self.assertEqual(mfg_se.docstatus, 1)

            fg_rows = [d for d in mfg_se.items if d.is_finished_item]
            rm_rows = [
                d
                for d in mfg_se.items
                if not d.is_finished_item and not d.is_scrap_item
            ]
            self.assertEqual(len(fg_rows), 1)
            self.assertEqual(rm_rows, [])
            self.assertAlmostEqual(flt(fg_rows[0].basic_rate), 30.0, places=2)
            self.assertAlmostEqual(
                flt(fg_rows[0].basic_amount), batch_qty * 30.0, places=2
            )

            cons_docs.append(cons_se)
            mfg_docs.append(mfg_se)

        self.assertEqual(
            len(
                self._get_wo_stock_entries(
                    wo.name, "Material Consumption for Manufacture"
                )
            ),
            3,
        )
        self.assertEqual(
            len(self._get_wo_stock_entries(wo.name, "Manufacture")),
            3,
        )

        sum_mfg_basic_amount = sum(
            flt(d.basic_amount)
            for mfg in mfg_docs
            for d in mfg.items
            if d.is_finished_item
        )
        sum_cons_outgoing_value = sum(
            flt(cons.total_outgoing_value) for cons in cons_docs
        )
        self.assertLessEqual(abs(sum_mfg_basic_amount - sum_cons_outgoing_value), 0.01)
        self.assertAlmostEqual(sum_mfg_basic_amount, 30000.0, places=2)

        wo.reload()
        self.assertEqual(flt(wo.produced_qty), 1000.0)
        self.assertEqual(wo.status, "Completed")

        for jc_docstatus in frappe.get_all(
            "Job Card", filters={"work_order": wo.name}, pluck="docstatus"
        ):
            self.assertEqual(jc_docstatus, 0)

    def test_e2e_legacy_manufacture_followed_by_shopfloor_partial_and_final(self):
        """Scenario 2: Legacy RM-bearing Manufacture (300) followed by Shopfloor Hub
        confirmations (300 partial + 400 final) succeeds without 'Only one Manufacture entry',
        isolates legacy cost from the consumption pool, and balances FG-only vs Consumption.
        """
        fg_item = self._make_stock_item("FG-LEGACY")
        rm1 = self._make_stock_item("RM1-LEGACY")
        rm2 = self._make_stock_item("RM2-LEGACY")
        rm3 = self._make_stock_item("RM3-LEGACY")

        # Initial stock for legacy Manufacture (300 FG @ 26.0 = 7,800.0)
        self._receive_stock(rm1, 300.0, 10.0)
        self._receive_stock(rm2, 2000.0, 5.0)
        self._receive_stock(rm3, 1000.0, 6.0)

        bom = self._create_bom(
            fg_item,
            [
                {"item_code": rm1, "qty": 1.0, "rate": 10.0, "operation": self.op_10},
                {"item_code": rm2, "qty": 2.0, "rate": 5.0, "operation": self.op_20},
                {"item_code": rm3, "qty": 1.0, "rate": 6.0, "operation": self.op_30},
            ],
            [self.op_10, self.op_20, self.op_30],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        # 1. Submit legacy standard Manufacture entry for 300 units with operations completed_qty=300
        for op_row in wo.operations:
            frappe.db.set_value(
                "Work Order Operation",
                op_row.name,
                {"completed_qty": 300.0, "status": "Work In Progress"},
            )

        legacy_mfg = frappe.new_doc("Stock Entry")
        legacy_mfg.purpose = "Manufacture"
        legacy_mfg.stock_entry_type = "Manufacture"
        legacy_mfg.work_order = wo.name
        legacy_mfg.company = self.company
        legacy_mfg.from_bom = 1
        legacy_mfg.bom_no = bom.name
        legacy_mfg.fg_completed_qty = 300.0
        legacy_mfg.from_warehouse = self.src_warehouse
        legacy_mfg.to_warehouse = self.fg_warehouse
        for item_code, qty in ((rm1, 300.0), (rm2, 600.0), (rm3, 300.0)):
            legacy_mfg.append(
                "items",
                {
                    "item_code": item_code,
                    "qty": qty,
                    "uom": "Nos",
                    "stock_uom": "Nos",
                    "conversion_factor": 1.0,
                    "s_warehouse": self.src_warehouse,
                },
            )
        legacy_mfg.append(
            "items",
            {
                "item_code": fg_item,
                "qty": 300.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.fg_warehouse,
                "is_finished_item": 1,
            },
        )
        legacy_mfg.insert(ignore_permissions=True)
        legacy_mfg.submit()
        self.assertEqual(legacy_mfg.docstatus, 1)
        self.assertAlmostEqual(flt(legacy_mfg.total_outgoing_value), 7800.0, places=2)

        # Replenish RM1 at a higher rate (22.0) for subsequent Shopfloor Hub batches
        # New actual FG unit cost = 1*22.0 + 2*5.0 + 1*6.0 = 38.0 (!= legacy 26.0)
        self._receive_stock(rm1, 700.0, 22.0)

        # 2. Continue via Shopfloor Hub: 300 partial, then 400 final
        cons_docs = []
        fg_only_docs = []
        for batch_qty, is_final in ((300.0, 0), (400.0, 1)):
            res = ConfirmationService.confirm_operation(
                {
                    "work_order": wo.name,
                    "operation": self.op_30,
                    "yield_qty": batch_qty,
                    "is_final_confirmation": is_final,
                }
            )
            self.assertTrue(res.get("success"))
            cons_se = frappe.get_doc("Stock Entry", res["consumption_stock_entry"])
            mfg_se = frappe.get_doc("Stock Entry", res["stock_entry"])
            self.assertEqual(cons_se.docstatus, 1)
            self.assertEqual(mfg_se.docstatus, 1)

            fg_rows = [d for d in mfg_se.items if d.is_finished_item]
            rm_rows = [
                d
                for d in mfg_se.items
                if not d.is_finished_item and not d.is_scrap_item
            ]
            self.assertEqual(len(fg_rows), 1)
            self.assertEqual(rm_rows, [])
            self.assertAlmostEqual(flt(fg_rows[0].basic_rate), 38.0, places=2)
            self.assertAlmostEqual(
                flt(fg_rows[0].basic_amount), batch_qty * 38.0, places=2
            )

            cons_docs.append(cons_se)
            fg_only_docs.append(mfg_se)

        sum_fg_only_amount = sum(
            flt(d.basic_amount)
            for mfg in fg_only_docs
            for d in mfg.items
            if d.is_finished_item
        )
        sum_cons_outgoing = sum(flt(cons.total_outgoing_value) for cons in cons_docs)
        self.assertAlmostEqual(sum_fg_only_amount, sum_cons_outgoing, places=2)
        self.assertAlmostEqual(sum_fg_only_amount, 26600.0, places=2)

        wo.reload()
        self.assertEqual(flt(wo.produced_qty), 1000.0)
        self.assertEqual(wo.status, "Completed")

    def test_e2e_ahead_of_schedule_intermediate_op_cost_isolation(self):
        """Scenario 3: OP10 consumes all 1000 units ahead of OP30 (300 then 700 final).
        The 300-unit Manufacture only absorbs 300 units' share of OP10 cost, and the
        final 700-unit Manufacture closes the remaining pool exactly.
        """
        fg_item = self._make_stock_item("FG-AHEAD")
        rm_op1 = self._make_stock_item("RM1-AHEAD")
        rm_op2 = self._make_stock_item("RM2-AHEAD")
        rm_op3 = self._make_stock_item("RM3-AHEAD")

        self._receive_stock(rm_op1, 1000.0, 10.0)
        self._receive_stock(rm_op2, 1000.0, 15.0)
        self._receive_stock(rm_op3, 1000.0, 25.0)

        bom = self._create_bom(
            fg_item,
            [
                {
                    "item_code": rm_op1,
                    "qty": 1.0,
                    "rate": 10.0,
                    "operation": self.op_10,
                },
                {
                    "item_code": rm_op2,
                    "qty": 1.0,
                    "rate": 15.0,
                    "operation": self.op_20,
                },
                {
                    "item_code": rm_op3,
                    "qty": 1.0,
                    "rate": 25.0,
                    "operation": self.op_30,
                },
            ],
            [self.op_10, self.op_20, self.op_30],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        # 1. OP10 confirms and consumes all 1000 units ahead of schedule (10,000.0)
        res_op1 = ConfirmationService.confirm_operation(
            {
                "work_order": wo.name,
                "operation": self.op_10,
                "yield_qty": 1000.0,
                "is_final_confirmation": 1,
            }
        )
        self.assertTrue(res_op1.get("success"))
        cons_op1 = frappe.get_doc("Stock Entry", res_op1["consumption_stock_entry"])
        self.assertEqual(cons_op1.docstatus, 1)
        self.assertAlmostEqual(flt(cons_op1.total_outgoing_value), 10000.0, places=2)
        self.assertEqual(len(self._get_wo_stock_entries(wo.name, "Manufacture")), 0)

        # 2. OP30 (milestone) confirms 300 partial -> should absorb 300*(10+15+25) = 15,000.0
        res_op3_p1 = ConfirmationService.confirm_operation(
            {
                "work_order": wo.name,
                "operation": self.op_30,
                "yield_qty": 300.0,
                "is_final_confirmation": 0,
            }
        )
        self.assertTrue(res_op3_p1.get("success"))
        cons_p1 = frappe.get_doc("Stock Entry", res_op3_p1["consumption_stock_entry"])
        mfg_p1 = frappe.get_doc("Stock Entry", res_op3_p1["stock_entry"])

        fg_row_1 = next(d for d in mfg_p1.items if d.is_finished_item)
        self.assertAlmostEqual(flt(fg_row_1.basic_rate), 50.0, places=2)
        self.assertAlmostEqual(flt(fg_row_1.basic_amount), 15000.0, places=2)

        # 3. OP30 (milestone) confirms remaining 700 final -> closes remaining 35,000.0
        res_op3_p2 = ConfirmationService.confirm_operation(
            {
                "work_order": wo.name,
                "operation": self.op_30,
                "yield_qty": 700.0,
                "is_final_confirmation": 1,
            }
        )
        self.assertTrue(res_op3_p2.get("success"))
        cons_p2 = frappe.get_doc("Stock Entry", res_op3_p2["consumption_stock_entry"])
        mfg_p2 = frappe.get_doc("Stock Entry", res_op3_p2["stock_entry"])

        fg_row_2 = next(d for d in mfg_p2.items if d.is_finished_item)
        self.assertAlmostEqual(flt(fg_row_2.basic_rate), 50.0, places=2)
        self.assertAlmostEqual(flt(fg_row_2.basic_amount), 35000.0, places=2)

        sum_mfg = flt(fg_row_1.basic_amount) + flt(fg_row_2.basic_amount)
        sum_cons = (
            flt(cons_op1.total_outgoing_value)
            + flt(cons_p1.total_outgoing_value)
            + flt(cons_p2.total_outgoing_value)
        )
        self.assertAlmostEqual(sum_mfg, sum_cons, places=2)
        self.assertAlmostEqual(sum_mfg, 50000.0, places=2)

        wo.reload()
        self.assertEqual(flt(wo.produced_qty), 1000.0)
        self.assertEqual(wo.status, "Completed")

    def test_e2e_short_close_reversal_and_reconfirmation(self):
        """Scenario 4: Partial 300 -> short-close 500 (is_final=1, total 800 < 1000) ->
        CORS cancel of conf2 -> re-confirm 600 (is_final=1, total 900 < 1000), ensuring
        cancelled entries (docstatus=2) never pollute the cost pool.
        """
        fg_item = self._make_stock_item("FG-SHORT-CORS")
        rm1 = self._make_stock_item("RM1-SHORT-CORS")
        rm2 = self._make_stock_item("RM2-SHORT-CORS")
        rm3 = self._make_stock_item("RM3-SHORT-CORS")

        self._receive_stock(rm1, 1000.0, 10.0)
        self._receive_stock(rm2, 1000.0, 15.0)
        self._receive_stock(rm3, 1000.0, 25.0)

        bom = self._create_bom(
            fg_item,
            [
                {"item_code": rm1, "qty": 1.0, "rate": 10.0, "operation": self.op_10},
                {"item_code": rm2, "qty": 1.0, "rate": 15.0, "operation": self.op_20},
                {"item_code": rm3, "qty": 1.0, "rate": 25.0, "operation": self.op_30},
            ],
            [self.op_10, self.op_20, self.op_30],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        # 1. Partial confirmation: 300 units on 0030 Test
        res1 = ConfirmationService.confirm_operation(
            {
                "work_order": wo.name,
                "operation": self.op_30,
                "yield_qty": 300.0,
                "is_final_confirmation": 0,
            }
        )
        self.assertTrue(res1.get("success"))
        cons1 = frappe.get_doc("Stock Entry", res1["consumption_stock_entry"])
        mfg1 = frappe.get_doc("Stock Entry", res1["stock_entry"])
        mfg1_fg = next(d for d in mfg1.items if d.is_finished_item)
        self.assertAlmostEqual(flt(mfg1_fg.basic_rate), 50.0, places=2)
        self.assertAlmostEqual(flt(mfg1_fg.basic_amount), 15000.0, places=2)

        # 2. Short close: 500 units with is_final_confirmation=1 (produced=800 < 1000)
        res2 = ConfirmationService.confirm_operation(
            {
                "work_order": wo.name,
                "operation": self.op_30,
                "yield_qty": 500.0,
                "is_final_confirmation": 1,
            }
        )
        self.assertTrue(res2.get("success"))
        conf2_name = res2["confirmation"]
        cons2 = frappe.get_doc("Stock Entry", res2["consumption_stock_entry"])
        mfg2 = frappe.get_doc("Stock Entry", res2["stock_entry"])
        mfg2_fg = next(d for d in mfg2.items if d.is_finished_item)

        # All remaining 700 recipe units (35,000.0) consumed and absorbed into 500 FG (70.0/unit)
        self.assertAlmostEqual(flt(cons2.total_outgoing_value), 35000.0, places=2)
        self.assertAlmostEqual(flt(mfg2_fg.basic_rate), 70.0, places=2)
        self.assertAlmostEqual(flt(mfg2_fg.basic_amount), 35000.0, places=2)

        sum_mfg_before_cancel = flt(mfg1_fg.basic_amount) + flt(mfg2_fg.basic_amount)
        sum_cons_before_cancel = flt(cons1.total_outgoing_value) + flt(
            cons2.total_outgoing_value
        )
        self.assertAlmostEqual(sum_mfg_before_cancel, sum_cons_before_cancel, places=2)

        wo.reload()
        self.assertEqual(flt(wo.produced_qty), 800.0)
        self.assertEqual(wo.status, "Completed")

        # 3. CORS cancel conf2
        cancel_res = ReversalService.cancel_confirmation(
            conf2_name, user="Administrator"
        )
        self.assertTrue(cancel_res.get("success"))

        self.assertEqual(
            frappe.db.get_value("KTA Production Confirmation", conf2_name, "docstatus"),
            2,
        )
        self.assertEqual(frappe.db.get_value("Stock Entry", mfg2.name, "docstatus"), 2)
        self.assertEqual(frappe.db.get_value("Stock Entry", cons2.name, "docstatus"), 2)

        wo.reload()
        self.assertEqual(flt(wo.produced_qty), 300.0)
        self.assertEqual(wo.status, "In Process")

        # 4. Re-confirm 600 units with is_final_confirmation=1 (produced=900 < 1000)
        res3 = ConfirmationService.confirm_operation(
            {
                "work_order": wo.name,
                "operation": self.op_30,
                "yield_qty": 600.0,
                "is_final_confirmation": 1,
            }
        )
        self.assertTrue(res3.get("success"))
        cons3 = frappe.get_doc("Stock Entry", res3["consumption_stock_entry"])
        mfg3 = frappe.get_doc("Stock Entry", res3["stock_entry"])
        mfg3_fg = next(d for d in mfg3.items if d.is_finished_item)

        self.assertEqual(cons3.docstatus, 1)
        self.assertEqual(mfg3.docstatus, 1)
        self.assertAlmostEqual(flt(cons3.total_outgoing_value), 35000.0, places=2)
        self.assertAlmostEqual(flt(mfg3_fg.basic_amount), 35000.0, places=2)

        active_mfg_docs = self._get_wo_stock_entries(
            wo.name, "Manufacture", docstatus=1
        )
        active_cons_docs = self._get_wo_stock_entries(
            wo.name, "Material Consumption for Manufacture", docstatus=1
        )
        self.assertEqual(len(active_mfg_docs), 2)
        self.assertEqual(len(active_cons_docs), 2)

        total_active_mfg = sum(
            flt(d.basic_amount)
            for se in active_mfg_docs
            for d in se.items
            if d.is_finished_item
        )
        total_active_cons = sum(flt(se.total_outgoing_value) for se in active_cons_docs)
        self.assertAlmostEqual(total_active_mfg, total_active_cons, places=2)
        self.assertAlmostEqual(total_active_mfg, 50000.0, places=2)

        wo.reload()
        self.assertEqual(flt(wo.produced_qty), 900.0)
        self.assertEqual(wo.status, "Completed")
