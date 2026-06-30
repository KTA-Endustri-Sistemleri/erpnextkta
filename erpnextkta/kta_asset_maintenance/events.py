import frappe
from frappe.utils import get_datetime, add_to_date, getdate, now_datetime


COLOR_BREAKDOWN_OPEN = "#ff5858"
COLOR_PLANNED_OPEN = "#4c85e8"
COLOR_COMPLETED = "#36a147"


def _get_team_users(asset_maintenance_name):
    am = frappe.db.get_value(
        "Asset Maintenance",
        asset_maintenance_name,
        ["maintenance_team", "maintenance_manager"],
        as_dict=True,
    )
    if not am:
        return []

    users = set()
    if am.maintenance_manager:
        users.add(am.maintenance_manager)

    if am.maintenance_team:
        team_members = frappe.get_all(
            "Maintenance Team Member",
            filters={"parent": am.maintenance_team},
            fields=["team_member"],
        )
        for row in team_members:
            if row.team_member:
                users.add(row.team_member)

    result = []
    for user in users:
        email = frappe.db.get_value("User", user, "email") or user
        full_name = frappe.db.get_value("User", user, "full_name") or user
        result.append({"user": user, "email": email, "full_name": full_name})
    return result


def _append_participants(event_doc, participants, aml_name=None, asset_maintenance_name=None):
    if asset_maintenance_name:
        event_doc.append(
            "event_participants",
            {
                "reference_doctype": "Asset Maintenance",
                "reference_docname": asset_maintenance_name,
            },
        )
    if aml_name:
        event_doc.append(
            "event_participants",
            {
                "reference_doctype": "Asset Maintenance Log",
                "reference_docname": aml_name,
            },
        )
    for p in participants:
        event_doc.append(
            "event_participants",
            {
                "reference_doctype": "User",
                "reference_docname": p["user"],
                "email": p["email"],
            },
        )


def create_breakdown_event(aml_doc, asset_maintenance_name, asset_name, ariza_nedeni, aciklama):
    participants = _get_team_users(asset_maintenance_name)

    starts_on = now_datetime()
    ends_on = add_to_date(starts_on, hours=1)

    subject = f"Arıza: {asset_name} - {ariza_nedeni}"

    event = frappe.new_doc("Event")
    event.subject = subject
    event.starts_on = starts_on
    event.ends_on = ends_on
    event.event_type = "Public"
    event.event_category = "Event"
    event.color = COLOR_BREAKDOWN_OPEN
    event.status = "Open"
    event.description = (aciklama or "") + (
        f"\n\nBakım Kaydı: {aml_doc.name}" if aml_doc and aml_doc.name else ""
    )
    event.reference_doctype = "Asset Maintenance"
    event.reference_docname = asset_maintenance_name

    _append_participants(
        event,
        participants,
        aml_name=aml_doc.name if aml_doc else None,
        asset_maintenance_name=asset_maintenance_name,
    )

    event.insert(ignore_permissions=True)
    return event.name


def create_planned_event(task_row, asset_maintenance_name, asset_name):
    if not task_row.next_due_date:
        return None

    participants = _get_team_users(asset_maintenance_name)

    start_dt = get_datetime(task_row.next_due_date)
    if start_dt.hour == 0 and start_dt.minute == 0:
        start_dt = start_dt.replace(hour=9, minute=0)
    ends_dt = add_to_date(start_dt, hours=1)

    task_label = task_row.maintenance_task or task_row.name
    subject = f"Planlı Bakım: {asset_name} - {task_label}"

    event = frappe.new_doc("Event")
    event.subject = subject
    event.starts_on = start_dt
    event.ends_on = ends_dt
    event.event_type = "Public"
    event.event_category = "Event"
    event.color = COLOR_PLANNED_OPEN
    event.status = "Open"
    event.description = task_row.description or ""
    event.reference_doctype = "Asset Maintenance"
    event.reference_docname = asset_maintenance_name

    _append_participants(event, participants, asset_maintenance_name=asset_maintenance_name)

    event.insert(ignore_permissions=True)
    return event.name


def mark_event_completed(event_name):
    if not event_name or not frappe.db.exists("Event", event_name):
        return
    frappe.db.set_value(
        "Event",
        event_name,
        {"color": COLOR_COMPLETED, "status": "Completed"},
        update_modified=False,
    )


