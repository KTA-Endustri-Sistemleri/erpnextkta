# English comments as requested

from __future__ import annotations

import json
import frappe
from frappe import _
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed
# -----------------------------
# QC Update (Role-gated)
# -----------------------------

QC_ALLOWED_ROLES = {"KTA Kalite Kullanıcısı", "Quality Manager", "System Manager"}
QC_ALLOWED_VALUES = {"Onay Bekliyor", "Onaylandı", "Reddedildi"}

def _session_employee_name_or_throw() -> str:
    """Return Employee.name (e.g., HR-EMP-00001) mapped to current session user."""
    user = frappe.session.user

    # Primary: Employee.user_id matches the logged-in user (email)
    emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if emp:
        return emp

    # Fallbacks (some setups store email in company_email / personal_email)
    emp = frappe.db.get_value("Employee", {"company_email": user}, "name")
    if emp:
        return emp

    emp = frappe.db.get_value("Employee", {"personal_email": user}, "name")
    if emp:
        return emp

    frappe.throw(
        _("Bu kullanıcı için Employee kaydı bulunamadı. Employee.user_id / company_email / personal_email eşleşmeli: {0}").format(user),
        frappe.ValidationError,
    )


def _has_any_role(roles: set[str]) -> bool:
    """Return True if current user has any of the given roles."""
    user_roles = set(frappe.get_roles(frappe.session.user) or [])
    return bool(user_roles.intersection(roles))

def _require_qc_role():
    """Hard gate for QC-related operations."""
    if not _has_any_role(QC_ALLOWED_ROLES):
        frappe.throw(_("QC güncelleme yetkiniz yok."), frappe.PermissionError)


@frappe.whitelist()
def update_kalite_kontrol(name: str, kalite_kontrol: str):
    """Update 'kalite_kontrol' on Calisma Karti.

    Security:
    - Only users with one of QC_ALLOWED_ROLES can update.
    - Uses server-side role check + ignore_permissions to bypass permlevel=1 restriction,
      while still remaining safe due to the strict role gate above.
    """

    _require_qc_role()

    val = (kalite_kontrol or "").strip()
    if val not in QC_ALLOWED_VALUES:
        frappe.throw(_("Geçersiz kalite kontrol durumu."))

    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    # permlevel=1 field -> bypass via ignore_permissions AFTER strict role gate
    doc.flags.ignore_permissions = True
    doc.db_set("kalite_kontrol", val, update_modified=True)

    # If QC rejected, also mark work card status as rejected.
    # If QC moved away from rejected, recompute status from time fields.
    if val == "Reddedildi":
        doc.db_set("durum", "Reddedildi", update_modified=True)
    else:
        if (doc.durum or "").strip() == "Reddedildi":
            # Recompute via DocType logic (get_durum uses kalite_kontrol too)
            try:
                durum_key = doc.get_durum()
                # STATU_HARITASI lives in the DocType module
                from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import STATU_HARITASI
                doc.db_set("durum", STATU_HARITASI.get(durum_key, "Hazır"), update_modified=True)
            except Exception:
                # Fail safe: don't block QC update if status recompute fails
                pass
     # Publish realtime events (db_set does not trigger DocType on_update)
    try:
        publish_calisma_karti_changed(name, reason="qc:update_kalite_kontrol")
    except Exception:
        # Don't block QC update if realtime publish fails
        pass
    return {"status": "success", "kalite_kontrol": val}


# -----------------------------
# QC Child Tables (Role-gated)
# - idc_olcumleri
# - barkod_kayitlari
# -----------------------------

IDC_CHILD_FIELDNAME = "idc_olcumleri"
BARKOD_CHILD_FIELDNAME = "barkod_kayitlari"


def _assert_child_table_exists(doc, fieldname: str):
    """Ensure the table field exists on Calisma Karti."""
    f = doc.meta.get_field(fieldname)
    if not f or f.fieldtype != "Table":
        frappe.throw(
            _("Child table alanı bulunamadı: {0}").format(fieldname),
            frappe.ValidationError,
        )


def _normalize_dt(val: str | None) -> str | None:
    v = (val or "").strip()
    return v or None


def _normalize_user(val: str | None) -> str | None:
    v = (val or "").strip()
    return v or None


def _get_doc_for_qc_write(name: str):
    """Get Calisma Karti and enable ignore_permissions after role gate.

    Rationale:
    - QC users may not have write permission to parent doc or child tables.
    - We enforce role gate first, then bypass permissions safely.
    """
    _require_qc_role()
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")
    doc.flags.ignore_permissions = True
    return doc

