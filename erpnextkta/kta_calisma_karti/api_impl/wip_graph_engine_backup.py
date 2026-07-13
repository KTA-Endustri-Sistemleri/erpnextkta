import frappe
from frappe import _
import json

class WIPValidationError(Exception):
    pass

# ---------------------------------------------------------
# Graph Core Engine - Davranış Yönlendirici
# ---------------------------------------------------------

@frappe.whitelist()
def get_wip_graph(wip_id):
    if not wip_id:
        return {"nodes": [], "edges": []}
    if not frappe.db.exists("KTA Sanal Yarimamul", wip_id):
        return {"nodes": [], "edges": []}
    graph_state = frappe.db.get_value("KTA Sanal Yarimamul", wip_id, "graph_state")
    if not graph_state:
        return {"nodes": [], "edges": []}
    import json
    return json.loads(graph_state)


def process_operation(wip_id_or_ids, operation_data, materials):
    """
    Ana giriş noktası. Operasyonun alt parametreleri ve davranış tipine göre
    ilgili handler'ı çağırır.
    """
    if isinstance(wip_id_or_ids, str):
        wip_ids = [wip_id_or_ids]
    else:
        wip_ids = wip_id_or_ids

    behavior = operation_data.get("sanal_yarimamul_davranisi")
    sub_param = operation_data.get("davranis_alt_parametresi")
    damar_sayisi = operation_data.get("damar_sayisi")

    handler = BEHAVIOR_HANDLERS.get(behavior)
    if not handler:
        raise WIPValidationError(_("Geçersiz Sanal Yarımamül Davranışı: {0}").format(behavior))
        
    op_ref = operation_data.get("operation_ref")

    if behavior == "Düğümleri Birleştirir":
        # Cleanup for all source WIPs if needed? Actually merge_wips creates a new WIP!
        # Re-run of merge_wips needs to delete the previously created merged WIP if it exists.
        # But we don't know the new WIP id here easily. We'll handle cleanup inside merge_wips or assume it's fresh.
        context = {
            "wip_ids": wip_ids,
            "materials": materials,
            "sub_param": sub_param,
            "damar_sayisi": damar_sayisi,
            "is_emri": operation_data.get("is_emri"),
            "calisma_karti": operation_data.get("calisma_karti"),
            "operation_ref": op_ref,
            "node_id": operation_data.get("hedef_node_id"),
            "pin_number": operation_data.get("pin_number")
        }
        return handler(context)

    # For other behaviors, process each wip_id independently
    for wip_id in wip_ids:
        # Cleanup previous state for this operation (Idempotency)
        if op_ref:
            wip = frappe.get_doc("KTA Sanal Yarimamul", wip_id)
            if wip.graph_state:
                graph = json.loads(wip.graph_state)
                nodes_to_remove = [n["id"] for n in graph["nodes"] if n.get("operation_ref") == op_ref]
                if nodes_to_remove:
                    graph["nodes"] = [n for n in graph["nodes"] if n["id"] not in nodes_to_remove]
                    graph["edges"] = [e for e in graph["edges"] if e["source"] not in nodes_to_remove and e["target"] not in nodes_to_remove]
                    for n in graph["nodes"]:
                        if n["type"] in ["Uç (T1)", "Uç (T2)"]:
                            has_connection = any(e for e in graph["edges"] if e["source"] == n["id"] or e["target"] == n["id"])
                            if not has_connection and not n.get("materials"):
                                n["status"] = "Açık"
                    wip.graph_state = json.dumps(graph)
                    wip.save()
                
        context = {
            "wip_id": wip_id,
            "materials": materials,
            "sub_param": sub_param,
            "damar_sayisi": damar_sayisi,
            "is_emri": operation_data.get("is_emri"),
            "calisma_karti": operation_data.get("calisma_karti"),
            "operation_ref": op_ref,
            "node_id": operation_data.get("hedef_node_id"),
            "pin_number": operation_data.get("pin_number")
        }
        
        handler(context)


# ---------------------------------------------------------
# Davranış Handlers (10 Ana Tip)
# ---------------------------------------------------------

