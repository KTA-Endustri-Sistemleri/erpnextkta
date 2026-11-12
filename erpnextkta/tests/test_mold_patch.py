# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.patches.v3_0_3.extract_enjeksiyon_kaliplari import execute as run_patch


class TestMoldPatch(FrappeTestCase):
    def test_extract_enjeksiyon_kaliplari_patch(self):
        """Test that the patch extracts 46 molds from Quality Inspection Templates and is idempotent."""
        # Run patch
        run_patch()

        # Check total count is at least 46
        count = frappe.db.count("KTA Enjeksiyon Kalibi")
        self.assertGreaterEqual(count, 46, f"Expected at least 46 molds, found {count}")

        # Check specific known mold
        sample = frappe.get_doc("KTA Enjeksiyon Kalibi", "8718645633")
        self.assertEqual(sample.kalip_no, "8718645633")
        self.assertTrue(sample.kalip_adi.startswith("8718645633"))
        self.assertTrue(bool(sample.varsayilan_kalite_sablonu))
        self.assertEqual(sample.disabled, 0)

        # Idempotency check: run patch again, should not fail or duplicate
        run_patch()
        new_count = frappe.db.count("KTA Enjeksiyon Kalibi")
        self.assertEqual(count, new_count, "Running patch twice should be idempotent")
