import re
import frappe
from datetime import datetime, time
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, add_to_date
from frappe.model.naming import make_autoname
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed


# Status definitions mapped to CSS classes (Frontend state)
STATU_HARITASI = {
    "reddedildi": "Reddedildi",
    "hazir": "Hazır",
    "calisiyor": "Çalışıyor",
    "durusta": "Duruşta",
    "bitmis": "Bitmiş",
    "iptal_edildi": "İptal Edildi",
}

def get_kta_settings():
    try:
        max_limit = frappe.db.get_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk") or 430
        warn_limit = frappe.db.get_single_value("KTA Calisma Karti Settings", "kart_uyari_suresi_dk") or 400
        return int(max_limit), int(warn_limit)
    except Exception:
        return 430, 400


def _shift_name_by_now(now_dt):
    """Pick shift name by current time-of-day (fallback when Shift Assignment is not used).

    Boundary rule: exact boundary times belong to the ENDING shift, not the starting one.
      - 00:00 → 2. Vardiya  (end of 2nd shift, not start of 3rd)
      - 08:00 → 3. Vardiya  (end of 3rd shift, not start of 1st)
      - 16:00 → 1. Vardiya  (end of 1st shift, not start of 2nd)
    This is critical for auto-close cards whose bitis_saati sits exactly on the boundary.
    """
    t = now_dt.time()
    if time(0, 0) < t <= time(8, 0):
        return "3. Vardiya"
    elif time(8, 0) < t <= time(16, 0):
        return "1. Vardiya"
    else:
        return "2. Vardiya"


