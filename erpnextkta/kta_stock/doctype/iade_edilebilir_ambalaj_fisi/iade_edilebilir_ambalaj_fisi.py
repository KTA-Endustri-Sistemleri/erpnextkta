# Copyright (c) 2026, KTA Endustri Sistemleri Ltd.Sti. and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

TYPE_IN = "Giriş"
TYPE_OUT = "Çıkış"
# Sayım ile hesaplanan adet arasındaki oransal fark bu eşiği aşarsa açıklama zorunludur
DIFFERENCE_TOLERANCE = 0.10


class IadeEdilebilirAmbalajFisi(Document):
	def validate(self):
		self.set_defaults()
		self.validate_qty()
		self.validate_purchase_receipt()
		self.set_calculated_qty()
		self.validate_count_difference()
		self.warn_duplicate_purchase_receipt()

	def on_submit(self):
		if self.type == TYPE_OUT:
			self.validate_balance_on_submit()

	def on_cancel(self):
		if self.type == TYPE_IN:
			self.validate_balance_on_cancel()

	def set_defaults(self):
		if not self.posting_date:
			self.posting_date = today()

	def validate_qty(self):
		if (self.qty or 0) <= 0:
			frappe.throw(_("Adet sıfırdan büyük olmalıdır."))

	def validate_purchase_receipt(self):
		if self.type != TYPE_IN:
			return
		if not self.purchase_receipt:
			frappe.throw(_("Giriş işlemlerinde Mal Alım İrsaliyesi seçilmesi zorunludur."))

		purchase_receipt = frappe.db.get_value(
			"Purchase Receipt", self.purchase_receipt, ["supplier", "docstatus"], as_dict=True
		)
		if not purchase_receipt or purchase_receipt.docstatus != 1:
			frappe.throw(_("Seçilen Mal Alım İrsaliyesi onaylanmış olmalıdır."))
		if not self.supplier:
			self.supplier = purchase_receipt.supplier
		elif self.supplier != purchase_receipt.supplier:
			frappe.throw(_("Tedarikçi, seçilen Mal Alım İrsaliyesindeki tedarikçi ile aynı olmalıdır."))

	def set_calculated_qty(self):
		if self.type == TYPE_IN and self.purchase_receipt:
			self.calculated_qty = calculate_packaging_qty(self.purchase_receipt)["total"]
		else:
			self.calculated_qty = 0

	def validate_count_difference(self):
		if not self.calculated_qty or (self.remarks or "").strip():
			return
		ratio = abs(self.qty - self.calculated_qty) / self.calculated_qty
		if ratio > DIFFERENCE_TOLERANCE:
			frappe.throw(
				_("Sayılan adet ({0}) ile hesaplanan adet ({1}) arasındaki fark çok büyük. Lütfen Açıklama alanını doldurun.").format(
					self.qty, self.calculated_qty
				)
			)

	def warn_duplicate_purchase_receipt(self):
		if self.type != TYPE_IN or not self.purchase_receipt:
			return
		duplicates = frappe.get_all(
			"Iade Edilebilir Ambalaj Fisi",
			filters={
				"purchase_receipt": self.purchase_receipt,
				"type": TYPE_IN,
				"docstatus": 1,
				"name": ["!=", self.name],
			},
			pluck="name",
		)
		if duplicates:
			frappe.msgprint(
				_("Bu Mal Alım İrsaliyesi için zaten onaylanmış giriş fişleri var: {0}").format(", ".join(duplicates)),
				title=_("Mükerrer Giriş Uyarısı"),
				indicator="orange",
			)

	def validate_balance_on_submit(self):
		balance = get_supplier_balance(self.supplier)
		if balance < 0:
			available = balance + self.qty
			frappe.throw(
				_("Tedarikçi {0} için yeterli ambalaj bakiyesi yok. Mevcut bakiye: {1}, düşülecek adet: {2}").format(
					self.supplier, available, self.qty
				)
			)

	def validate_balance_on_cancel(self):
		remaining_balance = get_supplier_balance(self.supplier)
		if remaining_balance < 0:
			frappe.throw(
				_(
					"Bu Giriş fişi iptal edilemez çünkü tedarikçiye yapılmış çıkışlar bulunmaktadır. Kalan bakiye: {0}"
				).format(remaining_balance)
			)

	def validate_balance(self, qty_to_deduct):
		balance = get_supplier_balance(self.supplier)
		if balance < 0:
			available = balance + qty_to_deduct
			frappe.throw(
				_("Tedarikçi {0} için yeterli ambalaj bakiyesi yok. Mevcut bakiye: {1}, düşülecek adet: {2}").format(
					self.supplier, available, qty_to_deduct
				)
			)


@frappe.whitelist()
def get_supplier_balance(supplier, exclude=None):
	"""Tedarikçi bazlı ambalaj bakiyesi: onaylı Giriş - onaylı Çıkış."""
	filters = {"supplier": supplier, "docstatus": 1}
	if exclude:
		filters["name"] = ["!=", exclude]
	rows = frappe.get_all(
		"Iade Edilebilir Ambalaj Fisi",
		filters=filters,
		fields=["type", "sum(qty) as total"],
		group_by="type",
	)
	totals = {d.type: flt(d.total) for d in rows}
	return int(totals.get(TYPE_IN, 0) - totals.get(TYPE_OUT, 0))


@frappe.whitelist()
def calculate_packaging_qty(purchase_receipt):
	"""İrsaliye kalemlerinden tahmini ambalaj sayısını hesaplar (ceil(qty / custom_split_qty))."""
	items = frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": purchase_receipt, "parenttype": "Purchase Receipt"},
		fields=["item_code", "qty", "custom_split_qty"],
		order_by="idx",
	)
	details = []
	for d in items:
		qty, split_qty = flt(d.qty), flt(d.custom_split_qty)
		if qty > 0 and split_qty > 0:
			details.append({"item_code": d.item_code, "qty": qty, "split_qty": split_qty, "count": math.ceil(qty / split_qty)})
	return {"total": sum(d["count"] for d in details), "details": details}
