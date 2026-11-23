import frappe
from erpnext.manufacturing.doctype.work_order.work_order import (
    make_stock_entry as make_stock_entry_from_wo,
)
from erpnext.stock.doctype.stock_entry.stock_entry import OperationsNotCompleteError
from frappe.utils import flt

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
        frappe.db.set_single_value(
            "Manufacturing Settings", "make_serial_no_batch_from_work_order", 0
        )
        self.company = create_test_company()
        self.item_group = create_test_item_group()
        self.item = create_test_item(self.item_group)
        frappe.db.set_value("Item", self.item, {"has_batch_no": 0, "has_serial_no": 0})
        self.warehouse = create_test_warehouse(self.company)
        self.workstation = create_test_workstation("_Test SE Workstation")
        self.operation = create_test_erpnext_operation(
            "_Test SE Operation", self.workstation
        )

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
        job_cards = frappe.get_all(
            "Job Card", filters={"work_order": wo.name}, fields=["name", "docstatus"]
        )
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
        frappe.db.delete(
            "Item Alternative", {"alternative_item_code": ["in", [item_a, item_b]]}
        )

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
        frappe.db.set_single_value(
            "Manufacturing Settings", "validate_components_quantities_per_bom", 1
        )
        item_a = create_test_item(self.item_group, "_Test BOM Req Item A")
        item_b = create_test_item(self.item_group, "_Test BOM Alt Item B")

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Manufacture"
        se.fg_completed_qty = 1
        se.bom_no = "BOM-TEST-ALT-001"
        se.get_bom_raw_materials = lambda fg_qty, *args, **kwargs: {
            item_a: {"qty": 2.0}
        }

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


