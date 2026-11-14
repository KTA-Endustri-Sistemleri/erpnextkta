# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
import frappe
from erpnextkta.kta_mrp.report.mrp_analysis import mrp_analysis


class TestMrpAnalysisReservationsAndFilters(unittest.TestCase):
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
			company = frappe.get_doc({
				"doctype": "Company",
				"company_name": "_Test Company",
				"abbr": "_TC",
				"default_currency": "TRY",
				"country": "Turkey",
			}).insert(ignore_permissions=True, ignore_if_duplicate=True).name

		# 1. Warehouse Type & Depo (Kullanılabilir Stok)
		if not frappe.db.exists("Warehouse Type", "Kullanılabilir Stok"):
			frappe.get_doc({
				"doctype": "Warehouse Type",
				"name": "Kullanılabilir Stok",
			}).insert(ignore_permissions=True)

		wh_name = frappe.db.get_value(
			"Warehouse", {"warehouse_type": "Kullanılabilir Stok", "company": company}
		)
		if not wh_name:
			wh = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": "_Test Kullanilabilir Depo",
				"warehouse_type": "Kullanılabilir Stok",
				"company": company,
			}).insert(ignore_permissions=True)
			wh_name = wh.name
		cls.warehouse = wh_name

		# 2. UOM ve Item Group
		uom = frappe.db.get_value("UOM", {}, "name")
		if not uom:
			frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)
			uom = "Nos"

		ig = "Raw Material" if frappe.db.exists("Item Group", "Raw Material") else (
			frappe.db.get_value("Item Group", {}, "name")
		)
		if not ig:
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": "All Item Groups",
				"is_group": 0,
			}).insert(ignore_permissions=True)
			ig = "All Item Groups"

		# 3. KTA Customer Group
		if not frappe.db.get_value("KTA Customer Group", {}, "name"):
			frappe.get_doc({
				"doctype": "KTA Customer Group",
				"kta_musteri_grubu": "TEST-CG",
			}).insert(ignore_permissions=True)

		# 4. KTA Ara Malzeme Grubu
		for amg in ["HAMMADDE", "BAKIM", "ÜRÜN"]:
			if not frappe.db.exists("KTA Ara Malzeme Grubu", amg):
				frappe.get_doc({
					"doctype": "KTA Ara Malzeme Grubu",
					"kta_ara_malzeme_grubu": amg,
				}).insert(ignore_permissions=True)

		# 5. Test Kalemleri (Hammadde, Bakım ve Ürün)
		items_def = [
			("_TEST_MRP_RAW", "HAMMADDE", "Test Raw Material"),
			("_TEST_MRP_MAINT", "BAKIM", "Test Maintenance Part"),
			("_TEST_MRP_FG", "ÜRÜN", "Test Finished Good"),
		]
		for code, grp, desc in items_def:
			if not frappe.db.exists("Item", code):
				frappe.get_doc({
					"doctype": "Item",
					"item_code": code,
					"item_name": desc,
					"item_group": ig,
					"stock_uom": uom,
					"is_stock_item": 1,
					"custom_ara_malzeme_grubu": grp,
				}).insert(ignore_permissions=True)
			else:
				frappe.db.set_value(
					"Item", code, {"custom_ara_malzeme_grubu": grp, "disabled": 0}
				)

		# 5. Tedarikçi
		cls.supplier_name = "_Test MRP Supplier"
		if not frappe.db.exists("Supplier", cls.supplier_name):
			sup_grp = frappe.db.get_value("Supplier Group", {}, "name")
			if not sup_grp:
				frappe.get_doc({
					"doctype": "Supplier Group",
					"supplier_group_name": "All Supplier Groups",
				}).insert(ignore_permissions=True)
				sup_grp = "All Supplier Groups"
			frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": cls.supplier_name,
				"supplier_group": sup_grp,
			}).insert(ignore_permissions=True)

		# 6. Varsayılan Tedarikçi (Item Default)
		frappe.db.delete("Item Default", {"parent": "_TEST_MRP_RAW"})
		frappe.get_doc({
			"doctype": "Item Default",
			"parent": "_TEST_MRP_RAW",
			"parenttype": "Item",
			"parentfield": "item_defaults",
			"company": company,
			"default_supplier": cls.supplier_name,
		}).insert(ignore_permissions=True)

		# 7. Fiyat Listesi ve Fiyat (Item Price)
		price_list = frappe.db.get_value("Price List", {"buying": 1}, "name")
		if not price_list:
			pl = frappe.get_doc({
				"doctype": "Price List",
				"price_list_name": "Standard Buying",
				"buying": 1,
				"currency": "EUR",
			}).insert(ignore_permissions=True)
			price_list = pl.name

		if not frappe.db.exists("Item Price", {"item_code": "_TEST_MRP_RAW", "supplier": cls.supplier_name}):
			frappe.get_doc({
				"doctype": "Item Price",
				"item_code": "_TEST_MRP_RAW",
				"price_list": price_list,
				"buying": 1,
				"supplier": cls.supplier_name,
				"price_list_rate": 25.50,
				"currency": "EUR",
			}).insert(ignore_permissions=True)

		# 8. Stok (Bin) Kayıtları
		bins_def = [
			("_TEST_MRP_RAW", 100.0, 20.0),
			("_TEST_MRP_MAINT", 50.0, 0.0),
			("_TEST_MRP_FG", 10.0, 0.0),
		]
		for code, actual, reserved in bins_def:
			b_name = frappe.db.get_value("Bin", {"item_code": code, "warehouse": cls.warehouse})
			if not b_name:
				b = frappe.get_doc({
					"doctype": "Bin",
					"item_code": code,
					"warehouse": cls.warehouse,
				}).insert(ignore_permissions=True)
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

		self.assertEqual(idx_rezerve, idx_depo + 1, "rezerve_stok, depo_stok'un hemen ardından gelmeli")
		self.assertEqual(idx_serbest, idx_rezerve + 1, "serbest_stok, rezerve_stok'un hemen ardından gelmeli")
		self.assertEqual(idx_bakiye, idx_serbest + 1, "bakiye_degeri, serbest_stok'un hemen ardından gelmeli")

		# Kolon etiketleri
		self.assertEqual(col_map["rezerve_stok"]["label"], "Rezerve Miktar")
		self.assertEqual(col_map["serbest_stok"]["label"], "Serbest Stok")
		self.assertEqual(col_map["bakiye_degeri"]["label"], "Bakiye Değeri (TL)")

	def test_data_row_net_available_stock_calculation(self):
		"""Her veri satırında serbest_stok == round(depo_stok - rezerve_stok, 2) olmalı."""
		_, data, *_ = mrp_analysis.execute({"sifir_tuketimi_goster": 1})
		data_rows = [d for d in data if not d.get("is_total_row")]

		self.assertTrue(len(data_rows) > 0, "Raporda en az bir veri satırı bulunmalı")

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

	def test_total_row_contains_all_stock_totals(self):
		"""TOPLAM satırında depo_stok, rezerve_stok, serbest_stok ve bakiye_degeri sayısal olmalı, hammadde_kodu HTML içermemeli."""
		_, data, *_ = mrp_analysis.execute({"sifir_tuketimi_goster": 1})
		total_rows = [d for d in data if d.get("is_total_row") == 1]
		self.assertEqual(len(total_rows), 1, "Yalnızca bir adet TOPLAM satırı olmalı")

		total_row = total_rows[0]
		self.assertEqual(total_row.get("hammadde_kodu"), "TOPLAM", "hammadde_kodu alanında ham HTML tag'i (örn. <b>) olmamalı, düz TOPLAM olmalı")
		for field in ("depo_stok", "rezerve_stok", "serbest_stok", "bakiye_degeri"):
			self.assertIn(field, total_row, f"TOPLAM satırında {field} eksik")
			val = total_row[field]
			self.assertIsInstance(val, (int, float), f"TOPLAM satırında {field} sayısal olmalı, gelen: {val}")

		# Toplam satırındaki serbest stok formülü doğrulaması
		self.assertAlmostEqual(
			total_row["serbest_stok"],
			round(total_row["depo_stok"] - total_row["rezerve_stok"], 2),
			places=2,
			msg="TOPLAM satırında serbest stok toplamı tutarsız",
		)

	def test_zero_consumption_items_excludes_finished_goods_and_maintenance(self):
		"""get_zero_consumption_items yalnızca HAMMADDE ve OBS* gruplarını getirmeli; BAKIM/AMBALAJ/ÜRÜN getirmemeli."""
		self.assertTrue(
			hasattr(mrp_analysis, "get_zero_consumption_items"),
			"mrp_analysis modülünde get_zero_consumption_items fonksiyonu tanımlı olmalı",
		)
		items = mrp_analysis.get_zero_consumption_items()
		self.assertTrue(len(items) > 0, "Sıfır tüketim kalem listesi boş dönmemeli")

		# Deterministik fikstür doğrulaması
		self.assertIn("_TEST_MRP_RAW", items, "HAMMADDE grubundaki kalem sıfır tüketim listesinde olmalı")
		self.assertNotIn("_TEST_MRP_MAINT", items, "BAKIM grubundaki kalem sıfır tüketim listesine sızmamalı")
		self.assertNotIn("_TEST_MRP_FG", items, "ÜRÜN grubundaki mamul sıfır tüketim listesine sızmamalı")

		sample_items = items[:100]
		item_records = frappe.db.get_all(
			"Item",
			filters={"name": ["in", sample_items]},
			fields=["name", "custom_ara_malzeme_grubu", "disabled"],
		)

		for rec in item_records:
			self.assertEqual(rec.disabled, 0, f"Pasif ürün listeye sızmamalı: {rec.name}")
			grp = rec.custom_ara_malzeme_grubu or ""
			is_valid = grp == "HAMMADDE" or grp.startswith("OBS")
			self.assertTrue(
				is_valid,
				f"Geçersiz ara malzeme grubu listeye sızdı: {rec.name} -> {grp}",
			)

	def test_default_supplier_pricing_standardization(self):
		"""Varsayılan tedarikçi üzerinden fiyat çekilmesi doğrulaması."""
		_, data, *_ = mrp_analysis.execute({"sifir_tuketimi_goster": 1})
		test_row = next((d for d in data if d.get("hammadde_kodu") == "_TEST_MRP_RAW"), None)

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
