# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
from datetime import date
from unittest.mock import patch

import frappe

from erpnextkta.kta_mrp.mrp_engine import supply


class TestStock(unittest.TestCase):
    def test_only_available_stock_warehouses_are_used(self):
        calls = []

        def fake_get_all(doctype, **kwargs):
            calls.append((doctype, kwargs))
            if doctype == "Warehouse":
                return ["WH-OK"]
            return [frappe._dict(item_code="RM-1", actual=10, reserved=4)]

        with patch.object(supply.frappe, "get_all", side_effect=fake_get_all):
            result = supply.get_stock(["RM-1"])

        self.assertEqual(
            calls[0][1]["filters"]["warehouse_type"], "Kullanılabilir Stok"
        )
        self.assertEqual(calls[1][1]["filters"]["warehouse"], ["in", ["WH-OK"]])
        self.assertEqual(result["RM-1"], {"actual": 10, "reserved": 4})

    def test_no_available_warehouse_returns_empty(self):
        with patch.object(supply.frappe, "get_all", return_value=[]):
            self.assertEqual(supply.get_stock(["RM-1"]), {})


class TestOpenPoReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.db:
            import os

            os.chdir("/home/frappe/frappe-bench/sites")
            frappe.init(site="old.kta-endustri.com.tr")
            frappe.connect()

    def test_query_excludes_closed_and_on_hold_orders(self):
        query = str(supply.build_open_po_query(["RM-1"]))
        self.assertIn("NOT IN ('Closed','On Hold','Completed','Delivered')", query)
        self.assertIn("`stock_qty`", query)

    def test_pending_qty_is_converted_to_stock_uom(self):
        """10 koli (x12) sipariş, 4 koli teslim alınmış: 72 adet bekliyor."""
        rows = [
            frappe._dict(
                po_item_name="POI-1",
                item_code="RM-1",
                schedule_date=date(2026, 11, 10),
                stock_qty=120,
                received_qty=4,
                conversion_factor=12,
            )
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=rows),
            patch.object(supply, "get_open_pr_rows", return_value=[]),
        ):
            result = supply.get_open_po_receipts(["RM-1"], "2026_w45")
        self.assertEqual(dict(result["RM-1"]), {"2026_w46": 72})

    def test_overdue_po_goes_to_first_week(self):
        rows = [
            frappe._dict(
                po_item_name="POI-1",
                item_code="RM-1",
                schedule_date=date(2026, 9, 1),
                stock_qty=5,
                received_qty=0,
                conversion_factor=1,
            )
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=rows),
            patch.object(supply, "get_open_pr_rows", return_value=[]),
        ):
            result = supply.get_open_po_receipts(["RM-1"], "2026_w45")
        self.assertEqual(dict(result["RM-1"]), {"2026_w45": 5})

    def test_rows_without_pending_qty_or_date_are_skipped(self):
        rows = [
            frappe._dict(
                po_item_name="POI-1",
                item_code="RM-1",
                schedule_date=date(2026, 11, 10),
                stock_qty=12,
                received_qty=1,
                conversion_factor=12,
            ),
            frappe._dict(
                po_item_name="POI-2",
                item_code="RM-1",
                schedule_date=None,
                stock_qty=5,
                received_qty=0,
                conversion_factor=1,
            ),
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=rows),
            patch.object(supply, "get_open_pr_rows", return_value=[]),
        ):
            self.assertEqual(
                dict(supply.get_open_po_receipts(["RM-1"], "2026_w45")), {}
            )


