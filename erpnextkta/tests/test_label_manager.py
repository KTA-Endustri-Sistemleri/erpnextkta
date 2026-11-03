import unittest
from unittest.mock import MagicMock, patch
import frappe
from erpnextkta.kta_stock.label_manager import LabelPrinter


class TestLabelManager(unittest.TestCase):
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

    def test_get_details_of_wo_for_label_fallback_when_packaging_qty_missing(self):
        """Packaging quantity missing or <= 0 should return 0.0 without throwing an error."""
        mock_wo = MagicMock()
        mock_wo.name = "MFG-WO-TEST-001"
        mock_wo.description = "Test Product Description"
        mock_wo.stock_uom = "Nos"
        mock_wo.production_item = "ITEM-TEST-001"
        mock_wo.qty = 50.0
        mock_wo.bom_no = "BOM-TEST-001"

        mock_bom = MagicMock()
        mock_bom.get.return_value = "01"

        self.mock_db.get_value.return_value = None  # No packaging qty defined

        with patch("erpnextkta.kta_stock.label_manager.frappe.get_doc") as mock_get_doc, \
             patch("erpnextkta.kta_stock.label_manager.frappe.get_meta") as mock_get_meta:
            mock_get_doc.side_effect = lambda dt, name: mock_wo if dt == "Work Order" else mock_bom
            mock_get_meta.return_value.has_field.return_value = True

            details = LabelPrinter.get_details_of_wo_for_label("MFG-WO-TEST-001")

        self.assertIsNotNone(details)
        self.assertEqual(details["work_order"], "MFG-WO-TEST-001")
        self.assertEqual(details["musteri_paketleme_miktari"], 0.0)
        self.assertEqual(details["material_index"], "01")

    def test_get_details_of_wo_for_label_custom_packaging_qty(self):
        """When packaging quantity is positive, it should be used."""
        mock_wo = MagicMock()
        mock_wo.name = "MFG-WO-TEST-002"
        mock_wo.description = "Test Product Description"
        mock_wo.stock_uom = "Nos"
        mock_wo.production_item = "ITEM-TEST-002"
        mock_wo.qty = 100.0
        mock_wo.bom_no = "BOM-TEST-002"

        mock_bom = MagicMock()
        mock_bom.get.return_value = "02"

        self.mock_db.get_value.return_value = 25.0

        with patch("erpnextkta.kta_stock.label_manager.frappe.get_doc") as mock_get_doc, \
             patch("erpnextkta.kta_stock.label_manager.frappe.get_meta") as mock_get_meta:
            mock_get_doc.side_effect = lambda dt, name: mock_wo if dt == "Work Order" else mock_bom
            mock_get_meta.return_value.has_field.return_value = True

            details = LabelPrinter.get_details_of_wo_for_label("MFG-WO-TEST-002")

        self.assertIsNotNone(details)
        self.assertEqual(details["musteri_paketleme_miktari"], 25.0)

    @patch.object(LabelPrinter, "_create_and_send_wo_label")
    def test_print_calculated_packs_fallback_to_entry_qty(self, mock_create_and_send):
        """When packaging quantity <= 0, single label with full entry qty should be printed."""
        mock_stock_entry_detail = MagicMock(qty=75.0)
        work_order_details = {
            "work_order": "MFG-WO-TEST-003",
            "production_item": "ITEM-TEST-003",
            "musteri_paketleme_miktari": 0,
        }

        LabelPrinter._print_calculated_packs(
            stock_entry_detail_doc=mock_stock_entry_detail,
            work_order_details=work_order_details,
            stock_entry_name="MAT-STE-TEST-001",
            stock_entry_doc=MagicMock(),
            destination_warehouse="Stores - TC",
            base_batch_no="BATCH-001",
            zebra_printer=MagicMock(),
            label_template="İş Emri Etiketi",
        )

        self.assertEqual(mock_create_and_send.call_count, 1)
        args, _ = mock_create_and_send.call_args
        self.assertEqual(args[5], 75.0)  # pack_qty equals entry_qty
        self.assertEqual(args[6], "BATCH-0010001")  # sut_code

    @patch.object(LabelPrinter, "_create_and_send_wo_label")
    def test_print_calculated_packs_with_packs_and_remainder(self, mock_create_and_send):
        """Calculates correct number of packs and remainder pack."""
        mock_stock_entry_detail = MagicMock(qty=25.0)
        work_order_details = {
            "work_order": "MFG-WO-TEST-004",
            "production_item": "ITEM-TEST-004",
            "musteri_paketleme_miktari": 10.0,
        }

        LabelPrinter._print_calculated_packs(
            stock_entry_detail_doc=mock_stock_entry_detail,
            work_order_details=work_order_details,
            stock_entry_name="MAT-STE-TEST-002",
            stock_entry_doc=MagicMock(),
            destination_warehouse="Stores - TC",
            base_batch_no="BATCH-002",
            zebra_printer=MagicMock(),
            label_template="İş Emri Etiketi",
        )

        # 2 packs of 10, 1 remainder of 5 -> total 3 calls
        self.assertEqual(mock_create_and_send.call_count, 3)
        calls = mock_create_and_send.call_args_list
        self.assertEqual(calls[0][0][5], 10.0)
        self.assertEqual(calls[0][0][6], "BATCH-0020001")
        self.assertEqual(calls[1][0][5], 10.0)
        self.assertEqual(calls[1][0][6], "BATCH-0020002")
        self.assertEqual(calls[2][0][5], 5.0)
        self.assertEqual(calls[2][0][6], "BATCH-0020003")

    @patch.object(LabelPrinter, "_create_and_send_wo_label")
    def test_print_calculated_packs_exact_division(self, mock_create_and_send):
        """When entry qty divides packaging qty evenly, exact number of packs without remainder is printed."""
        mock_stock_entry_detail = MagicMock(qty=20.0)
        work_order_details = {
            "work_order": "MFG-WO-TEST-005",
            "production_item": "ITEM-TEST-005",
            "musteri_paketleme_miktari": 10.0,
        }

        LabelPrinter._print_calculated_packs(
            stock_entry_detail_doc=mock_stock_entry_detail,
            work_order_details=work_order_details,
            stock_entry_name="MAT-STE-TEST-003",
            stock_entry_doc=MagicMock(),
            destination_warehouse="Stores - TC",
            base_batch_no="BATCH-003",
            zebra_printer=MagicMock(),
            label_template="İş Emri Etiketi",
        )

        # 2 packs of 10, 0 remainder -> total 2 calls
        self.assertEqual(mock_create_and_send.call_count, 2)
        calls = mock_create_and_send.call_args_list
        self.assertEqual(calls[0][0][5], 10.0)
        self.assertEqual(calls[0][0][6], "BATCH-0030001")
        self.assertEqual(calls[1][0][5], 10.0)
        self.assertEqual(calls[1][0][6], "BATCH-0030002")

    @patch.object(LabelPrinter, "_create_and_send_wo_label")
    def test_print_calculated_packs_entry_qty_smaller_than_pack_qty(self, mock_create_and_send):
        """When entry qty is smaller than packaging qty, single remainder label is printed."""
        mock_stock_entry_detail = MagicMock(qty=7.0)
        work_order_details = {
            "work_order": "MFG-WO-TEST-006",
            "production_item": "ITEM-TEST-006",
            "musteri_paketleme_miktari": 20.0,
        }

        LabelPrinter._print_calculated_packs(
            stock_entry_detail_doc=mock_stock_entry_detail,
            work_order_details=work_order_details,
            stock_entry_name="MAT-STE-TEST-004",
            stock_entry_doc=MagicMock(),
            destination_warehouse="Stores - TC",
            base_batch_no="BATCH-004",
            zebra_printer=MagicMock(),
            label_template="İş Emri Etiketi",
        )

        # 0 full packs, 1 remainder of 7.0 -> total 1 call
        self.assertEqual(mock_create_and_send.call_count, 1)
        args, _ = mock_create_and_send.call_args
        self.assertEqual(args[5], 7.0)
        self.assertEqual(args[6], "BATCH-0040001")
