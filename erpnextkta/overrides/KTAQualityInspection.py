import frappe
from frappe.model.docstatus import DocStatus

import erpnextkta.api
from erpnext.stock.doctype.quality_inspection.quality_inspection import QualityInspection


class KTAQualityInspection(QualityInspection):
    def on_submit(self):
        try:
            if self.docstatus == DocStatus.submitted() and self.reference_type == "Purchase Receipt":
                super().on_submit()

                doc = frappe.get_doc('Purchase Receipt Item', self.child_row_reference)
                erpnextkta.api.custom_split_kta_batches(self, row=doc)
                self.print_zebra()
            else:
                super().on_submit()
        except Exception as e:
            frappe.log_error(f"Quality Inspection Submit Error {str(e)}", "Quality Inspection Submit Error")
            frappe.throw(f"Quality Inspection Submit Error {str(e)}")

    def validate(self):
        super().validate()
        if self.should_validate_template():
            self.validate_quality_inspection_template()

    def should_validate_template(self):
        """Check if template validation should be performed"""
        return (self.inspection_type == "Incoming"
                and self.reference_type == "Purchase Receipt"
                and self.item_code
                and self.quality_inspection_template)

    def validate_quality_inspection_template(self):
        """Validate and prompt to set the default template if different"""
        default_qi_template = frappe.db.get_value(
            "Item",
            self.item_code,
            "quality_inspection_template"
        )

        if default_qi_template:
            if self.quality_inspection_template != default_qi_template:
                self.show_template_mismatch_prompt(
                    default_qi_template,
                    existing_template=True
                )
        else:
            self.show_template_mismatch_prompt(
                existing_template=False
            )

    def show_template_mismatch_prompt(self, default_template=None, existing_template=True):
        """Show the appropriate message based on whether the template exists"""
        message = self.get_template_message(default_template, existing_template)

        frappe.msgprint(
            msg=message,
            title="Kalite Kontrol Planı Uyarısı",
            primary_action={
                'label': 'Varsayılanı Değiştir',
                'server_action': 'set_default_qi_template',
                'args': {
                    'item': self.item_code,
                    'template': self.quality_inspection_template
                }
            }
        )

    def get_template_message(self, default_template, existing_template):
        """Generate the appropriate message based on template status"""
        if existing_template:
            return ("""
                    Kullanılan Kalite Kontrol Planı <b>{item_code}</b> üzerinde tanımlı varsayılandan farklı.<br><br>
                    Tanımlı Kalite Kontrol Planı: {default_template}<br>
                    Kullanılan Kalite Kontrol Planı: {current_template}<br><br>
                    Bu Kalite Kontrol Planını varsayılan yapmak ister misiniz?
            """).format(
                item_code=self.item_code,
                default_template=default_template,
                current_template=self.quality_inspection_template
            )
        else:
            return ("""
                    <b>{item_code}</b> üzerinde Kalite Kontrol Planı tanımlı değil.<br>
                    Kullanılan Kalite Kontrol Planı: {current_template}<br>
                    Bu Kalite Kontrol Planını varsayılan yapmak ister misiniz?
            """).format(
                item_code=self.item_code,
                current_template=self.quality_inspection_template
            )

    def print_zebra(self):
        erpnextkta.api.print_to_zebra_kta(q_ref=self.name)


@frappe.whitelist()
def set_default_qi_template(**kwargs):
    """Set the default quality inspection template for an item"""
    try:
        item = kwargs.get('item')
        template = kwargs.get('template')

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
