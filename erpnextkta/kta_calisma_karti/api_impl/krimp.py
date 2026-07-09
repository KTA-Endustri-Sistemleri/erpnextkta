# English comments as requested

from __future__ import annotations
import frappe
from frappe import _
from .qc import _get_doc_for_idc_write, _assert_child_table_exists, _session_employee_name_or_throw
from .alt_operasyon import _assert_qc_unlocked

KRIMP_CHILD_FIELDNAME = "krimp_olcumleri"

def _assert_krimp_qc_unlocked(doc, krimp_row):
    """Check if the krimp row's parent alt operasyon is QC-locked."""
    ao_row_id = (krimp_row.alt_operasyon_kaydi or "").strip()
    if not ao_row_id:
        return

    ao_row = next((r for r in doc.get("alt_operasyon_kayitlari", []) if r.name == ao_row_id), None)
    if not ao_row:
        return

    _assert_qc_unlocked(doc, ao_row)

@frappe.whitelist()
def add_krimp_olcumu(name: str, payload: str | dict):
    """Add a new krimp measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, KRIMP_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    row = {
        "satir_no": payload.get("satir_no"),
        "kablo_no": payload.get("kablo_no"),
        "kontak_no": payload.get("kontak_no"),
        "kalip_no": payload.get("kalip_no"),
        "makine_pres_no": payload.get("makine_pres_no"),
        "kablo_kesiti": payload.get("kablo_kesiti"),
        "hedef_kablo_boyu": float(payload.get("hedef_kablo_boyu") or 0),
        "olculen_kablo_boyu": float(payload.get("olculen_kablo_boyu") or 0),
        "hedef_iletken_krimp_yuksekliği": float(payload.get("hedef_iletken_krimp_yuksekliği") or 0),
        "olculen_iletken_krimp_yuksekliği": float(payload.get("olculen_iletken_krimp_yuksekliği") or 0),
        "izokrimp_yuksekligi": float(payload.get("izokrimp_yuksekligi") or 0),
        "siyirma_boyu": float(payload.get("siyirma_boyu") or 0),
        "hedef_cekme_kuvveti_n": float(payload.get("hedef_cekme_kuvveti_n") or 0),
        "olculen_cekme_kuvveti_n": float(payload.get("olculen_cekme_kuvveti_n") or 0),
        "capak_boyu": float(payload.get("capak_boyu") or 0),
        "radus_mevcut": 1 if payload.get("radus_mevcut") else 0,
        "tel_kesme_mevcut": 1 if payload.get("tel_kesme_mevcut") else 0,

        "alt_operasyon_kaydi": payload.get("alt_operasyon_kaydi"),
        "is_cift_tarafli": 1 if payload.get("is_cift_tarafli") else 0,
        "yon_2_kontak_no": payload.get("yon_2_kontak_no"),
        "yon_2_kablo_kesiti": payload.get("yon_2_kablo_kesiti"),
        "yon_2_kalip_no": payload.get("yon_2_kalip_no"),
        "yon_2_makine_pres_no": payload.get("makine_pres_no"),
        "yon_2_hedef_iletken_krimp_yuksekligi": float(payload.get("yon_2_hedef_iletken_krimp_yuksekligi") or 0),
        "yon_2_olculen_iletken_krimp_yuksekligi": float(payload.get("yon_2_olculen_iletken_krimp_yuksekligi") or 0),
        "yon_2_izokrimp_yuksekligi": float(payload.get("yon_2_izokrimp_yuksekligi") or 0),
        "yon_2_siyirma_boyu": float(payload.get("yon_2_siyirma_boyu") or 0),
        "yon_2_hedef_cekme_kuvveti_n": float(payload.get("yon_2_hedef_cekme_kuvveti_n") or 0),
        "yon_2_olculen_cekme_kuvveti_n": float(payload.get("yon_2_olculen_cekme_kuvveti_n") or 0),
        "yon_2_capak_boyu": float(payload.get("yon_2_capak_boyu") or 0),
        "yon_2_radus_mevcut": 1 if payload.get("yon_2_radus_mevcut") else 0,
        "yon_2_tel_kesme_mevcut": 1 if payload.get("yon_2_tel_kesme_mevcut") else 0,

        "olcum_tarihi": frappe.utils.now_datetime(),
        "operator": _session_employee_name_or_throw(),
    }

    doc.append(KRIMP_CHILD_FIELDNAME, row)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def update_krimp_olcumu(name: str, rowname: str, payload: str | dict):
    """Update an existing krimp measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, KRIMP_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    rows = doc.get(KRIMP_CHILD_FIELDNAME) or []
    target = next((r for r in rows if r.name == rowname), None)
    if not target:
        frappe.throw(_("Krimp ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    _assert_krimp_qc_unlocked(doc, target)

    target.satir_no = payload.get("satir_no")
    target.kablo_no = payload.get("kablo_no")
    target.kontak_no = payload.get("kontak_no")
    target.kalip_no = payload.get("kalip_no")
    target.makine_pres_no = payload.get("makine_pres_no")
    target.kablo_kesiti = payload.get("kablo_kesiti")
    target.hedef_kablo_boyu = float(payload.get("hedef_kablo_boyu") or 0)
    target.olculen_kablo_boyu = float(payload.get("olculen_kablo_boyu") or 0)
    target.hedef_iletken_krimp_yuksekliği = float(payload.get("hedef_iletken_krimp_yuksekliği") or 0)
    target.olculen_iletken_krimp_yuksekliği = float(payload.get("olculen_iletken_krimp_yuksekliği") or 0)
    target.izokrimp_yuksekligi = float(payload.get("izokrimp_yuksekligi") or 0)
    target.siyirma_boyu = float(payload.get("siyirma_boyu") or 0)
    target.hedef_cekme_kuvveti_n = float(payload.get("hedef_cekme_kuvveti_n") or 0)
    target.olculen_cekme_kuvveti_n = float(payload.get("olculen_cekme_kuvveti_n") or 0)
    target.capak_boyu = float(payload.get("capak_boyu") or 0)
    target.radus_mevcut = 1 if payload.get("radus_mevcut") else 0
    target.tel_kesme_mevcut = 1 if payload.get("tel_kesme_mevcut") else 0

    if "alt_operasyon_kaydi" in payload:
        target.alt_operasyon_kaydi = payload.get("alt_operasyon_kaydi")
    
    target.is_cift_tarafli = 1 if payload.get("is_cift_tarafli") else 0
    target.yon_2_kontak_no = payload.get("yon_2_kontak_no")
    target.yon_2_kablo_kesiti = payload.get("yon_2_kablo_kesiti")
    target.yon_2_kalip_no = payload.get("yon_2_kalip_no")
    target.yon_2_makine_pres_no = payload.get("makine_pres_no")
    target.yon_2_hedef_iletken_krimp_yuksekligi = float(payload.get("yon_2_hedef_iletken_krimp_yuksekligi") or 0)
    target.yon_2_olculen_iletken_krimp_yuksekligi = float(payload.get("yon_2_olculen_iletken_krimp_yuksekligi") or 0)
    target.yon_2_izokrimp_yuksekligi = float(payload.get("yon_2_izokrimp_yuksekligi") or 0)
    target.yon_2_siyirma_boyu = float(payload.get("yon_2_siyirma_boyu") or 0)
    target.yon_2_hedef_cekme_kuvveti_n = float(payload.get("yon_2_hedef_cekme_kuvveti_n") or 0)
    target.yon_2_olculen_cekme_kuvveti_n = float(payload.get("yon_2_olculen_cekme_kuvveti_n") or 0)
    target.yon_2_capak_boyu = float(payload.get("yon_2_capak_boyu") or 0)
    target.yon_2_radus_mevcut = 1 if payload.get("yon_2_radus_mevcut") else 0
    target.yon_2_tel_kesme_mevcut = 1 if payload.get("yon_2_tel_kesme_mevcut") else 0

    target.olcum_tarihi = frappe.utils.now_datetime()
    # operator is intentionally not updated to preserve the original creator's name

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def delete_krimp_olcumu(name: str, rowname: str):
    """Delete a krimp measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, KRIMP_CHILD_FIELDNAME)

    rows = doc.get(KRIMP_CHILD_FIELDNAME) or []
    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)

    if idx is None:
        frappe.throw(_("Krimp ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    target = rows[idx]
    _assert_krimp_qc_unlocked(doc, target)

    rows.pop(idx)
    doc.set(KRIMP_CHILD_FIELDNAME, rows)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}


def normalize_kesit(val):
    if not val: return ""
    import re
    # Remove all spaces and lowercase
    s = str(val).replace(" ", "").lower().replace(".", ",")
    
    # If it contains AWG, return a special identifier 'awg:XX'
    if "awg" in s:
        match = re.search(r"(\d+)", s)
        if match:
            return f"awg:{match.group(1)}"
    
    return s

def extract_kesit_from_item(item_code):
    item_name = frappe.db.get_value("Item", item_code, "item_name")
    if not item_name: 
        item_name = item_code
    
    import re
    # 1. Try to find a number followed by a unit (most reliable)
    unit_match = re.search(r"(\d+[.,]\d+|\d+)\s*(mm|mm2|AWG)", item_name, re.IGNORECASE)
    if unit_match:
        val = unit_match.group(1).replace(".", ",")
        # Ensure it's not just the item_code repeated
        if val.replace(",", "") != str(item_code):
            return val

    # 2. If no unit found, look for decimal numbers or small integers that don't match item_code
    matches = re.findall(r"(\d+[.,]\d+|\d+)", item_name)
    for m in matches:
        # Ignore if it's the item_code
        if m.replace(".", "").replace(",", "") == str(item_code):
            continue
        
        # Cross-sections are typically small (e.g., 0.1 to 150)
        try:
            val_float = float(m.replace(",", "."))
            if 0.05 <= val_float <= 150:
                return m.replace(".", ",")
        except ValueError:
            continue
            
    return None

@frappe.whitelist()
def get_unique_kesit_list(kontak_no=None):
    """Returns a flat list of unique kesit values from KTA Krimp Book, optionally filtered by terminal (kontak_no)."""
    if kontak_no:
        res = frappe.db.sql(
            "SELECT DISTINCT kesit FROM `tabKTA Krimp Book` WHERE kontak_no = %s ORDER BY kesit ASC",
            (kontak_no,)
        )
    else:
        res = frappe.db.sql("SELECT DISTINCT kesit FROM `tabKTA Krimp Book` ORDER BY kesit ASC")
    return [r[0] for r in res if r[0]]

@frappe.whitelist()
def get_kalip_list(kontak_no=None, selected_kesit=None):
    """Returns all unique kalip (mold) values from KTA Krimp Book for a given terminal + kesit combo.
    Used to populate the kalip_no dropdown in the krimp measurement dialog.
    """
    if not kontak_no or not selected_kesit:
        return []

    # Fetch all entries for this terminal
    entries = frappe.get_all(
        "KTA Krimp Book",
        filters={"kontak_no": kontak_no},
        fields=["kesit", "kalip"],
    )

    norm_target = normalize_kesit(selected_kesit)
    kaliplar = []
    for e in entries:
        if normalize_kesit(e.kesit) == norm_target and e.kalip:
            val = str(e.kalip).strip()
            if val and val not in kaliplar:
                kaliplar.append(val)

    return sorted(kaliplar)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_krimp_items(doctype, txt, searchfield, start, page_len, filters):
    """
    Search items for Krimp measurements based on BOM items of the Work Order.
    Filtered by the selected kesit from the form with robust matching.
    """
    ck_name = (filters or {}).get("calisma_karti")
    search_type = (filters or {}).get("type")
    selected_kesit = (filters or {}).get("kablo_kesiti")
    
    if not ck_name:
        return []

    from ._helpers import get_allowed_items_with_groups
    allowed_items = get_allowed_items_with_groups(ck_name)
    if not allowed_items:
        return []

    txt = (txt or "").strip()
    like = f"%{txt}%"
    target_group = "100-Wires & Cables" if search_type == "kablo" else "150-Terminals"

    # If kesit is selected, apply robust technical filtering
    if selected_kesit:
        norm_selected = normalize_kesit(selected_kesit)
        
        if search_type == "kablo":
            item_names = frappe.get_all("Item", 
                filters={"name": ["in", allowed_items]}, 
                fields=["name", "item_name"]
            )
            
            filtered_codes = []
            for itm in item_names:
                name_to_check = (itm.item_name or itm.name).lower()
                
                if norm_selected.startswith("awg:"):
                    # AWG matching: Find the number and 'awg' anywhere in the name
                    awg_num = norm_selected.split(":")[1]
                    # Use regex to find AWG and the number, allowing any characters between them
                    import re
                    # Pattern 1: Number then AWG (e.g. "20 AWG")
                    p1 = rf"{awg_num}\s*awg"
                    # Pattern 2: AWG then Number (e.g. "AWG 20")
                    p2 = rf"awg\s*{awg_num}"
                    
                    if re.search(p1, name_to_check) or re.search(p2, name_to_check):
                        filtered_codes.append(itm.name)
                else:
                    # Regular kesit matching: handle "0,75" vs "0.75" vs "0,75mm"
                    clean_target = norm_selected.replace(",", ".")
                    clean_name = name_to_check.replace(",", ".")
                    if clean_target in clean_name:
                        filtered_codes.append(itm.name)
            
            allowed_items = filtered_codes

        elif search_type == "kontak":
            # Search in Krimp Book using normalized value
            compatible_contacts = frappe.get_all("KTA Krimp Book", 
                fields=["kontak_no", "kesit"]
            )
            
            contact_list = []
            for c in compatible_contacts:
                if normalize_kesit(c.kesit) == norm_selected:
                    contact_list.append(c.kontak_no)
            
            allowed_items = [i for i in allowed_items if i in contact_list]

    if not allowed_items:
        return []

    return frappe.db.sql(
        f"""
        SELECT name, item_name
        FROM `tabItem`
        WHERE
            name IN %(allowed_items)s
            AND item_group = %(target_group)s
            AND disabled = 0
            AND (name LIKE %(like)s OR item_name LIKE %(like)s)
        ORDER BY name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "allowed_items": tuple(allowed_items),
            "target_group": target_group,
            "like": like,
            "start": int(start),
            "page_len": int(page_len),
        },
    )

