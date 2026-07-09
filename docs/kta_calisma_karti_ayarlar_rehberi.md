---
layout: default
title: "KTA Çalışma Kartı Konfigürasyon ve Ayarlar Rehberi"
---

<main class="container" markdown="1">

# ⚙️ KTA Çalışma Kartı Konfigürasyon ve Ayarlar Rehberi

KTA Çalışma Kartı uygulamasının davranışı, yöneticiler tarafından 3 farklı noktadan dinamik olarak yönetilir. Uygulamanın esnekliğini sağlayan tüm ayarlar, bunların ne işe yaradığı ve hangi modüllere etki ettiği aşağıda detaylandırılmıştır.

---

## 1. Genel Sistem Ayarları (`KTA Calisma Karti Settings`)

Sistemin kalbindeki ana kuralları belirler. ERPNext arama çubuğuna **KTA Calisma Karti Settings** yazarak ulaşabilirsiniz.

### ⏱️ Vardiya ve Süre Limitleri
- **Maksimum Çalışma Kartı Süresi (DK) (`max_kart_suresi_dk`):** Bir kartın en fazla kaç dakika açık (Çalışıyor) kalabileceğini belirler. (Standart: 430). Bu süreyi aşan kartlar sistem (cron) tarafından otomatik duraklatılır veya kapatılır.
- **Kart Uyarı Süresi (DK) (`kart_uyari_suresi_dk`):** Operatörün ekranında kırmızı renkli *"Vardiya Sonuna Yaklaşıyor"* uyarısının (Banner) çıkacağı dakikadır (Standart: 400).
- **Tamamlanmış İE Tolerans Süresi (Saat) (`tolerans_saat`):** ERPNext tarafında bir İş Emri kapatılsa bile, son stok hareketinin üzerinden bu kadar saat geçene kadar sahadaki operatör o iş emrine Çalışma Kartı başlatabilir.

### 🔄 Senkronizasyon ve UI Yenileme
- **Liste / Detay Yenileme Aralığı (Sn) (`liste_yenileme_araligi_sn`, `detay_yenileme_araligi_sn`):** Sahadaki tablet sayısına göre sunucu yükünü (API Rate Limit) ayarlamak için kullanılır. Frontend ekranlarının (Liste ve İç kart) arka planda veritabanını kaç saniyede bir yoklayacağını belirler.

### 🛑 Kart Geçiş ve Duruş Kontrolleri
- **Kart Geçiş Modu (`kart_gecis_modu`):**
  - **Sıkı (Hard):** Operatör mevcut kartına bir alt işlem vb. girmediyse yeni bir karta geçmesine **asla izin verilmez.**
  - **Esnek (Soft):** Operatöre uyarı verilir ancak sorumluluk onda kalmak üzere geçişine izin verilir.
- **Arıza Devam Modu (`ariza_devam_modu`):** Makine arızası bildirildiğinde, bakım ekibi arızayı kapatmadan operatörün üretime devam edip edemeyeceğini belirler.
- **Otomatik Duraklatma / Zaman Aşımı Nedeni:** Bir operatör açık bir kartı varken başka bir kartı başlattığında veya gece vardiya kapanışlarında önceki kartlar sistem tarafından durdurulur. Bu duruşlara atanacak "Duruş Sebepleri" buradan seçilir (Örn: *Zaman Aşımı* veya *Sistem Tarafından Otomatik Duraklatıldı*).

