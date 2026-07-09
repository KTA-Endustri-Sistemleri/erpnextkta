import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.tests.test_utils import KTATestCase

class TestQIValidation(KTATestCase):
    def setUp(self):
        super().setUp()
        from erpnextkta.tests.test_utils import make_mock_calisma_karti

        # Create Calisma Karti 1 (Legacy)
        self.ck_legacy = frappe.get_doc({
            "doctype": "Calisma Karti",
            "operasyon": "TEST-OP-LEGACY",
            "is_istasyonu": "Test WS",
            "operator": "test@kta.com",
            "custom_work_order": "WO-DUMMY",
            "is_karti": "JC-DUMMY"
        }).insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True)
        # Ensure operation is set to legacy mode
        frappe.db.set_value("KTA Calisma Karti Operasyonlari", self.ck_legacy.operasyon, "alt_operasyon_bazli_kalite", 0)

        # Create Calisma Karti 2 (Sub-Op)
        self.ck_sub = frappe.get_doc({
            "doctype": "Calisma Karti",
            "operasyon": "TEST-OP-SUB",
            "is_istasyonu": "Test WS",
            "operator": "test@kta.com",
            "custom_work_order": "WO-DUMMY",
            "is_karti": "JC-DUMMY"
        }).insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True)
        # Ensure operation is set to sub-op mode
        frappe.db.set_value("KTA Calisma Karti Operasyonlari", self.ck_sub.operasyon, "alt_operasyon_bazli_kalite", 1)

        # Create Dummy Item for QI
        if not frappe.db.exists("Item", "TEST-QI-ITEM"):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": "TEST-QI-ITEM",
                "item_group": "All Item Groups",
                "stock_uom": "Nos"
            }).insert(ignore_permissions=True)

    def test_legacy_mode_qi(self):
        """Senaryo 1: Alt operasyon bazlı kalite kapalıyken"""
        # Hata 1: Alt operasyon kaydı seçilmeye çalışılırsa
        qi_invalid = frappe.get_doc({
            "doctype": "Quality Inspection",
            "inspection_type": "In Process",
            "item_code": "TEST-QI-ITEM",
            "custom_calisma_karti": self.ck_legacy.name,
            "custom_alt_operasyon_kaydi": "DUMMY-SUB-OP"
        })
        with self.assertRaises(frappe.ValidationError) as cm:
            qi_invalid.insert(ignore_links=True, ignore_mandatory=True)
        self.assertIn("boş bırakılmalıdır", str(cm.exception))

        # Başarı 1: Normal kayıtta sorun yok
        qi_valid = frappe.get_doc({
            "doctype": "Quality Inspection",
            "inspection_type": "In Process",
            "item_code": "TEST-QI-ITEM",
            "custom_calisma_karti": self.ck_legacy.name,
        }).insert(ignore_links=True, ignore_mandatory=True)
        self.assertTrue(qi_valid.name)

        # Hata 2: İkinci kez boş bırakarak eklemeye çalışılırsa
        qi_duplicate = frappe.get_doc({
            "doctype": "Quality Inspection",
            "inspection_type": "In Process",
            "item_code": "TEST-QI-ITEM",
            "custom_calisma_karti": self.ck_legacy.name,
        })
        with self.assertRaises(frappe.ValidationError) as cm:
            qi_duplicate.insert(ignore_links=True, ignore_mandatory=True)
        self.assertIn("zaten bir Kalite Kontrol belgesi", str(cm.exception))

    def test_sub_op_mode_qi(self):
        """Senaryo 2: Alt operasyon bazlı kalite açıkken"""
        # Hata 1: Alt operasyon kaydı seçilmezse
        qi_invalid = frappe.get_doc({
            "doctype": "Quality Inspection",
            "inspection_type": "In Process",
            "item_code": "TEST-QI-ITEM",
            "custom_calisma_karti": self.ck_sub.name,
        })
        with self.assertRaises(frappe.ValidationError) as cm:
            qi_invalid.insert(ignore_links=True, ignore_mandatory=True)
        self.assertIn("mutlaka seçilmelidir", str(cm.exception))

        # Başarı 1: Alt operasyon (SubOp1) ile eklenebilir
        qi_valid_1 = frappe.get_doc({
            "doctype": "Quality Inspection",
            "inspection_type": "In Process",
            "item_code": "TEST-QI-ITEM",
            "custom_calisma_karti": self.ck_sub.name,
            "custom_alt_operasyon_kaydi": "SubOp1"
        }).insert(ignore_links=True, ignore_mandatory=True)
        self.assertTrue(qi_valid_1.name)

        # Hata 2: Aynı alt operasyon (SubOp1) ile ikinci kez eklenemez
        qi_duplicate = frappe.get_doc({
            "doctype": "Quality Inspection",
            "inspection_type": "In Process",
            "item_code": "TEST-QI-ITEM",
            "custom_calisma_karti": self.ck_sub.name,
            "custom_alt_operasyon_kaydi": "SubOp1"
        })
        with self.assertRaises(frappe.ValidationError) as cm:
            qi_duplicate.insert(ignore_links=True, ignore_mandatory=True)
        self.assertIn("seçili Alt Operasyonu için zaten", str(cm.exception))

        # Başarı 2: Farklı alt operasyon (SubOp2) ile eklenebilir
        qi_valid_2 = frappe.get_doc({
            "doctype": "Quality Inspection",
            "inspection_type": "In Process",
            "item_code": "TEST-QI-ITEM",
            "custom_calisma_karti": self.ck_sub.name,
            "custom_alt_operasyon_kaydi": "SubOp2"
        }).insert(ignore_links=True, ignore_mandatory=True)
        self.assertTrue(qi_valid_2.name)
