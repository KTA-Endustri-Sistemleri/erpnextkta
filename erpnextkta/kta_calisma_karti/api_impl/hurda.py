# English comments as requested

from __future__ import annotations

import frappe
from frappe import _

from ._helpers import (
    HURDA_PARENT_COST_CENTER,
    get_child_table_fieldname,
    is_system_manager,
    require_my_employee,
    get_allowed_items_with_groups,
)

@frappe.whitelist()
def get_hurda_nedeni_options(parent_cost_center: str = HURDA_PARENT_COST_CENTER):
    """Return cost center names whose parent_cost_center matches given value."""

    rows = frappe.get_all(
        "Cost Center",
        filters={"parent_cost_center": parent_cost_center, "is_group": 0},
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )
    return [r["name"] for r in rows]

def _assert_can_write_on_doc(doc):
    """Non-System Manager must be operator to modify."""
    if is_system_manager():
        return
    emp = require_my_employee()
    if doc.operator != emp:
        frappe.throw(_("Bu çalışma kartını düzenleme yetkiniz yok."), frappe.PermissionError)

def _assert_cost_center_allowed(hurda_nedeni: str):
    ok = frappe.db.exists(
        "Cost Center",
        {"name": hurda_nedeni, "parent_cost_center": HURDA_PARENT_COST_CENTER},
    )
    if not ok:
        frappe.throw(_("Hurda Nedeni geçersiz. Lütfen listeden seçin."))


# -----------------------------
# NEW: BOM operation based filter
# -----------------------------

def _assert_hurda_item_allowed_for_operation(doc, parca_no: str):
    """Reject if parca_no is not in allowed BOM items for Job Card operation."""
    code = (parca_no or "").strip()
    if not code:
        frappe.throw(_("Parça Numarası (Item) boş olamaz."))

    allowed = get_allowed_items_with_groups(doc.name)
    if code not in allowed:
        frappe.throw(
            _(
                "Bu hurda parçası bu operasyon için izinli değil. "
                "Sadece BOM içinde ilgili operasyon satırındaki hammaddeler hurdaya yazılabilir."
            ),
            frappe.PermissionError,
        )

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_allowed_hurda_items(doctype, txt, searchfield, start, page_len, filters):
    """Link field search for allowed hurda items for given Calisma Karti.

    filters expected:
      - calisma_karti: Calisma Karti name
    """
    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

    calisma_karti = (filters or {}).get("calisma_karti")
    if not calisma_karti:
        return []

    ck = frappe.get_doc("Calisma Karti", calisma_karti)
    ck.check_permission("read")

    txt = (txt or "").strip()

    allowed_items = get_allowed_items_with_groups(calisma_karti)
    if not allowed_items:
        return []

    items_placeholder = ", ".join(["%s"] * len(allowed_items))
    return frappe.db.sql(
        f"""
        SELECT name, item_name, item_group
        FROM `tabItem`
        WHERE
            name IN ({items_placeholder})
            AND disabled = 0
            AND (name LIKE %s OR item_name LIKE %s)
        ORDER BY name ASC
        LIMIT %s, %s
        """,
        tuple(allowed_items) + (f"%{txt}%", f"%{txt}%", int(start), int(page_len)),
    )

def _get_item_wo_defaults(ck_doc, item_code):
    """Fetch source_warehouse and stock_uom for item from Work Order required_items."""
    if not ck_doc.custom_work_order:
        return None, None

    # Get from Work Order required_items
    wo_item = frappe.db.get_value(
        "Work Order Item",
        {"parent": ck_doc.custom_work_order, "item_code": item_code},
        ["source_warehouse", "stock_uom"],
        as_dict=True
    )
    
    src_wh = None
    stock_uom = None
    
    if wo_item:
        src_wh = wo_item.source_warehouse
        stock_uom = wo_item.stock_uom

    # Fallback for UOM
    if not stock_uom:
        stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")

    # Fallback for Warehouse: if not in WO row, check WO header, then Item default
    if not src_wh:
        src_wh = frappe.db.get_value("Work Order", ck_doc.custom_work_order, "source_warehouse")
    
    if not src_wh:
        src_wh = frappe.db.get_value("Item", item_code, "default_warehouse")

    return src_wh, stock_uom

