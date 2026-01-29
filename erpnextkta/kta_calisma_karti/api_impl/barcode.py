# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

@frappe.whitelist()
def get_job_card_by_barcode(barcode: str):
    if not barcode:
        frappe.throw(_("İş Kartı boş olamaz."), title=_("Eksik Parametre"))

    # 1) Load Job Card
    try:
        jc = frappe.get_doc("Job Card", barcode)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Kartı bulunamadı: {0}").format(barcode),
            title=_("İş Kartı Bulunamadı"),
        )

    if not jc.has_permission("read"):
        frappe.throw(_("Bu İş Kartı için okuma yetkiniz yok."), frappe.PermissionError)

    # 2) Linked Work Order
    wo_name = getattr(jc, "work_order", None)
    if not wo_name:
        frappe.throw(
            _(
                "İş Kartının bağlı olduğu bir İş Emri bulunamadı. "
                "Lütfen İş Kartı ayarlarını kontrol edin."
            ),
            title=_("İş Emri Bulunamadı"),
        )

    try:
        wo = frappe.get_doc("Work Order", wo_name)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Emri bulunamadı: {0}").format(wo_name),
            title=_("İş Emri Bulunamadı"),
        )

    if not wo.has_permission("read"):
        frappe.throw(_("Bu İş Emri için okuma yetkiniz yok."), frappe.PermissionError)

    # 3) Status / docstatus checks (same spirit as create_calisma_karti)
    if wo.docstatus != 1:
        frappe.throw(_("İş Emri onaylanmamış (docstatus != 1)."), title=_("Geçersiz İş Emri"))

    if wo.status not in ("Not Started", "In Process"):
        frappe.throw(_("İş Emri açık değil. Mevcut durum: {0}").format(wo.status), title=_("İş Emri Kapalı"))

    # 4) Minimal payload
    return {
        "job_card": jc.name,
        "work_order": wo.name,
        "operation": getattr(jc, "operation", None),
        "workstation": getattr(jc, "workstation", None),
        "production_item": getattr(jc, "production_item", None),
        "for_quantity": getattr(jc, "for_quantity", None),
        "wo_status": wo.status,
        "wo_docstatus": wo.docstatus,
    }

@frappe.whitelist()
def get_work_order_by_barcode(barcode: str):
    if not barcode:
        frappe.throw(_("Barkod boş olamaz."))

    # 1) Try by name (most common: printed barcode = Work Order name)
    try:
        wo = frappe.get_doc("Work Order", barcode)
    except frappe.DoesNotExistError:
        wo = None

    if not wo:
        # If you are using a custom barcode field, uncomment and adapt this block:
        #
        # meta = frappe.get_meta("Work Order")
        # if meta.get_field("custom_barcode"):
        #     name = frappe.db.get_value("Work Order", {"custom_barcode": barcode}, "name")
        #     if name:
        #         wo = frappe.get_doc("Work Order", name)
        #
        # For now, we simply throw an error.
        frappe.throw(_("Bu barkoda ait bir İş Emri bulunamadı: {0}").format(barcode))

    if not wo.has_permission("read"):
        frappe.throw(_("Bu İş Emri için okuma yetkiniz yok."), frappe.PermissionError)

    if wo.docstatus != 1:
        frappe.throw(_("İş Emri onaylanmamış (docstatus != 1)."))

    if wo.status not in ("Not Started", "In Process"):
        frappe.throw(_("İş Emri açık değil. Mevcut durum: {0}").format(wo.status))

    return {
        "name": wo.name,
        "production_item": getattr(wo, "production_item", None),
        "qty": getattr(wo, "qty", None),
    }
