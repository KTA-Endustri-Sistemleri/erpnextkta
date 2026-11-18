# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase


class TestShopfloorSchema(FrappeTestCase):
    def _load_custom_fields(self, *path_parts):
        path = frappe.get_app_path("erpnextkta", *path_parts)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {cf["fieldname"]: cf for cf in data.get("custom_fields", [])}

    def test_work_order_shortage_custom_field_defined(self):
        fields = self._load_custom_fields("erpnextkta", "custom", "work_order.json")
        self.assertIn("custom_released_with_shortage", fields)
        cf = fields["custom_released_with_shortage"]
        self.assertEqual(cf["dt"], "Work Order")
        self.assertEqual(cf["fieldtype"], "Check")
        self.assertEqual(cf["label"], "Eksik Parça ile Serbest Bırakıldı")
        self.assertEqual(cf["read_only"], 1)

    def test_item_lead_days_custom_field_defined(self):
        fields = self._load_custom_fields("kta_mrp", "custom", "item.json")
        self.assertIn("custom_manufacturing_lead_days", fields)
        cf = fields["custom_manufacturing_lead_days"]
        self.assertEqual(cf["dt"], "Item")
        self.assertEqual(cf["fieldtype"], "Int")
        self.assertEqual(cf["label"], "Üretim Süresi (Gün)")
        self.assertEqual(str(cf["default"]), "14")
