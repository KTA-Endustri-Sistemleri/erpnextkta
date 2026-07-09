import frappe
from frappe import _
from frappe.model.docstatus import DocStatus
from frappe.utils import flt

from erpnext.stock.doctype.quality_inspection.quality_inspection import QualityInspection
from erpnextkta.kta_stock.label_manager import print_kta_pr_labels, custom_split_kta_batches


class KTAQualityInspection(QualityInspection):
    def validate(self):
        super().validate()
        self.validate_unique_calisma_karti()

    def validate_unique_calisma_karti(self):
        if getattr(self, "custom_calisma_karti", None):
            ck_operasyon = frappe.db.get_value("Calisma Karti", self.custom_calisma_karti, "operasyon")
            if ck_operasyon:
                alt_kalite_zorunlu = frappe.db.get_value("KTA Calisma Karti Operasyonlari", ck_operasyon, "alt_operasyon_bazli_kalite")
            else:
                alt_kalite_zorunlu = 0
            
            alt_op = getattr(self, "custom_alt_operasyon_kaydi", None)

            if alt_kalite_zorunlu and not alt_op:
                frappe.throw(_("Bu operasyon Alt Operasyon bazlı kalite onayı gerektirmektedir. Kalite kontrol belgesine Alt Operasyon Kaydı mutlaka seçilmelidir."))
            elif not alt_kalite_zorunlu and alt_op:
                frappe.throw(_("Bu operasyon Alt Operasyon bazlı kalite onayı gerektirmez. Alt Operasyon Kaydı alanı boş bırakılmalıdır."))

            filters = {
                "custom_calisma_karti": self.custom_calisma_karti,
                "name": ("!=", self.name),
                "docstatus": ("<", 2)
            }
            alt_op = getattr(self, "custom_alt_operasyon_kaydi", None)
            if alt_op:
                filters["custom_alt_operasyon_kaydi"] = alt_op
            else:
                filters["custom_alt_operasyon_kaydi"] = ("is", "not set")

            existing = frappe.db.get_value("Quality Inspection", filters, "name")
            if existing:
                if alt_op:
                    frappe.throw(_("Bu Çalışma Kartı'nın seçili Alt Operasyonu için zaten bir Kalite Kontrol belgesi ({0}) mevcut.").format(existing))
                else:
                    frappe.throw(_("Bu Çalışma Kartı için zaten bir Kalite Kontrol belgesi ({0}) mevcut.").format(existing))

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
            frappe.throw(_("Kalite Kontrol Gönderim Hatası {0}").format(str(e)))

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
                frappe.throw(_("Gerekli parametreler eksik: ürün ve template"))

            doc = frappe.get_doc('Item', item)
            doc.db_set('quality_inspection_template', template, commit=True)

            frappe.msgprint(
                _("Varsayılan kalite kontrol planı başarıyla güncellendi"),
                indicator="green",
                alert=True
            )

        except Exception as e:
            frappe.log_error(
                "Kalite kontrol planı güncelleme hatası",
                "set_default_qi_template\n{0}".format(frappe.get_traceback())
            )
            frappe.throw(
                _("Varsayılan plan güncellenirken hata oluştu: {0}").format(str(e))
            )
