# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_calisma_karti.api_impl._helpers import (
    _assert_enjeksiyon_kalip_valid,
)


class TestEnjeksiyonKalipApi(FrappeTestCase):
    def setUp(self):
        super().setUp()
        # Ensure a known active mold and disabled mold exist for testing
        if not frappe.db.exists("KTA Enjeksiyon Kalibi", "TEST-ACTIVE-MOLD"):
            frappe.get_doc({
                "doctype": "KTA Enjeksiyon Kalibi",
                "kalip_no": "TEST-ACTIVE-MOLD",
                "kalip_adi": "Test Active Mold",
                "disabled": 0,
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("KTA Enjeksiyon Kalibi", "TEST-DISABLED-MOLD"):
            frappe.get_doc({
                "doctype": "KTA Enjeksiyon Kalibi",
                "kalip_no": "TEST-DISABLED-MOLD",
                "kalip_adi": "Test Disabled Mold",
                "disabled": 1,
            }).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.db.delete("KTA Enjeksiyon Kalibi", {"name": ["in", ["TEST-ACTIVE-MOLD", "TEST-DISABLED-MOLD"]]})
        super().tearDown()

    def test_assert_valid_active_mold(self):
        """Active existing mold must pass validation without error."""
        # Should not raise exception
        _assert_enjeksiyon_kalip_valid("TEST-ACTIVE-MOLD")
        _assert_enjeksiyon_kalip_valid(" 8718645633 ")
        _assert_enjeksiyon_kalip_valid(None)
        _assert_enjeksiyon_kalip_valid("")

    def test_assert_nonexistent_mold_fails(self):
        """Non-existent mold must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError) as ctx:
            _assert_enjeksiyon_kalip_valid("NON-EXISTENT-999")
        self.assertIn("NON-EXISTENT-999", str(ctx.exception))

    def test_assert_disabled_mold_fails(self):
        """Disabled mold must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError) as ctx:
            _assert_enjeksiyon_kalip_valid("TEST-DISABLED-MOLD")
        self.assertIn("TEST-DISABLED-MOLD", str(ctx.exception))
