import frappe
from erpnext.manufacturing.doctype.job_card.job_card import JobCard
from frappe.utils import flt


class KTAJobCard(JobCard):
	def get_overlap_for(self, args, open_job_cards=None):
		if frappe.db.get_single_value("Manufacturing Settings", "disable_capacity_planning"):
			return {}
		return super().get_overlap_for(args, open_job_cards)

	def validate_sequence_id(self):
		if not self.flags.get("kta_sync_mode"):
			super().validate_sequence_id()

	def set_status(self, update_status=False):
		super().set_status(update_status)

		# Eger KTA skip_transfer yuzunden yanlislikla Material Transferred/Partially Transferred olduysa ve
		# aslinda gercek bir Material Transfer fisi yoksa, durumunu Open'a cevir.
		if self.status in (
			"Material Transferred",
			"Partially Transferred",
		) and self.get("work_order"):
			wo = frappe.get_cached_doc("Work Order", self.work_order)
			if wo and wo.skip_transfer:
				has_real_transfer = frappe.db.exists(
					"Stock Entry",
					{
						"job_card": self.name,
						"purpose": "Material Transfer for Manufacture",
						"docstatus": 1,
					},
				)
				if not has_real_transfer:
					self.status = "Open"

	def before_validate(self):
		if hasattr(super(), "before_validate"):
			super().before_validate()

		if not self.get("items"):
			self.get_required_items()

		# Ensure existing items also have transferred_qty = required_qty to fix UI
		if self.get("work_order"):
			wo = frappe.get_cached_doc("Work Order", self.work_order)
			if wo and wo.skip_transfer:
				for row in self.get("items", []):
					row.transferred_qty = row.required_qty

	@frappe.whitelist()
	def get_required_items(self):
		"""Load operation-specific raw materials even when skip_transfer is enabled."""
		if not self.get("work_order"):
			return

		doc = frappe.get_doc("Work Order", self.get("work_order"))

		# Standard behaviour for non-skip-transfer cases
		if not doc.skip_transfer:
			super().get_required_items()
			return

		# ── KTA: skip_transfer=True ise de operasyona ait malzemeleri yukle ──
		for d in doc.required_items:
			if not d.operation:
				continue

			if self.get("operation") == d.operation:
				self.append(
					"items",
					{
						"item_code": d.item_code,
						"source_warehouse": d.source_warehouse,
						"uom": frappe.db.get_value("Item", d.item_code, "stock_uom"),
						"item_name": d.item_name,
						"description": d.description,
						"required_qty": (d.required_qty * flt(self.for_quantity)) / doc.qty,
						"transferred_qty": (d.required_qty * flt(self.for_quantity)) / doc.qty,
						"rate": d.rate,
						"amount": d.amount,
					},
				)
		return

	def validate_transfer_qty(self):
		"""Skip transfer validation for skip_transfer Work Orders."""
		if not self.work_order:
			super().validate_transfer_qty()
			return

		wo_skip = frappe.get_cached_value("Work Order", self.work_order, "skip_transfer")
		if not wo_skip:
			super().validate_transfer_qty()