class TestSupplyReconciliation(unittest.TestCase):
    """PO ve Taslak PR (KTA Mal Giriş Süreci) uzlaştırma testleri."""

    @classmethod
    def setUpClass(cls):
        if not frappe.db:
            import os

            os.chdir("/home/frappe/frappe-bench/sites")
            frappe.init(site="old.kta-endustri.com.tr")
            frappe.connect()

    def test_reconciliation_heals_reduced_po_quantity(self):
        """Kullanıcı PO'yu yanlışlıkla 32.650'ye düşürmüş olsa bile, antrepodaki PR sayesinde 32.650 tam sayılır."""
        po_rows = [
            frappe._dict(
                po_item_name="POI-KTA-1",
                po_name="PUR-ORD-1",
                item_code="10026441",
                schedule_date=date(2026, 11, 9),
                stock_qty=32650,
                received_qty=22460,  # pending = 10.190
                conversion_factor=1,
            )
        ]
        pr_rows = [
            frappe._dict(
                pr_item_name="PRI-1",
                pr_name="PREC-RET-05483",
                purchase_order="PUR-ORD-1",
                purchase_order_item="POI-KTA-1",
                item_code="10026441",
                workflow_state="Gümrüklemede",
                stock_qty=32650,
                qty=32650,
                conversion_factor=1,
                posting_date=date(2026, 11, 2),
                custom_gumruk_islem_baslama_tarihi=date(2026, 11, 2),
                tahmini_varis_tarihi=None,
            )
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=po_rows),
            patch.object(supply, "get_open_pr_rows", return_value=pr_rows),
        ):
            receipts, breakdown = supply.get_open_supplies(["10026441"], "2026_w45")

        # W45 haftasına (Gümrükleme başlama + 2 gün ile çözümlenmiş) tam 32.650 gelmeli
        self.assertEqual(dict(receipts["10026441"]), {"2026_w45": 32650.0})
        # Kırılımda gumruklemede 32.650, po_kalan 0 olmalı
        self.assertEqual(breakdown["10026441"].gumruklemede, 32650.0)
        self.assertEqual(breakdown["10026441"].po_kalan, 0.0)
        self.assertEqual(breakdown["10026441"].total, 32650.0)

    def test_antrepoda_waiting_in_pool_not_in_receipts(self):
        """Antrepoda bekleyen (çekim başlatılmamış) PR, receipts matrisine girmez fakat breakdown'da görünür."""
        po_rows = [
            frappe._dict(
                po_item_name="POI-KTA-1",
                po_name="PUR-ORD-1",
                item_code="10026441",
                schedule_date=date(2026, 11, 23),
                stock_qty=32650,
                received_qty=0,
                conversion_factor=1,
            )
        ]
        pr_rows = [
            frappe._dict(
                pr_item_name="PRI-1",
                pr_name="PREC-RET-05483",
                purchase_order="PUR-ORD-1",
                purchase_order_item="POI-KTA-1",
                item_code="10026441",
                workflow_state="Antrepoda",
                stock_qty=32650,
                qty=32650,
                conversion_factor=1,
                posting_date=date(2026, 11, 2),
                gumruge_gelis_tarihi=date(2026, 11, 2),
                tahmini_varis_tarihi=None,
            )
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=po_rows),
            patch.object(supply, "get_open_pr_rows", return_value=pr_rows),
        ):
            receipts, breakdown = supply.get_open_supplies(["10026441"], "2026_w45")

        # PR antrepoda beklediği için haftalık teslimata girmez (receipts boş kalır)
        self.assertEqual(dict(receipts["10026441"]), {})
        # Ancak breakdown havuzunda antrepoda olarak tam görünür
        self.assertEqual(breakdown["10026441"].antrepoda, 32650.0)
        self.assertEqual(breakdown["10026441"].total, 32650.0)

    def test_reconciliation_prevents_double_counting(self):
        """PO düzeltildiğinde (55.110), 32.650 adet iki kez sayılmaz."""
        po_rows = [
            frappe._dict(
                po_item_name="POI-KTA-1",
                po_name="PUR-ORD-1",
                item_code="10026441",
                schedule_date=date(2026, 11, 9),
                stock_qty=55110,
                received_qty=22460,  # pending = 32.650
                conversion_factor=1,
            )
        ]
        pr_rows = [
            frappe._dict(
                pr_item_name="PRI-1",
                pr_name="PREC-RET-05483",
                purchase_order="PUR-ORD-1",
                purchase_order_item="POI-KTA-1",
                item_code="10026441",
                workflow_state="Gümrüklemede",
                stock_qty=32650,
                qty=32650,
                conversion_factor=1,
                posting_date=date(2026, 11, 2),
                custom_gumruk_islem_baslama_tarihi=date(2026, 11, 2),
                tahmini_varis_tarihi=None,
            )
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=po_rows),
            patch.object(supply, "get_open_pr_rows", return_value=pr_rows),
        ):
            receipts, breakdown = supply.get_open_supplies(["10026441"], "2026_w45")

        self.assertEqual(dict(receipts["10026441"]), {"2026_w45": 32650.0})
        self.assertEqual(breakdown["10026441"].total, 32650.0)

    def test_partial_shipment_splits_pr_and_remaining_po(self):
        """32.650'lik siparişin 20.000'i yola çıkmış (W46), 12.650'si henüz sevk edilmemiş (W48)."""
        po_rows = [
            frappe._dict(
                po_item_name="POI-KTA-1",
                po_name="PUR-ORD-1",
                item_code="10026441",
                schedule_date=date(2026, 11, 23),  # W48
                stock_qty=32650,
                received_qty=0,
                conversion_factor=1,
            )
        ]
        pr_rows = [
            frappe._dict(
                pr_item_name="PRI-1",
                pr_name="PREC-RET-05483",
                purchase_order="PUR-ORD-1",
                purchase_order_item="POI-KTA-1",
                item_code="10026441",
                workflow_state="Yolda",
                stock_qty=20000,
                qty=20000,
                conversion_factor=1,
                posting_date=date(2026, 11, 2),
                tahmini_varis_tarihi=date(2026, 11, 9),  # W46
            )
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=po_rows),
            patch.object(supply, "get_open_pr_rows", return_value=pr_rows),
        ):
            receipts, breakdown = supply.get_open_supplies(["10026441"], "2026_w45")

        self.assertEqual(receipts["10026441"]["2026_w46"], 20000.0)
        self.assertEqual(receipts["10026441"]["2026_w48"], 12650.0)
        self.assertEqual(breakdown["10026441"].yolda, 20000.0)
        self.assertEqual(breakdown["10026441"].po_kalan, 12650.0)
        self.assertEqual(breakdown["10026441"].total, 32650.0)

    def test_gumruklemede_prefers_clearance_date_over_po_schedule_date(self):
        """Gümrüklemedeki malzeme PO'daki aylar sonraki termine değil, gümrükleme başlama tarihine (+2) göre konumlanır."""
        pr = frappe._dict(
            workflow_state="Gümrüklemede",
            custom_gumruk_islem_baslama_tarihi=date(2026, 11, 4),
            gumruge_gelis_tarihi=date(2026, 10, 1),
            tahmini_varis_tarihi=None,
            posting_date=date(2026, 11, 4),
        )
        # po_schedule_date 1 ay sonraya (Aralık) verilse bile:
        res_date, is_est, label = supply.resolve_pr_receipt_info(
            pr, po_schedule_date=date(2026, 12, 15), clearance_days=2
        )
        # 2026-11-04 + 2 gün = 2026-11-06 (aynı hafta W45)
        self.assertEqual(res_date, date(2026, 11, 6))
        self.assertFalse(is_est)
        self.assertIn("Gümrüklemede", label)

    def test_yolda_uses_tahmini_varis_tarihi(self):
        """Yoldaki malzeme için İthalat sekmesindeki ETA (tahmini_varis_tarihi) birincil önceliklidir."""
        pr = frappe._dict(
            workflow_state="Yolda",
            yukleme_tarihi=date(2026, 11, 2),
            tahmini_varis_tarihi=date(2026, 11, 13),
            posting_date=date(2026, 11, 2),
        )
        res_date, is_est, label = supply.resolve_pr_receipt_info(
            pr, po_schedule_date=date(2026, 12, 1), default_transit_days=7
        )
        self.assertEqual(res_date, date(2026, 11, 13))
        self.assertFalse(is_est)
        self.assertEqual(label, "Tahmini Varış (ETA)")

    def test_yolda_fallback_to_po_schedule_date_when_eta_missing(self):
        """ETA boş olduğunda ve PO teslim tarihi varsa PO terminine yaslanır."""
        pr = frappe._dict(
            workflow_state="Yolda",
            yukleme_tarihi=date(2026, 11, 5),
            tahmini_varis_tarihi=None,
            posting_date=date(2026, 11, 5),
        )
        res_date, is_est, label = supply.resolve_pr_receipt_info(
            pr, po_schedule_date=date(2026, 12, 20)
        )
        self.assertEqual(res_date, date(2026, 12, 20))
        self.assertTrue(is_est)
        self.assertIn("PO Termini", label)

    def test_yolda_fallback_to_yukleme_plus_transit_days(self):
        """ETA ve PO termin tarihi boş olduğunda yükleme tarihi + 7 gün fallback çalışır."""
        pr = frappe._dict(
            workflow_state="Yolda",
            yukleme_tarihi=date(2026, 11, 5),
            tahmini_varis_tarihi=None,
            posting_date=date(2026, 11, 5),
        )
        res_date, is_est, label = supply.resolve_pr_receipt_info(
            pr, po_schedule_date=None, default_transit_days=7
        )
        # 2026-11-05 + 7 gün = 2026-11-12
        self.assertEqual(res_date, date(2026, 11, 12))
        self.assertTrue(is_est)
        self.assertIn("Transit", label)

    def test_antrepoda_waiting_pool_does_not_force_receipt_date(self):
        """Antrepoda bekleyen (çekim başlatılmamış) teslimat haftalık teslime zorlanmaz (None döner)."""
        pr = frappe._dict(
            workflow_state="Antrepoda",
            gumruge_gelis_tarihi=date(2026, 11, 6),
            tahmini_varis_tarihi=None,
        )
        res_date, _is_est, label = supply.resolve_pr_receipt_info(pr)
        self.assertIsNone(res_date)
        self.assertIn("Bekliyor", label)

    def test_gumruklemede_adds_clearance_days(self):
        """Gümrükleme / Çekim başlatıldığında işlem tarihine tampon gün eklenerek kesin varış belirlenir."""
        pr = frappe._dict(
            workflow_state="Gümrüklemede",
            custom_gumruk_islem_baslama_tarihi=date(2026, 11, 6),
            gumruge_gelis_tarihi=date(2026, 10, 1),
        )
        # 0 gün tampon: doğrudan 2026-11-06
        self.assertEqual(
            supply.resolve_pr_receipt_date(pr, clearance_days=0),
            date(2026, 11, 6),
        )
        # 2 gün tampon: 2026-11-08
        res_date, _is_est, label = supply.resolve_pr_receipt_info(pr, clearance_days=2)
        self.assertEqual(res_date, date(2026, 11, 8))
        self.assertIn("Gümrüklemede", label)

    def test_mal_kabul_uyusmazligi_returns_none_date_and_label(self):
        """Mal Kabul Uyuşmazlığı statüsündeki irsaliye hiçbir tarihe bağlanmaz (None döner) ve arz = 0 kalır."""
        pr = frappe._dict(
            workflow_state="Mal Kabul Uyuşmazlığı",
            posting_date=date(2026, 11, 6),
            custom_uyusmazlik_nedeni="Fiziki Hasar / Kalite Problemi",
        )
        res_date, is_est, label = supply.resolve_pr_receipt_info(pr)
        self.assertIsNone(res_date)
        self.assertFalse(is_est)
        self.assertEqual(label, "Mal Kabul Uyuşmazlığı")

    def test_mal_kabul_uyusmazligi_excluded_from_weekly_receipts_and_tracked_in_breakdown(
        self,
    ):
        """Uyuşmazlıktaki irsaliye haftalık arza (receipts) 0 girer, ancak breakdown.uyusmazlikta ve details'ta raporlanır."""
        pr_rows = [
            frappe._dict(
                pr_item_name="PRI-1",
                pr_name="MAT-PRE-2026-00099",
                supplier="Tedarikçi A",
                workflow_state="Mal Kabul Uyuşmazlığı",
                posting_date=date(2026, 11, 10),
                item_code="RM-1",
                stock_qty=500,
                qty=500,
                conversion_factor=1,
                purchase_order=None,
                purchase_order_item=None,
                custom_uyusmazlik_nedeni="Evrak / İrsaliye Uyuşmazlığı",
                custom_uyusmazlik_aciklamasi="Adet eksik",
            )
        ]
        with (
            patch.object(supply, "get_open_po_rows", return_value=[]),
            patch.object(supply, "get_open_pr_rows", return_value=pr_rows),
        ):
            receipts, breakdown = supply.get_open_supplies(["RM-1"], "2026_w45")

        # Haftalık arz 0 olmalı
        self.assertEqual(len(receipts["RM-1"]), 0)
        # Breakdown'da uyusmazlikta olarak görünmeli
        self.assertEqual(breakdown["RM-1"].uyusmazlikta, 500)
        self.assertEqual(
            breakdown["RM-1"].details[0].dispute_reason, "Evrak / İrsaliye Uyuşmazlığı"
        )


