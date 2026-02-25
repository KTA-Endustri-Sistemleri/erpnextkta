# English comments as requested

from __future__ import annotations

import frappe
from frappe import _
from collections import defaultdict


def _get_customer_groups_by_item_codes(item_codes: list[str]) -> dict[str, list[str]]:
    """Return {item_code: [customer_group, ...]} using Item Customer Detail."""
    groups_by_item: dict[str, list[str]] = defaultdict(list)

    item_codes = sorted({c for c in item_codes if c})
    if not item_codes:
        return groups_by_item

    details = frappe.get_all(
        "Item Customer Detail",
        filters={
            "parenttype": "Item",
            "parent": ["in", item_codes],
        },
        fields=["parent", "customer_group"],
    )

    for d in details:
        parent = d.get("parent")
        cg = d.get("customer_group")
        if parent and cg and cg not in groups_by_item[parent]:
            groups_by_item[parent].append(cg)

    return groups_by_item


def _attach_customer_groups_to_payload(payload: dict) -> dict:
    """
    Attach customer_group(s) to a single payload based on payload["production_item"].

    Always adds:
      - payload["customer_groups"]: list[str]
      - payload["customer_group"]: str | None
    """
    item_code = payload.get("production_item")
    groups_by_item = _get_customer_groups_by_item_codes([item_code] if item_code else [])

    cgs = groups_by_item.get(item_code, []) if item_code else []
    payload["customer_groups"] = cgs
    payload["customer_group"] = cgs[0] if cgs else None
    return payload


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

    # 4) Minimal payload + customer group(s)
    payload = {
        "job_card": jc.name,
        "work_order": wo.name,
        "operation": getattr(jc, "operation", None),
        "workstation": getattr(jc, "workstation", None),
        "production_item": getattr(jc, "production_item", None),
        "for_quantity": getattr(jc, "for_quantity", None),
        "wo_status": wo.status,
        "wo_docstatus": wo.docstatus,
    }

    return _attach_customer_groups_to_payload(payload)


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
        frappe.throw(_("Bu barkoda ait bir İş Emri bulunamadı: {0}").format(barcode))

    if not wo.has_permission("read"):
        frappe.throw(_("Bu İş Emri için okuma yetkiniz yok."), frappe.PermissionError)

    if wo.docstatus != 1:
        frappe.throw(_("İş Emri onaylanmamış (docstatus != 1)."))

    if wo.status not in ("Not Started", "In Process"):
        frappe.throw(_("İş Emri açık değil. Mevcut durum: {0}").format(wo.status))

    payload = {
        "name": wo.name,
        "production_item": getattr(wo, "production_item", None),
        "qty": getattr(wo, "qty", None),
    }

    return _attach_customer_groups_to_payload(payload)
