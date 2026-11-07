# Copyright (c) 2026, KTA Endüstri Sistemleri and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_calisma_karti.api_impl.enjeksiyon import (
    add_enjeksiyon_olcumu,
    update_enjeksiyon_olcumu,
)


class TestCalismaKartiEnjeksiyonOlcumleri(FrappeTestCase):
    def setUp(self):
        jc = frappe.db.get_value("Job Card", filters={}, fieldname="name")
        op = frappe.db.get_value("KTA Calisma Karti Operasyonlari", filters={}, fieldname="name")
        ws = frappe.db.get_value("Workstation", filters={}, fieldname="name")
        emp = frappe.db.get_value("Employee", filters={"status": "Active"}, fieldname="name")
        self.item_code = frappe.db.get_value("Item", filters={"disabled": 0}, fieldname="name")

        doc = frappe.new_doc("Calisma Karti")
        doc.is_karti = jc
        doc.operasyon = op
        doc.is_istasyonu = ws
        doc.operator = emp
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_permissions = True
        doc.flags.ignore_links = True
        doc.insert()
        self.docname = doc.name
        frappe.db.commit()

    def tearDown(self):
        if getattr(self, "docname", None) and frappe.db.exists("Calisma Karti", self.docname):
            frappe.delete_doc("Calisma Karti", self.docname, force=1, ignore_permissions=True)
            frappe.db.commit()

    def test_add_enjeksiyon_olcumu_requires_kalip_no(self):
        """Kalıp No boş girildiğinde hata fırlatıldığını doğrular."""
        payload = {
            "kontrol_periyodu": "Başlangıç",
            "kalip_no": "",
            "hammadde_no": self.item_code,
        }
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, payload)

    def test_add_enjeksiyon_olcumu_success(self):
        """Kalıp No ile başarılı bir şekilde enjeksiyon ölçümü eklendiğini doğrular."""
        payload = {
            "kontrol_periyodu": "Başlangıç",
            "kalip_no": "KLP-101",
            "hammadde_no": self.item_code,
            "hammadde_kazan_isisi": 180.5,
            "goz_kontrol": 1,
        }
        res = add_enjeksiyon_olcumu(self.docname, payload)
        self.assertEqual(res.get("status"), "success")

        doc = frappe.get_doc("Calisma Karti", self.docname)
        self.assertTrue(len(doc.enjeksiyon_olcumleri) > 0)
        row = doc.enjeksiyon_olcumleri[-1]
        self.assertEqual(row.kalip_no, "KLP-101")
        self.assertEqual(row.kontrol_periyodu, "Başlangıç")

    def test_update_enjeksiyon_olcumu(self):
        """Enjeksiyon ölçümünde Kalıp No güncellemesini doğrular."""
        payload = {
            "kontrol_periyodu": "Ara",
            "kalip_no": "KLP-INITIAL",
            "hammadde_no": self.item_code,
        }
        add_enjeksiyon_olcumu(self.docname, payload)
        doc = frappe.get_doc("Calisma Karti", self.docname)
        rowname = doc.enjeksiyon_olcumleri[-1].name

        # Update without kalip_no should fail
        with self.assertRaises(frappe.ValidationError):
            update_enjeksiyon_olcumu(self.docname, rowname, {
                "kontrol_periyodu": "Ara",
                "kalip_no": "",
                "hammadde_no": self.item_code,
            })

        # Update with valid kalip_no should succeed
        res = update_enjeksiyon_olcumu(self.docname, rowname, {
            "kontrol_periyodu": "Bitiş",
            "kalip_no": "KLP-UPDATED",
            "hammadde_no": self.item_code,
        })
        self.assertEqual(res.get("status"), "success")

        doc.reload()
        updated_row = next(r for r in doc.enjeksiyon_olcumleri if r.name == rowname)
        self.assertEqual(updated_row.kalip_no, "KLP-UPDATED")
        self.assertEqual(updated_row.kontrol_periyodu, "Bitiş")

    def test_op40_alt_operasyon_requires_kalip_no(self):
        """OP40 operasyonunda alt işlem eklenirken Kalıp No girilmesinin zorunlu olduğunu doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import add_alt_operasyon_kaydi
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        doc.operasyon = "OP40"
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                with self.assertRaises(frappe.ValidationError):
                    add_alt_operasyon_kaydi(
                        calisma_karti=self.docname,
                        alt_operasyon="OP40-0001",
                        hammadde=self.item_code,
                        kalip_no="",
                    )

    def test_op40_alt_operasyon_success_and_update(self):
        """OP40 operasyonunda alt işlem ekleme ve güncellemede Kalıp No'nun başarıyla kaydedildiğini doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import (
            add_alt_operasyon_kaydi,
            update_alt_operasyon_kaydi,
        )
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        doc.operasyon = "OP40"
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                row_id = add_alt_operasyon_kaydi(
                    calisma_karti=self.docname,
                    alt_operasyon="OP40-0001",
                    hammadde=self.item_code,
                    kalip_no="KLP-OP40-01",
                )
                self.assertTrue(bool(row_id))

                doc.reload()
                row = next(r for r in doc.alt_operasyon_kayitlari if r.name == row_id)
                self.assertEqual(row.kalip_no, "KLP-OP40-01")

                # Update kalip_no
                update_alt_operasyon_kaydi(
                    calisma_karti=self.docname,
                    row_id=row_id,
                    alt_operasyon="OP40-0001",
                    hammadde=self.item_code,
                    kalip_no="KLP-OP40-02",
                )
                doc.reload()
                row = next(r for r in doc.alt_operasyon_kayitlari if r.name == row_id)
                self.assertEqual(row.kalip_no, "KLP-OP40-02")


def run_tests():
    import unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCalismaKartiEnjeksiyonOlcumleri)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise Exception("Tests failed!")
    return "All tests passed successfully!"
