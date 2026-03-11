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
    """Parse 'M:SS' into total seconds. Returns 0 on invalid input."""
    if not value:
        return 0
    s = str(value).strip()
    if ":" not in s:
        return 0
    m, sec = s.split(":", 1)
    try:
        return int(m) * 60 + int(sec)
    except Exception:
        return 0


def _other_cards_net_seconds_in_shift(operator: str, shift_start, shift_end, exclude_name: str) -> int:
    """Sum net seconds of other cards for operator in shift window. Uses DB stored net_calisma_suresi."""
    if not operator or not shift_start or not shift_end:
        return 0

    rows = frappe.get_all(
        "Calisma Karti",
        filters={
            "operator": operator,
            "docstatus": 1,
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
    if not seconds or seconds < 0:
        return "0:00"
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes}:{seconds:02d}"

@frappe.whitelist()
def islem_yap(docname, islem_tipi, durus_nedeni=None, aciklama=None, tamamlanan_miktar=None):
    from erpnextkta.kta_calisma_karti.api_impl.cards import islem_yap as api_islem_yap
    return api_islem_yap(docname, islem_tipi, durus_nedeni, aciklama, tamamlanan_miktar)
    doc = frappe.get_doc("Calisma Karti", docname)
    now = now_datetime()
    durum = doc.get_durum()


    # Block any actions on rejected cards
    if (doc.kalite_kontrol or '').strip() == 'Reddedildi':
        frappe.throw('Reddedilmiş çalışma kartında işlem yapılamaz.')

    # English comments as requested
    # Parse optional completed qty entered during stop action
    qty = 0.0
    if tamamlanan_miktar is not None and str(tamamlanan_miktar).strip() != "":
        try:
            qty = float(tamamlanan_miktar)
        except Exception:
            frappe.throw("Tamamlanan miktar sayısal olmalıdır.")
        if qty < 0:
            frappe.throw("Tamamlanan miktar negatif olamaz.")

    if islem_tipi == "Baslat":
        if durum == "bitmis":
            frappe.throw("Bitmiş bir işlem tekrar başlatılamaz.")
        elif durum == "calisiyor":
            frappe.throw("İşlem zaten çalışıyor.")
        elif durum == "hazir":
            # BOARD DOĞRULAMA KONTROLÜ
            if doc.operasyon:
                operasyon_doc = frappe.get_doc("KTA Calisma Karti Operasyonlari", doc.operasyon)
                if operasyon_doc.board_dogrulamasi_gerektirir:
                    if not doc.test_masasi_dogrulama_kaydi:
                        frappe.throw("Bu operasyon için Test Masası Doğrulama Kaydı zorunludur. Lütfen önce 'Bord Doğrulama Yap' butonu ile doğrulama işlemini tamamlayın.")
                    
                    # (Opsiyonel) Eğer Test Masası Doğrulama Kaydı'nın da kendi içinde bir "onay" mekanizması eklendiyse kontrol edilebilir.
                    # Şimdilik sadece belgenin varlığını kontrol ediyoruz.

            doc.baslangic_saati = now
        elif durum == "durusta":
            if not doc.duruslar:
                frappe.throw("Duruş kaydı bulunamadı.")
            last_row = doc.duruslar[-1]
            last_row.durus_bitis = now
            start_dt = get_datetime(last_row.durus_baslangic)
            end_dt = get_datetime(last_row.durus_bitis)
            last_row.durus_suresi = (end_dt - start_dt).total_seconds() / 60

    elif islem_tipi == "Durus":
        if durum == "bitmis":
            frappe.throw("Bitmiş bir işlemde duruş yapılamaz.")
        elif durum == "hazir":
            frappe.throw("Henüz başlatılmamış bir işlemde duruş yapılamaz.")
        elif durum == "durusta":
            frappe.throw("Zaten duruşta.")
        elif durum == "calisiyor":
            if not durus_nedeni:
                frappe.throw("Duruş nedeni gerekli.")
            row = doc.append("duruslar", {})
            row.durus_baslangic = now
            row.durus_nedeni = durus_nedeni
            row.aciklama = aciklama or ""

            # Add to parent total if provided
            if qty > 0:
                doc.tamamlanan_miktar = float(doc.tamamlanan_miktar or 0) + qty

    elif islem_tipi == "Bitis":
        if durum == "bitmis":
            frappe.throw("İşlem zaten bitmiş.")
        elif durum == "hazir":
            frappe.throw("Başlatılmamış bir işlem bitirilemez.")
        # QC gate: must be approved to finish
        if (doc.kalite_kontrol or "").strip() != "Onaylandı":
            frappe.throw("Kalite kontrol onaylanmadan işlem bitirilemez.")

        # ✅ NEW (Option A): allow adding completed qty on finish as well
        if qty > 0:
            doc.tamamlanan_miktar = float(doc.tamamlanan_miktar or 0) + qty

        # Business rule: must have completed qty > 0 to finish
        total_done = float(doc.tamamlanan_miktar or 0)
        if total_done <= 0:
            frappe.throw("Bitirmek için tamamlanan miktar 0'dan büyük olmalı. Duruş sırasında tamamlanan adet girin.")

        if durum == "durusta":
            if not doc.duruslar:
                frappe.throw("Duruş kaydı bulunamadı.")
            last_row = doc.duruslar[-1]
            last_row.durus_bitis = now
            start_dt = get_datetime(last_row.durus_baslangic)
            end_dt = get_datetime(last_row.durus_bitis)
            last_row.durus_suresi = (end_dt - start_dt).total_seconds() / 60

        doc.bitis_saati = now

    else:
        frappe.throw(f"Geçersiz işlem tipi: {islem_tipi}. Geçerli değerler: Baslat, Durus, Bitis")

    doc.hesapla_durus_suresi()
    doc.hesapla_toplam_sure()
    doc.save()
    frappe.db.commit()

    return {
        "status": "success",
        "message": f"{islem_tipi} işlemi başarıyla tamamlandı.",
        "durum": doc.get_durum(),
        "tamamlanan_miktar": float(doc.tamamlanan_miktar or 0),
    }
