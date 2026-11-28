# Copyright (c) 2026, KTA and Contributors
# See license.txt

import frappe
from erpnext.manufacturing.doctype.work_order.work_order import (
    make_stock_entry as make_stock_entry_from_wo,
)
from frappe.desk.query_report import run as run_query_report
from frappe.utils import flt, getdate

from erpnextkta.kta_shopfloor.report.kta_wip_valuation_report.kta_wip_valuation_report import (
    execute as execute_wip_report,
)
from erpnextkta.kta_shopfloor.services.backflush_service import (
    create_consumption_entry,
    create_finished_goods_entry,
)
from erpnextkta.overrides.company_wip_validation import (
    ensure_journal_entry_work_order_field,
)
from erpnextkta.patches.v4_6.backfill_shopfloor_wip_account import (
    ensure_company_wip_field,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_erpnext_operation,
    create_test_item_group,
    create_test_workstation,
    setup_test_fiscal_years,
)

REPORT_TEST_COMPANY = "_Test WIP Report Co"
REPORT_TEST_ABBR = "TWIPR"


class TestWIPValuationReport(KTABaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        if not frappe.db.has_column("Company", "custom_wip_consumption_account"):
            ensure_company_wip_field()
        if not frappe.db.has_column("Journal Entry Account", "custom_work_order"):
            ensure_journal_entry_work_order_field()
        cls._ensure_report_test_company()
        frappe.db.commit()

    @classmethod
    def _ensure_report_test_company(cls):
        """Create an isolated perpetual-inventory company with 150/151/152/710.20 accounts."""
        if not frappe.db.exists("Company", REPORT_TEST_COMPANY):
            frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": REPORT_TEST_COMPANY,
                    "abbr": REPORT_TEST_ABBR,
                    "default_currency": "TRY",
                    "country": "Turkey",
                    "create_chart_of_accounts_based_on": "Standard Template",
                    "chart_of_accounts": "Standard",
                }
            ).insert(ignore_permissions=True)

        setup_test_fiscal_years(REPORT_TEST_COMPANY)

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

        frappe.db.set_value(
            "Company",
            REPORT_TEST_COMPANY,
            {
                "enable_perpetual_inventory": 1,
                "default_inventory_account": cls.rm_stock_account,
                "stock_adjustment_account": cls.stock_adj_account,
                "cost_center": cls.cost_center,
            },
        )

        cls.rm_warehouse = cls._ensure_warehouse(
            "_Test WIP Rep RM", cls.rm_stock_account
        )
        cls.wip_warehouse = cls._ensure_warehouse(
            "_Test WIP Rep Floor", cls.rm_stock_account
        )
        cls.fg_warehouse = cls._ensure_warehouse(
            "_Test WIP Rep FG", cls.fg_stock_account
        )

    @classmethod
    def _ensure_cost_center(cls) -> str:
        cc_name = f"Main - {REPORT_TEST_ABBR}"
        if frappe.db.exists("Cost Center", cc_name):
            return cc_name
        root_cc = frappe.db.get_value(
            "Cost Center",
            {"company": REPORT_TEST_COMPANY, "is_group": 1},
            "name",
        )
        if not root_cc:
            root_doc = frappe.get_doc(
                {
                    "doctype": "Cost Center",
                    "cost_center_name": REPORT_TEST_COMPANY,
                    "company": REPORT_TEST_COMPANY,
                    "is_group": 1,
                }
            )
            root_doc.insert(ignore_permissions=True)
            root_cc = root_doc.name
        cc_doc = frappe.get_doc(
            {
                "doctype": "Cost Center",
                "cost_center_name": "Main",
                "company": REPORT_TEST_COMPANY,
                "parent_cost_center": root_cc,
                "is_group": 0,
            }
        )
        cc_doc.insert(ignore_permissions=True)
        return cc_doc.name

    @classmethod
    def _ensure_root_account(cls, fallback_name: str, root_type: str) -> str:
        fullname = f"{fallback_name} - {REPORT_TEST_ABBR}"
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
            (REPORT_TEST_COMPANY, root_type),
            pluck=True,
        )
        if rows:
            return rows[0]

        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": REPORT_TEST_COMPANY,
                "account_name": fallback_name,
                "root_type": root_type,
                "report_type": "Balance Sheet"
                if root_type in ("Asset", "Liability", "Equity")
                else "Profit and Loss",
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
            {"company": REPORT_TEST_COMPANY, "account_number": account_number},
            "name",
        )
        if existing:
            return existing
        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": REPORT_TEST_COMPANY,
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
        fullname = f"{warehouse_name} - {REPORT_TEST_ABBR}"
        if not frappe.db.exists("Warehouse", fullname):
            doc = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": warehouse_name,
                    "company": REPORT_TEST_COMPANY,
                    "account": account,
                }
            )
            doc.insert(ignore_permissions=True)
            return doc.name
        frappe.db.set_value("Warehouse", fullname, "account", account)
        return fullname

    def setUp(self):
        super().setUp()
        self.company = REPORT_TEST_COMPANY
        self._cleanup_company_transactions()
        self._tag = frappe.generate_hash(length=6)
        self.item_group = create_test_item_group()
        self.workstation = create_test_workstation("_Test WIP Rep Workstation")
        frappe.db.set_value("Workstation", self.workstation, "hour_rate", 0.0)
        self.op_10 = create_test_erpnext_operation(
            "_Test WIP Rep Op 10", self.workstation
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

    def tearDown(self):
        self._cleanup_company_transactions()
        super().tearDown()

    def _cleanup_company_transactions(self):
        """Remove committed test transactions for the isolated test company."""
        for child_dt, parent_dt in (
            ("Stock Entry Detail", "Stock Entry"),
            ("Journal Entry Account", "Journal Entry"),
            ("Work Order Operation", "Work Order"),
            ("Work Order Item", "Work Order"),
            ("BOM Operation", "BOM"),
            ("BOM Item", "BOM"),
            ("Serial and Batch Entry", "Serial and Batch Bundle"),
        ):
            frappe.db.sql(
                f"""
                DELETE child FROM `tab{child_dt}` child
                INNER JOIN `tab{parent_dt}` parent ON parent.name = child.parent
                WHERE parent.company = %s
                """,
                (self.company,),
            )

        frappe.db.sql(
            """
            DELETE kpc FROM `tabKTA Production Confirmation` kpc
            INNER JOIN `tabWork Order` wo ON wo.name = kpc.work_order
            WHERE wo.company = %s
            """,
            (self.company,),
        )

        for dt in (
            "GL Entry",
            "Stock Ledger Entry",
            "Serial and Batch Bundle",
            "Stock Entry",
            "Journal Entry",
            "Job Card",
            "Work Order",
            "BOM",
        ):
            frappe.db.delete(dt, {"company": self.company})

        frappe.db.delete(
            "Bin",
            {
                "warehouse": [
                    "in",
                    [self.rm_warehouse, self.wip_warehouse, self.fg_warehouse],
                ]
            },
        )
        frappe.db.delete("Item Alternative", {"item_code": ["like", "_Test WIPR%"]})
        frappe.db.commit()

    def _make_item(self, suffix: str) -> str:
        code = f"_Test WIPR {suffix} {self._tag}"
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
                "valuation_method": "Moving Average",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _receive_rm(
        self, item_code: str, qty: float, rate: float, posting_date: str = "2026-11-15"
    ):
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = "Material Receipt"
        se.company = self.company
        se.posting_date = posting_date
        se.set_posting_time = 1
        se.to_warehouse = self.rm_warehouse
        se.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.rm_warehouse,
                "basic_rate": rate,
                "cost_center": self.cost_center,
                "expense_account": self.stock_adj_account,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_bom(self, fg_item: str, rm_item: str, rate: float):
        bom = frappe.new_doc("BOM")
        bom.item = fg_item
        bom.quantity = 1.0
        bom.company = self.company
        bom.currency = "TRY"
        bom.conversion_rate = 1.0
        bom.rm_cost_as_per = "Valuation Rate"
        bom.with_operations = 1
        bom.inspection_required = 0
        bom.append(
            "operations",
            {
                "operation": self.op_10,
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
                "operation": self.op_10,
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

    def _set_op_completed(self, wo, qty: float):
        for op_row in wo.operations:
            frappe.db.set_value(
                "Work Order Operation", op_row.name, "completed_qty", qty
            )
        wo.reload()

    def _submit_consumption(
        self, wo, rm_item: str, qty: float, posting_date: str = "2026-11-20"
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
        se.append(
            "items",
            {
                "item_code": rm_item,
                "qty": qty,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.rm_warehouse,
                "t_warehouse": "",
                "cost_center": self.cost_center,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _submit_fg_only_manufacture(
        self, wo, qty: float, posting_date: str = "2026-11-22", is_final: bool = False
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

    def test_as_of_date_cutoff(self):
        """Consumption on day 1 and FG on day 3 reflect accurately per as_of_date cutoff."""
        fg = self._make_item("FG-CUTOFF")
        rm = self._make_item("RM-CUTOFF")
        self._receive_rm(rm, 100.0, 25.0, posting_date="2026-11-15")
        bom = self._create_bom(fg, rm, 25.0)
        wo = self._create_work_order(fg, bom.name, 100.0)
        self._set_op_completed(wo, 100.0)

        self._submit_consumption(wo, rm, 100.0, posting_date="2026-11-20")
        self._submit_fg_only_manufacture(wo, 40.0, posting_date="2026-11-22")

        # Day 1 cutoff: only consumption visible
        _, rows_day1, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-20",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 0,
            }
        )
        self.assertEqual(len(rows_day1), 1)
        row_d1 = rows_day1[0]
        self.assertEqual(flt(row_d1["consumed_value"], 2), 2500.0)
        self.assertEqual(flt(row_d1["fg_transferred_value"], 2), 0.0)
        self.assertEqual(flt(row_d1["wip_balance"], 2), 2500.0)
        self.assertEqual(flt(row_d1["wip_in_wip_account"], 2), 2500.0)
        self.assertEqual(flt(row_d1["wip_in_adjustment_account"], 2), 0.0)
        self.assertEqual(getdate(row_d1["last_posting_date"]), getdate("2026-11-20"))

        # Day 3 cutoff: partial FG reduces WIP
        _, rows_day3, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-22",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 0,
            }
        )
        self.assertEqual(len(rows_day3), 1)
        row_d3 = rows_day3[0]
        self.assertEqual(flt(row_d3["consumed_value"], 2), 2500.0)
        self.assertEqual(flt(row_d3["fg_transferred_value"], 2), 1000.0)
        self.assertEqual(flt(row_d3["wip_balance"], 2), 1500.0)
        self.assertEqual(flt(row_d3["wip_in_wip_account"], 2), 1500.0)
        self.assertEqual(getdate(row_d3["last_posting_date"]), getdate("2026-11-22"))

    def test_only_open_wip_toggle(self):
        """only_open_wip=1 hides zeroed WOs while only_open_wip=0 includes them."""
        fg_open = self._make_item("FG-OPEN")
        rm_open = self._make_item("RM-OPEN")
        self._receive_rm(rm_open, 50.0, 20.0, posting_date="2026-11-15")
        bom_open = self._create_bom(fg_open, rm_open, 20.0)
        wo_open = self._create_work_order(fg_open, bom_open.name, 50.0)
        self._set_op_completed(wo_open, 50.0)
        self._submit_consumption(wo_open, rm_open, 50.0, posting_date="2026-11-20")
        self._submit_fg_only_manufacture(wo_open, 20.0, posting_date="2026-11-21")

        fg_closed = self._make_item("FG-CLOSED")
        rm_closed = self._make_item("RM-CLOSED")
        self._receive_rm(rm_closed, 25.0, 20.0, posting_date="2026-11-15")
        bom_closed = self._create_bom(fg_closed, rm_closed, 20.0)
        wo_closed = self._create_work_order(fg_closed, bom_closed.name, 25.0)
        self._set_op_completed(wo_closed, 25.0)
        self._submit_consumption(wo_closed, rm_closed, 25.0, posting_date="2026-11-20")
        self._submit_fg_only_manufacture(
            wo_closed, 25.0, posting_date="2026-11-21", is_final=True
        )

        # Open only (tree enabled: closed WO must have neither Level-0 nor child rows)
        _, open_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "only_open_wip": 1,
            }
        )
        open_wo_names = {r["work_order"] for r in open_rows if r["indent"] == 0}
        self.assertIn(wo_open.name, open_wo_names)
        self.assertNotIn(wo_closed.name, open_wo_names)
        self.assertTrue(all(r["work_order_ref"] != wo_closed.name for r in open_rows))

        # All WOs (including zeroed)
        _, all_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "only_open_wip": 0,
            }
        )
        by_wo = {r["work_order"]: r for r in all_rows if r["indent"] == 0}
        self.assertIn(wo_open.name, by_wo)
        self.assertIn(wo_closed.name, by_wo)
        self.assertEqual(flt(by_wo[wo_open.name]["wip_balance"], 2), 600.0)
        self.assertEqual(flt(by_wo[wo_closed.name]["wip_balance"], 2), 0.0)
        self.assertEqual(flt(by_wo[wo_closed.name]["consumed_value"], 2), 500.0)
        self.assertEqual(flt(by_wo[wo_closed.name]["fg_transferred_value"], 2), 500.0)

    def test_wip_account_vs_adjustment_account_split(self):
        """Report cleanly splits WIP GL balances between 151 WIP account and 710.20 Adjustment account."""
        # WO1 routed to 151 WIP account
        fg1 = self._make_item("FG-151")
        rm1 = self._make_item("RM-151")
        self._receive_rm(rm1, 40.0, 30.0, posting_date="2026-11-15")
        bom1 = self._create_bom(fg1, rm1, 30.0)
        wo1 = self._create_work_order(fg1, bom1.name, 40.0)
        self._set_op_completed(wo1, 40.0)
        self._submit_consumption(wo1, rm1, 40.0, posting_date="2026-11-20")

        # WO2 posted while Company WIP account is unset -> routes to 710.20 Stock Adjustment
        frappe.db.set_value(
            "Company", self.company, "custom_wip_consumption_account", None
        )
        fg2 = self._make_item("FG-710")
        rm2 = self._make_item("RM-710")
        self._receive_rm(rm2, 20.0, 30.0, posting_date="2026-11-15")
        bom2 = self._create_bom(fg2, rm2, 30.0)
        wo2 = self._create_work_order(fg2, bom2.name, 20.0)
        self._set_op_completed(wo2, 20.0)
        self._submit_consumption(wo2, rm2, 20.0, posting_date="2026-11-20")

        # Restore Company WIP account before running report
        frappe.db.set_value(
            "Company",
            self.company,
            "custom_wip_consumption_account",
            self.wip_consumption_account,
        )

        _, rows, _, _, summary = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "only_open_wip": 1,
            }
        )
        by_wo = {r["work_order"]: r for r in rows if r["indent"] == 0}

        self.assertEqual(flt(by_wo[wo1.name]["wip_in_wip_account"], 2), 1200.0)
        self.assertEqual(flt(by_wo[wo1.name]["wip_in_adjustment_account"], 2), 0.0)
        self.assertEqual(flt(by_wo[wo1.name]["wip_balance"], 2), 1200.0)

        self.assertEqual(flt(by_wo[wo2.name]["wip_in_wip_account"], 2), 0.0)
        self.assertEqual(flt(by_wo[wo2.name]["wip_in_adjustment_account"], 2), 600.0)
        self.assertEqual(flt(by_wo[wo2.name]["wip_balance"], 2), 600.0)

        summary_by_label = {item["label"]: item for item in summary}
        self.assertEqual(flt(summary_by_label["Total Open WIP"]["value"], 2), 1800.0)
        self.assertEqual(flt(summary_by_label["WIP Account (151)"]["value"], 2), 1200.0)
        self.assertEqual(
            flt(summary_by_label["Adjustment Account (710.20)"]["value"], 2), 600.0
        )

    def test_wo_status_filter_and_stopped_wo_summary_indicator(self):
        """wo_status filter isolates Stopped WOs and report_summary highlights Stopped WIP."""
        fg_active = self._make_item("FG-ACTIVE")
        rm_active = self._make_item("RM-ACTIVE")
        self._receive_rm(rm_active, 10.0, 50.0, posting_date="2026-11-15")
        bom_active = self._create_bom(fg_active, rm_active, 50.0)
        wo_active = self._create_work_order(fg_active, bom_active.name, 10.0)
        self._set_op_completed(wo_active, 10.0)
        self._submit_consumption(wo_active, rm_active, 10.0, posting_date="2026-11-20")

        fg_stopped = self._make_item("FG-STOP")
        rm_stopped = self._make_item("RM-STOP")
        self._receive_rm(rm_stopped, 20.0, 40.0, posting_date="2026-11-15")
        bom_stopped = self._create_bom(fg_stopped, rm_stopped, 40.0)
        wo_stopped = self._create_work_order(fg_stopped, bom_stopped.name, 20.0)
        self._set_op_completed(wo_stopped, 20.0)
        self._submit_consumption(
            wo_stopped, rm_stopped, 20.0, posting_date="2026-11-21"
        )
        frappe.db.set_value("Work Order", wo_stopped.name, "status", "Stopped")

        # Unfiltered summary picks up 1 Stopped WO with 800.0 WIP
        _, all_rows, _, _, summary_all = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "only_open_wip": 1,
            }
        )
        level0_all = [r for r in all_rows if r["indent"] == 0]
        self.assertEqual(len(level0_all), 2)
        summary_map = {item["label"]: item for item in summary_all}
        self.assertEqual(summary_map["Stopped WOs With Open WIP"]["value"], 1)
        self.assertEqual(summary_map["Stopped WOs With Open WIP"]["indicator"], "Red")
        self.assertEqual(flt(summary_map["Stopped WOs WIP Value"]["value"], 2), 800.0)

        # wo_status="Stopped" returns only the stopped WO
        _, stopped_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "wo_status": "Stopped",
                "only_open_wip": 1,
            }
        )
        level0_stopped = [r for r in stopped_rows if r["indent"] == 0]
        self.assertEqual(len(level0_stopped), 1)
        self.assertEqual(level0_stopped[0]["work_order"], wo_stopped.name)
        self.assertEqual(level0_stopped[0]["wo_status"], "Stopped")
        self.assertEqual(flt(level0_stopped[0]["wip_balance"], 2), 800.0)
        self.assertTrue(
            all(r["work_order_ref"] == wo_stopped.name for r in stopped_rows)
        )

    def test_backflush_service_end_to_end_reconciles_in_wip_report(self):
        """BackflushService consumption + FG-only entries post to 151 WIP and reconcile in report."""
        fg = self._make_item("FG-BF-E2E")
        rm = self._make_item("RM-BF-E2E")
        self._receive_rm(rm, 10.0, 15.0, posting_date="2026-11-15")
        bom = self._create_bom(fg, rm, 15.0)
        wo = self._create_work_order(fg, bom.name, 10.0)
        if not wo.allow_alternative_item:
            frappe.db.set_value("Work Order", wo.name, "allow_alternative_item", 1)
            wo.reload()

        cons_se_name = create_consumption_entry(wo, self.op_10, yield_qty=10.0)
        self.assertTrue(cons_se_name)
        cons_se = frappe.get_doc("Stock Entry", cons_se_name)
        self.assertEqual(cons_se.items[0].expense_account, self.wip_consumption_account)

        _, open_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "work_order": wo.name,
                "only_open_wip": 1,
            }
        )
        open_l0 = [r for r in open_rows if r["indent"] == 0]
        self.assertEqual(len(open_l0), 1)
        self.assertEqual(flt(open_l0[0]["wip_balance"], 2), 150.0)
        self.assertEqual(flt(open_l0[0]["wip_in_wip_account"], 2), 150.0)

        self._set_op_completed(wo, 10.0)
        fg_se_name = create_finished_goods_entry(wo, yield_qty=10.0, is_final=True)
        fg_se = frappe.get_doc("Stock Entry", fg_se_name)
        self.assertTrue(all(not d.s_warehouse for d in fg_se.items))
        self.assertEqual(fg_se.items[0].expense_account, self.wip_consumption_account)

        _, closed_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "work_order": wo.name,
                "only_open_wip": 0,
            }
        )
        closed_l0 = [r for r in closed_rows if r["indent"] == 0]
        self.assertEqual(len(closed_l0), 1)
        self.assertEqual(flt(closed_l0[0]["consumed_value"], 2), 150.0)
        self.assertEqual(flt(closed_l0[0]["fg_transferred_value"], 2), 150.0)
        self.assertEqual(flt(closed_l0[0]["wip_balance"], 2), 0.0)
        self.assertEqual(flt(closed_l0[0]["wip_in_wip_account"], 2), 0.0)

    def test_classic_mixed_manufacture_excluded_from_report_and_summary(self):
        """Classic mixed Manufacture with s_warehouse and non-zero 710.20 GL diff is excluded."""
        frappe.db.set_single_value(
            "Manufacturing Settings",
            {"material_consumption": 0, "get_rm_cost_from_consumption_entry": 0},
        )
        fg = self._make_item("FG-MIXED-EXCL")
        rm = self._make_item("RM-MIXED-EXCL")
        self._receive_rm(rm, 10.0, 15.0, posting_date="2026-11-15")
        bom = self._create_bom(fg, rm, 15.0)
        wo = self._create_work_order(fg, bom.name, 10.0)
        if not wo.allow_alternative_item:
            frappe.db.set_value("Work Order", wo.name, "allow_alternative_item", 1)
            wo.reload()
        self._set_op_completed(wo, 10.0)

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Manufacture"
        se.stock_entry_type = "Manufacture"
        se.work_order = wo.name
        se.company = self.company
        se.posting_date = "2026-11-24"
        se.set_posting_time = 1
        se.from_bom = 1
        se.bom_no = bom.name
        se.fg_completed_qty = 10.0
        se.from_warehouse = self.rm_warehouse
        se.to_warehouse = self.fg_warehouse
        se.append(
            "items",
            {
                "item_code": rm,
                "qty": 10.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.rm_warehouse,
                "cost_center": self.cost_center,
                "expense_account": self.stock_adj_account,
            },
        )
        se.append(
            "items",
            {
                "item_code": fg,
                "qty": 10.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.fg_warehouse,
                "is_finished_item": 1,
                "set_basic_rate_manually": 1,
                "basic_rate": 18.0,
                "cost_center": self.cost_center,
                "expense_account": self.stock_adj_account,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()

        # Verify a non-zero GL variance actually posted to stock_adjustment_account
        adj_gl = frappe.db.sql(
            """
            SELECT SUM(debit - credit)
            FROM `tabGL Entry`
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND account = %s
              AND is_cancelled = 0
            """,
            (se.name, self.stock_adj_account),
        )[0][0]
        self.assertEqual(flt(adj_gl, 2), -30.0)

        for only_open in (1, 0):
            _, rows, _, _, summary = execute_wip_report(
                {
                    "company": self.company,
                    "as_of_date": "2026-11-25",
                    "only_open_wip": only_open,
                }
            )
            self.assertEqual(rows, [])
            summary_map = {item["label"]: item for item in summary}
            self.assertEqual(flt(summary_map["Total Open WIP"]["value"], 2), 0.0)
            self.assertEqual(
                flt(summary_map["Adjustment Account (710.20)"]["value"], 2), 0.0
            )

    def _create_multi_op_bom(
        self,
        fg_item: str,
        op_items: list[tuple[str | None, list[tuple[str, float, float]]]],
        allow_alternative_item: int = 0,
    ):
        """Create a submitted BOM with multiple operations and per-operation raw materials."""
        bom = frappe.new_doc("BOM")
        bom.item = fg_item
        bom.quantity = 1.0
        bom.company = self.company
        bom.currency = "TRY"
        bom.conversion_rate = 1.0
        bom.rm_cost_as_per = "Valuation Rate"
        bom.with_operations = 1
        bom.inspection_required = 0
        bom.allow_alternative_item = allow_alternative_item
        for op_name, rms in op_items:
            if op_name:
                bom.append(
                    "operations",
                    {
                        "operation": op_name,
                        "workstation": self.workstation,
                        "time_in_mins": 10,
                        "hour_rate": 0.0,
                    },
                )
            for rm_item, qty_per_fg, rate in rms:
                bom.append(
                    "items",
                    {
                        "item_code": rm_item,
                        "qty": qty_per_fg,
                        "uom": "Nos",
                        "stock_uom": "Nos",
                        "rate": rate,
                        "operation": op_name or "",
                        "source_warehouse": self.rm_warehouse,
                    },
                )
        bom.insert(ignore_permissions=True)
        bom.submit()
        return bom

    def _submit_multi_item_consumption(
        self,
        wo,
        items_data: list[dict],
        posting_date: str = "2026-11-20",
        confirmation_name: str | None = None,
    ):
        """Submit a Material Consumption for Manufacture Stock Entry with multiple RM rows."""
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
        se.fg_completed_qty = flt(wo.qty)
        se.from_warehouse = self.rm_warehouse
        if confirmation_name:
            if hasattr(se, "meta") and se.meta.has_field("custom_confirmation"):
                se.custom_confirmation = confirmation_name
            se.remarks = f"KTA Production Confirmation: {confirmation_name}"

        for row_data in items_data:
            item_row = {
                "item_code": row_data["item_code"],
                "qty": row_data["qty"],
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.rm_warehouse,
                "t_warehouse": "",
                "cost_center": self.cost_center,
                "expense_account": self.wip_consumption_account,
            }
            if row_data.get("original_item"):
                item_row["original_item"] = row_data["original_item"]
            if row_data.get("custom_original_item"):
                item_row["custom_original_item"] = row_data["custom_original_item"]
            se.append("items", item_row)

        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_confirmation(
        self,
        wo,
        operation: str,
        stock_entry_name: str,
        yield_qty: float = 10.0,
        posting_date: str = "2026-11-20",
    ):
        """Create and submit a KTA Production Confirmation linked to a Stock Entry."""
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": wo.name,
                "operation": operation,
                "posting_date": posting_date,
                "posting_time": "10:00:00",
                "yield_qty": yield_qty,
                "stock_entry": stock_entry_name,
            }
        )
        conf.insert(ignore_permissions=True)
        conf.submit()
        return conf

    def test_three_level_tree_hierarchy_and_exact_reconciliation(self):
        """Report outputs 3-level tree (WO -> Operation -> Raw Material) with exact reconciliation."""
        op_20 = create_test_erpnext_operation("_Test WIP Rep Op 20", self.workstation)
        fg = self._make_item("FG-TREE3")
        rm1 = self._make_item("RM-TREE1")
        rm2 = self._make_item("RM-TREE2")
        rm3 = self._make_item("RM-TREE3")

        self._receive_rm(rm1, 20.0, 12.5, posting_date="2026-11-15")
        self._receive_rm(rm2, 20.0, 30.0, posting_date="2026-11-15")
        self._receive_rm(rm3, 20.0, 5.5, posting_date="2026-11-15")

        bom = self._create_multi_op_bom(
            fg,
            [
                (self.op_10, [(rm1, 1.0, 12.5)]),
                (op_20, [(rm2, 1.0, 30.0), (rm3, 1.0, 5.5)]),
            ],
        )
        wo = self._create_work_order(fg, bom.name, 10.0)
        if not wo.allow_alternative_item:
            frappe.db.set_value("Work Order", wo.name, "allow_alternative_item", 1)
            wo.reload()

        se1 = self._submit_multi_item_consumption(
            wo,
            [{"item_code": rm1, "qty": 10.0}],
            posting_date="2026-11-20",
        )
        self._create_confirmation(
            wo, self.op_10, se1.name, yield_qty=10.0, posting_date="2026-11-20"
        )

        se2 = self._submit_multi_item_consumption(
            wo,
            [{"item_code": rm2, "qty": 5.0}, {"item_code": rm3, "qty": 8.0}],
            posting_date="2026-11-21",
        )
        self._create_confirmation(
            wo, op_20, se2.name, yield_qty=10.0, posting_date="2026-11-21"
        )

        _, rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 1,
            }
        )

        # Expect: 1 Level-0 + 2 Level-1 + 3 Level-2 = 6 rows
        self.assertEqual(len(rows), 6)
        self.assertEqual([r["indent"] for r in rows], [0, 1, 2, 1, 2, 2])

        l0 = rows[0]
        self.assertEqual(l0["tree_node"], wo.name)
        self.assertEqual(l0["parent_node"], "")
        self.assertEqual(l0["row_type"], "work_order")
        self.assertEqual(l0["work_order_ref"], wo.name)
        self.assertIsNone(l0["consumed_qty"])
        self.assertEqual(l0["uom"], "")
        self.assertIsNone(l0["unit_rate"])
        self.assertEqual(flt(l0["consumed_value"], 2), 319.0)

        # Level 1 op_10 -> Level 2 rm1
        l1_op10, l2_rm1 = rows[1], rows[2]
        self.assertEqual(l1_op10["tree_node"], f"{wo.name}::{self.op_10}")
        self.assertEqual(l1_op10["parent_node"], wo.name)
        self.assertEqual(l1_op10["row_type"], "operation")
        self.assertEqual(l1_op10["operation"], self.op_10)
        self.assertIsNone(l1_op10["fg_transferred_value"])
        self.assertIsNone(l1_op10["wip_balance"])
        self.assertEqual(flt(l1_op10["consumed_value"], 2), 125.0)

        self.assertEqual(l2_rm1["tree_node"], f"{wo.name}::{self.op_10}::{rm1}::Nos")
        self.assertEqual(l2_rm1["parent_node"], l1_op10["tree_node"])
        self.assertEqual(l2_rm1["row_type"], "material")
        self.assertEqual(l2_rm1["material_item"], rm1)
        self.assertEqual(flt(l2_rm1["consumed_qty"], 4), 10.0)
        self.assertEqual(l2_rm1["uom"], "Nos")
        self.assertEqual(flt(l2_rm1["unit_rate"], 4), 12.5)
        self.assertEqual(flt(l2_rm1["consumed_value"], 2), 125.0)

        # Level 1 op_20 -> Level 2 rm2 (150.0) then rm3 (44.0) sorted by -consumed_value
        l1_op20, l2_rm2, l2_rm3 = rows[3], rows[4], rows[5]
        self.assertEqual(l1_op20["tree_node"], f"{wo.name}::{op_20}")
        self.assertEqual(flt(l1_op20["consumed_value"], 2), 194.0)
        self.assertEqual(l2_rm2["material_item"], rm2)
        self.assertEqual(flt(l2_rm2["consumed_qty"], 4), 5.0)
        self.assertEqual(flt(l2_rm2["unit_rate"], 4), 30.0)
        self.assertEqual(flt(l2_rm2["consumed_value"], 2), 150.0)
        self.assertEqual(l2_rm3["material_item"], rm3)
        self.assertEqual(flt(l2_rm3["consumed_qty"], 4), 8.0)
        self.assertEqual(flt(l2_rm3["unit_rate"], 4), 5.5)
        self.assertEqual(flt(l2_rm3["consumed_value"], 2), 44.0)

        # Exact reconciliation across all 3 levels
        sum_l2 = flt(sum(flt(r["consumed_value"]) for r in rows if r["indent"] == 2), 2)
        sum_l1 = flt(sum(flt(r["consumed_value"]) for r in rows if r["indent"] == 1), 2)
        self.assertEqual(sum_l2, sum_l1)
        self.assertEqual(sum_l1, flt(l0["consumed_value"], 2))

    def test_multi_operation_milestone_catchup_and_unassigned_fallback(self):
        """Milestone catch-up splits OP10/OP30 materials accurately and unlinked general SE uses Unassigned Operation."""
        op_30 = create_test_erpnext_operation("_Test WIP Rep Op 30", self.workstation)
        fg = self._make_item("FG-MILES")
        rm_op10 = self._make_item("RM-OP10")
        rm_op10_alt = self._make_item("RM-OP10-ALT")
        rm_op30 = self._make_item("RM-OP30")
        rm_unassigned = self._make_item("RM-UNASS")

        for item, rate in (
            (rm_op10, 10.0),
            (rm_op10_alt, 11.0),
            (rm_op30, 20.0),
            (rm_unassigned, 5.0),
        ):
            self._receive_rm(item, 20.0, rate, posting_date="2026-11-15")

        frappe.db.set_value("Item", rm_op10, "allow_alternative_item", 1)
        frappe.db.set_value("Item", rm_op10_alt, "allow_alternative_item", 1)
        frappe.get_doc(
            {
                "doctype": "Item Alternative",
                "item_code": rm_op10,
                "alternative_item_code": rm_op10_alt,
                "two_way": 1,
            }
        ).insert(ignore_permissions=True)

        bom = self._create_multi_op_bom(
            fg,
            [
                (self.op_10, [(rm_op10, 1.0, 10.0)]),
                (op_30, [(rm_op30, 1.0, 20.0)]),
                (None, [(rm_unassigned, 1.0, 5.0)]),
            ],
            allow_alternative_item=1,
        )
        wo = self._create_work_order(fg, bom.name, 10.0)
        if not wo.allow_alternative_item:
            frappe.db.set_value("Work Order", wo.name, "allow_alternative_item", 1)
            wo.reload()

        # Single milestone confirmation SE on op_30 consuming rm_op10_alt (substituted for rm_op10) + rm_op30
        se_milestone = self._submit_multi_item_consumption(
            wo,
            [
                {
                    "item_code": rm_op10_alt,
                    "qty": 5.0,
                    "original_item": rm_op10,
                    "custom_original_item": rm_op10,
                },
                {"item_code": rm_op30, "qty": 5.0},
            ],
            posting_date="2026-11-20",
        )
        self._create_confirmation(
            wo, op_30, se_milestone.name, yield_qty=5.0, posting_date="2026-11-20"
        )

        # Manual unlinked consumption SE for unassigned general item (no confirmation, no operation on WO Item)
        self._submit_multi_item_consumption(
            wo,
            [{"item_code": rm_unassigned, "qty": 4.0}],
            posting_date="2026-11-21",
        )

        _, rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 1,
            }
        )

        l1_by_op = {r["operation"]: r for r in rows if r["indent"] == 1}
        l2_by_op_item = {
            (r["operation"], r["material_item"]): r for r in rows if r["indent"] == 2
        }

        self.assertIn(self.op_10, l1_by_op)
        self.assertIn(op_30, l1_by_op)
        unassigned_label = frappe._("Unassigned Operation")
        self.assertIn(unassigned_label, l1_by_op)

        self.assertEqual(flt(l1_by_op[self.op_10]["consumed_value"], 2), 55.0)
        self.assertEqual(flt(l1_by_op[op_30]["consumed_value"], 2), 100.0)
        self.assertEqual(flt(l1_by_op[unassigned_label]["consumed_value"], 2), 20.0)

        self.assertIn((self.op_10, rm_op10_alt), l2_by_op_item)
        self.assertIn((op_30, rm_op30), l2_by_op_item)
        self.assertIn((unassigned_label, rm_unassigned), l2_by_op_item)

    def test_multi_batch_sle_aggregation_no_double_counting(self):
        """Multi-batch FIFO consumption and multiple SLE rows per SED never double-count qty or value."""
        prev_auto = frappe.db.get_single_value(
            "Stock Settings", "auto_create_serial_and_batch_bundle_for_outward"
        )
        prev_pick = frappe.db.get_single_value(
            "Stock Settings", "pick_serial_and_batch_based_on"
        )
        frappe.db.set_single_value(
            "Stock Settings",
            {
                "auto_create_serial_and_batch_bundle_for_outward": 1,
                "pick_serial_and_batch_based_on": "FIFO",
            },
        )
        try:
            fg = self._make_item("FG-BATCH")
            rm_code = f"_Test WIPR RM-BATCH {self._tag}"
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": rm_code,
                    "item_name": rm_code,
                    "item_group": self.item_group,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": 1,
                    "create_new_batch": 1,
                    "batch_number_series": f"TWB-{self._tag}-.####",
                    "has_serial_no": 0,
                    "valuation_method": "FIFO",
                }
            ).insert(ignore_permissions=True)

            # Batch 1: 40 Nos @ 10.00, Batch 2: 60 Nos @ 20.00
            self._receive_rm(rm_code, 40.0, 10.0, posting_date="2026-11-10")
            self._receive_rm(rm_code, 60.0, 20.0, posting_date="2026-11-12")

            bom = self._create_bom(fg, rm_code, 15.0)
            wo = self._create_work_order(fg, bom.name, 70.0)
            se = self._submit_consumption(wo, rm_code, 70.0, posting_date="2026-11-20")

            # Also verify SQL SLE aggregation when 2 SLE rows share the same voucher_detail_no
            sed_name = se.items[0].name
            sle_rows = frappe.get_all(
                "Stock Ledger Entry",
                filters={
                    "voucher_detail_no": sed_name,
                    "is_cancelled": 0,
                },
                fields=["name", "actual_qty", "stock_value_difference"],
            )
            self.assertGreaterEqual(len(sle_rows), 1)
            if len(sle_rows) == 1:
                # Split the single SLE row into 2 rows referencing the same voucher_detail_no
                orig_sle = frappe.get_doc("Stock Ledger Entry", sle_rows[0]["name"])
                half_qty = flt(orig_sle.actual_qty) / 2.0
                half_val = flt(orig_sle.stock_value_difference) / 2.0
                frappe.db.set_value(
                    "Stock Ledger Entry",
                    orig_sle.name,
                    {
                        "actual_qty": half_qty,
                        "stock_value_difference": half_val,
                    },
                )
                dup_sle = frappe.copy_doc(orig_sle)
                dup_sle.actual_qty = flt(orig_sle.actual_qty) - half_qty
                dup_sle.stock_value_difference = (
                    flt(orig_sle.stock_value_difference) - half_val
                )
                dup_sle.flags.ignore_permissions = True
                dup_sle.db_insert()

            _, rows, _, _, _ = execute_wip_report(
                {
                    "company": self.company,
                    "as_of_date": "2026-11-25",
                    "work_order": wo.name,
                    "only_open_wip": 1,
                    "show_consumption_details": 1,
                }
            )
            l0_rows = [r for r in rows if r["indent"] == 0]
            l2_rows = [r for r in rows if r["indent"] == 2]
            self.assertEqual(len(l0_rows), 1)
            self.assertEqual(len(l2_rows), 1)

            # 40 * 10 + 30 * 20 = 1000.00 (not 2000.00!)
            self.assertEqual(flt(l0_rows[0]["consumed_value"], 2), 1000.0)
            self.assertEqual(flt(l2_rows[0]["consumed_qty"], 4), 70.0)
            self.assertEqual(flt(l2_rows[0]["consumed_value"], 2), 1000.0)
            self.assertEqual(flt(l2_rows[0]["unit_rate"], 4), flt(1000.0 / 70.0, 4))
        finally:
            frappe.db.set_single_value(
                "Stock Settings",
                {
                    "auto_create_serial_and_batch_bundle_for_outward": prev_auto,
                    "pick_serial_and_batch_based_on": prev_pick,
                },
            )

    def test_show_consumption_details_toggle_and_summary_no_double_count(self):
        """Toggling show_consumption_details preserves identical report_summary KPI values."""
        op_20 = create_test_erpnext_operation("_Test WIP Rep Op 20", self.workstation)
        fg = self._make_item("FG-TOGGLE")
        rm1 = self._make_item("RM-TOG1")
        rm2 = self._make_item("RM-TOG2")
        self._receive_rm(rm1, 20.0, 15.0, posting_date="2026-11-15")
        self._receive_rm(rm2, 20.0, 25.0, posting_date="2026-11-15")

        bom = self._create_multi_op_bom(
            fg,
            [(self.op_10, [(rm1, 1.0, 15.0)]), (op_20, [(rm2, 1.0, 25.0)])],
        )
        wo = self._create_work_order(fg, bom.name, 10.0)
        if not wo.allow_alternative_item:
            frappe.db.set_value("Work Order", wo.name, "allow_alternative_item", 1)
            wo.reload()
        self._submit_multi_item_consumption(
            wo,
            [{"item_code": rm1, "qty": 10.0}, {"item_code": rm2, "qty": 10.0}],
            posting_date="2026-11-20",
        )

        _, rows_flat, _, _, summary_flat = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 0,
            }
        )
        _, rows_tree, _, _, summary_tree = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 1,
            }
        )

        self.assertEqual(len(rows_flat), 1)
        self.assertGreater(len(rows_tree), 1)
        self.assertEqual(summary_flat, summary_tree)

    def test_as_of_date_cutoff_filters_child_breakdown(self):
        """as_of_date cutoff filters Level-1 and Level-2 child consumption values accurately."""
        fg = self._make_item("FG-CHILD-CUT")
        rm = self._make_item("RM-CHILD-CUT")
        self._receive_rm(rm, 50.0, 40.0, posting_date="2026-11-15")
        bom = self._create_bom(fg, rm, 40.0)
        wo = self._create_work_order(fg, bom.name, 25.0)

        self._submit_consumption(wo, rm, 10.0, posting_date="2026-11-18")
        self._submit_consumption(wo, rm, 15.0, posting_date="2026-11-22")

        _, rows_early, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-20",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 1,
            }
        )
        l2_early = [r for r in rows_early if r["indent"] == 2]
        self.assertEqual(len(l2_early), 1)
        self.assertEqual(flt(l2_early[0]["consumed_qty"], 4), 10.0)
        self.assertEqual(flt(l2_early[0]["consumed_value"], 2), 400.0)

        _, rows_late, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 1,
            }
        )
        l2_late = [r for r in rows_late if r["indent"] == 2]
        self.assertEqual(len(l2_late), 1)
        self.assertEqual(flt(l2_late[0]["consumed_qty"], 4), 25.0)
        self.assertEqual(flt(l2_late[0]["consumed_value"], 2), 1000.0)

    def test_query_report_run_tree_total_row_no_double_counting(self):
        """frappe.desk.query_report.run with is_tree=True sums ONLY Level-0 rows in Total row."""
        fg = self._make_item("FG-QRTOTAL")
        rm = self._make_item("RM-QRTOTAL")
        self._receive_rm(rm, 30.0, 20.0, posting_date="2026-11-15")
        bom = self._create_bom(fg, rm, 20.0)
        wo = self._create_work_order(fg, bom.name, 30.0)
        self._set_op_completed(wo, 30.0)
        self._submit_consumption(wo, rm, 30.0, posting_date="2026-11-20")
        self._submit_fg_only_manufacture(wo, 10.0, posting_date="2026-11-21")

        res = run_query_report(
            "KTA WIP Valuation Report",
            filters={
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 1,
                "show_consumption_details": 1,
            },
            ignore_prepared_report=True,
            is_tree=True,
            parent_field="parent_node",
        )
        columns = res["columns"]
        result = res["result"]
        self.assertGreaterEqual(len(result), 4)  # L0 + L1 + L2 + Total row

        total_row = result[-1]
        self.assertIsInstance(total_row, list)
        col_idx = {col["fieldname"]: idx for idx, col in enumerate(columns)}

        self.assertEqual(total_row[0], frappe._("Total"))
        self.assertEqual(flt(total_row[col_idx["consumed_value"]], 2), 600.0)
        self.assertEqual(flt(total_row[col_idx["fg_transferred_value"]], 2), 200.0)
        self.assertEqual(flt(total_row[col_idx["wip_balance"]], 2), 400.0)
        self.assertEqual(flt(total_row[col_idx["wip_in_wip_account"]], 2), 400.0)
        self.assertEqual(total_row[col_idx["consumed_qty"]], "")
        self.assertEqual(total_row[col_idx["unit_rate"]], "")

    def test_work_order_ascending_order_preserves_tree_hierarchy(self):
        """Level-0 WOs sort ascending by work_order regardless of posting_date, with children under each parent."""
        fg1 = self._make_item("FG-SORT1")
        rm1 = self._make_item("RM-SORT1")
        self._receive_rm(rm1, 10.0, 15.0, posting_date="2026-11-15")
        bom1 = self._create_bom(fg1, rm1, 15.0)
        wo1 = self._create_work_order(fg1, bom1.name, 10.0)

        fg2 = self._make_item("FG-SORT2")
        rm2 = self._make_item("RM-SORT2")
        self._receive_rm(rm2, 10.0, 25.0, posting_date="2026-11-15")
        bom2 = self._create_bom(fg2, rm2, 25.0)
        wo2 = self._create_work_order(fg2, bom2.name, 10.0)

        smaller_wo, larger_wo = sorted([wo1.name, wo2.name])
        wo_by_name = {wo1.name: (wo1, rm1), wo2.name: (wo2, rm2)}

        # Give smaller_wo an older posting_date and larger_wo a newer posting_date
        self._submit_consumption(
            wo_by_name[smaller_wo][0],
            wo_by_name[smaller_wo][1],
            10.0,
            posting_date="2026-11-18",
        )
        self._submit_consumption(
            wo_by_name[larger_wo][0],
            wo_by_name[larger_wo][1],
            10.0,
            posting_date="2026-11-22",
        )

        _, rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "only_open_wip": 1,
            }
        )

        l0_names = [r["work_order"] for r in rows if r["indent"] == 0]
        self.assertEqual(l0_names, [smaller_wo, larger_wo])

        # Verify each WO is immediately followed by its own indent=1 and indent=2 rows
        self.assertEqual(len(rows), 6)
        self.assertEqual([r["indent"] for r in rows], [0, 1, 2, 0, 1, 2])
        self.assertTrue(all(r["work_order_ref"] == smaller_wo for r in rows[0:3]))
        self.assertTrue(all(r["work_order_ref"] == larger_wo for r in rows[3:6]))
        self.assertEqual(rows[1]["parent_node"], smaller_wo)
        self.assertEqual(rows[2]["parent_node"], rows[1]["tree_node"])
        self.assertEqual(rows[4]["parent_node"], larger_wo)
        self.assertEqual(rows[5]["parent_node"], rows[4]["tree_node"])

    def test_column_sortable_flag_follows_show_consumption_details(self):
        """Columns disable sorting in tree breakdown mode and enable sorting in flat mode."""
        cols_default, _, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
            }
        )
        self.assertTrue(cols_default)
        self.assertTrue(all(col.get("sortable") is False for col in cols_default))

        cols_flat, _, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "show_consumption_details": 0,
            }
        )
        self.assertTrue(cols_flat)
        self.assertTrue(all(col.get("sortable") is True for col in cols_flat))

    def _submit_wip_return_receipt(
        self,
        wo,
        rm_item: str,
        qty: float,
        rate: float,
        posting_date: str = "2026-11-22",
    ):
        """Submit a Material Receipt returning unused WIP stock back to warehouse."""
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = "Material Receipt"
        se.work_order = wo.name
        se.company = self.company
        se.posting_date = posting_date
        se.set_posting_time = 1
        se.to_warehouse = self.rm_warehouse
        se.append(
            "items",
            {
                "item_code": rm_item,
                "qty": qty,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.rm_warehouse,
                "basic_rate": rate,
                "expense_account": self.wip_consumption_account,
                "cost_center": self.cost_center,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def test_wip_return_material_receipt_reconciles_closed_wo_in_report(self):
        """Material Receipt with WIP expense_account closes open WIP on Closed WO without distorting consumption tree."""
        fg = self._make_item("FG-WIP-RET")
        rm = self._make_item("RM-WIP-RET")
        self._receive_rm(rm, 50.0, 20.0, posting_date="2026-11-15")
        bom = self._create_bom(fg, rm, 20.0)
        wo = self._create_work_order(fg, bom.name, 50.0)
        self._set_op_completed(wo, 50.0)

        self._submit_consumption(wo, rm, 50.0, posting_date="2026-11-18")
        self._submit_fg_only_manufacture(wo, 20.0, posting_date="2026-11-19")

        wo_doc = frappe.get_doc("Work Order", wo.name)
        wo_doc.update_status("Closed")

        self._submit_wip_return_receipt(wo, rm, 30.0, 20.0, posting_date="2026-11-22")

        # Cutoff before return date: still open with 600.0 WIP
        _, before_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-20",
                "work_order": wo.name,
                "only_open_wip": 1,
            }
        )
        before_l0 = [r for r in before_rows if r["indent"] == 0]
        self.assertEqual(len(before_l0), 1)
        self.assertEqual(flt(before_l0[0]["wip_adjustment_value"], 2), 0.0)
        self.assertEqual(flt(before_l0[0]["wip_balance"], 2), 600.0)

        # After return date with only_open_wip=1: WO is reconciled and hidden
        _, open_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 1,
            }
        )
        self.assertEqual(open_rows, [])

        # After return date with only_open_wip=0: return shows -600.0 and tree sums stay 1000.0
        _, all_rows, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo.name,
                "only_open_wip": 0,
            }
        )
        l0 = [r for r in all_rows if r["indent"] == 0]
        l1 = [r for r in all_rows if r["indent"] == 1]
        l2 = [r for r in all_rows if r["indent"] == 2]
        self.assertEqual(len(l0), 1)
        self.assertEqual(flt(l0[0]["consumed_value"], 2), 1000.0)
        self.assertEqual(flt(l0[0]["fg_transferred_value"], 2), 400.0)
        self.assertEqual(flt(l0[0]["wip_adjustment_value"], 2), -600.0)
        self.assertEqual(flt(l0[0]["wip_balance"], 2), 0.0)
        self.assertEqual(flt(l0[0]["wip_in_wip_account"], 2), 0.0)
        self.assertEqual(getdate(l0[0]["last_posting_date"]), getdate("2026-11-22"))
        self.assertEqual(flt(sum(flt(r["consumed_value"]) for r in l1), 2), 1000.0)
        self.assertEqual(flt(sum(flt(r["consumed_value"]) for r in l2), 2), 1000.0)

    def test_journal_entry_custom_work_order_reconciles_wip_and_ignores_adj_counter_row(
        self,
    ):
        """Journal Entry lines with custom_work_order close positive/negative WIP without double-counting 710.20 counter row."""
        # Case A: Positive WIP (500.0) closed by crediting 151.01.002 + debiting 710.20 (both tagged with custom_work_order)
        fg1 = self._make_item("FG-JE-POS")
        rm1 = self._make_item("RM-JE-POS")
        self._receive_rm(rm1, 10.0, 50.0, posting_date="2026-11-15")
        bom1 = self._create_bom(fg1, rm1, 50.0)
        wo1 = self._create_work_order(fg1, bom1.name, 10.0)
        self._submit_consumption(wo1, rm1, 10.0, posting_date="2026-11-18")

        je_pos = frappe.new_doc("Journal Entry")
        je_pos.voucher_type = "Journal Entry"
        je_pos.company = self.company
        je_pos.posting_date = "2026-11-22"
        je_pos.append(
            "accounts",
            {
                "account": self.wip_consumption_account,
                "credit_in_account_currency": 500.0,
                "cost_center": self.cost_center,
                "custom_work_order": wo1.name,
            },
        )
        je_pos.append(
            "accounts",
            {
                "account": self.stock_adj_account,
                "debit_in_account_currency": 500.0,
                "cost_center": self.cost_center,
                "custom_work_order": wo1.name,
            },
        )
        je_pos.insert(ignore_permissions=True)
        je_pos.submit()

        # Cutoff before JE1: WO1 still open with 500.0
        _, wo1_before, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-20",
                "work_order": wo1.name,
                "only_open_wip": 1,
            }
        )
        self.assertEqual(
            flt(next(r for r in wo1_before if r["indent"] == 0)["wip_balance"], 2),
            500.0,
        )

        # After JE1: hidden when only_open_wip=1, zeroed when only_open_wip=0
        _, wo1_open, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo1.name,
                "only_open_wip": 1,
            }
        )
        self.assertEqual(wo1_open, [])

        _, wo1_all, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo1.name,
                "only_open_wip": 0,
            }
        )
        wo1_l0 = next(r for r in wo1_all if r["indent"] == 0)
        self.assertEqual(flt(wo1_l0["wip_adjustment_value"], 2), -500.0)
        self.assertEqual(flt(wo1_l0["wip_balance"], 2), 0.0)
        self.assertEqual(flt(wo1_l0["wip_in_wip_account"], 2), 0.0)
        self.assertEqual(flt(wo1_l0["wip_in_adjustment_account"], 2), 0.0)

        # Case B: Negative WIP (-100.0 from 300 consumption - 400 return) closed by debiting 151.01.002 (+100.0)
        fg2 = self._make_item("FG-JE-NEG")
        rm2 = self._make_item("RM-JE-NEG")
        self._receive_rm(rm2, 20.0, 30.0, posting_date="2026-11-15")
        bom2 = self._create_bom(fg2, rm2, 30.0)
        wo2 = self._create_work_order(fg2, bom2.name, 10.0)
        self._submit_consumption(wo2, rm2, 10.0, posting_date="2026-11-18")
        self._submit_wip_return_receipt(wo2, rm2, 10.0, 40.0, posting_date="2026-11-19")

        je_neg = frappe.new_doc("Journal Entry")
        je_neg.voucher_type = "Journal Entry"
        je_neg.company = self.company
        je_neg.posting_date = "2026-11-22"
        je_neg.append(
            "accounts",
            {
                "account": self.wip_consumption_account,
                "debit_in_account_currency": 100.0,
                "cost_center": self.cost_center,
                "custom_work_order": wo2.name,
            },
        )
        je_neg.append(
            "accounts",
            {
                "account": self.stock_adj_account,
                "credit_in_account_currency": 100.0,
                "cost_center": self.cost_center,
                "custom_work_order": wo2.name,
            },
        )
        je_neg.insert(ignore_permissions=True)
        je_neg.submit()

        _, wo2_before, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-20",
                "work_order": wo2.name,
                "only_open_wip": 1,
            }
        )
        self.assertEqual(
            flt(next(r for r in wo2_before if r["indent"] == 0)["wip_balance"], 2),
            -100.0,
        )

        _, wo2_open, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo2.name,
                "only_open_wip": 1,
            }
        )
        self.assertEqual(wo2_open, [])

        _, wo2_all, _, _, _ = execute_wip_report(
            {
                "company": self.company,
                "as_of_date": "2026-11-25",
                "work_order": wo2.name,
                "only_open_wip": 0,
            }
        )
        wo2_l0 = next(r for r in wo2_all if r["indent"] == 0)
        self.assertEqual(flt(wo2_l0["consumed_value"], 2), 300.0)
        self.assertEqual(flt(wo2_l0["wip_adjustment_value"], 2), -300.0)
        self.assertEqual(flt(wo2_l0["wip_balance"], 2), 0.0)
        self.assertEqual(flt(wo2_l0["wip_in_wip_account"], 2), 0.0)
        self.assertEqual(flt(wo2_l0["wip_in_adjustment_account"], 2), 0.0)
