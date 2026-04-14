---
layout: default
title: "KTA Çalışma Kartı Kullanım Kılavuzu"
---

<main class="container" markdown="1">

# 📋 KTA Çalışma Kartı Kullanım Kılavuzu

**KTA Çalışma Kartı**, operatörlerin sahada üretim süreçlerini gerçek zamanlı olarak takip etmelerini, süreleri ölçmelerini, hurdaları ve ölçümleri kaydetmelerini sağlayan özel üretim arayüzüdür.

## 🌟 Modern SPA ve Kullanıcı Deneyimi (UI/UX)

Çalışma Kartı arayüzü, operatör kullanım kolaylığını en üst düzeye çıkarmak için modern bir **Single Page Application (SPA)** mimarisiyle çalışır.
- **Glassmorphism (Yarı Saydam Cam Efekti):** Arayüz, derinlik hissi veren, hem Açık (Light) hem de Koyu (Dark) temalara tam uyum gösteren *Soft UI* kart ve buton tasarımlarına sahiptir. 
- **Akıcı Tab Geçişleri:** Kalite, Hurda, Alt İşlem gibi alt sayfalar arasında hiçbir sayfa yenilenmesi olmadan, yüksek performanslı donanımsal (hardware-accelerated) kayma animasyonlarıyla pürüzsüzce geçiş yapılır.
- **Dinamik Geri Bildirim:** Kalite Kontrol sekmesi gibi alanlar, işlem durumlarına ("Onaylandı" - Yeşil, "Reddedildi" - Kırmızı) göre dinamik olarak renk değiştirerek kullanıcıya anında görsel onay sunar.
- **Mobil Öncelikli Endüstriyel Tasarım:** Çok dar (321px ve altı) ekranlı endüstriyel el terminallerinde bile yatay taşma yapmadan, bilgileri CSS Grid yapısıyla alt alta düzenleyerek mükemmel okunabilirlik sağlar.

---

## 🚀 1. Çalışma Kartı Oluşturma ve Başlatma

Çalışma Kartı, ERPNext'teki İş Emri (Work Order) ve İş Kartı (Job Card) temel alınarak oluşturulur.

### Kart Oluşturma Adımları:
1. **İş Kartı Seçimi:** QR kod okutarak veya listeden "İş Kartı" (`Job Card`) seçerek başlayın. İş Emri ve Üretilecek Ürün bilgileri otomatik olarak gelecektir. (Sistem akıllı barkod desteği ile `2026-X` gibi kısa girişleri otomatik tamamlar).
2. **Operasyon Seçimi:** Yapılacak işlemi (örneğin: *Kablo Kesme ve Kontak Basma*) seçin.
3. **İş İstasyonu ve Operatör:** Hangi istasyonda çalışılacağını ve operatörü belirleyin.
4. **Oluştur:** "Oluştur" butonuna basarak kartı sisteme kaydedin. Kart, başlangıçta **"Taslak" (Draft)** durumunda ve **"Hazır"** statüsünde bekleyecektir.

### Kartı Başlatma:
Kartı oluşturduktan sonra içine girip, üst kısımdaki **"Başlat"** butonuna basın. Durum **"Çalışıyor"** olarak güncellenecek ve süre sayacı başlayacaktır.

> **Önemli Kural (Kartın Bitirilmesi ve Veri Doğrulama):**
> Bir operatör hesabında yeni bir kart başlatıldığında, açıkta kalan diğer kartlar sistem tarafından otomatik olarak mola (Duruş) statüsüne alınır; yani sistem yeni bir karta geçiş yapmanıza her koşulda izin verecektir.
> **Ancak**, bir çalışma kartını tamamen *Bitirmek* (Kapatmak) istediğinizde; eğer kalite onayı alınmamışsa veya yapılması zorunlu alt operasyon kayıtları girilmemişse sistem hata verecek ve kartı bitirmenize izin vermeyecektir. İlgili kalite onayı ve alt veri girişleri tamamlandıktan sonra kart kapatılabilir.

---

## ⏸️ 2. Mola ve Duruş İşlemleri

Üretime ara vermeniz gerektiğinde (yemek, çay molası, arıza vb.) çalışma kartını duraklatmalısınız.

1. **Durdur Butonu:** Kart içindeyken **"Durdur"** butonuna basın.
2. **Duruş Nedeni:** Açılan ekrandan duruş nedeninizi seçin (Çay Molası, Yemek, Makine Arızası, vs.).
3. Kartın durumu **"Duruşta"** olarak güncellenir. Bu süre boyunca çalışılan net süre sayacı ilerlemez.
4. İşe tekrar dönüldüğünde **"Devam Et" (Başlat)** butonuna basarak kaldığınız yerden süre saymaya devam edebilirsiniz.

> **Güvenlik Sınırı:** Bir çalışma kartı açık unutulsa bile sistem en fazla vardiya sınırlarına (Örn: 430 dakika) kadar çalışmasına izin verir. Bu süreyi aşan kartlar arka planda sistem tarafından otomatik olarak mola/duruş durumuna alınır ve kırmızı uyarı banner'ı ile bildirilir.