def _get_doc_for_idc_write(name: str):
    """Get Calisma Karti for IDC write operations.

    IDC measurements can be entered by:
    - The operator assigned to this card
    - QC users / System Manager (full access)
    """
    from ._helpers import require_my_employee, is_system_manager, is_quality_user
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")
    if not (is_system_manager() or is_quality_user()):
        emp = require_my_employee()
        if doc.operator != emp:
            frappe.throw(_("Bu çalışma kartı için yetkiniz yok."), frappe.PermissionError)
    doc.flags.ignore_permissions = True
    return doc

# Raw Material + IDC Filter Helpers for Calisma Karti.

def _get_work_order_name_from_calisma_karti(doc) -> str:
    """Resolve Work Order name from Calisma Karti fields."""
    # You used doc.custom_work_order in UI; keep fallback for different field names.
    wo = (getattr(doc, "custom_work_order", None) or getattr(doc, "work_order", None) or "").strip()
    if not wo:
        frappe.throw(_("Çalışma Kartı üzerinde Work Order bulunamadı."), frappe.ValidationError)
    return wo


def _get_bom_no_from_work_order(wo_name: str) -> str:
    """Return bom_no from Work Order."""
    bom_no = (frappe.db.get_value("Work Order", wo_name, "bom_no") or "").strip()
    if not bom_no:
        frappe.throw(_("Work Order üzerinde BOM bulunamadı (bom_no boş)."), frappe.ValidationError)
    return bom_no


def _assert_idc_item_allowed_for_work_order(doc, item_code: str):
    """Validate IDC item belongs to WO BOM and matches required Item constraints."""
    code = (item_code or "").strip()
    if not code:
        frappe.throw(_("Item Code boş olamaz."), frappe.ValidationError)

    wo_name = _get_work_order_name_from_calisma_karti(doc)
    bom_no = _get_bom_no_from_work_order(wo_name)

    # 1) Item constraints
    ok_item = frappe.db.get_value(
        "Item",
        {
            "name": code,
            "item_group": ["in", ["120-IDC Connector", "110-Connector"]],
            "custom_ara_malzeme_grubu": "HAMMADDE",
        },
        "name"
    )
    if not ok_item:
        frappe.throw(
            _("Seçilen IDC kodu uygun değil. (item_group=120-IDC Connector veya 110-Connector, custom_ara_malzeme_grubu=HAMMADDE olmalı)"),
            frappe.ValidationError,
        )

    # 2) Must exist in the WO's BOM items
    ok_bom = frappe.db.exists(
        "BOM Item",
        {
            "parent": bom_no,
            "parenttype": "BOM",
            "parentfield": "items",
            "item_code": code,
        },
    )
    if not ok_bom:
        frappe.throw(
            _("Bu IDC kodu Work Order BOM içinde yok. Başka bir ürüne ait IDC eklenemez."),
            frappe.ValidationError,
        )

# Raw Material + IDC Filter Finder for Calisma Karti

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_allowed_idc_items(doctype, txt, searchfield, start, page_len, filters):
    """Link field search for allowed IDC items for given Calisma Karti.

    Open to any user who has read access to the given Calisma Karti.
    filters expected:
      - calisma_karti: Calisma Karti name
    """
    calisma_karti = (filters or {}).get("calisma_karti")
    if not calisma_karti:
        return []

    ck = frappe.get_doc("Calisma Karti", calisma_karti)
    ck.check_permission("read")

    wo_name = _get_work_order_name_from_calisma_karti(ck)
    bom_no = _get_bom_no_from_work_order(wo_name)

    txt = (txt or "").strip()

    # Join BOM Item -> Item and apply constraints + BOM scope
    return frappe.db.sql(
        """
        select i.name, i.item_name
        from `tabBOM Item` bi
        inner join `tabItem` i on i.name = bi.item_code
        where
            bi.parent = %(bom_no)s
            and bi.parenttype = 'BOM'
            and bi.parentfield = 'items'
            and i.item_group in ('120-IDC Connector', '110-Connector')
            and ifnull(i.custom_ara_malzeme_grubu, '') = 'HAMMADDE'
            and (
                i.name like %(like)s
                or i.item_name like %(like)s
            )
        order by i.name asc
        limit %(start)s, %(page_len)s
        """,
        {
            "bom_no": bom_no,
            "like": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )

# ---------- IDC CRUD ----------

@frappe.whitelist()
def add_idc_olcumu(name: str, item_code: str, yukseklik_mm: float = 0, cekme_n: float = 0,
                  olcum_tarihi: str | None = None, olcumu_giren: str | None = None):
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, IDC_CHILD_FIELDNAME)

    if not (item_code or "").strip():
        frappe.throw(_("Item Code boş olamaz."))

    _assert_idc_item_allowed_for_work_order(doc, item_code)

    row = {
        "item_code": (item_code or "").strip(),
        "yukseklik_mm": float(yukseklik_mm or 0),
        "cekme_n": float(cekme_n or 0),
        "olcum_tarihi": frappe.utils.now_datetime(),
        "olcumu_giren": _session_employee_name_or_throw(),  # Employee.name e.g. HR-EMP-00001
    }

    doc.append(IDC_CHILD_FIELDNAME, row)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}


