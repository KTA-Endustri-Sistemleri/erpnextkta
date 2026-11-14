# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest

import frappe
from frappe.model.workflow import get_workflow, is_transition_condition_satisfied


class TestPurchaseReceiptWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.db:
            import os

            os.chdir("/home/frappe/frappe-bench/sites")
            frappe.init(site="old.kta-endustri.com.tr")
            frappe.connect()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_kta_gumruk_sorumlusu_role_exists(self):
        """KTA Gümrük Sorumlusu rolü veritabanında mevcut olmalıdır."""
        self.assertTrue(
            frappe.db.exists("Role", "KTA Gümrük Sorumlusu"),
            "KTA Gümrük Sorumlusu rolü mevcut değil!",
        )

    def test_purchase_receipt_dispute_fields_exist(self):
        """Purchase Receipt üzerinde uyuşmazlık alanları tanımlı olmalıdır."""
        meta = frappe.get_meta("Purchase Receipt")
        self.assertTrue(
            meta.has_field("custom_uyusmazlik_nedeni"),
            "custom_uyusmazlik_nedeni alanı mevcut değil!",
        )
        self.assertTrue(
            meta.has_field("custom_uyusmazlik_aciklamasi"),
            "custom_uyusmazlik_aciklamasi alanı mevcut değil!",
        )

    def test_workflow_state_mal_kabul_uyusmazligi_exists(self):
        """Mal Kabul Uyuşmazlığı iş akışı statüsü mevcut olmalıdır."""
        self.assertTrue(
            frappe.db.exists("Workflow State", "Mal Kabul Uyuşmazlığı"),
            "Mal Kabul Uyuşmazlığı workflow state mevcut değil!",
        )

    def test_workflow_states_allow_edit_isolation(self):
        """Gümrük ve uyuşmazlık statülerinde allow_edit KTA Gümrük Sorumlusu olmalıdır."""
        wf = frappe.get_doc("Workflow", "KTA Mal Giris Sureci")
        states_map = {s.state: s.allow_edit for s in wf.states}

        self.assertEqual(
            states_map.get("Yolda"),
            "KTA Gümrük Sorumlusu",
            "Yolda statüsü allow_edit KTA Gümrük Sorumlusu olmalıdır!",
        )
        self.assertEqual(
            states_map.get("Antrepoda"),
            "KTA Gümrük Sorumlusu",
            "Antrepoda statüsü allow_edit KTA Gümrük Sorumlusu olmalıdır!",
        )
        self.assertEqual(
            states_map.get("Gümrüklemede"),
            "KTA Gümrük Sorumlusu",
            "Gümrüklemede statüsü allow_edit KTA Gümrük Sorumlusu olmalıdır!",
        )
        self.assertIn(
            "Mal Kabul Uyuşmazlığı",
            states_map,
            "Mal Kabul Uyuşmazlığı statüsü workflow'da bulunamadı!",
        )

    def test_customs_transitions_restricted_to_kta_gumruk_sorumlusu(self):
        """Transit ve gümrük aşamalarındaki geçişler yalnızca KTA Gümrük Sorumlusu rolüne izin vermelidir."""
        wf = frappe.get_doc("Workflow", "KTA Mal Giris Sureci")

        for t in wf.transitions:
            if t.state == "Mal Girişe Hazır" and t.action == "İthalat Başlat":
                self.assertEqual(
                    t.allowed,
                    "KTA Gümrük Sorumlusu",
                    "İthalat Başlat geçişi KTA Gümrük Sorumlusu rolüne kilitli olmalı!",
                )
            elif t.state in ("Yolda", "Antrepoda", "Gümrüklemede"):
                self.assertEqual(
                    t.allowed,
                    "KTA Gümrük Sorumlusu",
                    f"{t.state} -> {t.action} geçişi KTA Gümrük Sorumlusu rolüne kilitli olmalı! (Mevcut: {t.allowed})",
                )

    def test_step_by_step_rollback_transitions(self):
        """Geri dönüş zinciri adım adım geriye işlemelidir."""
        wf = frappe.get_doc("Workflow", "KTA Mal Giris Sureci")
        rollback_map = {
            (t.state, t.action): t.next_state
            for t in wf.transitions
            if t.action in ("Reject", "Gümrüğe İade")
        }

        # Gümrüklemede Reject -> Antrepoda
        self.assertEqual(
            rollback_map.get(("Gümrüklemede", "Reject")),
            "Antrepoda",
            "Gümrüklemede Reject işlemi Antrepoda statüsüne dönmelidir!",
        )
        # Antrepoda Reject -> Yolda
        self.assertEqual(
            rollback_map.get(("Antrepoda", "Reject")),
            "Yolda",
            "Antrepoda Reject işlemi Yolda statüsüne dönmelidir!",
        )
        # Yolda Reject -> Mal Girişe Hazır
        self.assertEqual(
            rollback_map.get(("Yolda", "Reject")),
            "Mal Girişe Hazır",
            "Yolda Reject işlemi Mal Girişe Hazır statüsüne dönmelidir!",
        )

    def test_mal_giris_reject_replaced_with_uyusmazlik(self):
        """Mal Giriş aşamasında doğrudan Yolda'ya ret olmamalı, Uyuşmazlık Bildir ile Mal Kabul Uyuşmazlığı'na geçilmelidir."""
        wf = frappe.get_doc("Workflow", "KTA Mal Giris Sureci")
        mal_giris_transitions = [t for t in wf.transitions if t.state == "Mal Giriş"]

        # Hiçbir geçiş doğrudan Yolda'ya gitmemelidir
        yolda_targets = [t for t in mal_giris_transitions if t.next_state == "Yolda"]
        self.assertEqual(
            len(yolda_targets),
            0,
            "Mal Giriş aşamasından doğrudan Yolda'ya ret geçişi bulunmamalıdır!",
        )

        # Uyuşmazlık Bildir geçişi bulunmalıdır
        uyusmazlik_trans = [
            t for t in mal_giris_transitions if t.action == "Uyuşmazlık Bildir"
        ]
        self.assertTrue(
            len(uyusmazlik_trans) > 0,
            "Mal Giriş aşamasında Uyuşmazlık Bildir geçişi bulunamadı!",
        )
        self.assertEqual(
            uyusmazlik_trans[0].next_state,
            "Mal Kabul Uyuşmazlığı",
            "Uyuşmazlık Bildir hedefi Mal Kabul Uyuşmazlığı olmalıdır!",
        )
        self.assertEqual(
            uyusmazlik_trans[0].allowed,
            "Stock User",
            "Uyuşmazlık Bildir Stock User tarafından yapılabilmelidir!",
        )

    def test_mal_kabul_uyusmazligi_transitions(self):
        """Mal Kabul Uyuşmazlığı çıkış rotaları doğrulanmalıdır."""
        wf = frappe.get_doc("Workflow", "KTA Mal Giris Sureci")
        dispute_transitions = [
            t for t in wf.transitions if t.state == "Mal Kabul Uyuşmazlığı"
        ]

        # 1. İthalat için Sorun Çözüldü -> KTA Gümrük Sorumlusu
        import_resolved = [
            t
            for t in dispute_transitions
            if t.action == "Sorun Çözüldü" and t.allowed == "KTA Gümrük Sorumlusu"
        ]
        self.assertTrue(
            len(import_resolved) > 0,
            "İthalat için Sorun Çözüldü (KTA Gümrük Sorumlusu) geçişi bulunamadı!",
        )
        self.assertIn("is_import_purchase_receipt", import_resolved[0].condition)
        self.assertEqual(import_resolved[0].next_state, "Mal Giriş")

        # 2. Yurtiçi için Sorun Çözüldü -> Purchase User
        domestic_resolved = [
            t
            for t in dispute_transitions
            if t.action == "Sorun Çözüldü" and t.allowed == "Purchase User"
        ]
        self.assertTrue(
            len(domestic_resolved) > 0,
            "Yurtiçi için Sorun Çözüldü (Purchase User) geçişi bulunamadı!",
        )
        self.assertIn("is_import_purchase_receipt", domestic_resolved[0].condition)
        self.assertEqual(domestic_resolved[0].next_state, "Mal Giriş")

        # 3. Gümrüğe İade -> KTA Gümrük Sorumlusu
        gumruk_iade = [
            t
            for t in dispute_transitions
            if t.action == "Gümrüğe İade" and t.allowed == "KTA Gümrük Sorumlusu"
        ]
        self.assertTrue(
            len(gumruk_iade) > 0,
            "Gümrüğe İade (KTA Gümrük Sorumlusu) geçişi bulunamadı!",
        )

    def test_role_authorization_enforcement(self):
        """Depocu transit/gümrük adımlarını tetikleyememeli, yalnızca gümrük sorumlusu tetikleyebilmelidir."""
        wf = get_workflow("Purchase Receipt")

        def get_allowed_actions_for_user(user, state, is_import=1, is_antrepo=1):
            frappe.set_user(user)
            roles = frappe.get_roles()
            doc = frappe.new_doc("Purchase Receipt")
            doc.workflow_state = state
            doc.is_return = 0
            doc.is_import_purchase_receipt = is_import
            doc.is_antrepo_purchase_receipt = is_antrepo
            return [
                t.action
                for t in wf.transitions
                if t.state == state
                and t.allowed in roles
                and is_transition_condition_satisfied(t, doc)
            ]

        # 1. Depocu (Hayri Mahiroğlu) Yolda, Antrepoda, Gümrüklemede hiçbir aksiyon göremez
        self.assertEqual(
            get_allowed_actions_for_user(
                "hayri.mahiroglu@kta-endustri.com.tr", "Yolda"
            ),
            [],
            "Depocu Yolda statüsünde aksiyon görememelidir!",
        )
        self.assertEqual(
            get_allowed_actions_for_user(
                "hayri.mahiroglu@kta-endustri.com.tr", "Antrepoda"
            ),
            [],
            "Depocu Antrepoda statüsünde aksiyon görememelidir!",
        )
        self.assertEqual(
            get_allowed_actions_for_user(
                "hayri.mahiroglu@kta-endustri.com.tr", "Gümrüklemede"
            ),
            [],
            "Depocu Gümrüklemede statüsünde aksiyon görememelidir!",
        )

        # 2. Ceren Keçici (KTA Gümrük Sorumlusu) tüm bu statülerde aksiyonları görebilir
        ceren_yolda = get_allowed_actions_for_user(
            "ceren.kecici@kta-endustri.com.tr", "Yolda"
        )
        self.assertIn("Antrepoya Al", ceren_yolda)
        self.assertIn("İthalatı Gerçekleştir", ceren_yolda)
        self.assertIn("Reject", ceren_yolda)

        ceren_antrepo = get_allowed_actions_for_user(
            "ceren.kecici@kta-endustri.com.tr", "Antrepoda"
        )
        self.assertIn("İşlem Başlat", ceren_antrepo)
        self.assertIn("Reject", ceren_antrepo)

        ceren_gumruk = get_allowed_actions_for_user(
            "ceren.kecici@kta-endustri.com.tr", "Gümrüklemede"
        )
        self.assertIn("Antrepodan Çek", ceren_gumruk)
        self.assertIn("Reject", ceren_gumruk)

        # 3. İthalat uyuşmazlığında depocu işlem yapamaz, gümrük sorumlusu yapabilir
        self.assertEqual(
            get_allowed_actions_for_user(
                "hayri.mahiroglu@kta-endustri.com.tr",
                "Mal Kabul Uyuşmazlığı",
                is_import=1,
            ),
            [],
            "Depocu ithalat uyuşmazlığında işlem yapamamalıdır!",
        )
        ceren_uyusmazlik = get_allowed_actions_for_user(
            "ceren.kecici@kta-endustri.com.tr",
            "Mal Kabul Uyuşmazlığı",
            is_import=1,
            is_antrepo=1,
        )
        self.assertIn("Sorun Çözüldü", ceren_uyusmazlik)
        self.assertIn("Gümrüğe İade", ceren_uyusmazlik)

    def test_validate_dispute_fields_mandatory(self):
        """Mal Kabul Uyuşmazlığı durumunda uyuşmazlık nedeni ve açıklaması zorunlu olmalıdır."""
        pr = frappe.new_doc("Purchase Receipt")
        pr.workflow_state = "Mal Kabul Uyuşmazlığı"

        # Her iki alan da boşken hata fırlatmalıdır
        with self.assertRaises(frappe.ValidationError):
            pr._validate_dispute_fields()

        # Yalnızca neden varken, açıklama yokken hata fırlatmalıdır
        pr.custom_uyusmazlik_nedeni = "Evrak / İrsaliye Uyuşmazlığı"
        pr.custom_uyusmazlik_aciklamasi = ""
        with self.assertRaises(frappe.ValidationError):
            pr._validate_dispute_fields()

        # Her iki alan da doluyken başarıyla geçmelidir
        pr.custom_uyusmazlik_aciklamasi = "İrsaliye ve fatura kalem adetleri uyuşmuyor."
        pr._validate_dispute_fields()

        # Başka bir statüdeyken (örneğin Mal Giriş) bu alanlar zorunlu değildir
        pr.workflow_state = "Mal Giriş"
        pr.custom_uyusmazlik_nedeni = ""
        pr.custom_uyusmazlik_aciklamasi = ""
        pr._validate_dispute_fields()
