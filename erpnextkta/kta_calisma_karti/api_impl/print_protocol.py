import frappe

def sapma_txt(olculen, hedef):
    if not hedef: return "-"
    d = olculen - hedef
    d_str = f"{d:.3f}"
    if d_str == "0.000" or d_str == "-0.000": return "✔ OK"
    return f"+{d_str} mm" if d > 0 else f"{d_str} mm"

def sapma_class(olculen, hedef):
    if not hedef: return ""
    d = olculen - hedef
    if abs(d) < 0.001: return "ok"
    return "low" if d < 0 else "high"

def _collect_quality_inspections(doc):
    qi_names = []

    def _add_qi(name):
        if name and str(name).strip():
            n = str(name).strip()
            if n not in qi_names:
                qi_names.append(n)

    for ao in doc.get("alt_operasyon_kayitlari", []):
        _add_qi(ao.get("quality_inspection"))

    _add_qi(doc.get("quality_inspection"))

    try:
        db_qis = frappe.get_all(
            "Quality Inspection",
            filters={"custom_calisma_karti": doc.name, "docstatus": ["<", 2]},
            fields=["name"],
            order_by="creation asc"
        )
        for q in db_qis:
            _add_qi(q.name)
    except Exception:
        # Silently ignore if custom_calisma_karti link or Quality Inspection records cannot be queried
        pass

    return qi_names


def _resolve_qi_approver(qi_name):
    try:
        qi_data = frappe.db.get_value(
            "Quality Inspection",
            qi_name,
            ["inspected_by", "owner"],
            as_dict=True
        ) or {}
        user_id = qi_data.get("inspected_by") or qi_data.get("owner")
        if user_id:
            full_name = frappe.db.get_value("User", user_id, "full_name")
            return full_name or user_id
    except Exception:
        # Quality Inspection or User record may not exist or be inaccessible; fall back to "-"
        pass
    return "-"


@frappe.whitelist()
def get_job_card_protocols_html(job_card):
    cards = frappe.get_all(
        "Calisma Karti",
        filters={"is_karti": job_card, "docstatus": ["<", 2]},
        order_by="creation asc"
    )
    
    docs = []
    has_any_records = False
    
    for c in cards:
        doc = frappe.get_doc("Calisma Karti", c.name)
        
        has_krimp = bool(doc.get("krimp_olcumleri"))
        has_idc = bool(doc.get("idc_olcumleri"))
        has_enjeksiyon = bool(doc.get("enjeksiyon_olcumleri"))
        has_barkod = bool(doc.get("barkod_kayitlari"))
        
        if has_krimp or has_idc or has_enjeksiyon or has_barkod:
            has_any_records = True
            
            qi_names = _collect_quality_inspections(doc)
            qis_list = []
            approvers_list = []
            
            if len(qi_names) == 1:
                qi_name = qi_names[0]
                approver = _resolve_qi_approver(qi_name)
                qis_list.append(qi_name)
                approvers_list.append(approver)
            elif len(qi_names) > 1:
                for idx, qi_name in enumerate(qi_names, 1):
                    approver = _resolve_qi_approver(qi_name)
                    qis_list.append(f"{idx}. {qi_name}")
                    approvers_list.append(f"{idx}. {approver}")

            doc.qis_list = qis_list
            doc.approvers_list = approvers_list
            doc.qi_summary = ", ".join(qi_names) if qi_names else (doc.get("quality_inspection") or "-")
            doc.qi_owner_name = approvers_list[0] if approvers_list else "-"
            doc.operator_display_name = doc.get("operator_name") or doc.get("operator") or "-"
            
            docs.append(doc)
            
    if not has_any_records:
        return None

    html = frappe.render_template(
        "erpnextkta/kta_calisma_karti/templates/job_card_protocols.html",
        {
            "docs": docs,
            "today": frappe.utils.formatdate(frappe.utils.nowdate(), "dd.MM.yyyy"),
            "sapma_txt": sapma_txt,
            "sapma_class": sapma_class
        }
    )
    
    return {"html": html}
