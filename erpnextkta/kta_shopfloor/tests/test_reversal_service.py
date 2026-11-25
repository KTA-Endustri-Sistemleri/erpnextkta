# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe import _
from frappe.utils import flt

from erpnextkta.kta_shopfloor.services.confirmation_service import ConfirmationService
from erpnextkta.kta_shopfloor.services.reversal_service import (
    ReversalService,
    bulk_cancel_confirmations,
    can_cancel_confirmations,
    cancel_confirmation,
)
from erpnextkta.tests.test_utils import KTATestCase, create_test_work_order


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

    def _create_submitted_confirmation(
        self,
        work_order: str,
        operation: str,
        job_card: str | None = None,
        yield_qty: float = 10.0,
        is_final: int = 0,
    ):
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": work_order,
                "operation": operation,
                "job_card": job_card,
                "yield_qty": yield_qty,
                "is_final_confirmation": is_final,
            }
        )
        conf.flags.ignore_permissions = True
        conf.insert(ignore_permissions=True)
        conf.submit()
        return conf

    def _setup_second_work_order(self, wo_name: str = "TEST-WO-CORS-002"):
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)
        frappe.db.delete("Work Order Operation", {"parent": wo_name})
        frappe.db.delete("Stock Entry", {"work_order": wo_name})
        frappe.db.delete("KTA Production Confirmation", {"work_order": wo_name})

        frappe.get_doc(
            {
                "doctype": "Work Order Operation",
                "parent": wo_name,
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

        frappe.db.set_value(
            "Work Order",
            wo_name,
            {"docstatus": 1, "status": "Not Started", "produced_qty": 0.0},
        )
        existing_jc = frappe.db.get_value(
            "Job Card",
            {"work_order": wo_name, "operation": self.op1},
            "name",
        )
        if existing_jc:
            frappe.db.set_value(
                "Job Card",
                existing_jc,
                {
                    "work_order": wo_name,
                    "operation": self.op1,
                    "docstatus": 0,
                    "status": "Open",
                    "total_completed_qty": 0.0,
                    "for_quantity": 100.0,
                },
            )
            jc_name = existing_jc
        else:
            jc = frappe.get_doc(
                {
                    "doctype": "Job Card",
                    "work_order": wo_name,
                    "operation": self.op1,
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
            jc_name = jc.name

        frappe.db.commit()
        return wo_name, jc_name

    def test_role_permissions_single_and_bulk(self):
        """Only System Manager / Manufacturing Manager (and Administrator) may cancel."""
        conf = self._create_submitted_confirmation(
            self.wo_name, self.op1, self.jc1, yield_qty=10.0
        )

        # KTA Çalışma Kartı Yöneticisi is rejected
        ck_manager = "test_ck_manager@example.com"
        with patch("frappe.get_roles", return_value=["KTA Çalışma Kartı Yöneticisi"]):
            self.assertFalse(can_cancel_confirmations(ck_manager))
            self.assertFalse(ReversalService.can_cancel_confirmations(ck_manager))
            with self.assertRaises(frappe.PermissionError):
                cancel_confirmation(conf.name, user=ck_manager)
            with self.assertRaises(frappe.PermissionError):
                bulk_cancel_confirmations([conf.name], user=ck_manager)

        # Manufacturing User is rejected
        mfg_user = "test_mfg_user@example.com"
        with patch("frappe.get_roles", return_value=["Manufacturing User"]):
            self.assertFalse(can_cancel_confirmations(mfg_user))
            self.assertFalse(ReversalService.can_cancel_confirmations(mfg_user))
            with self.assertRaises(frappe.PermissionError):
                cancel_confirmation(conf.name, user=mfg_user)
            with self.assertRaises(frappe.PermissionError):
                bulk_cancel_confirmations([conf.name], user=mfg_user)

        # Manufacturing Manager is allowed
        mfg_manager = "test_mfg_manager@example.com"
        with patch("frappe.get_roles", return_value=["Manufacturing Manager"]):
            self.assertTrue(can_cancel_confirmations(mfg_manager))
            self.assertTrue(ReversalService.can_cancel_confirmations(mfg_manager))
            res = bulk_cancel_confirmations([conf.name], user=mfg_manager)
            self.assertTrue(res["success"])
            self.assertEqual(res["cancelled_count"], 1)

        self.assertEqual(
            frappe.db.get_value("KTA Production Confirmation", conf.name, "docstatus"),
            2,
        )

    def test_bulk_cancel_validation_and_missing_confirmations(self):
        """Empty or non-list payloads raise ValidationError; missing names report in failed."""
        with self.assertRaises(frappe.ValidationError):
            bulk_cancel_confirmations([], user="Administrator")

        with self.assertRaises(frappe.ValidationError):
            bulk_cancel_confirmations("[]", user="Administrator")

        with self.assertRaises(frappe.ValidationError):
            bulk_cancel_confirmations("not-valid-json", user="Administrator")

        res = ReversalService.bulk_cancel_confirmations(
            ["CONF-DOES-NOT-EXIST-001", "CONF-DOES-NOT-EXIST-001"],
            user="Administrator",
        )
        self.assertFalse(res["success"])
        self.assertFalse(res["partial"])
        self.assertEqual(res["total_requested"], 1)
        self.assertEqual(res["failed_count"], 1)
        self.assertEqual(res["cancelled_count"], 0)
        self.assertEqual(res["failed"][0]["confirmation"], "CONF-DOES-NOT-EXIST-001")

    def test_bulk_cancel_across_two_work_orders_reverse_chronological(self):
        """Bulk cancel reverses multiple confirmations across 2 WOs in newest-first order."""
        wo2_name, wo2_jc = self._setup_second_work_order()

        with (
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
            ) as mock_consumption,
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
            ) as mock_fg,
        ):
            se1 = self._create_mock_stock_entry("Material Consumption for Manufacture")
            se2 = self._create_mock_stock_entry("Manufacture")

            mock_consumption.side_effect = [se1, None]
            mock_fg.return_value = None
            res1 = ConfirmationService.confirm_operation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op1,
                    "job_card": self.jc1,
                    "yield_qty": 30.0,
                }
            )
            conf1 = res1["confirmation"]

            mock_consumption.side_effect = None
            mock_consumption.return_value = None
            mock_fg.return_value = se2
            res2 = ConfirmationService.confirm_operation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op2,
                    "job_card": self.jc2,
                    "yield_qty": 30.0,
                    "is_final_confirmation": 1,
                }
            )
            conf2 = res2["confirmation"]

            # Second Work Order confirmation (single operation, milestone)
            se3 = f"TEST-SE-WO2-{frappe.generate_hash(length=6)}"
            frappe.db.sql(
                """
                INSERT INTO `tabStock Entry` (
                    name, docstatus, purpose, stock_entry_type, work_order, company,
                    remarks, creation, modified, modified_by
                ) VALUES (%s, 1, 'Manufacture', 'Manufacture', %s, %s, '', NOW(), NOW(), 'Administrator')
                """,
                (se3, wo2_name, self.company),
            )
            mock_fg.return_value = se3
            res3 = ConfirmationService.confirm_operation(
                {
                    "work_order": wo2_name,
                    "operation": self.op1,
                    "job_card": wo2_jc,
                    "yield_qty": 50.0,
                    "is_final_confirmation": 1,
                }
            )
            conf3 = res3["confirmation"]

        # Pass in oldest-first JSON string with a duplicate to verify deduplication & sorting
        payload_json = json.dumps([f" {conf1} ", conf2, conf3, conf1])
        bulk_res = bulk_cancel_confirmations(payload_json, user="Administrator")

        self.assertTrue(bulk_res["success"])
        self.assertFalse(bulk_res["partial"])
        self.assertEqual(bulk_res["total_requested"], 3)
        self.assertEqual(bulk_res["cancelled_count"], 3)
        self.assertEqual(bulk_res["cascade_cancelled_count"], 0)
        self.assertEqual(bulk_res["failed_count"], 0)
        self.assertEqual(
            set(bulk_res["affected_work_orders"]), {self.wo_name, wo2_name}
        )

        # Verify reverse-chronological execution order (conf3, conf2, conf1)
        cancelled_order = [item["confirmation"] for item in bulk_res["cancelled"]]
        self.assertEqual(cancelled_order, [conf3, conf2, conf1])

        # Verify all confirmations & stock entries are cancelled
        for c_name in (conf1, conf2, conf3):
            self.assertEqual(
                frappe.db.get_value("KTA Production Confirmation", c_name, "docstatus"),
                2,
            )
        for se_name in (se1, se2, se3):
            self.assertEqual(
                frappe.db.get_value("Stock Entry", se_name, "docstatus"), 2
            )

        # Verify Job Cards & both Work Orders rolled back
        for jc_name in (self.jc1, self.jc2, wo2_jc):
            jc_doc = frappe.get_doc("Job Card", jc_name)
            self.assertEqual(flt(jc_doc.total_completed_qty), 0.0)
            self.assertEqual(jc_doc.status, "Open")

        for wo_id in (self.wo_name, wo2_name):
            wo_doc = frappe.get_doc("Work Order", wo_id)
            self.assertEqual(flt(wo_doc.produced_qty), 0.0)
            for op_row in wo_doc.operations:
                self.assertEqual(flt(op_row.completed_qty), 0.0)
                self.assertEqual(op_row.status, "Pending")

    def test_bulk_cancel_catchup_cascade_deduplication(self):
        """Selecting both milestone and its catchup cancels both cleanly with cascade tracking."""
        with (
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
            ) as mock_consumption,
            patch(
                "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_finished_goods_entry"
            ) as mock_fg,
        ):
            se_cons = self._create_mock_stock_entry(
                "Material Consumption for Manufacture"
            )
            se_fg = self._create_mock_stock_entry("Manufacture")
            mock_consumption.return_value = se_cons
            mock_fg.return_value = se_fg

            # Confirm op2 directly -> triggers auto-catchup confirmation for op1
            res = ConfirmationService.confirm_operation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op2,
                    "job_card": self.jc2,
                    "yield_qty": 20.0,
                    "is_final_confirmation": 0,
                }
            )
            milestone_conf = res["confirmation"]
            catchup_confs = res.get("catchup_confirmations") or []
            self.assertEqual(len(catchup_confs), 1)
            catchup_conf = catchup_confs[0]

        # Select both catchup and milestone confirmation
        bulk_res = ReversalService.bulk_cancel_confirmations(
            [catchup_conf, milestone_conf], user="Administrator"
        )

        self.assertTrue(bulk_res["success"])
        self.assertFalse(bulk_res["partial"])
        self.assertEqual(bulk_res["total_requested"], 2)
        self.assertEqual(bulk_res["cancelled_count"], 1)
        self.assertEqual(bulk_res["cascade_cancelled_count"], 1)
        self.assertEqual(bulk_res["failed_count"], 0)
        self.assertEqual(bulk_res["cancelled"][0]["confirmation"], milestone_conf)
        self.assertEqual(bulk_res["cascade_cancelled"][0]["confirmation"], catchup_conf)
        self.assertEqual(
            bulk_res["cascade_cancelled"][0]["cancelled_by"], milestone_conf
        )

        self.assertEqual(
            frappe.db.get_value(
                "KTA Production Confirmation", milestone_conf, "docstatus"
            ),
            2,
        )
        self.assertEqual(
            frappe.db.get_value(
                "KTA Production Confirmation", catchup_conf, "docstatus"
            ),
            2,
        )

    def test_bulk_cancel_partial_failure_savepoint_isolation(self):
        """A failure on one confirmation isolates its rollback, cleans message_log, and continues."""
        conf_ok = self._create_submitted_confirmation(
            self.wo_name, self.op1, self.jc1, yield_qty=10.0
        ).name
        conf_fail = self._create_submitted_confirmation(
            self.wo_name, self.op1, self.jc1, yield_qty=15.0
        ).name
        frappe.db.set_value("Job Card", self.jc1, "total_completed_qty", 25.0)

        real_cancel = ReversalService.cancel_confirmation

        def _selective_cancel(confirmation_name: str, user: str | None = None):
            if confirmation_name == conf_fail:
                frappe.throw(_("Simüle edilmiş iptal hatası"), frappe.ValidationError)
            return real_cancel(confirmation_name, user=user)

        frappe.clear_messages()
        with patch.object(
            ReversalService, "cancel_confirmation", side_effect=_selective_cancel
        ):
            bulk_res = ReversalService.bulk_cancel_confirmations(
                [conf_ok, conf_fail], user="Administrator"
            )

        self.assertFalse(bulk_res["success"])
        self.assertTrue(bulk_res["partial"])
        self.assertEqual(bulk_res["total_requested"], 2)
        self.assertEqual(bulk_res["cancelled_count"], 1)
        self.assertEqual(bulk_res["failed_count"], 1)
        self.assertEqual(bulk_res["cancelled"][0]["confirmation"], conf_ok)
        self.assertEqual(bulk_res["failed"][0]["confirmation"], conf_fail)
        self.assertIn("Simüle edilmiş iptal hatası", bulk_res["failed"][0]["error"])
        self.assertEqual(frappe.local.message_log, [])

        # conf_ok is cancelled, conf_fail remains submitted
        self.assertEqual(
            frappe.db.get_value("KTA Production Confirmation", conf_ok, "docstatus"), 2
        )
        self.assertEqual(
            frappe.db.get_value("KTA Production Confirmation", conf_fail, "docstatus"),
            1,
        )
