# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import frappe

from erpnextkta.kta_mrp.report.mrp_analysis import mrp_analysis
from erpnextkta.tests.test_utils import KTABaseTestCase


class TestMrpAnalysisReservationsAndFilters(KTABaseTestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(frappe.local, "site", None):
            frappe.init("development.localhost")
            frappe.connect()

        cls.setup_test_fixtures()

    @classmethod
    def setup_test_fixtures(cls):
        """Boş test sistemlerinde (CI test runner) deterministik test ortamı hazırlar."""
        company = frappe.db.get_value("Company", filters={}, fieldname="name")
        if not company:
            company = (
                frappe.get_doc(
                    {
                        "doctype": "Company",
                        "company_name": "_Test Company",
                        "abbr": "_TC",
                        "default_currency": "TRY",
                        "country": "Turkey",
                    }
                )
                .insert(ignore_permissions=True, ignore_if_duplicate=True)
                .name
            )

        # 1. Warehouse Type & Depo (Kullanılabilir Stok)
        if not frappe.db.exists("Warehouse Type", "Kullanılabilir Stok"):
            frappe.get_doc(
                {
                    "doctype": "Warehouse Type",
                    "name": "Kullanılabilir Stok",
                }
            ).insert(ignore_permissions=True)

        wh_name = frappe.db.get_value(
            "Warehouse", {"warehouse_type": "Kullanılabilir Stok", "company": company}
        )
        if not wh_name:
            wh = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": "_Test Kullanilabilir Depo",
                    "warehouse_type": "Kullanılabilir Stok",
                    "company": company,
                }
            ).insert(ignore_permissions=True)
            wh_name = wh.name
        cls.warehouse = wh_name

        # 2. UOM ve Item Group
        for u_name in ["Nos", "Metre", "Adet"]:
            if not frappe.db.exists("UOM", u_name):
                frappe.get_doc({"doctype": "UOM", "uom_name": u_name}).insert(
                    ignore_permissions=True
                )

        ig = (
            "Raw Material"
            if frappe.db.exists("Item Group", "Raw Material")
            else (frappe.db.get_value("Item Group", {}, "name"))
        )
        if not ig:
            frappe.get_doc(
                {
                    "doctype": "Item Group",
                    "item_group_name": "All Item Groups",
                    "is_group": 0,
                }
            ).insert(ignore_permissions=True)
            ig = "All Item Groups"

        # 3. KTA Customer Group
        if not frappe.db.get_value("KTA Customer Group", {}, "name"):
            frappe.get_doc(
                {
                    "doctype": "KTA Customer Group",
                    "kta_musteri_grubu": "TEST-CG",
                }
            ).insert(ignore_permissions=True)

        # 4. KTA Ara Malzeme Grubu
        for amg in ["HAMMADDE", "BAKIM", "ÜRÜN"]:
            if not frappe.db.exists("KTA Ara Malzeme Grubu", amg):
                frappe.get_doc(
                    {
                        "doctype": "KTA Ara Malzeme Grubu",
                        "kta_ara_malzeme_grubu": amg,
                    }
                ).insert(ignore_permissions=True)

        # 5. Test Kalemleri (Hammadde, Bakım ve Ürün)
        items_def = [
            ("_TEST_MRP_RAW", "HAMMADDE", "Test Raw Material", "Nos"),
            ("_TEST_MRP_CABLE", "HAMMADDE", "Test Cable", "Metre"),
            ("_TEST_MRP_MAINT", "BAKIM", "Test Maintenance Part", "Nos"),
            ("_TEST_MRP_FG", "ÜRÜN", "Test Finished Good", "Nos"),
        ]
        for code, grp, desc, itm_uom in items_def:
            if not frappe.db.exists("Item", code):
                frappe.get_doc(
                    {
                        "doctype": "Item",
                        "item_code": code,
                        "item_name": desc,
                        "item_group": ig,
                        "stock_uom": itm_uom,
                        "is_stock_item": 1,
                        "custom_ara_malzeme_grubu": grp,
                    }
                ).insert(ignore_permissions=True)
            else:
                frappe.db.set_value(
                    "Item",
                    code,
                    {
                        "custom_ara_malzeme_grubu": grp,
                        "stock_uom": itm_uom,
                        "disabled": 0,
                    },
                )
            if not frappe.db.exists(
                "UOM Conversion Detail", {"parent": code, "uom": itm_uom}
            ):
                frappe.get_doc(
                    {
                        "doctype": "UOM Conversion Detail",
                        "parent": code,
                        "parenttype": "Item",
                        "parentfield": "uoms",
                        "uom": itm_uom,
                        "conversion_factor": 1.0,
                    }
                ).insert(ignore_permissions=True)

        # 6. Tedarikçi
        cls.supplier_name = "_Test MRP Supplier"
        if not frappe.db.exists("Supplier", cls.supplier_name):
            sup_grp = frappe.db.get_value("Supplier Group", {}, "name")
            if not sup_grp:
                frappe.get_doc(
                    {
                        "doctype": "Supplier Group",
                        "supplier_group_name": "All Supplier Groups",
                    }
                ).insert(ignore_permissions=True)
                sup_grp = "All Supplier Groups"
            frappe.get_doc(
                {
                    "doctype": "Supplier",
                    "supplier_name": cls.supplier_name,
                    "supplier_group": sup_grp,
                }
            ).insert(ignore_permissions=True)

        # 7. Varsayılan Tedarikçi (Item Default)
        for rm_code in ["_TEST_MRP_RAW", "_TEST_MRP_CABLE"]:
            frappe.db.delete("Item Default", {"parent": rm_code})
            frappe.get_doc(
                {
                    "doctype": "Item Default",
                    "parent": rm_code,
                    "parenttype": "Item",
                    "parentfield": "item_defaults",
                    "company": company,
                    "default_supplier": cls.supplier_name,
                }
            ).insert(ignore_permissions=True)

        # 8. Fiyat Listesi ve Fiyat (Item Price)
        price_list = frappe.db.get_value("Price List", {"buying": 1}, "name")
        if not price_list:
            pl = frappe.get_doc(
                {
                    "doctype": "Price List",
                    "price_list_name": "Standard Buying",
                    "buying": 1,
                    "currency": "EUR",
                }
            ).insert(ignore_permissions=True)
            price_list = pl.name

        for rm_code, rate in [("_TEST_MRP_RAW", 25.50), ("_TEST_MRP_CABLE", 15.00)]:
            if not frappe.db.exists(
                "Item Price", {"item_code": rm_code, "supplier": cls.supplier_name}
            ):
                rm_uom = frappe.db.get_value("Item", rm_code, "stock_uom") or "Nos"
                frappe.get_doc(
                    {
                        "doctype": "Item Price",
                        "item_code": rm_code,
                        "uom": rm_uom,
                        "price_list": price_list,
                        "buying": 1,
                        "supplier": cls.supplier_name,
                        "price_list_rate": rate,
                        "currency": "EUR",
                    }
                ).insert(ignore_permissions=True)

        # 9. Stok (Bin) Kayıtları
        bins_def = [
            ("_TEST_MRP_RAW", 100.0, 20.0),
            ("_TEST_MRP_CABLE", 200.0, 50.0),
            ("_TEST_MRP_MAINT", 50.0, 0.0),
            ("_TEST_MRP_FG", 10.0, 0.0),
        ]
        for code, actual, reserved in bins_def:
            b_name = frappe.db.get_value(
                "Bin", {"item_code": code, "warehouse": cls.warehouse}
            )
            if not b_name:
                b = frappe.get_doc(
                    {
                        "doctype": "Bin",
                        "item_code": code,
                        "warehouse": cls.warehouse,
                    }
                ).insert(ignore_permissions=True)
                b_name = b.name
            frappe.db.set_value(
                "Bin",
                b_name,
                {
                    "actual_qty": actual,
                    "reserved_qty_for_production": reserved,
                    "stock_value": actual * 10,
                },
            )

        frappe.db.commit()

    def test_columns_structure_and_labels(self):
        """rezerve_stok ve serbest_stok kolonlarının varlığı, sıralaması ve Bakiye Değeri (TL) etiketi."""
        cols, *_ = mrp_analysis.execute({})
        fieldnames = [c["fieldname"] for c in cols]
        col_map = {c["fieldname"]: c for c in cols}

        self.assertIn("rezerve_stok", fieldnames, "rezerve_stok kolonu eksik")
        self.assertIn("serbest_stok", fieldnames, "serbest_stok kolonu eksik")
        self.assertIn("bakiye_degeri", fieldnames, "bakiye_degeri kolonu eksik")

        # Sıralama kontrolü: depo_stok -> rezerve_stok -> serbest_stok -> bakiye_degeri
        idx_depo = fieldnames.index("depo_stok")
        idx_rezerve = fieldnames.index("rezerve_stok")
        idx_serbest = fieldnames.index("serbest_stok")
        idx_bakiye = fieldnames.index("bakiye_degeri")

        self.assertEqual(
            idx_rezerve,
            idx_depo + 1,
            "rezerve_stok, depo_stok'un hemen ardından gelmeli",
        )
        self.assertEqual(
            idx_serbest,
            idx_rezerve + 1,
            "serbest_stok, rezerve_stok'un hemen ardından gelmeli",
        )
        self.assertEqual(
            idx_bakiye,
            idx_serbest + 1,
            "bakiye_degeri, serbest_stok'un hemen ardından gelmeli",
        )

        # Kolon etiketleri
        self.assertIn(col_map["rezerve_stok"]["label"], ["Rezerve Miktar", "Reserved Qty"])
        self.assertIn(col_map["serbest_stok"]["label"], ["Serbest Stok", "Free Stock"])
        self.assertIn(col_map["bakiye_degeri"]["label"], ["Bakiye Değeri (TL)", "Balance Value (TL)"])

    def test_birim_column_and_item_uom_mapping(self):
        """Birim (stock_uom) kolonunun varlığı ve satırlara doğru atanması."""
        cols, data, *_ = mrp_analysis.execute({"sifir_tuketimi_goster": 1})
        fieldnames = [c["fieldname"] for c in cols]
        col_map = {c["fieldname"]: c for c in cols}

        self.assertIn("birim", fieldnames, "'birim' kolonu kolon listesinde bulunamadı")
        self.assertIn(col_map["birim"]["label"], ["Birim", "Unit"])

        idx_adi = fieldnames.index("hammadde_adi")
        idx_birim = fieldnames.index("birim")
        self.assertEqual(
            idx_birim,
            idx_adi + 1,
            "birim kolonu hammadde_adi'nin hemen ardından gelmeli",
        )

        data_rows = [d for d in data if not d.get("is_total_row")]
        self.assertGreater(len(data_rows), 0, "Raporda en az bir veri satırı bulunmalı")
        for row in data_rows:
            self.assertTrue(
                row.get("birim"), f"{row.get('hammadde_kodu')} için birim boş olamaz"
            )

    def test_data_row_net_available_stock_calculation(self):
        """Her veri satırında serbest_stok == round(depo_stok - rezerve_stok, 2) olmalı."""
        _, data, *_ = mrp_analysis.execute({"sifir_tuketimi_goster": 1})
        data_rows = [d for d in data if not d.get("is_total_row")]

        self.assertGreater(len(data_rows), 0, "Raporda en az bir veri satırı bulunmalı")

        for row in data_rows:
            depo = row.get("depo_stok", 0) or 0
            rezerve = row.get("rezerve_stok", 0) or 0
            serbest = row.get("serbest_stok", 0) or 0
            self.assertAlmostEqual(
                serbest,
                round(depo - rezerve, 2),
                places=2,
                msg=f"Hammadde {row.get('hammadde_kodu')} için serbest stok hesabı hatalı: {serbest} != {depo} - {rezerve}",
            )

    def test_uom_grouped_subtotals_and_grand_value(self):
        """Alt toplam satırlarının birim bazında ayrıştığı ve en altta genel bakiye değeri satırı olduğunu doğrular."""
        _, data, *_ = mrp_analysis.execute({"sifir_tuketimi_goster": 1})
        total_rows = [d for d in data if d.get("is_total_row") == 1]

        # 1. En az bir adet TOPLAM (<Birim>) satırı olmalı
        uom_rows = [
            r
            for r in total_rows
            if str(r.get("hammadde_kodu", "")).startswith("TOPLAM (")
        ]
        self.assertGreaterEqual(
            len(uom_rows), 1, "En az bir adet TOPLAM (<Birim>) satırı bulunmalı"
        )

        # 2. Her birim satırında birim alanı ve serbest stok hesabı doğru olmalı
        for r in uom_rows:
            self.assertTrue(
                r.get("birim"), "Birim toplam satırında 'birim' alanı dolu olmalı"
            )
            depo = r.get("depo_stok", 0) or 0
            rezerve = r.get("rezerve_stok", 0) or 0
            serbest = r.get("serbest_stok", 0) or 0
            self.assertAlmostEqual(
                serbest,
                round(depo - rezerve, 2),
                places=2,
                msg=f"{r.get('hammadde_kodu')} için serbest stok hesabı tutarsız",
            )

        # 3. En altta tek bir GENEL BAKİYE DEĞERİ satırı olmalı
        grand_rows = [
            r for r in total_rows if r.get("hammadde_kodu") == "GENEL BAKİYE DEĞERİ"
        ]
        self.assertEqual(
            len(grand_rows), 1, "Yalnızca bir adet GENEL BAKİYE DEĞERİ satırı olmalı"
        )
        grand_val = grand_rows[0].get("bakiye_degeri")
        self.assertIsInstance(
            grand_val,
            (int, float),
            "GENEL BAKİYE DEĞERİ satırında bakiye_degeri sayısal olmalı",
        )
        self.assertGreater(grand_val, 0, "GENEL BAKİYE DEĞERİ pozitif bir sayı olmalı")

    def test_zero_consumption_items_excludes_finished_goods_and_maintenance(self):
        """get_zero_consumption_items yalnızca HAMMADDE ve OBS* gruplarını getirmeli; BAKIM/AMBALAJ/ÜRÜN getirmemeli."""
        self.assertTrue(
            hasattr(mrp_analysis, "get_zero_consumption_items"),
            "mrp_analysis modülünde get_zero_consumption_items fonksiyonu tanımlı olmalı",
        )
        items = mrp_analysis.get_zero_consumption_items()
        self.assertGreater(len(items), 0, "Sıfır tüketim kalem listesi boş dönmemeli")

        # Deterministik fikstür doğrulaması
        self.assertIn(
            "_TEST_MRP_RAW",
            items,
            "HAMMADDE grubundaki kalem sıfır tüketim listesinde olmalı",
        )
        self.assertNotIn(
            "_TEST_MRP_MAINT",
            items,
            "BAKIM grubundaki kalem sıfır tüketim listesine sızmamalı",
        )
        self.assertNotIn(
            "_TEST_MRP_FG",
            items,
            "ÜRÜN grubundaki mamul sıfır tüketim listesine sızmamalı",
        )

        sample_items = items[:100]
        item_records = frappe.db.get_all(
            "Item",
            filters={"name": ["in", sample_items]},
            fields=["name", "custom_ara_malzeme_grubu", "disabled"],
        )

        for rec in item_records:
            self.assertEqual(
                rec.disabled, 0, f"Pasif ürün listeye sızmamalı: {rec.name}"
            )
            grp = rec.custom_ara_malzeme_grubu or ""
            is_valid = grp == "HAMMADDE" or grp.startswith("OBS")
            self.assertTrue(
                is_valid,
                f"Geçersiz ara malzeme grubu listeye sızdı: {rec.name} -> {grp}",
            )

    def test_default_supplier_pricing_standardization(self):
        """Varsayılan tedarikçi üzerinden fiyat çekilmesi doğrulaması."""
        _, data, *_ = mrp_analysis.execute({"sifir_tuketimi_goster": 1})
        test_row = next(
            (d for d in data if d.get("hammadde_kodu") == "_TEST_MRP_RAW"), None
        )

        self.assertIsNotNone(test_row, "_TEST_MRP_RAW satırı raporda bulunamadı")
        self.assertEqual(test_row.get("varsayilan_tedarikci"), "_Test MRP Supplier")
        self.assertEqual(test_row.get("fiyat"), 25.50)
        self.assertTrue(bool(test_row.get("para_birimi")), "Para birimi tanımlı olmalı")

    def test_period_dates_rolling_year(self):
        """get_period_dates 'Yıllık' periyodu takvim yılı sonu yerine 12 aylık kayan periyot dönmeli."""
        from frappe.utils import add_months, getdate, today

        from erpnextkta.kta_mrp.report_utils import get_period_dates

        from_date, to_date = get_period_dates("Yıllık")
        expected_from = str(getdate(today()))
        expected_to = str(add_months(getdate(today()), 12))
        self.assertEqual(from_date, expected_from)
        self.assertEqual(to_date, expected_to)
