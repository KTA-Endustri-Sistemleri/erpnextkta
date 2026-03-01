# English comments as requested

from __future__ import annotations

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
                from kta_calisma_karti.doctype.calisma_karti.calisma_karti import STATU_HARITASI
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
    ok_item = frappe.db.exists(
        "Item",
        {
            "name": code,
            "item_group": "120-IDC Connector",
            "custom_ara_malzeme_grubu": "HAMMADDE",
        },
    )
    if not ok_item:
        frappe.throw(
            _("Seçilen IDC kodu uygun değil. (item_group=120-IDC Connector, custom_ara_malzeme_grubu=HAMMADDE olmalı)"),
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
            and i.item_group = '120-IDC Connector'
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

    # If you want "recorded at insert time only", do NOT overwrite these on update:
    target.olcum_tarihi = frappe.utils.now_datetime()
    target.olcumu_giren = _session_employee_name_or_throw()

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
    doc.save()

    return {"status": "success"}
