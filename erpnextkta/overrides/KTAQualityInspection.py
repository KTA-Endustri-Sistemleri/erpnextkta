import frappe
from frappe.model.docstatus import DocStatus

import erpnextkta.api
from erpnext.stock.doctype.quality_inspection.quality_inspection import QualityInspection


class KTAQualityInspection(QualityInspection):
    def on_submit(self):
        try:
            if self.docstatus == DocStatus.submitted() and self.reference_type == "Purchase Receipt" and self.status == "Accepted":
                super().on_submit()

                doc = frappe.get_doc('Purchase Receipt Item', self.child_row_reference)
                erpnextkta.api.custom_split_kta_batches(row=doc, q_ref=self.name)
                self.print_zebra()
            else:
                super().on_submit()
            if self.custom_set_item_default_qi_template == 1:
                self.set_default_qi_template()
        except Exception as e:
            frappe.log_error(f"Quality Inspection Submit Error {str(e)}", "Quality Inspection Submit Error")
            frappe.throw(f"Quality Inspection Submit Error {str(e)}")

    def print_zebra(self):
        erpnextkta.api.print_to_zebra_kta(q_ref=self.name)

    def set_default_qi_template(self):
        """Set the default quality inspection template for an item
        :param changes:
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
