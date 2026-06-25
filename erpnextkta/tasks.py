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

def submit_draft_calisma_kartlari():
    """
    Haftalık olarak çalışıp, 'Draft' durumunda (docstatus=0) kalmış ve 
    kapatılmış (bitis_saati dolu) Çalışma Kartlarını otomatik olarak submit eder.
    """
    frappe.logger().info("submit_draft_calisma_kartlari started")
    
    kartlar = frappe.get_all(
        "Calisma Karti",
        filters={
            "docstatus": 0,
            "bitis_saati": ["is", "set"]
        },
        fields=["name"]
    )

    for k in kartlar:
        try:
            doc = frappe.get_doc("Calisma Karti", k.name)
            doc.submit()
            frappe.db.commit()
            publish_calisma_karti_changed(doc.name, reason="scheduler:weekly_submit")
        except Exception as e:
            frappe.db.rollback()
            frappe.log_error(title=f"submit_draft_calisma_kartlari hatası: {k.name}", message=frappe.get_traceback())

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
    hedef_zaman = get_datetime(datetime.combine(now.date(), time.min))

    kartlar = frappe.get_all(
        "Calisma Karti",
        filters={
            "baslangic_saati": ["is", "not set"],
            "bitis_saati": ["is", "not set"],
            "docstatus": ["!=", 2],  # draft (0) ve submitted (1) dahil
            "creation": ["<", hedef_zaman]
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


def send_daily_calisma_karti_error_report():
    """
    Günlük olarak çalışıp, bir önceki güne ait hatalı/uyumsuz kart işlemlerini analiz eder
    ve amirlere e-posta olarak gönderir.
    """
    frappe.logger().info("send_daily_calisma_karti_error_report started")

    # 1. Ayarları oku
    hata_raporu_aktif = frappe.db.get_single_value("KTA Calisma Karti Settings", "hata_raporu_aktif")
    hata_raporu_alicilari = frappe.db.get_single_value("KTA Calisma Karti Settings", "hata_raporu_alicilari")

    # Hata raporu aktif değilse veya alıcı e-postası belirtilmemişse sonlandır
    if not hata_raporu_aktif or not hata_raporu_alicilari:
        frappe.logger().info("send_daily_calisma_karti_error_report: Rapor aktif değil ya da alıcı bulunamadı. Kapatılıyor.")
        return

    # E-postaları listeye dönüştür
    recipients = [email.strip() for email in hata_raporu_alicilari.split(",") if email.strip()]
    if not recipients:
        frappe.logger().info("send_daily_calisma_karti_error_report: Geçerli alıcı e-postası bulunamadı.")
        return

    # 2. Zaman aralığını hesapla (Bir önceki gün)
    yesterday = add_to_date(now_datetime(), days=-1).date()
    start_time = datetime.combine(yesterday, time.min)
    end_time = datetime.combine(yesterday, time.max)

    # 3. Çalışma kartlarını çek
    cards = frappe.get_all(
        "Calisma Karti",
        filters={
            "docstatus": ["<", 2],
            "baslangic_saati": ["between", [start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S")]]
        },
        fields=[
            "name", "operator", "baslangic_saati", "bitis_saati", 
            "toplam_sure", "toplam_durus", "net_calisma_suresi", 
            "kalite_kontrol", "durum", "creation"
        ]
    )

    if not cards:
        frappe.logger().info("send_daily_calisma_karti_error_report: Dün hiç çalışma kartı oluşturulmamış.")
        return

    # Yardımcı fonksiyonlar
    def parse_time_str(val):
        if not val or not isinstance(val, str):
            return 0
        s = val.strip()
        if ":" not in s:
            return 0
        parts = s.split(":")
        try:
            if len(parts) == 3:
                h, m, sec = parts
                return int(h) * 3600 + int(m) * 60 + int(sec)
            elif len(parts) == 2:
                m, sec = parts
                return int(m) * 60 + int(sec)
        except Exception:
            pass
        return 0

    def format_seconds(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def get_dt_obj(val):
        if not val:
            return None
        if isinstance(val, datetime):
            return val
        try:
            return datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    # Operatör bazlı gruplama
    op_cards = {}
    for c in cards:
        if not c.operator or not c.baslangic_saati:
            continue
        if c.operator not in op_cards:
            op_cards[c.operator] = []
        op_cards[c.operator].append(c)

    results = []
    threshold_seconds = 5 * 3600  # 5 hours

    for op, op_group in op_cards.items():
        # Başlangıç saatine göre kronolojik sırala
        op_group.sort(key=lambda x: get_dt_obj(x.baslangic_saati) or datetime.min)
        
        total_net_seconds = 0
        total_durus_seconds = 0
        total_span_seconds = 0
        
        card_details = []
        for c in op_group:
            net_sec = parse_time_str(c.net_calisma_suresi)
            durus_sec = parse_time_str(c.toplam_durus)
            span_sec = parse_time_str(c.toplam_sure)
            
            total_net_seconds += net_sec
            total_durus_seconds += durus_sec
            total_span_seconds += span_sec
            
            c_creation_dt = get_dt_obj(c.creation)
            c_c_str = c_creation_dt.strftime("%H:%M:%S") if c_creation_dt else "Bilinmiyor"
            
            card_details.append({
                "name": c.name,
                "creation": c_c_str,
                "start": get_dt_obj(c.baslangic_saati).strftime("%H:%M:%S") if c.baslangic_saati else "Bilinmiyor",
                "end": get_dt_obj(c.bitis_saati).strftime("%H:%M:%S") if c.bitis_saati else "Açık",
                "toplam_sure": c.toplam_sure,
                "toplam_durus": c.toplam_durus,
                "net_calisma": c.net_calisma_suresi,
                "status": c.durum
            })

        if total_net_seconds < threshold_seconds:
            results.append({
                "operator": op,
                "total_net_seconds": total_net_seconds,
                "total_durus_seconds": total_durus_seconds,
                "total_span_seconds": total_span_seconds,
                "cards_count": len(op_group),
                "cards": card_details
            })

    # Eğer 5 saat altı çalışan yoksa e-posta gönderme
    if not results:
        frappe.logger().info("send_daily_calisma_karti_error_report: Dün 5 saat altı çalışan operatör bulunamadı.")
        return

    # Sırala (en az çalışan üstte olacak şekilde net saniyeye göre artan)
    results.sort(key=lambda x: x["total_net_seconds"])

    # 4. HTML E-posta İçeriğini Oluştur
    formatted_date = yesterday.strftime("%d-%m-%Y")
    
    html = f"""
    <h3>KTA Günlük 5 Saat Altı Çalışan Operatörler Bildirim Raporu ({formatted_date})</h3>
    <p>Merhaba,</p>
    <p>Dün ({formatted_date}) günlük çalışma hedefi olan <b>7 saat 10 dakikayı</b> dolduramayıp, <b>5 saatin altında</b> kalan operatörlerin listesi aşağıdadır.</p>
    
    <h4>1. Özet Tablo (Operatör Bazlı)</h4>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; font-family: Segoe UI, sans-serif; width: 100%;">
        <thead>
            <tr style="background-color: #800000; color: white;">
                <th>Sıra</th>
                <th>Operatör</th>
                <th>Kart Sayısı</th>
                <th>Günlük Toplam Duruş</th>
                <th>Günlük Toplam Süre (Span)</th>
                <th>Günlük Net Çalışma</th>
            </tr>
        </thead>
        <tbody>
    """
    for idx, r in enumerate(results, 1):
        html += f"""
            <tr>
                <td align="center">{idx}</td>
                <td><b>{r["operator"]}</b></td>
                <td align="center">{r["cards_count"]}</td>
                <td align="center">{format_seconds(r["total_durus_seconds"])}</td>
                <td align="center">{format_seconds(r["total_span_seconds"])}</td>
                <td align="center" style="font-weight: bold; color: #800000;">{format_seconds(r["total_net_seconds"])}</td>
            </tr>
        """
    html += """
        </tbody>
    </table>
    
    <br>
    <h4>2. Operatör Bazlı Kart Detayları</h4>
    """
    for r in results:
        html += f"""
        <div style="margin-top: 15px; border-bottom: 2px solid #ddd; padding-bottom: 10px;">
            <p style="font-size: 14px; font-weight: bold; color: #2c3e50; margin: 5px 0;">
                👤 {r["operator"]} &mdash; Günlük Net Çalışma: <span style="color: #800000;">{format_seconds(r["total_net_seconds"])}</span>
            </p>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; font-family: Segoe UI, sans-serif; width: 100%; font-size: 11px;">
                <thead>
                    <tr style="background-color: #4F5D73; color: white;">
                        <th>Kart Adı</th>
                        <th>Oluşturulma</th>
                        <th>Başlangıç</th>
                        <th>Bitiş</th>
                        <th>Toplam Süre</th>
                        <th>Toplam Duruş</th>
                        <th>Net Çalışma</th>
                        <th>Durum</th>
                    </tr>
                </thead>
                <tbody>
        """
        for card in r["cards"]:
            html += f"""
                    <tr>
                        <td>{card["name"]}</td>
                        <td align="center">{card["creation"]}</td>
                        <td align="center">{card["start"]}</td>
                        <td align="center">{card["end"]}</td>
                        <td align="center">{card["toplam_sure"]}</td>
                        <td align="center">{card["toplam_durus"]}</td>
                        <td align="center">{card["net_calisma"]}</td>
                        <td align="center">{card["status"]}</td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """

    html += """
    <br>
    <p><i>Not: Bu rapor sistem tarafından otomatik olarak üretilmiştir. Detaylı analizler için ERPNext panelini veya ilgili veri dosyalarını inceleyebilirsiniz.</i></p>
    """

    # 5. E-postayı Gönder
    frappe.sendmail(
        recipients=recipients,
        subject=f"KTA Günlük 5 Saat Altı Çalışan Operatörler Bildirimi ({formatted_date})",
        message=html,
        header=[f"5 Saat Altı Çalışan Operatörler - {formatted_date}", "red"]
    )
    frappe.logger().info(f"send_daily_calisma_karti_error_report: E-posta {len(recipients)} alıcıya başarıyla gönderildi.")

