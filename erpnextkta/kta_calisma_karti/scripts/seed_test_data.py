"""
KTA Çalışma Kartı — Test Verisi Seed Scripti
=============================================

Kullanım (bench console):
    %run /workspace/development/kta-dev-v15/apps/erpnextkta/erpnextkta/kta_calisma_karti/scripts/seed_test_data.py

Veya bench execute ile:
    bench --site <site-adi> execute erpnextkta.kta_calisma_karti.scripts.seed_test_data.run

Ne yapar:
    - Mevcut WO/JC/Operasyon/Employee kayıtlarını kullanır
    - JK / BOSCH / RATIONAL / MTU / ARÇELİK departmanlarındaki çalışanlara kart oluşturur
    - Son 14 günde (Pazar hariç) iş günlerine dağıtır
    - 5 farklı durum: Hazır, Çalışıyor, Duruşta, Bitmiş, Reddedildi
    - creation/modified alanları da geçmiş tarihe set edilir (dashboard grafikleri için)
"""

from __future__ import annotations

import random
import frappe
from datetime import datetime, timedelta, date as date_type

# ─── Ayarlar ─────────────────────────────────────────────────────────────────
MAX_PER_DEPT = 10     # Her departmandan max operatör sayısı (toplam kadar)

# Her operatör için durum başına kart adedi
KART_DAGILIMLARI = {
    "Hazır":      2,
    "Çalışıyor":  1,
    "Duruşta":    1,
    "Bitmiş":     4,
    "Reddedildi": 1,
}

# Seed günü aralığı (bugün hariç, geriye doğru, Pazar hariç)
GECMIS_GUN_ARALIĞI = 14

# Departman filtresi — adında bu kelimelerden birini içeren departmanlar
DEPT_ANAHTAR_KELIMELERI = ["JK", "BOSCH", "RATIONAL", "MTU", "ARÇELİK", "ARCELİK", "ARCELIK"]

# Duruş nedenleri
DURUS_NEDENLERI = ["Ariza", "Malzeme Bekleme", "Kalite Kontrol", "Mola", "Bakim", "Diger"]


# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

def _is_gunleri() -> list[date_type]:
    """Son GECMIS_GUN_ARALIĞI günün Pazar olmayan günlerini döndürür (bugün hariç)."""
    bugun = datetime.now().date()
    gunler = []
    for d in range(1, GECMIS_GUN_ARALIĞI + 1):
        g = bugun - timedelta(days=d)
        if g.weekday() != 6:  # 6 = Pazar
            gunler.append(g)
    return gunler or [bugun - timedelta(days=1)]


def _rnd_dt(gun: date_type, saat_min: int = 8, saat_max: int = 16) -> datetime:
    """Belirtilen günde rastgele mesai saati döndürür."""
    saat = random.randint(saat_min, saat_max - 1)
    dk   = random.randint(0, 59)
    sn   = random.randint(0, 59)
    return datetime(gun.year, gun.month, gun.day, saat, dk, sn)


def _fmt(seconds: float) -> str:
    """Saniyeyi M:SS formatına çevirir."""
    if not seconds or seconds < 0:
        return "0:00"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _set_past_creation(docname: str, past_dt: datetime):
    """creation ve modified alanlarını geçmiş tarihe çeker (SQL — Frappe API bunu desteklemez)."""
    dt_str = past_dt.strftime("%Y-%m-%d %H:%M:%S")
    frappe.db.sql(
        "UPDATE `tabCalisma Karti` SET creation = %s, modified = %s WHERE name = %s",
        (dt_str, dt_str, docname)
    )


# ─── Kart builder'ları ────────────────────────────────────────────────────────

def _insert_and_submit(doc_dict: dict) -> "frappe.Document":
    d = frappe.get_doc(doc_dict)
    d.flags.ignore_permissions = True
    d.flags.ignore_validate = True
    d.insert()
    d.flags.ignore_validate_update_after_submit = True
    d.submit()
    return d


