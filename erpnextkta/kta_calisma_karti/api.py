# English comments as requested

from __future__ import annotations

import frappe
from frappe import _


HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA"


def _is_system_manager() -> bool:
    """Return True if current user has System Manager role."""
    return "System Manager" in (frappe.get_roles(frappe.session.user) or [])


def _get_my_employee_or_none() -> str | None:
    """
    Try to resolve current user's Employee.name robustly.

    Common mappings:
    - Employee.user_id == frappe.session.user
    - Employee.company_email / personal_email == frappe.session.user
    """
    user = frappe.session.user

    # Check available columns first (schema-safe)
    cols = []
    try:
        cols = frappe.db.get_table_columns("Employee") or []
    except Exception:
        cols = []

    checks = []
    if "user_id" in cols:
        checks.append(("user_id", user))
    if "company_email" in cols:
        checks.append(("company_email", user))
    if "personal_email" in cols:
        checks.append(("personal_email", user))

    for field, value in checks:
        emp = frappe.db.get_value("Employee", {field: value}, "name")
        if emp:
            return emp

    return None


def _first_child_table(doc, candidates: list[str]) -> list[dict]:
    """Return first existing child table from candidate fieldnames."""
    for fn in candidates:
        rows = doc.get(fn)
        if rows:
            return [r.as_dict() for r in rows]
    return []


def _get_child_table_fieldname(parent_doc, child_doctype: str) -> str:
    """
    Find the parent fieldname (Table) that points to the given child doctype.
    Example: Calisma Karti -> Table field whose options == "Calisma Karti Hurda"
    """
    meta = frappe.get_meta(parent_doc.doctype)
    for df in meta.fields:
        if df.fieldtype == "Table" and df.options == child_doctype:
            return df.fieldname
    frappe.throw(_("Parent doctype içinde '{0}' child table alanı bulunamadı.").format(child_doctype))


# -----------------------------
# Public APIs for Vue
# -----------------------------