@frappe.whitelist()
def get_krimp_book_details(kablo_no=None, kontak_no=None, selected_kesit=None):
    """
    Tries to find matching values from 'KTA Krimp Book' based on Cable and Terminal.
    Uses normalization to handle variations like '20 AWG' vs 'AWG20'.
    """
    if not kontak_no:
        return {}

    norm_target = normalize_kesit(selected_kesit)
    
    if not norm_target and kablo_no:
        # If no kesit selected, try to extract from cable
        raw_val = extract_kesit_from_item(kablo_no)
        norm_target = normalize_kesit(raw_val)

    if not norm_target:
        return {}
    
    # Fetch entries for this contact and compare normalized kesit
    potential_entries = frappe.get_all("KTA Krimp Book", 
        filters={"kontak_no": kontak_no}, 
        fields=["*"]
    )
    
    book_entry = None
    for entry in potential_entries:
        if normalize_kesit(entry.kesit) == norm_target:
            book_entry = entry
            break
            
    if not book_entry:
        return {}
    
    # book_entry already found via normalized comparison above

    # Helper to parse string values to float
    def to_f(val):
        if not val: return 0.0
        try:
            # Handle ranges or multiple values like "1,20 - 1,30" by taking the first one
            s = str(val).split("-")[0].strip()
            return float(s.replace(",", "."))
        except:
            return 0.0

    return {
        "kablo_kesiti": book_entry.kesit,
        "kalip_no": book_entry.kalip,
        "hedef_iletken_krimp_yuksekliği": to_f(book_entry.krimp_yuksekligi),
        "hedef_cekme_kuvveti_n": to_f(book_entry.cekme_kuvveti),
        "izokrimp_yuksekligi": to_f(book_entry.izokrimp_yuksekligi)
    }

