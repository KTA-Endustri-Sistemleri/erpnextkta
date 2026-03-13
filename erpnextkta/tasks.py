from __future__ import unicode_literals
import frappe
from frappe.utils import now_datetime, get_datetime, add_to_date
from erpnextkta import api as api
from erpnextkta.kta_calisma_karti.realtime import publish_calisma_karti_changed

def weekly():
    api.clear_warehouse_labels()

def auto_close_timed_out_cards():
    """
    Vardiya sonlarında (örn. 16:15 ve 00:15) çalışarak KTA Calisma Karti Settings'te belirlenen dakikayı aşan
    açık Çalışma Kartlarını otomatik olarak yasal süre sınırında (başlangıç + limit) bitirir.
    """
    frappe.logger().info("auto_close_timed_out_cards started")
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

            if gecen_dk <= max_limit:
                continue

            doc = frappe.get_doc("Calisma Karti", k.name)

            # QC reddedildiyse elleşme
            if (doc.kalite_kontrol or "").strip() == "Reddedildi":
                continue

            limit_dt = add_to_date(start_dt, minutes=max_limit)

            # Açık duruş varsa, duruşu limit_dt ile kapat
            if doc.duruslar:
                last_row = doc.duruslar[-1]
                if last_row.durus_baslangic and not last_row.durus_bitis:
                    last_row.durus_bitis = limit_dt
                    durus_start = get_datetime(last_row.durus_baslangic)
                    last_row.durus_suresi = (limit_dt - durus_start).total_seconds() / 60

            # Timeout duruşu ekle (0 süreli bilgi kaydı)
            doc.append("duruslar", {
                "durus_baslangic": limit_dt,
                "durus_bitis": limit_dt,
                "durus_suresi": 0,
                "durus_nedeni": "Zaman Aşımı",
                "aciklama": f"Çalışma Kartı {max_limit} dakikadır bitirilmediği için otomatik olarak durdurulmuştur."
            })

            # Kartı bitir
            doc.bitis_saati = limit_dt

            # Süre + durum hesaplarını çalıştır (senin asıl hesap motorun burada)
            doc.update_durum()  # -> hesapla_durus_suresi + hesapla_toplam_sure + durum mapping

            # Submitted doc'ta validate/update kısıtlarını bypass
            doc.flags.ignore_validate_update_after_submit = True
            doc.save(ignore_permissions=True)

            # Read-only alanlar submitted doc'ta doc.save ile DB'ye yazılmayabiliyor.
            # islem_yap ile aynı şekilde zorla güncelle.
            frappe.db.set_value("Calisma Karti", doc.name, {
                "baslangic_saati": doc.baslangic_saati,
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
            # Diğer kartlara devam et

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
            "docstatus": 1,
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
