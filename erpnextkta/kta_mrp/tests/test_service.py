# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

from unittest.mock import patch

import frappe

from erpnextkta.kta_mrp.mrp_engine import bom, service
from erpnextkta.kta_mrp.mrp_engine.demand import ProductionPlan
from erpnextkta.tests.test_utils import KTAUnitTestCase

WEEKS = ["2026_w45", "2026_w46"]


def make_plan():
    return ProductionPlan(
        weeks=WEEKS,
        planned={"FG-1": {"2026_w45": 10, "2026_w46": 5}, "FG-2": {"2026_w46": 4}},
        work_orders={"FG-1": {"2026_w45": 3}},
    )


def explosion_items():
    return {
        "BOM-1": [frappe._dict(item_code="RM-1", stock_qty=2, stock_uom="Nos")],
        "BOM-2": [frappe._dict(item_code="RM-1", stock_qty=1, stock_uom="Nos")],
    }


class TestProductionPlan(KTAUnitTestCase):
    def test_open_work_orders_are_not_counted_twice(self):
        plan = make_plan()
        self.assertEqual(plan.material_driving_qty("FG-1", "2026_w45"), 7)
        self.assertEqual(plan.material_driving_qty("FG-1", "2026_w46"), 5)
        self.assertEqual(plan.material_driving_qty("FG-3", "2026_w46"), 0)

    def test_capacity_leveled_wo_consumption_driving_qty(self):
        """Kapasiteye dağıtılmış tüketim modunda iş emirleri plandan düşülmez."""
        plan = ProductionPlan(
            weeks=["2026_w47"],
            planned={"ITEM-A": {"2026_w47": 7000}},
            work_orders={"ITEM-A": {"2026_w47": 2000}},
        )
        # Klasik mod: 7000 - 2000 = 5000
        self.assertEqual(plan.material_driving_qty("ITEM-A", "2026_w47", capacity_leveled=False), 5000)
        # Kapasite modu: toplam planlanan 7000 doğrudan hammadde talep eder
        self.assertEqual(plan.material_driving_qty("ITEM-A", "2026_w47", capacity_leveled=True), 7000)


class TestBomExplosion(KTAUnitTestCase):
    def test_gross_and_pegging(self):
        with (
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
        ):
            result = bom.explode(make_plan())
        self.assertEqual(dict(result.gross["RM-1"]), {"2026_w45": 14, "2026_w46": 14})
        self.assertEqual(
            dict(result.pegging[("RM-1", "FG-2", "BOM-2")]), {"2026_w46": 4}
        )
        self.assertEqual(result.uoms, {"RM-1": "Nos"})


