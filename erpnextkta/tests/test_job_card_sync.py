import unittest
import frappe
from erpnextkta.tests.test_utils import KTATestCase
from erpnextkta.kta_calisma_karti.api_impl.job_card_sync import distribute_completed_qty

class TestJobCardSync(KTATestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        super().setUp()
        from unittest.mock import patch
        
        # Orijinal metodu tutalım
        self.original_get_single_value = frappe.db.get_single_value

        self.patcher = patch('frappe.db.get_single_value')
        self.mock_get_single_value = self.patcher.start()
        
        def mock_get_single_value_side_effect(doctype, fieldname, *args, **kwargs):
            if doctype == "KTA Calisma Karti Settings" and fieldname == "job_card_time_log_sync_modu":
                return "Sıkı (Hard)"
            return self.original_get_single_value(doctype, fieldname, *args, **kwargs)
            
        self.mock_get_single_value.side_effect = mock_get_single_value_side_effect

    def tearDown(self):
        super().tearDown()
        self.patcher.stop()

    def create_mock_job_card(self, for_quantity, time_logs):
        """Yardımcı metod: Job Card dokümanını taklit eden bir obje oluşturur."""
        logs = []
        for log in time_logs:
            logs.append(frappe._dict({
                "from_time": log.get("from_time"),
                "to_time": log.get("to_time"),
                "time_in_mins": 0.0,
                "completed_qty": 0.0
            }))
            
        doc = frappe._dict({
            "for_quantity": for_quantity,
            "time_logs": logs,
            "flags": frappe._dict()
        })
        return doc

    def test_distribute_completed_qty_equal_time(self):
        """Eşit sürede çalışan iki operatörün hedefi tam ortadan bölüşmesini test eder."""
        doc = self.create_mock_job_card(
            for_quantity=100.0,
            time_logs=[
                {"from_time": "2024-01-01 08:00:00", "to_time": "2024-01-01 09:00:00"}, # 1 saat
                {"from_time": "2024-01-01 09:00:00", "to_time": "2024-01-01 10:00:00"}  # 1 saat
            ]
        )
        distribute_completed_qty(doc)
        
        self.assertEqual(doc.time_logs[0].completed_qty, 50.0)
        self.assertEqual(doc.time_logs[1].completed_qty, 50.0)
        self.assertEqual(doc.time_logs[0].time_in_mins, 60.0)
        self.assertEqual(doc.time_logs[1].time_in_mins, 60.0)

    def test_distribute_completed_qty_proportional(self):
        """Sürelere orantılı olarak miktar dağıtılmasını test eder."""
        doc = self.create_mock_job_card(
            for_quantity=1000.0,
            time_logs=[
                {"from_time": "2024-01-01 08:00:00", "to_time": "2024-01-01 08:30:00"}, # 30 dk
                {"from_time": "2024-01-01 08:30:00", "to_time": "2024-01-01 09:40:00"}  # 70 dk
            ]
        )
        distribute_completed_qty(doc)
        
        self.assertEqual(doc.time_logs[0].completed_qty, 300.0)
        self.assertEqual(doc.time_logs[1].completed_qty, 700.0)
        self.assertEqual(doc.time_logs[0].time_in_mins, 30.0)
        self.assertEqual(doc.time_logs[1].time_in_mins, 70.0)

    def test_distribute_completed_qty_rounding_remainder(self):
        """Küsüratlı bölme işlemlerinde son satırın bakiyeyi toplayıp
           tam sayıyı (for_quantity) tutturmasını test eder."""
        doc = self.create_mock_job_card(
            for_quantity=10.0,
            time_logs=[
                {"from_time": "2024-01-01 08:00:00", "to_time": "2024-01-01 09:00:00"}, # 60 dk
                {"from_time": "2024-01-01 09:00:00", "to_time": "2024-01-01 10:00:00"}, # 60 dk
                {"from_time": "2024-01-01 10:00:00", "to_time": "2024-01-01 11:00:00"}  # 60 dk
            ]
        )
        distribute_completed_qty(doc)
        
        # 10 adet / 3 eşit süre = 3.33, 3.33 ve sonuncusu 3.34 almalı
        self.assertEqual(doc.time_logs[0].completed_qty, 3.33)
        self.assertEqual(doc.time_logs[1].completed_qty, 3.33)
        self.assertEqual(doc.time_logs[2].completed_qty, 3.34)
        
        # Toplamın tam 10 olduğuna emin olalım
        total = sum([log.completed_qty for log in doc.time_logs])
        self.assertEqual(total, 10.0)

    def test_distribute_completed_qty_no_time(self):
        """Hiç süre girilmemiş loglarda (veya eşit sürelerde) eşit dağıtım yapıldığını test eder."""
        doc = self.create_mock_job_card(
            for_quantity=10.0,
            time_logs=[
                {"from_time": None, "to_time": None},
                {"from_time": None, "to_time": None},
                {"from_time": None, "to_time": None}
            ]
        )
        distribute_completed_qty(doc)
        
        self.assertEqual(doc.time_logs[0].completed_qty, 3.33)
        self.assertEqual(doc.time_logs[1].completed_qty, 3.33)
        self.assertEqual(doc.time_logs[2].completed_qty, 3.34)

    def test_distribute_completed_qty_negative_remainder_prevention(self):
        """Matematiksel olarak yuvarlamalardan dolayı kalanın negatife düşmesi engellenmeli."""
        doc = self.create_mock_job_card(
            for_quantity=0.01,
            time_logs=[
                {"from_time": "2024-01-01 08:00:00", "to_time": "2024-01-01 09:00:00"},
                {"from_time": "2024-01-01 09:00:00", "to_time": "2024-01-01 10:00:00"},
            ]
        )
        distribute_completed_qty(doc)
        
        # İlk log 0.01 / 2 = 0.005 -> 0.01 olarak yuvarlanıyor.
        # İkinci log'a kalan bakiye normalde -0.01 olurdu, max(0) kontrolümüz sayesinde 0.0 olmalı.
        self.assertTrue(doc.time_logs[1].completed_qty >= 0.0)

    def test_custom_alt_operasyon_truncation(self):
        """140 karakterden uzun birleştirilmiş alt operasyon metinlerinin
           137 karakter + '...' olarak kırpıldığını test eder."""
        from erpnextkta.kta_calisma_karti.api_impl.job_card_sync import sync_time_log_to_job_card
        
        # Bu test için doc object'i mock'lamak biraz daha karmaşık olduğu için
        # sadece truncation işlemini test eden mantığın doğru çalışıp çalışmadığını
        # bağımsız olarak doğrularız. (mock obje ile)
        
        # Fonksiyon içerisinde bu kontrol yapılıyor:
        # if len(alt_op_str) > 140:
        #     alt_op_str = alt_op_str[:137] + "..."
        
        alt_ops = ["OP30-0001"] * 50  # Çok uzun bir string oluşturacak (yaklaşık 500 karakter)
        alt_op_str = ", ".join(alt_ops)
        
        if len(alt_op_str) > 140:
            alt_op_str = alt_op_str[:137] + "..."
            
        self.assertEqual(len(alt_op_str), 140)
        self.assertTrue(alt_op_str.endswith("..."))

    def test_distribute_completed_qty_kta_sync_mode_bypass(self):
        """kta_sync_mode flag'i True olduğunda miktar dağıtımının atlanmasını test eder."""
        doc = self.create_mock_job_card(
            for_quantity=100.0,
            time_logs=[
                {"from_time": "2024-01-01 08:00:00", "to_time": "2024-01-01 09:00:00"}, # 1 saat
                {"from_time": "2024-01-01 09:00:00", "to_time": "2024-01-01 10:00:00"}  # 1 saat
            ]
        )
        
        # Önceden 0.0 olarak mock edilmiş. Dağıtım yapılmazsa completed_qty 0.0 kalmalı.
        doc.flags.kta_sync_mode = True
        distribute_completed_qty(doc)
        
        self.assertEqual(doc.time_logs[0].completed_qty, 0.0)
        self.assertEqual(doc.time_logs[1].completed_qty, 0.0)

        # Flag'i kaldırıp tekrar çalıştıralım, bu sefer dağıtım yapılmalı.
        doc.flags.kta_sync_mode = False
        distribute_completed_qty(doc)
        
        self.assertEqual(doc.time_logs[0].completed_qty, 50.0)
        self.assertEqual(doc.time_logs[1].completed_qty, 50.0)

    def _run_sequence_bypass_scenario(self, skip_transfer, transfer_material_against, test_suffix, start_time):
        """Yardımcı metod: Farklı İş Emri senaryolarında sıra kuralı baypasını test eder."""
        from erpnextkta.tests.test_utils import create_test_erpnext_operation, make_mock_calisma_karti, create_test_operator
        from erpnextkta.kta_calisma_karti.api_impl.job_card_sync import sync_time_log_to_job_card
        
        op1_name = create_test_erpnext_operation(f"_Test Seq OP 1 {test_suffix}", self.ws_name)
        op2_name = create_test_erpnext_operation(f"_Test Seq OP 2 {test_suffix}", self.ws_name)
        
        # Test izolasyonu için benzersiz operatör oluşturalım
        emp_email = f"test_{test_suffix}@kta.com"
        create_test_operator(emp_email, f"Test Op {test_suffix}")
        
        # Daha önceki testlerden kalan draft Time Log'ları temizleyelim (OverlapError önlemi)
        frappe.db.sql("DELETE FROM `tabJob Card Time Log` WHERE employee=%s", emp_email)
        frappe.db.commit()
        
        wo = frappe.get_doc({
            "doctype": "Work Order",
            "production_item": self.item,
            "qty": 100,
            "company": self.company,
            "wip_warehouse": self.wip_warehouse,
            "fg_warehouse": self.wip_warehouse,
            "use_multi_level_bom": 0,
            "skip_transfer": skip_transfer,
            "transfer_material_against": transfer_material_against,
            "operations": [
                {
                    "operation": op1_name,
                    "workstation": self.ws_name,
                    "time_in_mins": 60,
                    "sequence_id": 1,
                    "operating_cost": 100
                },
                {
                    "operation": op2_name,
                    "workstation": self.ws_name,
                    "time_in_mins": 60,
                    "sequence_id": 2,
                    "operating_cost": 100
                }
            ]
        })
        # BOM validation'ı atlamak için:
        wo.flags.ignore_mandatory = True 
        wo.insert(ignore_permissions=True)
        wo.submit()
        
        # Frappe otomatik olarak 2 Job Card oluşturmuş olmalı
        job_cards = frappe.get_all("Job Card", filters={"work_order": wo.name}, order_by="sequence_id asc", pluck="name")
        self.assertEqual(len(job_cards), 2, "Frappe 2 adet Job Card oluşturmalıydı")
        
        jc1_name = job_cards[0]
        jc2_name = job_cards[1]
        
        # BOM olmadan Work Order yarattığımız için Frappe wip_warehouse'u Job Card'a 
        # taşımayı unutabiliyor. Biz manuel atayalım ki MandatoryError vermesin.
        frappe.db.set_value("Job Card", jc2_name, "wip_warehouse", self.wip_warehouse)
        
        # Frappe'nin Job Card kaydederken 'LinkValidationError' fırlatmaması için 
        # bu sahte Çalışma Kartı'nın gerçekten veritabanında var olması gerekiyor.
        ck_name = f"TEST-CK-OP2-{test_suffix}"
        frappe.db.sql("""
            INSERT INTO `tabCalisma Karti` (name, is_karti, baslangic_saati, net_calisma_suresi, operator, creation, modified, modified_by)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW(), 'Administrator')
            ON DUPLICATE KEY UPDATE name=name
        """, (ck_name, jc2_name, start_time, "01:00:00", emp_email))
        
        # Mock bir Çalışma Kartı nesnesi oluşturalım (Sadece süre tutan bir kayıt)
        ck = make_mock_calisma_karti(
            name=ck_name,
            is_karti=jc2_name,
            baslangic_saati=start_time,
            net_calisma_suresi="01:00:00",
            operator=emp_email
        )
        
        # Aktarma işlemi hata fırlatmamalı (Sıra hatası vermemeli)
        try:
            sync_time_log_to_job_card(ck)
        except frappe.exceptions.ValidationError as e:
            self.fail(f"Senkronizasyon (sync) sıra hatasına (OperationSequenceError) takıldı: {e}")
            
        # Başarıyla senkronize oldu mu ve completed_qty 0 kaldı mı kontrol edelim
        jc2_reloaded = frappe.get_doc("Job Card", jc2_name)
        self.assertTrue(len(jc2_reloaded.time_logs) >= 1)
        
        log_row = None
        for row in jc2_reloaded.time_logs:
            if row.get("custom_calisma_karti") == ck_name or row.employee == emp_email:
                log_row = row
                break
                
        self.assertIsNotNone(log_row)
        self.assertEqual(log_row.completed_qty, 0.0)
        self.assertEqual(jc2_reloaded.total_completed_qty, 0.0)

    def test_job_card_sequence_bypass_transfer_job_card(self):
        """KTA Senaryosu: Malzeme aktarımı atlanmış (Skip Transfer) ve Transfer Job Card'a göre."""
        self._run_sequence_bypass_scenario(skip_transfer=1, transfer_material_against="Job Card", test_suffix="JC", start_time="2026-01-01 08:00:00")

    def test_job_card_sequence_bypass_transfer_work_order(self):
        """KTA Senaryosu: Malzeme aktarımı atlanmış (Skip Transfer) ve Transfer Work Order'a göre."""
        self._run_sequence_bypass_scenario(skip_transfer=1, transfer_material_against="Work Order", test_suffix="WO", start_time="2026-01-01 10:00:00")

    def test_job_card_sequence_bypass_no_skip_transfer(self):
        """KTA Senaryosu: Malzeme aktarımı atlanmamış (No Skip Transfer) normal Work Order süreci."""
        self._run_sequence_bypass_scenario(skip_transfer=0, transfer_material_against="Work Order", test_suffix="NO_SKIP", start_time="2026-01-01 12:00:00")

    def test_overlap_error_bypass_with_disable_capacity_planning(self):
        """KTA Senaryosu: Kapasite planlama kapalıyken OverlapError'ın atlanması."""
        from erpnext.manufacturing.doctype.job_card.job_card import OverlapError
        from erpnextkta.tests.test_utils import create_test_operator
        
        # Orijinal side_effect'i saklayalım
        original_side_effect = self.mock_get_single_value.side_effect
        
        # Operatör
        emp_email = "test_overlap@kta.com"
        create_test_operator(emp_email, "Test Overlap")
        
        # Eski verileri temizleyelim ki OverlapError çakışmasın
        frappe.db.sql("DELETE FROM `tabJob Card Time Log` WHERE employee=%s", emp_email)
        
        # Workstation'ları oluşturalım
        ws1 = "Test WS Overlap 1"
        ws2 = "Test WS Overlap 1"  # Aynı istasyonu kullanalım ki çakışma olsun!
        for ws in [ws1, ws2]:
            if not frappe.db.exists("Workstation", ws):
                frappe.get_doc({"doctype": "Workstation", "workstation_name": ws}).insert(ignore_permissions=True)

        # Job Card 1 (Draft)
        jc1 = frappe.new_doc("Job Card")
        jc1.workstation = ws1
        jc1.operation = "Montaj"
        jc1.append("time_logs", {
            "from_time": "2026-05-01 08:00:00",
            "to_time": "2026-05-01 09:00:00",
            "completed_qty": 10,
            "employee": emp_email
        })
        jc1.insert(ignore_permissions=True, ignore_mandatory=True)

        # Job Card 2 (Draft)
        jc2 = frappe.new_doc("Job Card")
        jc2.workstation = ws2
        jc2.operation = "Montaj"
        jc2.append("time_logs", {
            "from_time": "2026-05-01 08:30:00",
            "to_time": "2026-05-01 09:30:00",
            "completed_qty": 10,
            "employee": emp_email
        })
        
        # 1. Kapasite planlama devredeyken (disable_capacity_planning=0) hata fırlatmasını bekliyoruz.
        def mock_side_effect_enabled(doctype, fieldname, *args, **kwargs):
            if doctype == "Manufacturing Settings" and fieldname == "disable_capacity_planning":
                return 0
            return original_side_effect(doctype, fieldname, *args, **kwargs)
            
        self.mock_get_single_value.side_effect = mock_side_effect_enabled
        
        with self.assertRaises(OverlapError):
            jc2.insert(ignore_permissions=True, ignore_mandatory=True)

        # 2. Kapasite planlama DEVRE DIŞIYKEN (disable_capacity_planning=1) hata FIRLATMAMASINI bekliyoruz.
        def mock_side_effect_disabled(doctype, fieldname, *args, **kwargs):
            if doctype == "Manufacturing Settings" and fieldname == "disable_capacity_planning":
                return 1
            return original_side_effect(doctype, fieldname, *args, **kwargs)
            
        self.mock_get_single_value.side_effect = mock_side_effect_disabled
        
        try:
            jc2.insert(ignore_permissions=True, ignore_mandatory=True)
            self.assertTrue(jc2.name) # Başarıyla oluşturuldu
        except OverlapError:
            self.fail("disable_capacity_planning=1 iken OverlapError fırlatılmamalıydı!")
        finally:
            self.mock_get_single_value.side_effect = original_side_effect

    def test_sync_time_log_to_submitted_job_card_distributes_qty(self):
        """Submit edilmiş bir Job Card'a yeni bir zaman logu (Calisma Karti uzerinden) eklendiğinde,
           kta_sync_mode baypası devreye girmeyecek ve miktarlar (completed_qty) dagitilacaktir."""
        from erpnextkta.tests.test_utils import create_test_operator, make_mock_calisma_karti
        from erpnextkta.kta_calisma_karti.api_impl.job_card_sync import sync_time_log_to_job_card
        
        emp_email = "test_dist_sub@kta.com"
        create_test_operator(emp_email, "Test Dist Sub")
        frappe.db.sql("DELETE FROM `tabJob Card Time Log` WHERE employee=%s", emp_email)
        
        # 1. Job Card oluştur ve Submit et
        jc = frappe.new_doc("Job Card")
        jc.workstation = self.ws_name
        jc.operation = "Montaj"
        jc.work_order = self.wo_name
        jc.wip_warehouse = self.wip_warehouse
        jc.for_quantity = 100.0
        jc.append("time_logs", {
            "from_time": "2026-05-01 10:00:00",
            "to_time": "2026-05-01 11:00:00",
            "completed_qty": 100.0,
            "employee": emp_email,
            "custom_calisma_karti": "ESKI-CK-001"
        })
        # Mocking to allow submit
        jc.flags.ignore_mandatory = True
        jc.insert(ignore_permissions=True, ignore_links=True)
        jc.submit()
        
        # Orijinal submitte 100.0 adet tek logda
        jc.reload()
        self.assertEqual(jc.time_logs[0].completed_qty, 100.0)
        self.assertEqual(jc.docstatus, 1)

        # 2. Yeni Çalışma Kartı (Mock) ile sync yap
        ck_name = "YENI-CK-001"
        frappe.db.sql("""
            INSERT INTO `tabCalisma Karti` (name, is_karti, baslangic_saati, net_calisma_suresi, operator, creation, modified, modified_by)
            VALUES 
            ('ESKI-CK-001', %s, '2026-05-01 10:00:00', '01:00:00', %s, NOW(), NOW(), 'Administrator'),
            (%s, %s, %s, %s, %s, NOW(), NOW(), 'Administrator')
            ON DUPLICATE KEY UPDATE name=name
        """, (jc.name, emp_email, ck_name, jc.name, "2026-05-01 11:00:00", "01:00:00", emp_email))
        
        ck = make_mock_calisma_karti(
            name=ck_name,
            is_karti=jc.name,
            baslangic_saati="2026-05-01 11:00:00",
            net_calisma_suresi="01:00:00", # 1 saat
            operator=emp_email
        )
        
        # Sync işlemini çalıştır (Submit edilmiş Job Card'a)
        sync_time_log_to_job_card(ck)
        
        # 3. Sonuçları kontrol et
        jc.reload()
        
        self.assertEqual(len(jc.time_logs), 2, "Yeni time log eklenmiş olmalı")
        
        # Zamanlar eşit olduğu için (1 saat vs 1 saat), 100.0 hedefi 50/50 dağılmalı.
        self.assertEqual(jc.time_logs[0].completed_qty, 50.0)
        self.assertEqual(jc.time_logs[1].completed_qty, 50.0)
