import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import OperationsNotCompleteError

from erpnextkta.tests.test_utils import (
	KTABaseTestCase,
	create_test_company,
	create_test_erpnext_operation,
	create_test_item,
	create_test_item_group,
	create_test_warehouse,
	create_test_workstation,
)


class TestStockEntryOverride(KTABaseTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("Manufacturing Settings", "make_serial_no_batch_from_work_order", 0)
		self.company = create_test_company()
		self.item_group = create_test_item_group()
		self.item = create_test_item(self.item_group)
		frappe.db.set_value("Item", self.item, {"has_batch_no": 0, "has_serial_no": 0})
		self.warehouse = create_test_warehouse(self.company)
		self.workstation = create_test_workstation("_Test SE Workstation")
		self.operation = create_test_erpnext_operation("_Test SE Operation", self.workstation)

	def _create_test_work_order(self, qty=10, completed_qty=0, bom_no=None):
		doc_dict = {
			"doctype": "Work Order",
			"production_item": self.item,
			"qty": qty,
			"company": self.company,
			"wip_warehouse": self.warehouse,
			"fg_warehouse": self.warehouse,
			"use_multi_level_bom": 0,
			"skip_transfer": 1,
			"transfer_material_against": "Work Order",
			"operations": [
				{
					"operation": self.operation,
					"workstation": self.workstation,
					"time_in_mins": 30,
					"completed_qty": completed_qty,
					"process_loss_qty": 0.0,
				}
			],
		}
		if bom_no:
			doc_dict["bom_no"] = bom_no
		wo = frappe.get_doc(doc_dict)
		wo.flags.ignore_mandatory = True
		wo.insert(ignore_permissions=True)
		wo.submit()
		return wo

	def test_material_consumption_skips_operations_check(self):
		"""Material Consumption for Manufacture should immediately skip op completion validation."""
		wo = self._create_test_work_order(qty=10, completed_qty=0)

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Consumption for Manufacture"
		se.work_order = wo.name
		se.fg_completed_qty = 10

		# Should return without raising OperationsNotCompleteError
		se.check_if_operations_completed()

	def test_manufacture_succeeds_when_op_completed_qty_satisfied_with_draft_job_card(
		self,
	):
		"""Manufacture stock entry check_if_operations_completed should succeed when operation

		completed_qty is satisfied, even when Job Cards are draft (docstatus=0).
		"""
		wo = self._create_test_work_order(qty=10, completed_qty=0)

		# Confirm that Job Cards for this work order are in draft (docstatus=0)
		job_cards = frappe.get_all("Job Card", filters={"work_order": wo.name}, fields=["name", "docstatus"])
		self.assertGreater(len(job_cards), 0)
		for jc in job_cards:
			self.assertEqual(jc.docstatus, 0)

		# Simulate operation completed_qty updated (e.g. by production confirmation)
		op_name = wo.operations[0].name
		frappe.db.set_value("Work Order Operation", op_name, "completed_qty", 10.0)

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.fg_completed_qty = 10.0

		# Validation must pass without error even though Job Cards are docstatus=0
		se.check_if_operations_completed()

	def test_manufacture_throws_informative_error_when_op_completed_qty_insufficient(
		self,
	):
		"""When operation completed_qty is insufficient, it should throw an informative error

		stating that the operation has not been sufficiently confirmed, without requiring Job Card submission.
		"""
		wo = self._create_test_work_order(qty=10, completed_qty=0)

		# Completed qty is only 4 out of 10
		op_name = wo.operations[0].name
		frappe.db.set_value("Work Order Operation", op_name, "completed_qty", 4.0)

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.fg_completed_qty = 10.0

		with self.assertRaises(OperationsNotCompleteError) as cm:
			se.check_if_operations_completed()

		self.assertIn("not been sufficiently confirmed yet", str(cm.exception))

	def test_manufacture_throws_informative_error_without_job_card(self):
		"""When Job Card is deleted or not found, it should NOT throw 'Job Card not found'

		error, but instead informative operation confirmation error.
		"""
		wo = self._create_test_work_order(qty=10, completed_qty=0)

		# Delete any generated Job Cards for this work order
		frappe.db.delete("Job Card", {"work_order": wo.name})

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.fg_completed_qty = 10.0

		with self.assertRaises(OperationsNotCompleteError) as cm:
			se.check_if_operations_completed()

		# Must not be "Job Card not found"
		self.assertNotIn("Job Card not found", str(cm.exception))
		self.assertIn("not been sufficiently confirmed yet", str(cm.exception))

	def test_validate_work_order_passes_when_completed_qty_satisfied(self):
		"""Standard validate_work_order lifecycle method succeeds without error

		when operation completed_qty is satisfied, even with draft Job Cards.
		"""
		wo = self._create_test_work_order(qty=10, completed_qty=0)

		op_name = wo.operations[0].name
		frappe.db.set_value("Work Order Operation", op_name, "completed_qty", 10.0)

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.fg_completed_qty = 10.0

		# validate_work_order calls check_if_operations_completed
		se.validate_work_order()

	def test_raw_materials_validation_skipped_when_custom_confirmation_set(self):
		"""When custom_confirmation is present on a Manufacture Stock Entry,

		validate_raw_materials_exists should not raise even if no raw materials are present.
		"""
		frappe.db.set_single_value("Manufacturing Settings", "material_consumption", 0)
		wo = self._create_test_work_order(qty=5, completed_qty=5)

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.bom_no = "BOM-TEST-CONFIRMATION-001"
		se.custom_confirmation = "TEST-CONF-001"
		se.append(
			"items",
			{
				"item_code": self.item,
				"qty": 5,
				"t_warehouse": self.warehouse,
				"is_finished_item": 1,
			},
		)

		# Should pass without ValidationError
		se.validate_raw_materials_exists()

	def test_raw_materials_validation_skipped_when_material_consumption_entry_exists(
		self,
	):
		"""When submitted Material Consumption for Manufacture entries exist for the Work Order,

		validate_raw_materials_exists should not raise even without raw materials in the FG entry.
		"""
		frappe.db.set_single_value("Manufacturing Settings", "material_consumption", 0)
		wo = self._create_test_work_order(qty=5, completed_qty=5)

		# Create a submitted Material Consumption entry for this work order
		consumption_se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"purpose": "Material Consumption for Manufacture",
				"work_order": wo.name,
				"company": self.company,
				"items": [
					{
						"item_code": self.item,
						"qty": 5,
						"s_warehouse": self.warehouse,
					}
				],
			}
		)
		consumption_se.flags.ignore_mandatory = True
		consumption_se.flags.ignore_validate = True
		consumption_se.insert(ignore_permissions=True)
		consumption_se.docstatus = 1
		consumption_se.db_update()

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.bom_no = "BOM-TEST-CONSUMED-001"
		se.append(
			"items",
			{
				"item_code": self.item,
				"qty": 5,
				"t_warehouse": self.warehouse,
				"is_finished_item": 1,
			},
		)

		# Should pass without ValidationError
		se.validate_raw_materials_exists()

	def test_raw_materials_validation_skipped_when_work_order_has_no_bom(self):
		"""When Work Order has no BOM (legacy/ad-hoc), validate_raw_materials_exists

		should not enforce raw materials on Manufacture stock entries.
		"""
		frappe.db.set_single_value("Manufacturing Settings", "material_consumption", 0)
		wo = self._create_test_work_order(qty=5, completed_qty=5, bom_no=None)
		frappe.db.set_value("Work Order", wo.name, "bom_no", None)

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.bom_no = None
		se.append(
			"items",
			{
				"item_code": self.item,
				"qty": 5,
				"t_warehouse": self.warehouse,
				"is_finished_item": 1,
			},
		)

		# Should pass without ValidationError
		se.validate_raw_materials_exists()

	def test_raw_materials_validation_enforced_for_normal_manufacture_without_consumption_or_confirmation(
		self,
	):
		"""For a normal Work Order with BOM, no confirmation and no prior consumption entries,

		validate_raw_materials_exists should delegate to super and raise ValidationError
		if no raw materials are present.
		"""
		frappe.db.set_single_value("Manufacturing Settings", "material_consumption", 0)
		wo = self._create_test_work_order(qty=5, completed_qty=5)
		frappe.db.set_value("Work Order", wo.name, "bom_no", "BOM-TEST-NORMAL-001")

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.bom_no = "BOM-TEST-NORMAL-001"
		se.custom_confirmation = None
		se.append(
			"items",
			{
				"item_code": self.item,
				"qty": 5,
				"t_warehouse": self.warehouse,
				"is_finished_item": 1,
			},
		)

		from frappe.exceptions import ValidationError

		with self.assertRaises(ValidationError) as cm:
			se.validate_raw_materials_exists()

		self.assertIn("raw material", str(cm.exception).lower())

	def test_raw_materials_validation_skipped_when_material_consumption_setting_enabled(
		self,
	):
		"""When Manufacturing Settings 'material_consumption' is enabled,

		validate_raw_materials_exists should immediately return without errors.
		"""
		frappe.db.set_single_value("Manufacturing Settings", "material_consumption", 1)
		wo = self._create_test_work_order(qty=5, completed_qty=5)
		frappe.db.set_value("Work Order", wo.name, "bom_no", "BOM-TEST-SETTING-001")

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.work_order = wo.name
		se.bom_no = "BOM-TEST-SETTING-001"
		se.append(
			"items",
			{
				"item_code": self.item,
				"qty": 5,
				"t_warehouse": self.warehouse,
				"is_finished_item": 1,
			},
		)

		# Should pass without ValidationError
		se.validate_raw_materials_exists()

	def test_raw_materials_validation_skipped_for_non_manufacturing_purposes(
		self,
	):
		"""Non-manufacturing purposes (e.g. Material Transfer) should immediately return."""
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Transfer"
		se.append(
			"items",
			{
				"item_code": self.item,
				"qty": 5,
				"t_warehouse": self.warehouse,
			},
		)

		# Should pass without ValidationError
		se.validate_raw_materials_exists()

	def test_get_matched_items_with_alternative_item(self):
		"""Test that get_matched_items correctly resolves alternative items
		via custom_original_item and approved Item Alternative records.
		"""
		item_a = create_test_item(self.item_group, "_Test Matched Item A")
		item_b = create_test_item(self.item_group, "_Test Matched Item B")
		frappe.db.set_value("Item", item_a, "allow_alternative_item", 1)
		frappe.db.set_value("Item", item_b, "allow_alternative_item", 1)

		# Case 1: Match via custom_original_item
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.append(
			"items",
			{
				"item_code": item_b,
				"qty": 5,
				"s_warehouse": self.warehouse,
				"custom_original_item": item_a,
			},
		)

		matched = se.get_matched_items(item_a)
		self.assertTrue(matched)
		self.assertEqual(matched[0].item_code, item_b)

		# Case 2: Match via Item Alternative (one-way: A -> B)
		frappe.db.delete("Item Alternative", {"item_code": ["in", [item_a, item_b]]})
		frappe.db.delete("Item Alternative", {"alternative_item_code": ["in", [item_a, item_b]]})

		alt = frappe.get_doc(
			{
				"doctype": "Item Alternative",
				"item_code": item_a,
				"alternative_item_code": item_b,
				"two_way": 0,
			}
		).insert(ignore_permissions=True)

		se2 = frappe.new_doc("Stock Entry")
		se2.purpose = "Manufacture"
		se2.append(
			"items",
			{
				"item_code": item_b,
				"qty": 5,
				"s_warehouse": self.warehouse,
			},
		)

		matched2 = se2.get_matched_items(item_a)
		self.assertTrue(matched2)
		self.assertEqual(matched2[0].item_code, item_b)

		# Case 3: Match via Item Alternative (two-way: B -> A, two_way=1)
		alt.delete(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Item Alternative",
				"item_code": item_b,
				"alternative_item_code": item_a,
				"two_way": 1,
			}
		).insert(ignore_permissions=True)

		matched3 = se2.get_matched_items(item_a)
		self.assertTrue(matched3)
		self.assertEqual(matched3[0].item_code, item_b)

		# Case 4: No match returns empty list
		item_c = create_test_item(self.item_group, "_Test Matched Item C")
		self.assertFalse(se2.get_matched_items(item_c))

	def test_validate_component_quantities_accepts_alternative_item(self):
		"""validate_component_and_quantities should accept an alternative item matching BOM qty."""
		frappe.db.set_single_value("Manufacturing Settings", "validate_components_quantities_per_bom", 1)
		item_a = create_test_item(self.item_group, "_Test BOM Req Item A")
		item_b = create_test_item(self.item_group, "_Test BOM Alt Item B")

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.fg_completed_qty = 1
		se.bom_no = "BOM-TEST-ALT-001"
		se.get_bom_raw_materials = lambda fg_qty, *args, **kwargs: {item_a: {"qty": 2.0}}

		se.append(
			"items",
			{
				"item_code": item_b,
				"qty": 2.0,
				"transfer_qty": 2.0,
				"s_warehouse": self.warehouse,
				"custom_original_item": item_a,
			},
		)

		# Should pass without throwing "Missing Item" or "Incorrect Component Quantity"
		se.validate_component_and_quantities()