def build_hazir(jc, wo, op, ws, emp, gun: date_type):
    """Hazır: başlatılmamış kart."""
    bas_dt = _rnd_dt(gun, 8, 10)
    d = _insert_and_submit({
        "doctype": "Calisma Karti",
        "custom_work_order": wo, "is_karti": jc,
        "operasyon": op, "is_istasyonu": ws, "operator": emp,
    })
    frappe.db.set_value("Calisma Karti", d.name, {
        "durum": "Hazır", "kalite_kontrol": "Onay Bekliyor",
        "baslangic_saati": None, "bitis_saati": None,
        "toplam_sure": "0:00", "toplam_durus": "0:00", "net_calisma_suresi": "0:00",
    }, update_modified=False)
    _set_past_creation(d.name, bas_dt)
    return d.name


def build_calisiyor(jc, wo, op, ws, emp, gun: date_type):
    """Çalışıyor: başlatılmış, bitmemiş, aktif duruş yok."""
    bas_dt = _rnd_dt(gun, 8, 11)
    net_dk = random.randint(30, 200)
    toplam_dk = net_dk  # duruş yok
    d = _insert_and_submit({
        "doctype": "Calisma Karti",
        "custom_work_order": wo, "is_karti": jc,
        "operasyon": op, "is_istasyonu": ws, "operator": emp,
    })
    frappe.db.set_value("Calisma Karti", d.name, {
        "durum": "Çalışıyor", "kalite_kontrol": "Onay Bekliyor",
        "baslangic_saati": str(bas_dt), "bitis_saati": None,
        "toplam_sure": _fmt(toplam_dk * 60),
        "toplam_durus": "0:00",
        "net_calisma_suresi": _fmt(net_dk * 60),
    }, update_modified=False)
    _set_past_creation(d.name, bas_dt)
    return d.name


def build_durusta(jc, wo, op, ws, emp, gun: date_type):
    """Duruşta: başlatılmış, aktif açık duruşu olan kart."""
    bas_dt  = _rnd_dt(gun, 8, 11)
    # Duruş başlangıcı: kartın başlamasından 30-90 dk sonra
    durus_bas = bas_dt + timedelta(minutes=random.randint(30, 90))
    # Duruşlara durus_bitis YOK → aktif duruş
    net_dk_onceki = (durus_bas - bas_dt).total_seconds() / 60
    d = _insert_and_submit({
        "doctype": "Calisma Karti",
        "custom_work_order": wo, "is_karti": jc,
        "operasyon": op, "is_istasyonu": ws, "operator": emp,
        "duruslar": [{
            "durus_baslangic": str(durus_bas),
            "durus_bitis":     None,
            "durus_suresi":    0,
            "durus_nedeni":    random.choice(DURUS_NEDENLERI),
            "aciklama":        "Seed verisi",
        }],
    })
    frappe.db.set_value("Calisma Karti", d.name, {
        "durum": "Duruşta", "kalite_kontrol": "Onay Bekliyor",
        "baslangic_saati": str(bas_dt), "bitis_saati": None,
        "toplam_sure": _fmt(net_dk_onceki * 60),
        "toplam_durus": "0:00",
        "net_calisma_suresi": _fmt(net_dk_onceki * 60),
    }, update_modified=False)
    _set_past_creation(d.name, bas_dt)
    return d.name


