# English comments as requested

from __future__ import annotations

import frappe

from erpnextkta.kta_calisma_karti.services.work_card_analytics_service import (
    get_work_order_card_analytics,
)
from erpnextkta.tests.test_utils import (
    KTATestCase,
    create_test_item,
    create_test_job_card,
    create_test_operator,
    create_test_work_order,
)


class TestWorkCardAnalyticsService(KTATestCase):
    def setUp(self):
        super().setUp()
        frappe.db.sql(
            "DELETE FROM `tabCalisma Karti` WHERE custom_work_order LIKE 'TEST-%'"
        )
        frappe.db.sql(
            "DELETE FROM `tabCalisma Karti Hurda` "
            "WHERE parent NOT IN (SELECT name FROM `tabCalisma Karti`)"
        )
        frappe.db.sql(
            "DELETE FROM `tabCalisma Karti Alt Operasyon Kayitlari` "
            "WHERE parent NOT IN (SELECT name FROM `tabCalisma Karti`)"
        )
        frappe.db.sql("DELETE FROM `tabWork Order Item` WHERE parent LIKE 'TEST-%'")
        frappe.db.commit()
        create_test_operator("operator1@kta.com", "Ahmet Yilmaz")
        self._ensure_mapping()

    def _ensure_mapping(self):
        """Ensure KTA Operation ERPNext mapping is set up for self.kta_op."""
        existing = frappe.db.get_value(
            "KTA Operation ERPNext Mappings",
            {"parent": self.kta_op, "erpnext_operation": self.erpnext_op},
            "name",
        )
        if not existing:
            kta_op_doc = frappe.get_doc("KTA Calisma Karti Operasyonlari", self.kta_op)
            kta_op_doc.append(
                "erpnext_operations",
                {
                    "erpnext_operation": self.erpnext_op,
                    "production_item": "",
                },
            )
            kta_op_doc.save(ignore_permissions=True)
            frappe.db.commit()

    def _create_sub_operation(
        self,
        title: str,
        sequence: int,
        is_tuketim: int = 1,
        parent_op: str | None = None,
    ):
        """Helper to create or get a test sub-operation."""
        target_op = parent_op or self.kta_op
        name = f"{target_op}-{title}"
        if not frappe.db.exists("KTA Calisma Karti Alt Operasyonlari", name):
            doc = frappe.get_doc(
                {
                    "doctype": "KTA Calisma Karti Alt Operasyonlari",
                    "parent_operation": target_op,
                    "title": title,
                    "sequence": sequence,
                    "is_active": 1,
                    "is_tuketim_hesaplanir": is_tuketim,
                }
            )
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return doc.name
        return name

    def test_permission_error_on_unpermitted_work_order(self):
        # User without read access raises frappe.PermissionError or DoesNotExistError
        frappe.set_user("test_no_perm@example.com")
        try:
            get_work_order_card_analytics("NON-EXISTENT-OR-FORBIDDEN-WO")
            self.fail("Should raise PermissionError or DoesNotExistError")
        except (frappe.PermissionError, frappe.DoesNotExistError):
            pass
        finally:
            frappe.set_user("Administrator")

    def test_empty_work_order_graceful_response(self):
        # Empty/unstarted WO returns 0 metrics and empty operations list
        wo_name = "TEST-EMPTY-WO-001"
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)
        create_test_job_card(
            "TEST-EMPTY-JC-001",
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        self._create_sub_operation("Empty Sub Op", sequence=10, is_tuketim=1)

        result = get_work_order_card_analytics(wo_name)
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["total_cards"], 0)
        self.assertEqual(result["summary"]["completed_cards"], 0)
        self.assertEqual(result["summary"]["in_progress_cards"], 0)
        self.assertEqual(result["summary"]["total_duration_mins"], 0.0)
        self.assertEqual(result["summary"]["total_scrap_qty"], 0.0)
        # Unstarted steps and operations without cards are completely excluded
        self.assertEqual(result.get("operations", []), [])

    def test_non_consumption_sub_operation(self):
        # is_tuketim_hesaplanir == 0 returns process qty and duration,
        # but empty consumptions list without calculation errors
        wo_name = "TEST-WO-NON-CONSUMPTION-001"
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)
        jc_name = "TEST-JC-NON-CONSUMPTION-001"
        create_test_job_card(
            jc_name,
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        sub_op_name = self._create_sub_operation(
            "Visual Inspection", sequence=20, is_tuketim=0
        )

        card = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc_name,
                "operasyon": self.kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 100,
                "operator": "operator1@kta.com",
                "durum": "Bitmiş",
                "baslangic_saati": "2026-11-19 11:15:00",
                "bitis_saati": "2026-11-19 12:00:00",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op_name,
                        "islem_adedi_1": 100,
                        "adet": 0,
                    }
                ],
            }
        )
        card.insert(ignore_permissions=True)
        frappe.db.commit()

        result = get_work_order_card_analytics(wo_name)
        found = False
        for op in result.get("operations", []):
            self.assertIn("kta_operations", op)
            for sub in op.get("sub_operations", []):
                if sub.get("is_tuketim_hesaplanir") == 0:
                    found = True
                    self.assertEqual(sub["consumptions"], [])
                    self.assertGreaterEqual(sub["total_process_qty"], 100.0)
                    self.assertGreaterEqual(sub["total_duration_mins"], 45.0)
        self.assertTrue(found, "Non-consumption sub-operation should be present")

    def test_duration_deduplication_multi_step_card(self):
        # Single card with multiple sub-ops must not double count
        # duration in operation or summary level
        wo_name = "TEST-WO-MULTI-STEP-001"
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)
        jc_name = "TEST-JC-MULTI-STEP-001"
        create_test_job_card(
            jc_name,
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        sub_op_1 = self._create_sub_operation("Step One", sequence=10, is_tuketim=1)
        sub_op_2 = self._create_sub_operation("Step Two", sequence=20, is_tuketim=1)

        raw_mat = create_test_item(self.item_group)

        card = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc_name,
                "operasyon": self.kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 50,
                "operator": "operator1@kta.com",
                "durum": "Bitmiş",
                "baslangic_saati": "2026-11-19 12:45:00",
                "bitis_saati": "2026-11-19 14:00:00",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op_1,
                        "hammadde": raw_mat,
                        "islem_adedi_1": 50,
                        "adet": 50,
                    },
                    {
                        "alt_operasyon": sub_op_2,
                        "hammadde": raw_mat,
                        "islem_adedi_1": 50,
                        "adet": 50,
                    },
                ],
            }
        )
        card.insert(ignore_permissions=True)
        frappe.db.commit()

        result = get_work_order_card_analytics(wo_name)
        summary_dur = result["summary"]["total_duration_mins"]
        total_unique = sum(op["total_duration_mins"] for op in result["operations"])
        self.assertEqual(summary_dur, total_unique)
        self.assertEqual(summary_dur, 75.0)

        op = result["operations"][0]
        self.assertEqual(len(op["kta_operations"]), 1)
        self.assertEqual(op["kta_operations"][0]["total_duration_mins"], 75.0)

    def test_unmatched_scraps_attached_to_operation(self):
        # Scraps not matching sub-op raw materials land in unmatched_scraps
        wo_name = "TEST-WO-SCRAPS-001"
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)
        jc_name = "TEST-JC-SCRAPS-001"
        create_test_job_card(
            jc_name,
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        sub_op = self._create_sub_operation("Wire Cut", sequence=10, is_tuketim=1)

        mat_consumed = create_test_item(
            self.item_group, item_code="TEST-CONSUMED-MAT-001"
        )
        unmatched_mat = create_test_item(
            self.item_group, item_code="TEST-UNMATCHED-SCRAP-001"
        )
        cc_name = frappe.db.get_value("Cost Center", {"is_group": 0}, "name")

        card = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc_name,
                "operasyon": self.kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 100,
                "operator": "operator1@kta.com",
                "durum": "Bitmiş",
                "baslangic_saati": "2026-11-19 15:10:00",
                "bitis_saati": "2026-11-19 16:00:00",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op,
                        "hammadde": mat_consumed,
                        "islem_adedi_1": 100,
                        "adet": 100,
                    }
                ],
                "hurdalar": [
                    {
                        "parca_no": mat_consumed,
                        "miktar": 3.0,
                        "hurda_nedeni": cc_name,
                        "aciklama": "Wire Jam",
                    },
                    {
                        "parca_no": unmatched_mat,
                        "miktar": 1.5,
                        "hurda_nedeni": cc_name,
                        "aciklama": "General Setup Loss",
                    },
                ],
            }
        )
        card.insert(ignore_permissions=True)
        frappe.db.commit()

        result = get_work_order_card_analytics(wo_name)
        # Check summary scrap
        self.assertEqual(result["summary"]["total_scrap_qty"], 4.5)

        op = result["operations"][0]
        self.assertEqual(len(op["unmatched_scraps"]), 1)
        self.assertEqual(op["unmatched_scraps"][0]["item_code"], unmatched_mat)
        self.assertEqual(op["unmatched_scraps"][0]["qty"], 1.5)

        # Matched scrap is in sub-operation
        sub = next(s for s in op["sub_operations"] if s["sub_op_id"] == sub_op)
        self.assertEqual(len(sub["scraps"]), 1)
        self.assertEqual(sub["scraps"][0]["item_code"], mat_consumed)
        self.assertEqual(sub["scraps"][0]["qty"], 3.0)

    def test_hierarchical_grouping_and_unstarted_exclusion(self):
        # Test hierarchical grouping: Job Cards -> KTA Operations -> Sub-Operations
        # and verify unstarted Job Cards and sub-operations are excluded.
        wo_name = "TEST-WO-HIER-001"
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)

        # Job Card 1 with cards
        jc1_name = "TEST-JC-HIER-001"
        create_test_job_card(
            jc1_name,
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        frappe.db.set_value("Job Card", jc1_name, "sequence_id", 1)

        # Job Card 2 without cards (must be excluded from operations output)
        jc2_name = "TEST-JC-HIER-002"
        create_test_job_card(
            jc2_name,
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        frappe.db.set_value("Job Card", jc2_name, "sequence_id", 2)
        frappe.db.commit()

        # Create second KTA operation with unique calisma_karti_op
        second_kta_op = "KTA-OP-002-TEST"
        if not frappe.db.exists("KTA Calisma Karti Operasyonlari", second_kta_op):
            frappe.get_doc(
                {
                    "doctype": "KTA Calisma Karti Operasyonlari",
                    "name": second_kta_op,
                    "calisma_karti_op": "Test Operasyon 2",
                    "miktar_zorunlu_mu": 1,
                    "plant_floor": "L-1",
                }
            ).insert(ignore_permissions=True, ignore_links=True)

        # Sub-operations for first KTA op
        sub_op_1 = self._create_sub_operation("OP10-0001", sequence=10, is_tuketim=1)
        sub_op_2 = self._create_sub_operation("OP10-0002", sequence=20, is_tuketim=1)
        # Unstarted sub-operation (must be excluded)
        self._create_sub_operation("OP10-0003", sequence=30, is_tuketim=1)

        # Sub-operation for second KTA op
        sub_op_b1 = self._create_sub_operation(
            "OP20-0001", sequence=10, is_tuketim=1, parent_op=second_kta_op
        )

        raw_mat = create_test_item(self.item_group)

        # Card 1 on JC1 under first KTA op
        card1 = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc1_name,
                "operasyon": self.kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 50,
                "operator": "operator1@kta.com",
                "durum": "Bitmiş",
                "baslangic_saati": "2026-11-19 09:00:00",
                "bitis_saati": "2026-11-19 09:30:00",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op_1,
                        "hammadde": raw_mat,
                        "islem_adedi_1": 50,
                        "adet": 50,
                    },
                    {
                        "alt_operasyon": sub_op_2,
                        "hammadde": raw_mat,
                        "islem_adedi_1": 50,
                        "adet": 50,
                    },
                ],
            }
        )
        card1.insert(ignore_permissions=True)

        # Card 2 on JC1 under second KTA op
        card2 = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc1_name,
                "operasyon": second_kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 50,
                "operator": "operator1@kta.com",
                "durum": "Bitmiş",
                "baslangic_saati": "2026-11-19 10:00:00",
                "bitis_saati": "2026-11-19 10:20:00",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op_b1,
                        "hammadde": raw_mat,
                        "islem_adedi_1": 50,
                        "adet": 50,
                    }
                ],
            }
        )
        card2.insert(ignore_permissions=True)
        frappe.db.commit()

        result = get_work_order_card_analytics(wo_name)

        # 1. JC2 has no cards opened -> completely excluded from operations
        self.assertEqual(len(result["operations"]), 1)

        jc = result["operations"][0]
        self.assertEqual(jc["job_card"], jc1_name)
        self.assertEqual(jc["sequence_id"], 1)
        # Unique cards sum: 30 + 20 = 50.0
        self.assertEqual(jc["total_duration_mins"], 50.0)

        # 2. Hierarchical KTA operations under JC1 (sorted by op_code asc)
        self.assertEqual(len(jc["kta_operations"]), 2)
        kta_op_a = jc["kta_operations"][0]
        kta_op_b = jc["kta_operations"][1]

        self.assertEqual(kta_op_a["op_code"], self.kta_op)
        self.assertEqual(kta_op_a["total_duration_mins"], 30.0)

        self.assertEqual(kta_op_b["op_code"], second_kta_op)
        self.assertEqual(kta_op_b["total_duration_mins"], 20.0)

        # 3. Sub-operations under KTA Op A: OP10-0001, OP10-0002; OP10-0003 excluded
        self.assertEqual(len(kta_op_a["sub_operations"]), 2)
        self.assertEqual(kta_op_a["sub_operations"][0]["sub_op_id"], sub_op_1)
        self.assertEqual(kta_op_a["sub_operations"][1]["sub_op_id"], sub_op_2)

        # 4. Flat sub_operations list under Job Card contains all 3 active sub-operations
        self.assertEqual(len(jc["sub_operations"]), 3)
        sub_op_ids_in_jc = [s["sub_op_id"] for s in jc["sub_operations"]]
        self.assertIn(sub_op_1, sub_op_ids_in_jc)
        self.assertIn(sub_op_2, sub_op_ids_in_jc)
        self.assertIn(sub_op_b1, sub_op_ids_in_jc)
        # Unstarted sub-operation OP10-0003 is NOT present
        self.assertNotIn(f"{self.kta_op}-OP10-0003", sub_op_ids_in_jc)

    def test_material_reconciliation_calculation(self):
        wo_name = "TEST-WO-RECON-001"
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)
        jc_name = "TEST-JC-RECON-001"
        create_test_job_card(
            jc_name,
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        sub_op = self._create_sub_operation(
            "Reconciliation Cut", sequence=10, is_tuketim=1
        )

        item_completed = create_test_item(
            self.item_group, item_code="TEST-MAT-COMPLETED-001"
        )
        item_in_prog = create_test_item(
            self.item_group, item_code="TEST-MAT-INPROG-001"
        )
        item_unconsumed = create_test_item(
            self.item_group, item_code="TEST-MAT-UNCONSUMED-001"
        )
        item_over = create_test_item(self.item_group, item_code="TEST-MAT-OVER-001")
        item_extra = create_test_item(self.item_group, item_code="TEST-MAT-EXTRA-001")

        # Insert Work Order Items
        frappe.db.sql(
            """
            INSERT INTO `tabWork Order Item`
                (name, parent, parenttype, parentfield, item_code, item_name,
                 required_qty, stock_uom, operation, docstatus, idx)
            VALUES
                (%s, %s, 'Work Order', 'required_items', %s, 'Item Completed',
                 100.0, 'Nos', %s, 1, 1),
                (%s, %s, 'Work Order', 'required_items', %s, 'Item In Progress',
                 50.0, 'Nos', %s, 1, 2),
                (%s, %s, 'Work Order', 'required_items', %s, 'Item Unconsumed',
                 30.0, 'Nos', %s, 1, 3),
                (%s, %s, 'Work Order', 'required_items', %s, 'Item Over Consumed',
                 10.0, 'Nos', %s, 1, 4)
            """,
            (
                f"{wo_name}-ITM-1",
                wo_name,
                item_completed,
                self.erpnext_op,
                f"{wo_name}-ITM-2",
                wo_name,
                item_in_prog,
                self.erpnext_op,
                f"{wo_name}-ITM-3",
                wo_name,
                item_unconsumed,
                self.erpnext_op,
                f"{wo_name}-ITM-4",
                wo_name,
                item_over,
                self.erpnext_op,
            ),
        )
        frappe.db.commit()

        # Insert Card with consumptions
        card = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc_name,
                "operasyon": self.kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 100,
                "operator": "operator1@kta.com",
                "durum": "Bitmiş",
                "baslangic_saati": "2026-11-19 16:00:00",
                "bitis_saati": "2026-11-19 17:00:00",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op,
                        "hammadde": item_completed,
                        "adet": 100,
                        "hammadde_2": item_in_prog,
                        "adet_2": 20,
                        "hammadde_3": item_over,
                        "adet_3": 15,
                    },
                    {
                        "alt_operasyon": sub_op,
                        "hammadde": item_extra,
                        "adet": 5,
                    },
                ],
                "hurdalar": [
                    {
                        "parca_no": item_in_prog,
                        "miktar": 2.0,
                        "aciklama": "Setup Scrap",
                    },
                    {
                        "parca_no": item_extra,
                        "miktar": 1.0,
                        "aciklama": "Extra Scrap",
                    },
                ],
            }
        )
        card.insert(ignore_permissions=True)
        frappe.db.commit()

        result = get_work_order_card_analytics(wo_name)
        self.assertIn("material_reconciliation", result)
        recon_list = result["material_reconciliation"]

        # Ensure all entries have required fields
        for entry in recon_list:
            self.assertIn("item_code", entry)
            self.assertIn("planned_qty", entry)
            self.assertIn("consumed_qty", entry)
            self.assertIn("scrap_qty", entry)
            self.assertIn("variance", entry)
            self.assertIn("status", entry)
            self.assertIn("operators", entry)

        recon_by_code = {e["item_code"]: e for e in recon_list}

        # 1. 100% matched item
        completed_entry = recon_by_code[item_completed]
        self.assertEqual(completed_entry["planned_qty"], 100.0)
        self.assertEqual(completed_entry["consumed_qty"], 100.0)
        self.assertEqual(completed_entry["scrap_qty"], 0.0)
        self.assertEqual(completed_entry["total_spent"], 100.0)
        self.assertEqual(completed_entry["variance"], 0.0)
        self.assertEqual(completed_entry["status"], "Tamamlandı")
        self.assertEqual(completed_entry["status_badge"], "🟢 %100 Eşleşti")
        self.assertEqual(len(completed_entry["operators"]), 1)
        comp_op = completed_entry["operators"][0]
        self.assertEqual(comp_op["operator"], "operator1@kta.com")
        self.assertEqual(comp_op["operator_name"], "Ahmet Yilmaz")
        self.assertEqual(comp_op["consumed_qty"], 100.0)
        self.assertEqual(comp_op["card_count"], 1)
        self.assertEqual(comp_op["percentage"], 100.0)

        # 2. In progress item
        inprog_entry = recon_by_code[item_in_prog]
        self.assertEqual(inprog_entry["planned_qty"], 50.0)
        self.assertEqual(inprog_entry["consumed_qty"], 20.0)
        self.assertEqual(inprog_entry["scrap_qty"], 2.0)
        self.assertEqual(inprog_entry["total_spent"], 22.0)
        self.assertEqual(inprog_entry["variance"], -30.0)
        self.assertEqual(inprog_entry["status"], "Devam Ediyor")
        self.assertEqual(inprog_entry["status_badge"], "🟡 Devam Ediyor")
        self.assertEqual(len(inprog_entry["operators"]), 1)
        inprog_op = inprog_entry["operators"][0]
        self.assertEqual(inprog_op["operator"], "operator1@kta.com")
        self.assertEqual(inprog_op["operator_name"], "Ahmet Yilmaz")
        self.assertEqual(inprog_op["consumed_qty"], 20.0)
        self.assertEqual(inprog_op["card_count"], 1)
        self.assertEqual(inprog_op["percentage"], 100.0)

        # 3. No consumption item
        unconsumed_entry = recon_by_code[item_unconsumed]
        self.assertEqual(unconsumed_entry["planned_qty"], 30.0)
        self.assertEqual(unconsumed_entry["consumed_qty"], 0.0)
        self.assertEqual(unconsumed_entry["scrap_qty"], 0.0)
        self.assertEqual(unconsumed_entry["total_spent"], 0.0)
        self.assertEqual(unconsumed_entry["variance"], -30.0)
        self.assertEqual(unconsumed_entry["status"], "Tüketim Yok")
        self.assertEqual(unconsumed_entry["status_badge"], "⚪ Tüketim Yok")
        self.assertEqual(unconsumed_entry["operators"], [])

        # 4. Over consumed item
        over_entry = recon_by_code[item_over]
        self.assertEqual(over_entry["planned_qty"], 10.0)
        self.assertEqual(over_entry["consumed_qty"], 15.0)
        self.assertEqual(over_entry["scrap_qty"], 0.0)
        self.assertEqual(over_entry["total_spent"], 15.0)
        self.assertEqual(over_entry["variance"], 5.0)
        self.assertEqual(over_entry["status"], "Plan Aşımı")
        self.assertEqual(over_entry["status_badge"], "🔴 Plan Aşımı")
        self.assertEqual(len(over_entry["operators"]), 1)
        over_op = over_entry["operators"][0]
        self.assertEqual(over_op["operator"], "operator1@kta.com")
        self.assertEqual(over_op["operator_name"], "Ahmet Yilmaz")
        self.assertEqual(over_op["consumed_qty"], 15.0)
        self.assertEqual(over_op["card_count"], 1)
        self.assertEqual(over_op["percentage"], 100.0)

        # 5. Out-of-BOM item ("Reçete Dışı")
        extra_entry = recon_by_code[item_extra]
        self.assertEqual(extra_entry["planned_qty"], 0.0)
        self.assertEqual(extra_entry["consumed_qty"], 5.0)
        self.assertEqual(extra_entry["scrap_qty"], 1.0)
        self.assertEqual(extra_entry["total_spent"], 6.0)
        self.assertEqual(extra_entry["variance"], 5.0)
        self.assertEqual(extra_entry["status"], "Reçete Dışı")
        self.assertEqual(extra_entry["status_badge"], "🟣 Reçete Dışı")
        self.assertEqual(len(extra_entry["operators"]), 1)
        extra_op = extra_entry["operators"][0]
        self.assertEqual(extra_op["operator"], "operator1@kta.com")
        self.assertEqual(extra_op["operator_name"], "Ahmet Yilmaz")
        self.assertEqual(extra_op["consumed_qty"], 5.0)
        self.assertEqual(extra_op["card_count"], 1)
        self.assertEqual(extra_op["percentage"], 100.0)

        # 6. Sorting check: operation asc, item_code asc
        expected_sort = sorted(
            recon_list,
            key=lambda x: (x.get("operation") or "", x.get("item_code") or ""),
        )
        self.assertEqual(recon_list, expected_sort)

    def test_material_reconciliation_multi_operator_breakdown(self):
        """Verify operator breakdown percentage and desc sort for multi-operator consumption."""
        create_test_operator("operator2@kta.com", "Mehmet Demir")
        wo_name = "TEST-WO-MULTI-OP-001"
        create_test_work_order(wo_name, self.item, self.company, self.wip_warehouse)
        jc_name = "TEST-JC-MULTI-OP-001"
        create_test_job_card(
            jc_name,
            wo_name,
            self.wip_warehouse,
            self.erpnext_op,
            self.ws_name,
            self.item,
            self.company,
        )
        sub_op = self._create_sub_operation("Multi Op Cut", sequence=10, is_tuketim=1)
        shared_item = create_test_item(
            self.item_group, item_code="TEST-MAT-MULTI-OP-001"
        )

        frappe.db.sql(
            """
            INSERT INTO `tabWork Order Item`
                (name, parent, parenttype, parentfield, item_code, item_name,
                 required_qty, stock_uom, operation, docstatus, idx)
            VALUES
                (%s, %s, 'Work Order', 'required_items', %s, 'Shared Material',
                 100.0, 'Nos', %s, 1, 1)
            """,
            (f"{wo_name}-ITM-1", wo_name, shared_item, self.erpnext_op),
        )
        frappe.db.commit()

        # Card 1: Operator 1 consumes 75
        card1 = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc_name,
                "operasyon": self.kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 75,
                "operator": "operator1@kta.com",
                "durum": "Bitmiş",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op,
                        "hammadde": shared_item,
                        "adet": 75,
                    }
                ],
            }
        )
        card1.insert(ignore_permissions=True)

        # Card 2: Operator 2 consumes 25
        card2 = frappe.get_doc(
            {
                "doctype": "Calisma Karti",
                "custom_work_order": wo_name,
                "is_karti": jc_name,
                "operasyon": self.kta_op,
                "is_istasyonu": self.ws_name,
                "urun_kodu": self.item,
                "uretilecek_miktar": 25,
                "operator": "operator2@kta.com",
                "durum": "Bitmiş",
                "alt_operasyon_kayitlari": [
                    {
                        "alt_operasyon": sub_op,
                        "hammadde": shared_item,
                        "adet": 25,
                    }
                ],
            }
        )
        card2.insert(ignore_permissions=True)
        frappe.db.commit()

        result = get_work_order_card_analytics(wo_name)
        recon_list = result["material_reconciliation"]
        shared_entry = next(e for e in recon_list if e["item_code"] == shared_item)

        self.assertEqual(shared_entry["consumed_qty"], 100.0)
        self.assertEqual(len(shared_entry["operators"]), 2)

        # First operator: Highest consumer (75 units, 75.0%)
        op1 = shared_entry["operators"][0]
        self.assertEqual(op1["operator"], "operator1@kta.com")
        self.assertEqual(op1["operator_name"], "Ahmet Yilmaz")
        self.assertEqual(op1["consumed_qty"], 75.0)
        self.assertEqual(op1["card_count"], 1)
        self.assertEqual(op1["percentage"], 75.0)

        # Second operator: Lower consumer (25 units, 25.0%)
        op2 = shared_entry["operators"][1]
        self.assertEqual(op2["operator"], "operator2@kta.com")
        self.assertEqual(op2["operator_name"], "Mehmet Demir")
        self.assertEqual(op2["consumed_qty"], 25.0)
        self.assertEqual(op2["card_count"], 1)
        self.assertEqual(op2["percentage"], 25.0)
