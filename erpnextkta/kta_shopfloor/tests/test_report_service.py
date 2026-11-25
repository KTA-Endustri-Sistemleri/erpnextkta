# Copyright (c) 2026, KTA and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.utils import flt

from erpnextkta.kta_shopfloor.services.report_service import (
    get_material_shortage_report,
    get_operation_completion_report,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_erpnext_operation,
    create_test_item_group,
    create_test_warehouse,
    create_test_workstation,
    setup_test_fiscal_years,
)


class TestReportService(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        self.uid = frappe.generate_hash(length=6)
        self.company = self._create_isolated_company(
            f"_Test Report Co {self.uid}", f"TR{self.uid[:4]}"
        )
        self.other_company = self._create_isolated_company(
            f"_Test Report Other Co {self.uid}", f"TO{self.uid[:4]}"
        )
        self.item_group = create_test_item_group()
        self.fg_item = self._create_item(
            f"_Test Rpt FG {self.uid}", f"Test Report FG Item {self.uid}"
        )
        self.other_item = self._create_item(
            f"_Test Rpt FG2 {self.uid}", f"Test Report Second Item {self.uid}"
        )
        self.wip_wh = create_test_warehouse(self.company, f"_Test Rpt WIP {self.uid}")
        self.ws_a = create_test_workstation(f"_Test Rpt WS A {self.uid}")
        self.ws_b = create_test_workstation(f"_Test Rpt WS B {self.uid}")
        self.op_a = create_test_erpnext_operation(
            f"_Test Rpt OP A {self.uid}", self.ws_a
        )
        self.op_b = create_test_erpnext_operation(
            f"_Test Rpt OP B {self.uid}", self.ws_b
        )
        self.op_c = create_test_erpnext_operation(
            f"_Test Rpt OP C {self.uid}", self.ws_a
        )

    def _create_isolated_company(self, company_name: str, abbr: str) -> str:
        if not frappe.db.exists("Company", company_name):
            frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": company_name,
                    "abbr": abbr,
                    "default_currency": "TRY",
                    "country": "Turkey",
                }
            ).insert(ignore_permissions=True)
        setup_test_fiscal_years(company_name)
        return company_name

    def _create_item(self, item_code: str, item_name: str) -> str:
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": item_name,
                    "item_group": self.item_group,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": 0,
                    "has_serial_no": 0,
                }
            ).insert(ignore_permissions=True)
        return item_code

    def _create_warehouse(self, company: str, wh_name: str) -> str:
        abbr = frappe.db.get_value("Company", company, "abbr") or ""
        expected_name = f"{wh_name} - {abbr}" if abbr else wh_name
        existing = frappe.db.get_value("Warehouse", expected_name, "name")
        if existing:
            return existing
        wh = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": wh_name,
                "company": company,
                "is_group": 0,
                "disabled": 0,
            }
        ).insert(ignore_permissions=True)
        return wh.name

    def _set_bin_qty(self, item_code: str, warehouse: str, actual_qty: float) -> None:
        bin_name = frappe.db.get_value(
            "Bin", {"item_code": item_code, "warehouse": warehouse}, "name"
        )
        if bin_name:
            frappe.db.set_value("Bin", bin_name, "actual_qty", flt(actual_qty))
        else:
            frappe.get_doc(
                {
                    "doctype": "Bin",
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "actual_qty": flt(actual_qty),
                }
            ).insert(ignore_permissions=True)

    def _create_wo(
        self,
        *,
        company: str | None = None,
        item_code: str | None = None,
        qty: float = 100.0,
        produced_qty: float = 0.0,
        docstatus: int = 1,
        status: str = "In Process",
        operations: list[dict] | None = None,
        required_items: list[dict] | None = None,
        source_warehouse: str | None = None,
        wip_warehouse: str | None = None,
        custom_released_with_shortage: int = 0,
        planned_start_date: str | None = None,
        expected_delivery_date: str | None = None,
        creation: str | None = None,
    ):
        comp = company or self.company
        item = item_code or self.fg_item
        resolved_wip = wip_warehouse or self.wip_wh
        wo_data = {
            "doctype": "Work Order",
            "naming_series": "MFG-WO-.YYYY.-",
            "production_item": item,
            "item_name": frappe.db.get_value("Item", item, "item_name") or item,
            "stock_uom": "Nos",
            "qty": qty,
            "produced_qty": produced_qty,
            "company": comp,
            "wip_warehouse": resolved_wip,
            "fg_warehouse": resolved_wip,
            "skip_transfer": 1,
            "status": status,
            "operations": operations or [],
            "required_items": required_items or [],
        }
        if source_warehouse:
            wo_data["source_warehouse"] = source_warehouse
        if planned_start_date:
            wo_data["planned_start_date"] = planned_start_date
        if expected_delivery_date:
            wo_data["expected_delivery_date"] = expected_delivery_date

        wo = frappe.get_doc(wo_data)
        wo.flags.ignore_permissions = True
        wo.flags.ignore_mandatory = True
        wo.flags.ignore_links = True
        wo.insert(ignore_permissions=True)
        updates = {}
        if docstatus != 0:
            updates.update(
                {
                    "docstatus": docstatus,
                    "status": status,
                    "produced_qty": produced_qty,
                }
            )
            wo.docstatus = docstatus
            wo.status = status
        if frappe.db.has_column("Work Order", "custom_released_with_shortage"):
            updates["custom_released_with_shortage"] = custom_released_with_shortage
        if creation:
            updates["creation"] = creation
        if updates:
            frappe.db.set_value(
                "Work Order",
                wo.name,
                updates,
                update_modified=False,
            )
        return wo

    def _create_co11n(
        self,
        wo_name: str,
        operation: str,
        yield_qty: float,
        *,
        docstatus: int = 1,
        is_final: int = 0,
        posting_date: str = "2026-11-24",
        posting_time: str = "09:30:00",
        confirmed_by: str = "Administrator",
        stock_entry: str | None = None,
    ):
        conf = frappe.get_doc(
            {
                "doctype": "KTA Production Confirmation",
                "work_order": wo_name,
                "operation": operation,
                "yield_qty": yield_qty,
                "is_final_confirmation": is_final,
                "posting_date": posting_date,
                "posting_time": posting_time,
                "confirmed_by": confirmed_by,
                "stock_entry": stock_entry,
            }
        )
        conf.flags.ignore_permissions = True
        conf.flags.ignore_links = True
        conf.insert(ignore_permissions=True)
        if docstatus == 1:
            conf.submit()
        elif docstatus == 2:
            conf.submit()
            conf.cancel()
        return conf

    def _insert_standalone_manufacture_se(
        self,
        wo_name: str,
        fg_qty: float,
        posting_date: str = "2026-11-22",
        posting_time: str = "08:15:00",
    ) -> str:
        se_name = f"TEST-SE-RPT-{frappe.generate_hash(length=6)}"
        frappe.db.sql(
            """
            INSERT INTO `tabStock Entry` (
                name, docstatus, purpose, stock_entry_type, work_order, company,
                fg_completed_qty, posting_date, posting_time, owner,
                creation, modified, modified_by
            ) VALUES (
                %s, 1, 'Manufacture', 'Manufacture', %s, %s,
                %s, %s, %s, 'Administrator',
                NOW(), NOW(), 'Administrator'
            )
            """,
            (se_name, wo_name, self.company, fg_qty, posting_date, posting_time),
        )
        return se_name

    def test_active_wo_scope_excludes_non_active_across_all_status_filters(self):
        """Exclude Draft, Completed, Closed, Cancelled, Stopped WOs under all status filters;
        include zero-progress active ops only in 'unconfirmed' and 'all'."""
        self._create_wo(
            docstatus=0,
            status="Draft",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 50.0,
                    "time_in_mins": 10.0,
                }
            ],
        )
        self._create_wo(
            docstatus=1,
            status="Completed",
            produced_qty=100.0,
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "time_in_mins": 10.0,
                }
            ],
        )
        self._create_wo(
            docstatus=1,
            status="Closed",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 50.0,
                    "time_in_mins": 10.0,
                }
            ],
        )
        self._create_wo(
            docstatus=2,
            status="Cancelled",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 50.0,
                    "time_in_mins": 10.0,
                }
            ],
        )
        self._create_wo(
            docstatus=1,
            status="Stopped",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 50.0,
                    "time_in_mins": 10.0,
                }
            ],
        )

        wo_not_started = self._create_wo(
            docstatus=1,
            status="Not Started",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 0.0,
                    "time_in_mins": 10.0,
                },
            ],
        )
        wo_in_process = self._create_wo(
            docstatus=1,
            status="In Process",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 40.0,
                    "time_in_mins": 10.0,
                }
            ],
        )
        active_wos = {wo_not_started.name, wo_in_process.name}

        for sf in ("completed", "partial", "unconfirmed", "all"):
            res = get_operation_completion_report(
                status_filter=sf, company=self.company
            )
            self.assertTrue(
                all(r["work_order"] in active_wos for r in res["rows"]),
                f"Non-active WO leaked under status_filter={sf}",
            )

        res_completed = get_operation_completion_report(
            status_filter="completed", company=self.company
        )
        self.assertEqual(
            {(r["work_order"], r["operation"]) for r in res_completed["rows"]},
            {(wo_not_started.name, self.op_a)},
        )

        res_partial = get_operation_completion_report(
            status_filter="partial", company=self.company
        )
        self.assertEqual(
            {(r["work_order"], r["operation"]) for r in res_partial["rows"]},
            {(wo_in_process.name, self.op_a)},
        )

        res_unconfirmed = get_operation_completion_report(
            status_filter="unconfirmed", company=self.company
        )
        self.assertEqual(
            {(r["work_order"], r["operation"]) for r in res_unconfirmed["rows"]},
            {(wo_not_started.name, self.op_b)},
        )
        unconf_row = res_unconfirmed["rows"][0]
        self.assertEqual(unconf_row["status"], "unconfirmed")
        self.assertEqual(unconf_row["source_type"], "none")
        self.assertEqual(unconf_row["last_posting_date"], "")
        self.assertEqual(unconf_row["confirmation_count"], 0)

        res_all = get_operation_completion_report(
            status_filter="all", company=self.company
        )
        self.assertEqual(
            {(r["work_order"], r["operation"]) for r in res_all["rows"]},
            {
                (wo_not_started.name, self.op_a),
                (wo_not_started.name, self.op_b),
                (wo_in_process.name, self.op_a),
            },
        )

    def test_status_filter_counts_summary_and_invalid_filter(self):
        """Verify pre-filter counts/summary vs post-filter summary and invalid status_filter error."""
        wo1 = self._create_wo(
            qty=100.0,
            status="In Process",
            creation="2026-11-20 08:00:00.123456",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "status": "Completed",
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 30.0,
                    "status": "Work in Progress",
                    "time_in_mins": 10.0,
                },
            ],
        )
        self._create_co11n(
            wo1.name,
            self.op_a,
            60.0,
            posting_date="2026-11-20",
            posting_time="08:00:00",
        )
        conf_wo1_op_a_2 = self._create_co11n(
            wo1.name,
            self.op_a,
            40.0,
            posting_date="2026-11-21",
            posting_time="09:15:05",
        )
        self._create_co11n(
            wo1.name,
            self.op_b,
            30.0,
            posting_date="2026-11-21",
            posting_time="10:00:00",
        )

        wo2 = self._create_wo(
            qty=200.0,
            status="In Process",
            creation="2026-11-25 10:15:30.654321",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 120.0,
                    "status": "Completed",
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 50.0,
                    "status": "Work in Progress",
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_c,
                    "workstation": self.ws_a,
                    "sequence_id": 3,
                    "completed_qty": 0.0,
                    "status": "Pending",
                    "time_in_mins": 10.0,
                },
            ],
        )
        # Short-close with is_final=1 -> treated as completed (100%)
        self._create_co11n(
            wo2.name,
            self.op_a,
            120.0,
            is_final=1,
            posting_date="2026-11-22",
            posting_time="11:00:00",
        )
        self._create_co11n(
            wo2.name,
            self.op_b,
            50.0,
            posting_date="2026-11-23",
            posting_time="12:00:00",
        )

        expected_counts = {
            "completed": 2,
            "partial": 2,
            "unconfirmed": 1,
            "shortage": 0,
            "all": 5,
        }

        res_completed = get_operation_completion_report(
            status_filter="completed", company=self.company
        )
        self.assertEqual(res_completed["counts"], expected_counts)
        self.assertEqual(
            res_completed["counts"]["all"],
            res_completed["counts"]["completed"]
            + res_completed["counts"]["partial"]
            + res_completed["counts"]["unconfirmed"],
        )
        self.assertEqual(res_completed["summary"]["completed_operations"], 2)
        self.assertEqual(res_completed["summary"]["partial_operations"], 2)
        self.assertEqual(res_completed["summary"]["unconfirmed_operations"], 1)
        self.assertEqual(res_completed["summary"]["shortage_operations"], 0)
        self.assertEqual(res_completed["summary"]["unique_work_orders"], 2)
        self.assertEqual(flt(res_completed["summary"]["total_confirmed_qty"]), 220.0)
        self.assertEqual(len(res_completed["rows"]), 2)
        self.assertEqual(res_completed["rows"][0]["work_order"], wo2.name)
        self.assertEqual(res_completed["rows"][0]["wo_creation"], "2026-11-25 10:15:30")
        self.assertEqual(res_completed["rows"][0]["has_final_confirmation"], 1)
        self.assertEqual(res_completed["rows"][0]["final_confirmation_count"], 1)
        self.assertEqual(flt(res_completed["rows"][0]["completion_pct"]), 100.0)
        self.assertEqual(res_completed["rows"][1]["work_order"], wo1.name)
        self.assertEqual(res_completed["rows"][1]["wo_creation"], "2026-11-20 08:00:00")
        self.assertEqual(
            res_completed["rows"][1]["last_confirmation"], conf_wo1_op_a_2.name
        )
        self.assertEqual(res_completed["rows"][1]["last_posting_time"], "09:15:05")
        self.assertEqual(res_completed["rows"][1]["confirmation_count"], 2)

        res_partial = get_operation_completion_report(
            status_filter="partial", company=self.company
        )
        self.assertEqual(res_partial["counts"], expected_counts)
        self.assertEqual(res_partial["summary"]["completed_operations"], 2)
        self.assertEqual(res_partial["summary"]["partial_operations"], 2)
        self.assertEqual(res_partial["summary"]["unconfirmed_operations"], 1)
        self.assertEqual(res_partial["summary"]["unique_work_orders"], 2)
        self.assertEqual(flt(res_partial["summary"]["total_confirmed_qty"]), 80.0)
        self.assertEqual(len(res_partial["rows"]), 2)
        self.assertTrue(all(r["status"] == "partial" for r in res_partial["rows"]))
        self.assertEqual(flt(res_partial["rows"][0]["completion_pct"]), 25.0)
        self.assertEqual(flt(res_partial["rows"][1]["completion_pct"]), 30.0)

        res_unconfirmed = get_operation_completion_report(
            status_filter="unconfirmed", company=self.company
        )
        self.assertEqual(res_unconfirmed["counts"], expected_counts)
        self.assertEqual(res_unconfirmed["summary"]["unconfirmed_operations"], 1)
        self.assertEqual(res_unconfirmed["summary"]["unique_work_orders"], 1)
        self.assertEqual(flt(res_unconfirmed["summary"]["total_confirmed_qty"]), 0.0)
        self.assertEqual(len(res_unconfirmed["rows"]), 1)
        self.assertEqual(res_unconfirmed["rows"][0]["operation"], self.op_c)
        self.assertEqual(res_unconfirmed["rows"][0]["status"], "unconfirmed")
        self.assertEqual(res_unconfirmed["rows"][0]["source_type"], "none")
        self.assertEqual(res_unconfirmed["rows"][0]["last_posting_date"], "")
        self.assertEqual(res_unconfirmed["rows"][0]["confirmation_count"], 0)

        res_all = get_operation_completion_report(
            status_filter="all", company=self.company
        )
        self.assertEqual(len(res_all["rows"]), 5)
        self.assertEqual(
            [(r["work_order"], r["operation"]) for r in res_all["rows"]],
            [
                (wo2.name, self.op_a),
                (wo2.name, self.op_b),
                (wo2.name, self.op_c),
                (wo1.name, self.op_a),
                (wo1.name, self.op_b),
            ],
        )
        self.assertEqual(flt(res_all["summary"]["total_confirmed_qty"]), 300.0)

        with self.assertRaises(frappe.ValidationError):
            get_operation_completion_report(
                status_filter="invalid_status", company=self.company
            )

    def test_filters_and_filter_options(self):
        """Verify operation, workstation, date range, search, company filters and filter_options."""
        wo1 = self._create_wo(
            item_code=self.fg_item,
            qty=100.0,
            status="In Process",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 50.0,
                    "time_in_mins": 10.0,
                },
            ],
        )
        self._create_co11n(wo1.name, self.op_a, 100.0, posting_date="2026-11-10")
        self._create_co11n(wo1.name, self.op_b, 50.0, posting_date="2026-11-20")

        wo2 = self._create_wo(
            item_code=self.other_item,
            qty=100.0,
            status="In Process",
            operations=[
                {
                    "operation": self.op_c,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "time_in_mins": 10.0,
                }
            ],
        )
        self._create_co11n(wo2.name, self.op_c, 100.0, posting_date="2026-11-15")

        # Another company's WO must not appear when filtering by self.company
        wo_other_co = self._create_wo(
            company=self.other_company,
            qty=100.0,
            status="In Process",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "time_in_mins": 10.0,
                }
            ],
        )
        self._create_co11n(wo_other_co.name, self.op_a, 100.0)

        # Operation filter preserves full filter_options for the company
        res_op = get_operation_completion_report(
            status_filter="all",
            operation=self.op_b,
            company=self.company,
        )
        self.assertEqual(len(res_op["rows"]), 1)
        self.assertEqual(res_op["rows"][0]["operation"], self.op_b)
        self.assertEqual(
            res_op["counts"],
            {
                "completed": 0,
                "partial": 1,
                "unconfirmed": 0,
                "shortage": 0,
                "all": 1,
            },
        )
        self.assertEqual(
            res_op["filter_options"]["operations"],
            sorted([self.op_a, self.op_b, self.op_c]),
        )
        self.assertEqual(
            res_op["filter_options"]["workstations"],
            sorted([self.ws_a, self.ws_b]),
        )

        # Workstation filter
        res_ws = get_operation_completion_report(
            status_filter="all",
            workstation=self.ws_a,
            company=self.company,
        )
        self.assertEqual(len(res_ws["rows"]), 2)
        self.assertTrue(all(r["workstation"] == self.ws_a for r in res_ws["rows"]))

        # Date range filter (inclusive)
        res_dates = get_operation_completion_report(
            status_filter="all",
            from_date="2026-11-12",
            to_date="2026-11-18",
            company=self.company,
        )
        self.assertEqual(len(res_dates["rows"]), 1)
        self.assertEqual(res_dates["rows"][0]["work_order"], wo2.name)

        # Case-insensitive search across item_name
        res_search = get_operation_completion_report(
            status_filter="all",
            search=f"second item {self.uid}".lower(),
            company=self.company,
        )
        self.assertEqual(len(res_search["rows"]), 1)
        self.assertEqual(res_search["rows"][0]["work_order"], wo2.name)

        # Default company resolution when company=None
        prev_default = frappe.db.get_default("company")
        self.addCleanup(frappe.db.set_default, "company", prev_default)
        frappe.db.set_default("company", self.other_company)
        res_default_co = get_operation_completion_report(status_filter="all")
        self.assertEqual(
            [r["work_order"] for r in res_default_co["rows"]], [wo_other_co.name]
        )

    def test_co11n_docstatus_filtering_and_no_co11n_completed_ops(self):
        """Exclude Draft and Cancelled CO11N entries; include ops completed without CO11N."""
        wo = self._create_wo(
            qty=100.0,
            status="In Process",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 60.0,
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 100.0,
                    "time_in_mins": 10.0,
                },
            ],
        )
        # OP_A: 1 submitted (60), 1 draft (20), 1 cancelled (15)
        self._create_co11n(wo.name, self.op_a, 60.0, docstatus=1)
        self._create_co11n(wo.name, self.op_a, 20.0, docstatus=0)
        self._create_co11n(wo.name, self.op_a, 15.0, docstatus=2)

        # OP_B: 0 submitted CO11N (1 cancelled CO11N only)
        self._create_co11n(wo.name, self.op_b, 50.0, docstatus=2)

        # Legacy standalone Manufacture SE + an unconfirmed operation on the same WO
        wo_legacy = self._create_wo(
            qty=100.0,
            produced_qty=40.0,
            status="In Process",
            operations=[
                {
                    "operation": self.op_c,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 40.0,
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 0.0,
                    "time_in_mins": 10.0,
                },
            ],
        )
        self._insert_standalone_manufacture_se(wo_legacy.name, 40.0)

        res = get_operation_completion_report(status_filter="all", company=self.company)
        by_key = {(r["work_order"], r["operation"]): r for r in res["rows"]}

        row_a = by_key[(wo.name, self.op_a)]
        self.assertEqual(flt(row_a["confirmed_qty"]), 60.0)
        self.assertEqual(row_a["confirmation_count"], 1)
        self.assertFalse(row_a["is_completed"])
        self.assertEqual(row_a["source_type"], "co11n")

        row_b = by_key[(wo.name, self.op_b)]
        self.assertEqual(flt(row_b["confirmed_qty"]), 0.0)
        self.assertEqual(row_b["confirmation_count"], 0)
        self.assertEqual(flt(row_b["completed_qty"]), 100.0)
        self.assertTrue(row_b["is_completed"])
        self.assertEqual(flt(row_b["completion_pct"]), 100.0)

        row_legacy = by_key[(wo_legacy.name, self.op_c)]
        self.assertEqual(row_legacy["confirmation_count"], 0)
        self.assertEqual(flt(row_legacy["legacy_manufacture_qty"]), 40.0)
        self.assertEqual(row_legacy["source_type"], "legacy")
        self.assertEqual(row_legacy["last_posting_date"], "2026-11-22")

        row_legacy_unconf = by_key[(wo_legacy.name, self.op_b)]
        self.assertEqual(row_legacy_unconf["status"], "unconfirmed")
        self.assertEqual(row_legacy_unconf["source_type"], "none")
        self.assertEqual(row_legacy_unconf["last_posting_date"], "")
        self.assertEqual(row_legacy_unconf["last_posting_time"], "")
        self.assertEqual(row_legacy_unconf["last_confirmation_at"], "")
        self.assertEqual(row_legacy_unconf["last_confirmed_by"], "")
        self.assertIsNone(row_legacy_unconf["last_confirmation"])
        self.assertEqual(row_legacy_unconf["stock_entry_count"], 0)
        self.assertEqual(row_legacy_unconf["confirmation_count"], 0)

    def test_permissions_enforced(self):
        """Missing Work Order or KTA Production Confirmation read permission raises PermissionError."""

        def deny_wo_read(doctype, ptype="read", *args, **kwargs):
            if doctype == "Work Order" and kwargs.get("throw"):
                raise frappe.PermissionError("No WO read")
            return True

        with (
            patch(
                "erpnextkta.kta_shopfloor.services.report_service.frappe.has_permission",
                side_effect=deny_wo_read,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            get_operation_completion_report(company=self.company)

        def deny_conf_read(doctype, ptype="read", *args, **kwargs):
            if doctype == "KTA Production Confirmation" and kwargs.get("throw"):
                raise frappe.PermissionError("No Confirmation read")
            return True

        with (
            patch(
                "erpnextkta.kta_shopfloor.services.report_service.frappe.has_permission",
                side_effect=deny_conf_read,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            get_operation_completion_report(company=self.company)

    def test_query_count_bounded_no_n_plus_one(self):
        """SQL query count remains bounded (<= 6) regardless of active WO / operation volume."""
        for idx in range(5):
            wo = self._create_wo(
                qty=100.0,
                status="In Process",
                operations=[
                    {
                        "operation": op,
                        "workstation": self.ws_a,
                        "sequence_id": seq,
                        "completed_qty": 100.0 if seq < 3 else 50.0,
                        "time_in_mins": 10.0,
                    }
                    for seq, op in enumerate((self.op_a, self.op_b, self.op_c), start=1)
                ],
            )
            for op in (self.op_a, self.op_b, self.op_c):
                self._create_co11n(
                    wo.name,
                    op,
                    50.0 + idx,
                    posting_date="2026-11-24",
                )

        with self.assertQueryCount(6):
            res = get_operation_completion_report(
                status_filter="all", company=self.company
            )

        self.assertEqual(len(res["rows"]), 15)
        self.assertEqual(res["summary"]["unique_work_orders"], 5)

    def test_only_shortage_filtering_and_counts(self):
        """Verify custom_released_with_shortage, only_shortage filter, counts, and fallback."""
        # Empty-company early return also exposes shortage keys
        res_empty = get_operation_completion_report(
            status_filter="all", company=self.other_company, only_shortage=1
        )
        self.assertEqual(res_empty["rows"], [])
        self.assertEqual(
            res_empty["counts"],
            {
                "completed": 0,
                "partial": 0,
                "unconfirmed": 0,
                "shortage": 0,
                "all": 0,
            },
        )
        self.assertEqual(res_empty["summary"]["shortage_operations"], 0)

        wo_shortage = self._create_wo(
            qty=100.0,
            status="In Process",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "status": "Completed",
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 40.0,
                    "status": "Work in Progress",
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_c,
                    "workstation": self.ws_a,
                    "sequence_id": 3,
                    "completed_qty": 0.0,
                    "status": "Pending",
                    "time_in_mins": 10.0,
                },
            ],
        )
        self._create_co11n(wo_shortage.name, self.op_a, 100.0)
        self._create_co11n(wo_shortage.name, self.op_b, 40.0)

        wo_normal = self._create_wo(
            qty=100.0,
            status="In Process",
            operations=[
                {
                    "operation": self.op_a,
                    "workstation": self.ws_a,
                    "sequence_id": 1,
                    "completed_qty": 100.0,
                    "status": "Completed",
                    "time_in_mins": 10.0,
                },
                {
                    "operation": self.op_b,
                    "workstation": self.ws_b,
                    "sequence_id": 2,
                    "completed_qty": 0.0,
                    "status": "Pending",
                    "time_in_mins": 10.0,
                },
            ],
        )
        self._create_co11n(wo_normal.name, self.op_a, 100.0)

        has_col = frappe.db.has_column("Work Order", "custom_released_with_shortage")
        if has_col:
            frappe.db.set_value(
                "Work Order",
                wo_shortage.name,
                "custom_released_with_shortage",
                1,
                update_modified=False,
            )
            frappe.db.set_value(
                "Work Order",
                wo_normal.name,
                "custom_released_with_shortage",
                0,
                update_modified=False,
            )

            res_all = get_operation_completion_report(
                status_filter="all", company=self.company
            )
            self.assertEqual(
                res_all["counts"],
                {
                    "completed": 2,
                    "partial": 1,
                    "unconfirmed": 2,
                    "shortage": 3,
                    "all": 5,
                },
            )
            self.assertEqual(res_all["summary"]["shortage_operations"], 3)
            for row in res_all["rows"]:
                expected_flag = 1 if row["work_order"] == wo_shortage.name else 0
                self.assertEqual(row["custom_released_with_shortage"], expected_flag)

            res_shortage_all = get_operation_completion_report(
                status_filter="all", company=self.company, only_shortage=1
            )
            self.assertEqual(len(res_shortage_all["rows"]), 3)
            self.assertTrue(
                all(
                    r["work_order"] == wo_shortage.name
                    and r["custom_released_with_shortage"] == 1
                    for r in res_shortage_all["rows"]
                )
            )
            self.assertEqual(
                res_shortage_all["counts"],
                {
                    "completed": 1,
                    "partial": 1,
                    "unconfirmed": 1,
                    "shortage": 3,
                    "all": 3,
                },
            )
            self.assertEqual(res_shortage_all["summary"]["shortage_operations"], 3)
            self.assertEqual(res_shortage_all["summary"]["unique_work_orders"], 1)
            self.assertEqual(
                flt(res_shortage_all["summary"]["total_confirmed_qty"]), 140.0
            )

            res_shortage_unconf = get_operation_completion_report(
                status_filter="unconfirmed", company=self.company, only_shortage=1
            )
            self.assertEqual(len(res_shortage_unconf["rows"]), 1)
            self.assertEqual(res_shortage_unconf["rows"][0]["operation"], self.op_c)
            self.assertEqual(
                res_shortage_unconf["rows"][0]["custom_released_with_shortage"], 1
            )
            self.assertEqual(res_shortage_unconf["counts"]["shortage"], 3)
            self.assertEqual(res_shortage_unconf["summary"]["shortage_operations"], 3)
            self.assertEqual(
                flt(res_shortage_unconf["summary"]["total_confirmed_qty"]), 0.0
            )

        # Fallback when Work Order.custom_released_with_shortage column is absent
        with patch(
            "erpnextkta.kta_shopfloor.services.report_service.frappe.db.has_column",
            return_value=False,
        ):
            res_fallback = get_operation_completion_report(
                status_filter="all", company=self.company, only_shortage=1
            )
            self.assertEqual(res_fallback["rows"], [])
            self.assertEqual(res_fallback["counts"]["shortage"], 0)
            self.assertEqual(res_fallback["summary"]["shortage_operations"], 0)

    def test_shortage_report_excludes_non_active_and_non_shortage_wos(self):
        """Exclude Draft, Completed, Closed, Cancelled, Stopped WOs and non-shortage WOs."""
        if not frappe.db.has_column("Work Order", "custom_released_with_shortage"):
            self.skipTest("custom_released_with_shortage column not migrated")

        with patch(
            "erpnextkta.kta_shopfloor.services.report_service.frappe.db.has_column",
            return_value=False,
        ):
            res_no_col = get_material_shortage_report(company=self.company)
            self.assertEqual(res_no_col["rows"], [])
            self.assertEqual(
                res_no_col["counts"],
                {
                    "all": 0,
                    "active_shortage": 0,
                    "critical": 0,
                    "transfer_required": 0,
                    "resolved": 0,
                },
            )
            self.assertEqual(res_no_col["filter_options"], {"warehouses": []})

        line_wh = self._create_warehouse(self.company, f"_Test Short Line {self.uid}")
        rm_item = self._create_item(
            f"_Test Short RM {self.uid}", f"Test Short RM {self.uid}"
        )

        # Non-active statuses with custom_released_with_shortage=1 must be excluded
        for docstatus, status in (
            (0, "Draft"),
            (1, "Completed"),
            (1, "Closed"),
            (2, "Cancelled"),
            (1, "Stopped"),
        ):
            self._create_wo(
                docstatus=docstatus,
                status=status,
                custom_released_with_shortage=1,
                required_items=[
                    {
                        "item_code": rm_item,
                        "source_warehouse": line_wh,
                        "required_qty": 10.0,
                        "stock_uom": "Nos",
                    }
                ],
            )

        # Active WOs with custom_released_with_shortage=0 must be excluded
        for status in ("Not Started", "In Process"):
            self._create_wo(
                docstatus=1,
                status=status,
                custom_released_with_shortage=0,
                required_items=[
                    {
                        "item_code": rm_item,
                        "source_warehouse": line_wh,
                        "required_qty": 10.0,
                        "stock_uom": "Nos",
                    }
                ],
            )

        wo_ns = self._create_wo(
            docstatus=1,
            status="Not Started",
            custom_released_with_shortage=1,
            required_items=[
                {
                    "item_code": rm_item,
                    "source_warehouse": line_wh,
                    "required_qty": 10.0,
                    "stock_uom": "Nos",
                }
            ],
        )
        wo_ip = self._create_wo(
            docstatus=1,
            status="In Process",
            custom_released_with_shortage=1,
            required_items=[
                {
                    "item_code": rm_item,
                    "source_warehouse": line_wh,
                    "required_qty": 10.0,
                    "stock_uom": "Nos",
                }
            ],
        )
        expected_wos = {wo_ns.name, wo_ip.name}

        for sf in (
            "all",
            "active_shortage",
            "critical",
            "transfer_required",
            "resolved",
        ):
            res = get_material_shortage_report(shortage_filter=sf, company=self.company)
            self.assertTrue(
                all(r["work_order"] in expected_wos for r in res["rows"]),
                f"Unexpected WO leaked under shortage_filter={sf}",
            )

        res_all = get_material_shortage_report(
            shortage_filter="all", company=self.company
        )
        self.assertEqual({r["work_order"] for r in res_all["rows"]}, expected_wos)
        self.assertEqual(res_all["counts"]["critical"], 2)
        self.assertEqual(res_all["counts"]["all"], 2)

        with self.assertRaises(frappe.ValidationError):
            get_material_shortage_report(
                shortage_filter="bad_filter", company=self.company
            )

    def test_shortage_report_classification_sorting_and_filters(self):
        """Verify critical/transfer_required/resolved classification, sorting, and filters."""
        if not frappe.db.has_column("Work Order", "custom_released_with_shortage"):
            self.skipTest("custom_released_with_shortage column not migrated")

        line_wh_1 = self._create_warehouse(
            self.company, f"_Test Short Line1 {self.uid}"
        )
        line_wh_2 = self._create_warehouse(
            self.company, f"_Test Short Line2 {self.uid}"
        )
        other_wh = self._create_warehouse(self.company, f"_Test Short Other {self.uid}")
        other_co_wh = self._create_warehouse(
            self.other_company, f"_Test Short ExtCo {self.uid}"
        )

        rm1 = self._create_item(f"_Test SRM1 {self.uid}", f"Alpha Cable {self.uid}")
        rm2 = self._create_item(f"_Test SRM2 {self.uid}", f"Beta Terminal {self.uid}")
        rm3 = self._create_item(f"_Test SRM3 {self.uid}", f"Gamma Sleeve {self.uid}")
        rm4 = self._create_item(f"_Test SRM4 {self.uid}", f"Delta Connector {self.uid}")
        rm5 = self._create_item(f"_Test SRM5 {self.uid}", f"Epsilon Tape {self.uid}")

        # Negative line stock clamps to 0.0; other_co_wh stock must NOT leak into other_warehouses_qty
        self._set_bin_qty(rm1, line_wh_1, 10.0)
        self._set_bin_qty(rm1, other_wh, 30.0)
        self._set_bin_qty(rm1, other_co_wh, 500.0)
        self._set_bin_qty(rm2, line_wh_1, 10.0)
        self._set_bin_qty(rm2, other_wh, 40.0)
        self._set_bin_qty(rm4, line_wh_2, -5.0)
        self._set_bin_qty(rm4, other_wh, 45.0)
        self._set_bin_qty(rm5, line_wh_1, 25.0)

        wo_critical = self._create_wo(
            docstatus=1,
            status="In Process",
            custom_released_with_shortage=1,
            planned_start_date="2026-11-24",
            expected_delivery_date="2026-11-30",
            creation="2026-11-23 08:00:00.123456",
            wip_warehouse=line_wh_1,
            required_items=[
                {
                    "item_code": rm3,
                    "item_name": f"Gamma Sleeve {self.uid}",
                    "operation": self.op_c,
                    "source_warehouse": line_wh_1,
                    "required_qty": 20.0,
                    "consumed_qty": 20.0,
                    "transferred_qty": 20.0,
                    "stock_uom": "Nos",
                },
                {
                    "item_code": rm2,
                    "item_name": f"Beta Terminal {self.uid}",
                    "operation": self.op_b,
                    "source_warehouse": line_wh_1,
                    "required_qty": 50.0,
                    "consumed_qty": 0.0,
                    "transferred_qty": 0.0,
                    "stock_uom": "Nos",
                },
                {
                    "item_code": rm1,
                    "item_name": f"Alpha Cable {self.uid}",
                    "operation": self.op_a,
                    "source_warehouse": line_wh_1,
                    "required_qty": 100.0,
                    "consumed_qty": 20.0,
                    "transferred_qty": 0.0,
                    "stock_uom": "Nos",
                },
            ],
        )
        # Fallback item source_warehouse from WO source_warehouse/wip_warehouse
        wo_transfer = self._create_wo(
            docstatus=1,
            status="Not Started",
            custom_released_with_shortage=1,
            creation="2026-11-24 09:00:00.000000",
            wip_warehouse=line_wh_2,
            source_warehouse=line_wh_2,
            required_items=[
                {
                    "item_code": rm4,
                    "item_name": f"Delta Connector {self.uid}",
                    "operation": self.op_b,
                    "required_qty": 40.0,
                    "consumed_qty": 0.0,
                    "stock_uom": "Nos",
                }
            ],
        )
        wo_resolved = self._create_wo(
            docstatus=1,
            status="In Process",
            custom_released_with_shortage=1,
            creation="2026-11-25 10:30:00.999999",
            wip_warehouse=line_wh_1,
            required_items=[
                {
                    "item_code": rm5,
                    "item_name": f"Epsilon Tape {self.uid}",
                    "operation": self.op_a,
                    "source_warehouse": line_wh_1,
                    "required_qty": 30.0,
                    "consumed_qty": 10.0,
                    "stock_uom": "Nos",
                }
            ],
        )

        res_all = get_material_shortage_report(
            shortage_filter="all", company=self.company
        )
        self.assertEqual(
            res_all["counts"],
            {
                "all": 3,
                "active_shortage": 2,
                "critical": 1,
                "transfer_required": 1,
                "resolved": 1,
            },
        )
        self.assertEqual(
            res_all["summary"],
            {
                "total_work_orders": 3,
                "critical_work_orders": 1,
                "transfer_work_orders": 1,
                "resolved_work_orders": 1,
                "total_shortage_items": 3,
            },
        )
        self.assertEqual(
            res_all["filter_options"]["warehouses"],
            sorted([line_wh_1, line_wh_2]),
        )
        # Rows sorted by Work Order creation DESC (newest first)
        self.assertEqual(
            [r["work_order"] for r in res_all["rows"]],
            [wo_resolved.name, wo_transfer.name, wo_critical.name],
        )

        resv_row = res_all["rows"][0]
        self.assertEqual(resv_row["shortage_status"], "resolved")
        self.assertEqual(resv_row["wo_creation"], "2026-11-25 10:30:00")
        self.assertEqual(resv_row["shortage_items_count"], 0)
        self.assertEqual(flt(resv_row["readiness_pct"]), 100.0)

        trans_row = res_all["rows"][1]
        self.assertEqual(trans_row["shortage_status"], "transfer_required")
        self.assertEqual(trans_row["wo_creation"], "2026-11-24 09:00:00")
        self.assertEqual(trans_row["items"][0]["source_warehouse"], line_wh_2)
        self.assertEqual(flt(trans_row["items"][0]["line_actual_qty"]), 0.0)
        self.assertEqual(flt(trans_row["items"][0]["shortage_qty"]), 40.0)
        self.assertEqual(flt(trans_row["readiness_pct"]), 0.0)

        crit_row = res_all["rows"][2]
        self.assertEqual(crit_row["shortage_status"], "critical")
        self.assertEqual(crit_row["wo_creation"], "2026-11-23 08:00:00")
        self.assertEqual(crit_row["total_items"], 3)
        self.assertEqual(crit_row["shortage_items_count"], 2)
        self.assertEqual(crit_row["critical_shortage_count"], 1)
        self.assertEqual(crit_row["transfer_required_count"], 1)
        self.assertEqual(flt(crit_row["readiness_pct"]), 44.2)
        self.assertEqual(crit_row["planned_start_date"], "2026-11-24")
        self.assertEqual(crit_row["expected_delivery_date"], "2026-11-30")
        self.assertEqual([i["item_code"] for i in crit_row["items"]], [rm1, rm2, rm3])
        self.assertEqual(
            [i["availability_status"] for i in crit_row["items"]],
            ["critical_shortage", "transfer_required", "available"],
        )
        self.assertEqual(flt(crit_row["items"][0]["remaining_required_qty"]), 80.0)
        self.assertEqual(flt(crit_row["items"][0]["shortage_qty"]), 70.0)
        self.assertEqual(flt(crit_row["items"][0]["other_warehouses_qty"]), 30.0)
        self.assertEqual(flt(crit_row["items"][0]["coverage_pct"]), 12.5)
        self.assertEqual(flt(crit_row["items"][2]["coverage_pct"]), 100.0)

        res_active = get_material_shortage_report(
            shortage_filter="active_shortage", company=self.company
        )
        self.assertEqual(
            [r["work_order"] for r in res_active["rows"]],
            [wo_transfer.name, wo_critical.name],
        )
        self.assertEqual(res_active["summary"]["total_shortage_items"], 3)

        res_resolved = get_material_shortage_report(
            shortage_filter="resolved", company=self.company
        )
        self.assertEqual(
            [r["work_order"] for r in res_resolved["rows"]], [wo_resolved.name]
        )
        self.assertEqual(res_resolved["summary"]["total_shortage_items"], 0)

        # Warehouse filter + search filter update counts before shortage_filter
        res_wh = get_material_shortage_report(
            shortage_filter="all", warehouse=line_wh_2, company=self.company
        )
        self.assertEqual([r["work_order"] for r in res_wh["rows"]], [wo_transfer.name])
        self.assertEqual(
            res_wh["counts"],
            {
                "all": 1,
                "active_shortage": 1,
                "critical": 0,
                "transfer_required": 1,
                "resolved": 0,
            },
        )
        self.assertEqual(
            res_wh["filter_options"]["warehouses"],
            sorted([line_wh_1, line_wh_2]),
        )

        res_search = get_material_shortage_report(
            shortage_filter="all",
            search=f"delta connector {self.uid}".lower(),
            company=self.company,
        )
        self.assertEqual(
            [r["work_order"] for r in res_search["rows"]], [wo_transfer.name]
        )

    def test_shortage_report_permissions_and_query_count(self):
        """Missing Work Order read permission fails and SQL queries remain bounded (<= 6)."""
        if not frappe.db.has_column("Work Order", "custom_released_with_shortage"):
            self.skipTest("custom_released_with_shortage column not migrated")

        def deny_wo_read(doctype, ptype="read", *args, **kwargs):
            if doctype == "Work Order" and kwargs.get("throw"):
                raise frappe.PermissionError("No WO read")
            return True

        with (
            patch(
                "erpnextkta.kta_shopfloor.services.report_service.frappe.has_permission",
                side_effect=deny_wo_read,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            get_material_shortage_report(company=self.company)

        line_wh = self._create_warehouse(self.company, f"_Test Short QryWh {self.uid}")
        other_wh = self._create_warehouse(
            self.company, f"_Test Short QryOth {self.uid}"
        )
        rm_items = [
            self._create_item(f"_Test QRM {i} {self.uid}", f"Query RM {i} {self.uid}")
            for i in range(3)
        ]
        for rm in rm_items:
            self._set_bin_qty(rm, line_wh, 5.0)
            self._set_bin_qty(rm, other_wh, 50.0)

        for _idx in range(5):
            self._create_wo(
                docstatus=1,
                status="In Process",
                custom_released_with_shortage=1,
                wip_warehouse=line_wh,
                required_items=[
                    {
                        "item_code": rm,
                        "source_warehouse": line_wh,
                        "required_qty": 20.0,
                        "stock_uom": "Nos",
                    }
                    for rm in rm_items
                ],
            )

        with self.assertQueryCount(6):
            res = get_material_shortage_report(
                shortage_filter="all", company=self.company
            )

        self.assertEqual(len(res["rows"]), 5)
        self.assertEqual(res["summary"]["total_work_orders"], 5)
        self.assertEqual(res["summary"]["total_shortage_items"], 15)