def _get_or_create_scrap_se(ck_name: str, ck_doc=None):
    """
    Get or create a single Draft 'Scrap for Manufacturing' Stock Entry for this card.
    
    KEY FIX: We read scrap_stock_entry directly from DB (not from in-memory doc)
    to avoid stale reads across multiple API calls.
    
    Returns (se_doc, se_name, is_new) tuple.
    se_name will be None if the SE is brand new (not yet inserted).
    """
    # Always re-read from DB to avoid stale cache
    se_name = frappe.db.get_value("Calisma Karti", ck_name, "scrap_stock_entry")
    
    if se_name:
        # Validate it still exists and is Draft
        se_doc = None
        try:
            se_doc = frappe.get_doc("Stock Entry", se_name)
            if se_doc.docstatus != 0:
                se_doc = None  # Was submitted/cancelled, create fresh
        except frappe.DoesNotExistError:
            se_doc = None
        
        if se_doc:
            return se_doc, se_name, False
    
    # No valid SE found on this card.
    if ck_doc is None:
        ck_doc = frappe.get_doc("Calisma Karti", ck_name)
    
    # User requested: One SE per Card. So we don't search for other cards' SEs here.
    
    # Return a new (unsaved) SE doc. Caller must append items THEN insert.
    company = frappe.db.get_value("Job Card", ck_doc.is_karti, "company") if ck_doc.is_karti else frappe.defaults.get_user_default("Company")
    
    se_doc = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Scrap for Manufacturing",
        "purpose": "Material Issue",
        "work_order": ck_doc.custom_work_order,
        "company": company,
        "remarks": f"Calisma Karti: {ck_name}",
    })
    
    # is_new=True means caller must insert (not save) after appending items
    return se_doc, None, True


def _get_expense_account():
    account = frappe.db.get_single_value("KTA Calisma Karti Settings", "hurda_gider_hesabi")
    if not account:
        frappe.throw(_("Lütfen KTA Çalışma Kartı Ayarları panelinden 'Hurda Gider Hesabı' bilgisini tanımlayın."), title=_("Ayarlar Eksik"))
    return account


def sync_stock_entry_to_calisma_karti(se_doc, method=None):
    """Reflect manual changes from Stock Entry back to all linked Calisma Karti."""
    if frappe.flags.syncing_hurda_from_card:
        return
    
    if se_doc.stock_entry_type != "Scrap for Manufacturing":
        return

    # Find ALL linked Calisma Karti records
    ck_list = frappe.get_all("Calisma Karti", filters={"scrap_stock_entry": se_doc.name, "docstatus": ["<", 2]}, fields=["name", "custom_work_order"])
    
    if not ck_list and se_doc.work_order:
        # Try to find card by WO if no direct link
        ck_name = frappe.db.get_value("Calisma Karti", {"custom_work_order": se_doc.work_order, "docstatus": ["<", 2]}, "name")
        if ck_name:
            ck_list = [{"name": ck_name, "custom_work_order": se_doc.work_order}]

    if not ck_list:
        return

    # Restore work_order field if ERPNext validation cleared it
    # ERPNext clears work_order on SE when job_card is not linked — we force it back via raw DB write
    linked_wo = (ck_list[0].get("custom_work_order") or "").strip()
    if linked_wo and not se_doc.work_order:
        frappe.db.set_value("Stock Entry", se_doc.name, "work_order", linked_wo, update_modified=False)

    frappe.flags.syncing_hurda_from_se = True
    try:
        # Collect all scrap items from SE
        se_scrap_items = [d for d in se_doc.items if getattr(d, "is_scrap_item", 0)]
        se_scrap_ids = [d.name for d in se_scrap_items]

        for ck_row in ck_list:
            ck_doc = frappe.get_doc("Calisma Karti", ck_row.name)
            child_fieldname = get_child_table_fieldname(ck_doc, "Calisma Karti Hurda")
            ck_hurdalar = ck_doc.get(child_fieldname) or []
            
            changed = False
            # 1. Update existing rows in this card
            for h in ck_hurdalar:
                if h.stock_entry_detail_id and h.stock_entry_detail_id in se_scrap_ids:
                    se_row = next(d for d in se_scrap_items if d.name == h.stock_entry_detail_id)
                    if h.miktar != se_row.qty or h.parca_no != se_row.item_code:
                        h.miktar = se_row.qty
                        h.parca_no = se_row.item_code
                        h.birim = se_row.uom
                        h.depo = se_row.s_warehouse
                        h.hurda_nedeni = se_row.cost_center
                        changed = True
            
            # 2. Deletions: if Card row has ID but it's gone from SE
            valid_hurdalar = [r for r in ck_hurdalar if (not r.stock_entry_detail_id) or (r.stock_entry_detail_id in se_scrap_ids)]
            if len(valid_hurdalar) != len(ck_hurdalar):
                ck_doc.set(child_fieldname, valid_hurdalar)
                changed = True
            
            if ck_doc.scrap_stock_entry != se_doc.name:
                ck_doc.scrap_stock_entry = se_doc.name
                changed = True

            if changed:
                ck_doc.flags.ignore_validate_update_after_submit = True
                ck_doc.save(ignore_permissions=True)
    finally:
        frappe.flags.syncing_hurda_from_se = False

