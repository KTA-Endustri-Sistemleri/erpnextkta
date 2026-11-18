# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.utils import flt

from erpnextkta.kta_shopfloor.services.confirmation_service import ConfirmationService
from erpnextkta.kta_shopfloor.services.reversal_service import (
    ReversalService,
    cancel_confirmation,
)
from erpnextkta.tests.test_utils import KTATestCase


class TestReversalService(KTATestCase):
    def setUp(self):
        super().setUp()
        self._setup_test_work_order_and_job_cards()

    def _setup_test_work_order_and_job_cards(self):
        """Prepare a Work Order with 2 operations and draft (docstatus=0) Job Cards."""
        self.op1 = "0010 Kesim"
        self.op2 = "0020 Test ve Montaj"

        for op in [self.op1, self.op2]:
            if not frappe.db.exists("Operation", op):
                frappe.get_doc(
                    {"doctype": "Operation", "name": op, "workstation": self.ws_name}
                ).insert(ignore_permissions=True)

        frappe.db.delete("Work Order Operation", {"parent": self.wo_name})
        frappe.db.delete("Stock Entry", {"work_order": self.wo_name})
        frappe.db.delete("KTA Production Confirmation", {"work_order": self.wo_name})
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

        self.jc1 = self._get_or_create_draft_job_card("TEST-JC-CORS-001", self.op1)
        self.jc2 = self._get_or_create_draft_job_card("TEST-JC-CORS-002", self.op2)
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

    def _create_mock_stock_entry(
        self, purpose: str, confirmation_name: str | None = None
    ) -> str:
        """Create and submit a mock stock entry for testing cancellation."""
        se_name = f"TEST-SE-{purpose[:3].upper()}-{frappe.generate_hash(length=6)}"
        remarks = (
            f"KTA Production Confirmation: {confirmation_name}"
            if confirmation_name
            else ""
        )
        frappe.db.sql(
            """
            INSERT INTO `tabStock Entry` (
                name, docstatus, purpose, stock_entry_type, work_order, company,
                remarks, creation, modified, modified_by
            ) VALUES (%s, 1, %s, %s, %s, %s, %s, NOW(), NOW(), 'Administrator')
            """,
            (se_name, purpose, purpose, self.wo_name, self.company, remarks),
        )
        frappe.db.commit()
        return se_name

    def test_permission_rejected_for_unauthorized_user(self):
        """Non-manager users must be rejected with frappe.PermissionError."""
        # Create a test confirmation
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 10.0,
                "is_final_confirmation": 0,
            }
        )
        conf.flags.ignore_permissions = True
        conf.insert(ignore_permissions=True)
        conf.submit()

        unauthorized_user = "test_unauthorized_operator@example.com"
        with (
            patch("frappe.get_roles", return_value=["Manufacturing User", "Guest"]),
            self.assertRaises(frappe.PermissionError),
        ):
            cancel_confirmation(conf.name, user=unauthorized_user)

    def test_cancel_intermediate_confirmation_rolls_back_quantities_and_cancels_stock_entry(
        self,
    ):
        """Intermediate operation reversal decrements JC and WO Operation, cancels linked Stock Entry."""
        with (
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
            ) as mock_consumption,
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
            ),
        ):
            mock_se = self._create_mock_stock_entry(
                "Material Consumption for Manufacture"
            )
            mock_consumption.return_value = mock_se

            # Perform confirmation of 25 units
            res = ConfirmationService.confirm_operation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op1,
                    "job_card": self.jc1,
                    "yield_qty": 25.0,
                }
            )
            conf_name = res["confirmation"]

        # Verify initial confirmation state
        jc = frappe.get_doc("Job Card", self.jc1)
        self.assertEqual(flt(jc.total_completed_qty), 25.0)

        # Cancel confirmation via ReversalService
        reversal_res = cancel_confirmation(conf_name, user="Administrator")
        self.assertTrue(reversal_res.get("success"))
        self.assertEqual(reversal_res.get("confirmation"), conf_name)

        # 1. Confirmation doc status must be Cancelled (2)
        conf_doc = frappe.get_doc("KTA Production Confirmation", conf_name)
        self.assertEqual(conf_doc.docstatus, 2)

        # 2. Linked Stock Entry docstatus must be Cancelled (2)
        se_doc = frappe.get_doc("Stock Entry", mock_se)
        self.assertEqual(se_doc.docstatus, 2)

        # 3. Job Card completed qty rolled back to 0.0, status reset to Open
        jc.reload()
        self.assertEqual(flt(jc.total_completed_qty), 0.0)
        self.assertEqual(jc.status, "Open")
        self.assertEqual(jc.docstatus, 0)

        # 4. Work Order Operation completed qty rolled back to 0.0
        wo = frappe.get_doc("Work Order", self.wo_name)
        op_row = next(d for d in wo.operations if d.operation == self.op1)
        self.assertEqual(flt(op_row.completed_qty), 0.0)

    def test_cancel_milestone_confirmation_rolls_back_wo_produced_qty_and_status(self):
        """Cancelling milestone confirmation rolls back Work Order produced_qty and resets status."""
        with (
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
            ) as mock_consumption,
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
            ) as mock_fg,
        ):
            mock_se_fg = self._create_mock_stock_entry("Manufacture")
            mock_fg.return_value = mock_se_fg
            mock_consumption.return_value = None

            res = ConfirmationService.confirm_operation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op2,  # milestone op
                    "job_card": self.jc2,
                    "yield_qty": 100.0,
                    "is_final_confirmation": 1,
                }
            )
            conf_name = res["confirmation"]

        # Confirm WO is completed
        wo = frappe.get_doc("Work Order", self.wo_name)
        self.assertEqual(wo.status, "Completed")
        self.assertEqual(flt(wo.produced_qty), 100.0)

        jc = frappe.get_doc("Job Card", self.jc2)
        self.assertEqual(jc.status, "Completed")
        self.assertEqual(flt(jc.total_completed_qty), 100.0)

        # Cancel confirmation
        reversal_res = ReversalService.cancel_confirmation(
            conf_name, user="Administrator"
        )
        self.assertTrue(reversal_res.get("success"))

        # Check WO produced_qty rolled back and status reset to In Process
        wo.reload()
        self.assertEqual(flt(wo.produced_qty), 0.0)
        self.assertIn(wo.status, ["In Process", "Not Started"])

        # Check Job Card rolled back
        jc.reload()
        self.assertEqual(flt(jc.total_completed_qty), 0.0)
        self.assertEqual(jc.status, "Open")
        self.assertEqual(jc.docstatus, 0)

        # Check confirmation cancelled
        conf_doc = frappe.get_doc("KTA Production Confirmation", conf_name)
        self.assertEqual(conf_doc.docstatus, 2)

    def test_cancel_fails_if_not_submitted(self):
        """Draft or already cancelled confirmation cannot be cancelled."""
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo_name,
                "operation": self.op1,
                "yield_qty": 10.0,
            }
        )
        conf.flags.ignore_permissions = True
        conf.insert(ignore_permissions=True)

        # Draft docstatus=0
        with self.assertRaises(frappe.ValidationError):
            cancel_confirmation(conf.name, user="Administrator")

        conf.submit()
        cancel_confirmation(conf.name, user="Administrator")

        # Already cancelled docstatus=2
        with self.assertRaises(frappe.ValidationError):
            cancel_confirmation(conf.name, user="Administrator")

    def test_atomic_rollback_on_failure(self):
        """If cancellation encounters error, changes are rolled back cleanly."""
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 15.0,
            }
        )
        conf.flags.ignore_permissions = True
        conf.insert(ignore_permissions=True)
        conf.submit()

        frappe.db.set_value("Job Card", self.jc1, "total_completed_qty", 15.0)

        # Mock conf_doc.cancel to raise an exception
        with (
            patch.object(
                frappe.get_doc("KTA Production Confirmation", conf.name).__class__,
                "cancel",
                side_effect=RuntimeError("Cancellation failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            cancel_confirmation(conf.name, user="Administrator")

        # Verify confirmation is still submitted (docstatus=1)
        conf_reloaded = frappe.get_doc("KTA Production Confirmation", conf.name)
        self.assertEqual(conf_reloaded.docstatus, 1)

        # Verify Job Card total_completed_qty is intact (15.0)
        jc = frappe.get_doc("Job Card", self.jc1)
        self.assertEqual(flt(jc.total_completed_qty), 15.0)