def create_base_wire(context):
    """Tip 1: Temel Kablo Oluşturur (doppel: Evet/Hayır)"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    graph = json.loads(wip.graph_state or '{"nodes": [], "edges": []}')
    
    center_id = frappe.generate_hash(length=8)
    t1_id = frappe.generate_hash(length=8)
    t2_id = frappe.generate_hash(length=8)
    
    orta_mats = [m for m in context["materials"] if m.get("yon") == "Orta" or not m.get("yon")]
    sol_mats = [m for m in context["materials"] if m.get("yon") == "Sol"]
    sag_mats = [m for m in context["materials"] if m.get("yon") == "Sağ"]
    
    t1_status = "Dolu" if sol_mats else "Açık"
    t2_status = "Dolu" if sag_mats else "Açık"
    
    graph["nodes"].extend([
        {"id": center_id, "type": "Kablo Merkezi", "status": "Aktif", "materials": orta_mats},
        {"id": t1_id, "type": "Uç (T1)", "status": t1_status, "materials": sol_mats},
        {"id": t2_id, "type": "Uç (T2)", "status": t2_status, "materials": sag_mats}
    ])
    
    graph["edges"].extend([
        {"source": center_id, "target": t1_id},
        {"source": center_id, "target": t2_id}
    ])
    
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": "Kablo başarıyla oluşturuldu", "graph": graph}

def attach_component(context):
    """Tip 2: Uca / Düğüme Bileşen Ekler (uç_durumu)"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    graph = json.loads(wip.graph_state)
    
    if not context.get("node_id") and context.get("materials"):
        yon = context["materials"][0].get("yon")
        target_type = "Uç (T1)" if yon == "Sol" else "Uç (T2)" if yon == "Sağ" else "Kablo Merkezi" if yon == "Orta" else None
        if target_type:
            auto_node = next((n for n in graph["nodes"] if n["type"] == target_type), None)
            if auto_node:
                context["node_id"] = auto_node["id"]
                
    target_node = next((n for n in graph["nodes"] if n["id"] == context["node_id"]), None)
    
    if not target_node:
        raise WIPValidationError(_("Hedef düğüm bulunamadı!"))
        
    if target_node.get("is_container"):
        raise WIPValidationError(_("Bu düğüm bölünmüş bir 'container' düğümüdür, doğrudan işlem yapılamaz!"))
        
    uc_durumu = context.get("sub_param")
    
    if uc_durumu == "Kapalı Düğüme Ekler" and target_node["status"] != "Dolu":
        raise WIPValidationError(_("Bu işlem sadece Dolu/Kapalı düğümlere uygulanabilir."))
    elif uc_durumu != "Kapalı Düğüme Ekler" and target_node["status"] == "Dolu":
        raise WIPValidationError(_("Bu düğüm zaten Dolu/Kapalı, yeni bileşen eklenemez!"))

    # Yeni bileşen düğümü yaratıp hedefe bağla
    comp_id = frappe.generate_hash(length=8)
    comp_status = "Beklemede" if uc_durumu == "Beklemede" else "Aktif"
    
    graph["nodes"].append({
        "id": comp_id, 
        "type": "Bileşen", 
        "status": comp_status, 
        "materials": context["materials"],
        "operation_ref": context.get("operation_ref")
    })
    graph["edges"].append({"source": target_node["id"], "target": comp_id})
    
    # Uç durumunu güncelle
    if uc_durumu == "Kapatır":
        target_node["status"] = "Dolu"
        
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": f"Bileşen eklendi ({uc_durumu})"}