def sync_calisma_karti_hurdalar_to_se(ck_doc, method=None):
    """
    Triggered on Calisma Karti on_update.
    """
    # Skip if triggered by our own SE sync
    if frappe.flags.syncing_hurda_from_card or frappe.flags.syncing_hurda_from_se:
        return

    # Check if we have any hurdalar rows. If none, nothing to sync.
    child_fieldname = get_child_table_fieldname(ck_doc, "Calisma Karti Hurda")
    ck_hurdalar = ck_doc.get(child_fieldname) or []
    if not ck_hurdalar:
        return

    # Use _get_or_create_scrap_se for consistency
    frappe.flags.syncing_hurda_from_card = True
    try:
        se_doc, se_name, is_new = _get_or_create_scrap_se(ck_doc.name, ck_doc)
        if not se_doc:
            return

        expense_account = _get_expense_account()
        wo = ck_doc.custom_work_order

        # Build a map of SE row IDs that are still in the card
        card_se_ids = {h.stock_entry_detail_id for h in ck_hurdalar if h.stock_entry_detail_id}

        # 1. Remove SE rows whose IDs no longer appear in the card
        se_doc.items = [d for d in se_doc.items if d.name in card_se_ids or not getattr(d, "is_scrap_item", 0)]

        # 2. Update or add SE rows for each hurda row
        for h in ck_hurdalar:
            src_wh, stock_uom = _get_item_wo_defaults(ck_doc, h.parca_no)
            description = f"Çalışma Kartı Hurdası: {h.hurda_nedeni}"
            if h.aciklama:
                description += f" - {h.aciklama}"

            if h.stock_entry_detail_id:
                # Find and update existing SE row
                se_row = next((d for d in se_doc.items if d.name == h.stock_entry_detail_id), None)
                if se_row:
                    se_row.item_code = h.parca_no
                    se_row.qty = h.miktar
                    se_row.uom = stock_uom or h.birim or "Nos"
                    se_row.stock_uom = stock_uom or h.birim or "Nos"
                    se_row.s_warehouse = src_wh or h.depo
                    se_row.cost_center = h.hurda_nedeni
                    se_row.expense_account = expense_account
                    se_row.is_scrap_item = 1
                    se_row.description = description
                    continue
            
            # No ID yet — append a new row
            new_row = se_doc.append("items", {
                "item_code": h.parca_no,
                "qty": h.miktar,
                "uom": stock_uom or h.birim or "Nos",
                "stock_uom": stock_uom or h.birim or "Nos",
                "conversion_factor": 1.0,
                "s_warehouse": src_wh or h.depo,
                "cost_center": h.hurda_nedeni,
                "expense_account": expense_account,
                "is_scrap_item": 1,
                "description": description,
            })

        if se_doc.items:
            if is_new:
                se_doc.insert(ignore_permissions=True)
                se_name = se_doc.name
                frappe.db.set_value("Calisma Karti", ck_doc.name, "scrap_stock_entry", se_name, update_modified=False)
            else:
                se_doc.save(ignore_permissions=True)

            # Restore work_order in case validation cleared it
            if wo:
                frappe.db.set_value("Stock Entry", se_name, "work_order", wo, update_modified=False)
            frappe.db.commit()
            
            # Write back stock_entry_detail_ids for any newly added rows
            se_doc.reload()
            changed = False
            for h in ck_hurdalar:
                if not h.stock_entry_detail_id:
                    matched = next((d for d in se_doc.items if d.item_code == h.parca_no and abs(float(d.qty) - float(h.miktar)) < 0.001 and getattr(d, "is_scrap_item", 0)), None)
                    if matched:
                        frappe.db.set_value("Calisma Karti Hurda", h.name, "stock_entry_detail_id", matched.name, update_modified=False)
                        changed = True
            if changed:
                frappe.db.commit()
        else:
            # All items removed — delete the SE and clear the link
            try:
                se_doc.delete(ignore_permissions=True)
                frappe.db.set_value("Calisma Karti", ck_doc.name, "scrap_stock_entry", None, update_modified=False)
                frappe.db.commit()
            except Exception:
                pass

    except Exception:
        frappe.log_error(title="CK->SE SYNC ERROR", message=frappe.get_traceback())
    finally:
        frappe.flags.syncing_hurda_from_card = False