### 📧 Kalite, Yetki ve Raporlama
- **Mükerrer Kalite Kontrolü Yap:** Aynı Kalite Muayene (QI) belgesinin birden fazla çalışma kartına bağlanmasını (kilit mekanizmasıyla) engeller.
- **Günlük Hata Raporu Aktif:** Dün 5 saatin altında çalışan (verimsiz) operatörleri her sabah ilgili e-postalara ileten arka plan görevini (cron) açıp kapatır.
- **Job Card Süre Senkronizasyon Modu:** Çalışma Kartındaki sürelerin standart ERPNext Job Card'lara aktarılırken hangi katılıkta olacağını (Submit edilmişlere yazılsın/yazılmasın) belirler.
- **Kalite Kontrol Rolleri (QC Allowed Roles):** Modüler (alt operasyon bazlı) kalite onaylarında, "Onaylandı" durumuna gelmiş ve kalite belgesi (Quality Inspection) kesilmiş bir satır operatörler tarafından silinemez veya düzenlenemez. Sadece bu tabloya (KTA Calisma Karti QC Rolleri) eklenen rollere sahip kullanıcılar (Örn: *Quality Manager*, *KTA Kalite Kullanıcısı*) bu kilidi aşarak (bypass) düzenleme ve silme işlemi yapabilir.
- **Admin Kontrol Rolleri (`admin_roles`):** Virgülle ayrılarak girilen roller (Örn: *System Manager, Quality Manager, Manufacturing Manager*); "Bitmiş" statüsüne geçerek normal operatörlere kilitlenen çalışma kartlarına dışarıdan girip içindeki verileri (alt işlem ekleme, hurda silme vb.) bypass ederek değiştirebilme yetkisine sahip olur. (Not: İptal edilmiş kartlara kimse müdahale edemez).

---

## 2. Operasyon Bazlı Ayarlar (`KTA Calisma Karti Operasyonlari`)

KTA Çalışma Kartı'nın arayüzü ve zorunlulukları **seçilen operasyona göre** şekil değiştirir. Bu ayarları değiştirmek için **KTA Calisma Karti Operasyonlari** listesine girmelisiniz.

### 📊 Üretim Akışı ve Zorunluluklar
- **Miktar Bildirimi Zorunlu (`miktar_zorunlu_mu`):** İşaretliyse operatör kartı bitirirken "Tamamlanan Miktar" kısmına en az 1 yazmalıdır. İşaretli değilse, miktar alanına 0 yazarak ve yalnızca alt operasyonlar vasıtasıyla tüketim gerçekleştirerek kartı bitirebilir.
- **Tüketim Limiti Doğrulaması Aktif (`tuketim_limiti_aktif`):** Alt operasyonlarda girilen hammadde miktarının, ERPNext İş Emrindeki (BOM) izin verilen miktarı aşıp aşmadığına bakar.

### 🧩 Kalite ve Ekran Arayüzleri (Form Görünürlükleri)
Bir operasyonun içine girdiğinizde arayüzde hangi sekmelerin görüneceğini buradan açıp kapatabilirsiniz:
- **Krimp Formu Aktif:** O operasyonda *Krimp (Sıkma)* sekmesini aktif eder.
- **IDC Formu Aktif:** O operasyonda *IDC* ölçüm sekmesini aktif eder.
- **Enjeksiyon Formu Aktif:** Plastik *Enjeksiyon* ölçüm formunu aktif eder.
- **Ekran Tipi (`ekran_tipi`):** Operatörün hammadde giriş tarzını belirler. *Çoklu Hammadde* seçilirse, alt operasyon ekranında tek işlemde birden fazla hammadde kullanılmasına izin veren geniş form açılır.

### 🧪 Yeni Özellik: Modüler Kalite (Alt Operasyon Bazlı Kalite Onayı)
- **Alt Operasyon Bazlı Kalite Onayı (`alt_operasyon_bazli_kalite`):** Bu kutucuk işaretlenirse, kalite kontrol birimi "Bütün Kart" yerine, kart içindeki her bir alt operasyona (Küt, Çift Taraf vb.) satır satır onay verir. Formlar (Krimp formu vb.) bu alt operasyonların içeriğine göre sihirli şekilde (Auto-fill) dolar.
  - **Sistem Davranışı:** Bu modda ana Çalışma Kartının (parent) `quality_inspection` (Kalite Belgesi) alanı hiçbir zaman doldurulmaz; yalnızca belgenin genel durumu (`kalite_kontrol` alanı) içindeki satırların durumlarına bakılarak dinamik olarak "Onaylandı" ya da "Onay Bekliyor" olarak hesaplanır. Böylelikle klasik kalite süreciyle modüler süreç birbirine karışmaz.

> **Önemli:** Modüler kalitenin ve krimp testlerinin aktif olması için o operasyonun **Quality Inspection Template** alanında ERPNext'te tanımlanmış bir Kalite Şablonunun seçili olması şarttır!

---

## 3. Duruş Sebebi Konfigürasyonları (`KTA Durus Sebebi`)