def on_asset_maintenance_log_update(doc, method=None):
    """Log güncellendiğinde eventleri ve Çalışma Kartı duruşlarını senkronize eder."""
        
    # Arıza kaydı tamamlandığında veya iptal edildiğinde, eğer bir çalışma kartına bağlıysa karttaki 'Arıza' duruşunu kapatıp normal beklemeye al.
    if doc.custom_calisma_karti_ref:
        try:
            if frappe.db.exists("Calisma Karti", doc.custom_calisma_karti_ref):
                ck = frappe.get_doc("Calisma Karti", doc.custom_calisma_karti_ref)
                if doc.maintenance_status in ["Completed", "Cancelled"]:
                    # Eğer son duruş henüz bitmediyse ve sebebi Arıza ise (İlk kapatma anı)
                    if ck.duruslar and not ck.duruslar[-1].durus_bitis and ck.duruslar[-1].durus_nedeni == "Arıza":
                        from frappe.utils import now_datetime, get_datetime
                        now = now_datetime()
                        
                        # 1. Mevcut arıza duruşunu bitir ve açıklamasına sonucu yaz (59 dk'lık asıl kayda not düşüyoruz)
                        last_row = ck.duruslar[-1]
                        last_row.durus_bitis = now
                        start_dt = get_datetime(last_row.durus_baslangic)
                        end_dt = get_datetime(last_row.durus_bitis)
                        last_row.durus_suresi = (end_dt - start_dt).total_seconds() / 60
                        
                        sonuc_notu = "Tamamlandı." if doc.maintenance_status == "Completed" else "İptal Edildi."
                        last_row.aciklama = (last_row.aciklama or "") + f"\n[Bakım Sonucu: {sonuc_notu}]"
                        
                        # 2. Yeni "Arıza Sonrası Bekleme" duruşu ekle
                        ck.append(
                            "duruslar",
                            {
                                "durus_nedeni": "Arıza Sonrası Bekleme",
                                "durus_baslangic": now,
                                "aciklama": "Bakım ekibi işlemi bitirdi, operatörün üretime devam etmesi bekleniyor.",
                            },
                        )
                        
                        ck.flags.ignore_validate_update_after_submit = True
                        ck.save(ignore_permissions=True)
                        
                        # UI'ı tetikle
                        from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed
                        publish_calisma_karti_changed(ck.name, reason="ariza_giderildi")
                    
                    else:
                        # Eğer Arıza (Esnek modda) operatör tarafından manuel kapatılmışsa veya sonradan statü düzeltiliyorsa
                        import re
                        sonuc_notu = "Tamamlandı." if doc.maintenance_status == "Completed" else "İptal Edildi."
                        changed = False
                        for row in reversed(ck.duruslar):
                            if row.durus_nedeni == "Arıza":
                                if "[Bakım Sonucu:" in (row.aciklama or ""):
                                    yeni_aciklama = re.sub(r"\[Bakım Sonucu:.*?\]", f"[Bakım Sonucu: {sonuc_notu}]", row.aciklama)
                                    if row.aciklama != yeni_aciklama:
                                        row.aciklama = yeni_aciklama
                                        changed = True
                                    break
                                else:
                                    row.aciklama = (row.aciklama or "") + f"\n[Bakım Sonucu: {sonuc_notu} (Kayıt Sonradan Kapatıldı)]"
                                    changed = True
                                    break
                        if changed:
                            ck.flags.ignore_validate_update_after_submit = True
                            ck.save(ignore_permissions=True)
                
                elif doc.maintenance_status in ["Arıza Bildirimi", "Fault Notification"]:
                    # Kullanıcı arızayı kapattıktan sonra "yanlış oldu" deyip tekrar açık duruma döndürürse
                    if len(ck.duruslar) >= 2:
                        last_row = ck.duruslar[-1]
                        prev_row = ck.duruslar[-2]
                        # Eğer operatör henüz "Devam Et" demediyse (son duruş hala "Arıza Sonrası Bekleme" ve açıksa)
                        if (not last_row.durus_bitis and last_row.durus_nedeni == "Arıza Sonrası Bekleme" and 
                            "operatörün üretime devam etmesi bekleniyor" in (last_row.aciklama or "")):
                            
                            if prev_row.durus_nedeni == "Arıza":
                                import re
                                # Son "Arıza Sonrası Bekleme" kaydını sil
                                ck.duruslar.pop()
                                
                                # Önceki "Arıza" kaydını tekrar aç (Zaman makinesi!)
                                prev_row.durus_bitis = None
                                prev_row.durus_suresi = 0
                                prev_row.aciklama = re.sub(r"\n\[Bakım Sonucu:.*?\]", "", prev_row.aciklama or "")
                                
                                ck.flags.ignore_validate_update_after_submit = True
                                ck.save(ignore_permissions=True)
                                
                                from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed
                                publish_calisma_karti_changed(ck.name, reason="ariza_geri_alindi")
        except Exception:
            frappe.log_error(title="Arıza Kapanışında Duruş Güncelleme Hatası", message=frappe.get_traceback())

    if doc.maintenance_status == "Completed":
        if doc.custom_event_id:
            mark_event_completed(doc.custom_event_id)
        elif doc.task:
            task_event = frappe.db.get_value(
                "Asset Maintenance Task", doc.task, "custom_event_id"
            )
            if task_event:
                mark_event_completed(task_event)


def on_asset_maintenance_update(doc, method=None):
    """Asset Maintenance kaydı update oldukça görevler için mavi event'ler oluşturur.

    Her planlı görev satırı için bir event tutulur. Event tamamlandıysa (yeşil)
    veya next_due_date ilerlemişse, yeni bir mavi event oluşturulur.
    """
    asset_name = doc.asset_name or doc.asset
    dirty = False

    for task in doc.get("asset_maintenance_tasks") or []:
        if (task.maintenance_type or "").strip() == "Arıza Bakımı":
            continue
        if not task.next_due_date:
            continue

        existing_event = task.get("custom_event_id")
        needs_new = True

        if existing_event and frappe.db.exists("Event", existing_event):
            ev = frappe.db.get_value(
                "Event",
                existing_event,
                ["status", "color", "starts_on"],
                as_dict=True,
            )
            ev_date = getdate(ev.starts_on) if ev and ev.starts_on else None
            task_date = getdate(task.next_due_date)
            is_completed = (ev.status == "Completed") or (ev.color == COLOR_COMPLETED)
            date_matches = ev_date == task_date
            if date_matches and not is_completed:
                needs_new = False

        if needs_new:
            event_name = create_planned_event(task, doc.name, asset_name)
            if event_name:
                frappe.db.set_value(
                    "Asset Maintenance Task",
                    task.name,
                    "custom_event_id",
                    event_name,
                    update_modified=False,
                )
                task.custom_event_id = event_name
                dirty = True

    if dirty:
        frappe.db.commit()
