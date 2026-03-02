from __future__ import unicode_literals
import frappe
from frappe.utils import now_datetime, get_datetime, add_to_date
from erpnextkta import api as api

def weekly():
    api.clear_warehouse_labels()

def auto_close_timed_out_cards():
    """
    Vardiya sonlarında (örn. 16:15 ve 00:15) çalışarak KTA Calisma Karti Settings'te belirlenen dakikayı aşan
    açık Çalışma Kartlarını otomatik olarak yasal süre sınırında (başlangıç + limit) bitirir.
    """
    try:
        max_limit = frappe.db.get_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk") or 430
        max_limit = int(max_limit)
    except Exception:
        max_limit = 430

    now = now_datetime()
    # Bitmemiş ve başlatılmış kartları bul (QC Reddedildi vs hariç olması için standart durum filtresi kullanılabilir,
    # ancak en güvenlisi bitis_saati boş olanlar)
    kartlar = frappe.get_all(
        "Calisma Karti",
        filters={
            "baslangic_saati": ["is", "set"],
            "bitis_saati": ["is", "not set"],
            "docstatus": 1
        },
        fields=["name", "baslangic_saati"]
    )

    for k in kartlar:
        try:
            start_dt = get_datetime(k.baslangic_saati)
            gecen_dk = (now - start_dt).total_seconds() / 60

            # Limiti geçmişse kapat
            if gecen_dk > max_limit:
                doc = frappe.get_doc("Calisma Karti", k.name)
                # Sadece Reddedilmemiş vb. kontrolü
                if (doc.kalite_kontrol or '').strip() == 'Reddedildi':
                    continue

                limit_dt = add_to_date(start_dt, minutes=max_limit)

                # Açık duruş varsa, duruşu da limit_dt ile kapat
                if doc.duruslar:
                    last_row = doc.duruslar[-1]
                    if last_row.durus_baslangic and not last_row.durus_bitis:
                        last_row.durus_bitis = limit_dt
                        durus_start = get_datetime(last_row.durus_baslangic)
                        last_row.durus_suresi = (limit_dt - durus_start).total_seconds() / 60

                # Kartı limit_dt ile bitir
                doc.bitis_saati = limit_dt
                not_ek = "[SİSTEM: Otomatik kapatıldı - zaman aşımı]"
                doc.notlar = f"{doc.notlar}\n{not_ek}" if doc.notlar else not_ek

                # Standart süre hesaplamalarını yeniden tetikle (zaten now değil artık limit_dt kullanılacak)
                doc.save(ignore_permissions=True)
                frappe.db.commit()

        except Exception as e:
            frappe.log_error(title=f"auto_close_timed_out_cards hatası: {k.name}", message=frappe.get_traceback())
            # Diğer kartlara devam et

def delete_old_unstarted_cards():
    """
    Oluşturulmuş ancak (üzerinden 1 günden fazla zaman geçmesine rağmen)
    hiç başlatılmamış ("Hazır" durumunda bekleyen) çalışma kartlarını veritabanından tamamen siler.
    """
    now = now_datetime()
    bir_gun_once = add_to_date(now, days=-1)

    kartlar = frappe.get_all(
        "Calisma Karti",
        filters={
            "baslangic_saati": ["is", "not set"],
            "bitis_saati": ["is", "not set"],
            "docstatus": 1,
            "creation": ["<", bir_gun_once]
        },
        fields=["name"]
    )

    silinen_sayisi = 0
    for k in kartlar:
        try:
            frappe.delete_doc("Calisma Karti", k.name, ignore_permissions=True, force=True)
            silinen_sayisi += 1
        except Exception as e:
            frappe.log_error(title=f"delete_old_unstarted_cards hatası: {k.name}", message=frappe.get_traceback())

    if silinen_sayisi > 0:
        frappe.db.commit()
