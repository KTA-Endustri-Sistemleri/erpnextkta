# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

from ._helpers import (
    first_child_table,
    is_system_manager,
    is_quality_user,
    require_my_employee,
)

@frappe.whitelist()
def get_my_calisma_kartlari():
    """Return assigned Calisma Karti rows for list UI."""

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
        "kalite_kontrol",
    ]

    if is_system_manager():
        return frappe.get_all(
            "Calisma Karti",
            fields=fields,
            order_by="modified desc",
            limit_page_length=200,
        )
    if is_quality_user():
        return frappe.get_all(
            "Calisma Karti",
            fields=fields,
            order_by="modified desc",
            limit_page_length=200,
        )

    emp = require_my_employee()
    return frappe.get_all(
        "Calisma Karti",
        filters={"operator": emp},
        fields=fields,
        order_by="modified desc",
        limit_page_length=200,
    )

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
    }
