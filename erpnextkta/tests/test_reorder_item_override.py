from unittest.mock import patch

import frappe
from erpnext.stock import reorder_item
from frappe.utils import add_days, flt, nowdate

from erpnextkta.overrides.reorder_item import (
    apply_reorder_item_override,
    calculate_kta_manufacture_reorder_qty,
    cleanup_stale_auto_reorder_drafts,
    get_kta_manufacture_projected_qty,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    KTAUnitTestCase,
    create_test_company,
    create_test_item,
    create_test_item_group,
)


class TestReorderQtyCalculation(KTAUnitTestCase):
    """Unit tests for KTA Manufacture reorder quantity calculation."""

    def test_returns_deficiency_when_larger_than_reorder_qty(self):
        """Deficiency above reorder_qty should return exact deficiency."""
        self.assertEqual(calculate_kta_manufacture_reorder_qty(700, 1050, 70), 350.0)
        self.assertEqual(
            calculate_kta_manufacture_reorder_qty(2399, 4800, 2400), 2401.0
        )

    def test_returns_reorder_qty_when_deficiency_less_or_equal(self):
        """Deficiency <= reorder_qty should clamp to reorder_qty."""
        self.assertEqual(calculate_kta_manufacture_reorder_qty(0, 1120, 1120), 1120.0)
        self.assertEqual(calculate_kta_manufacture_reorder_qty(1000, 1050, 70), 70.0)

    def test_returns_none_when_projected_meets_or_exceeds_level(self):
        """Strict `<` comparison should skip when projected >= reorder_level."""
        self.assertIsNone(calculate_kta_manufacture_reorder_qty(1050, 1050, 70))
        self.assertIsNone(calculate_kta_manufacture_reorder_qty(1200, 1050, 70))

    def test_returns_none_when_level_and_qty_are_zero(self):
        """Unconfigured reorder level and qty should return None."""
        self.assertIsNone(calculate_kta_manufacture_reorder_qty(0, 0, 0))


