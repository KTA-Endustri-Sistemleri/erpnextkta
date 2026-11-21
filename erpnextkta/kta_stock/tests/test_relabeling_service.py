import importlib
import os
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import cint, flt, nowdate

from erpnextkta.kta_stock.services import stock_reconciliation_lock
from erpnextkta.kta_stock.setup import setup
from erpnextkta.tests.test_utils import KTABaseTestCase


class TestRelabelingService(KTABaseTestCase):
    def tearDown(self):
        frappe.flags.pop("kta_ignore_reco_lock", None)
        super().tearDown()

    def _create_test_purchase_receipt(
        self,
        company,
        supplier,
        item_code,
        warehouse,
        qty,
        rate,
        posting_date,
        delivery_note,
    ):
        currency = frappe.db.get_value("Company", company, "default_currency") or "INR"
        price_list = (
            frappe.db.get_value("Price List", {"buying": 1}, "name")
            or "Standard Buying"
        )
        pr = frappe.get_doc(
            {
                "doctype": "Purchase Receipt",
                "company": company,
                "supplier": supplier,
                "posting_date": posting_date,
                "currency": currency,
                "conversion_rate": 1.0,
                "buying_price_list": price_list,
                "price_list_currency": currency,
                "plc_conversion_rate": 1.0,
                "supplier_delivery_note": delivery_note,
                "items": [
                    {
                        "item_code": item_code,
                        "qty": qty,
                        "rate": rate,
                        "warehouse": warehouse,
                    }
                ],
            }
        )
        pr.flags.ignore_mandatory = True
        pr.insert(ignore_permissions=True)
        return pr

    def _ensure_test_warehouses(self):
        company = "_Test Company"
        parent_wh = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1}, "name"
        )
        warehouses = []
        for wh_label in ("_Test Relabel Src", "_Test Relabel Dst"):
            wh_name = f"{wh_label} - _TC"
            if not frappe.db.exists("Warehouse", wh_name):
                frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": wh_label,
                        "company": company,
                        "parent_warehouse": parent_wh,
                    }
                ).insert(ignore_permissions=True)
            warehouses.append(wh_name)
        return company, warehouses[0], warehouses[1]

    def _ensure_batch_item(self, item_code="_TEST-RELABEL-BATCH-ITEM"):
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
                }
            ).insert(ignore_permissions=True)
        else:
            frappe.db.set_value(
                "Item",
                item_code,
                {"has_batch_no": 1, "is_stock_item": 1, "stock_uom": "Nos"},
            )
        return item_code

    def _create_batch(self, batch_id, item_code, **kwargs):
        if frappe.db.exists("Batch", batch_id):
            return frappe.get_doc("Batch", batch_id)
        doc_dict = {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
            "batch_qty": 0,
        }
        doc_dict.update(kwargs)
        doc = frappe.get_doc(doc_dict)
        doc.flags.ignore_links = True
        doc.insert(ignore_permissions=True)
        return doc

    def _receive_batch_stock(
        self, item_code, warehouse, batch_no, qty, rate=10.0, company="_Test Company"
    ):
        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": company,
                "posting_date": nowdate(),
                "items": [
                    {
                        "item_code": item_code,
                        "t_warehouse": warehouse,
                        "qty": flt(qty),
                        "basic_rate": flt(rate),
                        "allow_zero_valuation_rate": 1 if flt(rate) <= 0 else 0,
                        "batch_no": batch_no,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _issue_batch_stock(
        self, item_code, warehouse, batch_no, qty, company="_Test Company"
    ):
        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Issue",
                "purpose": "Material Issue",
                "company": company,
                "posting_date": nowdate(),
                "items": [
                    {
                        "item_code": item_code,
                        "s_warehouse": warehouse,
                        "qty": flt(qty),
                        "allow_zero_valuation_rate": 1,
                        "batch_no": batch_no,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def test_rest_api_modules_migrated(self):
        """All 3 services are importable under kta_stock.services and respect kta_ignore_reco_lock."""
        reco_service = importlib.import_module(
            "erpnextkta.kta_stock.services.stock_reconciliation_service"
        )
        dashboard_service = importlib.import_module(
            "erpnextkta.kta_stock.services.stock_reconciliation_dashboard_service"
        )
        lock_service = importlib.import_module(
            "erpnextkta.kta_stock.services.stock_reconciliation_lock"
        )

        self.assertTrue(hasattr(reco_service, "get_items_static"))
        self.assertTrue(
            hasattr(reco_service, "create_stock_reco_docs_for_warehouse_group")
        )
        self.assertTrue(
            hasattr(reco_service, "_job_create_stock_reco_docs_for_warehouse_group")
        )
        self.assertTrue(hasattr(dashboard_service, "get_years"))
        self.assertTrue(hasattr(dashboard_service, "get_dashboard"))
        self.assertTrue(hasattr(dashboard_service, "get_item_details"))
        self.assertTrue(hasattr(lock_service, "validate_stock_entry_warehouse_lock"))
        self.assertTrue(
            hasattr(lock_service, "validate_unique_draft_stock_reco_per_set_warehouse")
        )

        legacy_dir = frappe.get_app_path("erpnextkta", "rest-api")
        self.assertFalse(os.path.exists(legacy_dir))

        stock_entry_doc = frappe._dict(
            {"items": [{"s_warehouse": "_Test Warehouse - _TC"}]}
        )

        with (
            patch.object(stock_reconciliation_lock, "_can_bypass", return_value=False),
            patch.object(
                stock_reconciliation_lock,
                "_get_ancestors_including_self",
                return_value={"_Test Warehouse - _TC"},
            ),
            patch.object(
                stock_reconciliation_lock,
                "_find_draft_reco_lock_by_set_warehouse",
                return_value=("SR-TEST-0001", "_Test Warehouse - _TC"),
            ),
        ):
            frappe.flags.kta_ignore_reco_lock = True
            stock_reconciliation_lock.validate_stock_entry_warehouse_lock(
                stock_entry_doc
            )

            frappe.flags.kta_ignore_reco_lock = False
            with self.assertRaises(frappe.ValidationError):
                stock_reconciliation_lock.validate_stock_entry_warehouse_lock(
                    stock_entry_doc
                )

            frappe.flags.pop("kta_ignore_reco_lock", None)
            with self.assertRaises(frappe.ValidationError):
                stock_reconciliation_lock.validate_stock_entry_warehouse_lock(
                    stock_entry_doc
                )

    def test_setup_stock_entry_types(self):
        """setup() creates/updates custom Stock Entry Types and clears standard Repack label settings."""
        if not frappe.db.exists("Stock Entry Type", "Repack"):
            frappe.get_doc(
                {
                    "doctype": "Stock Entry Type",
                    "name": "Repack",
                    "purpose": "Repack",
                    "is_standard": 1,
                }
            ).insert(ignore_permissions=True)

        frappe.db.set_value(
            "Stock Entry Type",
            "Repack",
            {
                "is_standard": 1,
                "custom_etiket_basilabilir": 1,
                "custom_etiket_sablonu": "Repack Etiketi",
            },
        )

        setup()
        setup()

        return_type = frappe.get_doc(
            "Stock Entry Type", "Return from Production Supply"
        )
        self.assertEqual(return_type.purpose, "Material Transfer")
        self.assertEqual(cint(return_type.is_standard), 0)
        self.assertEqual(cint(return_type.custom_etiket_basilabilir), 1)
        self.assertEqual(return_type.custom_etiket_sablonu, "Depo Giriş Etiketi")

        split_type = frappe.get_doc("Stock Entry Type", "Package Split")
        self.assertEqual(split_type.purpose, "Repack")
        self.assertEqual(cint(split_type.is_standard), 0)
        self.assertEqual(cint(split_type.custom_etiket_basilabilir), 1)
        self.assertEqual(split_type.custom_etiket_sablonu, "Depo Giriş Etiketi")

        repack_type = frappe.get_doc("Stock Entry Type", "Repack")
        self.assertEqual(cint(repack_type.is_standard), 1)
        self.assertEqual(cint(repack_type.custom_etiket_basilabilir), 0)
        self.assertFalse(repack_type.custom_etiket_sablonu)

    def test_is_standard_kta_box_batch_and_extract_base_lot(self):
        """Validates 7-char uppercase alphanumeric + 4-digit non-0000 box batch rule."""
        from erpnextkta.kta_stock.services.relabeling_service import (
            extract_base_lot,
            is_standard_kta_box_batch,
        )

        self.assertTrue(is_standard_kta_box_batch("6640A670001"))
        self.assertTrue(is_standard_kta_box_batch("A1B2C3D9999"))
        self.assertEqual(extract_base_lot("6640A670001"), "6640A67")

        for invalid in (
            "6640A670000",
            "LEGACY-10040004",
            "R202400035-01",
            "6640a670001",
            "6640A67",
            None,
            "",
        ):
            self.assertFalse(
                is_standard_kta_box_batch(invalid), f"Expected False for {invalid!r}"
            )
            self.assertIsNone(extract_base_lot(invalid))

    def test_allocate_next_box_batches_and_generate_new_base_lot(self):
        """allocate_next_box_batches continues sequence and inherits metadata; generate_new_base_lot makes 7-char root."""
        from erpnextkta.kta_stock.services.relabeling_service import (
            allocate_next_box_batches,
            generate_new_base_lot,
        )

        item_code = self._ensure_batch_item()
        company, wh_src, _ = self._ensure_test_warehouses()
        supplier = "_Test Supplier"

        pr = self._create_test_purchase_receipt(
            company=company,
            supplier=supplier,
            item_code=item_code,
            warehouse=wh_src,
            qty=10,
            rate=15.0,
            posting_date="2025-01-10",
            delivery_note="IRS-TEST-001",
        )

        source_meta = {
            "supplier": supplier,
            "reference_doctype": "Purchase Receipt",
            "reference_name": pr.name,
            "manufacturing_date": "2025-01-10",
            "expiry_date": "2027-01-10",
            "stock_uom": "Nos",
        }
        self._create_batch("9911T010001", item_code, **source_meta)
        self._create_batch("9911T010002", item_code, **source_meta)

        allocated = allocate_next_box_batches(
            "9911T01", 1, item_code, source_meta=source_meta
        )
        self.assertEqual(allocated, ["9911T010003"])

        child = frappe.get_doc("Batch", "9911T010003")
        self.assertEqual(child.supplier, supplier)
        self.assertEqual(child.reference_doctype, "Purchase Receipt")
        self.assertEqual(child.reference_name, pr.name)
        self.assertEqual(str(child.manufacturing_date), "2025-01-10")
        self.assertEqual(str(child.expiry_date), "2027-01-10")
        self.assertEqual(flt(child.batch_qty), 0.0)

        new_lot = generate_new_base_lot(
            item_code=item_code,
            reference_doctype="Purchase Receipt",
            reference_name=pr.name,
            manufacturing_date="2025-01-10",
            supplier=supplier,
        )
        self.assertRegex(new_lot, r"^[A-Z0-9]{7}$")
        root_batch = frappe.get_doc("Batch", new_lot)
        self.assertEqual(flt(root_batch.batch_qty), 0.0)
        self.assertEqual(root_batch.reference_doctype, "Purchase Receipt")
        self.assertEqual(root_batch.reference_name, pr.name)
        self.assertEqual(root_batch.supplier, supplier)

    def test_upsert_box_label_preserves_pr_reference(self):
        """upsert_box_label updates qty/warehouses on existing PR label without overwriting Purchase Receipt reference."""
        from erpnextkta.kta_stock.services.relabeling_service import upsert_box_label

        item_code = self._ensure_batch_item()
        _, wh_src, wh_dst = self._ensure_test_warehouses()
        self._create_batch("8811A220001", item_code)

        pr_label = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "reference_doctype": "Purchase Receipt",
                "reference_name": "MAT-PRE-TEST-001",
                "item_code": item_code,
                "qty": 100.0,
                "uom": "Nos",
                "batch": "8811A220001",
                "sut_barcode": "8811A220001",
                "quality_ref": "QI-TEST-001",
                "supplier_delivery_note": "IRS-001",
                "gr_posting_date": "2025-01-10",
            }
        )
        pr_label.flags.ignore_links = True
        pr_label.insert(ignore_permissions=True)

        updated_name = upsert_box_label(
            item_code=item_code,
            batch_no="8811A220001",
            qty=65.0,
            target_warehouse=wh_dst,
            source_warehouse=wh_src,
            reference_doctype="Stock Entry",
            reference_name="MAT-STE-TEST-001",
            posting_date="2026-11-21",
        )

        self.assertEqual(updated_name, pr_label.name)
        count = frappe.db.count(
            "KTA Stock Label",
            {"sut_barcode": "8811A220001", "label_type": "Depo Giriş Etiketi"},
        )
        self.assertEqual(count, 1)

        reloaded = frappe.get_doc("KTA Stock Label", pr_label.name)
        self.assertEqual(flt(reloaded.qty), 65.0)
        self.assertEqual(reloaded.target_warehouse, wh_dst)
        self.assertEqual(reloaded.source_warehouse, wh_src)
        self.assertEqual(reloaded.reference_doctype, "Purchase Receipt")
        self.assertEqual(reloaded.reference_name, "MAT-PRE-TEST-001")
        self.assertEqual(reloaded.quality_ref, "QI-TEST-001")
        self.assertEqual(reloaded.supplier_delivery_note, "IRS-001")

    def test_sync_batch_label_to_ledger_balance(self):
        """sync_batch_label_to_ledger_balance syncs positive balance and deletes label + print logs at 0."""
        from erpnextkta.kta_stock.services.relabeling_service import (
            sync_batch_label_to_ledger_balance,
        )

        item_code = self._ensure_batch_item()
        company, wh_src, _ = self._ensure_test_warehouses()
        batch_no = "7711B330001"
        self._create_batch(batch_no, item_code)
        self._receive_batch_stock(
            item_code, wh_src, batch_no, 50.0, rate=10.0, company=company
        )

        lbl = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "reference_doctype": "Purchase Receipt",
                "reference_name": "MAT-PRE-SYNC-001",
                "item_code": item_code,
                "qty": 100.0,
                "uom": "Nos",
                "batch": batch_no,
                "sut_barcode": batch_no,
            }
        )
        lbl.flags.ignore_links = True
        lbl.insert(ignore_permissions=True)

        print_log = frappe.get_doc(
            {
                "doctype": "KTA Print Log",
                "label_doctype": "KTA Stock Label",
                "label_name": lbl.name,
                "status": "Success",
            }
        ).insert(ignore_permissions=True)

        sync_batch_label_to_ledger_balance(item_code, batch_no)
        lbl.reload()
        self.assertEqual(flt(lbl.qty), 50.0)
        self.assertEqual(lbl.target_warehouse, wh_src)

        self._issue_batch_stock(item_code, wh_src, batch_no, 50.0, company=company)
        sync_batch_label_to_ledger_balance(item_code, batch_no)

        self.assertFalse(frappe.db.exists("KTA Stock Label", lbl.name))
        self.assertFalse(frappe.db.exists("KTA Print Log", print_log.name))

    def test_create_package_split_repack_partial_standard_box(self):
        """Partial split of standard 7+4 box (1000 -> [350]) mints 0002, keeps Package Split type, and updates PR label."""
        from erpnextkta.kta_stock.services.relabeling_service import (
            create_package_split_repack,
            get_batch_ledger_balances,
        )

        setup()
        item_code = self._ensure_batch_item()
        company, wh_src, wh_dst = self._ensure_test_warehouses()
        base_lot = f"T{frappe.generate_hash('', 6).upper()}"
        source_batch = f"{base_lot}0001"
        expected_child_batch = f"{base_lot}0002"
        pr = self._create_test_purchase_receipt(
            company=company,
            supplier="_Test Supplier",
            item_code=item_code,
            warehouse=wh_src,
            qty=1000.0,
            rate=20.0,
            posting_date="2025-01-10",
            delivery_note="IRS-PARTIAL-01",
        )

        self._create_batch(
            source_batch,
            item_code,
            supplier="_Test Supplier",
            manufacturing_date="2025-01-10",
            reference_doctype="Purchase Receipt",
            reference_name=pr.name,
        )
        self._receive_batch_stock(
            item_code, wh_src, source_batch, 1000.0, rate=20.0, company=company
        )

        pr_label = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "reference_doctype": "Purchase Receipt",
                "reference_name": pr.name,
                "item_code": item_code,
                "qty": 1000.0,
                "uom": "Nos",
                "batch": source_batch,
                "sut_barcode": source_batch,
                "target_warehouse": wh_src,
                "quality_ref": "QI-PARTIAL-01",
                "supplier_delivery_note": "IRS-PARTIAL-01",
            }
        )
        pr_label.flags.ignore_links = True
        pr_label.insert(ignore_permissions=True)

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            result = create_package_split_repack(
                item_code=item_code,
                source_warehouse=wh_src,
                target_warehouse=wh_dst,
                source_batch=source_batch,
                split_qtys=[350.0],
                remarks="Partial split test",
            )

        self.assertEqual(result["base_lot"], base_lot)
        self.assertEqual(
            result["created_batches"],
            [{"batch_no": expected_child_batch, "qty": 350.0}],
        )

        se = frappe.get_doc("Stock Entry", result["stock_entry"])
        self.assertEqual(se.docstatus, 1)
        self.assertEqual(se.stock_entry_type, "Package Split")
        self.assertEqual(se.purpose, "Repack")
        self.assertLess(abs(flt(se.value_difference)), 0.01)

        src_balances = get_batch_ledger_balances(item_code, source_batch)
        self.assertEqual(src_balances, [{"warehouse": wh_src, "qty": 650.0}])

        dst_balances = get_batch_ledger_balances(item_code, expected_child_batch)
        self.assertEqual(dst_balances, [{"warehouse": wh_dst, "qty": 350.0}])

        pr_label.reload()
        self.assertEqual(flt(pr_label.qty), 650.0)
        self.assertEqual(pr_label.reference_doctype, "Purchase Receipt")
        self.assertEqual(pr_label.reference_name, pr.name)

        child_batch = frappe.get_doc("Batch", expected_child_batch)
        self.assertEqual(child_batch.supplier, "_Test Supplier")
        self.assertEqual(str(child_batch.manufacturing_date), "2025-01-10")
        self.assertEqual(child_batch.reference_doctype, "Purchase Receipt")
        self.assertEqual(child_batch.reference_name, pr.name)

    def test_create_package_split_repack_legacy_and_ignore_reco_lock(self):
        """LEGACY batch split creates new 7-char lot + 0001/0002 boxes, preserves rate, deletes stale label, and honors ignore_reco_lock."""
        from erpnextkta.kta_stock.services.relabeling_service import (
            create_package_split_repack,
            get_batch_ledger_balances,
        )

        setup()
        item_code = self._ensure_batch_item()
        company, wh_src, wh_dst = self._ensure_test_warehouses()
        legacy_batch = "LEGACY-TEST-SPLIT-01"
        self._create_batch(legacy_batch, item_code, manufacturing_date="2024-06-15")
        self._receive_batch_stock(
            item_code, wh_src, legacy_batch, 100.0, rate=12.5, company=company
        )

        stale_label = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "reference_doctype": "Purchase Receipt",
                "reference_name": "MAT-PRE-LEG-001",
                "item_code": item_code,
                "qty": 100.0,
                "uom": "Nos",
                "batch": legacy_batch,
                "sut_barcode": legacy_batch,
                "target_warehouse": wh_src,
            }
        )
        stale_label.flags.ignore_links = True
        stale_label.insert(ignore_permissions=True)

        with (
            patch.object(stock_reconciliation_lock, "_can_bypass", return_value=False),
            patch.object(
                stock_reconciliation_lock,
                "_find_draft_reco_lock_by_set_warehouse",
                return_value=("SR-TEST-LOCK", wh_src),
            ),
            patch(
                "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
                return_value=MagicMock(),
            ),
        ):
            with self.assertRaises(frappe.ValidationError):
                create_package_split_repack(
                    item_code=item_code,
                    source_warehouse=wh_src,
                    target_warehouse=wh_dst,
                    source_batch=legacy_batch,
                    split_qtys=[60.0, 40.0],
                    ignore_reco_lock=False,
                )

            result = create_package_split_repack(
                item_code=item_code,
                source_warehouse=wh_src,
                target_warehouse=wh_dst,
                source_batch=legacy_batch,
                split_qtys=[60.0, 40.0],
                ignore_reco_lock=True,
            )

        self.assertFalse(getattr(frappe.flags, "kta_ignore_reco_lock", False))
        base_lot = result["base_lot"]
        self.assertRegex(base_lot, r"^[A-Z0-9]{7}$")
        self.assertEqual(
            result["created_batches"],
            [
                {"batch_no": f"{base_lot}0001", "qty": 60.0},
                {"batch_no": f"{base_lot}0002", "qty": 40.0},
            ],
        )

        se = frappe.get_doc("Stock Entry", result["stock_entry"])
        self.assertEqual(se.stock_entry_type, "Package Split")
        self.assertLess(abs(flt(se.value_difference)), 0.01)
        fg_rows = [row for row in se.items if row.is_finished_item]
        self.assertEqual(len(fg_rows), 2)
        for fg_row in fg_rows:
            self.assertAlmostEqual(flt(fg_row.basic_rate), 12.5, places=2)

        self.assertEqual(get_batch_ledger_balances(item_code, legacy_batch), [])
        self.assertFalse(frappe.db.exists("KTA Stock Label", stale_label.name))
