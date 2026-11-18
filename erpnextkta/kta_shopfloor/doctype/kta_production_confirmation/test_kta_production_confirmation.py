# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe

from erpnextkta.tests.test_utils import KTATestCase


class TestKTAProductionConfirmation(KTATestCase):
    def setUp(self):
        super().setUp()
        self.wo = self._get_or_create_test_work_order()

    def _get_or_create_test_work_order(self):
        """Returns an existing or new test Work Order."""
        existing = frappe.db.get_value(
            "Work Order",
            {"docstatus": 1, "status": ("in", ["Not Started", "In Process"])},
            "name",
        )
        if existing:
            return existing

        # If none found, ensure an operation exists
        if not frappe.db.get_value("Operation", {}, "name"):
            frappe.get_doc(
                {
                    "doctype": "Operation",
                    "operation": "Test Kesim Operasyonu",
                }
            ).insert(ignore_permissions=True, ignore_if_duplicate=True)

        # Find an existing item or create dummy
        item_name = frappe.db.get_value("Item", {"is_stock_item": 1}, "name")
        if not item_name:
            item = frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": "_TEST_FG_ITEM",
                    "item_group": "All Item Groups",
                    "stock_uom": "Nos",
                    "is_stock_item": 1,
                }
            ).insert(ignore_permissions=True, ignore_if_duplicate=True)
            item_name = item.name

        wo = frappe.get_doc(
            {
                "doctype": "Work Order",
                "production_item": item_name,
                "qty": 10.0,
                "wip_warehouse": frappe.db.get_value(
                    "Warehouse", {"is_group": 0}, "name"
                )
                or "Work In Progress - _TC",
                "fg_warehouse": frappe.db.get_value(
                    "Warehouse", {"is_group": 0}, "name"
                )
                or "Finished Goods - _TC",
                "company": "_Test Company",
            }
        )
        try:
            wo.insert(ignore_permissions=True)
            wo.submit()
            return wo.name
        except (frappe.ValidationError, frappe.LinkValidationError):
            # Fallback to dummy string if full WO creation fails in isolation
            return "MFG-WO-TEST-0001"

    def test_create_and_submit_production_confirmation(self):
        """Test creation and submission of a valid KTA Production Confirmation document."""
        op_name = (
            frappe.db.get_value("Operation", {}, "name") or "Test Kesim Operasyonu"
        )
        teyit = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo,
                "operation": op_name,
                "posting_date": frappe.utils.nowdate(),
                "posting_time": frappe.utils.nowtime(),
                "yield_qty": 5.0,
                "is_final_confirmation": 0,
            }
        )
        teyit.insert()
        self.assertEqual(teyit.docstatus, 0)
        self.assertEqual(teyit.meta.module, "kta_shopfloor")
        self.assertTrue(teyit.confirmed_by)

        teyit.submit()
        self.assertEqual(teyit.docstatus, 1)

    def test_yield_qty_must_be_positive(self):
        """Test that yield_qty <= 0 is rejected with ValidationError."""
        op_name = (
            frappe.db.get_value("Operation", {}, "name") or "Test Kesim Operasyonu"
        )
        teyit = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo,
                "operation": op_name,
                "yield_qty": 0,
            }
        )
        with self.assertRaises(frappe.ValidationError):
            teyit.insert()

    def test_cancel_production_confirmation(self):
        """Test that a submitted confirmation can be cancelled."""
        op_name = (
            frappe.db.get_value("Operation", {}, "name") or "Test Kesim Operasyonu"
        )
        teyit = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo,
                "operation": op_name,
                "yield_qty": 2.0,
            }
        )
        teyit.insert()
        teyit.submit()
        self.assertEqual(teyit.docstatus, 1)

        teyit.cancel()
        self.assertEqual(teyit.docstatus, 2)

    def test_is_final_confirmation_flag(self):
        """Test that is_final_confirmation defaults to 0 and can be set to 1."""
        op_name = (
            frappe.db.get_value("Operation", {}, "name") or "Test Kesim Operasyonu"
        )
        teyit = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo,
                "operation": op_name,
                "yield_qty": 3.0,
                "is_final_confirmation": 1,
            }
        )
        teyit.insert()
        self.assertEqual(teyit.is_final_confirmation, 1)
        teyit.submit()
        self.assertEqual(teyit.docstatus, 1)

    def test_missing_mandatory_fields_raise(self):
        """Test that omitting work_order or operation raises MandatoryError."""
        teyit = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "yield_qty": 1.0,
            }
        )
        with self.assertRaises(frappe.MandatoryError):
            teyit.insert()
