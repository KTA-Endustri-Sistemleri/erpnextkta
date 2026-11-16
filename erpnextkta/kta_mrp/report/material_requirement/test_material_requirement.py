# Copyright (c) 2026, KTA Endüstri Sistemleri and Contributors
# See license.txt

import unittest
from unittest.mock import patch

from frappe import _

from erpnextkta.kta_mrp.mrp_engine.netting import net_material
from erpnextkta.kta_mrp.mrp_engine.service import MaterialRequirement, MaterialRequirementResult, Pegging
from erpnextkta.kta_mrp.report.material_requirement import material_requirement as mr

WEEKS = ["2026_w45", "2026_w46"]


def material(item_code, gross, free_stock, supplier="SUP-A", price=0, currency=None, receipts=None):
	return MaterialRequirement(
		item_code=item_code,
		item_name=f"{item_code} name",
		uom="Nos",
		supplier=supplier,
		actual=max(free_stock, 0),
		reserved=max(-free_stock, 0),
		netting=net_material(WEEKS, dict(zip(WEEKS, gross, strict=False)), receipts=receipts, free_stock=free_stock),
		price=price,
		currency=currency,
	)


def make_result():
	return MaterialRequirementResult(
		weeks=WEEKS,
		materials={
			"RM-OK": material("RM-OK", [5, 5], 100, price=1, currency="EUR"),
			"RM-SHORT": material("RM-SHORT", [0, 30], 10, supplier="SUP-B", price=2, currency="USD"),
			"RM-NOW": material("RM-NOW", [20, 0], 0),
		},
		pegging=[
			Pegging("RM-SHORT", "FG-1", "BOM-1", "FG 1", "CG-A", {"2026_w46": 20}),
			Pegging("RM-SHORT", "FG-2", "BOM-2", "FG 2", "CG-B", {"2026_w46": 10}),
		],
	)


def run(**filters):
	with patch.object(mr, "get_material_requirements", return_value=make_result()):
		return mr.execute(filters)


def fieldnames(columns):
	return [c["fieldname"] for c in columns]


class TestColumns(unittest.TestCase):
	def test_columns_do_not_change_with_weekly_view_or_po_option(self):
		expected = fieldnames(run()[0])
		for view in mr.WEEKLY_VIEWS:
			for include_po in (0, 1):
				self.assertEqual(fieldnames(run(weekly_view=view, include_po=include_po)[0]), expected)

	def test_stock_columns_exist_in_both_groupings(self):
		for group_by in ("Bitmiş Ürün + Hammadde", mr.GROUP_ONLY_MATERIAL):
			columns = fieldnames(run(group_by=group_by)[0])
			for fieldname in ("stok", "rezerve_stok", "serbest_stok", "po_teslimat", "net_ihtiyac", "onerilen_siparis"):
				self.assertIn(fieldname, columns)

	def test_week_columns_use_key_as_fieldname_and_iso_label(self):
		week_column = run()[0][-1]
		self.assertEqual((week_column["fieldname"], week_column["label"]), ("2026_w46", "2026-W46"))


