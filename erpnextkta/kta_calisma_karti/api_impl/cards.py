# English comments as requested

from __future__ import annotations

import frappe
from frappe import _
from collections import defaultdict

from ._helpers import (
    first_child_table,
    is_system_manager,
    is_quality_user,
    require_my_employee,
)

def _attach_customer_groups(rows):
    """Attach customer_group(s) for each row (based on urun_kodu). Always adds keys."""
    item_codes = sorted({r.get("urun_kodu") for r in rows if r.get("urun_kodu")})
    groups_by_item = defaultdict(list)

    if item_codes:
        details = frappe.get_all(
            "Item Customer Detail",
            filters={
                "parenttype": "Item",
                "parent": ["in", item_codes],
            },
            fields=["parent", "customer_group"],
        )
        for d in details:
            cg = d.get("customer_group")
            if cg and cg not in groups_by_item[d["parent"]]:
                groups_by_item[d["parent"]].append(cg)

    for r in rows:
        code = r.get("urun_kodu")
        cgs = groups_by_item.get(code, [])
        r["customer_groups"] = cgs                  # her zaman var: list
        r["customer_group"] = cgs[0] if cgs else None  # her zaman var: str|None

    return rows

@frappe.whitelist()
def get_my_calisma_kartlari(order_by=None, start=0, page_length=200):
    """Return assigned Calisma Karti rows for list UI (with customer_group info)."""

    fields = [
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
        "creation",
        "kalite_kontrol",
    ]

    allowed = {
        "modified_desc": "modified desc",
        "modified_asc": "modified asc",
        "creation_desc": "creation desc",
        "creation_asc": "creation asc",
        "name_asc": "name asc",
        "name_desc": "name desc",
    }
    order_by = allowed.get(order_by or "modified_desc", "modified desc")
    start = int(start or 0)
    page_length = int(page_length or 200)

    if is_system_manager():
        rows = frappe.get_all("Calisma Karti", fields=fields, order_by=order_by, limit_start=start,limit_page_length=page_length,)
        rows = _attach_customer_groups(rows)
        if customer_group:
            rows = [r for r in rows if r.get("customer_group") == customer_group or customer_group in (r.get("customer_groups") or [])]
        return rows

    if is_quality_user():
        rows = frappe.get_all("Calisma Karti", fields=fields, order_by=order_by, limit_start=start,limit_page_length=page_length,)
        rows = _attach_customer_groups(rows)
        if customer_group:
            rows = [r for r in rows if r.get("customer_group") == customer_group or customer_group in (r.get("customer_groups") or [])]
        return rows

    emp = require_my_employee()
    rows = frappe.get_all(
        "Calisma Karti",
        filters={"operator": emp},
        fields=fields,
        order_by=order_by,
        limit_start=start,
        limit_page_length=page_length,
    )
    rows = _attach_customer_groups(rows)
    if customer_group:
        rows = [r for r in rows if r.get("customer_group") == customer_group or customer_group in (r.get("customer_groups") or [])]
    return rows

@frappe.whitelist()
def get_calisma_karti_detail(name: str):
    """Return detail payload for Vue UI.

    - If System Manager: allow any card
    - Else: only allow if operator == current user's Employee
    """

    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    if not (is_system_manager() or is_quality_user()):
        emp = require_my_employee()
        if doc.operator != emp:
            frappe.throw(_("Bu çalışma kartını görüntüleme yetkiniz yok."), frappe.PermissionError)

    hurdalar = first_child_table(doc, ["hurdalar", "hurda", "calisma_karti_hurda"])
    duruslar = first_child_table(doc, ["duruslar", "durus", "operasyon_duruslari"])
    idc_olcumleri = first_child_table(doc, ["idc_olcumleri", "idc_olcumleri", "calisma_karti_idc_olcumleri"])
    barkod_kayitlari = first_child_table(doc, ["barkod_kayitlari", "barkod_kayitlari", "calisma_karti_barkod_kayitlari"])

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
        "idc_olcumleri": idc_olcumleri,
        "barkod_kayitlari": barkod_kayitlari,
        "tamamlanan_miktar": float(doc.tamamlanan_miktar or 0),
        "kalite_kontrol": doc.kalite_kontrol,
        "creation": doc.creation,
    }
