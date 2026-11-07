# Copyright (c) 2026, KTA Endüstri Sistemleri and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_calisma_karti.api_impl.qc import (
    search_allowed_idc_items,
    _assert_idc_item_allowed_for_work_order,
)


class TestCalismaKartiIdcOlcumleri(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")

        # 1. Ensure Item Groups and KTA Ara Malzeme Grubu exist
        for group in ["120-IDC Connector", "190-Connection Systems", "100-Wires & Cables", "Products"]:
            if not frappe.db.exists("Item Group", group):
                frappe.get_doc({
                    "doctype": "Item Group",
                    "item_group_name": group,
                    "parent_item_group": "All Item Groups",
                    "is_group": 0,
                }).insert(ignore_permissions=True)

        for amg in ["OBS-Bedelsiz", "Normal", "ÜRÜN"]:
            if not frappe.db.exists("KTA Ara Malzeme Grubu", amg):
                frappe.get_doc({
                    "doctype": "KTA Ara Malzeme Grubu",
                    "kta_ara_malzeme_grubu": amg,
                }).insert(ignore_permissions=True)

        # 2. Create test items
        cls.idc_item = "TEST-IDC-120-ITEM"
        cls.conn_item = "TEST-CONN-190-ITEM"
        cls.wire_item = "TEST-WIRE-100-ITEM"
        cls.not_in_bom = "TEST-IDC-NOT-IN-BOM"
        cls.fg_item = "TEST-FG-ITEM-FOR-IDC"

        item_specs = [
            (cls.idc_item, "120-IDC Connector", "OBS-Bedelsiz"),
            (cls.conn_item, "190-Connection Systems", "Normal"),
            (cls.wire_item, "100-Wires & Cables", "Normal"),
            (cls.not_in_bom, "120-IDC Connector", "Normal"),
            (cls.fg_item, "Products", "Normal"),
        ]
        for code, group, ara_grup in item_specs:
            if not frappe.db.exists("Item", code):
                doc = frappe.new_doc("Item")
                doc.item_code = code
                doc.item_name = code
                doc.item_group = group
                doc.is_stock_item = 1
                doc.stock_uom = "Nos"
                doc.custom_ara_malzeme_grubu = ara_grup
                doc.insert(ignore_permissions=True)
            else:
                frappe.db.set_value("Item", code, {
                    "item_group": group,
                    "custom_ara_malzeme_grubu": ara_grup,
                })

        company = frappe.db.get_value("Company", {}, "name") or "_Test Company"

        # 3. Create test BOM
        bom = frappe.new_doc("BOM")
        bom.item = cls.fg_item
        bom.quantity = 1
        bom.currency = "TRY"
        bom.company = company
        bom.append("items", {
            "item_code": cls.idc_item,
            "qty": 1,
            "uom": "Nos",
            "rate": 1,
        })
        bom.append("items", {
            "item_code": cls.conn_item,
            "qty": 1,
            "uom": "Nos",
            "rate": 1,
        })
        bom.flags.ignore_permissions = True
        bom.flags.ignore_mandatory = True
        bom.flags.ignore_validate = True
        bom.insert()
        cls.bom_name = bom.name

        # 4. Create Work Order
        cls.wo_name = "TEST-WO-IDC-001"
        frappe.db.sql("DELETE FROM `tabWork Order` WHERE name=%s", (cls.wo_name,))
        frappe.db.sql("""
            INSERT INTO `tabWork Order` (name, production_item, bom_no, qty, company, docstatus, status, creation, modified, modified_by)
            VALUES (%s, %s, %s, 10, %s, 1, 'In Process', NOW(), NOW(), 'Administrator')
        """, (cls.wo_name, cls.fg_item, cls.bom_name, company))

        # 5. Create Calisma Karti
        ck = frappe.new_doc("Calisma Karti")
        ck.custom_work_order = cls.wo_name
        ck.operator = "Administrator"
        ck.flags.ignore_mandatory = True
        ck.flags.ignore_permissions = True
        ck.flags.ignore_links = True
        ck.insert()
        cls.card_name = ck.name

        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "card_name", None) and frappe.db.exists("Calisma Karti", cls.card_name):
            frappe.delete_doc("Calisma Karti", cls.card_name, force=1, ignore_permissions=True)
        if getattr(cls, "wo_name", None) and frappe.db.exists("Work Order", cls.wo_name):
            frappe.db.sql("DELETE FROM `tabWork Order` WHERE name=%s", (cls.wo_name,))
        if getattr(cls, "bom_name", None) and frappe.db.exists("BOM", cls.bom_name):
            frappe.delete_doc("BOM", cls.bom_name, force=1, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        frappe.set_user("Administrator")
        self.ck = frappe.get_doc("Calisma Karti", self.card_name)

    def test_search_allowed_idc_items_includes_obs_bedelsiz(self):
        """120-IDC Connector grubundaki OBS-Bedelsiz malzemenin arama sonuçlarına dahil edildiğini doğrular."""
        results = search_allowed_idc_items("Item", "", "name", 0, 50, {"calisma_karti": self.ck.name})
        item_codes = [r[0] for r in results]
        self.assertIn(self.idc_item, item_codes)
        # 190-Connection Systems should also be in results
        self.assertIn(self.conn_item, item_codes)

    def test_assert_idc_item_allowed_for_work_order_obs_bedelsiz(self):
        """OBS-Bedelsiz 120-IDC Connector malzemesinin validasyondan başarıyla geçtiğini doğrular."""
        _assert_idc_item_allowed_for_work_order(self.ck, self.idc_item)

    def test_assert_idc_item_allowed_for_connection_systems_190(self):
        """190-Connection Systems grubundaki malzemenin validasyondan başarıyla geçtiğini doğrular."""
        _assert_idc_item_allowed_for_work_order(self.ck, self.conn_item)

    def test_assert_idc_item_rejects_invalid_group(self):
        """120, 110 veya 190 harici malzeme gruplarının reddedildiğini doğrular."""
        with self.assertRaises(frappe.ValidationError):
            _assert_idc_item_allowed_for_work_order(self.ck, self.wire_item)

    def test_assert_idc_item_rejects_item_not_in_bom(self):
        """BOM içinde yer almayan malzemenin reddedildiğini doğrular."""
        with self.assertRaises(frappe.ValidationError):
            _assert_idc_item_allowed_for_work_order(self.ck, self.not_in_bom)


def run_tests():
    import unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCalismaKartiIdcOlcumleri)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise Exception("Tests failed!")
    return "All IDC tests passed successfully!"