def merge_wips(context):
    """Tip 3: Düğümleri Birleştirir (birlesim_tipi: Terminal / Lehim / Perçin)"""
    wip_ids = context.get("wip_ids", [])
    if not wip_ids:
        raise WIPValidationError(_("Birleştirilecek WIP bulunamadı."))
        
    birlesim_tipi = context.get("sub_param", "Terminal")
    merge_node_id = frappe.generate_hash(length=8)
    op_ref = context.get("operation_ref")
    
    # 1. Eski birleşik WIP varsa temizle (Idempotency)
    # Bu operation_ref ile daha önce oluşturulmuş bir WIP var mı kontrol et.
    existing_merged = frappe.get_all("KTA Sanal Yarimamul", filters={"is_emri": context.get("is_emri")}, fields=["name", "graph_state"])
    for em in existing_merged:
        try:
            g = json.loads(em.graph_state or "{}")
            if any(n.get("operation_ref") == op_ref for n in g.get("nodes", [])):
                # Bu WIP bu operasyonla yaratılmış, sil.
                frappe.delete_doc("KTA Sanal Yarimamul", em.name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # 2. Kaynak WIP'leri topla, "Tüketildi" yap ve grafiği birleştir
    merged_graph = {"nodes": [], "edges": []}
    
    # Yeni birleşim düğümü
    merged_graph["nodes"].append({
        "id": merge_node_id,
        "type": f"Birleşim ({birlesim_tipi})",
        "status": "Dolu",
        "materials": context["materials"],
        "operation_ref": op_ref
    })
    
    yon = context["materials"][0].get("yon") if context.get("materials") else None
    target_type = "Uç (T1)" if yon == "Sol" else "Uç (T2)" if yon == "Sağ" else "Kablo Merkezi" if yon == "Orta" else None
    
    for wid in wip_ids:
        if not frappe.db.exists("KTA Sanal Yarimamul", wid):
            continue
        wip = frappe.get_doc("KTA Sanal Yarimamul", wid)
        wip.save(ignore_permissions=True)
        
        if wip.graph_state:
            g = json.loads(wip.graph_state)
            merged_graph["nodes"].extend(g.get("nodes", []))
            merged_graph["edges"].extend(g.get("edges", []))
            
            # Bağlanacak ucu bul
            node_to_connect = None
            if context.get("node_id"):
                node_to_connect = next((n for n in g.get("nodes", []) if n["id"] == context["node_id"]), None)
            
            if not node_to_connect and target_type:
                node_to_connect = next((n for n in g.get("nodes", []) if n["type"] == target_type), None)
                
            if node_to_connect:
                # Statüyü birleşti olarak güncelle (artık merged_graph içinde)
                for n in merged_graph["nodes"]:
                    if n["id"] == node_to_connect["id"]:
                        n["status"] = "Birleşti"
                merged_graph["edges"].append({"source": node_to_connect["id"], "target": merge_node_id})

    # 3. Yeni Birleşik WIP Yarat
    new_wip_id = f"{context.get('calisma_karti', 'WIP')}-{frappe.generate_hash(length=6)}"
    new_wip = frappe.get_doc({
        "doctype": "KTA Sanal Yarimamul",
        "name": new_wip_id,
        "is_emri": context.get("is_emri"),
        "calisma_karti": context.get("calisma_karti"),
        "status": "Aktif",
        "graph_state": json.dumps(merged_graph)
    })
    new_wip.insert(ignore_permissions=True)
    
    # 4. Kaynak WIP'leri de güncelle (UI'da kaynak id'ler üzerinden grafiği görebilmek için)
    for wid in wip_ids:
        if not frappe.db.exists("KTA Sanal Yarimamul", wid):
            continue
        wip = frappe.get_doc("KTA Sanal Yarimamul", wid)
        wip.graph_state = json.dumps(merged_graph)
        wip.status = "Tüketildi"
        wip.save(ignore_permissions=True)
    return {"status": "success", "message": f"{len(wip_ids)} WIP {birlesim_tipi} ile birleştirildi. Yeni WIP: {new_wip_id}", "new_wip_id": new_wip_id}

def plug_into_socket(context):
    """Tip 4: Soketler (Pin bazlı)"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    graph = json.loads(wip.graph_state)
    
    if not context.get("node_id") and context.get("materials"):
        yon = context["materials"][0].get("yon")
        target_type = "Uç (T1)" if yon == "Sol" else "Uç (T2)" if yon == "Sağ" else "Kablo Merkezi" if yon == "Orta" else None
        if target_type:
            auto_node = next((n for n in graph["nodes"] if n["type"] == target_type), None)
            if auto_node:
                context["node_id"] = auto_node["id"]
                
    target_node = next((n for n in graph["nodes"] if n["id"] == context["node_id"]), None)
    
    if not target_node:
        raise WIPValidationError(_("Hedef düğüm bulunamadı!"))
        
    pin_number = context.get("pin_number")
    
    socket_node_id = frappe.generate_hash(length=8)
    graph["nodes"].append({
        "id": socket_node_id,
        "type": "Soket Port",
        "status": "Dolu",
        "pin": pin_number,
        "materials": context["materials"]
    })
    
    target_node["status"] = "Soketlendi"
    graph["edges"].append({"source": target_node["id"], "target": socket_node_id})
    
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": f"Pin {pin_number} soketlendi."}

def apply_injection_mold(context):
    """Tip 5: Enjeksiyon"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    graph = json.loads(wip.graph_state)
    
    if not context.get("node_id") and context.get("materials"):
        yon = context["materials"][0].get("yon")
        target_type = "Uç (T1)" if yon == "Sol" else "Uç (T2)" if yon == "Sağ" else "Kablo Merkezi" if yon == "Orta" else None
        if target_type:
            auto_node = next((n for n in graph["nodes"] if n["type"] == target_type), None)
            if auto_node:
                context["node_id"] = auto_node["id"]
                
    target_node = next((n for n in graph["nodes"] if n["id"] == context["node_id"]), None)
    
    if not target_node:
        raise WIPValidationError(_("Hedef düğüm bulunamadı!"))
        
    target_node["status"] = "Kalıplanmış"
    # Enjeksiyon malzemesini düğümün malzemelerine ekle
    if "materials" not in target_node:
        target_node["materials"] = []
    target_node["materials"].extend(context["materials"])
    
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": "Enjeksiyon kalıbı uygulandı."}

def process_no_structure(context):
    """Tip 6: Yapısal Değişikliksiz İşlem (wip_durumu)"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    wip_durumu = context.get("sub_param")
    
    if wip_durumu == "Tamamlandı Kapatır":
        wip.status = "Tamamlandı"
    
    # Graph'a genel metadata veya metadata düğümü eklenebilir
    graph = json.loads(wip.graph_state)
    if "metadata" not in graph:
        graph["metadata"] = {}
    if "islem_gecmisi" not in graph["metadata"]:
        graph["metadata"]["islem_gecmisi"] = []
        
    graph["metadata"]["islem_gecmisi"].append({
        "islem": "Yapısal Değişikliksiz İşlem",
        "durum": wip_durumu,
        "materials": context["materials"]
    })
    
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": f"İşlem kaydedildi ({wip_durumu})"}

def record_test_result(context):
    """Tip 7: Doğrulama / Test"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    graph = json.loads(wip.graph_state)
    
    if "metadata" not in graph:
        graph["metadata"] = {}
        
    test_result = context.get("test_result", True) # Default OK
    graph["metadata"]["test_ok"] = test_result
    
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": "Test sonucu kaydedildi."}

def activate_pending_component(context):
    """Tip 8: Bileşeni Aktifleştirir (test_zorunlu)"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    graph = json.loads(wip.graph_state)
    
    if not context.get("node_id") and context.get("materials"):
        yon = context["materials"][0].get("yon")
        target_type = "Uç (T1)" if yon == "Sol" else "Uç (T2)" if yon == "Sağ" else "Kablo Merkezi" if yon == "Orta" else None
        if target_type:
            auto_node = next((n for n in graph["nodes"] if n["type"] == target_type), None)
            if auto_node:
                context["node_id"] = auto_node["id"]
                
    target_node = next((n for n in graph["nodes"] if n["id"] == context["node_id"]), None)
    
    if not target_node:
        raise WIPValidationError(_("Hedef düğüm bulunamadı!"))
        
    test_zorunlu = context.get("sub_param") == "Evet"
    
    if test_zorunlu:
        if not graph.get("metadata", {}).get("test_ok", False):
            raise WIPValidationError(_("Bu bileşeni aktifleştirmek için önce 'Test OK' gereklidir!"))
            
    if target_node["status"] != "Beklemede":
        raise WIPValidationError(_("Bu düğüm 'Beklemede' statüsünde değil!"))
        
    target_node["status"] = "Aktif"
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": "Bileşen aktifleştirildi."}

def split_endpoint(context):
    """Tip 9: Ucu Böler (damar_sayisi)"""
    wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
    graph = json.loads(wip.graph_state)
    
    if not context.get("node_id") and context.get("materials"):
        yon = context["materials"][0].get("yon")
        target_type = "Uç (T1)" if yon == "Sol" else "Uç (T2)" if yon == "Sağ" else "Kablo Merkezi" if yon == "Orta" else None
        if target_type:
            auto_node = next((n for n in graph["nodes"] if n["type"] == target_type), None)
            if auto_node:
                context["node_id"] = auto_node["id"]
                
    target_node = next((n for n in graph["nodes"] if n["id"] == context["node_id"]), None)
    
    if not target_node:
        raise WIPValidationError(_("Hedef düğüm bulunamadı!"))
    if target_node["status"] == "Dolu":
        raise WIPValidationError(_("Dolu/Kapalı bir uç bölünemez!"))
        
    damar_sayisi = context.get("damar_sayisi", 1)
    
    # Hedef düğümü kapsayıcıya çevir
    target_node["is_container"] = True
    target_node["status"] = "Bölündü"
    
    # N adet yeni damar ucu yarat
    for i in range(damar_sayisi):
        damar_id = frappe.generate_hash(length=8)
        graph["nodes"].append({
            "id": damar_id,
            "type": f"Damar Ucu ({i+1})",
            "status": "Açık",
            "materials": []
        })
        graph["edges"].append({"source": target_node["id"], "target": damar_id})
        
    wip.graph_state = json.dumps(graph)
    wip.save()
    return {"status": "success", "message": f"Uç {damar_sayisi} damara bölündü."}

def create_sub_assembly(context):
    """Tip 10: Alt Montaj (Sub-Assembly) (cikti_tipi)"""
    cikti_tipi = context.get("sub_param")
    
    if cikti_tipi == "Yeni WIP":
        # Yeni bir WIP kaydı yaratılır
        wip = frappe.get_doc({
            "doctype": "KTA Sanal Yarimamul",
            "is_emri": context.get("is_emri"),
            "calisma_karti": context.get("calisma_karti"),
            "status": "Aktif",
            "is_graph_based": 1
        })
        wip.insert(ignore_permissions=True)
        
        assembly_id = frappe.generate_hash(length=8)
        graph = {
            "nodes": [{
                "id": assembly_id,
                "type": "Alt Montaj",
                "status": "Aktif",
                "materials": context["materials"]
            }],
            "edges": []
        }
        wip.graph_state = json.dumps(graph)
        wip.save()
        return {"status": "success", "message": "Yeni Alt Montaj WIP'i oluşturuldu.", "wip_name": wip.name}
        
    elif cikti_tipi == "Mevcut WIP'e Ekle":
        wip = frappe.get_doc("KTA Sanal Yarimamul", context["wip_id"])
        graph = json.loads(wip.graph_state)
        target_node = next((n for n in graph["nodes"] if n["id"] == context["node_id"]), None)
        
        if not target_node:
            raise WIPValidationError(_("Hedef düğüm bulunamadı!"))
            
        assembly_id = frappe.generate_hash(length=8)
        graph["nodes"].append({
            "id": assembly_id,
            "type": "Alt Montaj Eklentisi",
            "status": "Aktif",
            "materials": context["materials"]
        })
        graph["edges"].append({"source": target_node["id"], "target": assembly_id})
        
        wip.graph_state = json.dumps(graph)
        wip.save()
        return {"status": "success", "message": "Alt Montaj mevcut WIP'e eklendi."}
    else:
        raise WIPValidationError(_("Geçersiz alt montaj çıktı tipi!"))

# ---------------------------------------------------------
# Handler Haritası
# ---------------------------------------------------------

BEHAVIOR_HANDLERS = {
    "Temel Kablo Oluşturur": create_base_wire,
    "Uca / Düğüme Bileşen Ekler": attach_component,
    "Düğümleri Birleştirir": merge_wips,
    "Soketler": plug_into_socket,
    "Enjeksiyon": apply_injection_mold,
    "Yapısal Değişikliksiz İşlem": process_no_structure,
    "Doğrulama / Test": record_test_result,
    "Bileşeni Aktifleştirir": activate_pending_component,
    "Ucu Böler": split_endpoint,
    "Alt Montaj (Sub-Assembly)": create_sub_assembly,
}
