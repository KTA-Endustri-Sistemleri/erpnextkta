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
        
        # Sadece içi dolu olan tabloları olan kartları veya en az bir tablosu olanları alacağız.
        # Aslında kartı ekleyelim, şablon içinde tabloların dolu olup olmadığına göre bölüm çıkaralım.
        has_krimp = bool(doc.get("krimp_olcumleri"))
        has_idc = bool(doc.get("idc_olcumleri"))
        has_enjeksiyon = bool(doc.get("enjeksiyon_olcumleri"))
        has_barkod = bool(doc.get("barkod_kayitlari"))
        
        if has_krimp or has_idc or has_enjeksiyon or has_barkod:
            has_any_records = True
            
            if doc.quality_inspection:
                try:
                    qi = frappe.get_doc("Quality Inspection", doc.quality_inspection)
                    doc.qi_owner_name = frappe.db.get_value("User", qi.owner, "full_name") or "-"
                except Exception:
                    doc.qi_owner_name = "-"
            else:
                doc.qi_owner_name = "-"
                
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
