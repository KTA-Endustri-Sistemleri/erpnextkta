# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe

from erpnextkta.patches.v4_4.fix_serial_batch_bundle_posting_dates import execute
from erpnextkta.tests.test_utils import KTAUnitTestCase


class TestFixSerialBatchBundlePostingDates(KTAUnitTestCase):
    """
    Test suite for database patch:
    erpnextkta.patches.v4_4.fix_serial_batch_bundle_posting_dates

    Verifies backfilling of posting_datetime and/or posting_date/posting_time
    on Serial and Batch Bundle from parent vouchers (Stock Entry, Purchase Receipt,
    Delivery Note, Purchase Invoice, Sales Invoice, Stock Reconciliation).
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
        self,
        name,
        voucher_type,
        voucher_no,
        posting_date=None,
        posting_time=None,
        posting_datetime=None,
    ):
        has_posting_datetime = frappe.db.has_column(
            "Serial and Batch Bundle", "posting_datetime"
        )
        has_posting_date = frappe.db.has_column(
            "Serial and Batch Bundle", "posting_date"
        )
        has_posting_time = frappe.db.has_column(
            "Serial and Batch Bundle", "posting_time"
        )

        fields = ["name", "voucher_type", "voucher_no", "docstatus"]
        values = [name, voucher_type, voucher_no, 1]

        if has_posting_datetime:
            if posting_datetime is None and posting_date:
                posting_datetime = f"{posting_date} {posting_time or '00:00:00'}"
            fields.append("posting_datetime")
            values.append(posting_datetime)

        if has_posting_date:
            fields.append("posting_date")
            values.append(posting_date)

        if has_posting_time:
            fields.append("posting_time")
            values.append(posting_time)

        fields_str = ", ".join(f"`{f}`" for f in fields)
        placeholders = ", ".join(["%s"] * len(values))

        frappe.db.sql(
            f"INSERT INTO `tabSerial and Batch Bundle` ({fields_str}) VALUES ({placeholders})",
            tuple(values),
        )

    def test_backfill_all_voucher_types_and_idempotency(self):
        """
        Comprehensive test verifying:
        1. Stock Entry backfill (posting_date/posting_time and/or posting_datetime).
        2. Purchase Receipt backfill.
        3. Delivery Note backfill.
        4. Purchase Invoice, Sales Invoice (COALESCE NULL posting_time -> 00:00:00), Stock Reconciliation.
        5. Existing posting_date / posting_datetime is preserved (not overwritten).
        6. Idempotency (subsequent execute() runs without error and keeps data).
        """
        has_posting_datetime = frappe.db.has_column(
            "Serial and Batch Bundle", "posting_datetime"
        )
        has_posting_date = frappe.db.has_column(
            "Serial and Batch Bundle", "posting_date"
        )
        has_posting_time = frappe.db.has_column(
            "Serial and Batch Bundle", "posting_time"
        )

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

        # 7. Existing posting_date / posting_datetime should NOT be overwritten
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

        frappe.db.commit()

        # Execute the patch
        execute()

        frappe.db.commit()

        fields_to_fetch = []
        if has_posting_datetime:
            fields_to_fetch.append("posting_datetime")
        if has_posting_date:
            fields_to_fetch.append("posting_date")
        if has_posting_time:
            fields_to_fetch.append("posting_time")

        def assert_bundle(bundle_name, expected_date, expected_time):
            res = frappe.db.get_value(
                "Serial and Batch Bundle",
                bundle_name,
                fields_to_fetch,
                as_dict=True,
            )
            self.assertIsNotNone(res)
            if has_posting_datetime:
                self.assertEqual(
                    str(res.posting_datetime), f"{expected_date} {expected_time}"
                )
            if has_posting_date:
                self.assertEqual(str(res.posting_date), expected_date)
            if has_posting_time:
                self.assertEqual(str(res.posting_time).zfill(8), expected_time)

        def verify_bundles():
            # 1. Stock Entry
            assert_bundle("TEST-SABB-SE-001", "2025-02-01", "09:15:00")
            # 2. Purchase Receipt
            assert_bundle("TEST-SABB-PR-001", "2025-02-02", "10:30:00")
            # 3. Delivery Note
            assert_bundle("TEST-SABB-DN-001", "2025-02-03", "14:45:00")
            # 4. Purchase Invoice
            assert_bundle("TEST-SABB-PI-001", "2025-02-04", "16:20:00")
            # 5. Sales Invoice (COALESCE to '00:00:00')
            assert_bundle("TEST-SABB-SI-001", "2025-02-05", "00:00:00")
            # 6. Stock Reconciliation
            assert_bundle("TEST-SABB-SR-001", "2025-02-06", "18:00:00")
            # 7. Existing posting_date / posting_datetime was NOT overwritten
            assert_bundle("TEST-SABB-EXISTING-001", "2025-01-01", "08:00:00")

        # First verification
        verify_bundles()

        # Run execute() a second time to verify idempotency
        execute()

        frappe.db.commit()

        # Second verification ensures data remains identical
        verify_bundles()
