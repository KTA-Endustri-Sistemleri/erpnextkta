import frappe
from frappe.utils import flt

from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_company,
    create_test_item,
    create_test_item_group,
    create_test_warehouse,
)


class TestStockReconciliationOverride(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        self.company = create_test_company()
        self.item_group = create_test_item_group()
        self.item = create_test_item(self.item_group)
        frappe.db.set_value("Item", self.item, {"has_batch_no": 0, "has_serial_no": 0})
        self.warehouse = create_test_warehouse(self.company)

    def _create_stock_reconciliation(self, qty=10, valuation_rate=100, batch_no=None):
        expense_account = frappe.db.get_value(
            "Account", {"account_type": "Temporary", "company": self.company}
        ) or frappe.db.get_value(
            "Account", {"account_type": "Stock Adjustment", "company": self.company}
        )
        cost_center = frappe.db.get_value(
            "Cost Center", {"is_group": 0, "company": self.company}
        )

        item_row = {
            "item_code": self.item,
            "warehouse": self.warehouse,
            "qty": qty,
            "valuation_rate": valuation_rate,
        }
        if batch_no:
            item_row["batch_no"] = batch_no

        sr = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": self.company,
                "purpose": "Stock Reconciliation",
                "posting_date": frappe.utils.today(),
                "posting_time": frappe.utils.nowtime(),
                "set_posting_time": 1,
                "expense_account": expense_account,
                "cost_center": cost_center,
                "items": [item_row],
            }
        )
        sr.insert(ignore_permissions=True)
        return sr

    def test_reconciliation_on_cancel_and_trash_cleans_up_labels(self):
        """Stock Reconciliation on_cancel and on_trash must clean up associated

        KTA Stock Label and KTA Print Log records without raising LinkExistsError.
        """
        sr = self._create_stock_reconciliation(qty=10, valuation_rate=100)

        label = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "item_code": self.item,
                "label_type": "Depo Giriş Etiketi",
                "qty": 10,
                "target_warehouse": self.warehouse,
                "reference_doctype": "Stock Reconciliation",
                "reference_name": sr.name,
            }
        )
        label.insert(ignore_permissions=True)

        print_log = frappe.get_doc(
            {
                "doctype": "KTA Print Log",
                "label_doctype": "KTA Stock Label",
                "label_name": label.name,
                "printed_by": "Administrator",
            }
        )
        print_log.insert(ignore_permissions=True)

        self.assertTrue(frappe.db.exists("KTA Stock Label", label.name))
        self.assertTrue(frappe.db.exists("KTA Print Log", print_log.name))

        sr.submit()

        sr.cancel()

        self.assertFalse(frappe.db.exists("KTA Stock Label", label.name))
        self.assertFalse(frappe.db.exists("KTA Print Log", print_log.name))

        sr.delete()
        self.assertFalse(frappe.db.exists("Stock Reconciliation", sr.name))

    def test_reconciliation_on_cancel_and_trash_cleans_up_batches(self):
        """Batches created for Stock Reconciliation should be deleted on trash if no SLE

        or disabled/zeroed on cancel.
        """
        batch_item_code = f"_Test Batch Item {frappe.generate_hash('', 5)}"
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": batch_item_code,
                "item_group": self.item_group,
                "is_stock_item": 1,
                "stock_uom": "Nos",
                "has_batch_no": 1,
            }
        ).insert(ignore_permissions=True)

        sr_draft = self._create_stock_reconciliation(qty=10, valuation_rate=100)
        batch_draft_name = f"BATCH-SR-DRAFT-{frappe.generate_hash('', 5)}"
        batch_draft = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": batch_draft_name,
                "item": batch_item_code,
                "batch_qty": 0,
                "reference_doctype": "Stock Reconciliation",
                "reference_name": sr_draft.name,
            }
        )
        batch_draft.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Stock Reconciliation Item",
            sr_draft.items[0].name,
            "batch_no",
            batch_draft.name,
            update_modified=False,
        )
        sr_draft.reload()

        self.assertTrue(frappe.db.exists("Batch", batch_draft.name))
        sr_draft.delete()
        self.assertFalse(frappe.db.exists("Batch", batch_draft.name))

        sr_cancel = self._create_stock_reconciliation(qty=10, valuation_rate=100)
        batch_cancel_name = f"BATCH-SR-CANCEL-{frappe.generate_hash('', 5)}"
        batch_cancel = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": batch_cancel_name,
                "item": batch_item_code,
                "batch_qty": 5,
                "reference_doctype": "Stock Reconciliation",
                "reference_name": sr_cancel.name,
            }
        )
        batch_cancel.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Stock Reconciliation Item",
            sr_cancel.items[0].name,
            "batch_no",
            batch_cancel.name,
            update_modified=False,
        )
        sr_cancel.reload()

        sr_cancel._cleanup_associated_labels_and_batches(delete_batches=False)

        batch_data = frappe.db.get_value(
            "Batch",
            batch_cancel.name,
            ["batch_qty", "disabled"],
            as_dict=True,
        )
        self.assertEqual(flt(batch_data.batch_qty), 0.0)
        self.assertEqual(batch_data.disabled, 1)