class TestStockEntryConsumptionCosting(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        orig_material_consumption = frappe.db.get_single_value(
            "Manufacturing Settings", "material_consumption"
        )
        orig_get_rm_cost = frappe.db.get_single_value(
            "Manufacturing Settings", "get_rm_cost_from_consumption_entry"
        )
        self.addCleanup(
            frappe.db.set_single_value,
            "Manufacturing Settings",
            {
                "material_consumption": orig_material_consumption,
                "get_rm_cost_from_consumption_entry": orig_get_rm_cost,
            },
        )
        frappe.db.set_single_value(
            "Manufacturing Settings",
            {
                "material_consumption": 1,
                "get_rm_cost_from_consumption_entry": 1,
            },
        )

        self.company = create_test_company()
        self.item_group = create_test_item_group()
        self.src_warehouse = create_test_warehouse(self.company, "_Test CC Source")
        self.wip_warehouse = create_test_warehouse(self.company, "_Test CC WIP")
        self.fg_warehouse = create_test_warehouse(self.company, "_Test CC FG")
        self.workstation = create_test_workstation("_Test CC Workstation")
        frappe.db.set_value("Workstation", self.workstation, "hour_rate", 0.0)
        self.op_10 = create_test_erpnext_operation("_Test CC Op 10", self.workstation)
        self.op_20 = create_test_erpnext_operation("_Test CC Op 20", self.workstation)
        self._tag = frappe.generate_hash(length=6)

    def _make_stock_item(
        self, label, valuation_method="Moving Average", allow_alternative_item=0
    ):
        code = f"_Test CC {label} {self._tag}"
        doc = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": code,
                "item_name": code,
                "item_group": self.item_group,
                "is_stock_item": 1,
                "stock_uom": "Nos",
                "has_batch_no": 0,
                "has_serial_no": 0,
                "valuation_method": valuation_method,
                "allow_alternative_item": allow_alternative_item,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _receive_stock(self, item_code, qty, rate, warehouse=None):
        wh = warehouse or self.src_warehouse
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = "Material Receipt"
        se.company = self.company
        se.to_warehouse = wh
        se.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": wh,
                "basic_rate": rate,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_bom(self, fg_item, raw_items_spec, operations):
        currency = (
            frappe.db.get_value("Company", self.company, "default_currency") or "TRY"
        )
        bom = frappe.new_doc("BOM")
        bom.item = fg_item
        bom.quantity = 1.0
        bom.company = self.company
        bom.currency = currency
        bom.conversion_rate = 1.0
        bom.rm_cost_as_per = "Valuation Rate"
        bom.with_operations = 1
        bom.inspection_required = 0
        for op in operations:
            bom.append(
                "operations",
                {
                    "operation": op,
                    "workstation": self.workstation,
                    "time_in_mins": 10,
                    "hour_rate": 0.0,
                },
            )
        for spec in raw_items_spec:
            bom.append(
                "items",
                {
                    "item_code": spec["item_code"],
                    "qty": spec["qty"],
                    "uom": "Nos",
                    "stock_uom": "Nos",
                    "rate": spec["rate"],
                    "operation": spec.get("operation"),
                    "source_warehouse": self.src_warehouse,
                    "allow_alternative_item": spec.get("allow_alternative_item", 0),
                },
            )
        bom.insert(ignore_permissions=True)
        bom.submit()
        return bom

    def _create_work_order(self, fg_item, bom_no, qty=1000.0, allow_alternative_item=0):
        wo = frappe.new_doc("Work Order")
        wo.production_item = fg_item
        wo.bom_no = bom_no
        wo.qty = qty
        wo.company = self.company
        wo.source_warehouse = self.src_warehouse
        wo.wip_warehouse = self.wip_warehouse
        wo.fg_warehouse = self.fg_warehouse
        wo.use_multi_level_bom = 0
        wo.skip_transfer = 1
        wo.allow_alternative_item = allow_alternative_item
        wo.set_work_order_operations()
        wo.set_required_items()
        for row in wo.required_items:
            row.source_warehouse = self.src_warehouse
        wo.insert(ignore_permissions=True)
        wo.submit()
        return wo

    def _set_wo_operations_completed_qty(self, wo, qty_by_op):
        for op_row in wo.operations:
            if op_row.operation in qty_by_op:
                frappe.db.set_value(
                    "Work Order Operation",
                    op_row.name,
                    "completed_qty",
                    qty_by_op[op_row.operation],
                )

    def _submit_consumption_entry(self, wo, fg_completed_qty, rows):
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Consumption for Manufacture"
        se.stock_entry_type = "Material Consumption for Manufacture"
        se.work_order = wo.name
        se.company = self.company
        se.from_bom = 1
        se.bom_no = wo.bom_no
        se.use_multi_level_bom = wo.use_multi_level_bom
        se.fg_completed_qty = fg_completed_qty
        se.from_warehouse = self.src_warehouse
        for row in rows:
            se.append(
                "items",
                {
                    "item_code": row["item_code"],
                    "qty": row["qty"],
                    "uom": "Nos",
                    "stock_uom": "Nos",
                    "conversion_factor": 1.0,
                    "s_warehouse": row.get("s_warehouse") or self.src_warehouse,
                    "t_warehouse": "",
                    "original_item": row.get("original_item"),
                    "custom_original_item": row.get("custom_original_item"),
                },
            )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_manufacture_entry(self, wo, qty, is_final=False, submit=True):
        se_dict = make_stock_entry_from_wo(wo.name, "Manufacture", qty)
        se = frappe.get_doc(se_dict)
        if is_final:
            se.flags.kta_is_final_confirmation = True
        if submit:
            se.insert(ignore_permissions=True)
            se.submit()
        return se

    def test_multiple_partial_manufacture_entries_with_consumption_costing(self):
        """1000-unit WO split into 300 + 300 + 400 partial Manufacture entries uses actual
        consumption rates without inflating subsequent batches and balances total consumed cost."""
        fg_item = self._make_stock_item("FG-MULTI")
        rm1 = self._make_stock_item("RM1-MULTI")
        rm2 = self._make_stock_item("RM2-MULTI")

        # Receive initial stock before BOM so BOM captures rate 10.0 / 5.0 (BOM FG cost = 20.0)
        self._receive_stock(rm1, 500.0, 10.0)
        self._receive_stock(rm2, 2000.0, 5.0)

        bom = self._create_bom(
            fg_item,
            [
                {"item_code": rm1, "qty": 1.0, "rate": 10.0, "operation": self.op_10},
                {"item_code": rm2, "qty": 2.0, "rate": 5.0, "operation": self.op_20},
            ],
            [self.op_10, self.op_20],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        # Receive second tranche at 18.0 after BOM so Moving Average RM1 becomes 14.0 (!= BOM 10.0)
        self._receive_stock(rm1, 500.0, 18.0)

        # Expected actual FG unit cost = 1 * 14.0 + 2 * 5.0 = 24.0
        consumption_entries = []
        manufacture_entries = []
        cumulative = 0.0

        for batch_qty in (300.0, 300.0, 400.0):
            cumulative += batch_qty
            self._set_wo_operations_completed_qty(
                wo, {self.op_10: cumulative, self.op_20: cumulative}
            )
            cons = self._submit_consumption_entry(
                wo,
                batch_qty,
                [
                    {"item_code": rm1, "qty": batch_qty},
                    {"item_code": rm2, "qty": batch_qty * 2.0},
                ],
            )
            consumption_entries.append(cons)

            mfg = self._create_manufacture_entry(wo, batch_qty, submit=True)
            manufacture_entries.append(mfg)

            fg_rows = [d for d in mfg.items if d.is_finished_item]
            rm_rows = [
                d for d in mfg.items if not d.is_finished_item and not d.is_scrap_item
            ]
            self.assertEqual(len(fg_rows), 1)
            self.assertEqual(rm_rows, [])
            self.assertAlmostEqual(flt(fg_rows[0].basic_rate), 24.0, places=2)
            self.assertAlmostEqual(
                flt(fg_rows[0].basic_amount), batch_qty * 24.0, places=2
            )

        total_mfg_amount = sum(
            flt(d.basic_amount)
            for mfg in manufacture_entries
            for d in mfg.items
            if d.is_finished_item
        )
        total_cons_amount = sum(
            flt(cons.total_outgoing_value) for cons in consumption_entries
        )
        self.assertAlmostEqual(total_mfg_amount, total_cons_amount, places=2)
        self.assertAlmostEqual(total_mfg_amount, 24000.0, places=2)

    def test_legacy_manufacture_then_consumption_and_fg_only_manufacture(self):
        """Legacy RM-bearing Manufacture entry (300) followed by Consumption + FG-only
        Manufacture (300 and 400) does not raise 'Only one Manufacture entry' and keeps
        legacy cost isolated from the consumption pool."""
        fg_item = self._make_stock_item("FG-LEGACY")
        rm1 = self._make_stock_item("RM1-LEGACY")
        rm2 = self._make_stock_item("RM2-LEGACY")

        self._receive_stock(rm1, 1000.0, 11.0)
        self._receive_stock(rm2, 2000.0, 4.5)

        bom = self._create_bom(
            fg_item,
            [
                {"item_code": rm1, "qty": 1.0, "rate": 7.0, "operation": self.op_10},
                {"item_code": rm2, "qty": 2.0, "rate": 2.0, "operation": self.op_20},
            ],
            [self.op_10, self.op_20],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        # 1. Legacy Manufacture (300 units) with raw materials directly in the entry
        self._set_wo_operations_completed_qty(
            wo, {self.op_10: 300.0, self.op_20: 300.0}
        )
        legacy_mfg = frappe.new_doc("Stock Entry")
        legacy_mfg.purpose = "Manufacture"
        legacy_mfg.stock_entry_type = "Manufacture"
        legacy_mfg.work_order = wo.name
        legacy_mfg.company = self.company
        legacy_mfg.from_bom = 1
        legacy_mfg.bom_no = bom.name
        legacy_mfg.fg_completed_qty = 300.0
        legacy_mfg.from_warehouse = self.src_warehouse
        legacy_mfg.to_warehouse = self.fg_warehouse
        legacy_mfg.append(
            "items",
            {
                "item_code": rm1,
                "qty": 300.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.src_warehouse,
            },
        )
        legacy_mfg.append(
            "items",
            {
                "item_code": rm2,
                "qty": 600.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.src_warehouse,
            },
        )
        legacy_mfg.append(
            "items",
            {
                "item_code": fg_item,
                "qty": 300.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.fg_warehouse,
                "is_finished_item": 1,
            },
        )
        legacy_mfg.insert(ignore_permissions=True)
        legacy_mfg.submit()
        self.assertGreater(flt(legacy_mfg.total_outgoing_value), 0.0)

        # 2. Consumption + FG-only Manufacture for 300 units and 400 units
        consumption_entries = []
        fg_only_entries = []
        cumulative = 300.0

        for batch_qty in (300.0, 400.0):
            cumulative += batch_qty
            self._set_wo_operations_completed_qty(
                wo, {self.op_10: cumulative, self.op_20: cumulative}
            )
            cons = self._submit_consumption_entry(
                wo,
                batch_qty,
                [
                    {"item_code": rm1, "qty": batch_qty},
                    {"item_code": rm2, "qty": batch_qty * 2.0},
                ],
            )
            consumption_entries.append(cons)

            mfg = self._create_manufacture_entry(wo, batch_qty, submit=True)
            fg_only_entries.append(mfg)

            fg_row = next(d for d in mfg.items if d.is_finished_item)
            # Unit cost = 1 * 11.0 + 2 * 4.5 = 20.0
            self.assertAlmostEqual(flt(fg_row.basic_rate), 20.0, places=2)
            self.assertAlmostEqual(flt(fg_row.basic_amount), batch_qty * 20.0, places=2)

        total_fg_only_amount = sum(
            flt(d.basic_amount)
            for mfg in fg_only_entries
            for d in mfg.items
            if d.is_finished_item
        )
        total_cons_amount = sum(
            flt(cons.total_outgoing_value) for cons in consumption_entries
        )
        self.assertAlmostEqual(total_fg_only_amount, total_cons_amount, places=2)
        self.assertAlmostEqual(total_fg_only_amount, 14000.0, places=2)
        self.assertAlmostEqual(
            flt(frappe.db.get_value("Work Order", wo.name, "produced_qty")),
            1000.0,
            places=2,
        )

    def test_ahead_of_schedule_intermediate_operation_cost_isolation(self):
        """When OP10 consumes all 1000 units ahead of OP20 (300 units), a 300-unit partial
        Manufacture only absorbs 300 units' share of RM_OP1 + RM_OP2, leaving the remaining
        700 units' OP10 cost in the pool for the final 700-unit Manufacture."""
        fg_item = self._make_stock_item("FG-ISOLATE")
        rm_op1 = self._make_stock_item("RM-OP1-ISO")
        rm_op2 = self._make_stock_item("RM-OP2-ISO")

        self._receive_stock(rm_op1, 1000.0, 10.0)
        self._receive_stock(rm_op2, 1000.0, 25.0)

        bom = self._create_bom(
            fg_item,
            [
                {"item_code": rm_op1, "qty": 1.0, "rate": 5.0, "operation": self.op_10},
                {
                    "item_code": rm_op2,
                    "qty": 1.0,
                    "rate": 12.0,
                    "operation": self.op_20,
                },
            ],
            [self.op_10, self.op_20],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        # 1. OP10 consumes full 1000 units ahead of schedule (10,000)
        self._set_wo_operations_completed_qty(wo, {self.op_10: 1000.0, self.op_20: 0.0})
        cons_op1 = self._submit_consumption_entry(
            wo, 1000.0, [{"item_code": rm_op1, "qty": 1000.0}]
        )

        # 2. OP20 confirms 300 units (7,500) and produces 300 FG
        self._set_wo_operations_completed_qty(
            wo, {self.op_10: 1000.0, self.op_20: 300.0}
        )
        cons_op2_part1 = self._submit_consumption_entry(
            wo, 300.0, [{"item_code": rm_op2, "qty": 300.0}]
        )

        mfg_part1 = self._create_manufacture_entry(wo, 300.0, submit=True)
        fg_row_1 = next(d for d in mfg_part1.items if d.is_finished_item)
        # Only 300 * (10.0 + 25.0) = 10,500 (unit rate = 35.0), NOT 17,500
        self.assertAlmostEqual(flt(fg_row_1.basic_rate), 35.0, places=2)
        self.assertAlmostEqual(flt(fg_row_1.basic_amount), 10500.0, places=2)

        # 3. OP20 confirms remaining 700 units (17,500) and produces final 700 FG
        self._set_wo_operations_completed_qty(
            wo, {self.op_10: 1000.0, self.op_20: 1000.0}
        )
        cons_op2_part2 = self._submit_consumption_entry(
            wo, 700.0, [{"item_code": rm_op2, "qty": 700.0}]
        )

        mfg_part2 = self._create_manufacture_entry(wo, 700.0, submit=True)
        fg_row_2 = next(d for d in mfg_part2.items if d.is_finished_item)
        self.assertAlmostEqual(flt(fg_row_2.basic_rate), 35.0, places=2)
        self.assertAlmostEqual(flt(fg_row_2.basic_amount), 24500.0, places=2)

        total_mfg_amount = flt(fg_row_1.basic_amount) + flt(fg_row_2.basic_amount)
        total_cons_amount = (
            flt(cons_op1.total_outgoing_value)
            + flt(cons_op2_part1.total_outgoing_value)
            + flt(cons_op2_part2.total_outgoing_value)
        )
        self.assertAlmostEqual(total_mfg_amount, total_cons_amount, places=2)
        self.assertAlmostEqual(total_mfg_amount, 35000.0, places=2)

    def test_short_close_final_flag_and_alternative_item_and_zero_pool_fallback(self):
        """Tests alternative item cost attribution for partial batch (300), final-flag
        short-close (500 over 300 = 800 < 1000) absorbing remaining consumption pool, and
        safe BOM fallback when remaining pool reaches zero."""
        fg_item = self._make_stock_item("FG-SHORT")
        rm_orig = self._make_stock_item("RM-ORIG", allow_alternative_item=1)
        rm_alt = self._make_stock_item("RM-ALT", allow_alternative_item=1)

        frappe.get_doc(
            {
                "doctype": "Item Alternative",
                "item_code": rm_orig,
                "alternative_item_code": rm_alt,
                "two_way": 0,
            }
        ).insert(ignore_permissions=True)

        # Seed valuation rate for original RM before BOM (10.0) and actual alt RM stock (18.0)
        self._receive_stock(rm_orig, 10.0, 10.0)
        self._receive_stock(rm_alt, 1000.0, 18.0)

        bom = self._create_bom(
            fg_item,
            [
                {
                    "item_code": rm_orig,
                    "qty": 1.0,
                    "rate": 10.0,
                    "operation": self.op_10,
                    "allow_alternative_item": 1,
                }
            ],
            [self.op_10],
        )
        wo = self._create_work_order(
            fg_item, bom.name, qty=1000.0, allow_alternative_item=1
        )

        # Consume all 1000 units using the alternative item
        self._set_wo_operations_completed_qty(wo, {self.op_10: 1000.0})
        cons = self._submit_consumption_entry(
            wo,
            1000.0,
            [
                {
                    "item_code": rm_alt,
                    "qty": 1000.0,
                    "original_item": rm_orig,
                    "custom_original_item": rm_orig,
                }
            ],
        )

        # 1. Partial Manufacture (300 units) gets actual alternative item cost (18.0/unit = 5400)
        mfg_1 = self._create_manufacture_entry(wo, 300.0, is_final=False, submit=True)
        fg_row_1 = next(d for d in mfg_1.items if d.is_finished_item)
        self.assertAlmostEqual(flt(fg_row_1.basic_rate), 18.0, places=2)
        self.assertAlmostEqual(flt(fg_row_1.basic_amount), 5400.0, places=2)

        # 2. Short-close Manufacture (500 units, total 800 < 1000) with kta_is_final_confirmation
        mfg_2 = self._create_manufacture_entry(wo, 500.0, is_final=True, submit=True)
        fg_row_2 = next(d for d in mfg_2.items if d.is_finished_item)
        # Absorbs remaining 18000 - 5400 = 12600 -> 25.20/unit
        self.assertAlmostEqual(flt(fg_row_2.basic_rate), 25.2, places=2)
        self.assertAlmostEqual(flt(fg_row_2.basic_amount), 12600.0, places=2)

        total_mfg_amount = flt(fg_row_1.basic_amount) + flt(fg_row_2.basic_amount)
        self.assertAlmostEqual(
            total_mfg_amount, flt(cons.total_outgoing_value), places=2
        )

        # 3. Pool is now exhausted (remaining_pool_cost == 0): additional Manufacture falls back safely to BOM cost
        mfg_extra = self._create_manufacture_entry(
            wo, 100.0, is_final=False, submit=False
        )
        mfg_extra.calculate_rate_and_amount(raise_error_if_no_rate=False)
        fg_row_extra = next(d for d in mfg_extra.items if d.is_finished_item)
        self.assertAlmostEqual(flt(fg_row_extra.basic_rate), 10.0, places=2)
        self.assertAlmostEqual(flt(fg_row_extra.basic_amount), 1000.0, places=2)

    def test_negative_raw_materials_blocked_in_manufacture_when_consumption_exists(
        self,
    ):
        """When material_consumption and get_rm_cost_from_consumption_entry are enabled and a
        submitted Consumption entry exists, adding raw materials to Manufacture throws ValidationError."""
        fg_item = self._make_stock_item("FG-BLOCK")
        rm1 = self._make_stock_item("RM1-BLOCK")

        self._receive_stock(rm1, 1000.0, 10.0)
        bom = self._create_bom(
            fg_item,
            [{"item_code": rm1, "qty": 1.0, "rate": 10.0, "operation": self.op_10}],
            [self.op_10],
        )
        wo = self._create_work_order(fg_item, bom.name, qty=1000.0)

        self._set_wo_operations_completed_qty(wo, {self.op_10: 300.0})
        self._submit_consumption_entry(wo, 300.0, [{"item_code": rm1, "qty": 300.0}])

        mfg = self._create_manufacture_entry(wo, 300.0, submit=False)
        mfg.append(
            "items",
            {
                "item_code": rm1,
                "qty": 300.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.src_warehouse,
            },
        )

        with self.assertRaises(frappe.ValidationError) as cm:
            mfg.insert(ignore_permissions=True)

        self.assertIn("raw materials cannot be added", str(cm.exception))