class TestRows(unittest.TestCase):
	def test_tree_mode_puts_finished_items_under_material(self):
		data = run(weekly_view="Önerilen Sipariş")[1]
		short_index = next(i for i, row in enumerate(data) if row["hammadde"] == "RM-SHORT")
		children = data[short_index + 1 : short_index + 3]
		self.assertEqual(data[short_index]["indent"], 0)
		self.assertEqual([c["hammadde"] for c in children], ["FG-1", "FG-2"])
		self.assertEqual([c["indent"] for c in children], [1, 1])
		self.assertEqual(children[0]["2026_w46"], 20)  # alt satır her zaman brüt
		self.assertNotIn("stok", children[0])

	def test_flat_mode_has_no_tree_rows(self):
		data = run(group_by=mr.GROUP_ONLY_MATERIAL)[1]
		self.assertEqual(len(data), 3)
		self.assertTrue(all("indent" not in row for row in data))

	def test_weekly_view_selects_measure(self):
		rows = {r["hammadde"]: r for r in run(group_by=mr.GROUP_ONLY_MATERIAL, weekly_view="Projeksiyon Bakiye")[1]}
		self.assertEqual(rows["RM-SHORT"]["2026_w46"], -20)
		rows = {r["hammadde"]: r for r in run(group_by=mr.GROUP_ONLY_MATERIAL, weekly_view="Brüt İhtiyaç")[1]}
		self.assertEqual(rows["RM-SHORT"]["2026_w46"], 30)

	def test_most_urgent_shortage_first_and_no_total_row(self):
		data = run(group_by=mr.GROUP_ONLY_MATERIAL)[1]
		self.assertEqual([r["hammadde"] for r in data], ["RM-NOW", "RM-SHORT", "RM-OK"])
		self.assertFalse(any("<b>" in str(r.get("hammadde")) for r in data))

	def test_gross_and_net_totals_are_separate(self):
		row = next(r for r in run(group_by=mr.GROUP_ONLY_MATERIAL)[1] if r["hammadde"] == "RM-SHORT")
		self.assertEqual((row["brut_ihtiyac"], row["net_ihtiyac"]), (30, 20))
		self.assertEqual((row["ilk_eksik_hafta"], row["kapsama_hafta"]), ("2026-W46", 1))

	def test_filters(self):
		self.assertEqual(len(run(group_by=mr.GROUP_ONLY_MATERIAL, only_shortages=1)[1]), 2)
		self.assertEqual([r["hammadde"] for r in run(group_by=mr.GROUP_ONLY_MATERIAL, supplier="SUP-B")[1]], ["RM-SHORT"])
		self.assertEqual([r["hammadde"] for r in run(group_by=mr.GROUP_ONLY_MATERIAL, hammadde="RM-OK")[1]], ["RM-OK"])

	def test_tree_mode_includes_po_receipt_row_when_material_has_po(self):
		res = make_result()
		res.materials["RM-SHORT"] = material(
			"RM-SHORT", [0, 30], 10, supplier="SUP-B", price=2, currency="USD", receipts={"2026_w46": 15}
		)
		with patch.object(mr, "get_material_requirements", return_value=res):
			data = mr.execute({"weekly_view": "Önerilen Sipariş"})[1]
			short_index = next(i for i, row in enumerate(data) if row["hammadde"] == "RM-SHORT")
			po_row = data[short_index + 1]
			self.assertEqual(po_row["hammadde"], _("Açık PO Girişleri"))
			self.assertEqual(po_row["indent"], 1)
			self.assertEqual(po_row["is_po_row"], 1)
			self.assertEqual(po_row["2026_w46"], 15)

	def test_weekly_view_po_deliveries(self):
		res = make_result()
		res.materials["RM-SHORT"] = material(
			"RM-SHORT", [0, 30], 10, supplier="SUP-B", price=2, currency="USD", receipts={"2026_w46": 15}
		)
		with patch.object(mr, "get_material_requirements", return_value=res):
			data = mr.execute({"group_by": mr.GROUP_ONLY_MATERIAL, "weekly_view": "PO Teslimatları"})[1]
			row = next(r for r in data if r["hammadde"] == "RM-SHORT")
			self.assertEqual(row["2026_w46"], 15)


class TestSummary(unittest.TestCase):
	def test_amount_cards_are_per_currency(self):
		cards = mr.get_summary_cards(list(make_result().materials.values()))
		labels = {c["label"]: c["value"] for c in cards}
		self.assertEqual(labels[_("Toplam Kalem")], 3)
		self.assertEqual(labels[_("Eksik Kalem")], 2)
		self.assertIn(_("Önerilen Sipariş Tutarı ({0})").format("USD"), labels)
		self.assertNotIn(_("Önerilen Sipariş Tutarı ({0})").format("EUR"), labels)  # RM-OK için sipariş yok
		self.assertEqual(labels[_("Fiyatı Olmayan Kalem")], 1)

	def test_no_summary_or_chart_rendered(self):
		res = run()
		self.assertIsNone(res[2])
		self.assertIsNone(res[3])

	def test_summary_card_warns_when_include_po_is_disabled(self):
		cards = mr.get_summary_cards(list(make_result().materials.values()), include_po=False)
		self.assertEqual(cards[0]["value"], _("Kapalı"))
		self.assertEqual(cards[0]["label"], _("Açık PO Teslimatları (Ham İhtiyaç Modu)"))
		self.assertEqual(cards[0]["indicator"], "Orange")
