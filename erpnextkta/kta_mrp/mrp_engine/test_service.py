# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
from unittest.mock import patch

import frappe

from erpnextkta.kta_mrp.mrp_engine import bom, service
from erpnextkta.kta_mrp.mrp_engine.demand import ProductionPlan

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


class TestProductionPlan(unittest.TestCase):
    def test_open_work_orders_are_not_counted_twice(self):
        plan = make_plan()
        self.assertEqual(plan.material_driving_qty("FG-1", "2026_w45"), 7)
        self.assertEqual(plan.material_driving_qty("FG-1", "2026_w46"), 5)
        self.assertEqual(plan.material_driving_qty("FG-3", "2026_w46"), 0)


class TestBomExplosion(unittest.TestCase):
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


class TestMaterialRequirementService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.db:
            import os

            os.chdir("/home/frappe/frappe-bench/sites")
            frappe.init(site="old.kta-endustri.com.tr")
            frappe.connect()

    def run_service(self, include_po=True):
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
        return service.get_material_requirements({}, include_po=include_po)

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




def terms():
    return frappe._dict(moq=50, pack=10, price=2.5, currency="EUR", lead_time_days=7)