def _shift_window(now_dt):
    """Return (window_start, window_end) for the current shift based on HRMS Shift Type."""
    shift = _shift_name_by_now(now_dt)
    shift_doc = frappe.get_doc("Shift Type", shift)

    # Shift Type stores time as timedelta in your system
    start_seconds = int(shift_doc.start_time.total_seconds())
    end_seconds = int(shift_doc.end_time.total_seconds())

    start_t = time(start_seconds // 3600, (start_seconds % 3600) // 60, 0)
    end_t = time(end_seconds // 3600, (end_seconds % 3600) // 60, 0)

    today = now_dt.date()
    ws = get_datetime(datetime.combine(today, start_t))
    we = get_datetime(datetime.combine(today, end_t))

    # Overnight shift (e.g. 16:00 -> 00:00)
    if we <= ws:
        we = add_to_date(we, days=1)

    return ws, we


def _parse_minsec(value: str) -> int:
    """Parse 'HH:MM:SS' or 'M:SS' into total seconds. Returns 0 on invalid input."""
    if not value or not isinstance(value, str):
        return 0
    s = str(value).strip()
    if ":" not in s:
        return 0
    
    parts = s.split(":")
    try:
        if len(parts) == 3:
            # HH:MM:SS
            h, m, sec = parts
            return int(h) * 3600 + int(m) * 60 + int(sec)
        elif len(parts) == 2:
            # M:SS
            m, sec = parts
            return int(m) * 60 + int(sec)
    except Exception:
        pass
    return 0


def _other_cards_net_seconds_in_shift(operator: str, shift_start, shift_end, exclude_name: str) -> int:
    """Sum net seconds of other cards for operator in shift window. 
    Uses FOR UPDATE lock to prevent race conditions during concurrent saves.
    """
    if not operator or not shift_start or not shift_end:
        return 0

    # 1. LOCK: Bu operatörün bu vardiyadaki tüm kayıtlarını kilitle (Race condition önleyici)
    # Bu, aynı operatör için aynı anda iki farklı kartın süre hesaplamasını engeller.
    frappe.db.sql("""
        SELECT name FROM `tabCalisma Karti`
        WHERE operator = %s 
          AND baslangic_saati BETWEEN %s AND %s
          AND docstatus < 2
        FOR UPDATE
    """, (operator, shift_start, shift_end))

    # 2. READ: Veriler kilitlendikten sonra güncel durumu oku
    rows = frappe.get_all(
        "Calisma Karti",
        filters={
            "operator": operator,
            "docstatus": ["!=", 2],
            "baslangic_saati": ["between", [shift_start, shift_end]],
            "name": ["!=", exclude_name],
        },
        fields=["net_calisma_suresi", "kalite_kontrol"],
        limit_page_length=2000,
    )

    total = 0
    for r in rows:
        if (r.get("kalite_kontrol") or "").strip() == "Reddedildi":
            continue
        total += _parse_minsec(r.get("net_calisma_suresi"))

    return total


class CalismaKarti(Document):
    def on_update(self):
        publish_calisma_karti_changed(self.name, reason="doc:on_update")
        from erpnextkta.kta_calisma_karti.api_impl.hurda import sync_calisma_karti_hurdalar_to_se
        sync_calisma_karti_hurdalar_to_se(self)

    def before_update_after_submit(self):
        self.update_durum()

    def on_update_after_submit(self):
        self.on_update()

    def on_cancel(self):
        self.db_set("durum", "İptal Edildi", update_modified=True)
        publish_calisma_karti_changed(self.name, reason="doc:on_cancel")

    def before_validate(self):
        if not self.custom_work_order and self.is_karti:
            self.custom_work_order = frappe.db.get_value("Job Card", self.is_karti, "work_order")
        if self.is_karti:
            if not self.urun_kodu or not self.uretilecek_miktar:
                jc_data = frappe.db.get_value("Job Card", self.is_karti, ["production_item", "for_quantity"], as_dict=True)
                if jc_data:
                    if not self.urun_kodu:
                        self.urun_kodu = jc_data.production_item
                    if not self.uretilecek_miktar:
                        self.uretilecek_miktar = jc_data.for_quantity

    def autoname(self):
        """
        İsim formatı: <OPR>-<WO_last5>-<Operasyon>-<01..>
        (Sayı üretimi Frappe tabSeries ile yapılır; SQL yok)
        """
        # 1) İş Emri (Work Order)
        wo_name = (self.get("custom_work_order") or "").strip()
        if not wo_name and (self.get("is_karti") or "").strip():
            wo_name = frappe.db.get_value("Job Card", self.is_karti, "work_order") or ""

        # 2) İş Emri formatı: "MFG-WO-2026-02172" => "2026-02172"
        if wo_name:
            wo_tail = wo_name.split("WO-")[-1].strip()
            # Güvenlik için sadece harf, rakam ve tireye izin ver
            wo_tail = re.sub(r"[^\w\-]", "", wo_tail)
            if not wo_tail:
                wo_tail = "WO"
        else:
            wo_tail = "WO"

        # 3) Operasyon: boşluk ve '-' temizle
        op_raw = self.get("operasyon") or ""
        op_clean = re.sub(r"[\s\-]+", "", op_raw).strip() or "OP"

        # 4) Operatör isim/soyisim (varsa), yoksa "OPR"
        op_full_raw = (
            (self.get("operator") or "")
        ).strip()
        if op_full_raw:
            op_full = re.sub(r"[\s_–—−]+", "-", op_full_raw)
            op_full = re.sub(r"-+", "-", op_full)
            op_full = re.sub(r"[^0-9A-Za-z\-ÇĞİÖŞÜçğıöşü]", "", op_full)
            op_full = op_full.strip("-") or "OPR"
        else:
            op_full = "OPR"

        # 5) Prefix ve seri
        prefix_core = f"{wo_tail}-{op_clean}"
        prefix = f"{op_full}-{prefix_core}"

        # .## => 01, 02, 03 ...
        self.name = make_autoname(f"{prefix}-.##")

    def validate(self):
        # 1. Duruş nedeni 'Diger' olan kayıtlarda açıklama zorunluluğunu denetle
        if self.duruslar:
            for row in self.duruslar:
                if row.durus_nedeni == "Diger" and not (row.aciklama or "").strip():
                    frappe.throw(
                        frappe._("Duruş nedeni olarak 'Diger' seçildiğinde açıklama girmek zorunludur. Lütfen {0}. sıradaki duruş kaydının açıklamasını doldurunuz.").format(row.idx),
                        title=frappe._("Açıklama Zorunlu")
                    )

        self.update_durum()
        if not self.kalite_kontrol:
            self.kalite_kontrol = "Onay Bekliyor"

        self.check_duplicate_quality_docs()

        # Proaktif Operatör İkazı (Dinamik Uyarı Süresi)
        durum_key = self.get_durum()
        if durum_key in ['calisiyor', 'durusta'] and self.baslangic_saati:
            start_dt = get_datetime(self.baslangic_saati)
            now_dt = now_datetime()
            gecen_dk = (now_dt - start_dt).total_seconds() / 60

            _, warn_limit = get_kta_settings()
            if gecen_dk > warn_limit:
                frappe.msgprint(
                    f"⚠️ Bu kart {warn_limit} dakikayı aştı! Lütfen formu kontrol edin (bitirin veya durdurun).",
                    title="Süre Uyarısı",
                    indicator="orange"
                )

    def hesapla_durus_suresi(self):
        toplam_dk = 0
        for row in self.duruslar:
            if row.durus_baslangic and row.durus_bitis:
                if not row.durus_suresi:
                    start_dt = get_datetime(row.durus_baslangic)
                    end_dt = get_datetime(row.durus_bitis)
                    row.durus_suresi = (end_dt - start_dt).total_seconds() / 60
                toplam_dk += (row.durus_suresi or 0)
        self.toplam_durus = format_sure(toplam_dk * 60)

    def update_durum(self):
        self.hesapla_durus_suresi()
        self.hesapla_toplam_sure()
        durum_key = self.get_durum()
        self.durum = STATU_HARITASI.get(durum_key, "Hazır")

    def before_submit(self):
        # Ensure status is fresh before checking
        self.update_durum()

        # We allow submission if the status is either "Bitmiş" or "Reddedildi".
        # Fallback: if bitis_saati is set, it's technically finished, so we allow it.
        # This prevents blocking due to potential stale 'durum' field logic.
        is_finished = self.durum in ["Bitmiş", "Reddedildi"] or self.bitis_saati
        
        if not is_finished:
            # Diagnostic logging to capture the state of the document at the moment of failure
            log_data = {
                "name": self.name,
                "durum": self.durum,
                "get_durum": self.get_durum(),
                "bitis_saati": str(self.bitis_saati),
                "baslangic_saati": str(self.baslangic_saati),
                "kalite_kontrol": self.kalite_kontrol,
                "docstatus": self.docstatus,
                "aktif_durus": self.aktif_durus_var_mi()
            }
            frappe.log_error(title="Calisma Karti Submit Blocked", message=frappe.as_json(log_data))
            
            frappe.throw(
                frappe._("Çalışma Kartı henüz bitirilmemiş. Lütfen önce kartı bitirin."),
                title=frappe._("Gönderim Engellendi")
            )

    def check_duplicate_quality_docs(self):
        # Ayarlar üzerinden kontrolün aktif olup olmadığını denetle
        check_enabled = frappe.db.get_single_value("KTA Calisma Karti Settings", "mukerrer_kalite_kontrolu_yap")
        if not check_enabled:
            return

        fields = [
            ("quality_inspection", "Kalite Muayene Belgesi"),
            ("test_masasi_dogrulama_kaydi", "Test Masası Doğrulama Kaydı")
        ]
        
        for field, label in fields:
            val = self.get(field)
            if not val:
                continue

            # 1. ADIM: İlgili kalite belgesini veritabanında kilitle (opsiyonel)
            target_doctype = "Quality Inspection" if field == "quality_inspection" else "Test Masasi Dogrulama Kaydi"
            if frappe.db.exists(target_doctype, val):
                # Kaydı kilitle (Race condition önleyici)
                frappe.db.sql("SELECT name FROM `tab{0}` WHERE name = %s FOR UPDATE".format(target_doctype), (val,))
                
            # 2. ADIM: Başka bir kartta kullanılıp kullanılmadığına bak
            # docstatus < 2 (Draft + Submitted) dahil, Cancelled (2) hariç
            duplicate = frappe.db.get_value(
                "Calisma Karti", 
                {
                    field: val,
                    "name": ["!=", self.name or ""],
                    "docstatus": ["<", 2]
                }, 
                "name",
                for_update=True
            )

            if duplicate:
                frappe.throw(
                    frappe._("{0} '{1}' başka bir Çalışma Kartı ({2}) tarafından zaten kullanılmış.").format(label, val, duplicate),
                    title=frappe._("Mükerrer Kayıt")
                )



    def hesapla_toplam_sure(self):
        if self.baslangic_saati:
            start_dt = get_datetime(self.baslangic_saati)
            end_dt = get_datetime(self.bitis_saati) if self.bitis_saati else now_datetime()

            toplam_saniye = (end_dt - start_dt).total_seconds()
            toplam_durus_dk = sum((r.durus_suresi or 0) for r in self.duruslar)
            toplam_durus_saniye = toplam_durus_dk * 60

            # Aktif (devam eden) duruş varsa onu da toplam duruşa ekle
            if self.aktif_durus_var_mi():
                last_durus = self.duruslar[-1]
                durus_start = get_datetime(last_durus.durus_baslangic)
                active_durus_seconds = (end_dt - durus_start).total_seconds()
                toplam_durus_saniye += active_durus_seconds

            # Vardiya kapasitesi (max_limit) tavan olarak kullanılır.
            max_limit, _ = get_kta_settings()
            max_saniye = max_limit * 60

            # Vardiya içindeki diğer kartların net süresiyle birlikte tavan aşılmamalı
            ws, we = _shift_window(start_dt)
            other_net = _other_cards_net_seconds_in_shift(
                operator=self.operator,
                shift_start=ws,
                shift_end=we,
                exclude_name=self.name,
            )
            remaining = max(0, max_saniye - other_net)

            # Get raw net seconds (total span minus breaks)
            raw_net_saniye = max(0, toplam_saniye - toplam_durus_saniye)
            
            # Apply shift remaining capacity limit to the NET time, not the total span.
            # This prevents "net squashing" when breaks are long.
            net_saniye = min(raw_net_saniye, remaining)

            self.toplam_sure = format_sure(toplam_saniye)
            self.net_calisma_suresi = format_sure(net_saniye)
        else:
            self.toplam_sure = "0:00"
            self.net_calisma_suresi = "0:00"

    def aktif_durus_var_mi(self):
        if not self.duruslar:
            return False
        last_row = self.duruslar[-1]
        return last_row.durus_baslangic and not last_row.durus_bitis

    def get_durum(self):
        if self.docstatus == 2:
            return 'iptal_edildi'
        # If QC rejected, lock the card status.
        if (self.kalite_kontrol or '').strip() == 'Reddedildi':
            return 'reddedildi'
        if self.bitis_saati:
            return 'bitmis'
        elif not self.baslangic_saati:
            return 'hazir'
        elif self.aktif_durus_var_mi():
            return 'durusta'
        else:
            return 'calisiyor'

def format_sure(seconds):
    if seconds is None or seconds < 0:
        return "00:00:00"

    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

@frappe.whitelist()
def islem_yap(docname, islem_tipi, durus_nedeni=None, aciklama=None, tamamlanan_miktar=None):
    from erpnextkta.kta_calisma_karti.api_impl.cards import islem_yap as api_islem_yap
    return api_islem_yap(docname, islem_tipi, durus_nedeni, aciklama, tamamlanan_miktar)


@frappe.whitelist()
def create_ariza_bildirimi(calisma_karti, makine_no, ariza_nedeni, aciklama):
    """
    Operatör tarafından Çalışma Kartı üzerinden yapılan Arıza Bildirimini
    Asset Maintenance Log olarak kaydeder.
    """
    from frappe.utils import today
    from frappe import _
    
    if not calisma_karti or not makine_no or not ariza_nedeni or not aciklama:
        frappe.throw(_("Çalışma Kartı, Makine No, Arıza Nedeni ve Açıklama alanları zorunludur."))

    doc = frappe.get_doc("Calisma Karti", calisma_karti)
    if not doc:
        frappe.throw(_("Çalışma kartı bulunamadı."))
    
    # Sadece "Çalışıyor" veya "Duruşta" olan kartlarda arıza bildirilebilir
    if doc.durum not in ["Çalışıyor", "Duruşta"]:
        frappe.throw(_("Sadece 'Çalışıyor' veya 'Duruşta' olan kartlar için arıza bildirimi yapabilirsiniz."))

    # Zaten açık/bekleyen bir arıza kaydı varsa yenisinin açılmasını engelle
    open_log = frappe.db.get_value("Asset Maintenance Log", {
        "custom_calisma_karti_ref": doc.name,
        "maintenance_status": ["not in", ["Completed", "Cancelled"]],
        "docstatus": ["<", 2]
    }, "name")
    
    if open_log:
        frappe.throw(_("Bu çalışma kartına ait zaten devam eden açık bir arıza kaydı ({0}) bulunuyor. Yeni bir kayıt açmadan önce mevcut kaydın tamamlanmasını veya iptal edilmesini beklemelisiniz.").format(open_log))

    asset_name = frappe.db.get_value("Asset", {"custom_makine_no": makine_no}, "name")
    if not asset_name:
        frappe.throw(_("Sistemde {0} numarasına sahip bir makine/varlık bulunamadı.").format(makine_no))

    asset_doc = frappe.get_doc("Asset", asset_name)

    # 1. Asset Maintenance kaydını bul (varsa)
    asset_maint_name = frappe.db.get_value("Asset Maintenance", {"asset_name": asset_name})
    
    if not asset_maint_name:
        frappe.throw(_("{0} makinesi için sistemde 'Asset Maintenance' (Varlık Bakımı) kaydı bulunamadı. Lütfen önce bakım ekibini atayın.").format(makine_no))
        
    asset_maint = frappe.get_doc("Asset Maintenance", asset_maint_name)

    # 2. Asset Maintenance Task oluştur (Arıza Bildirimi için bir kerelik görev)
    task_name = f"Arıza Bildirimi - {frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M')}"
    
    # Check if a similar task recently created to prevent duplicates in case of double clicks
    existing_task = frappe.db.get_value("Asset Maintenance Task", {
        "parent": asset_maint.name,
        "maintenance_status": "Arıza Bildirimi",
        "description": aciklama
    }, "name")
    
    if existing_task:
        task_id = existing_task
    else:
        # Bir task satırı eklenmek zorunda. Ancak parent.save() dersek 
        # Asset Maintenance içindeki on_update her satır için tekrar ToDo oluşturmaya çalışıyor
        # ve "Zaten şu kullanıcının yapılacaklar listesinde" hatası veriyor.
        # Bu yüzden satırı manuel insert ediyoruz.
        
        new_task = frappe.get_doc({
            "doctype": "Asset Maintenance Task",
            "parent": asset_maint.name,
            "parenttype": "Asset Maintenance",
            "parentfield": "asset_maintenance_tasks",
            "maintenance_task": task_name,
            "maintenance_type": "Arıza Bakımı",
            "maintenance_status": "Arıza Bildirimi",
            "start_date": today(),
            "next_due_date": today(),
            "end_date": frappe.utils.add_days(today(), 1),
            "periodicity": "Daily",
            "description": aciklama,
            "assign_to": asset_maint.maintenance_manager or (frappe.db.get_values("Maintenance Team Member", {"parent": asset_maint.maintenance_team}, "team_member")[0][0] if frappe.db.get_values("Maintenance Team Member", {"parent": asset_maint.maintenance_team}, "team_member") else None)
        })
        new_task.insert(ignore_permissions=True)
        task_id = new_task.name

    # 3. Asset Maintenance Log (Arıza Bildirimi) oluştur
    aml = frappe.new_doc("Asset Maintenance Log")
    aml.asset_maintenance = asset_maint.name
    aml.task = task_id
    aml.maintenance_status = "Arıza Bildirimi"
    aml.custom_calisma_karti_ref = calisma_karti
    aml.custom_ariza_nedeni = ariza_nedeni
    aml.custom_ariza_aciklamasi = aciklama
    aml.due_date = today()
    aml.insert(ignore_permissions=True)

    # 4. Takvim etkinliği (kırmızı) oluştur ve ekip üyelerini participant olarak ekle
    from erpnextkta.kta_asset_maintenance.events import create_breakdown_event
    try:
        event_name = create_breakdown_event(
            aml,
            asset_maint.name,
            asset_doc.asset_name or asset_name,
            ariza_nedeni,
            aciklama,
        )
        if event_name:
            frappe.db.set_value(
                "Asset Maintenance Log",
                aml.name,
                "custom_event_id",
                event_name,
                update_modified=False,
            )
    except Exception:
        frappe.log_error(
            title="Arıza Bildirimi - Takvim Etkinliği Oluşturulamadı",
            message=frappe.get_traceback(),
        )

    # Not: aml.submit() yapılmıyor çünkü ERPNext standarta "Completed" veya "Cancelled"
    # durumu olmadan gönderime izin vermez. Bildirim draft olarak kalacak,
    # bakım ekibi işi bitirince statüyü "Completed" yapıp submit edecek.

    # 5. Kart Çalışıyorsa veya Duruştaysa Otomatik Arıza Duruşuna Geçir
    durum = doc.get_durum()
    if durum in ("calisiyor", "durusta"):
        try:
            from erpnextkta.kta_calisma_karti.api_impl.cards import islem_yap
            needs_pause = True

            if durum == "durusta":
                # Eğer aktif duruş sebebi zaten "Arıza" ise yeni bir duruş kaydı açıp süreyi bölmeye gerek yok.
                if doc.duruslar and not doc.duruslar[-1].durus_bitis and doc.duruslar[-1].durus_nedeni == "Arıza":
                    needs_pause = False
                else:
                    # Başka bir duruştaysa (örn: Mola), o duruşu bitirmek için "DevamEt" tetikliyoruz
                    islem_yap(calisma_karti, "DevamEt")
            
            if needs_pause:
                islem_yap(calisma_karti, "Durus", durus_nedeni="Arıza", aciklama=aciklama)
        except Exception as e:
            frappe.log_error(title="Arıza Otomatik Duruş Hatası", message=frappe.get_traceback())

    return aml.name

@frappe.whitelist()
def get_auto_paused_cards(operator):
    if not operator:
        return []
    
    # Eğer operatörün halihazırda "Çalışıyor" durumunda olan aktif bir kartı varsa,
    # başka bir işlem için duruşu bitirdiğinde onu yeni kart seçmeye zorlamamalıyız.
    running_cards_count = frappe.db.count('Calisma Karti', filters={
        'operator': operator,
        'docstatus': ['<', 2],
        'durum': 'Çalışıyor'
    })

    if running_cards_count > 0:
        return []

    # `AGENTS.md` kurallarına uygun olarak Raw SQL yerine ORM kullanıyoruz
    duruslar = frappe.get_all(
        'Operasyon Duruslari',
        filters={
            'durus_bitis': ('is', 'not set'),
            'durus_nedeni': 'Başka kart başlatıldığı için sistem tarafından otomatik duraklatıldı.',
            'parenttype': 'Calisma Karti'
        },
        fields=['parent']
    )

    if not duruslar:
        return []

    parent_names = [d.parent for d in duruslar]

    cards = frappe.get_all(
        'Calisma Karti',
        filters={
            'name': ('in', parent_names),
            'operator': operator,
            'docstatus': ['<', 2],
            'bitis_saati': ('is', 'not set')
        },
        fields=['name', 'operasyon', 'urun_kodu']
    )
    
    return cards
