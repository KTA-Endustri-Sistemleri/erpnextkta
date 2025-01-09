from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt

class KTAPurchaseReceipt(PurchaseReceipt):
    def on_update(self):
        self.my_custom_code()
        super().on_update()

    def my_custom_code(self):
        for item in self.get("items"):
            if item.quality_inspection:
                qi = frappe.db.get_value(
                    "Quality Inspection",
                    item.quality_inspection,
                    ["reference_type", "reference_name", "item_code"],
                    as_dict=True,
                )

                if qi.reference_type != self.doctype or qi.reference_name != self.name:
                    msg = f"""Row #{item.idx}: Please select a valid Quality Inspection with Reference Type
        				{frappe.bold(self.doctype)} and Reference Name {frappe.bold(self.name)}."""
                    frappe.throw(_(msg))

                if qi.item_code != item.item_code:
                    msg = f"""Row #{item.idx}: Please select a valid Quality Inspection with Item Code
        				{frappe.bold(item.item_code)}."""
                    frappe.throw(_(msg))
