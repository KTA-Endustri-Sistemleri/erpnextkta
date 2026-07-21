# Copyright (c) 2026, Framras AS and Contributors
# See license.txt

import frappe
from erpnextkta.tests.test_utils import KTATestCase, clear_item_stock_and_batches, setup_test_fiscal_years

class TestKTAPurchaseReceiptGKK(KTATestCase):
    def setUp(self):
        super().setUp()
        # Temporarily disable PO requirement for ease of creating direct PRs in tests
        self.po_req_setting = frappe.db.get_single_value("Buying Settings", "po_required")
        frappe.db.set_single_value("Buying Settings", "po_required", "No")

        # Temporarily enable making quality inspection after purchase/delivery in Stock Settings
        self.allow_qi_after_delivery = frappe.db.get_single_value("Stock Settings", "allow_to_make_quality_inspection_after_purchase_or_delivery")
        frappe.db.set_single_value("Stock Settings", "allow_to_make_quality_inspection_after_purchase_or_delivery", 1)

        # Link _Test Company KTA to all global fiscal years so that it passes Fiscal Year validations
        setup_test_fiscal_years(self.company)

        # Reset item and custom fields to prevent test pollution
        # Clean up existing test records to avoid database pollution and incorrect FIFO batch selection
        clear_item_stock_and_batches(self.item)

        frappe.db.set_value("Item", self.item, {
            "inspection_required_before_purchase": 1,
            "has_batch_no": 0,
            "custom_atlama_sayisi": 0,
            "custom_atlama_sirasi": 0
        })
        
        # Ensure a test Quality Inspection Template exists
        self.qi_template = "Test GKK Template"
        if not frappe.db.exists("Quality Inspection Template", self.qi_template):
            frappe.get_doc({
                "doctype": "Quality Inspection Template",
                "quality_inspection_template_name": self.qi_template,
                "item_quality_inspection_parameter": [
                    {"specification": "Görsel Kontrol", "numeric": 0, "value": "OK"}
                ]
            }).insert(ignore_permissions=True)
            
        frappe.db.set_value("Item", self.item, "quality_inspection_template", self.qi_template)
        frappe.db.commit()

    def tearDown(self):
        if hasattr(self, "po_req_setting") and self.po_req_setting is not None:
            frappe.db.set_single_value("Buying Settings", "po_required", self.po_req_setting)
        if hasattr(self, "allow_qi_after_delivery") and self.allow_qi_after_delivery is not None:
            frappe.db.set_single_value("Stock Settings", "allow_to_make_quality_inspection_after_purchase_or_delivery", self.allow_qi_after_delivery)
        super().tearDown()

    def create_test_purchase_receipt(self, qty=5):
        supplier = "_Test Supplier"
        if not frappe.db.exists("Supplier", supplier):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": supplier,
                "supplier_group": "All Supplier Groups",
                "supplier_type": "Company"
            }).insert(ignore_permissions=True)
            
        default_currency = frappe.db.get_value("Company", self.company, "default_currency") or "TRY"
        buying_price_list = frappe.db.get_value("Price List", {"buying": 1}, "name") or "Standard Buying"

        # Resolve an active fiscal year date to prevent FiscalYearError
        fy_list = frappe.get_all("Fiscal Year", fields=["year_start_date", "year_end_date"])
        posting_date = fy_list[0].year_start_date if fy_list else frappe.utils.nowdate()

        pr = frappe.new_doc("Purchase Receipt")
        pr.company = self.company
        pr.supplier = supplier
        pr.posting_date = posting_date
        pr.posting_time = frappe.utils.nowtime()
        pr.set_posting_time = 1 # Force ERPNext to respect our manual posting date
        pr.currency = default_currency
        pr.conversion_rate = 1.0
        pr.buying_price_list = buying_price_list
        pr.price_list_currency = default_currency
        pr.plc_conversion_rate = 1.0
        
        # Custom mandatory fields for KTA setup
        pr.irsaliye_tarihi = posting_date
        pr.irsaliye_no = "TEST-WAYBILL-123"
        
        cost_center = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0}, "name")
        
        pr.append("items", {
            "item_code": self.item,
            "qty": qty,
            "rate": 100.0,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "warehouse": self.wip_warehouse,
            "cost_center": cost_center,
            "quality_inspection_template": self.qi_template
        })
        
        pr.calculate_taxes_and_totals()
        return pr

    def test_purchase_receipt_gkk_status_flow(self):
        """Purchase Receipt submitted with inspection-required item should set status to 'GKK Bekliyor'
        and update correctly when Quality Inspection is updated, submitted, or deleted."""
        
        # 1. Create and submit Purchase Receipt
        pr = self.create_test_purchase_receipt()
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        # Reload to get updated status
        pr.reload()
        self.assertEqual(pr.status, "GKK Bekliyor", "PR status should be set to 'GKK Bekliyor' upon submission")
        
        # Verify that Quality Inspection was created in Draft status (docstatus = 0)
        qi_name = frappe.db.get_value("Quality Inspection", {
            "reference_type": "Purchase Receipt",
            "reference_name": pr.name
        }, "name")
        
        self.assertTrue(qi_name, "Quality Inspection should be automatically created")
        self.assertEqual(frappe.db.get_value("Quality Inspection", qi_name, "docstatus"), 0, "QI should start in Draft status")
        
        # 2. Submit the Quality Inspection
        qi_doc = frappe.get_doc("Quality Inspection", qi_name)
        # Complete readings for submission
        for reading in qi_doc.readings:
            reading.reading_value = "OK"
            reading.status = "Accepted"
        qi_doc.submit()
        
        # Verify PR status is updated (no longer 'GKK Bekliyor')
        pr.reload()
        self.assertNotEqual(pr.status, "GKK Bekliyor", "PR status should clear 'GKK Bekliyor' once QI is submitted")

    def test_purchase_receipt_gkk_deletion_flow(self):
        """Deleting a draft Quality Inspection should revert Purchase Receipt status from 'GKK Bekliyor'."""
        
        # 1. Create and submit Purchase Receipt
        pr = self.create_test_purchase_receipt()
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        pr.reload()
        self.assertEqual(pr.status, "GKK Bekliyor")
        
        # Get the automatically created Quality Inspection
        qi_name = frappe.db.get_value("Quality Inspection", {
            "reference_type": "Purchase Receipt",
            "reference_name": pr.name
        }, "name")
        self.assertTrue(qi_name)
        
        # 2. Delete the draft Quality Inspection
        frappe.delete_doc("Quality Inspection", qi_name)
        
        # Verify PR status reverted from 'GKK Bekliyor'
        pr.reload()
        self.assertNotEqual(pr.status, "GKK Bekliyor", "PR status should clear 'GKK Bekliyor' after QI deletion")

    def test_purchase_receipt_gkk_skip_logic(self):
        """If Item has custom_atlama_sayisi set, Quality Inspection should only be created
        every Nth receipt according to the skip sequence, and status should only be 'GKK Bekliyor' when QI is created."""
        
        # Configure item to require quality inspection and set custom_atlama_sayisi = 3
        meta = frappe.get_meta("Item")
        if not meta.has_field("custom_atlama_sayisi"):
            # If the database doesn't have these custom fields, skip this test
            return

        frappe.db.set_value("Item", self.item, "custom_atlama_sayisi", 3)
        frappe.db.set_value("Item", self.item, "custom_atlama_sirasi", 0)
        frappe.db.commit()

        # --- Receipt 1 (atlama_sirasi = 0) -> Should create QI -> Status 'GKK Bekliyor'
        pr1 = self.create_test_purchase_receipt()
        pr1.insert(ignore_permissions=True)
        pr1.submit()
        pr1.reload()
        
        qi1 = frappe.db.get_value("Quality Inspection", {"reference_type": "Purchase Receipt", "reference_name": pr1.name}, "name")
        self.assertTrue(qi1, "QI should be created on first receipt (sequence 0)")
        self.assertEqual(pr1.status, "GKK Bekliyor")
        self.assertEqual(frappe.db.get_value("Item", self.item, "custom_atlama_sirasi"), 1)

        # --- Receipt 2 (atlama_sirasi = 1) -> Should SKIP QI -> Status not 'GKK Bekliyor'
        pr2 = self.create_test_purchase_receipt()
        pr2.insert(ignore_permissions=True)
        pr2.submit()
        pr2.reload()
        
        qi2 = frappe.db.get_value("Quality Inspection", {"reference_type": "Purchase Receipt", "reference_name": pr2.name}, "name")
        self.assertFalse(qi2, "QI should be skipped on second receipt (sequence 1)")
        self.assertNotEqual(pr2.status, "GKK Bekliyor")
        self.assertEqual(frappe.db.get_value("Item", self.item, "custom_atlama_sirasi"), 2)

        # --- Receipt 3 (atlama_sirasi = 2) -> Should SKIP QI -> Status not 'GKK Bekliyor'
        pr3 = self.create_test_purchase_receipt()
        pr3.insert(ignore_permissions=True)
        pr3.submit()
        pr3.reload()
        
        qi3 = frappe.db.get_value("Quality Inspection", {"reference_type": "Purchase Receipt", "reference_name": pr3.name}, "name")
        self.assertFalse(qi3, "QI should be skipped on third receipt (sequence 2)")
        self.assertNotEqual(pr3.status, "GKK Bekliyor")
        self.assertEqual(frappe.db.get_value("Item", self.item, "custom_atlama_sirasi"), 3)

        # --- Receipt 4 (atlama_sirasi = 3) -> Should create QI -> Status 'GKK Bekliyor'
        pr4 = self.create_test_purchase_receipt()
        pr4.insert(ignore_permissions=True)
        pr4.submit()
        pr4.reload()
        
        qi4 = frappe.db.get_value("Quality Inspection", {"reference_type": "Purchase Receipt", "reference_name": pr4.name}, "name")
        self.assertTrue(qi4, "QI should be created on fourth receipt (sequence 3)")
        self.assertEqual(pr4.status, "GKK Bekliyor")
        self.assertEqual(frappe.db.get_value("Item", self.item, "custom_atlama_sirasi"), 4)

        # --- Test cancellation of pr4 -> should decrement custom_atlama_sirasi back to 3
        pr4.cancel()
        self.assertEqual(frappe.db.get_value("Item", self.item, "custom_atlama_sirasi"), 3)

    def test_purchase_receipt_gkk_transfer_blocking(self):
        """A batch created by a Purchase Receipt cannot be transferred via Stock Entry
        until its Quality Inspection is submitted and Accepted."""
        
        # Enable batch tracking on the item for this test
        frappe.db.set_value("Item", self.item, "has_batch_no", 1)
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # 1. Create and submit Purchase Receipt
        pr = self.create_test_purchase_receipt()
        for item in pr.items:
            item.custom_split_qty = 5
            item.custom_do_not_split = 0
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        # Get the automatically created batch and Quality Inspection
        qi_name = frappe.db.get_value("Quality Inspection", {
            "reference_type": "Purchase Receipt",
            "reference_name": pr.name
        }, "name")
        self.assertTrue(qi_name)
        
        # We need the batch number generated for the item
        base_batch_no = pr.items[0].batch_no
        self.assertTrue(base_batch_no, "Batch should be automatically generated")
        batch_no = f"{base_batch_no}0001"
        
        # Create target warehouse
        to_warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "name": ["!=", self.wip_warehouse], "is_rejected_warehouse": ["!=", 1], "is_group": 0}, "name")
        if not to_warehouse:
            to_wh_doc = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": "_Test Target",
                "company": self.company
            }).insert(ignore_permissions=True)
            to_warehouse = to_wh_doc.name

        # 2. Try to transfer the batch before GKK approval
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Transfer"
        se.stock_entry_type = "Material Transfer"
        se.company = self.company
        se.posting_date = pr.posting_date
        se.posting_time = frappe.utils.nowtime()
        se.from_warehouse = self.wip_warehouse
        se.to_warehouse = to_warehouse
        
        cost_center = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0}, "name")
        
        se.append("items", {
            "item_code": self.item,
            "qty": 2,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "s_warehouse": self.wip_warehouse,
            "t_warehouse": to_warehouse,
            "batch_no": batch_no,
            "cost_center": cost_center
        })
        se.insert(ignore_permissions=True)
        
        # Submitting the Stock Entry should fail because QI is not submitted/accepted
        with self.assertRaises(frappe.ValidationError) as exc:
            se.submit()
            
        self.assertIn("henüz Kalite Kontrol (GKK) onayı almadığı", str(exc.exception), 
                      "Should block transfer with quality inspection warning")
                      
        # 3. Approve and submit the Quality Inspection
        qi_doc = frappe.get_doc("Quality Inspection", qi_name)
        for reading in qi_doc.readings:
            reading.reading_value = "OK"
            reading.status = "Accepted"
        qi_doc.submit()
        
        # 4. Try submitting the Stock Entry again - it should succeed now
        se.reload()
        se.submit()
        self.assertEqual(se.docstatus, 1, "Stock Entry should submit successfully after GKK approval")

    def test_purchase_receipt_batch_splitting(self):
        """When a Purchase Receipt is submitted, batch-tracked items with a set custom_split_qty
        should have their batch split into multiple smaller batches (boxes) and labels created."""
        
        # Configure item to require quality inspection and enable batch tracking
        frappe.db.set_value("Item", self.item, "inspection_required_before_purchase", 1)
        frappe.db.set_value("Item", self.item, "has_batch_no", 1)
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # Create Purchase Receipt with split quantity set to 2
        pr = self.create_test_purchase_receipt(qty=5)
        for item in pr.items:
            item.custom_split_qty = 2
            item.custom_do_not_split = 0

        pr.insert(ignore_permissions=True)
        pr.submit()
        
        # Reload to get the generated batch info
        pr.reload()
        
        # Verify that multiple split batches were created
        labels = frappe.get_all("KTA Stock Label", filters={
            "reference_doctype": "Purchase Receipt",
            "reference_name": pr.name,
            "label_type": "Depo Giriş Etiketi"
        }, fields=["batch", "qty"])
        
        # With qty=5 and split_qty=2, we expect:
        # - Box 1: qty=2
        # - Box 2: qty=2
        # - Box 3: qty=1
        # Total 3 boxes/labels!
        self.assertEqual(len(labels), 3, "Should generate exactly 3 split batches/labels")
        
        qtys = sorted([float(l.qty) for l in labels])
        self.assertEqual(qtys, [1.0, 2.0, 2.0], "Split quantities should be exactly [1.0, 2.0, 2.0]")

    def test_purchase_receipt_do_not_split(self):
        """When a Purchase Receipt is submitted, if custom_do_not_split is checked,
        the batch should NOT be split into smaller batches/labels, even if custom_split_qty is set."""
        
        # Configure item to require quality inspection and enable batch tracking
        frappe.db.set_value("Item", self.item, "inspection_required_before_purchase", 1)
        frappe.db.set_value("Item", self.item, "has_batch_no", 1)
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # Create Purchase Receipt with split quantity set to 2, but do_not_split = 1
        pr = self.create_test_purchase_receipt(qty=5)
        for item in pr.items:
            item.custom_split_qty = 2
            item.custom_do_not_split = 1

        pr.insert(ignore_permissions=True)
        pr.submit()
        
        pr.reload()
        
        # Verify that only 1 batch label was created with full quantity
        labels = frappe.get_all("KTA Stock Label", filters={
            "reference_doctype": "Purchase Receipt",
            "reference_name": pr.name,
            "label_type": "Depo Giriş Etiketi"
        }, fields=["batch", "qty"])
        
        self.assertEqual(len(labels), 1, "Should generate exactly 1 label when do_not_split is checked")
        self.assertEqual(float(labels[0].qty), 5.0, "The label quantity should be the full receipt quantity")

    def test_purchase_receipt_do_not_split_with_zero_split_qty(self):
        """When a Purchase Receipt is submitted, if custom_do_not_split is checked,
        the batch should NOT be split into smaller batches/labels, even if custom_split_qty is 0."""
        
        # Configure item to require quality inspection and enable batch tracking
        frappe.db.set_value("Item", self.item, "inspection_required_before_purchase", 1)
        frappe.db.set_value("Item", self.item, "has_batch_no", 1)
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # Create Purchase Receipt with split quantity set to 0, and do_not_split = 1
        pr = self.create_test_purchase_receipt(qty=5)
        for item in pr.items:
            item.custom_split_qty = 0
            item.custom_do_not_split = 1

        pr.insert(ignore_permissions=True)
        pr.submit()
        
        pr.reload()
        
        # Verify that only 1 batch label was created with full quantity
        labels = frappe.get_all("KTA Stock Label", filters={
            "reference_doctype": "Purchase Receipt",
            "reference_name": pr.name,
            "label_type": "Depo Giriş Etiketi"
        }, fields=["batch", "qty"])
        
        self.assertEqual(len(labels), 1, "Should generate exactly 1 label when do_not_split is checked")
        self.assertEqual(float(labels[0].qty), 5.0, "The label quantity should be the full receipt quantity")

    def test_purchase_receipt_gkk_transfer_skipped_allowed(self):
        """If a Purchase Receipt is skipped under the skip logic (no Quality Inspection is generated),
        the batch should be allowed to be transferred without any blocking."""
        
        # Enable batch tracking and skip logic on the item (skip count = 3, start sequence = 1)
        # Sequence 1 is skipped (QI is only generated at sequence 0, 3, 6, etc.)
        frappe.db.set_value("Item", self.item, {
            "inspection_required_before_purchase": 1,
            "has_batch_no": 1,
            "custom_atlama_sayisi": 3,
            "custom_atlama_sirasi": 1
        })
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # 1. Create and submit Purchase Receipt
        pr = self.create_test_purchase_receipt()
        for item in pr.items:
            item.custom_split_qty = 5
            item.custom_do_not_split = 0
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        # Verify that no Quality Inspection was created (since it's skipped at sequence 1)
        qi_name = frappe.db.get_value("Quality Inspection", {
            "reference_type": "Purchase Receipt",
            "reference_name": pr.name
        }, "name")
        self.assertFalse(qi_name, "No Quality Inspection should be created for a skipped receipt")
        
        base_batch_no = pr.items[0].batch_no
        batch_no = f"{base_batch_no}0001"
        
        to_warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "name": ["!=", self.wip_warehouse], "is_rejected_warehouse": ["!=", 1], "is_group": 0}, "name")
        
        # 2. Try to transfer the batch - it should be allowed because it's skipped
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Transfer"
        se.stock_entry_type = "Material Transfer"
        se.company = self.company
        se.posting_date = pr.posting_date
        se.posting_time = frappe.utils.nowtime()
        se.from_warehouse = self.wip_warehouse
        se.to_warehouse = to_warehouse
        
        cost_center = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0}, "name")
        
        se.append("items", {
            "item_code": self.item,
            "qty": 2,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "s_warehouse": self.wip_warehouse,
            "t_warehouse": to_warehouse,
            "batch_no": batch_no,
            "cost_center": cost_center
        })
        se.insert(ignore_permissions=True)
        se.submit()
        
        self.assertEqual(se.docstatus, 1, "Stock Entry transfer of a skipped batch should submit successfully")

    def test_purchase_receipt_gkk_rejection_blocking(self):
        """If a Quality Inspection is submitted and Rejected, the batch transfer must remain blocked."""
        
        frappe.db.set_value("Item", self.item, {
            "inspection_required_before_purchase": 1,
            "has_batch_no": 1
        })
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # 1. Create and submit Purchase Receipt
        pr = self.create_test_purchase_receipt()
        for item in pr.items:
            item.custom_split_qty = 5
            item.custom_do_not_split = 0
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        qi_name = frappe.db.get_value("Quality Inspection", {
            "reference_type": "Purchase Receipt",
            "reference_name": pr.name
        }, "name")
        self.assertTrue(qi_name)
        
        base_batch_no = pr.items[0].batch_no
        batch_no = f"{base_batch_no}0001"
        
        # 2. Reject the Quality Inspection
        qi_doc = frappe.get_doc("Quality Inspection", qi_name)
        qi_doc.status = "Rejected"
        for reading in qi_doc.readings:
            reading.reading_value = "Not OK"
            reading.status = "Rejected"
        qi_doc.submit()
        
        to_warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "name": ["!=", self.wip_warehouse], "is_rejected_warehouse": ["!=", 1], "is_group": 0}, "name")
        
        # 3. Try to transfer the batch - it should be blocked because it is rejected
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Transfer"
        se.stock_entry_type = "Material Transfer"
        se.company = self.company
        se.posting_date = pr.posting_date
        se.posting_time = frappe.utils.nowtime()
        se.from_warehouse = self.wip_warehouse
        se.to_warehouse = to_warehouse
        
        cost_center = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0}, "name")
        
        se.append("items", {
            "item_code": self.item,
            "qty": 2,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "s_warehouse": self.wip_warehouse,
            "t_warehouse": to_warehouse,
            "batch_no": batch_no,
            "cost_center": cost_center
        })
        se.insert(ignore_permissions=True)
        
        with self.assertRaises(frappe.ValidationError) as exc:
            se.submit()
            
        self.assertIn("henüz Kalite Kontrol (GKK) onayı almadığı", str(exc.exception), 
                      "Should block transfer if QI is rejected")

    def test_purchase_receipt_gkk_rejection_return_allowed(self):
        """If a Quality Inspection is submitted and Rejected, we should still be allowed
        to return the items to the supplier via a Purchase Receipt Return (is_return = 1)."""
        
        frappe.db.set_value("Item", self.item, {
            "inspection_required_before_purchase": 1,
            "has_batch_no": 1
        })
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # 1. Create and submit Purchase Receipt
        pr = self.create_test_purchase_receipt()
        for item in pr.items:
            item.custom_split_qty = 5
            item.custom_do_not_split = 0
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        qi_name = frappe.db.get_value("Quality Inspection", {
            "reference_type": "Purchase Receipt",
            "reference_name": pr.name
        }, "name")
        self.assertTrue(qi_name)
        
        # 2. Reject the Quality Inspection
        qi_doc = frappe.get_doc("Quality Inspection", qi_name)
        qi_doc.status = "Rejected"
        for reading in qi_doc.readings:
            reading.reading_value = "Not OK"
            reading.status = "Rejected"
        qi_doc.submit()
        
        # 3. Create a Purchase Return against the Purchase Receipt
        from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return
        return_pr_doc = make_purchase_return(pr.name)
        
        # Set waybill Tarihi and No as they are custom mandatory fields in KTA setup
        return_pr_doc.irsaliye_tarihi = pr.posting_date
        return_pr_doc.irsaliye_no = "RETURN-WAYBILL-123"
        
        return_pr_doc.insert(ignore_permissions=True)
        return_pr_doc.submit()
        
        self.assertEqual(return_pr_doc.docstatus, 1, "Purchase Receipt Return of a rejected batch should submit successfully")

    def test_purchase_receipt_gkk_transfer_to_rejected_warehouse_allowed(self):
        """If a Quality Inspection is not approved (or Rejected), we should still be allowed
        to transfer the items to a warehouse that is marked as 'is_rejected_warehouse'."""
        
        frappe.db.set_value("Item", self.item, {
            "inspection_required_before_purchase": 1,
            "has_batch_no": 1
        })
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # 1. Create and submit Purchase Receipt
        pr = self.create_test_purchase_receipt()
        for item in pr.items:
            item.custom_split_qty = 5
            item.custom_do_not_split = 0
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        qi_name = frappe.db.get_value("Quality Inspection", {
            "reference_type": "Purchase Receipt",
            "reference_name": pr.name
        }, "name")
        self.assertTrue(qi_name)
        
        # 2. Reject the Quality Inspection
        qi_doc = frappe.get_doc("Quality Inspection", qi_name)
        qi_doc.status = "Rejected"
        for reading in qi_doc.readings:
            reading.reading_value = "Not OK"
            reading.status = "Rejected"
        qi_doc.submit()
        
        base_batch_no = pr.items[0].batch_no
        batch_no = f"{base_batch_no}0001"
        
        # 3. Create a target rejected warehouse
        abbr = frappe.db.get_value("Company", self.company, "abbr")
        rejected_wh_name = f"_Test Rejected - {abbr}"
        if not frappe.db.exists("Warehouse", rejected_wh_name):
            rejected_wh = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": "_Test Rejected",
                "is_rejected_warehouse": 1,
                "company": self.company
            }).insert(ignore_permissions=True)
            rejected_wh_name = rejected_wh.name
        else:
            frappe.db.set_value("Warehouse", rejected_wh_name, "is_rejected_warehouse", 1)
            frappe.db.commit()
            
        # 4. Try to transfer the batch to the rejected warehouse - it should be allowed
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Transfer"
        se.stock_entry_type = "Material Transfer"
        se.company = self.company
        se.posting_date = pr.posting_date
        se.posting_time = frappe.utils.nowtime()
        se.from_warehouse = self.wip_warehouse
        se.to_warehouse = rejected_wh_name
        
        cost_center = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0}, "name")
        
        se.append("items", {
            "item_code": self.item,
            "qty": 2,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "s_warehouse": self.wip_warehouse,
            "t_warehouse": rejected_wh_name,
            "batch_no": batch_no,
            "cost_center": cost_center
        })
        se.insert(ignore_permissions=True)
        se.submit()
        
        self.assertEqual(se.docstatus, 1, "Stock Entry transfer of a rejected batch to a rejected warehouse should submit successfully")

    def test_purchase_receipt_gkk_transfer_to_rejected_warehouse_blocked_if_pending(self):
        """If a Quality Inspection is still pending (draft or not created), transferring
        the items to a warehouse that is marked as 'is_rejected_warehouse' must still be blocked."""
        
        frappe.db.set_value("Item", self.item, {
            "inspection_required_before_purchase": 1,
            "has_batch_no": 1
        })
        frappe.db.commit()
        frappe.local.request_cache.clear()

        # 1. Create and submit Purchase Receipt (this automatically creates a draft QI)
        pr = self.create_test_purchase_receipt()
        for item in pr.items:
            item.custom_split_qty = 5
            item.custom_do_not_split = 0
        pr.insert(ignore_permissions=True)
        pr.submit()
        
        base_batch_no = pr.items[0].batch_no
        batch_no = f"{base_batch_no}0001"
        
        # 2. Create a target rejected warehouse
        abbr = frappe.db.get_value("Company", self.company, "abbr")
        rejected_wh_name = f"_Test Rejected - {abbr}"
        if not frappe.db.exists("Warehouse", rejected_wh_name):
            rejected_wh = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": "_Test Rejected",
                "is_rejected_warehouse": 1,
                "company": self.company
            }).insert(ignore_permissions=True)
            rejected_wh_name = rejected_wh.name
        else:
            frappe.db.set_value("Warehouse", rejected_wh_name, "is_rejected_warehouse", 1)
            frappe.db.commit()
            
        # 3. Try to transfer the batch to the rejected warehouse - it should be blocked because GKK is pending (draft)
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Transfer"
        se.stock_entry_type = "Material Transfer"
        se.company = self.company
        se.posting_date = pr.posting_date
        se.posting_time = frappe.utils.nowtime()
        se.from_warehouse = self.wip_warehouse
        se.to_warehouse = rejected_wh_name
        
        cost_center = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0}, "name")
        
        se.append("items", {
            "item_code": self.item,
            "qty": 2,
            "uom": "Nos",
            "stock_uom": "Nos",
            "conversion_factor": 1.0,
            "s_warehouse": self.wip_warehouse,
            "t_warehouse": rejected_wh_name,
            "batch_no": batch_no,
            "cost_center": cost_center
        })
        se.insert(ignore_permissions=True)
        
        with self.assertRaises(frappe.ValidationError) as exc:
            se.submit()
            
        self.assertIn("henüz Kalite Kontrol (GKK) onayı almadığı", str(exc.exception), 
                      "Should block transfer to rejected warehouse if GKK is still pending/draft")




