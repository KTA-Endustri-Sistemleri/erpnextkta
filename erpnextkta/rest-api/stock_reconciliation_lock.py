# erpnextkta/stock_locks.py
from __future__ import annotations

import frappe

# Yalnızca bu rol kilidi bypass edebilir
LOCK_BYPASS_ROLES = {"Stock Reconciliation Manager"}


def _can_bypass() -> bool:
    return bool(set(frappe.get_roles(frappe.session.user)) & LOCK_BYPASS_ROLES)


def _get_ancestors_including_self(warehouse: str) -> set[str]:
    """
    ERPNext Warehouse tree (nested set) üzerinden:
    warehouse + tüm parent'larını döndürür.
    Parent'ta kilit varsa child'lar da kilitlenmiş olur.
    """
    node = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"], as_dict=True)
    if not node:
        return {warehouse}

    return set(
        frappe.db.get_all(
            "Warehouse",
            filters={"lft": ["<=", node.lft], "rgt": [">=", node.rgt]},
            pluck="name",
        )
    )


def _stock_entry_touched_warehouses(doc) -> set[str]:
    """
    Stock Entry dokunduğu depolar:
    - s_warehouse (source)
    - t_warehouse (target)
    """
    wh: set[str] = set()
    for it in doc.get("items") or []:
        s_wh = it.get("s_warehouse")
        t_wh = it.get("t_warehouse")
        if s_wh:
            wh.add(s_wh)
        if t_wh:
            wh.add(t_wh)
    return wh


def _find_draft_reco_lock_by_set_warehouse(warehouses_to_check: set[str]) -> tuple[str, str] | None:
    """
    SADECE Draft Stock Reconciliation'ları (docstatus=0) kontrol eder.
    Kilit anahtarı: sr.set_warehouse (mandatory)
    Dönerse: (sr_name, locked_warehouse)
    """
    if not warehouses_to_check:
        return None

    row = frappe.db.sql(
        """
        select sr.name, sr.set_warehouse
        from `tabStock Reconciliation` sr
        where sr.docstatus = 0
          and sr.set_warehouse in %(whs)s
        limit 1
        """,
        {"whs": tuple(warehouses_to_check)},
        as_dict=True,
    )

    if not row:
        return None

    return row[0]["name"], row[0]["set_warehouse"]


def validate_stock_entry_warehouse_lock(doc, method=None):
    """
    Stock Entry kaydedilirken:
    - Dokunulan depoların (s_warehouse/t_warehouse) kendisi + parent'ları kontrol edilir.
    - Bu set içinde Draft Stock Reconciliation (set_warehouse) varsa bloklar.
    - Yalnızca 'Stock Reconciliation Manager' bypass edebilir.
    """
    if _can_bypass():
        return

    touched = _stock_entry_touched_warehouses(doc)

    check_set: set[str] = set()
    for w in touched:
        check_set |= _get_ancestors_including_self(w)

    found = _find_draft_reco_lock_by_set_warehouse(check_set)
    if found:
        sr_name, locked_wh = found
        frappe.throw(
            f"'{locked_wh}' için sayım açık (Draft Stock Reconciliation: {sr_name}). "
            f"Bu nedenle Stock Entry işlemi yapılamaz."
        )


def validate_unique_draft_stock_reco_per_set_warehouse(doc, method=None):
    """
    Aynı set_warehouse için 2. bir Draft Stock Reconciliation açılmasını engeller.
    - Sadece docstatus=0 iken kontrol eder.
    - set_warehouse mandatory olduğundan boş beklenmez.
    """
    if doc.docstatus != 0:
        return

    set_wh = getattr(doc, "set_warehouse", None)
    if not set_wh:
        return

    existing = frappe.db.exists(
        "Stock Reconciliation",
        {
            "docstatus": 0,
            "set_warehouse": set_wh,
            "name": ["!=", doc.name],
        },
    )

    if existing:
        frappe.throw(
            f"'{set_wh}' için zaten açık (Draft) bir Stock Reconciliation var: {existing}. "
            f"Lütfen önce onu Submit/Cancel yapın veya o belge üzerinden devam edin."
        )