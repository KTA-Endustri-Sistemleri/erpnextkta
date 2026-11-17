from unittest.mock import MagicMock, patch

import frappe

from erpnextkta.kta_stock.batch_manager import BatchSplitManager
from erpnextkta.tests.test_utils import KTAUnitTestCase


class TestBatchSplitPostingDate(KTAUnitTestCase):
    def setUp(self):
        super().setUp()
        if not hasattr(frappe, "local"):
            frappe.local = MagicMock()
        self.mock_db = MagicMock()
        self._orig_db = getattr(frappe.local, "db", None)
        frappe.local.db = self.mock_db

    def tearDown(self):
        frappe.local.db = self._orig_db
        super().tearDown()

    def _create_mock_bundle(self, posting_date=None, posting_time=None, fields=None):
        bundle = MagicMock()
        bundle.name = "SABB-TEST-0001"
        bundle.posting_date = posting_date
        bundle.posting_time = posting_time
        bundle.posting_datetime = None
        bundle.meta = MagicMock()

        available_fields = (
            fields
            if fields is not None
            else ["posting_date", "posting_time", "posting_datetime"]
        )
        bundle.meta.has_field.side_effect = lambda f: f in available_fields
        bundle.flags = MagicMock()
        bundle.entries = []

        def mock_append(field, entry):
            if field == "entries":
                bundle.entries.append(entry)

        bundle.append.side_effect = mock_append
        bundle.set.side_effect = lambda field, val: setattr(bundle, field, val)
        return bundle

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=12.5)
    def test_update_bundle_safely_sets_posting_date_and_time_from_parent_doc(
        self, mock_rate, mock_clear_cache
    ):
        """When parent_doc has posting_date and posting_time, bundle should inherit them."""
        mock_bundle = self._create_mock_bundle(posting_date=None, posting_time=None)
        row = frappe._dict(
            {
                "name": "row-001",
                "serial_and_batch_bundle": "SABB-TEST-0001",
                "warehouse": "Stores - TC",
                "batch_no": None,
            }
        )
        parent_doc = frappe._dict(
            {
                "doctype": "Stock Entry",
                "name": "STE-2026-0001",
                "posting_date": "2026-11-17",
                "posting_time": "14:30:00",
            }
        )
        allocations = [
            {
                "batch_no": "BATCH-001",
                "qty": 10.0,
                "sut_code": "BATCH-0010001",
                "pack_no": 1,
            },
            {
                "batch_no": "BATCH-002",
                "qty": 10.0,
                "sut_code": "BATCH-0010002",
                "pack_no": 2,
            },
        ]

        with patch(
            "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
            return_value=mock_bundle,
        ):
            BatchSplitManager._update_bundle_safely(
                row, allocations, parent_doc=parent_doc
            )

        self.assertEqual(mock_bundle.posting_date, "2026-11-17")
        self.assertEqual(mock_bundle.posting_time, "14:30:00")
        self.assertEqual(str(mock_bundle.posting_datetime), "2026-11-17 14:30:00")
        mock_bundle.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(len(mock_bundle.entries), 2)

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=5.0)
    def test_update_bundle_safely_sets_posting_time_nowtime_if_parent_doc_time_missing(
        self, mock_rate, mock_clear_cache
    ):
        """When parent_doc has posting_date but no posting_time, nowtime() should be used."""
        mock_bundle = self._create_mock_bundle(posting_date=None, posting_time=None)
        row = frappe._dict(
            {
                "name": "row-002",
                "serial_and_batch_bundle": "SABB-TEST-0002",
                "warehouse": "Finished Goods - TC",
                "batch_no": None,
            }
        )
        parent_doc = frappe._dict(
            {
                "doctype": "Stock Entry",
                "name": "STE-2026-0002",
                "posting_date": "2026-05-20",
                "posting_time": None,
            }
        )
        allocations = [
            {
                "batch_no": "BATCH-003",
                "qty": 25.0,
                "sut_code": "BATCH-0030001",
                "pack_no": 1,
            }
        ]

        fixed_nowtime = "15:45:00"
        with (
            patch(
                "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
                return_value=mock_bundle,
            ),
            patch(
                "erpnextkta.kta_stock.batch_manager.nowtime", return_value=fixed_nowtime
            ),
        ):
            BatchSplitManager._update_bundle_safely(
                row, allocations, parent_doc=parent_doc
            )

        self.assertEqual(mock_bundle.posting_date, "2026-05-20")
        self.assertEqual(mock_bundle.posting_time, fixed_nowtime)
        self.assertEqual(
            str(mock_bundle.posting_datetime), f"2026-05-20 {fixed_nowtime}"
        )

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=8.0)
    def test_update_bundle_safely_fetches_from_db_when_parent_doc_is_none(
        self, mock_rate, mock_clear_cache
    ):
        """When parent_doc is not passed, row.parent and row.parenttype should fetch posting date and time from DB."""
        mock_bundle = self._create_mock_bundle(posting_date=None, posting_time=None)
        row = frappe._dict(
            {
                "name": "row-003",
                "serial_and_batch_bundle": "SABB-TEST-0003",
                "warehouse": "Stores - TC",
                "parent": "PR-2026-0001",
                "parenttype": "Purchase Receipt",
                "batch_no": None,
            }
        )
        allocations = [
            {
                "batch_no": "BATCH-004",
                "qty": 50.0,
                "sut_code": "BATCH-0040001",
                "pack_no": 1,
            }
        ]

        self.mock_db.get_value.return_value = {
            "posting_date": "2026-08-12",
            "posting_time": "10:15:30",
        }

        with patch(
            "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
            return_value=mock_bundle,
        ):
            BatchSplitManager._update_bundle_safely(row, allocations, parent_doc=None)

        self.assertEqual(mock_bundle.posting_date, "2026-08-12")
        self.assertEqual(mock_bundle.posting_time, "10:15:30")
        self.assertEqual(str(mock_bundle.posting_datetime), "2026-08-12 10:15:30")
        self.mock_db.get_value.assert_any_call(
            "Purchase Receipt",
            "PR-2026-0001",
            ["posting_date", "posting_time"],
            as_dict=True,
        )

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=1.0)
    def test_update_bundle_safely_fallback_when_no_parent_or_db_value(
        self, mock_rate, mock_clear_cache
    ):
        """When neither parent_doc nor row parent is available, fallback to nowdate() and nowtime() to prevent NULL."""
        mock_bundle = self._create_mock_bundle(posting_date=None, posting_time=None)
        row = frappe._dict(
            {
                "name": "row-004",
                "serial_and_batch_bundle": "SABB-TEST-0004",
                "warehouse": "Stores - TC",
                "batch_no": None,
            }
        )
        allocations = [
            {
                "batch_no": "BATCH-005",
                "qty": 10.0,
                "sut_code": "BATCH-0050001",
                "pack_no": 1,
            }
        ]

        fixed_nowdate = "2026-11-17"
        fixed_nowtime = "16:00:00"
        with (
            patch(
                "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
                return_value=mock_bundle,
            ),
            patch(
                "erpnextkta.kta_stock.batch_manager.nowdate", return_value=fixed_nowdate
            ),
            patch(
                "erpnextkta.kta_stock.batch_manager.nowtime", return_value=fixed_nowtime
            ),
        ):
            BatchSplitManager._update_bundle_safely(row, allocations, parent_doc=None)

        self.assertEqual(mock_bundle.posting_date, fixed_nowdate)
        self.assertEqual(mock_bundle.posting_time, fixed_nowtime)
        self.assertEqual(
            str(mock_bundle.posting_datetime), f"{fixed_nowdate} {fixed_nowtime}"
        )

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=1.0)
    def test_update_bundle_safely_preserves_existing_date_if_no_parent_override(
        self, mock_rate, mock_clear_cache
    ):
        """When bundle already has posting_date and no parent info is provided, existing date is preserved."""
        mock_bundle = self._create_mock_bundle(
            posting_date="2026-03-01", posting_time="09:00:00"
        )
        row = frappe._dict(
            {
                "name": "row-005",
                "serial_and_batch_bundle": "SABB-TEST-0005",
                "warehouse": "Stores - TC",
                "batch_no": None,
            }
        )
        allocations = [
            {
                "batch_no": "BATCH-006",
                "qty": 10.0,
                "sut_code": "BATCH-0060001",
                "pack_no": 1,
            }
        ]

        with patch(
            "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
            return_value=mock_bundle,
        ):
            BatchSplitManager._update_bundle_safely(row, allocations, parent_doc=None)

        self.assertEqual(mock_bundle.posting_date, "2026-03-01")
        self.assertEqual(mock_bundle.posting_time, "09:00:00")
        self.assertEqual(str(mock_bundle.posting_datetime), "2026-03-01 09:00:00")

    @patch.object(BatchSplitManager, "_update_bundle_safely")
    @patch.object(BatchSplitManager, "_prepare_batch_allocations")
    @patch.object(BatchSplitManager, "_get_customer_packaging_qty", return_value=10.0)
    @patch.object(
        BatchSplitManager, "get_base_batch_for_work_order", return_value="BASE-001"
    )
    @patch.object(BatchSplitManager, "_get_single_inward_batch_entry")
    def test_split_manufacturing_batches_passes_parent_doc(
        self, mock_inward, mock_base_wo, mock_pkg_qty, mock_prepare, mock_update_safely
    ):
        """split_manufacturing_batches should pass stock_entry doc as parent_doc."""
        mock_inward.return_value = {"batch_no": "BASE-001"}
        mock_prepare.return_value = [{"batch_no": "BASE-0010001", "qty": 10.0}]

        item_row = frappe._dict(
            {
                "is_finished_item": 1,
                "item_code": "ITEM-FG-001",
                "serial_and_batch_bundle": "SABB-MFG-001",
                "qty": 10.0,
            }
        )

        stock_entry_doc = frappe._dict(
            {
                "doctype": "Stock Entry",
                "purpose": "Manufacture",
                "work_order": "WO-001",
                "posting_date": "2026-11-17",
                "posting_time": "11:00:00",
                "flags": frappe._dict({"in_split_process": False}),
                "items": [item_row],
            }
        )

        BatchSplitManager.split_manufacturing_batches(stock_entry_doc)

        mock_update_safely.assert_called_once_with(
            item_row, mock_prepare.return_value, parent_doc=stock_entry_doc
        )

    @patch.object(BatchSplitManager, "_update_bundle_safely")
    @patch.object(BatchSplitManager, "_prepare_batch_allocations")
    def test_split_purchase_receipt_batches_passes_parent_doc(
        self, mock_prepare, mock_update_safely
    ):
        """split_purchase_receipt_batches should pass purchase_receipt doc as parent_doc."""
        mock_prepare.return_value = [{"batch_no": "PR-BATCH-001", "qty": 50.0}]

        row = frappe._dict(
            {
                "doctype": "Purchase Receipt Item",
                "name": "PRI-001",
                "parent": "PR-2026-0005",
                "item_code": "RAW-001",
                "serial_and_batch_bundle": "SABB-PR-001",
                "batch_no": "BASE-RAW-001",
            }
        )

        mock_pr = frappe._dict(
            {
                "doctype": "Purchase Receipt",
                "name": "PR-2026-0005",
                "posting_date": "2026-11-15",
                "posting_time": "08:30:00",
            }
        )

        self.mock_db.get_value.return_value = "BASE-RAW-001"

        with patch(
            "erpnextkta.kta_stock.batch_manager.frappe.get_cached_doc",
            return_value=mock_pr,
        ):
            allocations = BatchSplitManager.split_purchase_receipt_batches(row)

        self.assertEqual(allocations, mock_prepare.return_value)
        mock_update_safely.assert_called_once_with(
            row, mock_prepare.return_value, parent_doc=mock_pr
        )

    @patch.object(BatchSplitManager, "_update_bundle_safely")
    @patch.object(BatchSplitManager, "_prepare_batch_allocations")
    @patch.object(BatchSplitManager, "_get_customer_packaging_qty", return_value=5.0)
    @patch.object(
        BatchSplitManager, "get_base_batch_for_work_order", return_value="BASE-002"
    )
    @patch.object(BatchSplitManager, "_get_single_inward_batch_entry")
    def test_resplit_submitted_manufacturing_batches_passes_parent_doc(
        self, mock_inward, mock_base_wo, mock_pkg_qty, mock_prepare, mock_update_safely
    ):
        """resplit_submitted_manufacturing_batches should pass stock entry doc as parent_doc."""
        mock_inward.return_value = {"batch_no": "BASE-002"}
        mock_prepare.return_value = [{"batch_no": "BASE-0020001", "qty": 5.0}]

        item_row = frappe._dict(
            {
                "is_finished_item": 1,
                "item_code": "ITEM-FG-002",
                "serial_and_batch_bundle": "SABB-MFG-002",
                "qty": 5.0,
            }
        )

        stock_entry_doc = frappe._dict(
            {
                "doctype": "Stock Entry",
                "purpose": "Manufacture",
                "work_order": "WO-002",
                "posting_date": "2026-11-16",
                "posting_time": "15:00:00",
                "items": [item_row],
            }
        )

        with (
            patch(
                "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
                return_value=stock_entry_doc,
            ),
            patch("erpnextkta.kta_stock.batch_manager.frappe.get_all", return_value=[]),
        ):
            BatchSplitManager.resplit_submitted_manufacturing_batches("STE-2026-0002")

        mock_update_safely.assert_called_once_with(
            item_row, mock_prepare.return_value, parent_doc=stock_entry_doc
        )

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=10.0)
    def test_update_bundle_safely_when_schema_only_has_posting_datetime(
        self, mock_rate, mock_clear_cache
    ):
        """When bundle schema only has posting_datetime, only posting_datetime is assigned."""
        mock_bundle = self._create_mock_bundle(fields=["posting_datetime"])
        row = frappe._dict(
            {
                "name": "row-only-datetime",
                "serial_and_batch_bundle": "SABB-TEST-0006",
                "warehouse": "Stores - TC",
                "batch_no": None,
            }
        )
        parent_doc = frappe._dict(
            {
                "doctype": "Stock Entry",
                "name": "STE-2026-0003",
                "posting_date": "2026-11-17",
                "posting_time": "14:30:00",
            }
        )
        allocations = [{"batch_no": "BATCH-007", "qty": 10.0}]

        with patch(
            "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
            return_value=mock_bundle,
        ):
            BatchSplitManager._update_bundle_safely(
                row, allocations, parent_doc=parent_doc
            )

        self.assertEqual(str(mock_bundle.posting_datetime), "2026-11-17 14:30:00")
        self.assertIsNone(mock_bundle.posting_date)
        self.assertIsNone(mock_bundle.posting_time)

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=10.0)
    def test_update_bundle_safely_when_schema_only_has_posting_date_and_time(
        self, mock_rate, mock_clear_cache
    ):
        """When bundle schema only has posting_date and posting_time, posting_datetime is not set."""
        mock_bundle = self._create_mock_bundle(fields=["posting_date", "posting_time"])
        row = frappe._dict(
            {
                "name": "row-only-date-time",
                "serial_and_batch_bundle": "SABB-TEST-0007",
                "warehouse": "Stores - TC",
                "batch_no": None,
            }
        )
        parent_doc = frappe._dict(
            {
                "doctype": "Stock Entry",
                "name": "STE-2026-0004",
                "posting_date": "2026-11-17",
                "posting_time": "14:30:00",
            }
        )
        allocations = [{"batch_no": "BATCH-008", "qty": 10.0}]

        with patch(
            "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
            return_value=mock_bundle,
        ):
            BatchSplitManager._update_bundle_safely(
                row, allocations, parent_doc=parent_doc
            )

        self.assertEqual(mock_bundle.posting_date, "2026-11-17")
        self.assertEqual(mock_bundle.posting_time, "14:30:00")
        self.assertIsNone(mock_bundle.posting_datetime)

    @patch("erpnextkta.kta_stock.batch_manager.frappe.clear_document_cache")
    @patch.object(BatchSplitManager, "_get_reliable_incoming_rate", return_value=10.0)
    def test_update_bundle_safely_preserves_from_posting_datetime_if_only_datetime_set(
        self, mock_rate, mock_clear_cache
    ):
        """When bundle only has posting_datetime set and no parent info is provided, date and time are derived."""
        mock_bundle = self._create_mock_bundle()
        mock_bundle.posting_datetime = "2026-04-10 11:20:00"
        row = frappe._dict(
            {
                "name": "row-from-datetime",
                "serial_and_batch_bundle": "SABB-TEST-0008",
                "warehouse": "Stores - TC",
                "batch_no": None,
            }
        )
        allocations = [{"batch_no": "BATCH-009", "qty": 10.0}]

        with patch(
            "erpnextkta.kta_stock.batch_manager.frappe.get_doc",
            return_value=mock_bundle,
        ):
            BatchSplitManager._update_bundle_safely(row, allocations, parent_doc=None)

        self.assertEqual(mock_bundle.posting_date, "2026-04-10")
        self.assertEqual(mock_bundle.posting_time, "11:20:00")
        self.assertEqual(str(mock_bundle.posting_datetime), "2026-04-10 11:20:00")