---

## 🧩 3. Alt Operasyon Ekleme

Bir çalışma kartı içinde, daha spesifik alt işlemler veya malzeme kullanımları yapılıyorsa "Alt İşlemler" paneli kullanılır.

1. Kart içindeki **Alt İşlemler** sekmesine geçin.
2. Sağ üstteki **"Alt İşlem Ekle"** butonuna basın. *(Bu buton yalnızca kart "Çalışıyor" veya "Duruşta" ise görünür).*
3. **İşlem Tipi:** Uygulanan spesifik alt operasyonu listeden seçin. (Sistem karmaşık kodlar yerine kolay anlaşılır **Başlıklar** üzerinden seçim yapmanızı sağlar).
4. **Hammadde (Opsiyonel):** Eğer bu adımda spesifik bir malzeme girilecekse, sistem sadece bu operasyon için izin verilen malzemelerin (Örn: terminal, kablo vb.) listesini sunacaktır.
5. Kullanılan miktarı girin ve kaydedin. Her yeni eklenen alt işlem, geçmişte eklenenlere göre ve operasyon tanımlarındaki master sıralamaya (sequence) göre dizilir.

---

## 🗑️ 4. Hurda Bildirimi

Üretim sırasında fire/hurda verilirse sisteme kaydedilmelidir.

1. Kart içindeki **Hurda** sekmesine geçin.
2. **"Hurda Ekle"** butonuna basın.
3. Listede sadece bulunduğunuz iş emrine/operasyona bağlı malzemeleri (`BOM`) görebilirsiniz.
4. Hurdası verilen **Parça No**, **Miktar** ve **Hurda Nedeni** seçeneklerini doldurup kaydedin. 

---

## 📐 5. Kalite Kontrol (QC) ve IDC Ölçümleri

Kalite yetkilileri veya operatörler tarafından üründen alınan spesifik ölçümler buraya kaydedilir.

1. **Ölçümler (IDC vb.) Sekmesi:** "**IDC Ölçüleri**" tablosuna gelin ve satır ekleyin. 
2. Yalnızca *120-IDC Connector* veya *110-Connector* grubu içindeki hammaddeler IDC çekme ve yükseklik ölçümlerine konu edilebilir. Ölçüm değerlerini girerek onaylayın.
3. **Kalite Statüsü ve Belge Bağlantısı:**
    - Bir çalışma kartına standart kalite şablonu üzerinden belge bağlandığında, arayüzdeki kalite butonları **otomatik olarak kilitlenir**.
    - Bu aşamadan sonra kalite durumu sadece ilgili **Kalite Belgesi (Quality Inspection)** üzerinden yönetilir. "Görüntüle" butonu ile ilgili belgeye hızlıca ulaşılabilir.
4. **Statü Restorasyonu (Geri Dönüş):**
    - Bir kartın durumu *"Reddedildi"* yapıldığında, çalışma kartı tümüyle kilitlenerek üretim durdurulur.
    - Kalite yetkilisi Kalite Belgesi'nin durumunu tekrar *"Kabul Edildi"* (Accepted) durumuna çekerse, Çalışma Kartı'nın durumu **otomatik olarak eski haline** (Çalışıyor, Duruşta vb.) restore edilir.

---

---
## 🛠️ 6. Makine Günlük Bakım Onayı

Operatörlerin işe başlamadan önce veya vardiya sırasında kullandıkları makinenin (Asset) bakım kontrollerini yapmalarını sağlar.

1. **Bakım Sekmesi:** Kart içindeki **Bakım** sekmesine geçin.
2. **Talimat Görüntüleme:** İlgili makineye ait güncel bakım talimatı (Örn: `Bakım Talimatı - PTR.BT.049`) ekranda liste şeklinde görünecektir.
3. **Onay Verme:** Talimattaki maddeleri kontrol ettikten sonra, makineyi seçip "Bakım Yapıldı" onayını vererek kaydedin. Bu işlem arka planda resmi bir *Makine Günlük Bakım Formu* oluşturur.

---

## ✅ 7. Kartı Bitirme ve Vardiya Sonu

Üretim tamamlandığında veya vardiya sona erdiğinde işi kapatmak için kullanılır.

### Manuel Bitirme:
1. **"Bitir" Butonu:** İşlem bittiğinde **Bitir** butonuna tıklayın.
2. **Miktar Bildirimi:** Üretilen miktarı girin. Operasyon tanımına göre miktar girişi zorunlu olabilir. 0 girerek kapatma izni operasyon ayarına bağlıdır.

### Otomatik Vardiya Sonu Kapatma (Akıllı Kapatma):
Kartı açık unutmanız durumunda sistem vardiya sonlarında (**16:00** ve **00:00**) kartları otomatik olarak kapatır:
- **Duruşta olan kartlar**, duruşa geçtikleri saat itibariyle kapatılır.
- **Çalışıyor olan kartlar**, vardiyanın tam bitiş saatinde (16:00 / 00:00) kapatılır.
- Kapatılan kartların net süreleri vardiya sınırı olan **430 dakika** ile kısıtlanır.
- **İptal Edildi (Cancelled) Durumu:** Eğer bir kart yönetici tarafından veya hatalı olduğu için "İptal Edildi" (docstatus=2) konumuna getirilirse, arayüzde **Gri** renkte ve "İptal Edildi" etiketiyle görünür. Bu durumdaki kartlarda herhangi bir işlem yapılamaz ve tüm aksiyon butonları gizlenir.

