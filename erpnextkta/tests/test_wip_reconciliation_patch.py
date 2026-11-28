import frappe
from erpnext.manufacturing.doctype.work_order.work_order import (
    make_stock_entry as make_stock_entry_from_wo,
)
from frappe.utils import flt

from erpnextkta.kta_shopfloor.report.kta_wip_valuation_report.kta_wip_valuation_report import (
    execute as execute_wip_report,
)
from erpnextkta.overrides.company_wip_validation import (
    ensure_journal_entry_work_order_field,
)
from erpnextkta.patches.v4_6.backfill_shopfloor_wip_account import (
    ensure_company_wip_field,
)
from erpnextkta.patches.v4_6.reconcile_shopfloor_wip_discrepancies import (
    DRIFT_TAG,
    SCRAP_TAG,
    reconcile_shopfloor_wip_discrepancies,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_erpnext_operation,
    create_test_item_group,
    create_test_workstation,
    setup_test_fiscal_years,
)

RECON_TEST_COMPANY = "_Test WIP Recon Co"
RECON_TEST_ABBR = "TWRC"


class TestWIPReconciliationPatch(KTABaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        if not frappe.db.has_column("Company", "custom_wip_consumption_account"):
            ensure_company_wip_field()
        if not frappe.db.has_column("Journal Entry Account", "custom_work_order"):
            ensure_journal_entry_work_order_field()

        cls._ensure_recon_company()
        frappe.db.commit()

    @classmethod
    def _ensure_recon_company(cls):
        """Create isolated perpetual-inventory company for reconciliation patch tests."""
        if not frappe.db.exists("Company", RECON_TEST_COMPANY):
            frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": RECON_TEST_COMPANY,
                    "abbr": RECON_TEST_ABBR,
                    "default_currency": "TRY",
                    "country": "Turkey",
                    "create_chart_of_accounts_based_on": "Standard Template",
                    "chart_of_accounts": "Standard",
                }
            ).insert(ignore_permissions=True)

        setup_test_fiscal_years(RECON_TEST_COMPANY)

        cls.cost_center = cls._ensure_cost_center()
        assets_root = cls._ensure_root_account("Application of Funds (Assets)", "Asset")
        expenses_root = cls._ensure_root_account("Expenses", "Expense")

        cls.rm_stock_account = cls._ensure_account(
            "150 - Hammadde Stok",
            parent_account=assets_root,
            root_type="Asset",
            account_type="Stock",
            is_group=0,
            account_number="150",
        )
        cls.fg_stock_account = cls._ensure_account(
            "152 - Mamul Stok",
            parent_account=assets_root,
            root_type="Asset",
            account_type="Stock",
            is_group=0,
            account_number="152",
        )
        cls.wip_group_account = cls._ensure_account(
            "Yari Mamuller",
            parent_account=assets_root,
            root_type="Asset",
            account_type="",
            is_group=1,
            account_number="151.01",
        )
        cls.wip_consumption_account = cls._ensure_account(
            "ÜRETİM SÜRECİNDEKİ TÜKETİMLER (WIP)",
            parent_account=cls.wip_group_account,
            root_type="Asset",
            account_type="",
            is_group=0,
            account_number="151.01.002",
        )
        cls.stock_adj_account = cls._ensure_account(
            "Envanter Duzeltme",
            parent_account=expenses_root,
            root_type="Expense",
            account_type="Stock Adjustment",
            is_group=0,
            account_number="710.20",
        )
        cls.scrap_710_account = cls._ensure_account(
            "Uretim Fire ve Hurda Giderleri",
            parent_account=expenses_root,
            root_type="Expense",
            account_type="Expense Account",
            is_group=0,
            account_number="710.001",
        )

        frappe.db.set_value(
            "Company",
            RECON_TEST_COMPANY,
            {
                "enable_perpetual_inventory": 1,
                "default_inventory_account": cls.rm_stock_account,
                "stock_adjustment_account": cls.stock_adj_account,
                "cost_center": cls.cost_center,
                "custom_wip_consumption_account": cls.wip_consumption_account,
            },
        )

        cls.rm_warehouse = cls._ensure_warehouse("_Test Recon RM", cls.rm_stock_account)
        cls.wip_warehouse = cls._ensure_warehouse(
            "_Test Recon Floor", cls.rm_stock_account
        )
        cls.fg_warehouse = cls._ensure_warehouse("_Test Recon FG", cls.fg_stock_account)

    @classmethod
    def _ensure_cost_center(cls) -> str:
        cc_name = f"Main - {RECON_TEST_ABBR}"
        if frappe.db.exists("Cost Center", cc_name):
            return cc_name
        root_cc = frappe.db.get_value(
            "Cost Center",
            {"company": RECON_TEST_COMPANY, "is_group": 1},
            "name",
        )
        if not root_cc:
            root_doc = frappe.get_doc(
                {
                    "doctype": "Cost Center",
                    "cost_center_name": RECON_TEST_COMPANY,
                    "company": RECON_TEST_COMPANY,
                    "is_group": 1,
                }
            )
            root_doc.insert(ignore_permissions=True)
            root_cc = root_doc.name
        cc_doc = frappe.get_doc(
            {
                "doctype": "Cost Center",
                "cost_center_name": "Main",
                "company": RECON_TEST_COMPANY,
                "parent_cost_center": root_cc,
                "is_group": 0,
            }
        )
        cc_doc.insert(ignore_permissions=True)
        return cc_doc.name

    @classmethod
    def _ensure_root_account(cls, fallback_name: str, root_type: str) -> str:
        fullname = f"{fallback_name} - {RECON_TEST_ABBR}"
        if frappe.db.exists("Account", fullname):
            return fullname

        rows = frappe.db.sql(
            """
            SELECT name
            FROM `tabAccount`
            WHERE company = %s
              AND root_type = %s
              AND is_group = 1
              AND IFNULL(parent_account, '') = ''
            LIMIT 1
            """,
            (RECON_TEST_COMPANY, root_type),
            pluck=True,
        )
        if rows:
            return rows[0]

        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": RECON_TEST_COMPANY,
                "account_name": fallback_name,
                "root_type": root_type,
                "report_type": (
                    "Balance Sheet"
                    if root_type in ("Asset", "Liability", "Equity")
                    else "Profit and Loss"
                ),
                "is_group": 1,
                "account_currency": "TRY",
            }
        )
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc.name

    @classmethod
    def _ensure_account(
        cls,
        account_name: str,
        parent_account: str,
        root_type: str,
        account_type: str,
        is_group: int,
        account_number: str,
    ) -> str:
        existing = frappe.db.get_value(
            "Account",
            {"company": RECON_TEST_COMPANY, "account_number": account_number},
            "name",
        )
        if existing:
            return existing
        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": RECON_TEST_COMPANY,
                "account_name": account_name,
                "account_number": account_number,
                "parent_account": parent_account,
                "root_type": root_type,
                "account_type": account_type,
                "is_group": is_group,
                "account_currency": "TRY",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    @classmethod
    def _ensure_warehouse(cls, warehouse_name: str, account: str) -> str:
        fullname = f"{warehouse_name} - {RECON_TEST_ABBR}"
        if not frappe.db.exists("Warehouse", fullname):
            doc = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": warehouse_name,
                    "company": RECON_TEST_COMPANY,
                    "account": account,
                }
            )
            doc.insert(ignore_permissions=True)
            return doc.name
        frappe.db.set_value("Warehouse", fullname, "account", account)
        return fullname

    def setUp(self):
        super().setUp()
        self.company = RECON_TEST_COMPANY
        self._tag = frappe.generate_hash(length=6)
        self.item_group = create_test_item_group()
        self.workstation = create_test_workstation("_Test Recon Workstation")
        frappe.db.set_value("Workstation", self.workstation, "hour_rate", 0.0)
        self.op_10 = create_test_erpnext_operation(
            "_Test Recon Op 10", self.workstation
        )
        self.op_30 = create_test_erpnext_operation(
            "_Test Recon Op 30", self.workstation
        )

        frappe.db.set_single_value(
            "Manufacturing Settings",
            {
                "material_consumption": 1,
                "get_rm_cost_from_consumption_entry": 1,
                "disable_capacity_planning": 1,
                "make_serial_no_batch_from_work_order": 0,
            },
        )
        frappe.db.set_value(
            "Company",
            self.company,
            "custom_wip_consumption_account",
            self.wip_consumption_account,
        )

    def _make_item(self, suffix: str, has_batch_no: int = 0) -> str:
        code = f"_Test Recon {suffix} {self._tag}"
        doc = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": code,
                "item_name": code,
                "item_group": self.item_group,
                "is_stock_item": 1,
                "stock_uom": "Nos",
                "has_batch_no": has_batch_no,
                "has_serial_no": 0,
                "valuation_method": "Moving Average",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _make_batch(self, item_code: str, suffix: str) -> str:
        batch_id = f"_Test-Batch-{suffix}-{self._tag}"
        doc = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": batch_id,
                "item": item_code,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _receive_rm(
        self,
        item_code: str,
        qty: float,
        rate: float,
        posting_date: str = "2026-11-24",
        batch_no: str | None = None,
    ):
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = "Material Receipt"
        se.company = self.company
        se.posting_date = posting_date
        se.set_posting_time = 1
        se.to_warehouse = self.rm_warehouse
        row = {
            "item_code": item_code,
            "qty": qty,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "t_warehouse": self.rm_warehouse,
            "basic_rate": rate,
            "cost_center": self.cost_center,
            "expense_account": self.stock_adj_account,
        }
        if batch_no:
            row["use_serial_batch_fields"] = 1
            row["batch_no"] = batch_no
        se.append("items", row)
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_bom(self, fg_item: str, rm_item: str, rate: float, operations=None):
        ops = operations or [self.op_10]
        bom = frappe.new_doc("BOM")
        bom.item = fg_item
        bom.quantity = 1.0
        bom.company = self.company
        bom.currency = "TRY"
        bom.conversion_rate = 1.0
        bom.rm_cost_as_per = "Valuation Rate"
        bom.with_operations = 1
        bom.inspection_required = 0
        for op in ops:
            bom.append(
                "operations",
                {
                    "operation": op,
                    "workstation": self.workstation,
                    "time_in_mins": 10,
                    "hour_rate": 0.0,
                },
            )
        bom.append(
            "items",
            {
                "item_code": rm_item,
                "qty": 1.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "rate": rate,
                "operation": ops[0],
                "source_warehouse": self.rm_warehouse,
            },
        )
        bom.insert(ignore_permissions=True)
        bom.submit()
        return bom

    def _create_work_order(self, fg_item: str, bom_no: str, qty: float):
        wo = frappe.new_doc("Work Order")
        wo.production_item = fg_item
        wo.bom_no = bom_no
        wo.qty = qty
        wo.company = self.company
        wo.source_warehouse = self.rm_warehouse
        wo.wip_warehouse = self.wip_warehouse
        wo.fg_warehouse = self.fg_warehouse
        wo.use_multi_level_bom = 0
        wo.skip_transfer = 1
        wo.set_work_order_operations()
        wo.set_required_items()
        for row in wo.required_items:
            row.source_warehouse = self.rm_warehouse
        wo.insert(ignore_permissions=True)
        wo.submit()
        return wo

    def _set_op_completed(self, wo, qty_or_map):
        for op_row in wo.operations:
            qty = (
                qty_or_map.get(op_row.operation, 0.0)
                if isinstance(qty_or_map, dict)
                else qty_or_map
            )
            frappe.db.set_value(
                "Work Order Operation", op_row.name, "completed_qty", qty
            )

    def _submit_consumption(
        self,
        wo,
        rm_item: str,
        qty: float,
        posting_date: str = "2026-11-25",
        batch_no: str | None = None,
    ):
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Consumption for Manufacture"
        se.stock_entry_type = "Material Consumption for Manufacture"
        se.work_order = wo.name
        se.company = self.company
        se.posting_date = posting_date
        se.set_posting_time = 1
        se.from_bom = 1
        se.bom_no = wo.bom_no
        se.use_multi_level_bom = wo.use_multi_level_bom
        se.fg_completed_qty = qty
        se.from_warehouse = self.rm_warehouse
        row = {
            "item_code": rm_item,
            "qty": qty,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "s_warehouse": self.rm_warehouse,
            "t_warehouse": "",
            "cost_center": self.cost_center,
        }
        if batch_no:
            row["use_serial_batch_fields"] = 1
            row["batch_no"] = batch_no
        se.append("items", row)
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _submit_fg_only_manufacture(
        self, wo, qty: float, posting_date: str = "2026-11-26", is_final: bool = False
    ):
        se_dict = make_stock_entry_from_wo(wo.name, "Manufacture", qty)
        se = frappe.get_doc(se_dict)
        se.posting_date = posting_date
        se.set_posting_time = 1
        for d in se.items:
            d.cost_center = self.cost_center
        if is_final:
            se.flags.kta_is_final_confirmation = True
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _simulate_sle_drift_after_fg(
        self, cons_name: str, old_val: float, new_sle_val: float
    ):
        """Simulate a consumption SLE+GL repost divergence without changing SED valuation_rate."""
        frappe.db.sql(
            """
            UPDATE `tabStock Ledger Entry`
            SET stock_value_difference = %s
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND is_cancelled = 0
            """,
            (-abs(new_sle_val), cons_name),
        )
        frappe.db.sql(
            """
            UPDATE `tabGL Entry`
            SET debit = %s,
                debit_in_account_currency = %s
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND account = %s
              AND is_cancelled = 0
            """,
            (new_sle_val, new_sle_val, cons_name, self.wip_consumption_account),
        )
        frappe.db.sql(
            """
            UPDATE `tabGL Entry`
            SET credit = %s,
                credit_in_account_currency = %s
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND account = %s
              AND is_cancelled = 0
            """,
            (new_sle_val, new_sle_val, cons_name, self.rm_stock_account),
        )

    def _report_rows_by_wo(self, as_of_date: str) -> dict[str, dict]:
        _, data, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": as_of_date,
                "only_open_wip": 0,
                "show_consumption_details": 0,
            }
        )
        return {r["work_order"]: r for r in data if r.get("indent") == 0}

    def test_step1_drift_reconciliation_dry_run_apply_idempotency_and_in_process_follow_up(
        self,
    ):
        """Step 1 clears SLE-vs-SED drift on Completed, Closed, and negative-WIP In Process WOs while leaving positive In Process WO untouched."""
        as_of = "2026-11-28"
        fg = self._make_item("FG-DRIFT")
        rm = self._make_item("RM-DRIFT")
        self._receive_rm(rm, 200.0, 10.0, posting_date="2026-11-23")
        bom = self._create_bom(fg, rm, 10.0)

        # 1. Completed WO with negative SLE-vs-SED drift (-15.0)
        wo_comp = self._create_work_order(fg, bom.name, 10.0)
        self._set_op_completed(wo_comp, 10.0)
        cons_comp = self._submit_consumption(wo_comp, rm, 10.0)
        self._submit_fg_only_manufacture(wo_comp, 10.0, is_final=True)
        self._simulate_sle_drift_after_fg(cons_comp.name, 100.0, 85.0)
        self.assertEqual(
            frappe.db.get_value("Work Order", wo_comp.name, "status"), "Completed"
        )

        # 2. Closed WO with small negative SLE-vs-SED drift (-8.0)
        wo_closed = self._create_work_order(fg, bom.name, 10.0)
        self._set_op_completed(wo_closed, 8.0)
        cons_closed = self._submit_consumption(wo_closed, rm, 8.0)
        self._submit_fg_only_manufacture(wo_closed, 8.0, is_final=True)
        self._simulate_sle_drift_after_fg(cons_closed.name, 80.0, 72.0)
        frappe.get_doc("Work Order", wo_closed.name).update_status("Closed")
        self.assertEqual(
            frappe.db.get_value("Work Order", wo_closed.name, "status"), "Closed"
        )

        # 3. In Process WO with negative WIP drift (-10.0) and remaining 5 units to produce
        wo_inproc_drift = self._create_work_order(fg, bom.name, 10.0)
        self._set_op_completed(wo_inproc_drift, 5.0)
        cons_inproc_1 = self._submit_consumption(wo_inproc_drift, rm, 5.0)
        self._submit_fg_only_manufacture(wo_inproc_drift, 5.0, is_final=False)
        self._simulate_sle_drift_after_fg(cons_inproc_1.name, 50.0, 40.0)
        self.assertEqual(
            frappe.db.get_value("Work Order", wo_inproc_drift.name, "status"),
            "In Process",
        )

        # 4. In Process WO with normal positive WIP (+50.0) - must NOT be touched
        wo_inproc_normal = self._create_work_order(fg, bom.name, 10.0)
        self._set_op_completed(wo_inproc_normal, 7.0)
        self._submit_consumption(wo_inproc_normal, rm, 7.0)
        self._submit_fg_only_manufacture(wo_inproc_normal, 2.0, is_final=False)
        self.assertEqual(
            frappe.db.get_value("Work Order", wo_inproc_normal.name, "status"),
            "In Process",
        )

        # Dry-run creates zero Journal Entries
        dry_res = reconcile_shopfloor_wip_discrepancies(
            company=self.company, dry_run=True, as_of_date=as_of
        )
        comp_dry = dry_res["companies"][self.company]["step1"]
        self.assertTrue(comp_dry["would_create"])
        self.assertIsNone(comp_dry["journal_entry"])
        self.assertEqual(
            set(comp_dry["work_orders"]),
            {wo_comp.name, wo_closed.name, wo_inproc_drift.name},
        )
        self.assertEqual(
            frappe.db.count(
                "Journal Entry",
                {"company": self.company, "user_remark": ["like", f"%{DRIFT_TAG}%"]},
            ),
            0,
        )

        # Apply creates 1 JE and zeroes all 3 drift WOs while preserving positive In Process WO
        apply_res = reconcile_shopfloor_wip_discrepancies(
            company=self.company, dry_run=False, as_of_date=as_of
        )
        self.assertEqual(apply_res["step1_journal_entries"], 1)
        self.assertEqual(apply_res["step2_journal_entries"], 0)
        je_name = apply_res["companies"][self.company]["step1"]["journal_entry"]
        self.assertTrue(je_name)

        report_map = self._report_rows_by_wo(as_of)
        self.assertEqual(flt(report_map[wo_comp.name]["wip_balance"], 2), 0.0)
        self.assertEqual(flt(report_map[wo_closed.name]["wip_balance"], 2), 0.0)
        self.assertEqual(flt(report_map[wo_inproc_drift.name]["wip_balance"], 2), 0.0)
        self.assertEqual(flt(report_map[wo_inproc_normal.name]["wip_balance"], 2), 50.0)

        # Follow-up consumption + final FG Manufacture on wo_inproc_drift closes WIP to 0.00
        self._set_op_completed(wo_inproc_drift, 10.0)
        self._submit_consumption(wo_inproc_drift, rm, 5.0, posting_date="2026-11-28")
        mfg_final = self._submit_fg_only_manufacture(
            wo_inproc_drift, 5.0, posting_date="2026-11-28", is_final=True
        )
        fg_row = next(d for d in mfg_final.items if d.is_finished_item)
        self.assertAlmostEqual(flt(fg_row.basic_amount), 50.0, places=2)

        report_after_followup = self._report_rows_by_wo(as_of)
        self.assertEqual(
            flt(report_after_followup[wo_inproc_drift.name]["wip_balance"], 2), 0.0
        )

        # Idempotent second run creates nothing
        second_res = reconcile_shopfloor_wip_discrepancies(
            company=self.company, dry_run=False, as_of_date=as_of
        )
        self.assertEqual(second_res["step1_journal_entries"], 0)
        self.assertEqual(second_res["step2_journal_entries"], 0)

    def test_step2_closed_wo_scrap_writeoff_dry_run_apply_and_idempotency(
        self,
    ):
        """Step 2 writes off excess WIP on Closed WO to 710.001 without altering warehouse stock."""
        as_of = "2026-11-28"
        fg = self._make_item("FG-SCRAP-WO")
        rm = self._make_item("RM-SCRAP-WO", has_batch_no=1)
        orig_batch = self._make_batch(rm, "SCRAP")

        self._receive_rm(rm, 10.0, 20.0, posting_date="2026-11-23", batch_no=orig_batch)
        bom = self._create_bom(fg, rm, 20.0, operations=[self.op_10, self.op_30])
        wo = self._create_work_order(fg, bom.name, 10.0)

        # OP10 consumes 10 units (200.0), OP30 produces 8 FG units (160.0), then WO is Closed
        self._set_op_completed(wo, {self.op_10: 10.0, self.op_30: 8.0})
        self._submit_consumption(
            wo, rm, 10.0, posting_date="2026-11-25", batch_no=orig_batch
        )
        self._submit_fg_only_manufacture(
            wo, 8.0, posting_date="2026-11-26", is_final=False
        )
        frappe.get_doc("Work Order", wo.name).update_status("Closed")
        self.assertEqual(frappe.db.get_value("Work Order", wo.name, "status"), "Closed")

        rm_qty_before = flt(
            frappe.db.get_value(
                "Bin",
                {"item_code": rm, "warehouse": self.rm_warehouse},
                "actual_qty",
            )
        )
        self.assertAlmostEqual(rm_qty_before, 0.0, places=4)

        # Dry-run creates zero Journal Entries and previews exact scrap write-off
        dry_res = reconcile_shopfloor_wip_discrepancies(
            company=self.company, dry_run=True, as_of_date=as_of
        )
        comp_dry = dry_res["companies"][self.company]["step2"]
        self.assertTrue(comp_dry["would_create"])
        self.assertIsNone(comp_dry["journal_entry"])
        self.assertEqual(comp_dry["scrap_account"], self.scrap_710_account)
        self.assertEqual(comp_dry["work_orders"], [wo.name])
        self.assertAlmostEqual(flt(comp_dry["net_amount"]), 40.0, places=2)
        self.assertEqual(
            frappe.db.count(
                "Journal Entry",
                {"company": self.company, "user_remark": ["like", f"%{SCRAP_TAG}%"]},
            ),
            0,
        )

        # Apply creates 1 scrap write-off JE (710.001 Dr / 151.01.002 Cr) and 0 Stock Entries
        apply_res = reconcile_shopfloor_wip_discrepancies(
            company=self.company, dry_run=False, as_of_date=as_of
        )
        self.assertEqual(apply_res["step1_journal_entries"], 0, msg=str(apply_res))
        self.assertEqual(apply_res["step2_journal_entries"], 1, msg=str(apply_res))

        je_name = apply_res["companies"][self.company]["step2"]["journal_entry"]
        self.assertTrue(je_name)
        je_doc = frappe.get_doc("Journal Entry", je_name)
        self.assertEqual(je_doc.docstatus, 1)
        self.assertEqual(len(je_doc.accounts), 2)

        wip_row = next(
            r for r in je_doc.accounts if r.account == self.wip_consumption_account
        )
        scrap_row = next(
            r for r in je_doc.accounts if r.account == self.scrap_710_account
        )
        self.assertEqual(wip_row.custom_work_order, wo.name)
        self.assertAlmostEqual(flt(wip_row.credit_in_account_currency), 40.0, places=2)
        self.assertAlmostEqual(flt(wip_row.debit_in_account_currency), 0.0, places=2)
        self.assertIsNone(scrap_row.custom_work_order)
        self.assertAlmostEqual(flt(scrap_row.debit_in_account_currency), 40.0, places=2)
        self.assertAlmostEqual(flt(scrap_row.credit_in_account_currency), 0.0, places=2)

        # Zero Material Receipt Stock Entries created and warehouse stock unchanged
        self.assertEqual(
            frappe.db.count(
                "Stock Entry",
                {
                    "company": self.company,
                    "purpose": "Material Receipt",
                    "work_order": wo.name,
                },
            ),
            0,
        )
        rm_qty_after = flt(
            frappe.db.get_value(
                "Bin",
                {"item_code": rm, "warehouse": self.rm_warehouse},
                "actual_qty",
            )
        )
        self.assertAlmostEqual(rm_qty_after, rm_qty_before, places=4)
        self.assertEqual(frappe.db.get_value("Work Order", wo.name, "status"), "Closed")

        report_map = self._report_rows_by_wo(as_of)
        self.assertEqual(flt(report_map[wo.name]["wip_balance"], 2), 0.0)
        self.assertEqual(flt(report_map[wo.name]["wip_in_wip_account"], 2), 0.0)

        # Idempotent second run creates 0 new Journal Entries
        second_res = reconcile_shopfloor_wip_discrepancies(
            company=self.company, dry_run=False, as_of_date=as_of
        )
        self.assertEqual(second_res["step1_journal_entries"], 0)
        self.assertEqual(second_res["step2_journal_entries"], 0)