@frappe.whitelist()
def update_idc_olcumu(name: str, rowname: str, item_code: str, yukseklik_mm: float = 0, cekme_n: float = 0,
                      olcum_tarihi: str | None = None, olcumu_giren: str | None = None):
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, IDC_CHILD_FIELDNAME)

    if not (item_code or "").strip():
        frappe.throw(_("Item Code boş olamaz."))

    _assert_idc_item_allowed_for_work_order(doc, item_code)

    rows = doc.get(IDC_CHILD_FIELDNAME) or []
    target = next((r for r in rows if r.name == rowname), None)
    if not target:
        frappe.throw(_("IDC ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    target.item_code = (item_code or "").strip()
    target.yukseklik_mm = float(yukseklik_mm or 0)
    target.cekme_n = float(cekme_n or 0)

    target.olcum_tarihi = frappe.utils.now_datetime()
    target.olcumu_giren = _session_employee_name_or_throw()

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}


@frappe.whitelist()
def delete_idc_olcumu(name: str, rowname: str):
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, IDC_CHILD_FIELDNAME)

    rows = doc.get(IDC_CHILD_FIELDNAME) or []
    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)

    if idx is None:
        frappe.throw(_("IDC ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    rows.pop(idx)
    doc.set(IDC_CHILD_FIELDNAME, rows)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}


# ---------- Barkod CRUD ----------

@frappe.whitelist()
def add_barkod_kaydi(
    name: str,
    barcode: str,
    olcum_tarihi: str | None = None,
    olcumu_giren: str | None = None,
):
    doc = _get_doc_for_qc_write(name)
    _assert_child_table_exists(doc, BARKOD_CHILD_FIELDNAME)

    bc = (barcode or "").strip()
    if not bc:
        frappe.throw(_("Barkod boş olamaz."))

    row = {
        "barcode": bc,
        "olcum_tarihi": frappe.utils.now_datetime(),
        "olcumu_giren": _session_employee_name_or_throw(),
    }

    doc.append(BARKOD_CHILD_FIELDNAME, row)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}


@frappe.whitelist()
def update_barkod_kaydi(
    name: str,
    rowname: str,
    barcode: str,
    olcum_tarihi: str | None = None,
    olcumu_giren: str | None = None,
):
    doc = _get_doc_for_qc_write(name)
    _assert_child_table_exists(doc, BARKOD_CHILD_FIELDNAME)

    rows = doc.get(BARKOD_CHILD_FIELDNAME) or []
    target = next((r for r in rows if r.name == rowname), None)

    if not target:
        frappe.throw(_("Barkod satırı bulunamadı (rowname: {0}).").format(rowname))

    bc = (barcode or "").strip()
    if not bc:
        frappe.throw(_("Barkod boş olamaz."))

    target.barcode = bc
    target.olcum_tarihi = frappe.utils.now_datetime()
    target.olcumu_giren = _session_employee_name_or_throw()

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}


@frappe.whitelist()
def delete_barkod_kaydi(name: str, rowname: str):
    doc = _get_doc_for_qc_write(name)
    _assert_child_table_exists(doc, BARKOD_CHILD_FIELDNAME)

    rows = doc.get(BARKOD_CHILD_FIELDNAME) or []
    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)

    if idx is None:
        frappe.throw(_("Barkod satırı bulunamadı (rowname: {0}).").format(rowname))

    rows.pop(idx)
    doc.set(BARKOD_CHILD_FIELDNAME, rows)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}