---

## 📊 8. İzleme ve Dashboard

Yöneticiler ve kalite sorumluları, **Çalışma Kartı Dashboard** ekranı üzerinden:
- Günlük durum dağılımını (Çalışan, Duruşta, Bitmiş kart sayıları),
- Operatör net çalışma sürelerini,
- Kalite kontrol ve hurda dağılımlarını anlık olarak takip edebilirler.

---

## 🔒 9. Yetki Yönetimi ve Konfigürasyon (Yöneticiler İçin)

Çalışma Kartı üzerindeki veri düzenleme yetkileri (alt işlem ekleme, hurda silme, kalite girme), kartların **"Bitmiş"** veya **"İptal Edilmiş"** statüsünde olup olmadığına ve kullanıcının sahip olduğu rollere göre sistem tarafından dinamik olarak yönetilir:

- **Operatör Kısıtı:** Normal operatörler, yalnızca "Çalışıyor" veya "Duruşta" olan aktif kartlarda veri girişi/silme yapabilir. Bitmiş kartlarda arayüz kilitlenir.
- **İptal Kısıtı:** Bir kart iptal edildiyse hiçbir yetkili buna müdahale edemez.

### Sistem ve Performans Ayarları:
ERPNext Arama Çubuğuna `KTA Calisma Karti Settings` yazarak ulaşabileceğiniz konfigürasyonlar şunlardır:

1. **Maksimum Çalışma Kartı Süresi (Örn: 430 dk):** Bir kartın açık kalabileceği (Çalışıyor) maksimum vardiya süresi. Bu süreyi aşan kartlar sistem tarafından (cron-job) otomatik kapatılır veya duraklatılır.
2. **Kart Uyarı Süresi (Örn: 400 dk):** Çalışan kartlar bu süreye ulaştığında operatöre arayüz üzerinden kırmızı "Vardiya Sonuna Yaklaşıyor" uyarısı verilir.
3. **Tamamlanmış İE Tolerans Süresi (Örn: 8 saat):** İş Emri ERPNext üzerinden resmi olarak "Kapatıldı" konumuna alınsa bile, son stok girişinden itibaren bu kadar saat boyunca operatörler o iş emri için yeni çalışma kartı başlatabilir. Fazladan stok veya rütuş işlemlerini destekler.
4. **Kart Geçiş Modu (Sıkı / Esnek):**
    - `Sıkı (Hard)`: Operatör güncel kartına hiçbir veri girmediyse (Alt işlem vb.) yeni bir karta geçişine/iş başlatmasına **izin verilmez**.
    - `Esnek (Soft)`: Operatör uyarılır ancak yeni karta geçmesine veya eskisini duraklatmasına müsaade edilir.
5. **Yenileme Aralıkları (Liste ve Detay - Saniye):** Sahadaki tablet sayısının artışına bağlı olarak sunucu yükünü (API Rate) dengelemek için verilerin hangi aralıklarla polling ile (arka planda) güncelleneceğini belirler. Standart değerler Liste için 30, Detay için 10 saniyedir.
6. **Hurda Gider Hesabı:** Stok belgeleri (SE) otomatik oluşurken hurdaların muhasebeleşeceği gider veya hurda deposu hesabını tanımlar.
7. **Admin Kontrol Rolleri (`admin_roles`):**
    - İçeriği virgülle ayırarak genişletilir (Örnek: `System Manager, Quality Manager, Manufacturing Manager`).
    - Bu alana sistemdeki rollerin isimlerini girdiğinizde, ilgili role sahip yöneticiler; **"Bitmiş"** durumda kilitlenen kartlardaki Düzenle/Sil/Ekle gibi butonlara yeniden erişip (bypass edip) verileri düzeltebilir. İptal edilmiş (docstatus=2) kartlara ise hiçbir rol müdahale edemez.

---
+
+## 🛡️ 10. Sistem Güvenilirliği ve Test Otomasyonu
+
+KTA Çalışma Kartı platformu, endüstriyel sahadaki veri bütünlüğünü korumak için **Otomatik Entegrasyon Testleri** ile korunmaktadır.
+- **Kritik İş Akışları:** Kart başlatma, durdurma, bitirme ve kalite kontrol süreçleri her güncelleme öncesinde otomatik test senaryoları ile denetlenir.
+- **Veri Senkronizasyonu:** Hurda girişlerinin Stok Kayıtları ile senkronizasyonu ve Alt Operasyon kayıtlarının tutarlılığı sistem tarafından anlık olarak izlenir ve doğrulanır.
+- **Hata Önleme:** "Anti-double-click" gibi koruma mekanizmaları, operatörlerin yanlışlıkla mükerrer veri girişi yapmasını engeller ve bu özellikler düzenli olarak test edilir.
+
+</main>
