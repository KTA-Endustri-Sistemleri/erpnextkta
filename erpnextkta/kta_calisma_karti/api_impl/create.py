# English comments as requested

from __future__ import annotations

import frappe
from frappe import _
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed

@frappe.whitelist()
def create_calisma_karti(**kwargs):
    """Create Calisma Karti from Vue wizard payload."""

    # Merge kwargs with form_dict for flexibility
    data = frappe._dict(frappe.local.form_dict or {})
    data.update(kwargs or {})

    required_fields = ["is_karti", "operasyon", "is_istasyonu"]
    # custom_work_order is not strictly required; can be resolved from Job Card
    for field in required_fields:
        if not data.get(field):
            frappe.throw(_("Alan zorunludur: {0}").format(field), title=_("Eksik Zorunlu Alan"))

    job_card_name = data.is_karti
    work_order_name = data.get("custom_work_order")

    # 1) Load Job Card
    try:
        jc = frappe.get_doc("Job Card", job_card_name)
    except frappe.DoesNotExistError:
        frappe.throw(_("Seçilen İş Kartı bulunamadı: {0}").format(job_card_name))

    # 2) Resolve Work Order
    if not work_order_name:
        work_order_name = getattr(jc, "work_order", None)

    if not work_order_name:
        frappe.throw(
            _(
                "İş Kartının bağlı olduğu bir İş Emri bulunamadı. "
                "Lütfen İş Kartı ayarlarını kontrol edin."
            ),
            title=_("İş Emri Bulunamadı"),
        )

    # 3) Load Work Order
    try:
        wo = frappe.get_doc("Work Order", work_order_name)
    except frappe.DoesNotExistError:
        frappe.throw(_("Seçilen İş Emri bulunamadı: {0}").format(work_order_name))

    # 4) Permission checks
    if not wo.has_permission("read"):
        frappe.throw(_("Bu İş Emri için okuma yetkiniz yok."), frappe.PermissionError)

    if not jc.has_permission("read"):
        frappe.throw(_("Bu İş Kartı için okuma yetkiniz yok."), frappe.PermissionError)

    # 5) Validate JC belongs to WO
    if getattr(jc, "work_order", None) and jc.work_order != wo.name:
        frappe.throw(
            _(
                "Seçilen İş Kartı, seçilen İş Emri'ne ait değil. "
                "İş Kartı: {0}, İş Emri: {1}"
            ).format(jc.name, wo.name),
            title=_("Geçersiz İş Kartı"),
        )

    # 6) Work Order status checks
    if wo.docstatus != 1:
        frappe.throw(_("İş Emri onaylanmamış (docstatus != 1)."), title=_("Geçersiz İş Emri"))

    if wo.status not in ("Not Started", "In Process"):
        frappe.throw(_("İş Emri açık değil. Mevcut durum: {0}").format(wo.status), title=_("İş Emri Kapalı"))

    # 7) Derive fields
    urun_kodu = getattr(jc, "production_item", None) or getattr(wo, "production_item", None)
    uretilecek_miktar = getattr(jc, "for_quantity", None) or getattr(wo, "qty", None)

    is_istasyonu = data.get("is_istasyonu") or getattr(jc, "workstation", None)
    if not is_istasyonu:
        frappe.throw(_("İş İstasyonu zorunludur (Job Card veya wizard tarafından sağlanmalı)."))

    operator = data.get("operator")  # Employee.name

    # 8) Build and insert doc
    doc_dict = {
        "doctype": "Calisma Karti",
        "custom_work_order": wo.name,
        "is_karti": jc.name,
        "operasyon": data.operasyon,
        "is_istasyonu": is_istasyonu,
        "urun_kodu": urun_kodu,
        "uretilecek_miktar": uretilecek_miktar,
    }
    if operator:
        doc_dict["operator"] = operator

    doc = frappe.get_doc(doc_dict)
    doc.insert()

    # ✅ Publish realtime events (create does not automatically notify list UIs)
    try:
        publish_calisma_karti_changed(doc.name, reason="create:calisma_karti")
    except Exception:
        # Don't block creation if realtime publish fails
        pass

    # 9) Add department tag (best-effort)
    operator_department_tag = None
    if operator:
        try:
            emp = frappe.get_doc("Employee", operator)
            dept = getattr(emp, "department", None)
            if dept:
                operator_department_tag = dept.split("-")[0].strip()
        except frappe.DoesNotExistError:
            operator_department_tag = None

    if operator_department_tag:
        try:
            from frappe.desk.doctype.tag.tag import add_tag

            add_tag(operator_department_tag, doc.doctype, doc.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), _("Calisma Karti Tag Ekleme Hatası"))

    frappe.db.commit()
    return doc.as_dict()
