from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import flt, nowdate

from erpnextkta.kta_stock.label_manager import LabelPrinter, print_stock_entry_labels
from erpnextkta.kta_stock.setup import setup
from erpnextkta.tests.test_utils import KTABaseTestCase, KTAUnitTestCase


class TestLabelManager(KTAUnitTestCase):
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

        with (
            patch("erpnextkta.kta_stock.label_manager.frappe.get_doc") as mock_get_doc,
            patch(
                "erpnextkta.kta_stock.label_manager.frappe.get_meta"
            ) as mock_get_meta,
        ):
            mock_get_doc.side_effect = lambda dt, name: (
                mock_wo if dt == "Work Order" else mock_bom
            )
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

        with (
            patch("erpnextkta.kta_stock.label_manager.frappe.get_doc") as mock_get_doc,
            patch(
                "erpnextkta.kta_stock.label_manager.frappe.get_meta"
            ) as mock_get_meta,
        ):
            mock_get_doc.side_effect = lambda dt, name: (
                mock_wo if dt == "Work Order" else mock_bom
            )
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
    def test_print_calculated_packs_with_packs_and_remainder(
        self, mock_create_and_send
    ):
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
    def test_print_calculated_packs_entry_qty_smaller_than_pack_qty(
        self, mock_create_and_send
    ):
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

    def test_enqueue_print_labels_by_names_parses_json_and_skips_empty(self):
        """enqueue_print_labels_by_names parses JSON input, handles empty input, and enqueues batch job."""
        from erpnextkta.kta_stock.label_manager import enqueue_print_labels_by_names

        with patch("erpnextkta.kta_stock.label_manager.frappe.enqueue") as mock_enqueue:
            empty_res = enqueue_print_labels_by_names([])
            self.assertEqual(empty_res, {"queued": 0, "label_names": []})
            mock_enqueue.assert_not_called()

            res = enqueue_print_labels_by_names(
                '["LBL-001", "LBL-002"]', user="test@example.com"
            )
            self.assertEqual(res, {"queued": 2, "label_names": ["LBL-001", "LBL-002"]})
            mock_enqueue.assert_called_once()
            _, kwargs = mock_enqueue.call_args
            self.assertEqual(kwargs["label_names"], ["LBL-001", "LBL-002"])
            self.assertEqual(kwargs["user"], "test@example.com")


