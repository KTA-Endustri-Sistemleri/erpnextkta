import re
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime

STATU_HARITASI = {
    "hazir": "Hazır",
    "calisiyor": "Çalışıyor",
    "durusta": "Duruşta",
    "bitmis": "Bitmiş",
}

class CalismaKarti(Document):
    def autoname(self):
        """Yeni format: <WO_last5>-<operasyon>-<01..>
        - WO son 5 hane: custom_work_order varsa onu, yoksa is_karti -> work_order
        - Operasyon: boşluk ve '-' temizlenir
        - Sıra: mevcut en büyük sayının +1 (iki haneli, zfill(2))
        """
        # 1) İş Emri (Work Order) değerini bul
        wo_name = (self.get("custom_work_order") or "").strip()
        if not wo_name and (self.get("is_karti") or "").strip():
            wo_name = frappe.db.get_value("Job Card", self.is_karti, "work_order") or ""

        # 2) Son 5 hane (öncelik: sadece rakamlar; yoksa ismin son 5 karakteri)
        digits = re.sub(r"\D", "", wo_name or "")
        if digits:
            wo_tail = digits[-5:]
        else:
            wo_tail = (wo_name or "WO")[-5:] or "WO"

        # 3) Operasyon temizliği (boşluk ve tireleri kaldır)
        op_raw = self.get("operasyon") or ""
        op_clean = re.sub(r"[\s\-]+", "", op_raw).strip() or "OP"

        # 4) Prefix: <WO5>-<OP>
        prefix = f"{wo_tail}-{op_clean}"

        # 5) Mevcut en büyük sayıyı bul (sayı olarak)
        existing = frappe.db.sql(
            """
            SELECT CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED) AS idx
            FROM `tabCalisma Karti`
            WHERE name LIKE %s
            ORDER BY idx DESC
            LIMIT 1
            """,
            (f"{prefix}-%",),
            as_dict=1,
        )
        last_number = (existing[0]["idx"] if existing and existing[0]["idx"] else 0)
        new_number = int(last_number) + 1

        # 6) İsim ata: <WO5>-<OP>-<NN>
        self.name = f"{prefix}-{str(new_number).zfill(2)}"

    def validate(self):
        self.hesapla_durus_suresi()
        self.hesapla_toplam_sure()
        self.durum = STATU_HARITASI[self.get_durum()]
        if not self.kalite_kontrol:
            self.kalite_kontrol = QC_DURUM_ONAY_BEKLIYOR

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

    def hesapla_toplam_sure(self):
        if self.baslangic_saati and self.bitis_saati:
            start_dt = get_datetime(self.baslangic_saati)
            end_dt = get_datetime(self.bitis_saati)
            toplam_saniye = (end_dt - start_dt).total_seconds()
            self.toplam_sure = format_sure(toplam_saniye)

            toplam_durus_dk = sum((r.durus_suresi or 0) for r in self.duruslar)
            toplam_durus_saniye = toplam_durus_dk * 60

            net_saniye = max(0, toplam_saniye - toplam_durus_saniye)
            self.net_calisma_suresi = format_sure(net_saniye)
        else:
            self.net_calisma_suresi = "0:00"

    def aktif_durus_var_mi(self):
        if not self.duruslar:
            return False
        last_row = self.duruslar[-1]
        return last_row.durus_baslangic and not last_row.durus_bitis

    def get_durum(self):
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
def islem_yap(docname, islem_tipi, durus_nedeni=None, aciklama=None):
    doc = frappe.get_doc("Calisma Karti", docname)
    now = now_datetime()
    durum = doc.get_durum()

    if islem_tipi == "Baslat":
        if durum == 'bitmis':
            frappe.throw("Bitmiş bir işlem tekrar başlatılamaz.")
        elif durum == 'calisiyor':
            frappe.throw("İşlem zaten çalışıyor.")
        elif durum == 'hazir':
            doc.baslangic_saati = now
        elif durum == 'durusta':
            last_row = doc.duruslar[-1]
            last_row.durus_bitis = now
            start_dt = get_datetime(last_row.durus_baslangic)
            end_dt = get_datetime(last_row.durus_bitis)
            last_row.durus_suresi = (end_dt - start_dt).total_seconds() / 60

    elif islem_tipi == "Durus":
        if durum == 'bitmis':
            frappe.throw("Bitmiş bir işlemde duruş yapılamaz.")
        elif durum == 'hazir':
            frappe.throw("Henüz başlatılmamış bir işlemde duruş yapılamaz.")
        elif durum == 'durusta':
            frappe.throw("Zaten durusta.")
        elif durum == 'calisiyor':
            if not durus_nedeni:
                frappe.throw("Duruş nedeni gerekli.")
            row = doc.append("duruslar", {})
            row.durus_baslangic = now
            row.durus_nedeni = durus_nedeni
            row.aciklama = aciklama or ""

    elif islem_tipi == "Bitis":
        if durum == 'bitmis':
            frappe.throw("İşlem zaten bitmiş.")
        elif durum == 'hazir':
            frappe.throw("Başlatılmamış bir işlem bitirilemez.")
        elif durum == 'durusta':
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
        "durum": doc.get_durum()
    }
