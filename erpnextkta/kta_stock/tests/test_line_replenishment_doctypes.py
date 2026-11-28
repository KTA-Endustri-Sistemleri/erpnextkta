import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase


class TestLineReplenishmentDocTypes(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.reload_doc("kta_stock", "doctype", "kta_line_replenishment_item")
        frappe.reload_doc("kta_stock", "doctype", "kta_line_replenishment_order")

    def _get_doctype_path(self, doctype_folder: str, json_file: str) -> str:
        primary = frappe.get_app_path(
            "erpnextkta", "kta_stock", "doctype", doctype_folder, json_file
        )
        if os.path.exists(primary):
            return primary
        fallback = os.path.join(
            "erpnextkta", "kta_stock", "doctype", doctype_folder, json_file
        )
        return fallback

    def test_order_doctype_schema(self):
        path = self._get_doctype_path(
            "kta_line_replenishment_order", "kta_line_replenishment_order.json"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        fields = {d["fieldname"]: d for d in data.get("fields", [])}
        self.assertIn("target_warehouse", fields)
        self.assertEqual(fields["target_warehouse"]["reqd"], 1)
        self.assertNotIn("sourcing_strategy", fields)
        self.assertIn("stock_entry", fields)
        self.assertIn("items", fields)

    def test_item_doctype_schema(self):
        path = self._get_doctype_path(
            "kta_line_replenishment_item", "kta_line_replenishment_item.json"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        fields = {d["fieldname"]: d for d in data.get("fields", [])}
        self.assertIn("deficit_qty", fields)
        self.assertNotIn("sourcing_type", fields)
        self.assertNotIn("free_stock_qty", fields)
        self.assertEqual(
            fields["section_break_sourcing"].get("label"),
            "Shelf & Batch Allocation",
        )
        self.assertIn("suggested_source_warehouse", fields)
        self.assertIn("is_picked", fields)

    def test_all_order_fields_exist(self):
        path = self._get_doctype_path(
            "kta_line_replenishment_order", "kta_line_replenishment_order.json"
        )
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        fieldnames = {d["fieldname"] for d in data.get("fields", [])}
        expected = {
            "naming_series",
            "target_warehouse",
            "company",
            "posting_date",
            "posting_time",
            "status",
            "total_deficit_qty",
            "total_picked_qty",
            "stock_entry",
            "items",
            "remarks",
        }
        self.assertTrue(expected.issubset(fieldnames))
        self.assertNotIn("sourcing_strategy", fieldnames)

    def test_all_item_fields_exist(self):
        path = self._get_doctype_path(
            "kta_line_replenishment_item", "kta_line_replenishment_item.json"
        )
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        fieldnames = {d["fieldname"] for d in data.get("fields", [])}
        expected = {
            "item_code",
            "item_name",
            "uom",
            "reserved_qty",
            "line_actual_qty",
            "deficit_qty",
            "suggested_source_warehouse",
            "suggested_batch_no",
            "picked_qty",
            "picked_source_warehouse",
            "picked_batch_no",
            "is_picked",
            "is_skipped",
            "skipped_by",
            "is_fifo_override",
        }
        self.assertTrue(expected.issubset(fieldnames))
        self.assertNotIn("sourcing_type", fieldnames)
        self.assertNotIn("free_stock_qty", fieldnames)

    def test_order_controller_validation(self):
        order = frappe.new_doc("KTA Line Replenishment Order")
        order.target_warehouse = None
        with self.assertRaises(frappe.ValidationError):
            order.validate()

    def test_order_controller_calculate_totals(self):
        order = frappe.new_doc("KTA Line Replenishment Order")
        order.target_warehouse = "1501 KESMELER - KTA"
        order.append(
            "items",
            {
                "item_code": "TEST-ITEM-001",
                "uom": "Nos",
                "deficit_qty": 120.0,
                "picked_qty": 100.0,
            },
        )
        order.append(
            "items",
            {
                "item_code": "TEST-ITEM-002",
                "uom": "Nos",
                "deficit_qty": 80.0,
                "picked_qty": 80.0,
            },
        )
        order.validate()
        self.assertEqual(order.total_deficit_qty, 200.0)
        self.assertEqual(order.total_picked_qty, 180.0)