class TestBuyingTerms(unittest.TestCase):
    def test_default_supplier_map_takes_first_supplier(self):
        rows = [
            frappe._dict(parent="RM-1", default_supplier="SUP-A"),
            frappe._dict(parent="RM-1", default_supplier="SUP-B"),
            frappe._dict(parent="RM-2", default_supplier="SUP-C"),
        ]
        with patch.object(supply.frappe, "get_all", return_value=rows):
            result = supply.get_default_suppliers(["RM-1", "RM-2"])
        self.assertEqual(result, {"RM-1": "SUP-A", "RM-2": "SUP-C"})

    def test_terms_use_latest_price_of_default_supplier(self):
        prices = [  # valid_from desc sıralı
            price("RM-1", "SUP-X", 999, 9, 1.0, "USD", 1),
            price("RM-1", "SUP-A", 100, 10, 2.5, "EUR", 14),
            price("RM-1", "SUP-A", 50, 5, 2.0, "EUR", 7),
            price("RM-2", "SUP-C", None, None, None, "TRY", None),
        ]
        with patch.object(supply.frappe, "get_all", return_value=prices):
            result = supply.get_buying_terms({"RM-1": "SUP-A", "RM-2": "SUP-C"})
        self.assertEqual(
            result["RM-1"],
            {
                "moq": 100,
                "pack": 10,
                "price": 2.5,
                "currency": "EUR",
                "lead_time_days": 14,
            },
        )
        self.assertEqual(
            result["RM-2"],
            {"moq": 0, "pack": 1, "price": 0, "currency": "TRY", "lead_time_days": 0},
        )

    def test_empty_input(self):
        self.assertEqual(supply.get_buying_terms({}), {})
        self.assertEqual(supply.get_default_suppliers([]), {})


