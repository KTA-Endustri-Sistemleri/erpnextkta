import frappe

from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder


class KTAWorkOrder(WorkOrder):
    def on_submit(self):
        super.on_submit()
        item = frappe.get_doc('Item', self.production_item)
        bom = frappe.get_doc('BOM', self.bom_no)
        material_request = frappe.get_doc('Material Request', self.material_request)
        material_request_item = frappe.get_doc('Material Request Item', self.material_request_item)