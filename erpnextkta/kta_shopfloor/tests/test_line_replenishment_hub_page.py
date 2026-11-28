# Copyright (c) 2026, KTA and Contributors
# See license.txt

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnextkta.kta_shopfloor.page.line_replenishment_hub.line_replenishment_hub import (
    get_context,
)


class TestLineReplenishmentHubPage(FrappeTestCase):
    def _get_page_path(self, filename: str) -> str:
        app_path = frappe.get_app_path("erpnextkta")
        return os.path.join(
            app_path, "kta_shopfloor", "page", "line_replenishment_hub", filename
        )

    def test_hub_page_json_exists(self):
        json_path = self._get_page_path("line_replenishment_hub.json")
        self.assertTrue(os.path.exists(json_path), f"{json_path} must exist")
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("page_name"), "line-replenishment-hub")
        self.assertEqual(data.get("module"), "kta_shopfloor")
        roles = [r.get("role") for r in data.get("roles", [])]
        self.assertIn("Manufacturing Manager", roles)
        self.assertIn("Manufacturing User", roles)
        self.assertIn("Stock Manager", roles)
        self.assertIn("System Manager", roles)

    def test_hub_page_js_exists(self):
        js_path = self._get_page_path("line_replenishment_hub.js")
        self.assertTrue(os.path.exists(js_path), f"{js_path} must exist")
        with open(js_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('frappe.pages["line-replenishment-hub"]', content)
        self.assertIn('frappe.require("line-replenishment-hub.bundle.js")', content)
        self.assertIn("frappe.ui.setup_line_replenishment_hub_vue", content)
        self.assertIn(".layout-main-section", content)
        self.assertIn(".page-head", content)
        self.assertIn(".hide()", content)

    def test_hub_bundle_source_exists(self):
        app_path = frappe.get_app_path("erpnextkta")
        bundle_path = os.path.join(
            app_path,
            "public",
            "line-replenishment-hub",
            "line-replenishment-hub.bundle.js",
        )
        self.assertTrue(os.path.exists(bundle_path), f"{bundle_path} must exist")
        with open(bundle_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("setup_line_replenishment_hub_vue", content)

    def test_hub_page_py_context(self):
        ctx = {}
        # As Administrator / System Manager in test runner, permission passes
        get_context(ctx)
