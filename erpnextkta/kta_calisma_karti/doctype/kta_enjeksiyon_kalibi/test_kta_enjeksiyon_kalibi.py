# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestKTAEnjeksiyonKalibi(FrappeTestCase):
    def setUp(self):
        super().setUp()
        if frappe.db.table_exists("KTA Enjeksiyon Kalibi"):
            frappe.db.delete("KTA Enjeksiyon Kalibi", {"name": ["in", ["TEST-MOLD-01", "TEST-MOLD-02"]]})

    def tearDown(self):
        if frappe.db.table_exists("KTA Enjeksiyon Kalibi"):
            frappe.db.delete("KTA Enjeksiyon Kalibi", {"name": ["in", ["TEST-MOLD-01", "TEST-MOLD-02"]]})
        super().tearDown()

    def test_create_kta_enjeksiyon_kalibi(self):
        """Test creating a valid KTA Enjeksiyon Kalibi record."""
        doc = frappe.get_doc({
            "doctype": "KTA Enjeksiyon Kalibi",
            "kalip_no": "TEST-MOLD-01",
            "kalip_adi": "TEST-MOLD-01 Enjeksiyon Kalibi",
            "mevcut_adet": 1,
            "disabled": 0,
        }).insert(ignore_permissions=True)

        self.assertEqual(doc.name, "TEST-MOLD-01")
        self.assertEqual(doc.kalip_no, "TEST-MOLD-01")
        self.assertEqual(doc.kalip_adi, "TEST-MOLD-01 Enjeksiyon Kalibi")
        self.assertEqual(doc.mevcut_adet, 1)
        self.assertEqual(doc.disabled, 0)

    def test_duplicate_kalip_no_rejected(self):
        """Duplicate kalip_no should be rejected by unique constraint."""
        frappe.get_doc({
            "doctype": "KTA Enjeksiyon Kalibi",
            "kalip_no": "TEST-MOLD-01",
            "kalip_adi": "TEST-MOLD-01 Enjeksiyon Kalibi",
        }).insert(ignore_permissions=True)

        with self.assertRaises(frappe.DuplicateEntryError):
            frappe.get_doc({
                "doctype": "KTA Enjeksiyon Kalibi",
                "kalip_no": "TEST-MOLD-01",
                "kalip_adi": "Duplicate Mold",
            }).insert(ignore_permissions=True)
