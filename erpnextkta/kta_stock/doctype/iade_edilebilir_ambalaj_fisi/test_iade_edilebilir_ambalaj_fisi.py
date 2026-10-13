# Copyright (c) 2026, Framras AS and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_stock.doctype.iade_edilebilir_ambalaj_fisi.iade_edilebilir_ambalaj_fisi import (
	get_supplier_balance,
)
from erpnextkta.kta_stock.report.ambalaj_bakiye_raporu.ambalaj_bakiye_raporu import execute

TEST_SUPPLIER = "_Test Ambalaj Supplier"


def make_fisi(type, qty, submit=True, **kwargs):
	fisi = frappe.get_doc(
		{"doctype": "Iade Edilebilir Ambalaj Fisi", "supplier": TEST_SUPPLIER, "type": type, "qty": qty, **kwargs}
	)
	fisi.insert()
	if submit:
		fisi.submit()
	return fisi


def insert_giris_without_receipt(qty):
	"""Testlerde Purchase Receipt oluşturmadan bakiye kurmak için doğrulamayı atlar."""
	fisi = frappe.get_doc(
		{"doctype": "Iade Edilebilir Ambalaj Fisi", "supplier": TEST_SUPPLIER, "type": "Giriş", "qty": qty}
	)
	fisi.flags.ignore_validate = True
	fisi.insert()
	fisi.db_set("docstatus", 1)
	return fisi


class TestIadeEdilebilirAmbalajFisi(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Supplier", TEST_SUPPLIER):
			group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
			frappe.get_doc(
				{"doctype": "Supplier", "supplier_name": TEST_SUPPLIER, "supplier_group": group}
			).insert(ignore_permissions=True)

	def setUp(self):
		frappe.db.delete("Iade Edilebilir Ambalaj Fisi", {"supplier": TEST_SUPPLIER})

	def test_qty_must_be_positive(self):
		with self.assertRaises(frappe.ValidationError):
			make_fisi("Çıkış", 0, submit=False)

	def test_giris_requires_purchase_receipt(self):
		with self.assertRaises(frappe.ValidationError):
			make_fisi("Giriş", 5, submit=False)

	def test_cikis_blocked_without_balance(self):
		with self.assertRaises(frappe.ValidationError):
			make_fisi("Çıkış", 1)

	def test_balance_calculation_and_cikis(self):
		insert_giris_without_receipt(10)
		make_fisi("Çıkış", 4)
		self.assertEqual(get_supplier_balance(TEST_SUPPLIER), 6)
		with self.assertRaises(frappe.ValidationError):
			make_fisi("Çıkış", 7)

	def test_cancel_giris_blocked_if_balance_goes_negative(self):
		giris = insert_giris_without_receipt(5)
		make_fisi("Çıkış", 5)
		giris.reload()
		with self.assertRaises(frappe.ValidationError):
			giris.cancel()

	def test_report_balance(self):
		insert_giris_without_receipt(8)
		make_fisi("Çıkış", 3)
		_, data = execute({"supplier": TEST_SUPPLIER})
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["balance"], 5)
