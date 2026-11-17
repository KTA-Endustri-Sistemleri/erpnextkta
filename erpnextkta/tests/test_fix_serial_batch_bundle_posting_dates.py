# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe

from erpnextkta.patches.v4_4.fix_serial_batch_bundle_posting_dates import execute
from erpnextkta.tests.test_utils import KTAUnitTestCase


class TestFixSerialBatchBundlePostingDates(KTAUnitTestCase):
    """
    Test suite for database patch:
    erpnextkta.patches.v4_4.fix_serial_batch_bundle_posting_dates

    Verifies backfilling of posting_date and posting_time on Serial and Batch Bundle
    from parent vouchers (Stock Entry, Purchase Receipt, Delivery Note, Purchase Invoice,
    Sales Invoice, Stock Reconciliation) where posting_date IS NULL.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not getattr(frappe, "db", None) or not frappe.db:
            frappe.init("development.localhost")
            frappe.connect()
        frappe.set_user("Administrator")

    def setUp(self):
        super().setUp()
        self.cleanup_test_data()

    def tearDown(self):
        self.cleanup_test_data()
        super().tearDown()

    def cleanup_test_data(self):
        """Clean up all test vouchers and bundles created by this test suite."""
        test_bundles = [
            "TEST-SABB-SE-001",
            "TEST-SABB-PR-001",
            "TEST-SABB-DN-001",
            "TEST-SABB-PI-001",
            "TEST-SABB-SI-001",
            "TEST-SABB-SR-001",
            "TEST-SABB-EXISTING-001",
        ]
        for b_name in test_bundles:
            frappe.db.sql(
                "DELETE FROM `tabSerial and Batch Bundle` WHERE name=%s", (b_name,)
            )

        vouchers = [
            ("Stock Entry", "TEST-SE-PATCH-001"),
            ("Stock Entry", "TEST-SE-EXISTING-001"),
            ("Purchase Receipt", "TEST-PR-PATCH-001"),
            ("Delivery Note", "TEST-DN-PATCH-001"),
            ("Purchase Invoice", "TEST-PI-PATCH-001"),
            ("Sales Invoice", "TEST-SI-PATCH-001"),
            ("Stock Reconciliation", "TEST-SR-PATCH-001"),
        ]
        for doctype, v_name in vouchers:
            if frappe.db.exists("DocType", doctype):
                frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE name=%s", (v_name,))

        frappe.db.commit()

    def _create_voucher(self, doctype, name, posting_date, posting_time=None):
        frappe.db.sql(
            f"""
            INSERT INTO `tab{doctype}` (name, posting_date, posting_time, docstatus)
            VALUES (%s, %s, %s, 1)
            """,
            (name, posting_date, posting_time),
        )

    def _create_bundle(
        self, name, voucher_type, voucher_no, posting_date=None, posting_time=None
    ):
        frappe.db.sql(
            """
            INSERT INTO `tabSerial and Batch Bundle` (name, voucher_type, voucher_no, posting_date, posting_time, docstatus)
            VALUES (%s, %s, %s, %s, %s, 1)
            """,
            (name, voucher_type, voucher_no, posting_date, posting_time),
        )

    def test_backfill_all_voucher_types_and_idempotency(self):
        """
        Comprehensive test verifying:
        1. Stock Entry backfill (posting_date and posting_time).
        2. Purchase Receipt backfill.
        3. Delivery Note backfill.
        4. Purchase Invoice, Sales Invoice (COALESCE NULL posting_time -> 00:00:00), Stock Reconciliation.
        5. Existing posting_date is preserved (not overwritten).
        6. Idempotency (subsequent execute() runs without error and keeps data).
        """
        # 1. Stock Entry
        self._create_voucher(
            "Stock Entry", "TEST-SE-PATCH-001", "2025-02-01", "09:15:00"
        )
        self._create_bundle("TEST-SABB-SE-001", "Stock Entry", "TEST-SE-PATCH-001")

        # 2. Purchase Receipt
        self._create_voucher(
            "Purchase Receipt", "TEST-PR-PATCH-001", "2025-02-02", "10:30:00"
        )
        self._create_bundle("TEST-SABB-PR-001", "Purchase Receipt", "TEST-PR-PATCH-001")

        # 3. Delivery Note
        self._create_voucher(
            "Delivery Note", "TEST-DN-PATCH-001", "2025-02-03", "14:45:00"
        )
        self._create_bundle("TEST-SABB-DN-001", "Delivery Note", "TEST-DN-PATCH-001")

        # 4. Purchase Invoice
        self._create_voucher(
            "Purchase Invoice", "TEST-PI-PATCH-001", "2025-02-04", "16:20:00"
        )
        self._create_bundle("TEST-SABB-PI-001", "Purchase Invoice", "TEST-PI-PATCH-001")

        # 5. Sales Invoice with NULL posting_time (testing COALESCE to '00:00:00')
        self._create_voucher("Sales Invoice", "TEST-SI-PATCH-001", "2025-02-05", None)
        self._create_bundle("TEST-SABB-SI-001", "Sales Invoice", "TEST-SI-PATCH-001")

        # 6. Stock Reconciliation
        self._create_voucher(
            "Stock Reconciliation", "TEST-SR-PATCH-001", "2025-02-06", "18:00:00"
        )
        self._create_bundle(
            "TEST-SABB-SR-001", "Stock Reconciliation", "TEST-SR-PATCH-001"
        )

        # 7. Existing posting_date should NOT be overwritten
        self._create_voucher(
            "Stock Entry", "TEST-SE-EXISTING-001", "2025-02-10", "12:00:00"
        )
        self._create_bundle(
            "TEST-SABB-EXISTING-001",
            "Stock Entry",
            "TEST-SE-EXISTING-001",
            posting_date="2025-01-01",
            posting_time="08:00:00",
        )

        # Execute the patch
        execute()

        def verify_bundles():
            # 1. Stock Entry
            se_res = frappe.db.get_value(
                "Serial and Batch Bundle",
                "TEST-SABB-SE-001",
                ["posting_date", "posting_time"],
                as_dict=True,
            )
            self.assertIsNotNone(se_res)
            self.assertEqual(str(se_res.posting_date), "2025-02-01")
            self.assertEqual(str(se_res.posting_time).zfill(8), "09:15:00")

            # 2. Purchase Receipt
            pr_res = frappe.db.get_value(
                "Serial and Batch Bundle",
                "TEST-SABB-PR-001",
                ["posting_date", "posting_time"],
                as_dict=True,
            )
            self.assertIsNotNone(pr_res)
            self.assertEqual(str(pr_res.posting_date), "2025-02-02")
            self.assertEqual(str(pr_res.posting_time).zfill(8), "10:30:00")

            # 3. Delivery Note
            dn_res = frappe.db.get_value(
                "Serial and Batch Bundle",
                "TEST-SABB-DN-001",
                ["posting_date", "posting_time"],
                as_dict=True,
            )
            self.assertIsNotNone(dn_res)
            self.assertEqual(str(dn_res.posting_date), "2025-02-03")
            self.assertEqual(str(dn_res.posting_time).zfill(8), "14:45:00")

            # 4. Purchase Invoice
            pi_res = frappe.db.get_value(
                "Serial and Batch Bundle",
                "TEST-SABB-PI-001",
                ["posting_date", "posting_time"],
                as_dict=True,
            )
            self.assertEqual(str(pi_res.posting_date), "2025-02-04")
            self.assertEqual(str(pi_res.posting_time).zfill(8), "16:20:00")

            # 5. Sales Invoice (COALESCE to '00:00:00')
            si_res = frappe.db.get_value(
                "Serial and Batch Bundle",
                "TEST-SABB-SI-001",
                ["posting_date", "posting_time"],
                as_dict=True,
            )
            self.assertEqual(str(si_res.posting_date), "2025-02-05")
            self.assertEqual(str(si_res.posting_time).zfill(8), "00:00:00")

            # 6. Stock Reconciliation
            sr_res = frappe.db.get_value(
                "Serial and Batch Bundle",
                "TEST-SABB-SR-001",
                ["posting_date", "posting_time"],
                as_dict=True,
            )
            self.assertEqual(str(sr_res.posting_date), "2025-02-06")
            self.assertEqual(str(sr_res.posting_time).zfill(8), "18:00:00")

            # 7. Existing posting_date was NOT overwritten
            ex_res = frappe.db.get_value(
                "Serial and Batch Bundle",
                "TEST-SABB-EXISTING-001",
                ["posting_date", "posting_time"],
                as_dict=True,
            )
            self.assertEqual(str(ex_res.posting_date), "2025-01-01")
            self.assertEqual(str(ex_res.posting_time).zfill(8), "08:00:00")

        # First verification
        verify_bundles()

        # Run execute() a second time to verify idempotency
        execute()

        # Second verification ensures data remains identical
        verify_bundles()
