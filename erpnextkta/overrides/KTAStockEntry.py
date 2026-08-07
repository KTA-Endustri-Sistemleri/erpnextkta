import frappe
from frappe import _
from frappe.model.docstatus import DocStatus
from frappe.utils import flt
from erpnextkta.kta_stock.batch_manager import BatchSplitManager
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


class KTAStockEntry(StockEntry):
    def get_work_order_raw_materials(self, qty):
        """Override to deduct quantities already consumed via
        operation-based Material Consumption Stock Entries."""
        item_dict = super().get_work_order_raw_materials(qty)

        if not (self.work_order and self.pro_doc and self.pro_doc.skip_transfer):
            return item_dict

        consumed = self._get_already_consumed_qty()
        if not consumed:
            return item_dict

        items_to_remove = []
        for item_code, row in item_dict.items():
            already = flt(consumed.get(row.get("item_code") or item_code, 0))
            if already <= 0:
                continue
            remaining = flt(row.qty) - already
            if remaining <= 0:
                items_to_remove.append(item_code)
            else:
                row.qty = flt(
                    remaining,
                    frappe.get_precision("Stock Entry Detail", "qty"),
                )

        for key in items_to_remove:
            del item_dict[key]

        return item_dict

    def _get_already_consumed_qty(self):
        """Return {item_code: consumed_qty} from submitted
        Material Consumption for Manufacture Stock Entries
        against this Work Order."""
        data = frappe.db.sql(
            """
            SELECT detail.item_code, SUM(detail.qty) as qty
            FROM `tabStock Entry` entry
            INNER JOIN `tabStock Entry Detail` detail ON detail.parent = entry.name
            WHERE entry.work_order = %s
                AND entry.purpose = 'Material Consumption for Manufacture'
                AND entry.docstatus = 1
                AND detail.s_warehouse IS NOT NULL
            GROUP BY detail.item_code
            """,
            (self.work_order,),
            as_dict=True,
        )
        return {d.item_code: flt(d.qty) for d in data} if data else {}

    def check_if_operations_completed(self):
        """Override to skip operation completion validation for Material Consumption Stock Entries."""
        if self.purpose == "Material Consumption for Manufacture":
            return
            
        super().check_if_operations_completed()

    def validate_purpose(self):
        valid_purposes = [
            "Material Issue",
            "Material Receipt",
            "Material Transfer",
            "Material Transfer for Manufacture",
            "Manufacture",
            "Repack",
            "Send to Subcontractor",
            "Material Consumption for Manufacture",
            "Disassemble",
        ]

        if self.purpose not in valid_purposes:
            frappe.throw(_("Purpose must be one of {0}").format(", ".join(valid_purposes)))

        # KTA Override: Allow 'Material Consumption for Manufacture' against Job Card
        allowed_job_card_purposes = ["Material Transfer for Manufacture", "Repack", "Material Consumption for Manufacture"]
        if self.job_card and self.purpose not in allowed_job_card_purposes:
            frappe.throw(
                _(
                    "For job card {0}, you can only make {1} type stock entries"
                ).format(self.job_card, ", ".join(allowed_job_card_purposes))
            )

    def validate(self):
        # 1. Standart ERPNext kontrollerini yap
        super().validate()
        
        # 2. Sadece Manufacture tipinde ve Draft (0) durumundaysa çalış
        if self.purpose == "Manufacture" and self.work_order and self.docstatus == 0:
            # 3. Sonsuz döngü koruması (Flag)
            if not self.get("__splitting_batches"):
                self.set("__splitting_batches", True)
                BatchSplitManager.split_manufacturing_batches(self)

    def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
        """
        Base StockEntry.update_stock_ledger does not accept via_landed_cost_voucher, swallow it here
        """
        super().update_stock_ledger(allow_negative_stock=allow_negative_stock)

    def on_submit(self):
        super().on_submit()
        frappe.enqueue(
            "erpnextkta.overrides.KTAStockEntry.print_labels_on_submit",
            stock_entry=self.name,
            user=frappe.session.user,
            queue="short",
            timeout=120,
            now=frappe.flags.in_test,
            enqueue_after_commit=True,
        )

    def on_cancel(self):
        batches_to_disable = []
        if self.purpose == "Manufacture":
            batches_to_disable = self._get_generated_batches()
            
        super().on_cancel()
        
        self._delete_associated_labels()
        
        if self.purpose == "Manufacture":
            for batch_name in batches_to_disable:
                if frappe.db.exists("Batch", batch_name):
                    frappe.db.set_value("Batch", batch_name, {"batch_qty": 0, "disabled": 1}, update_modified=False)

    def on_trash(self):
        batches_to_delete = []
        if self.purpose == "Manufacture":
            batches_to_delete = self._get_generated_batches()
            
        self._delete_associated_labels()
        super().on_trash()
        
        if self.purpose == "Manufacture":
            for batch_name in batches_to_delete:
                if frappe.db.exists("Batch", batch_name):
                    try:
                        frappe.delete_doc("Batch", batch_name, ignore_permissions=True)
                    except Exception:
                        # If deletion fails (e.g., due to LinkExistsError), ensure it's empty and disabled
                        frappe.db.set_value("Batch", batch_name, {
                            "batch_qty": 0,
                            "disabled": 1
                        }, update_modified=False)
                    
    def _delete_associated_labels(self):
        labels = frappe.get_all("KTA Stock Label", filters={
            "reference_doctype": "Stock Entry",
            "reference_name": self.name
        }, pluck="name")
        for label in labels:
            logs = frappe.get_all("KTA Print Log", filters={
                "label_doctype": "KTA Stock Label",
                "label_name": label
            }, pluck="name")
            for log in logs:
                try:
                    frappe.delete_doc("KTA Print Log", log, ignore_permissions=True, force=True)
                except Exception:
                    frappe.log_error(
                        f"Failed to delete KTA Print Log {log} for label {label} (Stock Entry {self.name}).\n{frappe.get_traceback()}",
                        "KTAStockEntry cleanup"
                    )
            try:
                frappe.delete_doc("KTA Stock Label", label, ignore_permissions=True, force=True)
            except Exception:
                frappe.log_error(
                    f"Failed to delete KTA Stock Label {label} (Stock Entry {self.name}).\n{frappe.get_traceback()}",
                    "KTAStockEntry cleanup"
                )

    def _get_generated_batches(self):
        batches = set()
        
        # 1. Try to find bundles via voucher_no in DB (works even if doc is cancelled and row links are cleared)
        bundles = frappe.get_all("Serial and Batch Bundle", 
                                 filters={"voucher_type": "Stock Entry", "voucher_no": self.name},
                                 pluck="name")
                                 
        # 2. Fallback to row fields if not found (e.g. before save/submit)
        if not bundles:
            bundles = [row.get("serial_and_batch_bundle") for row in self.get("items", []) 
                      if row.get("is_finished_item") and row.get("serial_and_batch_bundle")]

        for bundle in bundles:
            entries = frappe.get_all("Serial and Batch Entry", 
                                    filters={"parent": bundle, "is_outward": 0},
                                    pluck="batch_no")
            for b in entries:
                if b:
                    batches.add(b)
        return list(batches)

def print_labels_on_submit(stock_entry, user=None):
    if user:
        frappe.set_user(user)

    from erpnextkta.kta_stock.label_manager import print_stock_entry_labels
    try:
        doc = frappe.get_doc("Stock Entry", stock_entry)
        if doc.stock_entry_type:
            is_printable = frappe.db.get_value("Stock Entry Type", doc.stock_entry_type, "custom_etiket_basilabilir")
            if is_printable:
                print_stock_entry_labels(stock_entry)
    except Exception as e:
        import traceback
        frappe.log_error(f"Stock Entry Print Error: {traceback.format_exc()}", "Stock Entry Submit Print Error")