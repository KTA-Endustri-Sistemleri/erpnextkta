import frappe
from frappe.utils import flt

from erpnextkta.patches.v4_6.fix_accounting_master_defaults import (
    fix_accounting_master_defaults,
)
from erpnextkta.patches.v4_6.post_2026_accounting_reclassifications import (
    post_2026_accounting_reclassifications,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_item_group,
    setup_test_fiscal_years,
)

RECLASS_TEST_COMPANY = "_Test Reclass Co"
RECLASS_TEST_ABBR = "TRCL"


class TestAccountingReclassificationPatches(KTABaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls._ensure_test_company_and_masters()
        frappe.db.commit()

    @classmethod
    def _ensure_test_company_and_masters(cls):
        """Create isolated perpetual inventory test company with full chart and warehouses."""
        if not frappe.db.exists("Company", RECLASS_TEST_COMPANY):
            frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": RECLASS_TEST_COMPANY,
                    "abbr": RECLASS_TEST_ABBR,
                    "default_currency": "TRY",
                    "country": "Turkey",
                    "create_chart_of_accounts_based_on": "Standard Template",
                    "chart_of_accounts": "Standard",
                }
            ).insert(ignore_permissions=True)

        setup_test_fiscal_years(RECLASS_TEST_COMPANY)

        cls.cost_center = cls._ensure_cost_center()
        assets_root = cls._ensure_root_account("Application of Funds (Assets)", "Asset")
        income_root = cls._ensure_root_account("Income", "Income")
        expenses_root = cls._ensure_root_account("Expenses", "Expense")

        cls.acc_150_1 = cls._ensure_account(
            "150.01.001 - Test RM Stock",
            parent_account=assets_root,
            root_type="Asset",
            account_type="Stock",
            is_group=0,
            account_number="150.01.001",
            account_currency="TRY",
        )
        cls.acc_150_4 = cls._ensure_account(
            "150.01.004 - Test Production Stock",
            parent_account=assets_root,
            root_type="Asset",
            account_type="Stock",
            is_group=0,
            account_number="150.01.004",
            account_currency="TRY",
        )
        cls.acc_152_01 = cls._ensure_account(
            "152.01 - Test FG Stock",
            parent_account=assets_root,
            root_type="Asset",
            account_type="Stock",
            is_group=0,
            account_number="152.01",
            account_currency="TRY",
        )
        cls.acc_197 = cls._ensure_account(
            "197.01.001 - Test Classic Mfg Offset",
            parent_account=assets_root,
            root_type="Asset",
            account_type="",
            is_group=0,
            account_number="197.01.001",
            account_currency="TRY",
        )
        cls.acc_600 = cls._ensure_account(
            "600.01.001 - Test Domestic Income",
            parent_account=income_root,
            root_type="Income",
            account_type="Income Account",
            is_group=0,
            account_number="600.01.001",
            account_currency="TRY",
        )
        cls.acc_601 = cls._ensure_account(
            "601.01.002 - Test Export Income EUR",
            parent_account=income_root,
            root_type="Income",
            account_type="Income Account",
            is_group=0,
            account_number="601.01.002",
            account_currency="EUR",
        )
        cls.acc_620 = cls._ensure_account(
            "620.01 - Test FG COGS",
            parent_account=expenses_root,
            root_type="Expense",
            account_type="Cost of Goods Sold",
            is_group=0,
            account_number="620.01",
            account_currency="TRY",
        )
        cls.acc_621 = cls._ensure_account(
            "621.01 - Test RM COGS",
            parent_account=expenses_root,
            root_type="Expense",
            account_type="Cost of Goods Sold",
            is_group=0,
            account_number="621.01",
            account_currency="TRY",
        )
        cls.acc_710 = cls._ensure_account(
            "710.20 - Test Stock Adjustment",
            parent_account=expenses_root,
            root_type="Expense",
            account_type="Stock Adjustment",
            is_group=0,
            account_number="710.20",
            account_currency="TRY",
        )
        cls.acc_730_group = cls._ensure_account(
            "730.01 - Test Operating Group",
            parent_account=expenses_root,
            root_type="Expense",
            account_type="",
            is_group=1,
            account_number="730.01",
            account_currency="TRY",
        )
        cls.acc_731 = cls._ensure_account(
            "731.01 - Test Operating Leaf",
            parent_account=cls.acc_730_group,
            root_type="Expense",
            account_type="",
            is_group=0,
            account_number="731.01",
            account_currency="TRY",
        )

        frappe.db.set_value(
            "Company",
            RECLASS_TEST_COMPANY,
            {
                "enable_perpetual_inventory": 1,
                "default_inventory_account": cls.acc_150_1,
                "stock_adjustment_account": cls.acc_710,
                "cost_center": cls.cost_center,
            },
        )

        cls.wh_150_group = cls._ensure_warehouse(
            "_Test Reclass 150 URETIM", cls.acc_150_4, is_group=1
        )
        cls.wh_1501_child = cls._ensure_warehouse(
            "_Test Reclass 1501",
            cls.acc_150_1,
            is_group=0,
            parent_warehouse=cls.wh_150_group,
        )
        cls.wh_rm = cls._ensure_warehouse("_Test Reclass RM", cls.acc_150_1, is_group=0)
        cls.wh_w1x = cls._ensure_warehouse("_Test Reclass W1x", None, is_group=0)
        cls.wh_fg = cls._ensure_warehouse(
            "_Test Reclass 170-1", cls.acc_152_01, is_group=0
        )

        cls.customer = cls._ensure_customer("_Test Reclass Customer")
        cls.price_list = cls._ensure_price_list("_Test Reclass EUR Selling", "EUR")

    @classmethod
    def _ensure_cost_center(cls) -> str:
        cc_name = f"Main - {RECLASS_TEST_ABBR}"
        if frappe.db.exists("Cost Center", cc_name):
            return cc_name
        root_cc = frappe.db.get_value(
            "Cost Center", {"company": RECLASS_TEST_COMPANY, "is_group": 1}, "name"
        )
        if not root_cc:
            root_doc = frappe.get_doc(
                {
                    "doctype": "Cost Center",
                    "cost_center_name": RECLASS_TEST_COMPANY,
                    "company": RECLASS_TEST_COMPANY,
                    "is_group": 1,
                }
            )
            root_doc.insert(ignore_permissions=True)
            root_cc = root_doc.name
        cc_doc = frappe.get_doc(
            {
                "doctype": "Cost Center",
                "cost_center_name": "Main",
                "company": RECLASS_TEST_COMPANY,
                "parent_cost_center": root_cc,
                "is_group": 0,
            }
        )
        cc_doc.insert(ignore_permissions=True)
        return cc_doc.name

    @classmethod
    def _ensure_root_account(cls, fallback_name: str, root_type: str) -> str:
        fullname = f"{fallback_name} - {RECLASS_TEST_ABBR}"
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
            (RECLASS_TEST_COMPANY, root_type),
            pluck=True,
        )
        if rows:
            return rows[0]

        report_type = (
            "Balance Sheet"
            if root_type in ("Asset", "Liability", "Equity")
            else "Profit and Loss"
        )
        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": RECLASS_TEST_COMPANY,
                "account_name": fallback_name,
                "root_type": root_type,
                "report_type": report_type,
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
        account_currency: str = "TRY",
    ) -> str:
        existing = frappe.db.get_value(
            "Account",
            {"company": RECLASS_TEST_COMPANY, "account_number": account_number},
            "name",
        )
        if existing:
            return existing
        doc = frappe.get_doc(
            {
                "doctype": "Account",
                "company": RECLASS_TEST_COMPANY,
                "account_name": account_name,
                "account_number": account_number,
                "parent_account": parent_account,
                "root_type": root_type,
                "account_type": account_type,
                "is_group": is_group,
                "account_currency": account_currency,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    @classmethod
    def _ensure_warehouse(
        cls,
        warehouse_name: str,
        account: str | None,
        is_group: int = 0,
        parent_warehouse: str | None = None,
    ) -> str:
        fullname = f"{warehouse_name} - {RECLASS_TEST_ABBR}"
        if not frappe.db.exists("Warehouse", fullname):
            doc = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": warehouse_name,
                    "company": RECLASS_TEST_COMPANY,
                    "account": account,
                    "is_group": is_group,
                    "parent_warehouse": parent_warehouse,
                }
            )
            doc.insert(ignore_permissions=True)
            return doc.name
        frappe.db.set_value(
            "Warehouse",
            fullname,
            {"account": account, "parent_warehouse": parent_warehouse},
        )
        return fullname

    @classmethod
    def _ensure_customer(cls, customer_name: str) -> str:
        if frappe.db.exists("Customer", customer_name):
            return customer_name
        customer_group = (
            frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
            or "_Test Customer Group"
        )
        territory = (
            frappe.db.get_value("Territory", {"is_group": 0}, "name")
            or "All Territories"
        )
        doc = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": customer_name,
                "customer_type": "Company",
                "customer_group": customer_group,
                "territory": territory,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    @classmethod
    def _ensure_price_list(cls, price_list_name: str, currency: str) -> str:
        if frappe.db.exists("Price List", price_list_name):
            return price_list_name
        doc = frappe.get_doc(
            {
                "doctype": "Price List",
                "price_list_name": price_list_name,
                "currency": currency,
                "selling": 1,
                "enabled": 1,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _ensure_item_group(self, name: str, parent: str = "All Item Groups") -> str:
        if frappe.db.exists("Item Group", name):
            return name
        doc = frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": name,
                "parent_item_group": parent,
                "is_group": 1,
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _make_item(self, suffix: str, item_group: str | None = None) -> str:
        code = f"_Test Reclass {suffix} {self._tag}"
        doc = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": code,
                "item_name": code,
                "item_group": item_group or create_test_item_group(),
                "is_stock_item": 1,
                "stock_uom": "Nos",
                "has_batch_no": 0,
                "has_serial_no": 0,
                "valuation_method": "Moving Average",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _get_account_gl_balance(
        self, account: str, posting_date_upto: str | None = None
    ) -> float:
        filters = {
            "company": self.company,
            "account": account,
            "is_cancelled": 0,
        }
        if posting_date_upto:
            filters["posting_date"] = ["<=", posting_date_upto]
        rows = frappe.get_all("GL Entry", filters=filters, fields=["debit", "credit"])
        return flt(sum(flt(r.debit) - flt(r.credit) for r in rows), 2)

    def _get_account_currency_gl_balance(self, account: str) -> float:
        rows = frappe.get_all(
            "GL Entry",
            filters={"company": self.company, "account": account, "is_cancelled": 0},
            fields=["debit_in_account_currency", "credit_in_account_currency"],
        )
        return flt(
            sum(
                flt(r.debit_in_account_currency) - flt(r.credit_in_account_currency)
                for r in rows
            ),
            2,
        )

    def setUp(self):
        super().setUp()
        self.company = RECLASS_TEST_COMPANY
        self._tag = frappe.generate_hash(length=6)
        frappe.db.set_value(
            "Company",
            self.company,
            {
                "enable_perpetual_inventory": 1,
                "default_inventory_account": self.acc_150_1,
                "stock_adjustment_account": self.acc_710,
                "cost_center": self.cost_center,
            },
        )
        frappe.db.set_value("Warehouse", self.wh_1501_child, "account", self.acc_150_1)
        frappe.db.set_value("Warehouse", self.wh_150_group, "account", self.acc_150_4)
        frappe.clear_cache()

    def test_fix_accounting_master_defaults_dry_run_apply_and_idempotency(self):
        """Master defaults patch supports dry_run, fixes Company/Item Group defaults, and is idempotent."""
        self._ensure_item_group("HAMMADDELER")
        self._ensure_item_group("ÜRÜNLER")
        rm_sub = self._ensure_item_group(
            f"_Test RM Sub {self._tag}", parent="HAMMADDELER"
        )
        fg_sub = self._ensure_item_group(f"_Test FG Sub {self._tag}", parent="ÜRÜNLER")

        frappe.db.set_value(
            "Company",
            self.company,
            {
                "default_expense_account": self.acc_710,
                "default_operating_cost_account": self.acc_730_group,
            },
        )

        # Seed HAMMADDELER default with 710.20 + default_warehouse (warehouse must survive!)
        rm_parent_doc = frappe.get_doc("Item Group", "HAMMADDELER")
        rm_parent_doc.item_group_defaults = [
            row
            for row in rm_parent_doc.item_group_defaults
            if row.company != self.company
        ]
        rm_parent_doc.append(
            "item_group_defaults",
            {
                "company": self.company,
                "default_warehouse": self.wh_rm,
                "expense_account": self.acc_710,
            },
        )
        rm_parent_doc.save(ignore_permissions=True)

        rm_sub_doc = frappe.get_doc("Item Group", rm_sub)
        rm_sub_doc.append(
            "item_group_defaults",
            {
                "company": self.company,
                "default_warehouse": self.wh_rm,
                "expense_account": self.acc_621,
            },
        )
        rm_sub_doc.save(ignore_permissions=True)

        # Seed ÜRÜNLER parent with wrong expense_account (710.20) while fg_sub has no row
        fg_parent_doc = frappe.get_doc("Item Group", "ÜRÜNLER")
        fg_parent_doc.item_group_defaults = [
            row
            for row in fg_parent_doc.item_group_defaults
            if row.company != self.company
        ]
        fg_parent_doc.append(
            "item_group_defaults",
            {
                "company": self.company,
                "default_warehouse": self.wh_fg,
                "expense_account": self.acc_710,
            },
        )
        fg_parent_doc.save(ignore_permissions=True)

        # 1. Dry run leaves DB unchanged
        dry_res = fix_accounting_master_defaults(company=self.company, dry_run=True)
        self.assertTrue(dry_res["dry_run"])
        comp_dry = dry_res["companies"][self.company]
        self.assertEqual(len(comp_dry["company_defaults_updated"]), 2)
        self.assertEqual(comp_dry["rm_defaults_cleared_count"], 2)
        self.assertGreaterEqual(comp_dry["fg_defaults_updated_count"], 1)
        self.assertGreaterEqual(comp_dry["fg_defaults_appended_count"], 1)

        self.assertEqual(
            frappe.db.get_value("Company", self.company, "default_expense_account"),
            self.acc_710,
        )
        self.assertEqual(
            frappe.db.get_value(
                "Company", self.company, "default_operating_cost_account"
            ),
            self.acc_730_group,
        )

        # 2. Apply fixes
        apply_res = fix_accounting_master_defaults(company=self.company, dry_run=False)
        self.assertFalse(apply_res["dry_run"])
        self.assertEqual(
            frappe.db.get_value("Company", self.company, "default_expense_account"),
            self.acc_621,
        )
        self.assertEqual(
            frappe.db.get_value(
                "Company", self.company, "default_operating_cost_account"
            ),
            self.acc_731,
        )

        rm_parent_row = frappe.db.get_value(
            "Item Default",
            {
                "parenttype": "Item Group",
                "parent": "HAMMADDELER",
                "company": self.company,
            },
            ["expense_account", "default_warehouse"],
            as_dict=True,
        )
        self.assertIsNone(rm_parent_row.expense_account)
        self.assertEqual(rm_parent_row.default_warehouse, self.wh_rm)

        rm_sub_row = frappe.db.get_value(
            "Item Default",
            {"parenttype": "Item Group", "parent": rm_sub, "company": self.company},
            ["expense_account", "default_warehouse"],
            as_dict=True,
        )
        self.assertIsNone(rm_sub_row.expense_account)
        self.assertEqual(rm_sub_row.default_warehouse, self.wh_rm)

        fg_parent_row = frappe.db.get_value(
            "Item Default",
            {"parenttype": "Item Group", "parent": "ÜRÜNLER", "company": self.company},
            ["expense_account", "default_warehouse"],
            as_dict=True,
        )
        self.assertEqual(fg_parent_row.expense_account, self.acc_620)
        self.assertEqual(fg_parent_row.default_warehouse, self.wh_fg)

        fg_sub_exp = frappe.db.get_value(
            "Item Default",
            {"parenttype": "Item Group", "parent": fg_sub, "company": self.company},
            "expense_account",
        )
        self.assertEqual(fg_sub_exp, self.acc_620)

        # 3. Idempotent second run makes 0 changes
        second_res = fix_accounting_master_defaults(company=self.company, dry_run=False)
        self.assertEqual(second_res["total_company_fields_updated"], 0)
        self.assertEqual(second_res["total_rm_defaults_cleared"], 0)
        self.assertEqual(second_res["total_fg_defaults_updated"], 0)
        self.assertEqual(second_res["total_fg_defaults_appended"], 0)

    def test_post_2026_accounting_reclassifications_dry_run_apply_and_idempotency(self):
        """Reclassification patch computes all 5 steps accurately, clears 1501 WH, posts balanced JEs (incl. EUR), and skips re-runs."""
        rm_item = self._make_item("RM")
        fg_item = self._make_item("FG")

        # 1) Receipt 10 units @ 50 into 1501 child warehouse (500.00 TRY on 150.01.001)
        se_1501 = frappe.new_doc("Stock Entry")
        se_1501.purpose = "Material Receipt"
        se_1501.stock_entry_type = "Material Receipt"
        se_1501.company = self.company
        se_1501.posting_date = "2026-01-10"
        se_1501.set_posting_time = 1
        se_1501.append(
            "items",
            {
                "item_code": rm_item,
                "qty": 10.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.wh_1501_child,
                "basic_rate": 50.0,
                "cost_center": self.cost_center,
                "expense_account": self.acc_710,
            },
        )
        se_1501.insert(ignore_permissions=True)
        se_1501.submit()

        # Receipt RM into wh_rm (20 units @ 50 = 1000.00) and FG into wh_fg (10 units @ 50 = 500.00)
        se_seed = frappe.new_doc("Stock Entry")
        se_seed.purpose = "Material Receipt"
        se_seed.stock_entry_type = "Material Receipt"
        se_seed.company = self.company
        se_seed.posting_date = "2026-01-12"
        se_seed.set_posting_time = 1
        se_seed.append(
            "items",
            {
                "item_code": rm_item,
                "qty": 20.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.wh_rm,
                "basic_rate": 50.0,
                "cost_center": self.cost_center,
                "expense_account": self.acc_710,
            },
        )
        se_seed.append(
            "items",
            {
                "item_code": fg_item,
                "qty": 10.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.wh_fg,
                "basic_rate": 50.0,
                "cost_center": self.cost_center,
                "expense_account": self.acc_710,
            },
        )
        se_seed.insert(ignore_permissions=True)
        se_seed.submit()

        # 2) Classic Manufacture Stock Entry with 710.20 Debit (250.00) and 197.01.001 Credit (250.00)
        se_mfg = frappe.new_doc("Stock Entry")
        se_mfg.purpose = "Manufacture"
        se_mfg.stock_entry_type = "Manufacture"
        se_mfg.company = self.company
        se_mfg.posting_date = "2026-03-10"
        se_mfg.set_posting_time = 1
        se_mfg.from_bom = 0
        se_mfg.append(
            "items",
            {
                "item_code": rm_item,
                "qty": 5.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.wh_rm,
                "basic_rate": 50.0,
                "cost_center": self.cost_center,
                "expense_account": self.acc_710,
            },
        )
        se_mfg.append(
            "items",
            {
                "item_code": fg_item,
                "qty": 5.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "t_warehouse": self.wh_fg,
                "is_finished_item": 1,
                "basic_rate": 50.0,
                "cost_center": self.cost_center,
                "expense_account": self.acc_197,
            },
        )
        se_mfg.insert(ignore_permissions=True)
        se_mfg.submit()

        # 3) Jan/Feb Material Transfer to shelf W1x -> simulate net 710.20 Debit (150.00), 150.01.001 Credit
        se_mt = frappe.new_doc("Stock Entry")
        se_mt.purpose = "Material Transfer"
        se_mt.stock_entry_type = "Material Transfer"
        se_mt.company = self.company
        se_mt.posting_date = "2026-02-15"
        se_mt.set_posting_time = 1
        se_mt.append(
            "items",
            {
                "item_code": rm_item,
                "qty": 3.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": self.wh_rm,
                "t_warehouse": self.wh_w1x,
                "basic_rate": 50.0,
                "cost_center": self.cost_center,
                "expense_account": self.acc_710,
            },
        )
        se_mt.insert(ignore_permissions=True)
        se_mt.submit()
        # Simulate unmapped-shelf historical GL state: Dr 710.20 (150.00) / Cr 150.01.001 (150.00)
        # while stock sits in wh_w1x (which maps to 150.01.001 via default_inventory_account).
        frappe.db.sql(
            """
            DELETE FROM `tabGL Entry`
            WHERE voucher_type = 'Stock Entry'
              AND voucher_no = %s
            """,
            (se_mt.name,),
        )
        for account, against, debit, credit in (
            (self.acc_710, self.acc_150_1, 150.0, 0.0),
            (self.acc_150_1, self.acc_710, 0.0, 150.0),
        ):
            frappe.get_doc(
                {
                    "doctype": "GL Entry",
                    "company": self.company,
                    "posting_date": "2026-02-15",
                    "fiscal_year": "2026",
                    "voucher_type": "Stock Entry",
                    "voucher_no": se_mt.name,
                    "voucher_subtype": "Material Transfer",
                    "account": account,
                    "against": against,
                    "cost_center": self.cost_center,
                    "account_currency": "TRY",
                    "debit": debit,
                    "credit": credit,
                    "debit_in_account_currency": debit,
                    "credit_in_account_currency": credit,
                    "is_opening": "No",
                    "is_cancelled": 0,
                }
            ).db_insert()

        # 4 & 5) Delivery Note with 710.20 (100.00), 600.01.001 TRY (100.00), and 601.01.002 EUR (150.00 TRY / 4.29 EUR)
        dn = frappe.new_doc("Delivery Note")
        dn.company = self.company
        dn.customer = self.customer
        dn.posting_date = "2026-06-15"
        dn.set_posting_time = 1
        dn.currency = "EUR"
        dn.conversion_rate = 35.0
        dn.selling_price_list = self.price_list
        dn.price_list_currency = "EUR"
        dn.plc_conversion_rate = 35.0
        dn.append(
            "items",
            {
                "item_code": rm_item,
                "qty": 2.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "rate": 10.0,
                "warehouse": self.wh_rm,
                "cost_center": self.cost_center,
                "expense_account": self.acc_710,
            },
        )
        dn.append(
            "items",
            {
                "item_code": fg_item,
                "qty": 2.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "rate": 10.0,
                "warehouse": self.wh_fg,
                "cost_center": self.cost_center,
                "expense_account": self.acc_600,
            },
        )
        dn.append(
            "items",
            {
                "item_code": fg_item,
                "qty": 3.0,
                "uom": "Nos",
                "stock_uom": "Nos",
                "conversion_factor": 1.0,
                "rate": 10.0,
                "warehouse": self.wh_fg,
                "cost_center": self.cost_center,
                "expense_account": self.acc_601,
            },
        )
        dn.insert(ignore_permissions=True)
        dn.submit()

        # Verify dry_run=True computes all 5 amounts without mutating DB
        dry_res = post_2026_accounting_reclassifications(
            company=self.company,
            posting_date="2026-11-27",
            fiscal_year_start="2026-01-01",
            fiscal_year_end="2026-12-31",
            dry_run=True,
        )
        self.assertTrue(dry_res["dry_run"])
        self.assertEqual(dry_res["total_journal_entries_created"], 0)
        self.assertEqual(dry_res["errors"], [])

        steps_dry = dry_res["companies"][self.company]["steps"]
        self.assertEqual(steps_dry["step_1_1501_wh"]["amount"], 500.0)
        self.assertEqual(steps_dry["step_2_mfg_mirror"]["amount"], 250.0)
        self.assertEqual(steps_dry["step_3_mt_janfeb"]["amount"], 150.0)
        self.assertEqual(steps_dry["step_4_dn_710"]["amount"], 100.0)
        self.assertEqual(steps_dry["step_5_dn_income"]["amount"], 250.0)
        self.assertTrue(steps_dry["step_5_dn_income"]["multi_currency"])

        # Warehouse account must remain untouched after dry_run
        self.assertEqual(
            frappe.db.get_value("Warehouse", self.wh_1501_child, "account"),
            self.acc_150_1,
        )

        bal_150_1_before = self._get_account_gl_balance(self.acc_150_1)
        bal_150_4_before = self._get_account_gl_balance(self.acc_150_4)

        # Apply all 5 reclassifications
        apply_res = post_2026_accounting_reclassifications(
            company=self.company,
            posting_date="2026-11-27",
            fiscal_year_start="2026-01-01",
            fiscal_year_end="2026-12-31",
            dry_run=False,
        )
        self.assertFalse(apply_res["dry_run"])
        self.assertEqual(apply_res["errors"], [])
        self.assertEqual(apply_res["total_journal_entries_created"], 5)

        steps_apply = apply_res["companies"][self.company]["steps"]
        for key in (
            "step_1_1501_wh",
            "step_2_mfg_mirror",
            "step_3_mt_janfeb",
            "step_4_dn_710",
            "step_5_dn_income",
        ):
            self.assertEqual(steps_apply[key]["status"], "applied")
            je_name = steps_apply[key]["journal_entry"]
            self.assertEqual(
                frappe.db.get_value("Journal Entry", je_name, "docstatus"), 1
            )

        # 1501 child warehouse account cleared to None
        self.assertIsNone(
            frappe.db.get_value("Warehouse", self.wh_1501_child, "account")
        )

        # Balances zeroed / shifted properly
        self.assertEqual(self._get_account_gl_balance(self.acc_197), 0.0)
        self.assertEqual(self._get_account_gl_balance(self.acc_600), 0.0)
        self.assertEqual(self._get_account_gl_balance(self.acc_601), 0.0)
        self.assertEqual(self._get_account_currency_gl_balance(self.acc_601), 0.0)
        self.assertEqual(self._get_account_gl_balance(self.acc_620), 250.0)
        self.assertEqual(self._get_account_gl_balance(self.acc_621), 100.0)

        # 150.01.001 shifted -500 (Step 1) +150 (Step 3) = -350; 150.01.004 shifted +500
        self.assertEqual(
            self._get_account_gl_balance(self.acc_150_1),
            flt(bal_150_1_before - 500.0 + 150.0, 2),
        )
        self.assertEqual(
            self._get_account_gl_balance(self.acc_150_4),
            flt(bal_150_4_before + 500.0, 2),
        )

        # Second run is strictly idempotent and creates 0 new JEs
        second_res = post_2026_accounting_reclassifications(
            company=self.company,
            posting_date="2026-11-27",
            fiscal_year_start="2026-01-01",
            fiscal_year_end="2026-12-31",
            dry_run=False,
        )
        self.assertEqual(second_res["total_journal_entries_created"], 0)
        self.assertEqual(second_res["errors"], [])
        steps_second = second_res["companies"][self.company]["steps"]
        for key in (
            "step_1_1501_wh",
            "step_2_mfg_mirror",
            "step_3_mt_janfeb",
            "step_4_dn_710",
            "step_5_dn_income",
        ):
            self.assertEqual(steps_second[key]["status"], "skipped")
            self.assertEqual(steps_second[key]["reason"], "already_posted")