def on_stock_entry_trash(se_doc, method=None):
    """Clear link on Calisma Karti if Stock Entry is deleted."""
    if se_doc.stock_entry_type != "Scrap for Manufacturing":
        return
        
    ck_names = frappe.get_all("Calisma Karti", filters={"scrap_stock_entry": se_doc.name}, fields=["name"])
    for ck in ck_names:
        # Use set_value instead of save() to avoid timestamp mismatch errors 
        # when triggered during another document's save process or sync.
        frappe.db.set_value("Calisma Karti", ck.name, "scrap_stock_entry", None, update_modified=False)

# -----------------------------
# CRUD (updated)
# -----------------------------

@frappe.whitelist()
def add_hurda(
    name: str,
    parca_no: str,
    hurda_nedeni: str,
    miktar: float,
    aciklama: str | None = None,
):
    # 1. Load the Card and validate
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    _assert_can_write_on_doc(doc)
    _assert_cost_center_allowed(hurda_nedeni)
    _assert_hurda_item_allowed_for_operation(doc, parca_no)

    # 2. Get or create the shared SE (reads from DB to avoid stale cache)
    frappe.flags.syncing_hurda_from_card = True
    try:
        se_doc, se_name, is_new = _get_or_create_scrap_se(name, doc)

        # 3. Build new SE row
        src_wh, stock_uom = _get_item_wo_defaults(doc, parca_no)
        description = f"Çalışma Kartı Hurdası: {hurda_nedeni}"
        if aciklama:
            description += f" - {aciklama}"

        se_row = se_doc.append("items", {
            "item_code": parca_no,
            "qty": float(miktar or 0),
            "uom": stock_uom or "Nos",
            "stock_uom": stock_uom or "Nos",
            "conversion_factor": 1.0,
            "s_warehouse": src_wh,
            "cost_center": hurda_nedeni,
            "expense_account": _get_expense_account(),
            "is_scrap_item": 1,
            "description": description,
        })

        wo = doc.custom_work_order  # capture before any potential modification

        if is_new:
            # First time: insert (not save) so validation doesn't complain about empty items
            se_doc.insert(ignore_permissions=True)
            se_name = se_doc.name
            # Persist the link to DB immediately
            frappe.db.set_value("Calisma Karti", name, "scrap_stock_entry", se_name, update_modified=False)
        else:
            se_name = se_doc.name
            se_doc.save(ignore_permissions=True)

        # Force write work_order — ERPNext may clear it during validate() when job_card is not set
        if wo:
            frappe.db.set_value("Stock Entry", se_name, "work_order", wo, update_modified=False)
        frappe.db.commit()

        # 4. Reload items to get the DB-assigned row name
        se_doc.reload()
        # The last appended row should match our item
        saved_row = next(
            (d for d in sorted(se_doc.items, key=lambda x: x.idx, reverse=True)
             if d.item_code == parca_no),
            None
        )
        se_detail_id = saved_row.name if saved_row else None

        # 5. Add the child row to the Card
        child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")
        doc.reload()  # Re-read to pick up the se_name we committed earlier
        doc.append(child_fieldname, {
            "parca_no": parca_no,
            "hurda_nedeni": hurda_nedeni,
            "miktar": float(miktar or 0),
            "aciklama": aciklama,
            "birim": stock_uom or "Nos",
            "depo": src_wh,
            "stock_entry_detail_id": se_detail_id,
        })

        doc.flags.ignore_validate_update_after_submit = True
        doc.save(ignore_permissions=True)

    finally:
        frappe.flags.syncing_hurda_from_card = False

    return {"status": "success", "stock_entry": se_name}

