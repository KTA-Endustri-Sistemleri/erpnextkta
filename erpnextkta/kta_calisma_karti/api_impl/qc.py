# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

# -----------------------------
# QC Update (Role-gated)
# -----------------------------

QC_ALLOWED_ROLES = {"KTA Kalite Kullanıcısı", "Quality Manager", "System Manager"}
QC_ALLOWED_VALUES = {"Onay Bekliyor", "Onaylandı", "Reddedildi"}

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


# ---------- IDC CRUD ----------

@frappe.whitelist()
def add_idc_olcumu(
    name: str,
    item_code: str,
    yukseklik_mm: float,
    cekme_n: float,
    olcum_tarihi: str | None = None,
    olcumu_giren: str | None = None,
):
    doc = _get_doc_for_qc_write(name)
    _assert_child_table_exists(doc, IDC_CHILD_FIELDNAME)

    if not (item_code or "").strip():
        frappe.throw(_("Item Code boş olamaz."))

    row = {
        "item_code": (item_code or "").strip(),
        "yukseklik_mm": float(yukseklik_mm or 0),
        "cekme_n": float(cekme_n or 0),
        "olcum_tarihi": _normalize_dt(olcum_tarihi),
        # Default to current user if not provided
        "olcumu_giren": _normalize_user(olcumu_giren) or frappe.session.user,
    }

    doc.append(IDC_CHILD_FIELDNAME, row)
    doc.save()

    return {"status": "success"}


@frappe.whitelist()
def update_idc_olcumu(
    name: str,
    rowname: str,
    item_code: str,
    yukseklik_mm: float,
    cekme_n: float,
    olcum_tarihi: str | None = None,
    olcumu_giren: str | None = None,
):
    doc = _get_doc_for_qc_write(name)
    _assert_child_table_exists(doc, IDC_CHILD_FIELDNAME)

    rows = doc.get(IDC_CHILD_FIELDNAME) or []
    target = next((r for r in rows if r.name == rowname), None)

    if not target:
        frappe.throw(_("IDC ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    if not (item_code or "").strip():
        frappe.throw(_("Item Code boş olamaz."))

    target.item_code = (item_code or "").strip()
    target.yukseklik_mm = float(yukseklik_mm or 0)
    target.cekme_n = float(cekme_n or 0)
    target.olcum_tarihi = _normalize_dt(olcum_tarihi)
    target.olcumu_giren = _normalize_user(olcumu_giren) or frappe.session.user

    doc.save()
    return {"status": "success"}


@frappe.whitelist()
def delete_idc_olcumu(name: str, rowname: str):
    doc = _get_doc_for_qc_write(name)
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
        "olcum_tarihi": _normalize_dt(olcum_tarihi),
        "olcumu_giren": _normalize_user(olcumu_giren) or frappe.session.user,
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
    target.olcum_tarihi = _normalize_dt(olcum_tarihi)
    target.olcumu_giren = _normalize_user(olcumu_giren) or frappe.session.user

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