class TestLabelManagerIntegration(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        self._ensure_zebra_templates()

    def _ensure_zebra_templates(self):
        if not frappe.db.exists("DocType", "KTA Zebra Templates"):
            return
        for tmpl_name in ("Depo Giriş Etiketi", "İş Emri Etiketi"):
            if not frappe.db.exists("KTA Zebra Templates", tmpl_name):
                frappe.get_doc(
                    {
                        "doctype": "KTA Zebra Templates",
                        "doctype_name": tmpl_name,
                        "zebra_template": "^XA^FD{data.item_code}|{data.sut_barcode}|{data.qty}^FS^XZ",
                    }
                ).insert(ignore_permissions=True, ignore_if_duplicate=True)
            frappe.cache().delete_value(f"kta_zebra_template_{tmpl_name}")

    def _ensure_warehouses(self):
        company = "_Test Company"
        parent_wh = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1}, "name"
        )
        names = []
        for label in ("_Test LM Src A", "_Test LM Src B", "_Test LM Dst"):
            wh_name = f"{label} - _TC"
            if not frappe.db.exists("Warehouse", wh_name):
                frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": label,
                        "company": company,
                        "parent_warehouse": parent_wh,
                    }
                ).insert(ignore_permissions=True)
            names.append(wh_name)
        return company, names[0], names[1], names[2]

    def _ensure_batch_item(self, item_code, packaging_qty=0.0):
        if not frappe.db.exists("Item Group", "_Test Item Group KTA"):
            frappe.get_doc(
                {
                    "doctype": "Item Group",
                    "item_group_name": "_Test Item Group KTA",
                    "is_group": 0,
                    "parent_item_group": "All Item Groups",
                }
            ).insert(ignore_permissions=True)
        if not frappe.db.exists("Item", item_code):
            doc = frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": item_code,
                    "item_group": "_Test Item Group KTA",
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                }
            )
            if packaging_qty > 0:
                doc.append(
                    "customer_items",
                    {
                        "customer_name": "_Test Customer",
                        "ref_code": f"REF-{item_code}",
                        "custom_musteri_paketleme_miktari": packaging_qty,
                    },
                )
            doc.insert(ignore_permissions=True)
        return item_code

    def _ensure_batch(self, batch_id, item_code):
        if not frappe.db.exists("Batch", batch_id):
            frappe.get_doc(
                {
                    "doctype": "Batch",
                    "batch_id": batch_id,
                    "item": item_code,
                    "batch_qty": 0,
                }
            ).insert(ignore_permissions=True)
        return batch_id

    def test_print_stock_entry_labels_reads_v15_bundle_and_skips_packaging_split(self):
        """Return from Production Supply with row.batch_no=None reads inward SABE and ignores customer packaging split."""
        setup()
        company, wh_src, _, wh_dst = self._ensure_warehouses()
        item_code = self._ensure_batch_item("_TEST-LM-V15-ITEM", packaging_qty=10.0)
        batch_no = "5511A100001"
        self._ensure_batch(batch_no, item_code)

        # Receive 35 units into wh_src via v15 bundle (without batch_no on row)
        receipt = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": company,
                "posting_date": nowdate(),
                "items": [
                    {
                        "item_code": item_code,
                        "t_warehouse": wh_src,
                        "qty": 35.0,
                        "basic_rate": 10.0,
                        "batch_no": batch_no,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        receipt.insert(ignore_permissions=True)
        receipt.submit()

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            transfer = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Return from Production Supply",
                    "purpose": "Material Transfer",
                    "company": company,
                    "posting_date": nowdate(),
                    "items": [
                        {
                            "item_code": item_code,
                            "s_warehouse": wh_src,
                            "t_warehouse": wh_dst,
                            "qty": 35.0,
                            "batch_no": batch_no,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            )
            transfer.insert(ignore_permissions=True)
            transfer.submit()

            # Simulate v15 submitted row where row.batch_no is cleared and serial_and_batch_bundle holds the inward entry
            transfer.reload()
            row = transfer.items[0]
            self.assertTrue(row.serial_and_batch_bundle)
            frappe.db.set_value("Stock Entry Detail", row.name, "batch_no", None)
            frappe.db.delete(
                "KTA Stock Label",
                {"sut_barcode": batch_no, "label_type": "Depo Giriş Etiketi"},
            )

            print_stock_entry_labels(transfer.name)

        labels = frappe.get_all(
            "KTA Stock Label",
            filters={"sut_barcode": batch_no, "label_type": "Depo Giriş Etiketi"},
            fields=[
                "name",
                "qty",
                "source_warehouse",
                "target_warehouse",
                "sut_barcode",
            ],
        )
        self.assertEqual(len(labels), 1)
        self.assertEqual(flt(labels[0].qty), 35.0)
        self.assertEqual(labels[0].source_warehouse, wh_src)
        self.assertEqual(labels[0].target_warehouse, wh_dst)

    def test_print_stock_entry_labels_repack_matches_source_by_item_and_lot(self):
        """Multi-row Repack matches incoming row to its own item_code + base_lot source warehouse."""
        setup()
        company, wh_a, wh_b, wh_dst = self._ensure_warehouses()
        item_a = self._ensure_batch_item("_TEST-LM-LOT-A")
        item_b = self._ensure_batch_item("_TEST-LM-LOT-B")

        for item_code, wh, batch_no in (
            (item_a, wh_a, "1111A110001"),
            (item_a, wh_b, "2222B220001"),
            (item_b, wh_b, "3333C330001"),
        ):
            self._ensure_batch(batch_no, item_code)
            se_rec = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Material Receipt",
                    "purpose": "Material Receipt",
                    "company": company,
                    "posting_date": nowdate(),
                    "items": [
                        {
                            "item_code": item_code,
                            "t_warehouse": wh,
                            "qty": 20.0,
                            "basic_rate": 10.0,
                            "batch_no": batch_no,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            )
            se_rec.insert(ignore_permissions=True)
            se_rec.submit()

        self._ensure_batch("2222B220002", item_a)
        self._ensure_batch("3333C330002", item_b)

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            repack = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Package Split",
                    "purpose": "Repack",
                    "company": company,
                    "posting_date": nowdate(),
                    "items": [
                        {
                            "item_code": item_a,
                            "s_warehouse": wh_a,
                            "qty": 20.0,
                            "batch_no": "1111A110001",
                            "use_serial_batch_fields": 1,
                        },
                        {
                            "item_code": item_a,
                            "s_warehouse": wh_b,
                            "qty": 20.0,
                            "batch_no": "2222B220001",
                            "use_serial_batch_fields": 1,
                        },
                        {
                            "item_code": item_a,
                            "t_warehouse": wh_dst,
                            "qty": 20.0,
                            "batch_no": "2222B220002",
                            "is_finished_item": 1,
                            "use_serial_batch_fields": 1,
                        },
                    ],
                }
            )
            repack.insert(ignore_permissions=True)
            repack.submit()

            frappe.db.delete(
                "KTA Stock Label",
                {"sut_barcode": "2222B220002", "label_type": "Depo Giriş Etiketi"},
            )
            print_stock_entry_labels(repack.name)

        lbl = frappe.db.get_value(
            "KTA Stock Label",
            {"sut_barcode": "2222B220002", "label_type": "Depo Giriş Etiketi"},
            ["source_warehouse", "target_warehouse", "qty"],
            as_dict=True,
        )
        self.assertIsNotNone(lbl)
        self.assertEqual(lbl.source_warehouse, wh_b)
        self.assertEqual(lbl.target_warehouse, wh_dst)
        self.assertEqual(flt(lbl.qty), 20.0)

    def test_clear_empty_labels_deletes_zero_balance_batch_even_with_sabe_history(self):
        """clear_empty_labels deletes labels whose net batch ledger qty <= 0 even when SABE history exists."""
        company, wh_a, _, wh_dst = self._ensure_warehouses()
        item_code = self._ensure_batch_item("_TEST-LM-CLEAR-ITEM")
        empty_batch = "4411D440001"
        active_batch = "4411D440002"
        self._ensure_batch(empty_batch, item_code)
        self._ensure_batch(active_batch, item_code)

        for batch_no, qty in ((empty_batch, 15.0), (active_batch, 25.0)):
            rec = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Material Receipt",
                    "purpose": "Material Receipt",
                    "company": company,
                    "posting_date": nowdate(),
                    "items": [
                        {
                            "item_code": item_code,
                            "t_warehouse": wh_a,
                            "qty": qty,
                            "basic_rate": 10.0,
                            "batch_no": batch_no,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            )
            rec.insert(ignore_permissions=True)
            rec.submit()

        # Issue all 15 of empty_batch so SABE history exists but net balance is 0
        issue = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Issue",
                "purpose": "Material Issue",
                "company": company,
                "posting_date": nowdate(),
                "items": [
                    {
                        "item_code": item_code,
                        "s_warehouse": wh_a,
                        "qty": 15.0,
                        "allow_zero_valuation_rate": 1,
                        "batch_no": empty_batch,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        issue.insert(ignore_permissions=True)
        issue.submit()

        empty_lbl = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "item_code": item_code,
                "qty": 15.0,
                "uom": "Nos",
                "batch": empty_batch,
                "sut_barcode": empty_batch,
                "target_warehouse": wh_dst,
            }
        ).insert(ignore_permissions=True)
        empty_log = frappe.get_doc(
            {
                "doctype": "KTA Print Log",
                "label_doctype": "KTA Stock Label",
                "label_name": empty_lbl.name,
                "status": "Success",
            }
        ).insert(ignore_permissions=True)

        active_lbl = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "item_code": item_code,
                "qty": 25.0,
                "uom": "Nos",
                "batch": active_batch,
                "sut_barcode": active_batch,
                "target_warehouse": wh_a,
            }
        ).insert(ignore_permissions=True)

        LabelPrinter.clear_empty_labels(
            pairs=[(item_code, empty_batch), (item_code, active_batch)]
        )

        self.assertFalse(frappe.db.exists("KTA Stock Label", empty_lbl.name))
        self.assertFalse(frappe.db.exists("KTA Print Log", empty_log.name))
        self.assertTrue(frappe.db.exists("KTA Stock Label", active_lbl.name))
