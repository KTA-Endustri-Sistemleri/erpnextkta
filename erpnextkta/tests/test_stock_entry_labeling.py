from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import cint, flt, nowdate

from erpnextkta.kta_stock.services.relabeling_service import (
    create_package_split_repack,
)
from erpnextkta.kta_stock.setup import setup
from erpnextkta.tests.test_utils import KTABaseTestCase, setup_test_fiscal_years


class TestStockEntryLabeling(KTABaseTestCase):
    """Integration tests for Wave 2 Stock Entry labeling, naming, and cleanup."""

    COMPANY = "_Test Company"
    ABBR = "_TC"

    def setUp(self):
        super().setUp()
        setup()
        setup_test_fiscal_years(self.COMPANY)
        self._prev_po_required = frappe.db.get_single_value(
            "Buying Settings", "po_required"
        )
        frappe.db.set_single_value("Buying Settings", "po_required", "No")

    def tearDown(self):
        if getattr(self, "_prev_po_required", None) is not None:
            frappe.db.set_single_value(
                "Buying Settings", "po_required", self._prev_po_required
            )
        super().tearDown()

    def _ensure_warehouses(self) -> tuple[str, str, str]:
        parent_wh = frappe.db.get_value(
            "Warehouse", {"company": self.COMPANY, "is_group": 1}, "name"
        )
        names = []
        for label in (
            "_Test SE Label Src",
            "_Test SE Label Dst",
            "_Test SE Label Prod",
        ):
            wh_name = f"{label} - {self.ABBR}"
            if not frappe.db.exists("Warehouse", wh_name):
                frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": label,
                        "company": self.COMPANY,
                        "parent_warehouse": parent_wh,
                    }
                ).insert(ignore_permissions=True)
            names.append(wh_name)
        return names[0], names[1], names[2]

    def _ensure_batch_item(self, item_code: str) -> str:
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
            frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": item_code,
                    "item_group": "_Test Item Group KTA",
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                    "inspection_required_before_purchase": 0,
                }
            ).insert(ignore_permissions=True)
        else:
            frappe.db.set_value(
                "Item",
                item_code,
                {
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "inspection_required_before_purchase": 0,
                },
            )
        return item_code

    def _ensure_batch(self, batch_id: str, item_code: str) -> str:
        if not frappe.db.exists("Batch", batch_id):
            doc = frappe.get_doc(
                {
                    "doctype": "Batch",
                    "batch_id": batch_id,
                    "item": item_code,
                    "batch_qty": 0,
                }
            )
            doc.flags.ignore_links = True
            doc.insert(ignore_permissions=True)
        return batch_id

    def _ensure_supplier(self) -> str:
        supplier = "_Test Supplier"
        if not frappe.db.exists("Supplier", supplier):
            frappe.get_doc(
                {
                    "doctype": "Supplier",
                    "supplier_name": supplier,
                    "supplier_group": "All Supplier Groups",
                    "supplier_type": "Company",
                }
            ).insert(ignore_permissions=True)
        return supplier

    def _receive_via_stock_entry(
        self, item_code: str, warehouse: str, batch_no: str, qty: float
    ):
        self._ensure_batch(batch_no, item_code)
        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": self.COMPANY,
                "posting_date": nowdate(),
                "items": [
                    {
                        "item_code": item_code,
                        "t_warehouse": warehouse,
                        "qty": flt(qty),
                        "basic_rate": 10.0,
                        "batch_no": batch_no,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_pr_with_box_batch(
        self, item_code: str, warehouse: str, qty: float
    ) -> tuple[object, str]:
        supplier = self._ensure_supplier()
        currency = (
            frappe.db.get_value("Company", self.COMPANY, "default_currency") or "INR"
        )
        price_list = (
            frappe.db.get_value("Price List", {"buying": 1}, "name")
            or "Standard Buying"
        )
        posting_date = nowdate()
        pr = frappe.get_doc(
            {
                "doctype": "Purchase Receipt",
                "company": self.COMPANY,
                "supplier": supplier,
                "posting_date": posting_date,
                "currency": currency,
                "conversion_rate": 1.0,
                "buying_price_list": price_list,
                "price_list_currency": currency,
                "plc_conversion_rate": 1.0,
                "supplier_delivery_note": "TEST-SDN-SE-LBL",
                "irsaliye_tarihi": posting_date,
                "irsaliye_no": "TEST-IRS-SE-LBL",
                "items": [
                    {
                        "item_code": item_code,
                        "qty": flt(qty),
                        "rate": 10.0,
                        "warehouse": warehouse,
                        "custom_split_qty": flt(qty),
                        "custom_do_not_split": 0,
                    }
                ],
            }
        )
        pr.flags.ignore_mandatory = True
        pr.insert(ignore_permissions=True)
        pr.submit()
        pr.reload()

        box_batch = f"{pr.items[0].batch_no}0001"
        return pr, box_batch

    def test_package_split_inward_bundle_naming_and_fallback(self):
        """Package Split inward bundle uses 7-char base_lot when unused, then falls back cleanly."""
        wh_src, wh_dst, _ = self._ensure_warehouses()
        item_code = self._ensure_batch_item("_TEST-SELBL-BUNDLE-ITEM")
        self._receive_via_stock_entry(item_code, wh_src, "RAW-SRC-LOT-01", 100.0)

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            res1 = create_package_split_repack(
                item_code=item_code,
                source_warehouse=wh_src,
                target_warehouse=wh_dst,
                source_batch="RAW-SRC-LOT-01",
                split_qtys=[60.0],
            )
            base_lot = res1["base_lot"]
            first_inward_bundle = frappe.db.get_value(
                "Serial and Batch Bundle",
                {
                    "voucher_type": "Stock Entry",
                    "voucher_no": res1["stock_entry"],
                    "type_of_transaction": "Inward",
                },
                "name",
            )
            self.assertEqual(len(base_lot), 7)
            self.assertEqual(first_inward_bundle, base_lot)

            res2 = create_package_split_repack(
                item_code=item_code,
                source_warehouse=wh_dst,
                target_warehouse=wh_src,
                source_batch=res1["created_batches"][0]["batch_no"],
                split_qtys=[20.0],
            )
            second_inward_bundle = frappe.db.get_value(
                "Serial and Batch Bundle",
                {
                    "voucher_type": "Stock Entry",
                    "voucher_no": res2["stock_entry"],
                    "type_of_transaction": "Inward",
                },
                "name",
            )
            self.assertTrue(second_inward_bundle)
            self.assertNotEqual(second_inward_bundle, base_lot)

    def test_non_printable_standard_stock_entries_are_silent(self):
        """Standard Material Transfer and Repack do not enqueue label printing or create labels."""
        wh_src, wh_dst, wh_prod = self._ensure_warehouses()
        item_code = self._ensure_batch_item("_TEST-SELBL-SILENT-ITEM")
        self._receive_via_stock_entry(item_code, wh_src, "SILENT10001", 50.0)
        self._ensure_batch("SILENT10002", item_code)

        with patch("erpnextkta.overrides.KTAStockEntry.frappe.enqueue") as mock_enqueue:
            transfer = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Material Transfer",
                    "purpose": "Material Transfer",
                    "company": self.COMPANY,
                    "posting_date": nowdate(),
                    "items": [
                        {
                            "item_code": item_code,
                            "s_warehouse": wh_src,
                            "t_warehouse": wh_dst,
                            "qty": 20.0,
                            "batch_no": "SILENT10001",
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            )
            transfer.insert(ignore_permissions=True)
            transfer.submit()

            repack = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Repack",
                    "purpose": "Repack",
                    "company": self.COMPANY,
                    "posting_date": nowdate(),
                    "items": [
                        {
                            "item_code": item_code,
                            "s_warehouse": wh_dst,
                            "qty": 10.0,
                            "batch_no": "SILENT10001",
                            "use_serial_batch_fields": 1,
                            "allow_zero_valuation_rate": 1,
                        },
                        {
                            "item_code": item_code,
                            "t_warehouse": wh_prod,
                            "qty": 10.0,
                            "batch_no": "SILENT10002",
                            "is_finished_item": 1,
                            "use_serial_batch_fields": 1,
                            "allow_zero_valuation_rate": 1,
                        },
                    ],
                }
            )
            repack.insert(ignore_permissions=True)
            repack.submit()

            mock_enqueue.assert_not_called()

        self.assertEqual(
            frappe.db.count("KTA Stock Label", {"item_code": item_code}), 0
        )

    def test_package_split_rejects_multiple_target_items_in_validate(self):
        """Package Split with two distinct target items throws ValidationError in validate()."""
        wh_src, wh_dst, _ = self._ensure_warehouses()
        item_a = self._ensure_batch_item("_TEST-SELBL-MULTI-A")
        item_b = self._ensure_batch_item("_TEST-SELBL-MULTI-B")

        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Package Split",
                "purpose": "Repack",
                "company": self.COMPANY,
                "posting_date": nowdate(),
                "items": [
                    {
                        "item_code": item_a,
                        "s_warehouse": wh_src,
                        "qty": 10.0,
                        "allow_zero_valuation_rate": 1,
                    },
                    {
                        "item_code": item_a,
                        "t_warehouse": wh_dst,
                        "qty": 5.0,
                        "is_finished_item": 1,
                        "allow_zero_valuation_rate": 1,
                    },
                    {
                        "item_code": item_b,
                        "t_warehouse": wh_dst,
                        "qty": 5.0,
                        "is_finished_item": 1,
                        "allow_zero_valuation_rate": 1,
                    },
                ],
            }
        )
        with self.assertRaises(frappe.ValidationError):
            se.insert(ignore_permissions=True)

    def test_return_from_production_supply_submit_and_cancel_preserves_pr_label(self):
        """Return from Production Supply updates PR label on submit and restores qty on cancel."""
        wh_src, _, wh_prod = self._ensure_warehouses()
        item_code = self._ensure_batch_item("_TEST-SELBL-RET-ITEM")
        pr, box_batch = self._create_pr_with_box_batch(item_code, wh_src, 100.0)

        # Move full box to production supply first via silent Material Transfer
        issue_to_prod = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Transfer",
                "purpose": "Material Transfer",
                "company": self.COMPANY,
                "posting_date": nowdate(),
                "items": [
                    {
                        "item_code": item_code,
                        "s_warehouse": wh_src,
                        "t_warehouse": wh_prod,
                        "qty": 100.0,
                        "batch_no": box_batch,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        issue_to_prod.insert(ignore_permissions=True)
        issue_to_prod.submit()

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            ret_se = frappe.get_doc(
                {
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Return from Production Supply",
                    "purpose": "Material Transfer",
                    "company": self.COMPANY,
                    "posting_date": nowdate(),
                    "items": [
                        {
                            "item_code": item_code,
                            "s_warehouse": wh_prod,
                            "t_warehouse": wh_src,
                            "qty": 40.0,
                            "batch_no": box_batch,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            )
            ret_se.insert(ignore_permissions=True)
            ret_se.submit()

        lbl = frappe.db.get_value(
            "KTA Stock Label",
            {"sut_barcode": box_batch, "label_type": "Depo Giriş Etiketi"},
            ["reference_doctype", "reference_name", "qty", "target_warehouse"],
            as_dict=True,
        )
        self.assertIsNotNone(lbl)
        self.assertEqual(lbl.reference_doctype, "Purchase Receipt")
        self.assertEqual(lbl.reference_name, pr.name)
        self.assertEqual(flt(lbl.qty), 40.0)
        self.assertEqual(lbl.target_warehouse, wh_src)

        ret_se.reload()
        ret_se.cancel()

        lbl_after_cancel = frappe.db.get_value(
            "KTA Stock Label",
            {"sut_barcode": box_batch, "label_type": "Depo Giriş Etiketi"},
            ["reference_doctype", "reference_name", "qty", "target_warehouse"],
            as_dict=True,
        )
        self.assertIsNotNone(lbl_after_cancel)
        self.assertEqual(lbl_after_cancel.reference_doctype, "Purchase Receipt")
        self.assertEqual(lbl_after_cancel.reference_name, pr.name)
        self.assertEqual(flt(lbl_after_cancel.qty), 100.0)
        self.assertEqual(lbl_after_cancel.target_warehouse, wh_prod)

    def test_package_split_submit_cancel_and_trash_lifecycle(self):
        """Package Split updates source PR label and mints 0002; cancel disables 0002 and restores 0001."""
        wh_src, wh_dst, _ = self._ensure_warehouses()
        item_code = self._ensure_batch_item("_TEST-SELBL-SPLIT-ITEM")
        pr, src_batch = self._create_pr_with_box_batch(item_code, wh_src, 100.0)

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            res = create_package_split_repack(
                item_code=item_code,
                source_warehouse=wh_src,
                target_warehouse=wh_dst,
                source_batch=src_batch,
                split_qtys=[40.0],
            )

        se_name = res["stock_entry"]
        child_batch = res["created_batches"][0]["batch_no"]
        self.assertTrue(child_batch.endswith("0002"))

        src_lbl = frappe.db.get_value(
            "KTA Stock Label",
            {"sut_barcode": src_batch, "label_type": "Depo Giriş Etiketi"},
            ["reference_doctype", "reference_name", "qty"],
            as_dict=True,
        )
        self.assertIsNotNone(src_lbl)
        self.assertEqual(src_lbl.reference_doctype, "Purchase Receipt")
        self.assertEqual(src_lbl.reference_name, pr.name)
        self.assertEqual(flt(src_lbl.qty), 60.0)

        child_lbl = frappe.db.get_value(
            "KTA Stock Label",
            {"sut_barcode": child_batch, "label_type": "Depo Giriş Etiketi"},
            ["reference_doctype", "reference_name", "qty", "target_warehouse"],
            as_dict=True,
        )
        self.assertIsNotNone(child_lbl)
        self.assertEqual(child_lbl.reference_doctype, "Stock Entry")
        self.assertEqual(child_lbl.reference_name, se_name)
        self.assertEqual(flt(child_lbl.qty), 40.0)
        self.assertEqual(child_lbl.target_warehouse, wh_dst)

        se_doc = frappe.get_doc("Stock Entry", se_name)
        se_doc.cancel()

        self.assertFalse(
            frappe.db.exists(
                "KTA Stock Label",
                {"sut_barcode": child_batch, "label_type": "Depo Giriş Etiketi"},
            )
        )
        self.assertEqual(cint(frappe.db.get_value("Batch", child_batch, "disabled")), 1)
        self.assertEqual(
            flt(frappe.db.get_value("Batch", child_batch, "batch_qty")), 0.0
        )

        src_lbl_restored = frappe.db.get_value(
            "KTA Stock Label",
            {"sut_barcode": src_batch, "label_type": "Depo Giriş Etiketi"},
            ["reference_doctype", "reference_name", "qty"],
            as_dict=True,
        )
        self.assertIsNotNone(src_lbl_restored)
        self.assertEqual(src_lbl_restored.reference_doctype, "Purchase Receipt")
        self.assertEqual(src_lbl_restored.reference_name, pr.name)
        self.assertEqual(flt(src_lbl_restored.qty), 100.0)

        # Trashing an already-cancelled Package Split must remain idempotent and keep PR label intact
        se_doc.reload()
        se_doc.delete()
        src_lbl_after_trash = frappe.db.get_value(
            "KTA Stock Label",
            {"sut_barcode": src_batch, "label_type": "Depo Giriş Etiketi"},
            ["reference_doctype", "reference_name", "qty"],
            as_dict=True,
        )
        self.assertIsNotNone(src_lbl_after_trash)
        self.assertEqual(src_lbl_after_trash.reference_doctype, "Purchase Receipt")
        self.assertEqual(flt(src_lbl_after_trash.qty), 100.0)
        self.assertEqual(cint(frappe.db.get_value("Batch", child_batch, "disabled")), 1)