@frappe.whitelist()
def update_hurda(
    name: str,
    rowname: str,
    parca_no: str,
    hurda_nedeni: str,
    miktar: float,
    aciklama: str | None = None,
):
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    _assert_can_write_on_doc(doc)
    _assert_cost_center_allowed(hurda_nedeni)
    _assert_hurda_item_allowed_for_operation(doc, parca_no)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    target = next((r for r in rows if r.name == rowname), None)
    if not target:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    frappe.flags.syncing_hurda_from_card = True
    try:
        # Update SE row if we have a detail ID
        se_name = frappe.db.get_value("Calisma Karti", name, "scrap_stock_entry")
        if se_name and target.stock_entry_detail_id:
            try:
                se_doc = frappe.get_doc("Stock Entry", se_name)
                se_row = next((d for d in se_doc.items if d.name == target.stock_entry_detail_id), None)
                if se_row:
                    src_wh, stock_uom = _get_item_wo_defaults(doc, parca_no)
                    se_row.item_code = parca_no
                    se_row.qty = float(miktar or 0)
                    se_row.uom = stock_uom or se_row.uom
                    se_row.stock_uom = stock_uom or se_row.stock_uom
                    se_row.s_warehouse = src_wh or se_row.s_warehouse
                    se_row.cost_center = hurda_nedeni
                    se_row.expense_account = _get_expense_account()
                    description = f"Çalışma Kartı Hurdası: {hurda_nedeni}"
                    if aciklama:
                        description += f" - {aciklama}"
                    se_row.description = description
                    se_doc.save(ignore_permissions=True)
            except Exception:
                frappe.log_error(title="HURDA UPDATE ERROR", message=frappe.get_traceback())

        # Update card row
        target.parca_no = (parca_no or "").strip()
        target.hurda_nedeni = hurda_nedeni
        target.miktar = float(miktar or 0)
        target.aciklama = aciklama

        doc.flags.ignore_validate_update_after_submit = True
        doc.save(ignore_permissions=True)

    finally:
        frappe.flags.syncing_hurda_from_card = False

    return {"status": "success"}

@frappe.whitelist()
def delete_hurda(name: str, rowname: str):
    doc = frappe.get_doc("Calisma Karti", name)
    doc.check_permission("read")

    _assert_can_write_on_doc(doc)

    child_fieldname = get_child_table_fieldname(doc, "Calisma Karti Hurda")
    rows = doc.get(child_fieldname) or []

    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)
    if idx is None:
        frappe.throw(_("Hurda satırı bulunamadı (rowname: {0}).").format(rowname))

    target = rows[idx]

    frappe.flags.syncing_hurda_from_card = True
    try:
        # Remove corresponding SE row
        se_name = frappe.db.get_value("Calisma Karti", name, "scrap_stock_entry")
        if se_name:
            try:
                se_doc = frappe.get_doc("Stock Entry", se_name)
                if se_doc.docstatus == 0:
                    if target.stock_entry_detail_id:
                        se_doc.items = [d for d in se_doc.items if d.name != target.stock_entry_detail_id]
                    else:
                        # Fallback: match by item_code and qty
                        se_doc.items = [
                            d for d in se_doc.items
                            if not (d.item_code == target.parca_no and abs(float(d.qty) - float(target.miktar)) < 0.001)
                        ]

                    if se_doc.items:
                        se_doc.save(ignore_permissions=True)
                    else:
                        # SE is now empty — delete it.
                        # The on_stock_entry_trash hook will handle clearing the link in DB safely.
                        se_doc.delete(ignore_permissions=True)
                        doc.scrap_stock_entry = None
                
                frappe.db.commit() # Ensure SE deletion/update is committed
            except Exception:
                frappe.log_error(title="HURDA DELETE ERROR", message=frappe.get_traceback())

        # Remove card row
        rows.pop(idx)
        doc.set(child_fieldname, rows)
        doc.flags.ignore_validate_update_after_submit = True
        doc.save(ignore_permissions=True)

    finally:
        frappe.flags.syncing_hurda_from_card = False

    return {"status": "success"}
