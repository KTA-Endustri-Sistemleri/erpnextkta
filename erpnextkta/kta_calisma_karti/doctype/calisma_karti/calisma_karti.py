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
}

def get_kta_settings():
    try:
        max_limit = frappe.db.get_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk") or 430
        warn_limit = frappe.db.get_single_value("KTA Calisma Karti Settings", "kart_uyari_suresi_dk") or 400
        return int(max_limit), int(warn_limit)
    except Exception:
        return 430, 400


def _shift_name_by_now(now_dt):
    """Pick shift name by current time-of-day (fallback when Shift Assignment is not used)."""
    t = now_dt.time()
    if time(0, 0) <= t < time(8, 0):
        return "3. Vardiya"
    elif time(8, 0) <= t < time(16, 0):
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
    """Sum net seconds of other cards for operator in shift window. Uses DB stored net_calisma_suresi."""
    if not operator or not shift_start or not shift_end:
        return 0

    rows = frappe.get_all(
        "Calisma Karti",
        filters={
            "operator": operator,
            "docstatus": ["!=", 2],  # draft (0) ve submitted (1) dahil, iptal (2) hariç
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

    def on_update_after_submit(self):
        self.on_update()

    def autoname(self):
        """
        İsim formatı: <OPR>-<WO_last5>-<Operasyon>-<01..>
        (Sayı üretimi Frappe tabSeries ile yapılır; SQL yok)
        """
        # 1) İş Emri (Work Order)
        wo_name = (self.get("custom_work_order") or "").strip()
        if not wo_name and (self.get("is_karti") or "").strip():
            wo_name = frappe.db.get_value("Job Card", self.is_karti, "work_order") or ""

        # 2) WO son 5 hane (öncelik: rakamlar)
        digits = re.sub(r"\D", "", wo_name or "")
        if digits:
            wo_tail = digits[-5:]
        else:
            wo_tail = (wo_name or "WO")[-5:] or "WO"

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
        self.update_durum()
        if not self.kalite_kontrol:
            self.kalite_kontrol = "Onay Bekliyor"

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

    def hesapla_toplam_sure(self):
        if self.baslangic_saati:
            start_dt = get_datetime(self.baslangic_saati)
            end_dt = get_datetime(self.bitis_saati) if self.bitis_saati else now_datetime()

            toplam_saniye = (end_dt - start_dt).total_seconds()
            toplam_durus_dk = sum((r.durus_suresi or 0) for r in self.duruslar)
            toplam_durus_saniye = toplam_durus_dk * 60

            net_saniye = max(0, toplam_saniye - toplam_durus_saniye)

            # If there is an active stop, subtract its progress from net_saniye as well
            if self.aktif_durus_var_mi():
                last_durus = self.duruslar[-1]
                durus_start = get_datetime(last_durus.durus_baslangic)
                active_durus_seconds = (end_dt - durus_start).total_seconds()
                net_saniye = max(0, net_saniye - active_durus_seconds)

            # --- NEW: Shift total limit (operator total within current shift) ---
            max_limit, _ = get_kta_settings()
            ws, we = _shift_window(end_dt)
            other_net = _other_cards_net_seconds_in_shift(
                operator=self.operator,
                shift_start=ws,
                shift_end=we,
                exclude_name=self.name,
            )
            remaining = max(0, (max_limit * 60) - other_net)
            net_saniye = min(net_saniye, remaining)

            # Sınırlandırma (Hard Limit) - keep as safety net
            max_saniye = max_limit * 60
            if net_saniye > max_saniye:
                net_saniye = max_saniye

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

    ck_doc = frappe.get_doc("Calisma Karti", calisma_karti)
    if not ck_doc:
        frappe.throw(_("Çalışma kartı bulunamadı."))
        
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
        # Append new task
        new_task = asset_maint.append("asset_maintenance_tasks", {})
        new_task.maintenance_task = task_name
        new_task.maintenance_type = "Arıza Bakımı" 
        new_task.maintenance_status = "Arıza Bildirimi"
        new_task.start_date = today()
        new_task.end_date = frappe.utils.add_days(today(), 1) # Prevent recurrence for one-off breakdowns
        new_task.periodicity = "Daily" # Just a placeholder since it's required
        new_task.description = aciklama
        
        # Atama yapılacak kişiyi maintenance_manager veya ilk member seçelim
        if asset_maint.maintenance_manager:
            new_task.assign_to = asset_maint.maintenance_manager
        else:
            team_members = frappe.db.get_values("Maintenance Team Member", {"parent": asset_maint.maintenance_team}, "team_member")
            if team_members:
                new_task.assign_to = team_members[0][0]
                
        asset_maint.save(ignore_permissions=True)
        # after save, get the actual task row name
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
    aml.submit()
    
    # Optional: Send notification or ToDo if assign_tasks in asset_maintenance.py doesn't cover this specific status properly
    
    return aml.name

