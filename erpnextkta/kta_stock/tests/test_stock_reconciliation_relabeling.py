from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import flt, nowdate, nowtime

from erpnextkta.kta_stock.services import stock_reconciliation_lock
from erpnextkta.kta_stock.services.relabeling_service import (
    get_batch_ledger_balances,
    is_standard_kta_box_batch,
)
from erpnextkta.kta_stock.setup import setup
from erpnextkta.tests.test_utils import KTABaseTestCase


class TestStockReconciliationRelabeling(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        setup()
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

    def _ensure_test_warehouses(self, suffix="base"):
        company = "_Test Company"
        parent_wh = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1}, "name"
        )
        group_name = f"_Test Reco Hub Grp {suffix} - _TC"
        if not frappe.db.exists("Warehouse", group_name):
            group_doc = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": f"_Test Reco Hub Grp {suffix}",
                    "company": company,
                    "parent_warehouse": parent_wh,
                    "is_group": 1,
                }
            ).insert(ignore_permissions=True)
            group_name = group_doc.name

        leaf_names = []
        for label in (f"_Test Reco Leaf A {suffix}", f"_Test Reco Leaf B {suffix}"):
            wh_name = f"{label} - _TC"
            if not frappe.db.exists("Warehouse", wh_name):
                wh_doc = frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": label,
                        "company": company,
                        "parent_warehouse": group_name,
                        "is_group": 0,
                    }
                ).insert(ignore_permissions=True)
                wh_name = wh_doc.name
            leaf_names.append(wh_name)

        return company, group_name, leaf_names[0], leaf_names[1]

    def _ensure_fractional_uom(self, uom_name="_Test Kg"):
        if not frappe.db.exists("UOM", uom_name):
            frappe.get_doc(
                {
                    "doctype": "UOM",
                    "uom_name": uom_name,
                    "must_be_whole_number": 0,
                    "enabled": 1,
                }
            ).insert(ignore_permissions=True)
        return uom_name

    def _ensure_batch_item(self, item_code="_TEST-SR-RELABEL-ITEM"):
        uom = self._ensure_fractional_uom()
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
                    "stock_uom": uom,
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                }
            ).insert(ignore_permissions=True)
        return item_code

    def _ensure_batch(self, batch_id, item_code, **kwargs):
        if frappe.db.exists("Batch", batch_id):
            return frappe.get_doc("Batch", batch_id)
        payload = {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
            "batch_qty": 0,
        }
        payload.update(kwargs)
        doc = frappe.get_doc(payload)
        doc.flags.ignore_links = True
        doc.insert(ignore_permissions=True)
        return doc

    def _receive_stock(
        self, item_code, warehouse, batch_no, qty, rate=15.0, company="_Test Company"
    ):
        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": company,
                "posting_date": nowdate(),
                "posting_time": nowtime(),
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

    def _create_pr_label(
        self, item_code, batch_no, qty, warehouse, pr_name="MAT-PRE-SR-TEST"
    ):
        lbl = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": "Depo Giriş Etiketi",
                "reference_doctype": "Purchase Receipt",
                "reference_name": pr_name,
                "item_code": item_code,
                "qty": flt(qty),
                "uom": self._ensure_fractional_uom(),
                "batch": batch_no,
                "sut_barcode": batch_no,
                "target_warehouse": warehouse,
                "quality_ref": "QI-SR-TEST",
                "supplier_delivery_note": "IRS-SR-01",
                "gr_posting_date": nowdate(),
            }
        )
        lbl.flags.ignore_links = True
        lbl.insert(ignore_permissions=True)
        return lbl

    def test_list_and_preview_reads_submitted_v15_bundle(self):
        """Submitted Stock Reconciliation with row.batch_no=None reads inward SABE entries and computes exact preview statuses."""
        from erpnextkta.kta_stock.services.stock_reconciliation_service import (
            get_stock_reconciliation_label_preview,
            list_stock_reconciliations,
        )

        company, _, wh_a, wh_b = self._ensure_test_warehouses("prv")
        item_code = self._ensure_batch_item("_TEST-SR-PREVIEW-ITEM")
        lot_prefix = f"P{frappe.generate_hash('', 6).upper()}"
        std_changed_batch = f"{lot_prefix}0001"
        std_valid_batch = f"{lot_prefix}0002"
        legacy_batch = f"LEGACY-PRV-{frappe.generate_hash('', 5).upper()}"

        self._ensure_batch(std_changed_batch, item_code)
        self._ensure_batch(std_valid_batch, item_code)
        self._ensure_batch(legacy_batch, item_code)

        self._receive_stock(
            item_code, wh_a, std_changed_batch, 40.0, rate=10.0, company=company
        )
        self._receive_stock(
            item_code, wh_a, std_valid_batch, 10.0, rate=10.0, company=company
        )
        self._receive_stock(
            item_code, wh_a, legacy_batch, 20.0, rate=10.0, company=company
        )

        # Existing labels: changed batch had 40 on PR label (now counted 30), valid batch matches 10
        self._create_pr_label(item_code, std_changed_batch, 40.0, wh_a)
        self._create_pr_label(item_code, std_valid_batch, 10.0, wh_a)

        bundle = frappe.get_doc(
            {
                "doctype": "Serial and Batch Bundle",
                "item_code": item_code,
                "warehouse": wh_a,
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "voucher_type": "Stock Reconciliation",
                "type_of_transaction": "Inward",
                "company": company,
                "entries": [
                    {
                        "batch_no": std_changed_batch,
                        "qty": 30.0,
                        "warehouse": wh_a,
                        "incoming_rate": 10.0,
                        "is_outward": 0,
                    },
                    {
                        "batch_no": legacy_batch,
                        "qty": 20.0,
                        "warehouse": wh_a,
                        "incoming_rate": 10.0,
                        "is_outward": 0,
                    },
                ],
            }
        ).insert(ignore_permissions=True)

        sr = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "set_warehouse": wh_a,
                "items": [
                    {
                        "item_code": item_code,
                        "warehouse": wh_a,
                        "qty": 50.0,
                        "valuation_rate": 10.0,
                        "use_serial_batch_fields": 0,
                        "serial_and_batch_bundle": bundle.name,
                    }
                ],
            }
        )
        sr.insert(ignore_permissions=True)
        sr.submit()

        # Also create a Submitted Stock Reconciliation for std_valid_batch in wh_b
        self._receive_stock(
            item_code, wh_b, std_valid_batch, 10.0, rate=10.0, company=company
        )
        sr_valid = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "set_warehouse": wh_b,
                "items": [
                    {
                        "item_code": item_code,
                        "warehouse": wh_b,
                        "batch_no": std_valid_batch,
                        "qty": 10.0,
                        "current_qty": 10.0,
                        "valuation_rate": 10.0,
                        "current_valuation_rate": 10.0,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        sr_valid.submit()

        listed = list_stock_reconciliations(
            status_filter="submitted", warehouse=wh_a, search=sr.name
        )
        self.assertEqual([r["name"] for r in listed], [sr.name])
        self.assertEqual(listed[0]["item_count"], 1)

        preview = get_stock_reconciliation_label_preview(sr.name)
        self.assertEqual(preview["doc"]["name"], sr.name)
        self.assertEqual(preview["doc"]["docstatus"], 1)
        by_batch = {r["batch_no"]: r for r in preview["rows"]}
        self.assertEqual(set(by_batch.keys()), {std_changed_batch, legacy_batch})

        self.assertEqual(by_batch[std_changed_batch]["status"], "qty_changed")
        self.assertEqual(flt(by_batch[std_changed_batch]["qty"]), 30.0)
        self.assertEqual(flt(by_batch[std_changed_batch]["label_qty"]), 40.0)
        self.assertTrue(by_batch[std_changed_batch]["suggested_mode1_selected"])

        self.assertEqual(by_batch[legacy_batch]["status"], "legacy_batch")
        self.assertTrue(by_batch[legacy_batch]["is_legacy"])
        self.assertTrue(by_batch[legacy_batch]["suggested_mode1_selected"])

        self.assertEqual(preview["summary"]["total_positive"], 2)
        self.assertEqual(preview["summary"]["qty_changed"], 1)
        self.assertEqual(preview["summary"]["legacy_batch"], 1)

        valid_preview = get_stock_reconciliation_label_preview(sr_valid.name)
        self.assertEqual(len(valid_preview["rows"]), 1)
        valid_row = valid_preview["rows"][0]
        self.assertEqual(valid_row["status"], "valid")
        self.assertFalse(valid_row["suggested_mode1_selected"])

    def test_draft_submit_and_print_converts_legacy_without_doubling_stock(self):
        """Draft Stock Reconciliation converts LEGACY batch into 2 boxes, zeroes LEGACY ledger qty, cleans old label, and prints."""
        from erpnextkta.kta_stock.services.stock_reconciliation_service import (
            submit_and_print_stock_reconciliation,
        )

        company, _, wh_a, _ = self._ensure_test_warehouses("leg")
        item_code = self._ensure_batch_item("_TEST-SR-DRAFT-LEG-ITEM")
        legacy_batch = f"LEGACY-DRF-{frappe.generate_hash('', 5).upper()}"
        self._ensure_batch(legacy_batch, item_code, manufacturing_date="2024-08-01")
        self._receive_stock(
            item_code, wh_a, legacy_batch, 77.5, rate=18.0, company=company
        )
        stale_lbl = self._create_pr_label(item_code, legacy_batch, 77.5, wh_a)

        sr = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "set_warehouse": wh_a,
                "items": [
                    {
                        "item_code": item_code,
                        "warehouse": wh_a,
                        "batch_no": legacy_batch,
                        "qty": 77.5,
                        "current_qty": 77.5,
                        "valuation_rate": 18.0,
                        "current_valuation_rate": 18.0,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        ).insert(ignore_permissions=True)

        row_name = sr.items[0].name
        with (
            patch(
                "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
                return_value=MagicMock(),
            ),
            patch(
                "erpnextkta.kta_stock.services.stock_reconciliation_service.enqueue_print_labels_by_names",
                wraps=__import__(
                    "erpnextkta.kta_stock.label_manager",
                    fromlist=["enqueue_print_labels_by_names"],
                ).enqueue_print_labels_by_names,
            ) as mock_enqueue,
        ):
            res = submit_and_print_stock_reconciliation(
                stock_reconciliation=sr.name,
                selected_items=[
                    {
                        "row_name": row_name,
                        "batch_no": legacy_batch,
                        "qty": 77.5,
                        "convert_legacy": 1,
                        "box_splits": [50.0, 27.5],
                    }
                ],
                print_labels=1,
            )

        sr.reload()
        self.assertEqual(sr.docstatus, 1)
        self.assertEqual(res["stock_reconciliation"], sr.name)
        self.assertEqual(res["docstatus"], 1)
        self.assertEqual(len(res["labels"]), 2)
        mock_enqueue.assert_called_once()

        # Critical check: LEGACY balance must be 0 (not doubled to 155!)
        self.assertEqual(get_batch_ledger_balances(item_code, legacy_batch), [])
        self.assertFalse(frappe.db.exists("KTA Stock Label", stale_lbl.name))

        created_labels = frappe.get_all(
            "KTA Stock Label",
            filters={"name": ["in", res["labels"]]},
            fields=["name", "batch", "sut_barcode", "qty"],
        )
        self.assertEqual(len(created_labels), 2)
        qtys_by_batch = {l.batch: flt(l.qty) for l in created_labels}
        self.assertEqual(sorted(qtys_by_batch.values()), [27.5, 50.0])
        for b_no, b_qty in qtys_by_batch.items():
            self.assertTrue(is_standard_kta_box_batch(b_no))
            self.assertEqual(
                get_batch_ledger_balances(item_code, b_no),
                [{"warehouse": wh_a, "qty": b_qty}],
            )
            batch_doc = frappe.get_doc("Batch", b_no)
            self.assertEqual(str(batch_doc.manufacturing_date), "2024-08-01")

    def test_draft_split_standard_box_mints_sibling_and_preserves_rate(self):
        """Draft split of standard 7+4 box (77.5 -> [50.0, 27.5]) keeps 50.0 on 0001 and mints 0002 with 27.5."""
        from erpnextkta.kta_stock.services.stock_reconciliation_service import (
            submit_and_print_stock_reconciliation,
        )

        company, _, wh_a, _ = self._ensure_test_warehouses("std")
        item_code = self._ensure_batch_item("_TEST-SR-DRAFT-STD-ITEM")
        base_lot = f"S{frappe.generate_hash('', 6).upper()}"
        box_1 = f"{base_lot}0001"
        box_2 = f"{base_lot}0002"
        self._ensure_batch(box_1, item_code, manufacturing_date="2025-02-15")
        self._receive_stock(item_code, wh_a, box_1, 77.5, rate=22.0, company=company)
        pr_lbl = self._create_pr_label(item_code, box_1, 77.5, wh_a)

        sr = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "set_warehouse": wh_a,
                "items": [
                    {
                        "item_code": item_code,
                        "warehouse": wh_a,
                        "batch_no": box_1,
                        "qty": 77.5,
                        "current_qty": 77.5,
                        "valuation_rate": 22.0,
                        "current_valuation_rate": 22.0,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        ).insert(ignore_permissions=True)

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            res = submit_and_print_stock_reconciliation(
                stock_reconciliation=sr.name,
                selected_items=[
                    {
                        "row_name": sr.items[0].name,
                        "batch_no": box_1,
                        "qty": 77.5,
                        "box_splits": [50.0, 27.5],
                    }
                ],
                print_labels=1,
            )

        sr.reload()
        self.assertEqual(sr.docstatus, 1)
        self.assertEqual(
            get_batch_ledger_balances(item_code, box_1),
            [{"warehouse": wh_a, "qty": 50.0}],
        )
        self.assertEqual(
            get_batch_ledger_balances(item_code, box_2),
            [{"warehouse": wh_a, "qty": 27.5}],
        )
        pr_lbl.reload()
        self.assertEqual(flt(pr_lbl.qty), 50.0)
        self.assertEqual(pr_lbl.reference_doctype, "Purchase Receipt")
        self.assertEqual(len(res["labels"]), 2)

        for row in sr.items:
            if row.qty > 0:
                self.assertAlmostEqual(flt(row.valuation_rate), 22.0, places=2)

    def test_draft_box_splits_mismatch_fails_atomically(self):
        """Mismatched box_splits sum fails with ValidationError, leaving docstatus=0 and 0 labels/batches created."""
        from erpnextkta.kta_stock.services.stock_reconciliation_service import (
            submit_and_print_stock_reconciliation,
        )

        company, _, wh_a, _ = self._ensure_test_warehouses("mis")
        item_code = self._ensure_batch_item("_TEST-SR-MISMATCH-ITEM")
        legacy_batch = f"LEGACY-MIS-{frappe.generate_hash('', 5).upper()}"
        self._ensure_batch(legacy_batch, item_code)
        self._receive_stock(
            item_code, wh_a, legacy_batch, 77.5, rate=10.0, company=company
        )

        sr = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "set_warehouse": wh_a,
                "items": [
                    {
                        "item_code": item_code,
                        "warehouse": wh_a,
                        "batch_no": legacy_batch,
                        "qty": 77.5,
                        "current_qty": 77.5,
                        "valuation_rate": 10.0,
                        "current_valuation_rate": 10.0,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        ).insert(ignore_permissions=True)

        labels_before = frappe.db.count("KTA Stock Label", {"item_code": item_code})
        batches_before = frappe.db.count("Batch", {"item": item_code})

        with self.assertRaises(frappe.ValidationError):
            submit_and_print_stock_reconciliation(
                stock_reconciliation=sr.name,
                selected_items=[
                    {
                        "row_name": sr.items[0].name,
                        "batch_no": legacy_batch,
                        "qty": 77.5,
                        "convert_legacy": 1,
                        "box_splits": [50.0, 20.0],
                    }
                ],
                print_labels=1,
            )

        sr.reload()
        self.assertEqual(sr.docstatus, 0)
        self.assertEqual(
            frappe.db.count("KTA Stock Label", {"item_code": item_code}), labels_before
        )
        self.assertEqual(frappe.db.count("Batch", {"item": item_code}), batches_before)

    def test_relabel_submitted_direct_and_split_with_lock_bypass(self):
        """Submitted SR updates single box label without Stock Entry; split/LEGACY creates Package Split even under Draft parent lock."""
        from erpnextkta.kta_stock.services.stock_reconciliation_service import (
            relabel_submitted_stock_reconciliation,
        )

        company, group_wh, wh_a, wh_b = self._ensure_test_warehouses("sub")
        item_code = self._ensure_batch_item("_TEST-SR-SUBMITTED-ITEM")
        base_lot = f"R{frappe.generate_hash('', 6).upper()}"
        std_box = f"{base_lot}0001"
        legacy_batch = f"LEGACY-SUB-{frappe.generate_hash('', 5).upper()}"

        self._ensure_batch(std_box, item_code)
        self._ensure_batch(legacy_batch, item_code)
        self._receive_stock(item_code, wh_a, std_box, 100.0, rate=15.0, company=company)
        self._receive_stock(
            item_code, wh_a, legacy_batch, 60.0, rate=15.0, company=company
        )

        sr = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "set_warehouse": wh_a,
                "items": [
                    {
                        "item_code": item_code,
                        "warehouse": wh_a,
                        "batch_no": std_box,
                        "qty": 100.0,
                        "current_qty": 100.0,
                        "valuation_rate": 15.0,
                        "current_valuation_rate": 15.0,
                        "use_serial_batch_fields": 1,
                    },
                    {
                        "item_code": item_code,
                        "warehouse": wh_a,
                        "batch_no": legacy_batch,
                        "qty": 60.0,
                        "current_qty": 60.0,
                        "valuation_rate": 15.0,
                        "current_valuation_rate": 15.0,
                        "use_serial_batch_fields": 1,
                    },
                ],
            }
        ).insert(ignore_permissions=True)
        sr.submit()

        # 1) Direct single standard box relabel -> NO Stock Entry created
        se_count_before = frappe.db.count("Stock Entry")
        with (
            patch(
                "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
                return_value=MagicMock(),
            ),
            patch(
                "erpnextkta.kta_stock.services.stock_reconciliation_service.enqueue_print_labels_by_names",
                wraps=__import__(
                    "erpnextkta.kta_stock.label_manager",
                    fromlist=["enqueue_print_labels_by_names"],
                ).enqueue_print_labels_by_names,
            ) as mock_enqueue,
        ):
            direct_res = relabel_submitted_stock_reconciliation(
                stock_reconciliation=sr.name,
                selected_items=[
                    {
                        "row_name": sr.items[0].name,
                        "batch_no": std_box,
                        "qty": 100.0,
                    }
                ],
                print_labels=1,
            )

        self.assertEqual(direct_res["stock_entries"], [])
        self.assertEqual(len(direct_res["labels"]), 1)
        self.assertEqual(frappe.db.count("Stock Entry"), se_count_before)
        mock_enqueue.assert_called_once_with(direct_res["labels"])

        # 2) Draft Stock Reconciliation lock on parent group warehouse -> Package Split succeeds for Manager
        draft_lock_sr = frappe.get_doc(
            {
                "doctype": "Stock Reconciliation",
                "company": company,
                "purpose": "Stock Reconciliation",
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "set_warehouse": group_wh,
                "items": [
                    {
                        "item_code": item_code,
                        "warehouse": wh_b,
                        "batch_no": std_box,
                        "qty": 1.0,
                        "valuation_rate": 15.0,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        self.assertEqual(draft_lock_sr.docstatus, 0)

        with (
            patch.object(stock_reconciliation_lock, "_can_bypass", return_value=False),
            patch(
                "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
                return_value=MagicMock(),
            ),
            patch(
                "erpnextkta.kta_stock.services.stock_reconciliation_service.enqueue_print_labels_by_names",
                wraps=__import__(
                    "erpnextkta.kta_stock.label_manager",
                    fromlist=["enqueue_print_labels_by_names"],
                ).enqueue_print_labels_by_names,
            ) as mock_enqueue_split,
        ):
            split_res = relabel_submitted_stock_reconciliation(
                stock_reconciliation=sr.name,
                selected_items=[
                    {
                        "row_name": sr.items[1].name,
                        "batch_no": legacy_batch,
                        "qty": 60.0,
                        "convert_legacy": 1,
                        "box_splits": [35.0, 25.0],
                    }
                ],
                print_labels=1,
            )

        self.assertEqual(len(split_res["stock_entries"]), 1)
        se_doc = frappe.get_doc("Stock Entry", split_res["stock_entries"][0])
        self.assertEqual(se_doc.docstatus, 1)
        self.assertEqual(se_doc.stock_entry_type, "Package Split")
        self.assertEqual(len(split_res["labels"]), 2)
        mock_enqueue_split.assert_called_once_with(split_res["labels"])
        self.assertEqual(get_batch_ledger_balances(item_code, legacy_batch), [])
