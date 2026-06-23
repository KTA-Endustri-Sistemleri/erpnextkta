import frappe
from frappe.model.docstatus import DocStatus
from frappe.utils import flt

from erpnext.stock.doctype.quality_inspection.quality_inspection import QualityInspection
from erpnextkta.kta_stock.label_manager import print_kta_pr_labels, custom_split_kta_batches


class KTAQualityInspection(QualityInspection):
    def on_update(self):
        super().on_update()
        self.update_reference_status()

    def on_submit(self):
        try:
            super().on_submit()
            if self.custom_set_item_default_qi_template == 1:
                self.set_default_qi_template()
            self.update_reference_status()
        except Exception as e:
            import traceback
            full_trace = traceback.format_exc()
            frappe.log_error(f"Quality Inspection Submit Error {str(e)}\n{full_trace}", "Quality Inspection Submit Error")
            frappe.throw(f"Quality Inspection Submit Error {str(e)}")

    def on_cancel(self):
        super().on_cancel()
        self.update_reference_status()

    def on_trash(self):
        super().on_trash()
        self.flags.qi_being_deleted = True
        self.update_reference_status()

    def update_reference_status(self):
        if self.reference_type == "Purchase Receipt" and self.reference_name:
            try:
                pr = frappe.get_doc("Purchase Receipt", self.reference_name)
                if self.flags.qi_being_deleted:
                    pr.flags.qi_being_deleted = self.name
                pr.set_status(update=True)
            except Exception as e:
                frappe.log_error(f"Error updating reference PR status: {e}", "KTA QI Status Update Error")

    def set_default_qi_template(self):
        """Set the default quality inspection template for an item
        """
        try:
            item = self.item_code
            template = self.quality_inspection_template

            if not item or not template:
                frappe.throw("Gerekli parametreler eksik: item ve template")

            doc = frappe.get_doc('Item', item)
            doc.db_set('quality_inspection_template', template, commit=True)

            frappe.msgprint(
                "Varsayılan kalite kontrol planı başarıyla güncellendi",
                indicator="green",
                alert=True
            )

        except Exception as e:
            frappe.log_error(
                "Kalite kontrol planı güncelleme hatası",
                "set_default_qi_template\n{0}".format(frappe.get_traceback())
            )
            frappe.throw(
                "Varsayılan plan güncellenirken hata oluştu: {0}".format(str(e))
            )