@frappe.whitelist()
def get_my_calisma_kartlari():
    """
    Return cards for current user.
    - If System Manager: return all cards (still respects doctype permissions).
    - Else: filter by operator = current user's Employee.
    """
    if _is_system_manager():
        return frappe.get_all(
            "Calisma Karti",
            fields=[
                "name",
                "custom_work_order",
                "is_karti",
                "operasyon",
                "urun_kodu",
                "is_istasyonu",
                "operator",
                "durum",
                "baslangic_saati",
                "bitis_saati",
                "modified",
            ],
            order_by="modified desc",
            limit_page_length=200,
        )

    emp = _get_my_employee_or_none()
    if not emp:
        frappe.throw(
            _("Employee eşleşmesi bulunamadı. Lütfen Employee kayıtlarında user_id / company_email / personal_email alanlarını kontrol edin. User: {0}")
            .format(frappe.session.user)
        )

    return frappe.get_all(
        "Calisma Karti",
        filters={"operator": emp},
        fields=[
            "name",
            "custom_work_order",
            "is_karti",
            "operasyon",
            "urun_kodu",
            "is_istasyonu",
            "operator",
            "durum",
            "baslangic_saati",
            "bitis_saati",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=200,
    )


@frappe.whitelist()
def get_calisma_karti_detail(name: str):
    """
    Return detail payload for Vue UI.
    - If System Manager: allow any card
    - Else: only allow if operator == current user's Employee
    """
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    if not _is_system_manager():
        emp = _get_my_employee_or_none()
        if not emp:
            frappe.throw(
                _("Employee eşleşmesi bulunamadı. Lütfen Employee kayıtlarında user_id / company_email / personal_email alanlarını kontrol edin. User: {0}")
                .format(frappe.session.user)
            )
        if doc.operator != emp:
            frappe.throw(_("Bu çalışma kartını görüntüleme yetkiniz yok."), frappe.PermissionError)

    hurdalar = _first_child_table(doc, ["hurdalar", "hurda", "calisma_karti_hurda"])
    duruslar = _first_child_table(doc, ["duruslar", "durus", "operasyon_duruslari"])

    return {
        "name": doc.name,
        "custom_work_order": doc.custom_work_order,
        "is_karti": doc.is_karti,
        "operasyon": doc.operasyon,
        "urun_kodu": doc.urun_kodu,
        "is_istasyonu": doc.is_istasyonu,
        "operator": doc.operator,
        "durum": doc.durum,
        "baslangic_saati": doc.baslangic_saati,
        "bitis_saati": doc.bitis_saati,
        "hurdalar": hurdalar,
        "duruslar": duruslar,
        "tamamlanan_miktar": float(doc.tamamlanan_miktar or 0),
        "kalite_kontrol": doc.kalite_kontrol,
    }


@frappe.whitelist()
def get_hurda_nedeni_options(parent_cost_center: str = HURDA_PARENT_COST_CENTER):
    """
    Return cost center names where parent_cost_center matches given value.
    Intended to be used as Select options in Vue prompt.
    """
    rows = frappe.get_all(
        "Cost Center",
        filters={"parent_cost_center": parent_cost_center, "is_group": 0},
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )
    return [r["name"] for r in rows]


@frappe.whitelist()
def add_hurda(
    name: str,
    parca_no: str,
    hurda_nedeni: str,
    miktar: float,
    birim: str,
    depo: str | None = None,
):
    """
    Append a row to Calisma Karti Hurda child table.
    Security:
      - System Manager: allowed
      - Others: must be operator's card
    Also validates hurda_nedeni is a Cost Center under configured parent.
    """
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("write")

    if not _is_system_manager():
        emp = _get_my_employee_or_none()
        if not emp:
            frappe.throw(
                _("Employee eşleşmesi bulunamadı. User: {0}").format(frappe.session.user)
            )
        if doc.operator != emp:
            frappe.throw(_("Bu çalışma kartına hurda ekleme yetkiniz yok."), frappe.PermissionError)

    # Validate selected cost center
    ok = frappe.db.exists(
        "Cost Center",
        {"name": hurda_nedeni, "parent_cost_center": HURDA_PARENT_COST_CENTER},
    )
    if not ok:
        frappe.throw(_("Hurda Nedeni geçersiz. Lütfen listeden seçin."))

    child_fieldname = _get_child_table_fieldname(doc, "Calisma Karti Hurda")

    row = {
        "parca_no": parca_no,
        "hurda_nedeni": hurda_nedeni,
        "miktar": float(miktar or 0),
        "birim": birim,
    }
    if depo:
        row["depo"] = depo

    doc.append(child_fieldname, row)
    doc.save()

    return {"status": "success"}
@frappe.whitelist()
def update_hurda(
    name: str,
    rowname: str,
    parca_no: str,
    hurda_nedeni: str,
    miktar: float,
    birim: str,
    depo: str | None = None,
):
    """
    Update an existing Calisma Karti Hurda child row by its row 'name'.
    """
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("write")

    if not _is_system_manager():
        emp = _get_my_employee_or_none()
        if not emp:
            frappe.throw(_("Employee eşleşmesi bulunamadı. User: {0}").format(frappe.session.user))
        if doc.operator != emp:
            frappe.throw(_("Bu çalışma kartında hurda düzenleme yetkiniz yok."), frappe.PermissionError)

    # Validate selected cost center
    ok = frappe.db.exists(
        "Cost Center",
        {"name": hurda_nedeni, "parent_cost_center": HURDA_PARENT_COST_CENTER},
    )
    if not ok:
        frappe.throw(_("Hurda Nedeni geçersiz. Lütfen listeden seçin."))

    child_fieldname = _get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    target = None
    for r in rows:
        if r.name == rowname:
            target = r
            break

    if not target:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    target.parca_no = parca_no
    target.hurda_nedeni = hurda_nedeni
    target.miktar = float(miktar or 0)
    target.birim = birim
    target.depo = depo or None

    doc.save()
    return {"status": "success"}


@frappe.whitelist()
def delete_hurda(name: str, rowname: str):
    """
    Delete a Calisma Karti Hurda child row by its row 'name'.
    """
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("write")

    if not _is_system_manager():
        emp = _get_my_employee_or_none()
        if not emp:
            frappe.throw(_("Employee eşleşmesi bulunamadı. User: {0}").format(frappe.session.user))
        if doc.operator != emp:
            frappe.throw(_("Bu çalışma kartında hurda silme yetkiniz yok."), frappe.PermissionError)

    child_fieldname = _get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    idx = None
    for i, r in enumerate(rows):
        if r.name == rowname:
            idx = i
            break

    if idx is None:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    rows.pop(idx)
    doc.set(child_fieldname, rows)
    doc.save()


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

    # --- 9) Operatör'ün departmanından tag üret ve ekle ---
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

    # İstersen otomatik submit:
    # doc.submit()

    frappe.db.commit()
    return doc.as_dict()

@frappe.whitelist()
def get_job_card_by_barcode(barcode: str):
    """
    Job Card flow için erken validasyon.
    - Job Card'ı al
    - Bağlı olduğu Work Order'ı al
    - WO docstatus/status kontrolü yap
    - Uygun değilse HEMEN hata fırlat
    - Uygunsa frontend'e gerekli temel bilgileri döner
    """
    if not barcode:
        frappe.throw(_("İş Kartı boş olamaz."), title=_("Eksik Parametre"))

    # 1) Job Card'ı al
    try:
        jc = frappe.get_doc("Job Card", barcode)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Seçilen İş Kartı bulunamadı: {0}").format(barcode),
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