class TestMaterialRequirementService(KTAUnitTestCase):
    def run_service(self, include_po=True, filters=None):
        patches = [
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(service, "get_item_meta", return_value={}),
            patch.object(
                service.supply, "get_default_suppliers", return_value={"RM-1": "SUP-A"}
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=10, reserved=6)},
            ),
            patch.object(
                service.supply,
                "get_open_supplies",
                return_value=({"RM-1": {"2026_w46": 100}}, {}),
            ),
            patch.object(
                service.supply,
                "get_open_po_receipts",
                return_value={"RM-1": {"2026_w46": 100}},
            ),
        ]
        for p in patches:
            p.start()
        self.addCleanup(patch.stopall)
        return service.get_material_requirements(filters or {}, include_po=include_po)

    def test_material_is_netted_with_free_stock_and_po(self):
        material = self.run_service().materials["RM-1"]
        self.assertEqual(material.free_stock, 4)
        self.assertEqual(material.netting.net, {"2026_w45": 10, "2026_w46": 0})
        self.assertEqual(material.netting.planned_orders["2026_w45"], 50)
        self.assertEqual(material.order_amount, 125)
        self.assertEqual(
            (material.supplier, material.currency, material.uom),
            ("SUP-A", "EUR", "Nos"),
        )

    def test_material_free_stock_with_classic_wo_consumption_strategy(self):
        # Varsayılan klasik stratejide rezervasyonlar stoktan peşin düşülür
        material = self.run_service(
            filters={"wo_consumption_strategy": "Anlık Stok Rezervasyonu (Klasik)"}
        ).materials["RM-1"]
        self.assertEqual(material.actual, 10)
        self.assertEqual(material.reserved, 6)
        self.assertEqual(material.free_stock, 4)
        self.assertTrue(material.deduct_reservations)
        self.assertFalse(material.capacity_leveled)
        # Net ihtiyaç: gross (14) - free_stock (4) = 10
        self.assertEqual(material.netting.net, {"2026_w45": 10, "2026_w46": 0})

    def test_capacity_leveled_wo_consumption_strategy_material_requirements(self):
        # Kapasiteye Dağıtılmış Tüketim modunda:
        # 1. free_stock = actual (reserved stoktan düşülmez, zaman fazlı tüketilir)
        # 2. gross demand = planned (iş emirleri plandan peşin düşülmez)
        material = self.run_service(
            filters={"wo_consumption_strategy": "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)"}
        ).materials["RM-1"]
        self.assertEqual(material.actual, 10)
        self.assertEqual(material.reserved, 6)
        self.assertEqual(material.free_stock, 10)
        self.assertFalse(material.deduct_reservations)
        self.assertTrue(material.capacity_leveled)
        # FG-1 planned W45=10 (klasikte 10-3=7 idi, gross 14 idi). Kapasitede gross = 10 * 2 = 20.
        self.assertEqual(material.netting.gross["2026_w45"], 20)
        # Net: gross (20) - free_stock (10) = 10.
        self.assertEqual(material.netting.net, {"2026_w45": 10, "2026_w46": 0})

    def test_material_requirement_summary_alias_and_property(self):
        from erpnextkta.kta_mrp.mrp_engine.service import (
            MaterialRequirementSummary,
            _build_single_material,
        )

        self.assertIs(MaterialRequirementSummary, service.MaterialRequirement)
        self.assertIs(_build_single_material, service.build_material)

    def test_po_is_ignored_when_not_included(self):
        material = self.run_service(include_po=False).materials["RM-1"]
        self.assertEqual(material.netting.receipts_total, 0)

    def test_pegging_keeps_finished_item_breakdown(self):
        pegging = {(p.finished_item, p.total) for p in self.run_service().pegging}
        self.assertEqual(pegging, {("FG-1", 24), ("FG-2", 4)})

    def test_get_material_requirements_data_structure(self):
        with (
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(service, "get_item_meta", return_value={}),
            patch.object(
                service.supply, "get_default_suppliers", return_value={"RM-1": "SUP-A"}
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=10, reserved=6)},
            ),
            patch.object(
                service.supply,
                "get_open_po_receipts",
                return_value={"RM-1": {"2026_w46": 100}},
            ),
            patch.object(service.supply, "get_open_po_rows", return_value=[]),
        ):
            data = service.get_material_requirements_data({})
            self.assertIn("weeks", data)
            self.assertIn("materials", data)
            self.assertIn("summary", data)
            self.assertEqual(len(data["materials"]), 1)
            mat = data["materials"][0]
            self.assertEqual(mat["item_code"], "RM-1")
            self.assertIn("weeks", mat)
            self.assertIn("2026_w45", mat["weeks"])
            self.assertEqual(mat["weeks"]["2026_w45"]["order"], 50)
            self.assertIn("sourcing_strategy", mat)
            self.assertIn("suppliers_quota", mat)
            self.assertIn("planned_orders_by_supplier", mat)

    def test_get_material_requirements_data_reservation_toggle(self):
        with (
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(service, "get_item_meta", return_value={}),
            patch.object(
                service.supply, "get_default_suppliers", return_value={"RM-1": "SUP-A"}
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=10, reserved=6)},
            ),
            patch.object(
                service.supply,
                "get_open_po_receipts",
                return_value={"RM-1": {"2026_w46": 100}},
            ),
            patch.object(service.supply, "get_open_po_rows", return_value=[]),
        ):
            # wo_consumption_strategy = "Anlık Stok Rezervasyonu (Klasik)" ile çağrı
            data = service.get_material_requirements_data(
                {"wo_consumption_strategy": "Anlık Stok Rezervasyonu (Klasik)"}
            )
            self.assertTrue(data["settings"]["deduct_work_order_reservations"])
            self.assertFalse(data["settings"]["is_capacity_leveled_consumption"])
            mat = data["materials"][0]
            self.assertEqual(mat["actual_stock"], 10)
            self.assertEqual(mat["reserved_stock"], 6)
            self.assertEqual(mat["free_stock"], 4)
            self.assertEqual(mat["weeks"]["2026_w45"]["net"], 10)

    def test_get_material_requirements_data_capacity_leveled_strategy(self):
        with (
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(service, "get_item_meta", return_value={}),
            patch.object(
                service.supply, "get_default_suppliers", return_value={"RM-1": "SUP-A"}
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=10, reserved=6)},
            ),
            patch.object(
                service.supply,
                "get_open_po_receipts",
                return_value={"RM-1": {"2026_w46": 100}},
            ),
            patch.object(service.supply, "get_open_po_rows", return_value=[]),
        ):
            data = service.get_material_requirements_data(
                {"wo_consumption_strategy": "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)"}
            )
            self.assertEqual(
                data["settings"]["wo_consumption_strategy"],
                "Kapasiteye Dağıtılmış Tüketim (Zaman Fazlı)",
            )
            self.assertTrue(data["settings"]["is_capacity_leveled_consumption"])
            self.assertFalse(data["settings"]["deduct_work_order_reservations"])
            mat = data["materials"][0]
            self.assertEqual(mat["actual_stock"], 10)
            self.assertEqual(mat["reserved_stock"], 6)
            self.assertEqual(mat["free_stock"], 10)
            self.assertTrue(mat["capacity_leveled"])
            # In capacity leveled mode: gross for FG-1 W45 is planned(10) * 2 = 20 (wo not subtracted)
            self.assertEqual(mat["weeks"]["2026_w45"]["gross"], 20)
            # Net: gross(20) - free_stock(10) = 10
            self.assertEqual(mat["weeks"]["2026_w45"]["net"], 10)

    def test_sourcing_integration_quota(self):
        # Shortage (14) >= total_moq (10) -> kotalı dağılım gerçekleşir
        sourcing_cfg = {
            "RM-1": frappe._dict(
                strategy="Kotalı Dağılım (% Paylaşım)",
                default_supplier="SUP-A",
                suppliers=[
                    frappe._dict(
                        supplier="SUP-A",
                        quota_share=60.0,
                        moq=5,
                        pack=5,
                        price=2.0,
                        currency="EUR",
                        lead_time_days=7,
                        is_default=True,
                    ),
                    frappe._dict(
                        supplier="SUP-B",
                        quota_share=40.0,
                        moq=5,
                        pack=5,
                        price=1.5,
                        currency="EUR",
                        lead_time_days=7,
                        is_default=False,
                    ),
                ],
            )
        }
        with (
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(service, "get_item_meta", return_value={}),
            patch.object(
                service.supply, "get_item_sourcing_configs", return_value=sourcing_cfg
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=0, reserved=0)},
            ),
            patch.object(service.supply, "get_open_supplies", return_value=({}, {})),
        ):
            data = service.get_material_requirements_data({})
            mat = data["materials"][0]
            self.assertEqual(mat["sourcing_strategy"], "Kotalı Dağılım (% Paylaşım)")
            self.assertEqual(len(mat["suppliers_quota"]), 2)
            # Gross demand in W45 is 14
            # SUP-A: 14 * 0.6 = 8.4 -> moq 5, pack 5 -> 10
            # SUP-B: 14 * 0.4 = 5.6 -> moq 5, pack 5 -> 10
            self.assertEqual(mat["planned_orders_by_supplier"]["SUP-A"]["2026_w45"], 10)
            self.assertEqual(mat["planned_orders_by_supplier"]["SUP-B"]["2026_w45"], 10)
            # Total order for W45 = 20
            self.assertEqual(mat["weeks"]["2026_w45"]["order"], 20)

    def test_sourcing_integration_quota_small_shortage_consolidates(self):
        # Shortage (14) < total_moq (20) -> ana tedarikçide toplanır
        sourcing_cfg = {
            "RM-1": frappe._dict(
                strategy="Kotalı Dağılım (% Paylaşım)",
                default_supplier="SUP-A",
                suppliers=[
                    frappe._dict(
                        supplier="SUP-A",
                        quota_share=60.0,
                        moq=10,
                        pack=5,
                        price=2.0,
                        currency="EUR",
                        lead_time_days=7,
                        is_default=True,
                    ),
                    frappe._dict(
                        supplier="SUP-B",
                        quota_share=40.0,
                        moq=10,
                        pack=5,
                        price=1.5,
                        currency="EUR",
                        lead_time_days=7,
                        is_default=False,
                    ),
                ],
            )
        }
        with (
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(service, "get_item_meta", return_value={}),
            patch.object(
                service.supply, "get_item_sourcing_configs", return_value=sourcing_cfg
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=0, reserved=0)},
            ),
            patch.object(service.supply, "get_open_supplies", return_value=({}, {})),
        ):
            data = service.get_material_requirements_data({})
            mat = data["materials"][0]
            # 14 < (10 + 10): SUP-A'da toplanır -> 14 için pack=5, moq=10 -> 15
            self.assertEqual(mat["planned_orders_by_supplier"]["SUP-A"]["2026_w45"], 15)
            self.assertEqual(
                mat["planned_orders_by_supplier"].get("SUP-B", {}).get("2026_w45", 0), 0
            )
            self.assertEqual(mat["weeks"]["2026_w45"]["order"], 15)

    def test_safety_stock_passed_to_netting(self):
        sourcing_cfg = {
            "RM-1": frappe._dict(
                strategy="Varsayılan Tedarikçi (%100)",
                default_supplier="SUP-A",
                suppliers=[],
            )
        }
        with (
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(
                service,
                "get_item_meta",
                return_value={"RM-1": frappe._dict(safety_stock=50)},
            ),
            patch.object(
                service.supply, "get_item_sourcing_configs", return_value=sourcing_cfg
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=60, reserved=0)},
            ),
            patch.object(service.supply, "get_open_supplies", return_value=({}, {})),
        ):
            data = service.get_material_requirements_data({})
            mat = data["materials"][0]
            # Demand is 14, stock is 60, safety stock is 50.
            # Available (60) - demand (14) = 46 < 50 safety stock!
            # Shortage should be: 14 + 50 - 60 = 4. With moq=50, pack=10 -> order is 50.
            self.assertEqual(mat["safety_stock"], 50)
            self.assertEqual(mat["weeks"]["2026_w45"]["net"], 4)
            self.assertEqual(mat["weeks"]["2026_w45"]["order"], 50)

    def test_disputed_pr_in_material_requirements_data(self):
        """Mal Kabul Uyuşmazlığı verisi uyusmazlikta_total ve open_supplies altında doğru serialize edilmelidir."""
        bd = frappe._dict(
            antrepoda=0,
            gumruklemede=0,
            yolda=0,
            po_kalan=0,
            uyusmazlikta=350,
            total=350,
            details=[
                frappe._dict(
                    type="PR",
                    name="PR-01",
                    supplier="SUP-A",
                    state="Mal Kabul Uyuşmazlığı",
                    qty=350,
                    date=None,
                    week=None,
                    date_label="Mal Kabul Uyuşmazlığı",
                    is_estimated=False,
                    loading_date=None,
                    eta_date=None,
                    customs_date=None,
                    clearance_start_date=None,
                    dispute_reason="Fiziki Hasar / Kalite Problemi",
                    dispute_description="Koliler ıslak",
                )
            ],
        )
        with (
            patch.object(
                service.demand, "get_production_plan", return_value=make_plan()
            ),
            patch.object(
                bom, "get_default_boms", return_value={"FG-1": "BOM-1", "FG-2": "BOM-2"}
            ),
            patch.object(bom, "get_explosion_items", return_value=explosion_items()),
            patch.object(service, "get_item_meta", return_value={}),
            patch.object(
                service.supply, "get_default_suppliers", return_value={"RM-1": "SUP-A"}
            ),
            patch.object(
                service.supply, "get_buying_terms", return_value={"RM-1": terms()}
            ),
            patch.object(
                service.supply,
                "get_stock",
                return_value={"RM-1": frappe._dict(actual=0, reserved=0)},
            ),
            patch.object(
                service.supply, "get_open_supplies", return_value=({}, {"RM-1": bd})
            ),
        ):
            data = service.get_material_requirements_data({})
            mat = data["materials"][0]
            self.assertEqual(mat["uyusmazlikta_total"], 350)
            self.assertEqual(len(mat["open_supplies"]), 1)
            self.assertEqual(
                mat["open_supplies"][0]["dispute_reason"],
                "Fiziki Hasar / Kalite Problemi",
            )
            self.assertEqual(
                mat["open_supplies"][0]["dispute_description"], "Koliler ıslak"
            )
            self.assertEqual(mat["open_supplies"][0]["state"], "Mal Kabul Uyuşmazlığı")

    def test_get_material_requirements_data_filtering_and_summary(self):
        from erpnextkta.kta_mrp.mrp_engine.netting import net_material
        from erpnextkta.kta_mrp.mrp_engine.service import (
            MaterialRequirement,
            MaterialRequirementResult,
        )

        weeks = ["2026_w45", "2026_w46"]
        m1 = MaterialRequirement(
            item_code="KABLO-01",
            item_name="Otomotiv Kablosu FLRY-B",
            uom="M",
            supplier="TEDARIKCI-ALPHA",
            actual=100,
            reserved=20,
            netting=net_material(
                weeks, {"2026_w45": 50, "2026_w46": 100}, free_stock=80
            ),
            item_group="Kablo Grubu",
            price=1.5,
            currency="EUR",
        )
        m2 = MaterialRequirement(
            item_code="TERMINAL-02",
            item_name="Disi Terminal 2.8mm",
            uom="Adet",
            supplier="TEDARIKCI-BETA",
            actual=20,
            reserved=0,
            netting=net_material(
                weeks, {"2026_w45": 10, "2026_w46": 10}, free_stock=20
            ),
            item_group="Terminal Grubu",
            price=0.2,
            currency="USD",
        )
        m3 = MaterialRequirement(
            item_code="KONTAKT-03",
            item_name="Konnektor Kilidi",
            uom="Adet",
            supplier="TEDARIKCI-ALPHA",
            actual=0,
            reserved=0,
            netting=net_material(weeks, {"2026_w45": 20, "2026_w46": 30}, free_stock=0),
            item_group="Plastik Grubu",
            price=0.5,
            currency="EUR",
        )

        mock_result = MaterialRequirementResult(
            weeks=weeks,
            materials={"KABLO-01": m1, "TERMINAL-02": m2, "KONTAKT-03": m3},
            pegging=[],
        )

        with patch.object(
            service, "get_material_requirements", return_value=mock_result
        ):
            # 1. No filters: all 3 items returned
            all_data = service.get_material_requirements_data({})
            self.assertEqual(len(all_data["materials"]), 3)
            self.assertEqual(all_data["summary"]["total_items"], 3)

            # 2. Filter by hammadde (matching item_code case-insensitive)
            kablo_data = service.get_material_requirements_data({"hammadde": "kablo"})
            self.assertEqual(len(kablo_data["materials"]), 1)
            self.assertEqual(kablo_data["materials"][0]["item_code"], "KABLO-01")
            self.assertEqual(kablo_data["summary"]["total_items"], 1)

            # 3. Filter by hammadde (matching item_name case-insensitive)
            name_data = service.get_material_requirements_data({"hammadde": "terminal"})
            self.assertEqual(len(name_data["materials"]), 1)
            self.assertEqual(name_data["materials"][0]["item_code"], "TERMINAL-02")
            self.assertEqual(name_data["summary"]["total_items"], 1)

            # 4. Filter by supplier (case-insensitive)
            beta_data = service.get_material_requirements_data({"supplier": "beta"})
            self.assertEqual(len(beta_data["materials"]), 1)
            self.assertEqual(beta_data["materials"][0]["supplier"], "TEDARIKCI-BETA")
            self.assertEqual(beta_data["summary"]["total_items"], 1)

            alpha_data = service.get_material_requirements_data({"supplier": "alpha"})
            self.assertEqual(len(alpha_data["materials"]), 2)
            self.assertEqual(alpha_data["summary"]["total_items"], 2)

            # 5. Filter by item_group (case-insensitive)
            plastik_data = service.get_material_requirements_data(
                {"item_group": "plastik"}
            )
            self.assertEqual(len(plastik_data["materials"]), 1)
            self.assertEqual(plastik_data["materials"][0]["item_code"], "KONTAKT-03")
            self.assertEqual(plastik_data["summary"]["total_items"], 1)

            # 6. Check summary values match the filtered results
            self.assertEqual(plastik_data["summary"]["shortage_count"], 1)
            self.assertEqual(plastik_data["summary"]["sufficient_count"], 0)
            self.assertIn("EUR", plastik_data["summary"]["order_amount_by_currency"])

            # 7. Filter matching nothing
            none_data = service.get_material_requirements_data(
                {"hammadde": "nonexistent"}
            )
            self.assertEqual(len(none_data["materials"]), 0)
            self.assertEqual(none_data["summary"]["total_items"], 0)
            self.assertEqual(none_data["summary"]["shortage_count"], 0)
            self.assertEqual(none_data["summary"]["order_amount_by_currency"], {})

    def test_export_material_requirements_excel_multi_sheet(self):
        import io

        import openpyxl
        from frappe import _

        mock_data = {
            "weeks": [
                {"key": "2026_w45", "label": "2026-W45 (02-08 Kas)"},
                {"key": "2026_w46", "label": "2026-W46 (09-15 Kas)"},
            ],
            "materials": [
                {
                    "item_code": "RM-01",
                    "item_name": "Bakır Tel 1.5mm",
                    "uom": "M",
                    "supplier": "SUP-ALPHA",
                    "actual_stock": 100.0,
                    "reserved_stock": 20.0,
                    "free_stock": 80.0,
                    "lead_time_days": 14,
                    "moq": 500,
                    "pack": 100,
                    "unit_price": 2.5,
                    "currency": "EUR",
                    "order_amount": 1250.0,
                    "weeks": {
                        "2026_w45": {
                            "order": 500.0,
                            "net": 400.0,
                            "gross": 480.0,
                            "projected": 100.0,
                        },
                        "2026_w46": {
                            "order": 0.0,
                            "net": 0.0,
                            "gross": 50.0,
                            "projected": 50.0,
                        },
                    },
                    "pegging": [
                        {
                            "finished_item": "FG-01",
                            "item_name": "Kablo Demeti A",
                            "bom": "BOM-FG01-001",
                            "customer_group": "OEM",
                            "total": 300.0,
                            "weeks": {"2026_w45": 250.0, "2026_w46": 50.0},
                        },
                        {
                            "finished_item": "FG-02",
                            "item_name": "Kablo Demeti B",
                            "bom": "BOM-FG02-001",
                            "customer_group": "Aftermarket",
                            "total": 230.0,
                            "weeks": {"2026_w45": 230.0, "2026_w46": 0.0},
                        },
                    ],
                }
            ],
        }

        with patch.object(
            service, "get_material_requirements_data", return_value=mock_data
        ):
            service.export_material_requirements_excel({})

            self.assertEqual(frappe.response["type"], "binary")
            self.assertTrue(
                frappe.response["filename"].startswith("Hammadde_Ihtiyac_Planlama_")
            )

            wb = openpyxl.load_workbook(io.BytesIO(frappe.response["filecontent"]))
            self.assertIn(_("Hammadde İhtiyaç Planlama"), wb.sheetnames)
            self.assertIn(_("Talep ve Bitmiş Ürünler"), wb.sheetnames)

            # Check Sheet 1
            ws1 = wb[_("Hammadde İhtiyaç Planlama")]
            self.assertEqual(ws1.cell(row=1, column=1).value, _("Hammadde Kodu"))
            self.assertEqual(ws1.cell(row=2, column=1).value, "RM-01")

            # Check Sheet 2
            ws2 = wb[_("Talep ve Bitmiş Ürünler")]
            expected_headers2 = [
                _("Hammadde Kodu"),
                _("Hammadde Açıklaması"),
                _("Birim"),
                _("Varsayılan Tedarikçi"),
                _("Bitmiş Ürün Kodu"),
                _("Bitmiş Ürün Açıklaması"),
                _("BOM"),
                _("Müşteri Grubu"),
                _("Toplam Talep"),
                "2026-W45 (02-08 Kas)",
                "2026-W46 (09-15 Kas)",
            ]
            actual_headers2 = [
                ws2.cell(row=1, column=c).value
                for c in range(1, len(expected_headers2) + 1)
            ]
            self.assertEqual(actual_headers2, expected_headers2)

            # Sheet 2 should have 2 pegging data rows
            self.assertEqual(ws2.max_row, 3)

            # Row 2 (FG-01)
            row2_values = [
                ws2.cell(row=2, column=c).value
                for c in range(1, len(expected_headers2) + 1)
            ]
            self.assertEqual(
                row2_values,
                [
                    "RM-01",
                    "Bakır Tel 1.5mm",
                    "M",
                    "SUP-ALPHA",
                    "FG-01",
                    "Kablo Demeti A",
                    "BOM-FG01-001",
                    "OEM",
                    300.0,
                    250.0,
                    50.0,
                ],
            )

            # Row 3 (FG-02)
            row3_values = [
                ws2.cell(row=3, column=c).value
                for c in range(1, len(expected_headers2) + 1)
            ]
            self.assertEqual(
                row3_values,
                [
                    "RM-01",
                    "Bakır Tel 1.5mm",
                    "M",
                    "SUP-ALPHA",
                    "FG-02",
                    "Kablo Demeti B",
                    "BOM-FG02-001",
                    "Aftermarket",
                    230.0,
                    230.0,
                    0.0,
                ],
            )

            # Number formats on ws2 for columns 9, 10, 11
            self.assertEqual(ws2.cell(row=2, column=9).number_format, "#,##0.00")
            self.assertEqual(ws2.cell(row=2, column=10).number_format, "#,##0.00")
            self.assertEqual(ws2.cell(row=2, column=11).number_format, "#,##0.00")


def terms():
    return frappe._dict(moq=50, pack=10, price=2.5, currency="EUR", lead_time_days=7)
