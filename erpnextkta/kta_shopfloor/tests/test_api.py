# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime

from erpnextkta.kta_shopfloor.api import (
    cancel_co11n_confirmation,
    cancel_production_confirmation,
    check_confirmation_materials,
    check_material_availability,
    create_work_order,
    get_active_work_orders,
    get_co11n_confirmations,
    get_co11n_context,
    get_item_default_bom,
    get_production_confirmations,
    get_shopfloor_hub_context,
    release_work_order,
    stage_confirmation_materials,
    submit_co11n_confirmation,
    submit_production_confirmation,
    update_work_order_quantity,
)
from erpnextkta.tests.test_utils import KTATestCase


class TestCO11NAPI(KTATestCase):
    def setUp(self):
        super().setUp()
        self._prev_default_company = frappe.db.get_default("company")
        self._setup_test_work_order_and_job_cards()

    def tearDown(self):
        if getattr(self, "_prev_default_company", None):
            frappe.db.set_default("company", self._prev_default_company)
            frappe.db.commit()
            frappe.clear_cache()
        super().tearDown()

    def _setup_test_work_order_and_job_cards(self):
        frappe.db.set_default("company", self.company)
        frappe.clear_cache()
        self.op1 = "0010 Kesim"
        self.op2 = "0020 Test ve Montaj"

        for op in [self.op1, self.op2]:
            if not frappe.db.exists("Operation", op):
                frappe.get_doc(
                    {"doctype": "Operation", "name": op, "workstation": self.ws_name}
                ).insert(ignore_permissions=True)

        frappe.db.delete("Work Order Operation", {"parent": self.wo_name})
        frappe.db.delete("Stock Entry", {"work_order": self.wo_name})
        frappe.db.delete("KTA Production Confirmation", {"work_order": self.wo_name})
        frappe.get_doc(
            {
                "doctype": "Work Order Operation",
                "parent": self.wo_name,
                "parenttype": "Work Order",
                "parentfield": "operations",
                "operation": self.op1,
                "workstation": self.ws_name,
                "sequence_id": 1,
                "idx": 1,
                "completed_qty": 0.0,
                "time_in_mins": 60.0,
                "status": "Pending",
            }
        ).insert(ignore_permissions=True)

        frappe.get_doc(
            {
                "doctype": "Work Order Operation",
                "parent": self.wo_name,
                "parenttype": "Work Order",
                "parentfield": "operations",
                "operation": self.op2,
                "workstation": self.ws_name,
                "sequence_id": 2,
                "idx": 2,
                "completed_qty": 0.0,
                "time_in_mins": 60.0,
                "status": "Pending",
            }
        ).insert(ignore_permissions=True)

        frappe.db.set_value(
            "Work Order",
            self.wo_name,
            {
                "docstatus": 1,
                "status": "Not Started",
                "produced_qty": 0.0,
            },
        )
        self.wo = frappe.get_doc("Work Order", self.wo_name)
        self.jc1 = self._get_or_create_draft_job_card("TEST-JC-API-001", self.op1)
        self.jc2 = self._get_or_create_draft_job_card("TEST-JC-API-002", self.op2)
        frappe.db.commit()

    def _get_or_create_draft_job_card(self, name: str, operation: str) -> str:
        if frappe.db.exists("Job Card", name):
            frappe.db.set_value(
                "Job Card",
                name,
                {
                    "work_order": self.wo_name,
                    "operation": operation,
                    "docstatus": 0,
                    "status": "Open",
                    "total_completed_qty": 0.0,
                    "for_quantity": 100.0,
                },
            )
            return name

        jc = frappe.get_doc(
            {
                "doctype": "Job Card",
                "name": name,
                "work_order": self.wo_name,
                "operation": operation,
                "workstation": self.ws_name,
                "production_item": self.item,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "for_quantity": 100.0,
                "total_completed_qty": 0.0,
                "status": "Open",
                "docstatus": 0,
            }
        )
        jc.flags.ignore_permissions = True
        jc.flags.ignore_mandatory = True
        jc.insert(ignore_permissions=True)
        return jc.name

    def test_get_co11n_context_empty_barcode(self):
        """Empty or None barcode raises ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            get_co11n_context("")

        with self.assertRaises(frappe.ValidationError):
            get_co11n_context(None)

    def test_get_co11n_context_nonexistent_barcode(self):
        """Nonexistent barcode raises ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            get_co11n_context("INVALID_BARCODE_XYZ_123")

    def test_get_co11n_context_from_work_order(self):
        """Scanning Work Order name returns context and operations."""
        ctx = get_co11n_context(self.wo_name)
        self.assertEqual(ctx["work_order"], self.wo_name)
        self.assertEqual(ctx["item_code"], self.item)
        self.assertEqual(ctx["qty"], 100.0)
        self.assertEqual(ctx["produced_qty"], 0.0)
        self.assertEqual(ctx["selected_operation"], self.op1)
        self.assertEqual(len(ctx["operations"]), 2)

        op1_data = ctx["operations"][0]
        self.assertEqual(op1_data["operation"], self.op1)
        self.assertEqual(op1_data["sequence_id"], 1)
        self.assertEqual(op1_data["is_last_op"], False)
        self.assertEqual(op1_data["job_card"], self.jc1)

        op2_data = ctx["operations"][1]
        self.assertEqual(op2_data["operation"], self.op2)
        self.assertEqual(op2_data["is_last_op"], True)
        self.assertEqual(op2_data["job_card"], self.jc2)

    def test_get_co11n_context_from_job_card(self):
        """Scanning Job Card name resolves WO and sets selected_job_card and operation."""
        ctx = get_co11n_context(self.jc2)
        self.assertEqual(ctx["work_order"], self.wo_name)
        self.assertEqual(ctx["selected_job_card"], self.jc2)
        self.assertEqual(ctx["selected_operation"], self.op2)
        self.assertEqual(len(ctx["operations"]), 2)

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    def test_submit_co11n_confirmation(self, mock_consumption):
        """submit_co11n_confirmation delegates to ConfirmationService and returns result."""
        mock_consumption.return_value = "TEST-SE-API-001"

        res = submit_co11n_confirmation(
            {
                "work_order": self.wo_name,
                "operation": self.op1,
                "yield_qty": 25.0,
                "is_final_confirmation": 0,
            }
        )
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("confirmation"))
        self.assertEqual(res.get("stock_entry"), "TEST-SE-API-001")

    @patch(
        "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService.create_consumption_entry"
    )
    def test_cancel_co11n_confirmation(self, mock_consumption):
        """cancel_co11n_confirmation cancels confirmation using ReversalService."""
        mock_consumption.return_value = None

        res = submit_co11n_confirmation(
            {
                "work_order": self.wo_name,
                "operation": self.op1,
                "yield_qty": 10.0,
                "is_final_confirmation": 0,
            }
        )
        conf_name = res["confirmation"]

        cancel_res = cancel_co11n_confirmation(conf_name)
        self.assertTrue(cancel_res.get("success"))
        self.assertEqual(
            frappe.db.get_value("KTA Production Confirmation", conf_name, "docstatus"),
            2,
        )

    def test_cancel_co11n_confirmation_unauthorized(self):
        """Non-manager user cannot cancel confirmation."""
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo_name,
                "operation": self.op1,
                "job_card": self.jc1,
                "yield_qty": 10.0,
                "is_final_confirmation": 0,
            }
        )
        conf.flags.ignore_permissions = True
        conf.insert(ignore_permissions=True)
        conf.submit()

        unauthorized_user = "test_unauthorized_operator@example.com"
        current_user = frappe.session.user
        try:
            frappe.set_user(unauthorized_user)
            with (
                patch("frappe.get_roles", return_value=["Manufacturing User"]),
                self.assertRaises(frappe.PermissionError),
            ):
                cancel_co11n_confirmation(conf.name)
        finally:
            frappe.set_user(current_user)

    def _create_legacy_work_order(
        self, qty: float = 5000.0, legacy_mfg_qty: float = 720.0
    ) -> str:
        wo = frappe.get_doc(
            {
                "doctype": "Work Order",
                "naming_series": "MFG-WO-.YYYY.-",
                "production_item": self.item,
                "qty": qty,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "fg_warehouse": getattr(self.wo, "fg_warehouse", self.wip_warehouse),
                "status": "In Process",
                "produced_qty": legacy_mfg_qty,
                "operations": [
                    {
                        "operation": self.op1,
                        "workstation": self.ws_name,
                        "sequence_id": 1,
                        "idx": 1,
                        "completed_qty": qty,
                        "status": "Completed",
                        "time_in_mins": 60.0,
                    }
                ],
            }
        )
        wo.flags.ignore_permissions = True
        wo.flags.ignore_mandatory = True
        wo.insert(ignore_permissions=True)
        frappe.db.set_value("Work Order", wo.name, "docstatus", 1)

        # Legacy Job Card submitted for full qty (docstatus=1)
        jc = frappe.get_doc(
            {
                "doctype": "Job Card",
                "work_order": wo.name,
                "operation": self.op1,
                "workstation": self.ws_name,
                "production_item": self.item,
                "company": self.company,
                "wip_warehouse": self.wip_warehouse,
                "for_quantity": qty,
                "total_completed_qty": qty,
                "process_loss_qty": 0.0,
                "status": "Completed",
                "docstatus": 0,
            }
        )
        jc.flags.ignore_permissions = True
        jc.flags.ignore_mandatory = True
        jc.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Job Card", jc.name, {"docstatus": 1, "status": "Completed"}
        )

        # Create legacy Stock Entry (Manufacture) of 720 units
        # (not tied to any KTA Production Confirmation)
        se_name = f"TEST-SE-LEGACY-{frappe.generate_hash(length=6)}"
        frappe.db.sql(
            """
            INSERT INTO `tabStock Entry` (
                name, docstatus, purpose, stock_entry_type, work_order, company,
                fg_completed_qty, creation, modified, modified_by
            ) VALUES (%s, 1, 'Manufacture', 'Manufacture', %s, %s, %s,
                NOW(), NOW(), 'Administrator')
            """,
            (se_name, wo.name, self.company, legacy_mfg_qty),
        )
        frappe.db.commit()
        return wo.name

    def test_legacy_work_order_operation_quantities_normalization(self):
        """get_co11n_context normalizes legacy WO quantities and self-heals Work Order Operation."""
        legacy_wo = self._create_legacy_work_order(qty=5000.0, legacy_mfg_qty=720.0)

        # Verify initial raw DB row has artificial 5000.0
        initial_db = frappe.db.get_value(
            "Work Order Operation",
            {"parent": legacy_wo, "operation": self.op1},
            ["completed_qty", "status"],
            as_dict=True,
        )
        self.assertEqual(flt(initial_db.completed_qty), 5000.0)
        self.assertEqual(initial_db.status, "Completed")

        # Call get_co11n_context
        ctx = get_co11n_context(legacy_wo)
        self.assertEqual(ctx["work_order"], legacy_wo)
        self.assertEqual(len(ctx["operations"]), 1)

        op = ctx["operations"][0]
        self.assertEqual(op["operation"], self.op1)
        self.assertEqual(flt(op["completed_qty"]), 720.0)
        self.assertEqual(flt(op["pending_qty"]), 4280.0)
        self.assertEqual(op["status"], "Work In Progress")

        # Verify Work Order Operation row was self-healed in DB
        healed_db = frappe.db.get_value(
            "Work Order Operation",
            {"parent": legacy_wo, "operation": self.op1},
            ["completed_qty", "status"],
            as_dict=True,
        )
        self.assertEqual(flt(healed_db.completed_qty), 720.0)
        self.assertEqual(healed_db.status, "Work In Progress")

    def test_legacy_work_order_subsequent_confirmation(self):
        """CO11N confirmation on legacy WO adds on top of legacy qty (720 + 100 = 820)."""
        legacy_wo = self._create_legacy_work_order(qty=5000.0, legacy_mfg_qty=720.0)

        cons_entry_target = (
            "erpnextkta.kta_shopfloor.services.confirmation_service."
            "BackflushService.create_consumption_entry"
        )
        with patch(cons_entry_target) as mock_se:
            mock_se.return_value = None
            res = submit_co11n_confirmation(
                {
                    "work_order": legacy_wo,
                    "operation": self.op1,
                    "yield_qty": 100.0,
                    "is_final_confirmation": 0,
                }
            )
            self.assertTrue(res.get("success"))

        ctx = get_co11n_context(legacy_wo)
        op = ctx["operations"][0]
        self.assertEqual(flt(op["completed_qty"]), 820.0)
        self.assertEqual(flt(op["pending_qty"]), 4180.0)
        self.assertEqual(op["status"], "Work In Progress")

    def test_legacy_work_order_reversal(self):
        """Cancelling 100-unit confirmation restores legacy quantities (completed=720, pending=4280)."""
        legacy_wo = self._create_legacy_work_order(qty=5000.0, legacy_mfg_qty=720.0)

        cons_entry_target = (
            "erpnextkta.kta_shopfloor.services.confirmation_service."
            "BackflushService.create_consumption_entry"
        )
        with patch(cons_entry_target) as mock_se:
            mock_se.return_value = None
            res = submit_co11n_confirmation(
                {
                    "work_order": legacy_wo,
                    "operation": self.op1,
                    "yield_qty": 100.0,
                    "is_final_confirmation": 0,
                }
            )
            self.assertTrue(res.get("success"))
            conf_name = res["confirmation"]

        # Cancel confirmation
        cancel_res = cancel_co11n_confirmation(conf_name)
        self.assertTrue(cancel_res.get("success"))

        ctx = get_co11n_context(legacy_wo)
        op = ctx["operations"][0]
        self.assertEqual(flt(op["completed_qty"]), 720.0)
        self.assertEqual(flt(op["pending_qty"]), 4280.0)
        self.assertEqual(op["status"], "Work In Progress")

    def test_get_active_work_orders(self):
        """get_active_work_orders returns active work orders with search and status filtering."""
        # 1. Basic listing: self.wo_name must be present in the active list
        active_orders = get_active_work_orders()
        wo_names = [d["name"] for d in active_orders]
        self.assertIn(self.wo_name, wo_names)

        # Check required fields exist in result
        matching_order = next(d for d in active_orders if d["name"] == self.wo_name)
        for key in [
            "name",
            "production_item",
            "item_name",
            "qty",
            "produced_qty",
            "status",
            "planned_start_date",
            "modified",
        ]:
            self.assertIn(key, matching_order)
        self.assertEqual(matching_order["status"], "Not Started")

        # 2. Search filter by WO name
        search_by_name = get_active_work_orders(search=self.wo_name)
        self.assertTrue(any(d["name"] == self.wo_name for d in search_by_name))

        # Search filter by production_item
        search_by_item = get_active_work_orders(
            search=matching_order["production_item"]
        )
        self.assertTrue(any(d["name"] == self.wo_name for d in search_by_item))

        # Search with non-matching query
        no_match = get_active_work_orders(search="NON_EXISTENT_WO_999999_XYZ")
        self.assertEqual(len(no_match), 0)

        # 3. Status filter
        not_started = get_active_work_orders(status="Not Started")
        self.assertTrue(any(d["name"] == self.wo_name for d in not_started))

        completed = get_active_work_orders(status="Completed")
        self.assertFalse(any(d["name"] == self.wo_name for d in completed))

        # 4. Limit parameter
        limited = get_active_work_orders(limit=1)
        self.assertLessEqual(len(limited), 1)

        # 5. Explicit company filter
        by_company = get_active_work_orders(company=self.company)
        self.assertTrue(any(d["name"] == self.wo_name for d in by_company))

        by_other_company = get_active_work_orders(company="_Test Company")
        self.assertFalse(any(d["name"] == self.wo_name for d in by_other_company))

    def test_submit_co11n_confirmation_returns_multiple_stock_entries(self):
        """Milestone confirmation produces and returns both consumption and manufacture entries."""
        target_pkg = (
            "erpnextkta.kta_shopfloor.services.confirmation_service.BackflushService"
        )
        with (
            patch(
                f"{target_pkg}.create_consumption_entry",
                return_value="MAT-STE-TEST-CONS",
            ),
            patch(
                f"{target_pkg}.create_finished_goods_entry",
                return_value="MAT-STE-TEST-FG",
            ),
        ):
            res = submit_co11n_confirmation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op2,
                    "yield_qty": 10.0,
                }
            )
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("stock_entry"), "MAT-STE-TEST-FG")
            self.assertEqual(res.get("consumption_stock_entry"), "MAT-STE-TEST-CONS")
            stock_entries = res.get("stock_entries") or []
            self.assertEqual(len(stock_entries), 2)
            self.assertEqual(stock_entries[0]["name"], "MAT-STE-TEST-CONS")
            self.assertEqual(stock_entries[0]["type"], "consumption")
            self.assertEqual(stock_entries[0]["label"], _("Tüketim"))
            self.assertEqual(stock_entries[1]["name"], "MAT-STE-TEST-FG")
            self.assertEqual(stock_entries[1]["type"], "manufacture")
            self.assertEqual(stock_entries[1]["label"], _("Üretim"))

    def test_get_co11n_confirmations(self):
        """get_co11n_confirmations returns confirmations with all associated stock entries."""
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": self.wo_name,
                "operation": self.op2,
                "job_card": self.jc2,
                "yield_qty": 30.0,
                "is_final_confirmation": 0,
                "posting_date": frappe.utils.nowdate(),
                "posting_time": frappe.utils.nowtime(),
                "confirmed_by": "Administrator",
            }
        ).insert(ignore_permissions=True)

        se_cons = frappe.new_doc("Stock Entry")
        se_cons.purpose = "Material Consumption for Manufacture"
        se_cons.stock_entry_type = "Material Consumption for Manufacture"
        se_cons.work_order = self.wo_name
        se_cons.company = self.company
        se_cons.remarks = f"KTA Production Confirmation: {conf.name}"
        se_cons.flags.ignore_validate = True
        se_cons.flags.ignore_mandatory = True
        se_cons.insert(ignore_permissions=True)

        se_fg = frappe.new_doc("Stock Entry")
        se_fg.purpose = "Manufacture"
        se_fg.stock_entry_type = "Manufacture"
        se_fg.work_order = self.wo_name
        se_fg.company = self.company
        se_fg.fg_completed_qty = 30.0
        se_fg.remarks = f"KTA Production Confirmation: {conf.name}"
        se_fg.flags.ignore_validate = True
        se_fg.flags.ignore_mandatory = True
        se_fg.insert(ignore_permissions=True)

        conf.db_set("stock_entry", se_fg.name)

        confirmations = get_co11n_confirmations(self.wo_name)
        self.assertGreaterEqual(len(confirmations), 1)

        c = next(d for d in confirmations if d["name"] == conf.name)
        self.assertEqual(flt(c["yield_qty"]), 30.0)
        self.assertEqual(c["operation"], self.op2)

        stock_entries = c.get("stock_entries") or []
        self.assertEqual(len(stock_entries), 2)

        cons_entry = next(d for d in stock_entries if d["type"] == "consumption")
        self.assertEqual(cons_entry["name"], se_cons.name)
        self.assertEqual(cons_entry["purpose"], "Material Consumption for Manufacture")
        self.assertEqual(cons_entry["label"], _("Tüketim"))

        fg_entry = next(d for d in stock_entries if d["type"] == "manufacture")
        self.assertEqual(fg_entry["name"], se_fg.name)
        self.assertEqual(fg_entry["purpose"], "Manufacture")
        self.assertEqual(fg_entry["label"], _("Üretim"))

    def test_endpoint_aliases(self):
        """Verify new English endpoint names and legacy aliases match."""
        ctx_new = get_shopfloor_hub_context(self.wo_name)
        ctx_legacy = get_co11n_context(self.wo_name)
        self.assertEqual(ctx_new["work_order"], ctx_legacy["work_order"])
        self.assertEqual(len(ctx_new["operations"]), len(ctx_legacy["operations"]))

        confs_new = get_production_confirmations(self.wo_name)
        confs_legacy = get_co11n_confirmations(self.wo_name)
        self.assertEqual(len(confs_new), len(confs_legacy))

        cons_entry_target = (
            "erpnextkta.kta_shopfloor.services.confirmation_service."
            "BackflushService.create_consumption_entry"
        )
        with patch(
            cons_entry_target,
            return_value="MAT-STE-ALIAS-01",
        ):
            res_new = submit_production_confirmation(
                {
                    "work_order": self.wo_name,
                    "operation": self.op1,
                    "yield_qty": 5.0,
                }
            )
            self.assertTrue(res_new.get("success"))
            conf_id = res_new["confirmation"]

            cancel_res = cancel_production_confirmation(conf_id)
            self.assertTrue(cancel_res.get("success"))

    def _setup_api_bom_and_warehouses(self):
        item_group = (
            frappe.db.get_value("Item", self.item, "item_group") or "All Item Groups"
        )
        src_wh = f"_Test API Source WH - {frappe.db.get_value('Company', self.company, 'abbr')}"
        fg_wh = (
            f"_Test API FG WH - {frappe.db.get_value('Company', self.company, 'abbr')}"
        )
        for wh_name, full_wh in [
            ("_Test API Source WH", src_wh),
            ("_Test API FG WH", fg_wh),
        ]:
            if not frappe.db.exists("Warehouse", full_wh):
                frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": wh_name,
                        "company": self.company,
                    }
                ).insert(ignore_permissions=True)

        fg_item = "_Test FG Item API WO"
        rm_item = "_Test RM Item API WO"
        for code in [fg_item, rm_item]:
            if not frappe.db.exists("Item", code):
                frappe.get_doc(
                    {
                        "doctype": "Item",
                        "item_code": code,
                        "item_name": f"{code} Name",
                        "item_group": item_group,
                        "is_stock_item": 1,
                        "stock_uom": "Nos",
                        "valuation_rate": 10.0,
                    }
                ).insert(ignore_permissions=True)

        bom_name = frappe.db.get_value(
            "BOM",
            {"item": fg_item, "is_active": 1, "is_default": 1, "docstatus": 1},
            "name",
        )
        if not bom_name:
            bom = frappe.get_doc(
                {
                    "doctype": "BOM",
                    "item": fg_item,
                    "company": self.company,
                    "quantity": 1,
                    "is_active": 1,
                    "is_default": 1,
                    "with_operations": 0,
                    "currency": "TRY",
                    "conversion_rate": 1.0,
                    "items": [
                        {
                            "item_code": rm_item,
                            "qty": 3,
                            "uom": "Nos",
                            "rate": 5.0,
                            "source_warehouse": src_wh,
                        }
                    ],
                }
            )
            bom.flags.ignore_permissions = True
            bom.insert(ignore_permissions=True)
            bom.submit()
            bom_name = bom.name

        return fg_item, rm_item, bom_name, src_wh, fg_wh

    def _set_api_bin_qty(
        self,
        item_code: str,
        warehouse: str,
        qty: float,
        reserved_qty: float = 0.0,
    ):
        bin_name = frappe.db.get_value(
            "Bin", {"item_code": item_code, "warehouse": warehouse}, "name"
        )
        if bin_name:
            frappe.db.set_value(
                "Bin",
                bin_name,
                {
                    "actual_qty": flt(qty),
                    "reserved_qty_for_production": flt(reserved_qty),
                },
            )
        else:
            frappe.get_doc(
                {
                    "doctype": "Bin",
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "actual_qty": flt(qty),
                    "reserved_qty_for_production": flt(reserved_qty),
                }
            ).insert(ignore_permissions=True)

    def test_api_get_item_default_bom(self):
        """get_item_default_bom returns default BOM, UOM, and 14-day fallback lead days."""
        res_missing = get_item_default_bom("NON_EXISTENT")
        self.assertEqual(res_missing["item_code"], "NON_EXISTENT")
        self.assertIn("bom", res_missing)
        self.assertIsNone(res_missing["bom"])
        self.assertEqual(res_missing["manufacturing_lead_days"], 14)

        fg_item, _, bom_name, _, _ = self._setup_api_bom_and_warehouses()
        res = get_item_default_bom(fg_item)
        self.assertEqual(res["item_code"], fg_item)
        self.assertEqual(res["item_name"], f"{fg_item} Name")
        self.assertEqual(res["bom"], bom_name)
        self.assertEqual(res["stock_uom"], "Nos")
        self.assertEqual(res["manufacturing_lead_days"], 14)

    def test_api_create_work_order(self):
        """create_work_order creates a Draft Work Order via work_order_service."""
        fg_item, _, bom_name, src_wh, fg_wh = self._setup_api_bom_and_warehouses()
        start_date = "2026-11-18"
        res = create_work_order(
            item_code=fg_item,
            qty=4,
            source_warehouse=src_wh,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=fg_wh,
            planned_start_date=start_date,
            company=self.company,
        )
        self.assertEqual(res["docstatus"], 0)
        self.assertEqual(res["status"], "Draft")
        self.assertEqual(res["bom_no"], bom_name)
        self.assertEqual(
            str(getdate(res["planned_end_date"])), add_days(start_date, 14)
        )
        self.assertTrue(frappe.db.exists("Work Order", res["name"]))

    def test_api_check_material_availability(self):
        """check_material_availability returns availability summary and clamps negative stock."""
        fg_item, rm_item, _, src_wh, fg_wh = self._setup_api_bom_and_warehouses()
        wo_res = create_work_order(
            item_code=fg_item,
            qty=4,  # requires 12 of rm_item
            source_warehouse=src_wh,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=fg_wh,
            company=self.company,
        )
        self._set_api_bin_qty(rm_item, src_wh, 6.0)
        avail = check_material_availability(wo_res["name"])
        self.assertEqual(avail["work_order"], wo_res["name"])
        self.assertTrue(avail["has_shortage"])
        self.assertEqual(avail["overall_readiness_percent"], 50.0)
        self.assertEqual(avail["items"][0]["shortage_qty"], 6.0)
        self.assertEqual(avail["items"][0]["coverage_percent"], 50.0)

        # Negative actual_qty should clamp coverage_percent to 0.0
        self._set_api_bin_qty(rm_item, src_wh, -5.0)
        avail_neg = check_material_availability(wo_res["name"])
        self.assertEqual(avail_neg["items"][0]["coverage_percent"], 0.0)
        self.assertEqual(avail_neg["overall_readiness_percent"], 0.0)

    def test_api_release_work_order(self):
        """release_work_order blocks shortage unless allow_shortage=1, and submits cleanly."""
        fg_item, rm_item, _, src_wh, fg_wh = self._setup_api_bom_and_warehouses()
        wo_res = create_work_order(
            item_code=fg_item,
            qty=4,
            source_warehouse=src_wh,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=fg_wh,
            company=self.company,
        )
        wo_name = wo_res["name"]
        self._set_api_bin_qty(rm_item, src_wh, 2.0)

        with self.assertRaises(frappe.ValidationError):
            release_work_order(wo_name, allow_shortage=0)

        rel = release_work_order(wo_name, allow_shortage=1)
        self.assertEqual(rel["name"], wo_name)
        self.assertEqual(rel["docstatus"], 1)
        self.assertEqual(rel["status"], "Not Started")
        self.assertTrue(rel["released_with_shortage"])

    def test_api_get_active_work_orders_status_filter_and_include_drafts(self):
        """get_active_work_orders supports include_drafts and status_filter values."""
        fg_item, _, _, src_wh, fg_wh = self._setup_api_bom_and_warehouses()
        draft_wo = create_work_order(
            item_code=fg_item,
            qty=2,
            source_warehouse=src_wh,
            wip_warehouse=self.wip_warehouse,
            fg_warehouse=fg_wh,
            company=self.company,
        )
        draft_name = draft_wo["name"]

        # Default (include_drafts=0): excludes Draft, includes Not Started
        ops_orders = get_active_work_orders(company=self.company)
        ops_names = [d["name"] for d in ops_orders]
        self.assertNotIn(draft_name, ops_names)
        self.assertIn(self.wo_name, ops_names)
        sample = next(d for d in ops_orders if d["name"] == self.wo_name)
        for key in [
            "docstatus",
            "status",
            "name",
            "production_item",
            "item_name",
            "qty",
            "produced_qty",
            "planned_start_date",
            "planned_end_date",
        ]:
            self.assertIn(key, sample)

        # include_drafts=1: includes both Draft (docstatus=0) and Released (docstatus=1)
        all_orders = get_active_work_orders(company=self.company, include_drafts=1)
        all_names = [d["name"] for d in all_orders]
        self.assertIn(draft_name, all_names)
        self.assertIn(self.wo_name, all_names)

        # status_filter='Draft': only docstatus=0
        draft_only = get_active_work_orders(
            company=self.company, status_filter="Draft", include_drafts=1
        )
        draft_names = [d["name"] for d in draft_only]
        self.assertIn(draft_name, draft_names)
        self.assertNotIn(self.wo_name, draft_names)
        self.assertTrue(all(d["docstatus"] == 0 for d in draft_only))

        # status_filter='Released': only docstatus=1
        released_only = get_active_work_orders(
            company=self.company, status_filter="Released", include_drafts=1
        )
        released_names = [d["name"] for d in released_only]
        self.assertNotIn(draft_name, released_names)
        self.assertIn(self.wo_name, released_names)
        self.assertTrue(all(d["docstatus"] == 1 for d in released_only))

        # status_filter='In Process' and 'Completed'
        frappe.db.set_value("Work Order", self.wo_name, "status", "In Process")
        in_process = get_active_work_orders(
            company=self.company, status_filter="In Process"
        )
        self.assertIn(self.wo_name, [d["name"] for d in in_process])

        completed_before = get_active_work_orders(
            company=self.company, status_filter="Completed"
        )
        self.assertNotIn(self.wo_name, [d["name"] for d in completed_before])
        frappe.db.set_value("Work Order", self.wo_name, "status", "Completed")
        completed_after = get_active_work_orders(
            company=self.company, status_filter="Completed"
        )
        self.assertIn(self.wo_name, [d["name"] for d in completed_after])

    def test_get_shopfloor_hub_context_includes_uom_docstatus_and_shortage_flag(self):
        """get_shopfloor_hub_context returns stock_uom, docstatus, and custom_released_with_shortage."""
        ctx = get_shopfloor_hub_context(self.wo_name)
        self.assertIn("stock_uom", ctx)
        self.assertEqual(ctx["docstatus"], 1)
        self.assertIn("custom_released_with_shortage", ctx)
        self.assertEqual(ctx["custom_released_with_shortage"], 0)

    def test_api_permission_checks_enforced(self):
        """Whitelisted endpoints enforce Item read, WO read, and WO submit permissions."""
        with (
            patch(
                "erpnextkta.kta_shopfloor.api.frappe.has_permission",
                side_effect=frappe.PermissionError,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            get_item_default_bom(self.item)

        doc_check_perm = (
            "erpnextkta.kta_shopfloor.services.work_order_service."
            "frappe.model.document.Document.check_permission"
        )
        with patch(
            doc_check_perm,
            side_effect=frappe.PermissionError,
        ):
            with self.assertRaises(frappe.PermissionError):
                check_material_availability(self.wo_name)

            with self.assertRaises(frappe.PermissionError):
                release_work_order(self.wo_name, allow_shortage=0)

    def test_get_active_work_orders_company_fallback_guard(self):
        """Outside unit-test mode, _Test default company falls back to first real active company."""
        prev_in_test = frappe.flags.in_test
        try:
            frappe.flags.in_test = False
            with (
                patch(
                    "erpnextkta.kta_shopfloor.api.frappe.defaults.get_user_default",
                    return_value="_Test Company",
                ),
                patch(
                    "erpnextkta.kta_shopfloor.api.frappe.db.get_value",
                    return_value="Real Company A.S.",
                ) as mock_get_value,
                patch(
                    "erpnextkta.kta_shopfloor.api.frappe.get_all",
                    return_value=[],
                ) as mock_get_all,
            ):
                get_active_work_orders()
                mock_get_value.assert_called_once_with(
                    "Company",
                    {"name": ["not like", "_Test%"], "is_group": 0},
                    "name",
                )
                self.assertEqual(
                    mock_get_all.call_args.kwargs["filters"]["company"],
                    "Real Company A.S.",
                )
        finally:
            frappe.flags.in_test = prev_in_test

    def test_get_active_work_orders_fiscal_year_and_order_by(self):
        """get_active_work_orders supports fiscal_year date bounds and custom order_by."""
        orders_asc = get_active_work_orders(
            company=self.company,
            order_by="name asc",
            include_drafts=1,
        )
        orders_desc = get_active_work_orders(
            company=self.company,
            order_by="name desc",
            include_drafts=1,
        )
        if len(orders_asc) >= 2:
            self.assertEqual(orders_asc[0]["name"], orders_desc[-1]["name"])
            self.assertEqual(orders_asc[-1]["name"], orders_desc[0]["name"])

        with patch(
            "erpnextkta.kta_shopfloor.api.frappe.get_all", return_value=[]
        ) as mock_get_all:
            get_active_work_orders(
                company=self.company,
                status_filter="Completed",
            )
            self.assertEqual(mock_get_all.call_args.kwargs.get("order_by"), "name desc")

        with patch(
            "erpnextkta.kta_shopfloor.api.frappe.get_all", return_value=[]
        ) as mock_get_all:
            get_active_work_orders(
                company=self.company,
                status_filter="Not Started",
            )
            self.assertEqual(mock_get_all.call_args.kwargs.get("order_by"), "name asc")

        res_cur_year = get_active_work_orders(
            company=self.company,
            fiscal_year="2026",
            include_drafts=1,
        )
        names_cur_year = [d["name"] for d in res_cur_year]
        self.assertIn(self.wo_name, names_cur_year)

        res_past_year = get_active_work_orders(
            company=self.company,
            fiscal_year="2024",
            include_drafts=1,
        )
        names_past_year = [d["name"] for d in res_past_year]
        self.assertNotIn(self.wo_name, names_past_year)

        with patch(
            "erpnextkta.kta_shopfloor.api.frappe.get_all", return_value=[]
        ) as mock_get_all:
            get_active_work_orders(
                company=self.company,
                status_filter="Completed",
            )
            creation_filter = mock_get_all.call_args.kwargs["filters"].get("creation")
            self.assertIsNotNone(creation_filter)
            self.assertEqual(creation_filter[0], "between")
            self.assertTrue(creation_filter[1][0].startswith("2026-01-01"))
            self.assertTrue(creation_filter[1][1].startswith("2026-12-31"))

    def test_api_update_work_order_quantity(self):
        """update_work_order_quantity endpoint scales draft WO qty and enforces docstatus validation."""
        fg_item, _, bom_name, src_wh, fg_wh = self._setup_api_bom_and_warehouses()
        draft_wo = frappe.get_doc(
            {
                "doctype": "Work Order",
                "production_item": fg_item,
                "bom_no": bom_name,
                "qty": 10.0,
                "company": self.company,
                "source_warehouse": src_wh,
                "wip_warehouse": self.wip_warehouse,
                "fg_warehouse": fg_wh,
            }
        ).insert(ignore_permissions=True)

        res = update_work_order_quantity(draft_wo.name, 25)
        self.assertEqual(res["qty"], 25.0)
        self.assertEqual(res["old_qty"], 10.0)

        draft_wo.reload()
        self.assertEqual(flt(draft_wo.qty), 25.0)

        # Submitted Work Order raises ValidationError
        with self.assertRaises(frappe.ValidationError):
            update_work_order_quantity(self.wo_name, 50)

    def _setup_staging_warehouses_and_rm(
        self,
        line_qty: float,
        prod_source_qty: float,
        rm_stores_qty: float = 0.0,
        has_batch_no: int = 0,
        create_new_batch: int = 0,
        batch_number_series: str | None = None,
    ) -> tuple[str, str, str, str]:
        abbr = frappe.db.get_value("Company", self.company, "abbr")
        uid = frappe.generate_hash(length=6)
        rm_item = f"_Test RM API {uid}"
        item_doc = {
            "doctype": "Item",
            "item_code": rm_item,
            "item_name": f"{rm_item} Name",
            "item_group": "All Item Groups",
            "is_stock_item": 1,
            "stock_uom": "Nos",
            "has_batch_no": has_batch_no,
            "create_new_batch": create_new_batch,
            "has_serial_no": 0,
            "valuation_rate": 10.0,
        }
        if batch_number_series:
            item_doc["batch_number_series"] = batch_number_series
        elif create_new_batch:
            item_doc["batch_number_series"] = f"TSFB-{uid}-.#####"
        frappe.get_doc(item_doc).insert(ignore_permissions=True)
        line_wh = f"_Test WIP Line 1 {uid} - {abbr}"
        prod_source_wh = f"_Test WIP Line 2 {uid} - {abbr}"
        rm_stores_wh = f"_Test Raw Material Stores {uid} - {abbr}"

        for wh_name, full_wh in [
            (f"_Test WIP Line 1 {uid}", line_wh),
            (f"_Test WIP Line 2 {uid}", prod_source_wh),
            (f"_Test Raw Material Stores {uid}", rm_stores_wh),
        ]:
            if not frappe.db.exists("Warehouse", full_wh):
                frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": wh_name,
                        "company": self.company,
                    }
                ).insert(ignore_permissions=True)

        receipt_items = []
        if prod_source_qty > 0:
            receipt_items.append(
                {
                    "item_code": rm_item,
                    "t_warehouse": prod_source_wh,
                    "qty": prod_source_qty,
                    "basic_rate": 10.0,
                    "conversion_factor": 1.0,
                }
            )
        if rm_stores_qty > 0:
            receipt_items.append(
                {
                    "item_code": rm_item,
                    "t_warehouse": rm_stores_wh,
                    "qty": rm_stores_qty,
                    "basic_rate": 10.0,
                    "conversion_factor": 1.0,
                }
            )
        if line_qty > 0:
            receipt_items.append(
                {
                    "item_code": rm_item,
                    "t_warehouse": line_wh,
                    "qty": line_qty,
                    "basic_rate": 10.0,
                    "conversion_factor": 1.0,
                }
            )

        if receipt_items:
            init_se = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "purpose": "Material Receipt",
                    "stock_entry_type": "Material Receipt",
                    "company": self.company,
                    "items": receipt_items,
                }
            )
            init_se.flags.ignore_permissions = True
            init_se.insert(ignore_permissions=True)
            init_se.submit()

        return rm_item, line_wh, prod_source_wh, rm_stores_wh

    def test_check_confirmation_materials_and_staging(self):
        """Verify check_confirmation_materials detects line shortages, restricts replenishment

        strictly to production warehouses, and stage_confirmation_materials executes transfer.
        """
        fg_item, _, _, _, fg_wh = self._setup_api_bom_and_warehouses()
        rm_item, line_wh, prod_source_wh, rm_stores_wh = (
            self._setup_staging_warehouses_and_rm(
                line_qty=2.0,
                prod_source_qty=50.0,
                rm_stores_qty=100.0,
            )
        )

        wo_doc = frappe.get_doc(
            {
                "doctype": "Work Order",
                "production_item": fg_item,
                "qty": 10.0,
                "company": self.company,
                "source_warehouse": line_wh,
                "wip_warehouse": line_wh,
                "fg_warehouse": fg_wh,
                "skip_transfer": 1,
            }
        )
        wo_doc.flags.ignore_permissions = True
        wo_doc.flags.ignore_mandatory = True
        wo_doc.insert(ignore_permissions=True)
        wo_doc.required_items = []
        wo_doc.append(
            "required_items",
            {
                "item_code": rm_item,
                "required_qty": 30.0,
                "source_warehouse": line_wh,
            },
        )
        wo_doc.save(ignore_permissions=True)
        wo_doc.submit()

        # 1. Check confirmation materials detects shortage and ONLY suggests production warehouse
        chk = check_confirmation_materials(
            work_order=wo_doc.name,
            operation="",
            yield_qty=2.0,
        )
        self.assertTrue(chk["has_shortage"])
        self.assertEqual(len(chk["shortages"]), 1)
        shortage = chk["shortages"][0]
        self.assertEqual(shortage["item_code"], rm_item)
        self.assertEqual(flt(shortage["required_qty"]), 6.0)
        self.assertEqual(flt(shortage["line_actual_qty"]), 2.0)
        self.assertEqual(flt(shortage["shortage_qty"]), 4.0)
        self.assertEqual(shortage["target_warehouse"], line_wh)
        # Crucial: Must recommend production warehouse (prod_source_wh), NEVER rm_stores_wh
        self.assertEqual(shortage["source_warehouse"], prod_source_wh)
        self.assertGreaterEqual(flt(shortage["source_available_qty"]), 50.0)
        source_warehouses = [s["warehouse"] for s in shortage["available_sources"]]
        self.assertIn(prod_source_wh, source_warehouses)
        self.assertNotIn(rm_stores_wh, source_warehouses)

        # 2. Validation errors
        # 2a. Raw material / Central store blocked from line staging
        with self.assertRaises(frappe.ValidationError):
            stage_confirmation_materials(
                wo_doc.name,
                [
                    {
                        "item_code": rm_item,
                        "qty": 4.0,
                        "source_warehouse": rm_stores_wh,
                        "target_warehouse": line_wh,
                    }
                ],
            )

        # 2b. Same warehouse blocked
        with self.assertRaises(frappe.ValidationError):
            stage_confirmation_materials(
                wo_doc.name,
                [
                    {
                        "item_code": rm_item,
                        "qty": 4.0,
                        "source_warehouse": prod_source_wh,
                        "target_warehouse": prod_source_wh,
                    }
                ],
            )

        # 2c. Qty <= 0 blocked
        with self.assertRaises(frappe.ValidationError):
            stage_confirmation_materials(
                wo_doc.name,
                [
                    {
                        "item_code": rm_item,
                        "qty": 0.0,
                        "source_warehouse": prod_source_wh,
                        "target_warehouse": line_wh,
                    }
                ],
            )

        # 2d. Insufficient stock at source blocked
        with self.assertRaises(frappe.ValidationError):
            stage_confirmation_materials(
                wo_doc.name,
                [
                    {
                        "item_code": rm_item,
                        "qty": 999.0,
                        "source_warehouse": prod_source_wh,
                        "target_warehouse": line_wh,
                    }
                ],
            )

        # 3. Perform valid staging transfer between production warehouses
        transfers = [
            {
                "item_code": rm_item,
                "qty": 4.0,
                "source_warehouse": prod_source_wh,
                "target_warehouse": line_wh,
            }
        ]
        res = stage_confirmation_materials(wo_doc.name, transfers)
        self.assertTrue(res["success"])
        self.assertTrue(res["stock_entry"])
        se_doc = frappe.get_doc("Stock Entry", res["stock_entry"])
        self.assertEqual(se_doc.docstatus, 1)
        self.assertEqual(se_doc.purpose, "Material Transfer for Manufacture")
        self.assertEqual(se_doc.work_order, wo_doc.name)
        self.assertEqual(len(se_doc.items), 1)
        self.assertEqual(se_doc.items[0].s_warehouse, prod_source_wh)
        self.assertEqual(se_doc.items[0].t_warehouse, line_wh)
        self.assertEqual(flt(se_doc.items[0].qty), 4.0)

        # 4. JSON string payload input
        json_res = stage_confirmation_materials(
            wo_doc.name,
            frappe.as_json(
                [
                    {
                        "item_code": rm_item,
                        "qty": 1.0,
                        "source_warehouse": prod_source_wh,
                        "target_warehouse": line_wh,
                    }
                ]
            ),
        )
        self.assertTrue(json_res["success"])

        # 5. Check line stock after transfers: 2.0 + 4.0 + 1.0 = 7.0 >= 6.0 -> No shortage
        chk_after = check_confirmation_materials(
            work_order=wo_doc.name,
            operation="",
            yield_qty=2.0,
        )
        self.assertFalse(chk_after["has_shortage"])
        self.assertEqual(len(chk_after["shortages"]), 0)

    def test_check_confirmation_materials_partial_milestone_after_prior_production(
        self,
    ):
        """Partial milestone confirmation checks detect preceding-operation shortages even when
        yield_qty <= prior completed_qty or Work Order Operation.completed_qty is artificially inflated.
        """
        orig_disable_capacity_planning = frappe.db.get_single_value(
            "Manufacturing Settings", "disable_capacity_planning"
        )
        orig_make_batch_from_wo = frappe.db.get_single_value(
            "Manufacturing Settings", "make_serial_no_batch_from_work_order"
        )
        self.addCleanup(
            frappe.db.set_single_value,
            "Manufacturing Settings",
            {
                "disable_capacity_planning": orig_disable_capacity_planning,
                "make_serial_no_batch_from_work_order": orig_make_batch_from_wo,
            },
        )
        frappe.db.set_single_value(
            "Manufacturing Settings",
            {
                "disable_capacity_planning": 1,
                "make_serial_no_batch_from_work_order": 0,
            },
        )

        op_10 = "0010 Kesim"
        op_20 = "0020 Krimp"
        op_30 = "0030 Test"
        for op in (op_10, op_20, op_30):
            if not frappe.db.exists("Operation", op):
                frappe.get_doc(
                    {"doctype": "Operation", "name": op, "workstation": self.ws_name}
                ).insert(ignore_permissions=True)

        fg_item, _, _, _, fg_wh = self._setup_api_bom_and_warehouses()
        rm_item, line_wh, prod_source_wh, rm_stores_wh = (
            self._setup_staging_warehouses_and_rm(
                line_qty=100.0,
                prod_source_qty=1000.0,
                rm_stores_qty=2000.0,
            )
        )

        wo_doc = frappe.get_doc(
            {
                "doctype": "Work Order",
                "production_item": fg_item,
                "qty": 1800.0,
                "company": self.company,
                "source_warehouse": line_wh,
                "wip_warehouse": line_wh,
                "fg_warehouse": fg_wh,
                "skip_transfer": 1,
                "transfer_material_against": "Work Order",
                "planned_start_date": now_datetime(),
                "operations": [
                    {
                        "operation": op_10,
                        "workstation": self.ws_name,
                        "sequence_id": 1,
                        "completed_qty": 990.0,
                        "time_in_mins": 10.0,
                    },
                    {
                        "operation": op_20,
                        "workstation": self.ws_name,
                        "sequence_id": 2,
                        "completed_qty": 990.0,
                        "time_in_mins": 10.0,
                    },
                    {
                        "operation": op_30,
                        "workstation": self.ws_name,
                        "sequence_id": 3,
                        "completed_qty": 990.0,
                        "time_in_mins": 10.0,
                    },
                ],
            }
        )
        wo_doc.flags.ignore_permissions = True
        wo_doc.flags.ignore_mandatory = True
        wo_doc.insert(ignore_permissions=True)
        wo_doc.required_items = []
        wo_doc.append(
            "required_items",
            {
                "item_code": rm_item,
                "operation": op_10,
                "required_qty": 1800.0,
                "consumed_qty": 990.0,
                "source_warehouse": line_wh,
            },
        )
        wo_doc.save(ignore_permissions=True)
        wo_doc.submit()

        # Ensure exact consumed_qty and completed_qty on WO child rows after submit
        frappe.db.set_value(
            "Work Order Item",
            wo_doc.required_items[0].name,
            "consumed_qty",
            990.0,
        )
        for op_row in wo_doc.operations:
            frappe.db.set_value(
                "Work Order Operation",
                op_row.name,
                "completed_qty",
                990.0,
            )

        # Record prior 990 units of production via approved KTA Production Confirmation records
        for op in (op_10, op_20, op_30):
            conf = frappe.get_doc(
                {
                    "doctype": "KTA Production Confirmation",
                    "work_order": wo_doc.name,
                    "operation": op,
                    "yield_qty": 990.0,
                    "is_final_confirmation": 0,
                }
            )
            conf.flags.ignore_permissions = True
            conf.flags.ignore_links = True
            conf.insert(ignore_permissions=True)
            conf.submit()

        # 1. Partial confirmation 330.0 (<= 990.0) on milestone 0030 Test
        chk_330 = check_confirmation_materials(
            work_order=wo_doc.name,
            operation=op_30,
            yield_qty=330.0,
            is_final_confirmation=0,
        )
        self.assertTrue(chk_330["has_shortage"])
        self.assertEqual(len(chk_330["shortages"]), 1)
        shortage_330 = chk_330["shortages"][0]
        self.assertEqual(shortage_330["item_code"], rm_item)
        self.assertEqual(flt(shortage_330["required_qty"]), 330.0)
        self.assertEqual(flt(shortage_330["line_actual_qty"]), 100.0)
        self.assertEqual(flt(shortage_330["shortage_qty"]), 230.0)
        self.assertEqual(shortage_330["target_warehouse"], line_wh)
        self.assertEqual(shortage_330["source_warehouse"], prod_source_wh)
        self.assertNotIn(
            rm_stores_wh, [s["warehouse"] for s in shortage_330["available_sources"]]
        )

        # 2. Partial confirmation 810.0 (<= 990.0) on milestone 0030 Test
        chk_810 = check_confirmation_materials(
            work_order=wo_doc.name,
            operation=op_30,
            yield_qty=810.0,
            is_final_confirmation=0,
        )
        self.assertTrue(chk_810["has_shortage"])
        self.assertEqual(len(chk_810["shortages"]), 1)
        shortage_810 = chk_810["shortages"][0]
        self.assertEqual(shortage_810["item_code"], rm_item)
        self.assertEqual(flt(shortage_810["required_qty"]), 810.0)
        self.assertEqual(flt(shortage_810["line_actual_qty"]), 100.0)
        self.assertEqual(flt(shortage_810["shortage_qty"]), 710.0)
        self.assertEqual(shortage_810["target_warehouse"], line_wh)
        self.assertEqual(shortage_810["source_warehouse"], prod_source_wh)
        self.assertNotIn(
            rm_stores_wh, [s["warehouse"] for s in shortage_810["available_sources"]]
        )

        # 3. Even if Work Order Operation.completed_qty is artificially 1800.0 (stale/legacy mismatch),
        # ConfirmationService.get_operation_quantities still reads 990.0 and detects the 330.0 shortage.
        for op_row in wo_doc.operations:
            frappe.db.set_value(
                "Work Order Operation",
                op_row.name,
                "completed_qty",
                1800.0,
            )

        chk_stale = check_confirmation_materials(
            work_order=wo_doc.name,
            operation=op_30,
            yield_qty=330.0,
            is_final_confirmation=0,
        )
        self.assertTrue(chk_stale["has_shortage"])
        self.assertEqual(len(chk_stale["shortages"]), 1)
        shortage_stale = chk_stale["shortages"][0]
        self.assertEqual(flt(shortage_stale["required_qty"]), 330.0)
        self.assertEqual(flt(shortage_stale["line_actual_qty"]), 100.0)
        self.assertEqual(flt(shortage_stale["shortage_qty"]), 230.0)
        self.assertEqual(shortage_stale["target_warehouse"], line_wh)
        self.assertEqual(shortage_stale["source_warehouse"], prod_source_wh)

    def test_check_confirmation_materials_uses_usable_batch_qty_over_inflated_bin(
        self,
    ):
        """Batch-tracked RM shortage checks use get_available_batches() consumable qty instead
        of an inflated Bin.actual_qty, so staging transfers the full deficit.
        """
        orig_disable_capacity_planning = frappe.db.get_single_value(
            "Manufacturing Settings", "disable_capacity_planning"
        )
        orig_make_batch_from_wo = frappe.db.get_single_value(
            "Manufacturing Settings", "make_serial_no_batch_from_work_order"
        )
        orig_auto_bundle_outward = frappe.db.get_single_value(
            "Stock Settings", "auto_create_serial_and_batch_bundle_for_outward"
        )
        self.addCleanup(
            frappe.db.set_single_value,
            "Manufacturing Settings",
            {
                "disable_capacity_planning": orig_disable_capacity_planning,
                "make_serial_no_batch_from_work_order": orig_make_batch_from_wo,
            },
        )
        self.addCleanup(
            frappe.db.set_single_value,
            "Stock Settings",
            "auto_create_serial_and_batch_bundle_for_outward",
            orig_auto_bundle_outward,
        )
        frappe.db.set_single_value(
            "Manufacturing Settings",
            {
                "disable_capacity_planning": 1,
                "make_serial_no_batch_from_work_order": 0,
            },
        )
        frappe.db.set_single_value(
            "Stock Settings",
            "auto_create_serial_and_batch_bundle_for_outward",
            1,
        )

        fg_item, _, _, _, fg_wh = self._setup_api_bom_and_warehouses()
        rm_item, wh_line, wh_prod_src, _ = self._setup_staging_warehouses_and_rm(
            line_qty=40.0,
            prod_source_qty=200.0,
            rm_stores_qty=0.0,
            has_batch_no=1,
            create_new_batch=1,
        )

        bom = frappe.get_doc(
            {
                "doctype": "BOM",
                "item": fg_item,
                "company": self.company,
                "quantity": 1.0,
                "is_active": 1,
                "is_default": 0,
                "with_operations": 0,
                "currency": "TRY",
                "conversion_rate": 1.0,
                "items": [
                    {
                        "item_code": rm_item,
                        "qty": 1.0,
                        "uom": "Nos",
                        "rate": 10.0,
                        "source_warehouse": wh_line,
                    }
                ],
            }
        )
        bom.flags.ignore_permissions = True
        bom.insert(ignore_permissions=True)
        bom.submit()

        wo_doc = frappe.get_doc(
            {
                "doctype": "Work Order",
                "production_item": fg_item,
                "bom_no": bom.name,
                "qty": 100.0,
                "company": self.company,
                "source_warehouse": wh_line,
                "wip_warehouse": wh_line,
                "fg_warehouse": fg_wh,
                "skip_transfer": 1,
                "transfer_material_against": "Work Order",
            }
        )
        wo_doc.flags.ignore_permissions = True
        wo_doc.flags.ignore_mandatory = True
        wo_doc.set_required_items()
        for row in wo_doc.required_items:
            row.source_warehouse = wh_line
        wo_doc.insert(ignore_permissions=True)
        wo_doc.submit()

        # Simulate Bin-vs-Batch discrepancy where Bin.actual_qty (70.0) exceeds usable batch qty (40.0)
        frappe.db.set_value(
            "Bin",
            {"item_code": rm_item, "warehouse": wh_line},
            "actual_qty",
            70.0,
        )

        chk = check_confirmation_materials(
            work_order=wo_doc.name,
            operation="",
            yield_qty=100.0,
        )
        self.assertIs(chk["has_shortage"], True)
        self.assertEqual(len(chk["shortages"]), 1)
        shortage = chk["shortages"][0]
        self.assertEqual(shortage["item_code"], rm_item)
        self.assertEqual(flt(shortage["required_qty"]), 100.0)
        self.assertEqual(flt(shortage["line_actual_qty"]), 40.0)
        self.assertEqual(flt(shortage["shortage_qty"]), 60.0)
        self.assertEqual(shortage["target_warehouse"], wh_line)
        self.assertEqual(shortage["source_warehouse"], wh_prod_src)
        self.assertEqual(flt(shortage["source_available_qty"]), 200.0)

        stage_res = stage_confirmation_materials(
            wo_doc.name,
            [
                {
                    "item_code": rm_item,
                    "qty": 60.0,
                    "source_warehouse": wh_prod_src,
                    "target_warehouse": wh_line,
                }
            ],
        )
        self.assertIs(stage_res["success"], True)

        chk_after = check_confirmation_materials(
            work_order=wo_doc.name,
            operation="",
            yield_qty=100.0,
        )
        self.assertIs(chk_after["has_shortage"], False)
