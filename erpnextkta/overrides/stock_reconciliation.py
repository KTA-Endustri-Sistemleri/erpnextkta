import frappe
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
    StockReconciliation as CoreStockReconciliation,
)
from frappe.utils import flt


class StockReconciliation(CoreStockReconciliation):
    """
    Keep reconciliation rows intact even on submit and handle cleanup on cancel/trash.
    """

    def remove_items_with_no_change(self):
        # NO-OP: never drop unchanged rows
        return

    def on_cancel(self):
        super().on_cancel()
        self._cleanup_associated_labels_and_batches(delete_batches=False)

    def on_trash(self):
        self._cleanup_associated_labels_and_batches(delete_batches=True)
        super().on_trash()

    def _cleanup_associated_labels_and_batches(self, delete_batches: bool = False):
        # 1. Reference ile bağlı KTA Stock Label ve KTA Print Log kayıtlarını temizle
        label_names = frappe.get_all(
            "KTA Stock Label",
            filters={
                "reference_doctype": "Stock Reconciliation",
                "reference_name": self.name,
            },
            pluck="name",
        )
        if label_names:
            from erpnextkta.kta_stock.services.relabeling_service import (
                delete_labels_with_print_logs,
            )

            delete_labels_with_print_logs(label_names)

        # 2. Partileri topla ve kontrol et
        touched_pairs = set()
        batches_to_check = set()
        for item in getattr(self, "items", []) or []:
            item_code = getattr(item, "item_code", None)
            batch_no = getattr(item, "batch_no", None)
            if item_code and batch_no:
                touched_pairs.add((item_code, batch_no))
                batches_to_check.add(batch_no)

        for batch_name in batches_to_check:
            if not frappe.db.exists("Batch", batch_name):
                continue

            batch_meta = frappe.db.get_value(
                "Batch",
                batch_name,
                ["reference_doctype", "reference_name"],
                as_dict=True,
            )
            if not batch_meta:
                continue

            created_in_sr = (
                batch_meta.get("reference_doctype") == "Stock Reconciliation"
                and batch_meta.get("reference_name") == self.name
            )

            sle_qty = flt(
                frappe.db.sql(
                    """
                    SELECT SUM(actual_qty)
                    FROM `tabStock Ledger Entry`
                    WHERE docstatus = 1 AND is_cancelled = 0 AND batch_no = %s
                    """,
                    (batch_name,),
                )[0][0]
                or 0
            )
            is_zero_balance = abs(sle_qty) < 1e-6

            if created_in_sr and is_zero_balance:
                if delete_batches:
                    sle_count = frappe.db.count(
                        "Stock Ledger Entry", {"batch_no": batch_name}
                    )
                    deleted = False
                    if sle_count == 0:
                        try:
                            frappe.delete_doc(
                                "Batch",
                                batch_name,
                                ignore_permissions=True,
                                force=True,
                            )
                            deleted = True
                        except Exception:  # noqa: BLE001
                            deleted = False
                    if not deleted:
                        frappe.db.set_value(
                            "Batch",
                            batch_name,
                            {"batch_qty": 0, "disabled": 1},
                            update_modified=False,
                        )
                else:
                    frappe.db.set_value(
                        "Batch",
                        batch_name,
                        {"batch_qty": 0, "disabled": 1},
                        update_modified=False,
                    )

        # 3. Sıfır bakiyeli etiketleri temizle
        if touched_pairs:
            from erpnextkta.kta_stock.label_manager import LabelPrinter

            LabelPrinter.clear_empty_labels(pairs=list(touched_pairs))