@frappe.whitelist()
def create_dummy_assets_helper():
    """Utility to create dummy asset data safely for testing."""
    # Try to find an existing category and location first
    cat = frappe.db.get_value("Asset Category", {}, "name")
    if not cat:
        cat = "Makineler"
        if not frappe.db.exists("Asset Category", cat):
            # We skip creating it if it requires accounts, user should have at least one
            return "ERROR: No Asset Category found. Please create one first."

    location = frappe.db.get_value("Location", {}, "name")
    if not location:
        location = "Üretim"
        if not frappe.db.exists("Location", location):
            frappe.get_doc({"doctype": "Location", "location_name": location}).insert(ignore_permissions=True)

    item_code = frappe.db.get_value("Item", {"is_fixed_asset": 1}, "name")
    if not item_code:
        return "ERROR: No Fixed Asset Item found. Please create an Item with 'Is Fixed Asset' checked."

    assets = ["Krimp Presi - 01", "Krimp Presi - 02", "Mekanik Pres - A1"]
    created_count = 0

    for name in assets:
        if not frappe.db.exists("Asset", {"asset_name": name}):
            doc = frappe.get_doc({
                "doctype": "Asset",
                "asset_name": name,
                "item_code": item_code,
                "location": location,
                "status": "Draft",
                "available_for_use_date": frappe.utils.today(),
                "gross_purchase_amount": 1000
            })
            doc.insert(ignore_permissions=True)
            created_count += 1
    
    frappe.db.commit()
    return f"SUCCESS: Created {created_count} assets."