class TestReorderItemOverride(KTABaseTestCase):
    """Integration tests for KTA Manufacture auto-reorder override and draft cleanup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = create_test_company()
        cls.item_group = create_test_item_group()

    def setUp(self):
        super().setUp()
        apply_reorder_item_override()
        frappe.db.set_single_value("Stock Settings", "auto_indent", 1)
        frappe.db.set_single_value("Stock Settings", "reorder_email_notify", 0)

        self.suffix = frappe.generate_hash(length=6)
        self.item_code = create_test_item(
            self.item_group, f"_Test Reorder Item {self.suffix}"
        )
        frappe.db.set_value(
            "Item", self.item_code, {"has_batch_no": 0, "has_serial_no": 0}
        )

        self.group_wh = self._create_warehouse(
            f"_Test Reorder Group {self.suffix}", is_group=1
        )
        self.normal_wh = self._create_warehouse(
            f"_Test Reorder Normal {self.suffix}",
            parent_warehouse=self.group_wh,
        )
        self.rejected_wh = self._create_warehouse(
            f"_Test Reorder Rejected {self.suffix}",
            parent_warehouse=self.group_wh,
            is_rejected_warehouse=1,
        )

    def _create_warehouse(
        self,
        warehouse_name,
        is_group=0,
        parent_warehouse=None,
        is_rejected_warehouse=0,
    ):
        """Create a test warehouse under the test company."""
        doc = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": warehouse_name,
                "company": self.company,
                "is_group": is_group,
                "parent_warehouse": parent_warehouse or "All Warehouses - TKTA",
                "is_rejected_warehouse": is_rejected_warehouse,
            }
        ).insert(ignore_permissions=True)
        return doc.name

    def _create_bin(
        self,
        warehouse,
        actual_qty=0.0,
        planned_qty=0.0,
        reserved_qty=0.0,
    ):
        """Create a Bin record with explicit quantities."""
        return frappe.get_doc(
            {
                "doctype": "Bin",
                "item_code": self.item_code,
                "warehouse": warehouse,
                "actual_qty": actual_qty,
                "planned_qty": planned_qty,
                "reserved_qty": reserved_qty,
            }
        ).insert(ignore_permissions=True)

    def _build_reorder_row(
        self,
        warehouse,
        warehouse_group=None,
        material_request_type="Manufacture",
        reorder_level=1050,
        reorder_qty=70,
    ):
        """Build a mock Item Reorder query row matching get_items_for_reorder()."""
        return frappe._dict(
            {
                "warehouse": warehouse,
                "warehouse_group": warehouse_group,
                "material_request_type": material_request_type,
                "warehouse_reorder_level": reorder_level,
                "warehouse_reorder_qty": reorder_qty,
                "name": self.item_code,
                "stock_uom": "Nos",
                "purchase_uom": "Nos",
                "description": "Test Reorder Item",
                "item_name": self.item_code,
                "item_group": self.item_group,
                "brand": None,
                "variant_of": None,
                "has_variants": 0,
                "lead_time_days": 1,
            }
        )

    def _create_mr(
        self,
        material_request_type="Manufacture",
        transaction_date=None,
        owner="Administrator",
        submit=False,
    ):
        """Create a Material Request for cleanup tests."""
        tx_date = transaction_date or nowdate()
        mr = frappe.get_doc(
            {
                "doctype": "Material Request",
                "company": self.company,
                "material_request_type": material_request_type,
                "transaction_date": tx_date,
                "schedule_date": nowdate(),
                "items": [
                    {
                        "item_code": self.item_code,
                        "qty": 10,
                        "schedule_date": nowdate(),
                        "warehouse": self.normal_wh,
                    }
                ],
            }
        ).insert(ignore_permissions=True)

        if owner != "Administrator":
            frappe.db.set_value(
                "Material Request", mr.name, "owner", owner, update_modified=False
            )

        if submit:
            mr.reload()
            mr.submit()

        return mr

    def test_manufacture_projected_qty_excludes_reserved_and_rejected_warehouses(self):
        """Projected qty should ignore Sales Order reserves, rejected warehouses, and +0.0001 drift."""
        self._create_bin(self.normal_wh, planned_qty=700, reserved_qty=12810)
        self._create_bin(self.rejected_wh, actual_qty=500)

        projected_map = get_kta_manufacture_projected_qty([self.item_code])

        self.assertEqual(projected_map[self.item_code][self.normal_wh], 700.0)
        self.assertEqual(projected_map[self.item_code][self.group_wh], 700.0)
        self.assertNotIn(self.rejected_wh, projected_map[self.item_code])

    def test_manufacture_reorder_creates_draft_mr_with_deficiency_qty(self):
        """Manufacture reorder below level should create a Draft MR with deficiency quantity."""
        self._create_bin(self.normal_wh, planned_qty=700, reserved_qty=12810)
        row = self._build_reorder_row(
            warehouse=self.normal_wh,
            warehouse_group=self.group_wh,
            material_request_type="Manufacture",
            reorder_level=1050,
            reorder_qty=70,
        )

        with patch.object(
            reorder_item, "get_items_for_reorder", return_value={self.item_code: [row]}
        ):
            created_mrs = reorder_item.reorder_item()

        self.assertEqual(len(created_mrs), 1)
        mr = frappe.get_doc("Material Request", created_mrs[0].name)
        self.assertEqual(mr.docstatus, 0)
        self.assertEqual(mr.material_request_type, "Manufacture")
        self.assertEqual(len(mr.items), 1)
        self.assertEqual(mr.items[0].item_code, self.item_code)
        self.assertEqual(flt(mr.items[0].qty), 350.0)

    def test_manufacture_reorder_skips_when_projected_equals_level(self):
        """Manufacture reorder should not create an MR when projected equals reorder level."""
        self._create_bin(self.normal_wh, planned_qty=1050)
        row = self._build_reorder_row(
            warehouse=self.normal_wh,
            warehouse_group=self.group_wh,
            material_request_type="Manufacture",
            reorder_level=1050,
            reorder_qty=70,
        )

        with patch.object(
            reorder_item, "get_items_for_reorder", return_value={self.item_code: [row]}
        ):
            created_mrs = reorder_item.reorder_item()

        self.assertEqual(created_mrs, [])

    def test_cleanup_stale_auto_reorder_drafts_only_deletes_old_admin_manufacture_drafts(
        self,
    ):
        """Cleanup should delete only old Administrator Draft Manufacture MRs and linked ToDos."""
        yesterday = add_days(nowdate(), -1)
        today = nowdate()

        mr_old_admin_draft = self._create_mr("Manufacture", transaction_date=yesterday)
        linked_todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": "Stale MR ToDo",
                "reference_type": "Material Request",
                "reference_name": mr_old_admin_draft.name,
                "status": "Open",
            }
        ).insert(ignore_permissions=True)

        mr_today_admin_draft = self._create_mr("Manufacture", transaction_date=today)
        mr_old_other_user_draft = self._create_mr(
            "Manufacture",
            transaction_date=yesterday,
            owner="planner@example.com",
        )
        mr_old_purchase_draft = self._create_mr("Purchase", transaction_date=yesterday)
        mr_old_admin_submitted = self._create_mr(
            "Manufacture", transaction_date=yesterday, submit=True
        )

        deleted = cleanup_stale_auto_reorder_drafts()

        self.assertIn(mr_old_admin_draft.name, deleted)
        self.assertFalse(frappe.db.exists("Material Request", mr_old_admin_draft.name))
        self.assertFalse(frappe.db.exists("ToDo", linked_todo.name))

        for kept_name in (
            mr_today_admin_draft.name,
            mr_old_other_user_draft.name,
            mr_old_purchase_draft.name,
            mr_old_admin_submitted.name,
        ):
            self.assertNotIn(kept_name, deleted)
            self.assertTrue(frappe.db.exists("Material Request", kept_name))

    def test_non_manufacture_delegates_to_original_reorder_item(self):
        """Non-Manufacture rows should delegate to _original_reorder_item without Manufacture rows."""
        self._create_bin(self.normal_wh, actual_qty=0)
        purchase_row = self._build_reorder_row(
            warehouse=self.normal_wh,
            warehouse_group=None,
            material_request_type="Purchase",
            reorder_level=100,
            reorder_qty=50,
        )

        captured_items = []
        real_original = reorder_item._original_reorder_item

        def spy_original_reorder_item():
            captured_items.append(reorder_item.get_items_for_reorder())
            return real_original()

        with (
            patch.object(
                reorder_item,
                "get_items_for_reorder",
                return_value={self.item_code: [purchase_row]},
            ),
            patch.object(
                reorder_item,
                "_original_reorder_item",
                side_effect=spy_original_reorder_item,
            ),
        ):
            created_mrs = reorder_item.reorder_item()

        self.assertEqual(len(captured_items), 1)
        self.assertEqual(list(captured_items[0].keys()), [self.item_code])
        self.assertEqual(len(captured_items[0][self.item_code]), 1)
        self.assertEqual(
            captured_items[0][self.item_code][0].material_request_type, "Purchase"
        )
        self.assertEqual(len(created_mrs), 1)
        self.assertEqual(created_mrs[0].material_request_type, "Purchase")
