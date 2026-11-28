import frappe
from erpnext.manufacturing.doctype.work_order.work_order import (
    make_stock_entry as make_stock_entry_from_wo,
)
from frappe.utils import flt

from erpnextkta.overrides.company_wip_validation import (
    ensure_journal_entry_work_order_field,
    get_validated_wip_consumption_account,
)
from erpnextkta.patches.v4_6.backfill_shopfloor_wip_account import (
    backfill_shopfloor_wip_entries,
    ensure_company_wip_field,
    ensure_default_wip_account,
    get_min_editable_posting_date,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_erpnext_operation,
    create_test_item_group,
    create_test_workstation,
    setup_test_fiscal_years,
)

WIP_TEST_COMPANY = "_Test WIP Accounting Co"
WIP_TEST_ABBR = "TWIP"


class TestWIPAccounting(KTABaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        if not frappe.db.has_column("Company", "custom_wip_consumption_account"):
            ensure_company_wip_field()
        if not frappe.db.has_column("Journal Entry Account", "custom_work_order"):
            ensure_journal_entry_work_order_field()

        cls._ensure_wip_test_company()
        frappe.db.commit()

    @classmethod
    def _ensure_wip_test_company(cls):
        """Create an isolated perpetual-inventory test company with 150/151/152/710.20 accounts."""
        if not frappe.db.exists("Company", WIP_TEST_COMPANY):
            frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": WIP_TEST_COMPANY,
                    "abbr": WIP_TEST_ABBR,
                    "default_currency": "TRY",
                    "country": "Turkey",
                    "create_chart_of_accounts_based_on": "Standard Template",
                    "chart_of_accounts": "Standard",
                }
            ).insert(ignore_permissions=True)

        setup_test_fiscal_years(WIP_TEST_COMPANY)

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
        cls.consignment_stock_account = cls._ensure_account(
            "Dis Konsinye Stok",
            parent_account=cls.wip_group_account,
            root_type="Asset",
            account_type="Stock",
            is_group=0,
            account_number="151.01.001",
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
            WIP_TEST_COMPANY,
            {
                "enable_perpetual_inventory": 1,
                "default_inventory_account": cls.rm_stock_account,
                "stock_adjustment_account": cls.stock_adj_account,
                "cost_center": cls.cost_center,
            },
        )

        cls.rm_warehouse = cls._ensure_warehouse("_Test WIP RM", cls.rm_stock_account)
        cls.wip_warehouse = cls._ensure_warehouse(
            "_Test WIP Floor", cls.rm_stock_account
        )
        cls.fg_warehouse = cls._ensure_warehouse("_Test WIP FG", cls.fg_stock_account)

    @classmethod
    def _ensure_cost_center(cls) -> str:
        cc_name = f"Main - {WIP_TEST_ABBR}"
        if frappe.db.exists("Cost Center", cc_name):
            return cc_name
        root_cc = frappe.db.get_value(
            "Cost Center",
            {"company": WIP_TEST_COMPANY, "is_group": 1},
            "name",
        )
        if not root_cc:
            root_doc = frappe.get_doc(
                {
                    "doctype": "Cost Center",
                    "cost_center_name": WIP_TEST_COMPANY,
                    "company": WIP_TEST_COMPANY,
                    "is_group": 1,
                }
            )
            root_doc.insert(ignore_permissions=True)
            root_cc = root_doc.name
        cc_doc = frappe.get_doc(
            {
                "doctype": "Cost Center",
                "cost_center_name": "Main",
                "company": WIP_TEST_COMPANY,
                "parent_cost_center": root_cc,
                "is_group": 0,
            }
        )
        cc_doc.insert(ignore_permissions=True)
        return cc_doc.name

    @classmethod
    def _ensure_root_account(cls, fallback_name: str, root_type: str) -> str:
        fullname = f"{fallback_name} - {WIP_TEST_ABBR}"
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
            (WIP_TEST_COMPANY, root_type),
            pluck=True,
        )
        if rows:
            return rows[0]

        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": WIP_TEST_COMPANY,
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
            {"company": WIP_TEST_COMPANY, "account_number": account_number},
            "name",
        )
        if existing:
            return existing
        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": WIP_TEST_COMPANY,
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
        fullname = f"{warehouse_name} - {WIP_TEST_ABBR}"
        if not frappe.db.exists("Warehouse", fullname):
            doc = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": warehouse_name,
                    "company": WIP_TEST_COMPANY,
                    "account": account,
                }
            )
            doc.insert(ignore_permissions=True)
            return doc.name
        frappe.db.set_value("Warehouse", fullname, "account", account)
        return fullname

    def setUp(self):
        super().setUp()
        self.company = WIP_TEST_COMPANY
        self._tag = frappe.generate_hash(length=6)
        self.item_group = create_test_item_group()
        self.workstation = create_test_workstation("_Test WIP Workstation")
        frappe.db.set_value("Workstation", self.workstation, "hour_rate", 0.0)
        self.op_10 = create_test_erpnext_operation("_Test WIP Op 10", self.workstation)

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

    def _make_item(self, suffix: str) -> str:
        code = f"_Test WIP {suffix} {self._tag}"
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

    def _submit_consumption(
        self, wo, rm_item: str, qty: float, posting_date: str = "2026-11-24"
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
        self, wo, qty: float, posting_date: str = "2026-11-25", is_final: bool = False
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

    def _get_gl_sum(
        self, voucher_names: list[str], account: str, include_cancelled: bool = False
    ) -> float:
        filters = {
            "voucher_type": "Stock Entry",
            "voucher_no": ["in", voucher_names],
            "account": account,
        }
        if not include_cancelled:
            filters["is_cancelled"] = 0
        rows = frappe.get_all("GL Entry", filters=filters, fields=["debit", "credit"])
        return flt(sum(flt(r.debit) - flt(r.credit) for r in rows), 2)

    def test_company_rejects_stock_type_and_group_wip_account(self):
        """Company validation rejects Stock-type, Group, and cross-company WIP accounts."""
        company_doc = frappe.get_doc("Company", self.company)

        company_doc.custom_wip_consumption_account = self.consignment_stock_account
        with self.assertRaises(frappe.ValidationError):
            company_doc.save(ignore_permissions=True)

        company_doc.custom_wip_consumption_account = self.wip_group_account
        with self.assertRaises(frappe.ValidationError):
            company_doc.save(ignore_permissions=True)

        other_acc = frappe.db.get_value(
            "Account",
            {
                "company": ["!=", self.company],
                "is_group": 0,
                "account_type": ["!=", "Stock"],
            },
            "name",
        )
        if other_acc:
            company_doc.custom_wip_consumption_account = other_acc
            with self.assertRaises(frappe.ValidationError):
                company_doc.save(ignore_permissions=True)

        company_doc = frappe.get_doc("Company", self.company)
        company_doc.custom_wip_consumption_account = self.wip_consumption_account
        company_doc.save(ignore_permissions=True)
        self.assertEqual(
            get_validated_wip_consumption_account(self.company),
            self.wip_consumption_account,
        )

    def test_consumption_and_fg_only_manufacture_route_to_wip_account_and_zero_out_on_completion(
        self,
    ):
        """Consumption debits WIP 151 / credits 150; partial and final FG-only Manufacture credit WIP 151 to 0.00."""
        fg = self._make_item("FG-ROUTE")
        rm = self._make_item("RM-ROUTE")
        self._receive_rm(rm, 100.0, 25.0)
        bom = self._create_bom(fg, rm, 25.0)
        wo = self._create_work_order(fg, bom.name, 100.0)

        self._set_op_completed(wo, 100.0)
        cons = self._submit_consumption(wo, rm, 100.0)

        self.assertEqual(
            self._get_gl_sum([cons.name], self.wip_consumption_account), 2500.0
        )
        self.assertEqual(self._get_gl_sum([cons.name], self.rm_stock_account), -2500.0)
        self.assertEqual(self._get_gl_sum([cons.name], self.stock_adj_account), 0.0)

        mfg_partial = self._submit_fg_only_manufacture(wo, 40.0)
        self.assertEqual(
            self._get_gl_sum([mfg_partial.name], self.fg_stock_account), 1000.0
        )
        self.assertEqual(
            self._get_gl_sum([mfg_partial.name], self.wip_consumption_account), -1000.0
        )
        self.assertEqual(
            self._get_gl_sum(
                [cons.name, mfg_partial.name], self.wip_consumption_account
            ),
            1500.0,
        )

        mfg_final = self._submit_fg_only_manufacture(wo, 60.0, is_final=True)
        self.assertEqual(
            self._get_gl_sum([mfg_final.name], self.fg_stock_account), 1500.0
        )
        self.assertEqual(
            self._get_gl_sum([mfg_final.name], self.wip_consumption_account), -1500.0
        )
        self.assertEqual(
            self._get_gl_sum(
                [cons.name, mfg_partial.name, mfg_final.name],
                self.wip_consumption_account,
            ),
            0.0,
        )

    def test_mixed_standard_manufacture_does_not_use_wip_account(self):
        """Standard Manufacture entries containing source RM rows do not route to WIP account."""
        frappe.db.set_single_value(
            "Manufacturing Settings",
            {"material_consumption": 0, "get_rm_cost_from_consumption_entry": 0},
        )
        fg = self._make_item("FG-MIXED")
        rm = self._make_item("RM-MIXED")
        self._receive_rm(rm, 10.0, 15.0)
        bom = self._create_bom(fg, rm, 15.0)
        wo = self._create_work_order(fg, bom.name, 10.0)
        self._set_op_completed(wo, 10.0)

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Manufacture"
        se.stock_entry_type = "Manufacture"
        se.work_order = wo.name
        se.company = self.company
        se.posting_date = "2026-11-25"
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
                "cost_center": self.cost_center,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()

        for row in se.items:
            self.assertNotEqual(row.expense_account, self.wip_consumption_account)

        self.assertEqual(self._get_gl_sum([se.name], self.wip_consumption_account), 0.0)

    def test_cors_cancellation_reverses_wip_account_cleanly(self):
        """Cancelling FG-only Manufacture and Consumption entries reverses WIP 151 to 0.00."""
        fg = self._make_item("FG-CORS")
        rm = self._make_item("RM-CORS")
        self._receive_rm(rm, 50.0, 20.0)
        bom = self._create_bom(fg, rm, 20.0)
        wo = self._create_work_order(fg, bom.name, 50.0)

        self._set_op_completed(wo, 50.0)
        cons = self._submit_consumption(wo, rm, 50.0)
        mfg = self._submit_fg_only_manufacture(wo, 50.0, is_final=True)

        mfg.cancel()
        cons.cancel()

        vouchers = [cons.name, mfg.name]
        for account in (
            self.wip_consumption_account,
            self.rm_stock_account,
            self.fg_stock_account,
        ):
            self.assertEqual(
                self._get_gl_sum(vouchers, account, include_cancelled=False), 0.0
            )
            self.assertEqual(
                self._get_gl_sum(vouchers, account, include_cancelled=True), 0.0
            )

    def test_backfill_patch_dry_run_apply_cutoff_idempotency_and_post_backfill_cancel(
        self,
    ):
        """Backfill patch supports dry_run, respects cutoff & freeze clamp, is idempotent, and supports post-backfill cancel."""
        fg = self._make_item("FG-BF")
        rm = self._make_item("RM-BF")
        self._receive_rm(rm, 100.0, 30.0, posting_date="2026-11-15")
        bom = self._create_bom(fg, rm, 30.0)
        wo = self._create_work_order(fg, bom.name, 100.0)

        # Simulate historical entries posted before WIP account was configured on Company
        frappe.db.set_value(
            "Company", self.company, "custom_wip_consumption_account", ""
        )

        self._set_op_completed(wo, 100.0)
        pre_cutoff_cons = self._submit_consumption(
            wo, rm, 20.0, posting_date="2026-11-20"
        )
        in_window_cons = self._submit_consumption(
            wo, rm, 40.0, posting_date="2026-11-24"
        )
        in_window_mfg = self._submit_fg_only_manufacture(
            wo, 40.0, posting_date="2026-11-25"
        )

        # Verify historical entries hit stock_adjustment_account (710.20)
        self.assertEqual(
            self._get_gl_sum([in_window_cons.name], self.stock_adj_account), 1200.0
        )
        self.assertEqual(
            self._get_gl_sum([in_window_mfg.name], self.stock_adj_account), -1200.0
        )

        # Verify freeze-date clamping helper
        frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", "2026-11-24")
        clamped_date, was_clamped = get_min_editable_posting_date(
            self.company, "2026-11-23"
        )
        self.assertTrue(was_clamped)
        self.assertEqual(clamped_date, "2026-11-25")

        frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", "")

        # Test ensure_default_wip_account links 151.01.002 automatically
        linked_acc = ensure_default_wip_account(self.company)
        self.assertEqual(linked_acc, self.wip_consumption_account)

        # 1. Dry-run makes zero DB writes
        dry_res = backfill_shopfloor_wip_entries(
            company=self.company, from_date="2026-11-23", dry_run=True
        )
        self.assertTrue(dry_res["dry_run"])
        self.assertEqual(dry_res["matched_vouchers"], 2)
        self.assertEqual(dry_res["updated_vouchers"], 0)
        self.assertEqual(dry_res["total_debit_moved"], 1200.0)
        self.assertEqual(dry_res["total_credit_moved"], 1200.0)
        self.assertEqual(dry_res["net_wip_moved"], 0.0)
        self.assertEqual(
            self._get_gl_sum([in_window_cons.name], self.stock_adj_account), 1200.0
        )

        # 2. Apply backfill
        apply_res = backfill_shopfloor_wip_entries(
            company=self.company, from_date="2026-11-23", dry_run=False
        )
        self.assertFalse(apply_res["dry_run"])
        self.assertEqual(apply_res["matched_vouchers"], 2)
        self.assertEqual(apply_res["updated_vouchers"], 2)
        self.assertEqual(apply_res["errors"], [])

        # Pre-cutoff voucher stays untouched on stock_adjustment_account
        self.assertEqual(
            self._get_gl_sum([pre_cutoff_cons.name], self.stock_adj_account), 600.0
        )
        self.assertEqual(
            self._get_gl_sum([pre_cutoff_cons.name], self.wip_consumption_account), 0.0
        )

        # In-window vouchers moved to WIP account (both Detail and GL account & against)
        self.assertEqual(
            self._get_gl_sum([in_window_cons.name], self.wip_consumption_account),
            1200.0,
        )
        self.assertEqual(
            self._get_gl_sum([in_window_mfg.name], self.wip_consumption_account),
            -1200.0,
        )
        self.assertEqual(
            self._get_gl_sum(
                [in_window_cons.name, in_window_mfg.name], self.stock_adj_account
            ),
            0.0,
        )

        cons_detail_exp = frappe.db.get_value(
            "Stock Entry Detail", {"parent": in_window_cons.name}, "expense_account"
        )
        mfg_detail_exp = frappe.db.get_value(
            "Stock Entry Detail", {"parent": in_window_mfg.name}, "expense_account"
        )
        self.assertEqual(cons_detail_exp, self.wip_consumption_account)
        self.assertEqual(mfg_detail_exp, self.wip_consumption_account)

        rm_against = frappe.db.get_value(
            "GL Entry",
            {
                "voucher_type": "Stock Entry",
                "voucher_no": in_window_cons.name,
                "account": self.rm_stock_account,
                "is_cancelled": 0,
            },
            "against",
        )
        self.assertEqual(rm_against, self.wip_consumption_account)

        # 3. Idempotent second run updates 0 vouchers
        second_res = backfill_shopfloor_wip_entries(
            company=self.company, from_date="2026-11-23", dry_run=False
        )
        self.assertEqual(second_res["matched_vouchers"], 0)
        self.assertEqual(second_res["updated_vouchers"], 0)

        # 4. Cancelling backfilled Stock Entries reverses WIP 151 cleanly
        in_window_mfg.reload()
        in_window_mfg.cancel()
        in_window_cons.reload()
        in_window_cons.cancel()

        self.assertEqual(
            self._get_gl_sum(
                [in_window_cons.name, in_window_mfg.name],
                self.wip_consumption_account,
                include_cancelled=False,
            ),
            0.0,
        )
        self.assertEqual(
            self._get_gl_sum(
                [in_window_cons.name, in_window_mfg.name],
                self.wip_consumption_account,
                include_cancelled=True,
            ),
            0.0,
        )

    def test_fg_manufacture_uses_sle_actual_cost_when_sed_diverges(self):
        """Partial and final FG-only Manufacture entries use SLE stock_value_difference when SED diverges."""
        fg = self._make_item("FG-SLE-DIV")
        rm = self._make_item("RM-SLE-DIV")
        self._receive_rm(rm, 100.0, 25.0)
        bom = self._create_bom(fg, rm, 25.0)
        wo = self._create_work_order(fg, bom.name, 100.0)

        self._set_op_completed(wo, 100.0)
        cons = self._submit_consumption(wo, rm, 100.0)

        # Simulate SLE/GL divergence (3100.0) vs SED valuation_rate * transfer_qty (2500.0)
        frappe.db.sql(
            """
            UPDATE `tabStock Ledger Entry`
            SET stock_value_difference = -3100.0,
                valuation_rate = 31.0
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND is_cancelled = 0
            """,
            (cons.name,),
        )
        frappe.db.sql(
            """
            UPDATE `tabGL Entry`
            SET debit = 3100.0,
                debit_in_account_currency = 3100.0
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND account = %s
              AND is_cancelled = 0
            """,
            (cons.name, self.wip_consumption_account),
        )
        frappe.db.sql(
            """
            UPDATE `tabGL Entry`
            SET credit = 3100.0,
                credit_in_account_currency = 3100.0
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
              AND account = %s
              AND is_cancelled = 0
            """,
            (cons.name, self.rm_stock_account),
        )

        mfg_partial = self._submit_fg_only_manufacture(wo, 40.0, is_final=False)
        partial_fg = next(d for d in mfg_partial.items if d.is_finished_item)
        self.assertAlmostEqual(flt(partial_fg.basic_amount), 1240.0, places=2)
        self.assertAlmostEqual(flt(partial_fg.basic_rate), 31.0, places=2)

        mfg_final = self._submit_fg_only_manufacture(wo, 60.0, is_final=True)
        final_fg = next(d for d in mfg_final.items if d.is_finished_item)
        self.assertAlmostEqual(flt(final_fg.basic_amount), 1860.0, places=2)
        self.assertAlmostEqual(flt(final_fg.basic_rate), 31.0, places=2)

        self.assertEqual(
            self._get_gl_sum(
                [cons.name, mfg_partial.name, mfg_final.name],
                self.wip_consumption_account,
            ),
            0.0,
        )

    def test_wip_return_material_receipt_allowed_on_closed_work_order(self):
        """Material Receipt with WIP expense_account keeps work_order on Closed WO, credits 151, and cancels cleanly."""
        fg = self._make_item("FG-WIP-RET")
        rm = self._make_item("RM-WIP-RET")
        self._receive_rm(rm, 50.0, 20.0)
        bom = self._create_bom(fg, rm, 20.0)
        wo = self._create_work_order(fg, bom.name, 50.0)

        self._set_op_completed(wo, 50.0)
        cons = self._submit_consumption(wo, rm, 50.0)

        wo_doc = frappe.get_doc("Work Order", wo.name)
        wo_doc.update_status("Closed")
        self.assertEqual(frappe.db.get_value("Work Order", wo.name, "status"), "Closed")

        ret_se = frappe.new_doc("Stock Entry")
        ret_se.purpose = "Material Receipt"
        ret_se.stock_entry_type = "Material Receipt"
        ret_se.work_order = wo.name
        ret_se.company = self.company
        ret_se.posting_date = "2026-11-25"
        ret_se.set_posting_time = 1
        ret_se.to_warehouse = self.rm_warehouse
        ret_se.append(
            "items",
            {
                "item_code": rm,
                "qty": 10.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.rm_warehouse,
                "basic_rate": 20.0,
                "expense_account": self.wip_consumption_account,
                "cost_center": self.cost_center,
            },
        )
        ret_se.insert(ignore_permissions=True)
        ret_se.submit()

        self.assertEqual(ret_se.work_order, wo.name)
        self.assertEqual(frappe.db.get_value("Work Order", wo.name, "status"), "Closed")
        self.assertEqual(
            self._get_gl_sum([ret_se.name], self.wip_consumption_account), -200.0
        )
        self.assertEqual(self._get_gl_sum([ret_se.name], self.rm_stock_account), 200.0)
        self.assertEqual(
            self._get_gl_sum([cons.name, ret_se.name], self.wip_consumption_account),
            800.0,
        )
        self.assertAlmostEqual(ret_se._get_total_consumed_cost(), 800.0, places=2)

        ret_se.reload()
        ret_se.cancel()

        self.assertEqual(frappe.db.get_value("Work Order", wo.name, "status"), "Closed")
        self.assertEqual(
            self._get_gl_sum(
                [ret_se.name], self.wip_consumption_account, include_cancelled=False
            ),
            0.0,
        )
        self.assertEqual(
            self._get_gl_sum(
                [ret_se.name], self.wip_consumption_account, include_cancelled=True
            ),
            0.0,
        )

    def test_regular_material_receipt_still_clears_work_order(self):
        """Standard Material Receipt without WIP expense_account clears work_order as usual."""
        fg = self._make_item("FG-REG-MR")
        rm = self._make_item("RM-REG-MR")
        self._receive_rm(rm, 10.0, 15.0)
        bom = self._create_bom(fg, rm, 15.0)
        wo = self._create_work_order(fg, bom.name, 10.0)

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = "Material Receipt"
        se.work_order = wo.name
        se.company = self.company
        se.posting_date = "2026-11-25"
        se.set_posting_time = 1
        se.to_warehouse = self.rm_warehouse
        se.append(
            "items",
            {
                "item_code": rm,
                "qty": 5.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.rm_warehouse,
                "basic_rate": 15.0,
                "expense_account": self.stock_adj_account,
                "cost_center": self.cost_center,
            },
        )
        se.insert(ignore_permissions=True)
        se.submit()

        self.assertIsNone(se.work_order)
