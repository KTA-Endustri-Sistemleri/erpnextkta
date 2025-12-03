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
def get_job_card_by_barcode(job_card: str):
    """
    Job Card flow için erken validasyon.
    - Job Card'ı al
    - Bağlı olduğu Work Order'ı al
    - WO docstatus/status kontrolü yap
    - Uygun değilse HEMEN hata fırlat
    - Uygunsa frontend'e gerekli temel bilgileri döner
    """
    if not job_card:
        frappe.throw(_("İş Kartı boş olamaz."), title=_("Eksik Parametre"))

    # 1) Job Card'ı al
    try:
        jc = frappe.get_doc("Job Card", job_card)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Kartı bulunamadı: {0}").format(job_card),
            title=_("İş Kartı Bulunamadı"),
        )

    if not jc.has_permission("read"):
        frappe.throw(
            _("Bu İş Kartı için okuma yetkiniz yok."),
            frappe.PermissionError,
        )

    # 2) Bağlı olduğu Work Order
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
        frappe.throw(
            _("Bu İş Emri için okuma yetkiniz yok."),
            frappe.PermissionError,
        )

    # 3) WO docstatus + status kontrolü (create_calisma_karti ile aynı mantık)
    if wo.docstatus != 1:
        frappe.throw(
            _("İş Emri onaylanmamış (docstatus != 1)."),
            title=_("Geçersiz İş Emri"),
        )

    if wo.status not in ("Not Started", "In Process"):
        frappe.throw(
            _("İş Emri açık değil. Mevcut durum: {0}").format(wo.status),
            title=_("İş Emri Kapalı"),
        )

    # 4) Frontend'e geri dönen minimal veri
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
def create_calisma_karti(**kwargs):
    """
    Create a new Calisma Karti document from wizard payload.

    Expected payload from frontend (JSON body):
        {
            "custom_work_order": "...",  # (optional) Work Order name
            "is_karti": "...",           # Job Card name (zorunlu)
            "operasyon": "...",          # Operasyon
            "is_istasyonu": "...",       # Workstation
            "operator": "..."            # Employee.name (EMP-0001 vb., optional)
        }
    """
    # Merge kwargs with form_dict for flexibility
    data = frappe._dict(frappe.local.form_dict or {})
    data.update(kwargs or {})

    required_fields = ["is_karti", "operasyon", "is_istasyonu"]
    # custom_work_order'ı özellikle zorunlu yapmıyoruz; JC'den resolve edebiliriz
    for field in required_fields:
        if not data.get(field):
            frappe.throw(
                _("Alan zorunludur: {0}").format(field),
                title=_("Eksik Zorunlu Alan"),
            )

    job_card_name = data.is_karti
    work_order_name = data.get("custom_work_order")

    # --- 1) Önce Job Card'ı al ---
    try:
        jc = frappe.get_doc("Job Card", job_card_name)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Kartı bulunamadı: {0}").format(job_card_name)
        )

    # --- 2) İş Emri adını kesinleştir ---
    # Eğer frontend'den WO gelmediyse, JC üzerindeki work_order'ı kullan
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

    # --- 3) Work Order'ı al ---
    try:
        wo = frappe.get_doc("Work Order", work_order_name)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Emri bulunamadı: {0}").format(work_order_name)
        )

    # --- 4) Yetki kontrolleri ---
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

    # --- 5) JC gerçekten bu WO'ya mı ait? ---
    if getattr(jc, "work_order", None) and jc.work_order != wo.name:
        frappe.throw(
            _(
                "Seçilen İş Kartı, seçilen İş Emri'ne ait değil. "
                "İş Kartı: {0}, İş Emri: {1}"
            ).format(jc.name, wo.name),
            title=_("Geçersiz İş Kartı"),
        )

    # --- 6) Work Order durum kontrolü (kritik kısım burası) ---
    if wo.docstatus != 1:
        frappe.throw(
            _("İş Emri onaylanmamış (docstatus != 1)."),
            title=_("Geçersiz İş Emri"),
        )

    # Sadece açık (Not Started / In Process) İş Emri için izin ver
    if wo.status not in ("Not Started", "In Process"):
        frappe.throw(
            _("İş Emri açık değil. Mevcut durum: {0}").format(wo.status),
            title=_("İş Emri Kapalı"),
        )

    # --- 7) Alan türetmeleri (ürün, miktar vs.) ---
    urun_kodu = getattr(jc, "production_item", None) or getattr(
        wo, "production_item", None
    )
    uretilecek_miktar = getattr(jc, "for_quantity", None) or getattr(
        wo, "qty", None
    )

    # Workstation: wizard > Job Card fallback
    is_istasyonu = data.get("is_istasyonu") or getattr(jc, "workstation", None)
    if not is_istasyonu:
        frappe.throw(
            _("İş İstasyonu zorunludur (Job Card veya wizard tarafından sağlanmalı).")
        )

    operator = data.get("operator")  # Employee.name

    # --- 8) Doküman dict'i inşa et ---
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
    doc.insert()  # izinlere saygılı

    frappe.db.commit()
    return doc.as_dict()