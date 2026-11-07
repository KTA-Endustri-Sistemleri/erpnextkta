# Copyright (c) 2026, KTA Endüstri Sistemleri and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_calisma_karti.api_impl.qc import (
    search_allowed_idc_items,
    _assert_idc_item_allowed_for_work_order,
)


class TestCalismaKartiIdcOlcumleri(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.card_name = "TEST-KULLANICISI-2026-04980-OP40-01"
        self.idc_item = "10024487"

        # If the card exists in the system, use it directly
        if frappe.db.exists("Calisma Karti", self.card_name):
            self.ck = frappe.get_doc("Calisma Karti", self.card_name)
        else:
            # Fallback for isolated CI environments: create valid records
            wo_name = frappe.db.get_value("Work Order", {"docstatus": 1}, "name")
            if not wo_name:
                wo_name = frappe.db.get_value("Work Order", {}, "name")
            self.ck = frappe.new_doc("Calisma Karti")
            self.ck.custom_work_order = wo_name
            self.ck.operator = "Administrator"
            self.ck.flags.ignore_mandatory = True
            self.ck.flags.ignore_permissions = True
            self.ck.flags.ignore_links = True
            self.ck.insert()

    def test_search_allowed_idc_items_includes_obs_bedelsiz(self):
        """120-IDC Connector grubundaki OBS-Bedelsiz malzemenin arama sonuçlarına dahil edildiğini doğrular."""
        results = search_allowed_idc_items("Item", "", "name", 0, 50, {"calisma_karti": self.ck.name})
        item_codes = [r[0] for r in results]
        self.assertIn(self.idc_item, item_codes)
        # 190-Connection Systems should also be in results
        self.assertIn("10024532", item_codes)

    def test_assert_idc_item_allowed_for_work_order_obs_bedelsiz(self):
        """OBS-Bedelsiz 120-IDC Connector malzemesinin validasyondan başarıyla geçtiğini doğrular."""
        _assert_idc_item_allowed_for_work_order(self.ck, self.idc_item)

    def test_assert_idc_item_allowed_for_connection_systems_190(self):
        """190-Connection Systems grubundaki malzemenin validasyondan başarıyla geçtiğini doğrular."""
        _assert_idc_item_allowed_for_work_order(self.ck, "10024532")

    def test_assert_idc_item_rejects_invalid_group(self):
        """120, 110 veya 190 harici malzeme gruplarının reddedildiğini doğrular."""
        # Find an item with different group
        wire_item = frappe.db.get_value("Item", {"item_group": "100-Wires & Cables"}, "name")
        if wire_item:
            with self.assertRaises(frappe.ValidationError):
                _assert_idc_item_allowed_for_work_order(self.ck, wire_item)


def run_tests():
    import unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCalismaKartiIdcOlcumleri)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise Exception("Tests failed!")
    return "All IDC tests passed successfully!"
