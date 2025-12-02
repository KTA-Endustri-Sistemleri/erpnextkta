import frappe
from frappe import _


@frappe.whitelist()
def get_work_order_by_barcode(barcode: str):
    """
    Resolve Work Order from scanned barcode.

    Current implementation assumes that the barcode is equal to Work Order name.
    If you use a custom barcode field on Work Order (e.g. custom_barcode),
    you can change the lookup logic below accordingly.
    """
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
        frappe.throw(
            _("Bu barkoda ait bir İş Emri bulunamadı: {0}").format(barcode)
        )

    # Permission check
    if not wo.has_permission("read"):
        frappe.throw(
            _("Bu İş Emri için okuma yetkiniz yok."),
            frappe.PermissionError,
        )

    # Status / docstatus check (same spirit as form query filters)
    if wo.docstatus != 1:
        frappe.throw(_("İş Emri onaylanmamış (docstatus != 1)."))

    if wo.status not in ("Not Started", "In Process"):
        frappe.throw(
            _("İş Emri açık değil. Mevcut durum: {0}").format(wo.status)
        )

    # Return minimal data needed by the Vue wizard
    return {
        "name": wo.name,
        "production_item": getattr(wo, "production_item", None),
        "qty": getattr(wo, "qty", None),
    }


@frappe.whitelist()
def create_calisma_karti(**kwargs):
    """
    Create a new Calisma Karti document from wizard payload.

    Expected payload from frontend (JSON body):
        {
            "custom_work_order": "...",  # Link to Work Order
            "is_karti": "...",           # Link to Job Card
            "operasyon": "...",          # Operation string (calisma_karti_op)
            "is_istasyonu": "...",       # Workstation
            "operator": "EMP-0001"       # (optional) Employee.name (Link -> Employee)
        }

    Adjust fieldnames below if your DocType uses different names.
    """
    # Merge kwargs with form_dict for flexibility
    data = frappe._dict(frappe.local.form_dict or {})
    # kwargs has precedence if both exist
    data.update(kwargs or {})

    required_fields = ["custom_work_order", "is_karti", "operasyon", "is_istasyonu"]
    for field in required_fields:
        if not data.get(field):
            frappe.throw(
                _("Alan zorunludur: {0}").format(field),
                title=_("Eksik Zorunlu Alan"),
            )

    # Fetch related documents
    work_order_name = data.custom_work_order
    job_card_name = data.is_karti

    try:
        wo = frappe.get_doc("Work Order", work_order_name)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Emri bulunamadı: {0}").format(work_order_name)
        )

    try:
        jc = frappe.get_doc("Job Card", job_card_name)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Kartı bulunamadı: {0}").format(job_card_name)
        )

    # Permission checks
    if not wo.has_permission("read"):
        frappe.throw(
            _("Bu İş Emri için okuma yetkiniz yok."),
            frappe.PermissionError,
        )

    if not jc.has_permission("read"):
        frappe.throw(
            _("Bu İş Kartı için okuma yetkiniz yok."),
            frappe.PermissionError,
        )

    # Ensure Job Card belongs to selected Work Order (same logic as JS form)
    if getattr(jc, "work_order", None) and jc.work_order != wo.name:
        frappe.throw(
            _(
                "Seçilen İş Kartı, seçilen İş Emri'ne ait değil. "
                "İş Kartı: {0}, İş Emri: {1}"
            ).format(jc.name, wo.name),
            title=_("Geçersiz İş Kartı"),
        )

    # Derive some fields from Job Card / Work Order, like in calisma_karti.js
    urun_kodu = getattr(jc, "production_item", None) or getattr(
        wo, "production_item", None
    )
    uretilecek_miktar = getattr(jc, "for_quantity", None) or getattr(wo, "qty", None)

    # If frontend sent a workstation, trust that; otherwise fallback to Job Card workstation
    is_istasyonu = data.get("is_istasyonu") or getattr(jc, "workstation", None)

    if not is_istasyonu:
        frappe.throw(
            _("İş İstasyonu zorunludur (Job Card veya wizard tarafından sağlanmalı).")
        )

    # Optional operator (Employee) field
    operator = data.get("operator")

    # Try to resolve Employee.department and prepare tag value
    operator_department_tag = None
    if operator:
        try:
            emp = frappe.get_doc("Employee", operator)
            dept = getattr(emp, "department", None)
            if dept:
                # Örn: "RATIONAL - KTA" -> "RATIONAL"
                operator_department_tag = dept.split("-")[0].strip()
        except frappe.DoesNotExistError:
            # Employee yoksa tag üretmeyelim; link validation zaten insert'te patlar
            operator_department_tag = None

    # Build document dict
    doc_dict = {
        "doctype": "Calisma Karti",
        "custom_work_order": wo.name,
        "is_karti": jc.name,
        "operasyon": data.operasyon,
        "is_istasyonu": is_istasyonu,
        # Derived fields (these exist in your JS logic)
        "urun_kodu": urun_kodu,
        "uretilecek_miktar": uretilecek_miktar,
    }

    # Add responsible user if field exists in your DocType
    if operator:
        # If your fieldname is different, change this key:
        doc_dict["operator"] = operator

    # Create & insert document
    doc = frappe.get_doc(doc_dict)
    doc.insert()  # respect permissions

    # Departmandan üretilen tag'i ekle (varsa)
    if operator_department_tag:
        try:
            from frappe.desk.doctype.tag.tag import add_tag

            add_tag(operator_department_tag, doc.doctype, doc.name)
        except Exception:
            # Tag ekleme hatası ana akışı bozmamalı
            frappe.log_error(
                frappe.get_traceback(),
                _("Calisma Karti Tag Ekleme Hatası"),
            )

    # Optionally submit automatically:
    # if you want Calisma Karti to start as submitted, uncomment:
    # doc.submit()

    frappe.db.commit()

    # Return the created doc for frontend
    return doc.as_dict()