@frappe.whitelist()
def get_qc_templates_for_ck(ck_name):
    """Get available quality inspection templates for a Calisma Karti
    1. From Item master
    2. From Job Card (Operation)
    3. Wildcard matching item code
    """
    if not ck_name:
        return {"templates": [], "default_template": None, "item_code": None}

    ck = frappe.get_doc("Calisma Karti", ck_name)
    if not ck.is_karti:
        return {"templates": [], "default_template": None, "item_code": None}

    # Job Card üzerinden production_item ve template'i alalım
    job_card = frappe.get_doc("Job Card", ck.is_karti)
    item_code = job_card.production_item
    
    unique_templates = set()

    # 1. Template from Item master (Default)
    default_template = frappe.db.get_value("Item", item_code, "quality_inspection_template")
    if default_template:
        unique_templates.add(default_template)

    # 2. Template from Job Card (Operation)
    jc_template = job_card.quality_inspection_template
    if jc_template:
        unique_templates.add(jc_template)
    
    # 3. Search for templates that might mention the item code in their name
    wildcard_templates = frappe.get_all(
        "Quality Inspection Template",
        filters={"name": ["like", f"%{item_code}%"]},
        pluck="name"
    )
    for t in wildcard_templates:
        unique_templates.add(t)

    result = [{"name": t_name} for t_name in sorted(list(unique_templates))]

    return {
        "templates": result,
        "default_template": default_template,
        "item_code": item_code
    }


@frappe.whitelist()
def get_template_details(template_name):
    """
    Returns the parameters of a specific Quality Inspection Template.
    """
    template = frappe.get_doc("Quality Inspection Template", template_name)
    params = []
    for p in template.item_quality_inspection_parameter:
        params.append({
            "specification": p.specification,
            "value": p.value,
            "numeric": p.numeric,
            "min_value": p.min_value,
            "max_value": p.max_value
        })
    return params


@frappe.whitelist()
def submit_kta_quality_inspection(ck_name, template_name, readings, sample_size=1, intent="approve"):
    """
    Creates and submits a Quality Inspection (MAT-QA) linked to the Calisma Karti.

    intent: "approve" → kalite_kontrol = "Onaylandı" (if QA Accepted)
            "reject"  → all readings forced Rejected, kalite_kontrol = "Reddedildi"
    sample_size: numune sayısı (kullanıcı tarafından girilir, default 1)
    """
    ck = frappe.get_doc("Calisma Karti", ck_name)
    _require_qc_role()

    if not ck.is_karti:
        frappe.throw(_("Çalışma Kartı bir İş Kartı (Job Card) ile bağlantılı değil."))

    # Create Quality Inspection
    qa = frappe.new_doc("Quality Inspection")
    qa.report_date = frappe.utils.nowdate()
    qa.inspection_type = "In Process"
    qa.reference_type = "Job Card"
    qa.reference_name = ck.is_karti
    qa.item_code = frappe.db.get_value("Job Card", ck.is_karti, "production_item")
    qa.quality_inspection_template = template_name
    qa.inspected_by = frappe.session.user
    qa.sample_size = int(sample_size or 1)

    # Parse readings if it arrives as a JSON string (HTTP form data)
    if isinstance(readings, str):
        readings = json.loads(readings)

    is_reject = (intent or "approve") == "reject"

    # Add readings
    # ERPNext Quality Inspection Reading fields:
    #   numeric=True  → reading_1 (and reading_2..10 for multiple samples)
    #   numeric=False → reading_value
    for r in readings:
        is_numeric = bool(r.get("numeric"))
        raw_val = str(r.get("reading_1") or r.get("reading_value") or "").strip()
        # If intent=reject, force all readings to Rejected regardless of what frontend sent
        row_status = "Rejected" if is_reject else (r.get("status") or "Accepted")
        row = {
            "specification": r.get("specification"),
            "numeric": 1 if is_numeric else 0,
            # manual_inspection=1: prevent ERPNext from auto-overriding status
            # on submit (it would compare reading_1 against min/max and force "Rejected")
            "manual_inspection": 1,
            "status": row_status,
            "min_value": r.get("min_value"),
            "max_value": r.get("max_value"),
        }
        if is_numeric:
            row["reading_1"] = raw_val
        else:
            row["reading_value"] = raw_val
        qa.append("readings", row)

    qa.insert(ignore_permissions=True)
    qa.submit()

    # Determine final kalite_kontrol status for Calisma Karti:
    #   intent=reject  → always "Reddedildi" (regardless of individual reading outcomes)
    #   intent=approve → "Onaylandı" if QA Accepted, else "Onay Bekliyor"
    if is_reject:
        final_qc_status = "Reddedildi"
    else:
        final_qc_status = "Onaylandı" if qa.status == "Accepted" else "Onay Bekliyor"

    # Update Calisma Karti
    ck.db_set("quality_inspection", qa.name)
    ck.db_set("kalite_kontrol", final_qc_status)

    # If rejected, also update durum field
    if final_qc_status == "Reddedildi":
        ck.db_set("durum", "Reddedildi", update_modified=True)

    # Notify frontend
    publish_calisma_karti_changed(ck_name, reason=f"qc_submit:{qa.name}")

    return {
        "status": "success",
        "quality_inspection": qa.name,
        "qc_status": final_qc_status
    }


