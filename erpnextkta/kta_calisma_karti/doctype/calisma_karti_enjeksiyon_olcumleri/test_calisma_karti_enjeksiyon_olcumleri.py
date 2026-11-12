# Copyright (c) 2026, KTA Endüstri Sistemleri and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_calisma_karti.api_impl.enjeksiyon import (
    add_enjeksiyon_olcumu,
    update_enjeksiyon_olcumu,
)


class TestCalismaKartiEnjeksiyonOlcumleri(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
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

        if not frappe.db.exists("KTA Calisma Karti Alt Operasyonlari", "OP40-0001"):
            doc = frappe.new_doc("KTA Calisma Karti Alt Operasyonlari")
            doc.name = "OP40-0001"
            doc.parent_operation = "OP40"
            doc.title = "0001"
            doc.operasyon_tipi = "Blunt"
            doc.is_active = 1
            doc.flags.ignore_permissions = True
            doc.flags.ignore_mandatory = True
            doc.insert()

        test_molds = [
            "KLP-101", "KLP-102", "KLP-DUP", "KLP-FIRST", "KLP-INITIAL",
            "KLP-LOCK-01", "KLP-LOCK-CHANGED", "KLP-LOCKED", "KLP-MAX",
            "KLP-OP40-01", "KLP-OP40-02", "KLP-POINTS-01", "KLP-RECIPE-01",
            "KLP-REJ-01", "KLP-SHIFT-01", "KLP-TAMPERED", "KLP-TAMPERED-AGAIN",
            "KLP-UNIQ-01", "KLP-UPDATED"
        ]
        for m in test_molds:
            if not frappe.db.exists("KTA Enjeksiyon Kalibi", m):
                mold = frappe.new_doc("KTA Enjeksiyon Kalibi")
                mold.kalip_no = m
                mold.kalip_adi = f"Test Mold {m}"
                mold.disabled = 0
                mold.flags.ignore_permissions = True
                mold.flags.ignore_mandatory = True
                mold.insert()

        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self.item_code = frappe.db.get_value("Item", filters={"disabled": 0}, fieldname="name")
        if not self.item_code:
            self.item_code = "TEST-ENJ-ITEM"
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
        self.docname = doc.name
        frappe.db.commit()

    def tearDown(self):
        if getattr(self, "docname", None) and frappe.db.exists("Calisma Karti", self.docname):
            frappe.delete_doc("Calisma Karti", self.docname, force=1, ignore_permissions=True)
            frappe.db.commit()

    def _get_valid_payload(self, **kwargs):
        payload = {
            "kontrol_periyodu": "Başlangıç",
            "kalip_no": "KLP-101",
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
        payload.update(kwargs)
        return payload

    def test_add_enjeksiyon_olcumu_requires_kalip_no(self):
        """Kalıp No boş girildiğinde hata fırlatıldığını doğrular."""
        payload = self._get_valid_payload(kalip_no="")
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, payload)

    def test_add_enjeksiyon_olcumu_requires_goz_kontrol(self):
        """Göz Kontrol işaretlenmediğinde veya 0 olduğunda ValidationError fırlatıldığını doğrular."""
        payload = self._get_valid_payload(goz_kontrol=0)
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, payload)

        payload_no_goz = self._get_valid_payload()
        payload_no_goz.pop("goz_kontrol", None)
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, payload_no_goz)

    def test_add_enjeksiyon_olcumu_success(self):
        """Kalıp No ve alt_operasyon_kaydi ile başarılı bir şekilde enjeksiyon ölçümü eklendiğini doğrular."""
        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao_row = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-101",
            "hammadde": self.item_code,
        })
        doc.save(ignore_permissions=True)

        payload = self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-101",
            hammadde_no=self.item_code,
            alt_operasyon_kaydi=ao_row.name,
        )
        res = add_enjeksiyon_olcumu(self.docname, payload)
        self.assertEqual(res.get("status"), "success")

        doc.reload()
        self.assertGreater(len(doc.enjeksiyon_olcumleri), 0)
        row = doc.enjeksiyon_olcumleri[-1]
        self.assertEqual(row.kalip_no, "KLP-101")
        self.assertEqual(row.kontrol_periyodu, "Başlangıç")
        self.assertEqual(row.alt_operasyon_kaydi, ao_row.name)

    def test_update_enjeksiyon_olcumu(self):
        """Enjeksiyon ölçümünde Kalıp No ve alt_operasyon_kaydi güncellemesini doğrular."""
        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao1 = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-INITIAL",
            "hammadde": self.item_code,
        })
        ao2 = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-UPDATED",
            "hammadde": self.item_code,
        })
        doc.save(ignore_permissions=True)

        payload = self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-INITIAL",
            hammadde_no=self.item_code,
            alt_operasyon_kaydi=ao1.name,
        )
        add_enjeksiyon_olcumu(self.docname, payload)
        doc.reload()
        rowname = doc.enjeksiyon_olcumleri[-1].name

        # Update without kalip_no should fail
        with self.assertRaises(frappe.ValidationError):
            update_enjeksiyon_olcumu(self.docname, rowname, self._get_valid_payload(
                kontrol_periyodu="Ara",
                kalip_no="",
            ))

        # Update without goz_kontrol should fail
        with self.assertRaises(frappe.ValidationError):
            update_enjeksiyon_olcumu(self.docname, rowname, self._get_valid_payload(
                kontrol_periyodu="Ara",
                kalip_no="KLP-UPDATED",
                goz_kontrol=0,
            ))

        # Update with valid kalip_no, goz_kontrol and updated alt_operasyon_kaydi should succeed
        res = update_enjeksiyon_olcumu(self.docname, rowname, self._get_valid_payload(
            kontrol_periyodu="Bitiş",
            kalip_no="KLP-UPDATED",
            alt_operasyon_kaydi=ao2.name,
        ))
        self.assertEqual(res.get("status"), "success")

        doc.reload()
        updated_row = next(r for r in doc.enjeksiyon_olcumleri if r.name == rowname)
        self.assertEqual(updated_row.kalip_no, "KLP-UPDATED")
        self.assertEqual(updated_row.kontrol_periyodu, "Bitiş")
        self.assertEqual(updated_row.alt_operasyon_kaydi, ao2.name)

    def test_add_enjeksiyon_olcumu_rejects_nonexistent_alt_operasyon_kaydi(self):
        """Bağlı alt operasyon bu karta ait olmadığında ValidationError fırlatıldığını doğrular."""
        payload = {
            "kontrol_periyodu": "Başlangıç",
            "kalip_no": "KLP-101",
            "hammadde_no": self.item_code,
            "goz_kontrol": 1,
            "alt_operasyon_kaydi": "NON-EXISTENT-AO-999",
        }
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, payload)

    def test_add_enjeksiyon_olcumu_rejects_qc_rejected_alt_operasyon(self):
        """Kalite tarafından reddedilmiş alt operasyona operatör tarafından yeni ölçüm eklenemediğini doğrular."""
        from erpnextkta.tests.test_utils import create_test_operator

        frappe.db.set_value("KTA Calisma Karti Operasyonlari", "OP40", "alt_operasyon_bazli_kalite", 1)

        qi_name = "QI-TEST-REJECTED"
        if not frappe.db.exists("Quality Inspection", qi_name):
            frappe.db.sql("""
                INSERT INTO `tabQuality Inspection` (name, docstatus, status, creation, modified, modified_by)
                VALUES (%s, 1, 'Rejected', NOW(), NOW(), 'Administrator')
            """, (qi_name,))

        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao_row = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-101",
            "hammadde": self.item_code,
            "quality_inspection": qi_name,
            "quality_inspection_status": "Reddedildi",
        })
        operator_email = "test_enj_op@kta.com"
        create_test_operator(operator_email, "Test Enj Operator")
        if not frappe.db.exists("User", operator_email):
            frappe.get_doc({
                "doctype": "User",
                "email": operator_email,
                "first_name": "Test Enj",
                "roles": [{"role": "Manufacturing User"}],
            }).insert(ignore_permissions=True)
        frappe.db.set_value("Employee", operator_email, "user_id", operator_email)

        doc.operator = operator_email
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        orig_user = frappe.session.user
        try:
            frappe.set_user(operator_email)
            payload = self._get_valid_payload(
                kontrol_periyodu="Başlangıç",
                kalip_no="KLP-101",
                hammadde_no=self.item_code,
                alt_operasyon_kaydi=ao_row.name,
            )
            with self.assertRaises(frappe.ValidationError):
                add_enjeksiyon_olcumu(self.docname, payload)
        finally:
            frappe.set_user(orig_user)

    def test_add_enjeksiyon_olcumu_allows_approved_alt_operasyon_for_ara_and_bitis(self):
        """Kalite onayı almış alt operasyona 'Ara' ve 'Bitiş' ölçümlerinin eklenebildiğini doğrular."""
        frappe.db.set_value("KTA Calisma Karti Operasyonlari", "OP40", "alt_operasyon_bazli_kalite", 1)

        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao_row = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-101",
            "hammadde": self.item_code,
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        # Add initial measurement
        add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-101",
            hammadde_no=self.item_code,
            alt_operasyon_kaydi=ao_row.name,
        ))

        # Simulate QC approval on the sub-operation
        doc.reload()
        ao_saved = next(r for r in doc.alt_operasyon_kayitlari if r.name == ao_row.name)
        ao_saved.quality_inspection_status = "Onaylandı"
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        # Adding Ara should succeed even though quality_inspection_status is Onaylandı
        res_ara = add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
            kontrol_periyodu="Ara",
            kalip_no="KLP-101",
            hammadde_no=self.item_code,
            alt_operasyon_kaydi=ao_row.name,
        ))
        self.assertEqual(res_ara.get("status"), "success")

        # Adding Bitiş should also succeed
        res_bitis = add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
            kontrol_periyodu="Bitiş",
            kalip_no="KLP-101",
            hammadde_no=self.item_code,
            alt_operasyon_kaydi=ao_row.name,
        ))
        self.assertEqual(res_bitis.get("status"), "success")

    def test_enjeksiyon_first_measurement_must_be_baslangic(self):
        """Alt operasyona girilen ilk ölçümün Başlangıç periyodu olması gerektiğini doğrular."""
        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao_row = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-FIRST",
            "hammadde": self.item_code,
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
                kontrol_periyodu="Ara",
                kalip_no="KLP-FIRST",
                hammadde_no=self.item_code,
                alt_operasyon_kaydi=ao_row.name,
            ))

    def test_enjeksiyon_rejects_duplicate_period(self):
        """Aynı alt operasyona mükerrer kontrol periyodu girilemeyeceğini doğrular."""
        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao_row = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-DUP",
            "hammadde": self.item_code,
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        # First Başlangıç
        add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-DUP",
            hammadde_no=self.item_code,
            alt_operasyon_kaydi=ao_row.name,
        ))

        # Second Başlangıç must fail
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
                kontrol_periyodu="Başlangıç",
                kalip_no="KLP-DUP",
                hammadde_no=self.item_code,
                alt_operasyon_kaydi=ao_row.name,
            ))

    def test_enjeksiyon_max_3_measurements(self):
        """Bir alt operasyona 3'ten fazla ölçüm kaydedilemeyeceğini doğrular."""
        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao_row = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-MAX",
            "hammadde": self.item_code,
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        for period in ["Başlangıç", "Ara", "Bitiş"]:
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
                kontrol_periyodu=period,
                kalip_no="KLP-MAX",
                hammadde_no=self.item_code,
                alt_operasyon_kaydi=ao_row.name,
            ))

        # 4th measurement must raise ValidationError
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(
                kontrol_periyodu="Ekstra",
                kalip_no="KLP-MAX",
                hammadde_no=self.item_code,
                alt_operasyon_kaydi=ao_row.name,
            ))

    def test_update_enjeksiyon_olcumu_rejects_qc_locked_alt_operasyon(self):
        """Kalite belgesi bağlanmış alt operasyona operatör tarafından ölçüm atanamadığını doğrular."""
        from erpnextkta.tests.test_utils import create_test_operator

        frappe.db.set_value("KTA Calisma Karti Operasyonlari", "OP40", "alt_operasyon_bazli_kalite", 1)

        qi_name = "QI-TEST-DUMMY"
        if not frappe.db.exists("Quality Inspection", qi_name):
            frappe.db.sql("""
                INSERT INTO `tabQuality Inspection` (name, docstatus, status, creation, modified, modified_by)
                VALUES (%s, 1, 'Accepted', NOW(), NOW(), 'Administrator')
            """, (qi_name,))

        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao1 = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-101",
            "hammadde": self.item_code,
        })
        ao2_locked = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-102",
            "hammadde": self.item_code,
            "quality_inspection": "QI-TEST-DUMMY",
            "quality_inspection_status": "Onaylandı",
        })
        operator_email = "test_enj_op@kta.com"
        create_test_operator(operator_email, "Test Enj Operator")
        if not frappe.db.exists("User", operator_email):
            frappe.get_doc({
                "doctype": "User",
                "email": operator_email,
                "first_name": "Test Enj",
                "roles": [{"role": "Manufacturing User"}],
            }).insert(ignore_permissions=True)
        frappe.db.set_value("Employee", operator_email, "user_id", operator_email)

        doc.operator = operator_email
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        payload = self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-101",
            hammadde_no=self.item_code,
            alt_operasyon_kaydi=ao1.name,
        )
        add_enjeksiyon_olcumu(self.docname, payload)
        doc.reload()
        rowname = doc.enjeksiyon_olcumleri[-1].name

        orig_user = frappe.session.user
        try:
            frappe.set_user(operator_email)
            with self.assertRaises(frappe.ValidationError):
                update_enjeksiyon_olcumu(self.docname, rowname, self._get_valid_payload(
                    kontrol_periyodu="Ara",
                    kalip_no="KLP-102",
                    hammadde_no=self.item_code,
                    alt_operasyon_kaydi=ao2_locked.name,
                ))
        finally:
            frappe.set_user(orig_user)

    def test_enjeksiyon_cekme_kuvveti_must_be_min_100(self):
        """Çekme kuvveti ölçülen değerinin en az 100 N olması gerektiğini doğrular."""
        # 0 N must fail
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(cekme_kuvveti_olculen=0))

        # None / missing must fail
        with self.assertRaises(frappe.ValidationError):
            payload = self._get_valid_payload()
            payload.pop("cekme_kuvveti_olculen", None)
            add_enjeksiyon_olcumu(self.docname, payload)

        # 99.9 N must fail
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(cekme_kuvveti_olculen=99.9))

        # 100 N must pass
        res = add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(cekme_kuvveti_olculen=100.0))
        self.assertEqual(res.get("status"), "success")

    def test_enjeksiyon_parameters_rejects_zero_or_empty(self):
        """Tüm enjeksiyon proses parametrelerinin zorunlu ve > 0 olması gerektiğini doğrular."""
        param_fields = [
            "hammadde_kazan_isisi",
            "ara_hortum_isisi",
            "kafa_meme_isisi",
            "soguk_su_isisi",
            "motor_devir",
            "hammadde_enjeksiyon_zamani",
            "sogutma_zamani",
        ]
        for field in param_fields:
            with self.subTest(field=field):
                # 0 must fail
                with self.assertRaises(frappe.ValidationError):
                    add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(**{field: 0}))

                # None must fail
                with self.assertRaises(frappe.ValidationError):
                    add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(**{field: None}))

    def test_enjeksiyon_locks_kalip_and_hammadde_to_sub_operasyon(self):
        """Ölçüm alt operasyona bağlı olduğunda kalıp_no ve hammadde_no'nun alt operasyondan kilitlendiğini doğrular."""
        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao_row = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-LOCKED",
            "hammadde": self.item_code,
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        # Add measurement trying to pass different kalip_no and hammadde_no
        payload = self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-TAMPERED",
            hammadde_no="TAMPERED-MATERIAL",
            alt_operasyon_kaydi=ao_row.name,
        )
        res = add_enjeksiyon_olcumu(self.docname, payload)
        self.assertEqual(res.get("status"), "success")

        doc.reload()
        row = doc.enjeksiyon_olcumleri[-1]
        self.assertEqual(row.kalip_no, "KLP-LOCKED")
        self.assertEqual(row.hammadde_no, self.item_code)

        # Update measurement trying to tamper with kalip_no and hammadde_no
        update_enjeksiyon_olcumu(self.docname, row.name, self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-TAMPERED-AGAIN",
            hammadde_no="TAMPERED-MATERIAL-AGAIN",
            alt_operasyon_kaydi=ao_row.name,
        ))
        doc.reload()
        updated_row = next(r for r in doc.enjeksiyon_olcumleri if r.name == row.name)
        self.assertEqual(updated_row.kalip_no, "KLP-LOCKED")
        self.assertEqual(updated_row.hammadde_no, self.item_code)

    def test_enjeksiyon_rejects_material_without_tolerances(self):
        """Tolerans parametresi tanımlanmamış hammadde için ölçüm eklenemeyeceğini doğrular."""
        raw_code = "ITEM-NO-TOLERANCE"
        if frappe.db.exists("KTA Enjeksiyon Toleranslari", {"hammadde_no": raw_code}):
            frappe.delete_doc("KTA Enjeksiyon Toleranslari", raw_code, force=1, ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(hammadde_no=raw_code))

    def test_enjeksiyon_rejects_out_of_tolerance_center_parameter(self):
        """Merkez ± tolerans sınırları dışındaki değerlerin reddedildiğini doğrular."""
        # Kazan isisi merkez: 180, tolerans: 40 -> geçerli aralık: 140 - 220
        # 225 out of tolerance
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(hammadde_kazan_isisi=225.0))

        # 135 out of tolerance
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(hammadde_kazan_isisi=135.0))

    def test_enjeksiyon_rejects_out_of_tolerance_range_parameter(self):
        """Min - maks aralığı dışındaki proses parametrelerinin reddedildiğini doğrular."""
        # Soğuk su ısısı: min 10, maks 25
        # 30.0 out of tolerance
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(soguk_su_isisi=30.0))

        # 5.0 out of tolerance
        with self.assertRaises(frappe.ValidationError):
            add_enjeksiyon_olcumu(self.docname, self._get_valid_payload(soguk_su_isisi=5.0))

    def test_enjeksiyon_accepts_valid_tolerances_and_populates_hedefs(self):
        """Tolerans sınırları içindeki ölçümün kabul edildiğini ve hedef alanlarının doldurulduğunu doğrular."""
        res = add_enjeksiyon_olcumu(self.docname, self._get_valid_payload())
        self.assertEqual(res.get("status"), "success")

        doc = frappe.get_doc("Calisma Karti", self.docname)
        row = doc.enjeksiyon_olcumleri[-1]
        self.assertEqual(row.hedef_hammadde_kazan_isisi_merkez, 180.0)
        self.assertEqual(row.hedef_hammadde_kazan_isisi_tolerans, 40.0)
        self.assertEqual(row.hedef_soguk_su_isisi_min, 10.0)
        self.assertEqual(row.hedef_soguk_su_isisi_maks, 25.0)

    def test_op40_alt_operasyon_requires_kalip_no(self):
        """OP40 operasyonunda alt işlem eklenirken Kalıp No girilmesinin zorunlu olduğunu doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import add_alt_operasyon_kaydi
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        doc.operasyon = "OP40"
        doc.flags.ignore_links = True
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
        doc.flags.ignore_links = True
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
                expected_uom = frappe.db.get_value("Item", self.item_code, "stock_uom")
                self.assertEqual(row.uom, expected_uom)

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

    def test_calculate_enjeksiyon_tuketim(self):
        """İş emri reçetesine göre adetten kg tüketim hesaplamasını doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import _calculate_enjeksiyon_tuketim
        from unittest.mock import patch

        with patch("frappe.db.get_value") as mock_val:
            with patch("frappe.get_all") as mock_get_all:
                mock_val.side_effect = lambda dt, name, field, *a, **k: 5000.0 if dt == "Work Order" and field == "qty" else "kg"
                mock_get_all.return_value = [frappe._dict(required_qty=30.0, stock_uom="kg")]

                # 500 adet üretildiğinde 30/5000 * 500 = 3.0 kg olmalı
                tuketim, uom = _calculate_enjeksiyon_tuketim("WO-001", "PLASTIC-RAW", 500.0)
                self.assertEqual(tuketim, 3.0)
                self.assertEqual(uom, "kg")

                # 600 adet üretildiğinde 30/5000 * 600 = 3.6 kg olmalı
                tuketim, uom = _calculate_enjeksiyon_tuketim("WO-001", "PLASTIC-RAW", 600.0)
                self.assertEqual(tuketim, 3.6)
                self.assertEqual(uom, "kg")

    def test_enjeksiyon_calculates_consumption_from_work_order_recipe(self):
        """Operatör adet girdiğinde alt operasyon kaydında işlem adedi korunurken tüketimin kg olarak hesaplandığını doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import (
            add_alt_operasyon_kaydi,
            update_alt_operasyon_kaydi,
        )
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        doc.operasyon = "OP40"
        doc.custom_work_order = "WO-TEST-RECIPE"
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                with patch(
                    "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._calculate_enjeksiyon_tuketim",
                    side_effect=lambda wo, mat, qty: (round(float(qty) * 0.006, 4), "kg"),
                ):
                    row_id = add_alt_operasyon_kaydi(
                        calisma_karti=self.docname,
                        alt_operasyon="OP40-0001",
                        hammadde=self.item_code,
                        kalip_no="KLP-RECIPE-01",
                        islem_adedi_1=500.0,
                    )
                    self.assertTrue(bool(row_id))

                    doc.reload()
                    row = next(r for r in doc.alt_operasyon_kayitlari if r.name == row_id)
                    self.assertEqual(row.islem_adedi_1, 500.0)
                    self.assertEqual(row.adet, 3.0)
                    self.assertEqual(row.uom, "kg")

                    # Güncelleme senaryosu
                    update_alt_operasyon_kaydi(
                        calisma_karti=self.docname,
                        row_id=row_id,
                        alt_operasyon="OP40-0001",
                        hammadde=self.item_code,
                        kalip_no="KLP-RECIPE-01",
                        islem_adedi_1=600.0,
                    )
                    doc.reload()
                    row = next(r for r in doc.alt_operasyon_kayitlari if r.name == row_id)
                    self.assertEqual(row.islem_adedi_1, 600.0)
                    self.assertEqual(row.adet, 3.6)
                    self.assertEqual(row.uom, "kg")

    def test_op40_alt_operasyon_unique_kalip_and_hammadde(self):
        """Aynı çalışma kartında aynı kalıp ve aynı hammaddeye sahip ikinci bir aktif alt işlem eklenemeyeceğini doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import add_alt_operasyon_kaydi
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        doc.operasyon = "OP40"
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                # 1. İlk kalıp + hammadde ekleme başarılı olmalı
                add_alt_operasyon_kaydi(
                    calisma_karti=self.docname,
                    alt_operasyon="OP40-0001",
                    hammadde="ITEM-TEST-A",
                    kalip_no="KLP-UNIQ-01",
                )

                # 2. Aynı kalıp ve aynı hammadde tekrar eklenmek istendiğinde ValidationError fırlatmalı
                with self.assertRaises(frappe.ValidationError):
                    add_alt_operasyon_kaydi(
                        calisma_karti=self.docname,
                        alt_operasyon="OP40-0001",
                        hammadde="ITEM-TEST-A",
                        kalip_no="KLP-UNIQ-01",
                    )

                # 3. Aynı kalıp fakat FARKLI bir hammadde ile eklenmek istendiğinde başarılı olmalı (Seçenek C)
                row2 = add_alt_operasyon_kaydi(
                    calisma_karti=self.docname,
                    alt_operasyon="OP40-0001",
                    hammadde="ITEM-TEST-B",
                    kalip_no="KLP-UNIQ-01",
                )
                self.assertTrue(bool(row2))

    def test_enjeksiyon_allows_updating_quantity_after_qc_approval(self):
        """Kalite onayı almış enjeksiyon alt işleminde operatörün vardiya sonu işlem adedini güncelleyebildiğini doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import update_alt_operasyon_kaydi
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-SHIFT-01",
            "hammadde": self.item_code,
            "islem_adedi_1": 1,
            "quality_inspection": "QI-TEST-DUMMY",
            "quality_inspection_status": "Onaylandı",
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.has_qc_role", return_value=False):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
                with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                    update_alt_operasyon_kaydi(
                        calisma_karti=self.docname,
                        row_id=ao.name,
                        alt_operasyon="OP40-0001",
                        hammadde=self.item_code,
                        kalip_no="KLP-SHIFT-01",
                        islem_adedi_1=350,
                    )
                    doc.reload()
                    row = next(r for r in doc.alt_operasyon_kayitlari if r.name == ao.name)
                    self.assertEqual(row.islem_adedi_1, 350)

    def test_enjeksiyon_rejects_updating_mold_or_material_after_qc_approval(self):
        """Kalite onayı almış enjeksiyon alt işleminde operatörün kalıp veya hammaddeyi değiştirmesinin engellendiğini doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import update_alt_operasyon_kaydi
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-LOCK-01",
            "hammadde": self.item_code,
            "islem_adedi_1": 1,
            "quality_inspection": "QI-TEST-DUMMY",
            "quality_inspection_status": "Onaylandı",
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.has_qc_role", return_value=False):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
                with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                    # Kalıp değiştirme reddedilmeli
                    with self.assertRaises(frappe.ValidationError):
                        update_alt_operasyon_kaydi(
                            calisma_karti=self.docname,
                            row_id=ao.name,
                            alt_operasyon="OP40-0001",
                            hammadde=self.item_code,
                            kalip_no="KLP-LOCK-CHANGED",
                            islem_adedi_1=10,
                        )

                    # Hammadde değiştirme reddedilmeli
                    with self.assertRaises(frappe.ValidationError):
                        update_alt_operasyon_kaydi(
                            calisma_karti=self.docname,
                            row_id=ao.name,
                            alt_operasyon="OP40-0001",
                            hammadde="ITEM-DIFFERENT",
                            kalip_no="KLP-LOCK-01",
                            islem_adedi_1=10,
                        )

    def test_enjeksiyon_rejects_updating_quantity_if_qc_rejected(self):
        """Kalite tarafından reddedilmiş enjeksiyon alt işleminde operatörün güncelleme yapamadığını doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import update_alt_operasyon_kaydi
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        ao = doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "KLP-REJ-01",
            "hammadde": self.item_code,
            "islem_adedi_1": 1,
            "quality_inspection": "QI-TEST-REJ",
            "quality_inspection_status": "Reddedildi",
        })
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.has_qc_role", return_value=False):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
                with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                    with self.assertRaises(frappe.ValidationError):
                        update_alt_operasyon_kaydi(
                            calisma_karti=self.docname,
                            row_id=ao.name,
                            alt_operasyon="OP40-0001",
                            hammadde=self.item_code,
                            kalip_no="KLP-REJ-01",
                            islem_adedi_1=100,
                        )

    def test_enjeksiyon_awards_energy_points_on_3_of_3(self):
        """Enjeksiyon alt operasyonunda Başlangıç, Ara ve Bitiş periyotları (3/3) tamamlandığında 3 Enerji Puanı verildiğini doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.alt_operasyon import add_alt_operasyon_kaydi
        from unittest.mock import patch

        doc = frappe.get_doc("Calisma Karti", self.docname)
        doc.operasyon = "OP40"
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)

        with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_hammadde_allowed"):
            with patch("erpnextkta.kta_calisma_karti.api_impl.alt_operasyon._assert_within_wo_limits"):
                ao_id = add_alt_operasyon_kaydi(
                    calisma_karti=self.docname,
                    alt_operasyon="OP40-0001",
                    hammadde=self.item_code,
                    kalip_no="KLP-POINTS-01",
                )

        # 1. Başlangıç ölçümü ekle -> Henüz 3/3 değil, puan 0
        p1 = self._get_valid_payload(
            kontrol_periyodu="Başlangıç",
            kalip_no="KLP-POINTS-01",
            alt_operasyon_kaydi=ao_id,
        )
        r1 = add_enjeksiyon_olcumu(self.docname, p1)
        self.assertEqual(r1.get("earned_points"), 0)

        # 2. Ara ölçümü ekle -> Henüz 3/3 değil, puan 0
        p2 = self._get_valid_payload(
            kontrol_periyodu="Ara",
            kalip_no="KLP-POINTS-01",
            alt_operasyon_kaydi=ao_id,
        )
        r2 = add_enjeksiyon_olcumu(self.docname, p2)
        self.assertEqual(r2.get("earned_points"), 0)

        # 3. Bitiş ölçümü ekle -> 3/3 tamamlandı, 3 puan verilmeli!
        p3 = self._get_valid_payload(
            kontrol_periyodu="Bitiş",
            kalip_no="KLP-POINTS-01",
            alt_operasyon_kaydi=ao_id,
        )
        r3 = add_enjeksiyon_olcumu(self.docname, p3)
        self.assertEqual(r3.get("earned_points"), 3)

        # Veritabanında Energy Point Log oluştuğunu doğrula
        log = frappe.db.get_value(
            "Energy Point Log",
            {
                "reference_doctype": "Calisma Karti",
                "reference_name": self.docname,
                "rule": "Enjeksiyon 3/3 Ölçüm Tamamlama",
                "reverted": 0,
            },
            ["points", "user"],
            as_dict=True,
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.points, 3)

        # Temizlik: Eklenen test logunu sil
        frappe.db.sql("DELETE FROM `tabEnergy Point Log` WHERE reference_name = %s", (self.docname,))
        frappe.db.commit()

    def test_enjeksiyon_protocol_renders_quality_inspection_and_approver(self):
        """Enjeksiyon protokol belgesinde alt operasyon kalite belgesi ve onaylayan kişinin görüntülendiğini doğrular."""
        from erpnextkta.kta_calisma_karti.api_impl.print_protocol import get_job_card_protocols_html

        doc = frappe.get_doc("Calisma Karti", self.docname)
        doc.flags.ignore_links = True
        doc.append("enjeksiyon_olcumleri", {
            "kontrol_periyodu": "Başlangıç",
            "kalip_no": "8750306384",
            "hammadde_no": self.item_code,
            "goz_kontrol": 1,
            "cekme_kuvveti_olculen": 105.0,
            "hammadde_kazan_isisi": 180.0,
            "ara_hortum_isisi": 180.0,
            "kafa_meme_isisi": 180.0,
            "soguk_su_isisi": 18.0,
            "motor_devir": 20.0,
            "hammadde_enjeksiyon_zamani": 15.0,
            "sogutma_zamani": 15.0,
            "operator": doc.operator,
        })
        doc.append("alt_operasyon_kayitlari", {
            "alt_operasyon": "OP40-0001",
            "kalip_no": "8750306384",
            "hammadde": self.item_code,
            "adet": 1.0,
            "uom": "kg",
            "quality_inspection": "QI-TEST-DUMMY",
            "quality_inspection_status": "Onaylandı",
        })
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)

        res = get_job_card_protocols_html(doc.is_karti)
        self.assertIsNotNone(res)
        html = res.get("html", "")
        self.assertIn("QI-TEST-DUMMY", html)
        self.assertIn(frappe._("Enjeksiyon Ölçüm Protokol Belgesi"), html)


def run_tests():
    import unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCalismaKartiEnjeksiyonOlcumleri)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise Exception("Tests failed!")
    return "All tests passed successfully!"
