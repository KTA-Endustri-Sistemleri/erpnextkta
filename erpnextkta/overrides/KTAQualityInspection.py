import frappe
from frappe.model.docstatus import DocStatus
from frappe.utils import flt

from erpnext.stock.doctype.quality_inspection.quality_inspection import QualityInspection
from erpnextkta.api import custom_split_kta_batches
from erpnextkta.api import print_kta_pr_labels


class KTAQualityInspection(QualityInspection):
    def on_submit(self):
        try:
            super().on_submit()
            if self.docstatus == DocStatus.submitted() and self.reference_type == "Purchase Receipt" and self.status == "Accepted":
                doc = frappe.get_doc('Purchase Receipt Item', self.child_row_reference)
                custom_split_kta_batches(row=doc, q_ref=self.name)

                # QI akışında batch split, SLE oluşturulduktan SONRA gerçekleşiyor.
                # _update_bundle_safely bundle entry'lerini günceller ama mevcut SLE'yi değiştirmez.
                # Repost Item Valuation, SLE'lerin yeni bundle verileriyle yeniden hesaplanmasını sağlar.
                self._repost_sle_after_qi_split(doc)

                try:
                    self.print_zebra()
                except Exception as print_err:
                    frappe.log_error(f"Zebra Print Error (QI): {str(print_err)}", "QI Zebra Print Error")
                    frappe.msgprint(f"Zebra yazdırma hatası (göz ardı edildi): {str(print_err)}", alert=True)
            if self.custom_set_item_default_qi_template == 1:
                self.set_default_qi_template()
        except Exception as e:
            import traceback
            full_trace = traceback.format_exc()
            frappe.log_error(f"Quality Inspection Submit Error {str(e)}\n{full_trace}", "Quality Inspection Submit Error")
            frappe.throw(f"Quality Inspection Submit Error {str(e)}")

    def _repost_sle_after_qi_split(self, pr_item_doc):
        """
        QI onayı sonrası bundle split yapıldığında SLE'leri yeniden hesaplar.

        Neden gerekli:
        Bundle, SLE oluşturulduktan sonra (QI onayı sırasında) değiştirilir.
        Bu nedenle giriş SLE'si orijinal bundle'a (ana batch) dayanır, ancak
        tüketim SLE'leri artık var olmayan ana batch entry'lerini arar.
        Repost, tüm SLE'lerin yeni child batch entry'leriyle tutarlı olmasını sağlar.
        """
        try:
            pr_name = pr_item_doc.parent
            pr = frappe.db.get_value(
                "Purchase Receipt",
                pr_name,
                ["posting_date", "posting_time", "company"],
                as_dict=True,
            )
            if not pr:
                return

            repost_doc = frappe.get_doc({
                "doctype": "Repost Item Valuation",
                "based_on": "Transaction",
                "voucher_type": "Purchase Receipt",
                "voucher_no": pr_name,
                "posting_date": pr.posting_date,
                "posting_time": pr.posting_time or "00:00:00",
                "company": pr.company,
                "allow_negative_stock": 1,
            })
            repost_doc.flags.ignore_permissions = True
            repost_doc.insert()
            repost_doc.submit()

        except Exception as e:
            # Repost hatası split'i geri almamalı; log'la ve devam et
            frappe.log_error(
                f"QI Split Sonrası Repost Hatası: PR={pr_item_doc.parent}, "
                f"Item={pr_item_doc.item_code}, Hata={str(e)}",
                "KTA QI Repost Error",
            )

    def print_zebra(self):
        print_kta_pr_labels(q_ref=self.name)

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