def price(item_code, supplier, moq, pack, rate, currency, lead_time):
    return frappe._dict(
        item_code=item_code,
        supplier=supplier,
        custom_minimum_order_quantity=moq,
        custom_minimum_paketleme_miktari=pack,
        price_list_rate=rate,
        currency=currency,
        lead_time_days=lead_time,
    )


class TestForeignSupplier(unittest.TestCase):
    def test_is_foreign_supplier_hybrid_rule(self):
        """Foreign supplier check respects both country != Turkey and supplier_group == 'YD-Hammadde'."""
        from erpnextkta.kta_mrp.mrp_engine.supply import is_foreign_supplier

        # Foreign country
        self.assertTrue(
            is_foreign_supplier(
                frappe._dict(country="Germany", supplier_group="YD-Hammadde")
            )
        )
        # Country left as Turkey by mistake but group is YD-Hammadde
        self.assertTrue(
            is_foreign_supplier(
                frappe._dict(country="Turkey", supplier_group="YD-Hammadde")
            )
        )
        # Foreign country even if group is not set
        self.assertTrue(
            is_foreign_supplier(frappe._dict(country="Germany", supplier_group="Diğer"))
        )
        # Domestic supplier
        self.assertFalse(
            is_foreign_supplier(
                frappe._dict(country="Turkey", supplier_group="Yİ-Hammadde")
            )
        )
        # None or empty
        self.assertFalse(is_foreign_supplier(None))