Operatörlerin arayüzde seçtiği veya sistemin atadığı duruş nedenleri **KTA Durus Sebebi** listesinden yönetilir. 

- **Duruş Tipi (`durus_tipi`):** Planlı, Plansız veya Sistem olarak ayrılır. Dashboard raporlamalarında OEE hesaplamalarına (Kayıp Zaman vs.) etki eder.
- **Sistem Kaydı (`is_system`):** Bu kutucuk işaretliyse operatörler tabletlerinde bu nedeni göremez. Yalnızca arka plan işlemleri (Vardiya otomatik kapatma vb.) bu nedeni gizli şekilde atayabilir.
- **Grafiklerde Gizle (`exclude_from_charts`):** Günlük mola veya yemek gibi duruşların Dashboard'daki pasta grafiklerini şişirmemesi isteniyorsa bu kutucuk işaretlenir.

---

## 4. ERPNext Çekirdek (Core) Bağımlılıkları

> [!IMPORTANT]
> **Bu ayarlar KTA menüsünde veya kodlarında bulunmaz!** Bunlar ERPNext'in standart modül ayarlarıdır. Eğer operatörler sahada *"Kapasite Aşıldı"* veya *"Stok Yetersiz"* gibi sistem hataları alıyorsa, bunun sebebi KTA Çalışma Kartı kodu değil, aşağıdaki ERPNext standart kısıtlamalarıdır.

KTA Çalışma Kartı, ERPNext'in üretim ve stok altyapısı üzerine inşa edildiği için standart ERPNext ayarlarından da doğrudan etkilenir.

### 🏭 Üretim Ayarları (`Manufacturing Settings`)
- **Kapasite Planlamasını Devre Dışı Bırak (`disable_capacity_planning`):** Eğer bu seçenek işaretlenirse, Çalışma Kartı bittiğinde arka planda Job Card (İş Kartı) güncellenirken iş istasyonlarının kapasite limitleri göz ardı edilir. Bu ayar kapalıyken (yani kapasite planlaması aktifken), bir iş istasyonuna aynı saatler arasında kapasitesinden fazla Çalışma Kartı süresi yazmaya çalışırsanız sistem (Job Card override üzerinden) bunu engeller.
- **Hammadde Tüketimi (Backflush):** Sistem çalışma kartını kapatırken miktar girilirse arka planda ERPNext standartlarına göre üretim (Manufacture) stok belgesi oluşturur. Bu belgedeki varsayılan hammadde depoları ve backflush kuralları standart Üretim Ayarları'ndan okunur.

### 📦 Stok Ayarları (`Stock Settings`)
- **Stok İşlemleri:** Çalışma Kartı üzerinden verilen "Hurda" girişleri, arka planda bir `Stock Entry` (Stok Girişi/Çıkışı) belgesi oluşturur. Stok Ayarları altındaki eksi stok izinleri, isimlendirme serileri gibi kurallar Hurda girişinin başarılı olup olmayacağını doğrudan belirler. KTA modülü bu kurallara %100 sadık kalır.

---

## 🎯 Özet Tablo: Nerede Ne Yapılır?

| Sorun / İhtiyaç | Çözüm Yeri | Ne Yapılmalı? |
| :--- | :--- | :--- |
| Operatörlerin kart kapatma limiti olan 430 dakikayı değiştirmek | **KTA Calisma Karti Settings** | `max_kart_suresi_dk` değerini güncelleyin. |
| Kaliteci bir çalışma kartının verisini değiştiremiyor (Kilitli) | **KTA Calisma Karti Settings** | `admin_roles` listesine kalitecinin Frappe rolünü ekleyin. |
| X operasyonunda Krimp formunu görmek istiyoruz | **KTA Calisma Karti Operasyonlari** | İlgili operasyonu açıp `has_krimp` tikini işaretleyin. |
| Y operasyonunda her alt işleme kalite onayı vermek istiyoruz | **KTA Calisma Karti Operasyonlari** | İlgili operasyonu açıp `alt_operasyon_bazli_kalite` tikini işaretleyin. |
| Yeni bir duruş nedeni eklemek (Örn: Çay Molası) | **KTA Durus Sebebi** | Yeni kayıt açıp Planlı Duruş olarak sisteme kaydedin. |

</main>