def build_bitmis(jc, wo, op, ws, emp, gun: date_type, alt_op_names, hurda_items, reddedildi=False):
    """Bitmiş (veya Reddedildi): tamamlanmış kart."""
    bas_dt    = _rnd_dt(gun, 8, 12)
    toplam_dk = random.randint(60, 380)
    bit_dt    = bas_dt + timedelta(minutes=toplam_dk)

    # Duruşlar
    duruslar = []
    toplam_durus_dk = 0.0
    cursor = bas_dt + timedelta(minutes=random.randint(15, 40))
    for _ in range(random.randint(0, 3)):
        if cursor >= bit_dt - timedelta(minutes=15):
            break
        d_bas = cursor + timedelta(minutes=random.randint(5, 20))
        if d_bas >= bit_dt - timedelta(minutes=10):
            break
        d_bit = d_bas + timedelta(minutes=random.randint(5, 40))
        if d_bit >= bit_dt:
            d_bit = bit_dt - timedelta(minutes=5)
        durasi = (d_bit - d_bas).total_seconds() / 60
        duruslar.append({
            "durus_baslangic": str(d_bas),
            "durus_bitis":     str(d_bit),
            "durus_suresi":    round(durasi, 2),
            "durus_nedeni":    random.choice(DURUS_NEDENLERI),
            "aciklama":        "Seed verisi",
        })
        toplam_durus_dk += durasi
        cursor = d_bit + timedelta(minutes=random.randint(10, 30))

    net_dk = min(max(0, toplam_dk - toplam_durus_dk), 430)

    # Alt operasyonlar
    alt_op_rows = []
    if alt_op_names:
        for ao in random.sample(alt_op_names, min(random.randint(1, 3), len(alt_op_names))):
            alt_op_rows.append({"alt_operasyon": ao, "adet": random.randint(1, 20), "note": "Seed"})

    # Hurda (%40 ihtimal)
    hurda_rows = []
    if hurda_items and random.random() < 0.4:
        hurda_rows.append({
            "parca_no": random.choice(hurda_items),
            "adet": random.randint(1, 5),
            "aciklama": "Seed verisi",
        })

    kk = "Reddedildi" if reddedildi else random.choice(["Onay Bekliyor", "Onaylandı", "Onay Bekliyor"])
    durum = "Reddedildi" if reddedildi else "Bitmiş"

    d = _insert_and_submit({
        "doctype": "Calisma Karti",
        "custom_work_order": wo, "is_karti": jc,
        "operasyon": op, "is_istasyonu": ws, "operator": emp,
        "duruslar": duruslar,
        "alt_operasyon_kayitlari": alt_op_rows,
        "hurdalar": hurda_rows,
    })
    frappe.db.set_value("Calisma Karti", d.name, {
        "durum": durum, "kalite_kontrol": kk,
        "baslangic_saati":    str(bas_dt),
        "bitis_saati":        str(bit_dt),
        "tamamlanan_miktar":  random.randint(1, 50),
        "toplam_sure":        _fmt(toplam_dk * 60),
        "toplam_durus":       _fmt(toplam_durus_dk * 60),
        "net_calisma_suresi": _fmt(net_dk * 60),
    }, update_modified=False)
    _set_past_creation(d.name, bas_dt)
    return d.name


