"""
job_card_sync.py
~~~~~~~~~~~~~~~~
Çalışma Kartı'nın net çalışma süresini, bağlı Job Card'ın
``time_logs`` child tablosuna (Job Card Time Log) yansıtır.

Mantık:
    Job Card'ın ``validate_time_logs`` metodu her zaman
    ``time_in_mins = (to_time - from_time)`` hesabını yapar ve
    manuel girilen değeri ezdiğinden, doğru net süreyi elde etmek için
    ``to_time = baslangic_saati + net_calisma_suresi`` formülünü kullanırız.

    Bu sayede brüt süre yerine duruşlar düşülmüş net süre Job Card'a taşınır.
"""

import frappe
from frappe.utils import get_datetime, add_to_date


# ---------------------------------------------------------------------------
# Yardımcı
# ---------------------------------------------------------------------------

def _net_saniye(net_calisma_suresi: str) -> int:
    """'HH:MM:SS' formatındaki string'i toplam saniyeye çevirir."""
    if not net_calisma_suresi or not isinstance(net_calisma_suresi, str):
        return 0
    parts = str(net_calisma_suresi).strip().split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + int(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + int(s)
    except (ValueError, TypeError):
        pass
    return 0


# ---------------------------------------------------------------------------
# Ana fonksiyonlar
# ---------------------------------------------------------------------------

def sync_time_log_to_job_card(calisma_karti_doc) -> None:
    """
    Settings aktifse net_calisma_suresi → to_time = baslangic + net_saniye
    Job Card'a upsert eder. completed_qty aktarılmaz.
    """
    mod = frappe.db.get_single_value("KTA Calisma Karti Settings", "job_card_time_log_sync_modu")
    if not mod or mod == "Kapalı":
        return

    doc = calisma_karti_doc

    if not doc.is_karti:
        return
    if not doc.baslangic_saati:
        return
    if not doc.net_calisma_suresi:
        return

    net_sn = _net_saniye(doc.net_calisma_suresi)
    if net_sn <= 0:
        return

    baslangic_dt = get_datetime(doc.baslangic_saati)

    # to_time = baslangic_saati + net_calisma_suresi
    # → Job Card validate'i (to_time - from_time) ile time_in_mins hesaplar
    # → Duruşlar düşülmüş net süre otomatik olarak doğru çıkar
    bitis_dt = add_to_date(baslangic_dt, seconds=net_sn)

    try:
        job_card = frappe.get_doc("Job Card", doc.is_karti)
    except frappe.DoesNotExistError:
        frappe.log_error(
            title="Job Card Sync — Job Card bulunamadı",
            message=f"Calisma Karti: {doc.name}, is_karti: {doc.is_karti}",
        )
        return

    # Mevcut satırı bul (idempotent upsert)
    existing_row = None
    for row in job_card.time_logs:
        if row.get("custom_calisma_karti") == doc.name:
            existing_row = row
            break

    alt_op_str = None
    if hasattr(doc, "alt_operasyon_kayitlari") and doc.alt_operasyon_kayitlari:
        alt_ops = [r.alt_operasyon for r in doc.alt_operasyon_kayitlari if r.alt_operasyon]
        if alt_ops:
            alt_op_str = ", ".join(alt_ops)
            if len(alt_op_str) > 140:
                alt_op_str = alt_op_str[:137] + "..."

    if existing_row:
        existing_row.from_time = baslangic_dt
        existing_row.to_time = bitis_dt
        existing_row.completed_qty = 0
        existing_row.employee = doc.operator
        existing_row.custom_operasyon = doc.operasyon if hasattr(doc, "operasyon") else None
        existing_row.custom_alt_operasyon = alt_op_str
    else:
        job_card.append(
            "time_logs",
            {
                "from_time": baslangic_dt,
                "to_time": bitis_dt,
                "completed_qty": 0,
                "employee": doc.operator,
                "custom_calisma_karti": doc.name,
                "custom_operasyon": doc.operasyon if hasattr(doc, "operasyon") else None,
                "custom_alt_operasyon": alt_op_str,
            },
        )

    if mod == "Sıkı (Hard)":
        job_card.flags.ignore_validate_update_after_submit = True

    if job_card.docstatus == 0:
        # Senkronizasyon sırasında (henüz submit edilmemişse)
        # sadece zaman logları kaydediliyor; completed_qty = 0
        # dağıtımı atlayarak validate_sequence_id hatasını önle.
        job_card.flags.kta_sync_mode = True
        
    job_card.flags.ignore_permissions = True
    job_card.save()

    if job_card.docstatus == 1:
        frappe.flags.ignore_permissions = True
        job_card.update_work_order()


def remove_time_log_from_job_card(calisma_karti_doc) -> None:
    """
    Çalışma Kartı iptal edildiğinde Job Card'ın time_logs tablosundaki
    ilgili satırı temizler.
    """
    mod = frappe.db.get_single_value("KTA Calisma Karti Settings", "job_card_time_log_sync_modu")
    if not mod or mod == "Kapalı":
        return

    doc = calisma_karti_doc

    if not doc.is_karti:
        return

    try:
        job_card = frappe.get_doc("Job Card", doc.is_karti)
    except frappe.DoesNotExistError:
        return

    rows_to_keep = [
        row for row in job_card.time_logs
        if row.get("custom_calisma_karti") != doc.name
    ]

    if len(rows_to_keep) == len(job_card.time_logs):
        # Silinecek satır yok, işlem yapma
        return

    job_card.time_logs = rows_to_keep

    if mod == "Sıkı (Hard)":
        job_card.flags.ignore_validate_update_after_submit = True

    if job_card.docstatus == 0:
        # Senkronizasyon sırasında sadece zaman logları kaydediliyor; completed_qty = 0
        # dağıtımı atlayarak validate_sequence_id hatasını önle.
        job_card.flags.kta_sync_mode = True
        
    job_card.flags.ignore_permissions = True
    job_card.save()

    if job_card.docstatus == 1:
        frappe.flags.ignore_permissions = True
        job_card.update_work_order()


def distribute_completed_qty(doc, method=None):
    """
    Job Card'ın for_quantity değerini, time_logs satırlarına eşit böler.
    Küsürat kaynaklı hataları engellemek için kalan miktarı son satıra ekler.
    Bu metod hooks.py üzerinden Job Card'ın 'validate' event'ine bağlıdır.
    """
    if not doc.time_logs:
        return

    # KTA sync modunda sadece zaman logları kaydedilir; adet dağıtımı atlanır
    # (completed_qty = 0 kalır → validate_sequence_id sırası hatası oluşmaz).
    if doc.flags.get("kta_sync_mode"):
        return

    # KTA Calisma Karti Settings kontrolü
    mod = frappe.db.get_single_value("KTA Calisma Karti Settings", "job_card_time_log_sync_modu")
    if not mod or mod == "Kapalı":
        return

    total_qty = frappe.utils.flt(doc.for_quantity)
    num_logs = len(doc.time_logs)

    # Kullanıcı isteği üzerine miktar (completed_qty) 2 haneye (virgülden sonra) yuvarlanıyor
    qty_precision = 2

    total_time_in_mins = 0.0

    from frappe.utils import time_diff_in_hours

    # 1. Aşama: Tüm satırların sürelerini hesapla ve toplamı bul
    for row in doc.time_logs:
        if row.from_time and row.to_time:
            # Süreyi 2 haneye (virgülden sonra) yuvarlıyoruz ki göze temiz görünsün
            row.time_in_mins = frappe.utils.flt(time_diff_in_hours(row.to_time, row.from_time) * 60, 2)
            total_time_in_mins += row.time_in_mins
        else:
            row.time_in_mins = 0.0

    # 2. Aşama: Zamana orantılı adet dağıtımı
    base_qty = frappe.utils.flt(total_qty / num_logs, qty_precision)
    distributed_so_far = 0.0

    for i, row in enumerate(doc.time_logs):
        if total_time_in_mins > 0:
            # Zamana orantılı (Time-Proportional)
            row_weight = row.time_in_mins / total_time_in_mins
            calculated_qty = total_qty * row_weight
        else:
            # Süre hiç yoksa eski mantık (Eşit Dağıtım)
            calculated_qty = base_qty

        if i == num_logs - 1:
            # Son satıra kalanı ver
            remainder = total_qty - distributed_so_far
            if remainder < 0:
                remainder = 0.0
            row.completed_qty = frappe.utils.flt(remainder, qty_precision)
        else:
            row.completed_qty = frappe.utils.flt(calculated_qty, qty_precision)
            distributed_so_far += row.completed_qty

    doc.total_time_in_mins = total_time_in_mins
    doc.total_completed_qty = doc.for_quantity
