from __future__ import unicode_literals
import frappe
from frappe.utils import now_datetime, get_datetime, add_to_date
from erpnextkta import api as api
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed
from erpnextkta.kta_calisma_karti.api_impl.cards import _submit_linked_quality_inspection
from datetime import datetime, time

from erpnextkta.kta_stock.label_manager import clear_warehouse_labels

def weekly():
    clear_warehouse_labels()

def auto_close_timed_out_cards():
    """
    Vardiya sonlarında çalışarak açık kalan kartları akıllıca kapatır:
    - 'Duruşta' olanlar: Son duruş başlangıç saatinde kapatılır.
    - 'Çalışıyor' olanlar: Vardiya bitiş saatinde (16:00 veya 00:00) kapatılır.
    """
    frappe.logger().info("auto_close_timed_out_cards started")
    
    now = now_datetime()
    t = now.time()
    
    # Hedef vardiya sonunu belirle (16:15 civarı çalışıyorsa 16:00, 00:15 civarı ise 00:00)
    if time(16, 0) <= t < time(17, 0):
        target_end_time = time(16, 0)
    else:
        target_end_time = time(0, 0)
    
    target_dt = get_datetime(datetime.combine(now.date(), target_end_time))
    # Eğer 00:00 ise ve şu an 00:15 ise, tarih bugündür. 
    # Ama eğer bir önceki günün 00:15'ini hedefliyaksak logic değişir, 
    # ancak mevcut scheduler 15 dakika sonra çalıştığı için bugünün tarihi doğrudur.

    kartlar = frappe.get_all(
        "Calisma Karti",
        filters={
            "baslangic_saati": ["is", "set"],
            "bitis_saati": ["is", "not set"],
            "docstatus": ["!=", 2]
        },
        fields=["name", "baslangic_saati"]
    )

    for k in kartlar:
        try:
            doc = frappe.get_doc("Calisma Karti", k.name)
            
            # Eğer kart, hedef vardiya bitiş saatinden SONRA başlamışsa, bu vardiya kapatmasına dahil etme.
            if get_datetime(doc.baslangic_saati) >= target_dt:
                continue

            # QC reddedildiyse dokunma
            if (doc.kalite_kontrol or "").strip() == "Reddedildi":
                continue

            # Duruma göre bitiş saatini belirle
            if doc.aktif_durus_var_mi():
                # Duruşta olanlar için: Duruşun başladığı an
                last_row = doc.duruslar[-1]
                close_dt = get_datetime(last_row.durus_baslangic)
                
                # Açık duruşu da kapat
                last_row.durus_bitis = close_dt
                last_row.durus_suresi = 0
            else:
                # Çalışıyor olanlar için: Vardiya sonu
                close_dt = target_dt
                # Eğer kart vardiyadan sonra başladıysa (garip durum), close_dt'yi şimdi yap
                if get_datetime(doc.baslangic_saati) > close_dt:
                     close_dt = now

            # Kartı bitir
            doc.bitis_saati = close_dt
            
            # Timeout duruşu ekle (Bilgi amaçlı, 0 süreli)
            t_reason = frappe.db.get_single_value("KTA Calisma Karti Settings", "timeout_durus_nedeni")
            if not t_reason:
                t_reason = "Zaman Aşımı"

            doc.append("duruslar", {
                "durus_baslangic": close_dt,
                "durus_bitis": close_dt,
                "durus_suresi": 0,
                "durus_nedeni": t_reason,
                "aciklama": "Vardiya sonunda açık unutulduğu için sistem tarafından otomatik kapatılmıştır."
            })

            # Süre + durum hesaplarını çalıştır
            doc.update_durum()

            # Bağlı kalite belgesini onayla
            _submit_linked_quality_inspection(doc)

            if doc.docstatus == 1:
                doc.flags.ignore_validate_update_after_submit = True
            doc.save(ignore_permissions=True)

            # DB zorunlu güncelleme
            frappe.db.set_value("Calisma Karti", doc.name, {
                "bitis_saati": doc.bitis_saati,
                "durum": doc.durum,
                "toplam_sure": doc.toplam_sure,
                "toplam_durus": doc.toplam_durus,
                "net_calisma_suresi": doc.net_calisma_suresi,
            }, update_modified=False)
            
            frappe.db.commit()
            publish_calisma_karti_changed(doc.name, reason="scheduler:auto_close")

        except Exception as e:
            frappe.log_error(title=f"auto_close_timed_out_cards hatası: {k.name}", message=frappe.get_traceback())

def delete_old_unstarted_cards():
    frappe.logger().info("delete_old_unstarted_cards started")
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
            "docstatus": ["!=", 2],  # draft (0) ve submitted (1) dahil
            "creation": ["<", bir_gun_once]
        },
        fields=["name"]
    )

    silinen_sayisi = 0
    for k in kartlar:
        try:
            doc = frappe.get_doc("Calisma Karti", k.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Calisma Karti", k.name, ignore_permissions=True, force=True)
            silinen_sayisi += 1
        except Exception as e:
            frappe.log_error(title=f"delete_old_unstarted_cards hatası: {k.name}", message=frappe.get_traceback())

    if silinen_sayisi > 0:
        frappe.db.commit()
