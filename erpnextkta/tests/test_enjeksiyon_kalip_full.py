# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_calisma_karti.api_impl._helpers import (
    _assert_enjeksiyon_kalip_valid,
)
from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import (
    add_alt_operasyon_kaydi,
    update_alt_operasyon_kaydi,
)
from erpnextkta.kta_calisma_karti.api_impl.enjeksiyon import (
    add_enjeksiyon_olcumu,
)


class TestEnjeksiyonKalipFull(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")

        # Ensure OP40 operation exists
        if not frappe.db.exists("KTA Calisma Karti Operasyonlari", "OP40"):
            doc = frappe.new_doc("KTA Calisma Karti Operasyonlari")
            doc.name = "OP40"
            doc.calisma_karti_op = "OP40"
            doc.has_enjeksiyon = 1
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.insert()
        else:
            frappe.db.set_value("KTA Calisma Karti Operasyonlari", "OP40", "has_enjeksiyon", 1)

        # Ensure OP40-E2E alt operasyonu exists
        if not frappe.db.exists("KTA Calisma Karti Alt Operasyonlari", "OP40-E2E"):
            doc = frappe.new_doc("KTA Calisma Karti Alt Operasyonlari")
            doc.parent_operation = "OP40"
            doc.title = "E2E"
            doc.operasyon_tipi = "Blunt"
            doc.is_active = 1
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.insert()

        # Ensure baseline injection molds are seeded for CI environments
        try:
            from erpnextkta.patches.v3_0_3.extract_enjeksiyon_kaliplari import (
                execute as seed_molds,
            )

            seed_molds()
        except (frappe.DuplicateEntryError, frappe.ValidationError) as e:
            frappe.logger("tests").debug(f"seed_molds atlandı: {e}")

        frappe.db.commit()

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.created_cards = []
        self.created_molds = []

        # Find or create a test item with tolerances
        self.item_code = frappe.db.get_value("Item", filters={"disabled": 0}, fieldname="name")
        if not self.item_code:
            self.item_code = "E2E-TEST-ITEM"
            if not frappe.db.exists("Item", self.item_code):
                frappe.get_doc({
                    "doctype": "Item",
                    "item_code": self.item_code,
                    "item_name": self.item_code,
                    "item_group": "Products",
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                }).insert(ignore_permissions=True)

        if not frappe.db.exists("KTA Enjeksiyon Toleranslari", {"hammadde_no": self.item_code}):
            frappe.get_doc({
                "doctype": "KTA Enjeksiyon Toleranslari",
                "hammadde_no": self.item_code,
                "hammadde_kazan_isisi_merkez": 180.0,
                "hammadde_kazan_isisi_tolerans": 40.0,
                "ara_hortum_isisi_merkez": 185.0,
                "ara_hortum_isisi_tolerans": 40.0,
                "kafa_meme_isisi_merkez": 190.0,
                "kafa_meme_isisi_tolerans": 40.0,
                "soguk_su_isisi_min": 10.0,
                "soguk_su_isisi_maks": 25.0,
                "motor_devir_min": 10.0,
                "motor_devir_maks": 60.0,
                "enjeksiyon_zamani_min": 5.0,
                "enjeksiyon_zamani_maks": 30.0,
                "sogutma_zamani_min": 5.0,
                "sogutma_zamani_maks": 30.0,
                "cekme_kuvveti_min": 100.0,
            }).insert(ignore_permissions=True)
            frappe.db.commit()

        # Dedicated test mold (disabled)
        if not frappe.db.exists("KTA Enjeksiyon Kalibi", "E2E-DISABLED-MOLD"):
            frappe.get_doc({
                "doctype": "KTA Enjeksiyon Kalibi",
                "kalip_no": "E2E-DISABLED-MOLD",
                "kalip_adi": "Disabled Test Mold",
                "disabled": 1,
            }).insert(ignore_permissions=True)
            self.created_molds.append("E2E-DISABLED-MOLD")

    def tearDown(self):
        for card_name in self.created_cards:
            if frappe.db.exists("Calisma Karti", card_name):
                frappe.delete_doc("Calisma Karti", card_name, force=1, ignore_permissions=True)

        for mold_name in self.created_molds:
            if frappe.db.exists("KTA Enjeksiyon Kalibi", mold_name):
                frappe.delete_doc("KTA Enjeksiyon Kalibi", mold_name, force=1, ignore_permissions=True)

        frappe.db.commit()
        super().tearDown()

    def _create_test_calisma_karti(self):
        jc = frappe.db.get_value("Job Card", filters={}, fieldname="name")
        ws = frappe.db.get_value("Workstation", filters={}, fieldname="name")
        emp = frappe.db.get_value("Employee", filters={"status": "Active"}, fieldname="name") or "Administrator"

        doc = frappe.new_doc("Calisma Karti")
        doc.is_karti = jc
        doc.operasyon = "OP40"
        doc.is_istasyonu = ws
        doc.operator = emp
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_permissions = True
        doc.flags.ignore_links = True
        doc.insert()
        self.created_cards.append(doc.name)
        frappe.db.commit()
        return doc.name

    def test_01_extracted_molds_populated(self):
        """Verifies that at least 46 injection molds exist from the migration patch."""
        count = frappe.db.count("KTA Enjeksiyon Kalibi")
        self.assertGreaterEqual(count, 46, f"Expected at least 46 molds, found {count}")

        # Verify representative mold
        sample_mold = frappe.db.get_value(
            "KTA Enjeksiyon Kalibi",
            "8718645633",
            ["name", "kalip_no", "disabled", "varsayilan_kalite_sablonu"],
            as_dict=True,
        )
        self.assertIsNotNone(sample_mold, "Mold 8718645633 should exist")
        self.assertEqual(sample_mold.kalip_no, "8718645633")
        self.assertEqual(sample_mold.disabled, 0)
        self.assertTrue(
            bool(sample_mold.varsayilan_kalite_sablonu),
            "Mold 8718645633 should have varsayilan_kalite_sablonu populated",
        )
        self.assertIn("8718645633", sample_mold.varsayilan_kalite_sablonu)

    def test_02_assert_enjeksiyon_kalip_valid(self):
        """Validates _assert_enjeksiyon_kalip_valid behavior on active, disabled, and missing molds."""
        # Active existing mold passes
        _assert_enjeksiyon_kalip_valid("8718645633")
        _assert_enjeksiyon_kalip_valid("  8718645633  ")

        # Empty passes (as non-enjeksiyon or optional flows don't require mold)
        _assert_enjeksiyon_kalip_valid("")
        _assert_enjeksiyon_kalip_valid(None)

        # Non-existent mold throws ValidationError
        with self.assertRaises(frappe.ValidationError):
            _assert_enjeksiyon_kalip_valid("NON-EXISTENT-XYZ-999")

        # Disabled mold throws ValidationError
        with self.assertRaises(frappe.ValidationError):
            _assert_enjeksiyon_kalip_valid("E2E-DISABLED-MOLD")

    def test_03_alt_operasyon_api_kalip_validation(self):
        """Tests adding and updating sub-operation records with valid vs invalid mold."""
        from unittest.mock import patch

        card_name = self._create_test_calisma_karti()

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"), \
             patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):

            # Adding with invalid mold must fail
            with self.assertRaises(frappe.ValidationError):
                add_alt_operasyon_kaydi(
                    calisma_karti=card_name,
                    alt_operasyon="OP40-E2E",
                    kalip_no="NON-EXISTENT-MOLD",
                    hammadde=self.item_code,
                    islem_adedi_1=50,
                )

            # Adding with disabled mold must fail
            with self.assertRaises(frappe.ValidationError):
                add_alt_operasyon_kaydi(
                    calisma_karti=card_name,
                    alt_operasyon="OP40-E2E",
                    kalip_no="E2E-DISABLED-MOLD",
                    hammadde=self.item_code,
                    islem_adedi_1=50,
                )

            # Adding with valid mold must succeed
            ao_id = add_alt_operasyon_kaydi(
                calisma_karti=card_name,
                alt_operasyon="OP40-E2E",
                kalip_no="8718645633",
                hammadde=self.item_code,
                islem_adedi_1=50,
            )
            self.assertTrue(ao_id)

            # Verify saved record has correct mold link
            card = frappe.get_doc("Calisma Karti", card_name)
            saved_ao = next(row for row in card.alt_operasyon_kayitlari if row.name == ao_id)
            self.assertEqual(saved_ao.kalip_no, "8718645633")

            # Updating with invalid mold must fail
            with self.assertRaises(frappe.ValidationError):
                update_alt_operasyon_kaydi(
                    calisma_karti=card_name,
                    row_id=ao_id,
                    alt_operasyon="OP40-E2E",
                    kalip_no="INVALID-UPDATE-MOLD",
                )

    def test_04_enjeksiyon_olcum_api_kalip_validation(self):
        """Tests adding injection measurement with valid vs invalid mold."""
        card_name = self._create_test_calisma_karti()

        base_payload = {
            "kontrol_periyodu": "Başlangıç",
            "hammadde_no": self.item_code,
            "goz_kontrol": 1,
            "cekme_kuvveti_olculen": 120.0,
            "hammadde_kazan_isisi": 180.0,
            "ara_hortum_isisi": 185.0,
            "kafa_meme_isisi": 190.0,
            "soguk_su_isisi": 18.0,
            "motor_devir": 45.0,
            "hammadde_enjeksiyon_zamani": 12.0,
            "sogutma_zamani": 10.0,
        }

        # Adding with invalid mold must fail
        invalid_payload = dict(base_payload, kalip_no="INVALID-MOLD-999")
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(card_name, invalid_payload)

        # Adding with disabled mold must fail
        disabled_payload = dict(base_payload, kalip_no="E2E-DISABLED-MOLD")
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(card_name, disabled_payload)

        # Adding with valid mold must succeed
        valid_payload = dict(base_payload, kalip_no="8718645633")
        res = add_enjeksiyon_olcumu(card_name, valid_payload)
        self.assertEqual(res.get("status"), "success")

        card = frappe.get_doc("Calisma Karti", card_name)
        saved_olcum = card.enjeksiyon_olcumleri[0]
        self.assertEqual(saved_olcum.kalip_no, "8718645633")