# ─── Ana fonksiyon ────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("KTA Çalışma Kartı — Test Verisi Seed başlıyor...")
    print("=" * 60)

    # ── KTA Operasyonları ─────────────────────────────────────────────────────
    operasyonlar = frappe.get_all(
        "KTA Calisma Karti Operasyonlari",
        fields=["name"], limit_page_length=200,
    )
    if not operasyonlar:
        print("❌ KTA Calisma Karti Operasyonlari bulunamadı.")
        return
    op_names = [o["name"] for o in operasyonlar]
    print(f"   ✓ {len(op_names)} KTA operasyonu")

    # ── Alt Operasyonlar ──────────────────────────────────────────────────────
    alt_ops = frappe.get_all("KTA Calisma Karti Alt Operasyonlari", fields=["name"], limit_page_length=100)
    alt_op_names = [a["name"] for a in alt_ops]
    print(f"   ✓ {len(alt_op_names)} alt operasyon")

    # ── Workstations ──────────────────────────────────────────────────────────
    workstations = frappe.get_all("Workstation", fields=["name"], limit_page_length=50)
    if not workstations:
        print("❌ Workstation bulunamadı.")
        return
    ws_names = [w["name"] for w in workstations]
    print(f"   ✓ {len(ws_names)} workstation")

    # ── Job Card'lar ──────────────────────────────────────────────────────────
    jc_list = frappe.get_all(
        "Job Card",
        filters={"docstatus": ["!=", 2]},
        fields=["name", "work_order", "workstation"],
        limit_page_length=500,
    )
    jc_list = [j for j in jc_list if j.get("work_order")]
    if not jc_list:
        print("❌ Job Card bulunamadı.")
        return
    print(f"   ✓ {len(jc_list)} Job Card")

    # ── Hurda item adayları ───────────────────────────────────────────────────
    wo_names = list({j["work_order"] for j in jc_list})
    hurda_items = []
    if wo_names:
        ri = frappe.get_all(
            "Work Order Item",
            filters={"parent": ["in", wo_names[:50]]},
            fields=["item_code"], limit_page_length=200,
        )
        hurda_items = list({r["item_code"] for r in ri if r.get("item_code")})
    print(f"   ✓ {len(hurda_items)} hurda item adayı")

    # ── İş günleri havuzu ─────────────────────────────────────────────────────
    is_gunleri = _is_gunleri()
    print(f"   ✓ {len(is_gunleri)} iş günü (son {GECMIS_GUN_ARALIĞI} gün, Pazar hariç)")

    # ── Departman bazlı Employee seçimi ───────────────────────────────────────
    all_employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name", "department"],
        limit_page_length=1000,
    )

    def _dept_eslesiyor(dept: str) -> bool:
        u = (dept or "").upper()
        return any(kw.upper() in u for kw in DEPT_ANAHTAR_KELIMELERI)

    dept_map: dict[str, list] = {}
    for emp in all_employees:
        dept = emp.get("department") or ""
        if _dept_eslesiyor(dept):
            dept_map.setdefault(dept, []).append(emp)

    selected = []
    for dept, emps in dept_map.items():
        picked = emps[:MAX_PER_DEPT]
        selected.extend(picked)
        print(f"     · {dept}: {len(picked)} kişi")

    if not selected:
        print("❌ Hedef departmanlarda aktif çalışan bulunamadı.")
        print(f"   Aranan: {DEPT_ANAHTAR_KELIMELERI}")
        return
    print(f"   ✓ Toplam {len(selected)} operatör seçildi")

    # ── Kart oluşturma ────────────────────────────────────────────────────────
    sayac = {d: 0 for d in KART_DAGILIMLARI}
    hatali = 0

    BUILDERS = {
        "Hazır":      lambda jc, wo, op, ws, emp, gun: build_hazir(jc, wo, op, ws, emp, gun),
        "Çalışıyor":  lambda jc, wo, op, ws, emp, gun: build_calisiyor(jc, wo, op, ws, emp, gun),
        "Duruşta":    lambda jc, wo, op, ws, emp, gun: build_durusta(jc, wo, op, ws, emp, gun),
        "Bitmiş":     lambda jc, wo, op, ws, emp, gun: build_bitmis(jc, wo, op, ws, emp, gun, alt_op_names, hurda_items, False),
        "Reddedildi": lambda jc, wo, op, ws, emp, gun: build_bitmis(jc, wo, op, ws, emp, gun, alt_op_names, hurda_items, True),
    }

    for emp in selected:
        emp_name  = emp["name"]
        emp_label = emp.get("employee_name") or emp_name

        for durum, adet in KART_DAGILIMLARI.items():
            builder = BUILDERS[durum]
            for _ in range(adet):
                jc  = random.choice(jc_list)
                op  = random.choice(op_names)
                ws  = jc.get("workstation") or random.choice(ws_names)
                gun = random.choice(is_gunleri)
                try:
                    builder(jc["name"], jc["work_order"], op, ws, emp_name, gun)
                    sayac[durum] += 1
                except Exception as e:
                    hatali += 1
                    print(f"     ⚠ [{durum}] atlandı [{emp_label}]: {e}")

    frappe.db.commit()

    print()
    print("=" * 60)
    print("✅ Seed tamamlandı:")
    for durum, adet in sayac.items():
        print(f"   {durum:<12}: {adet}")
    print(f"   {'Toplam':<12}: {sum(sayac.values())}")
    print(f"   {'Hatalı':<12}: {hatali}")
    print("=" * 60)


if __name__ == "__main__":
    run()
