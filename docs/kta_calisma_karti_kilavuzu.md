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
2. **Duruş Nedeni:** Açılan ekrandan duruş nedeninizi seçin. Duruş nedenleri artık dinamik olarak yönetilir ve üç ana kategoriye ayrılır:
    - **Plansız Duruşlar**: Makine arızası, malzeme bekleme, kalite onayı bekleme vb. (OEE kayıpları).
    - **Planlı Duruşlar**: Mola, yemek, eğitim veya planlı bakım süreçleri.
    - **Sistem Duruşları**: Arka plan görevleri veya otomatik kurallar tarafından eklenen, operatöre gizli duruşlar.
    - **"Diğer" Nedeni Kontrolü**: Duruş nedeni olarak *"Diğer"* seçilirse, duruşun nedenini açıklayan bir metin (en az bir kelime) girmek zorunludur. Aksi takdirde hem arayüzde (kırmızı uyarı) hem de sunucu tarafında kaydetme işlemi engellenir.
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

## 📐 5. Kalite Kontrol (QC) ve Akıllı Ölçüm Formları

Üretim esnasında alınan spesifik ölçümler (Çekme testi, krimp yüksekliği, gramaj vb.) bu sekme altından yürütülür. Sistemin getirdiği en yenilikçi özelliklerden biri **Modüler (Satır Bazlı) Kalite Onayı** sistemidir. Bu sayede tüm karta tek bir kalite belgesi kesmek yerine, operatörün ürettiği her bir alt işleme sırasıyla onay verilir.

### Modüler Kalite Onayı (Satır Bazlı QC)
1. **Kalite Sekmesi Görünümü:** Çalışma Kartı ayarlarında "Alt Operasyon Bazlı Kalite" özelliği aktifse, kalite paneline girdiğinizde tüm kartı reddetmek yerine; eklenmiş olan her bir alt operasyon için ayrı bir satır ve onay butonu görürsünüz.
2. **Liste Arayüzünde Degrade Geçişler:** Bir kartın alt operasyonlarının bazıları onaylanıp, bazıları red yemiş veya bekliyor olabilir. Bu çoklu durumu liste görünümünde (CkCard.vue) sağ kenardaki dinamik parçalı/degrade renk bloklarından anlık olarak görebilirsiniz. Örneğin 3 alt operasyon varsa sağ kenarda üst üste Yeşil (Onaylı), Kırmızı (Red) ve Mavi (Bekleyen) renk blokları görünür.
3. **Onaylama ve Belge Entegrasyonu:** Her satırdaki "Kalite Onayı Ver" butonuna basıldığında arka planda sadece o satıra özel bir Kalite Kontrol Belgesi (Quality Inspection) oluşturulur ve o satıra bağlanır.
   - **Önemli Not:** Alt operasyonların tamamı onaylansa dahi, ana çalışma kartının sadece "Durum" (Kalite Kontrol) alanı "Onaylandı" olarak güncellenir. Ancak ana karta **herhangi bir kalite belgesi (Quality Inspection ID) işlenmez**. Bu sayede, UI tarafında kartın "Klasik" bir QC belgesine sahip olduğu yanılgısı yaratılmaz ve her bir belgenin kendi satırında kalması sağlanır.


### Akıllı Krimp Formu ve Çift Taraf Mantığı
Özellikle "Kablo Kesme ve Kontak Basma" gibi krimp işlemlerinde kalite onayı verilirken sistem, girilen alt operasyon verisine bakarak form ekranını akıllı bir şekilde yapılandırır:

1. **Tek Taraf ve Küt İşlemler:** Eğer alt operasyonun isminde "Küt" veya "Tek Taraf" geçiyorsa, krimp formunda sadece tek bir tarafa ait kontak numarası, hedef ölçü, makine numarası ve çekme testi alanı açılır.
2. **Çift Taraf (Double Sided) İşlemler:** Eğer alt operasyonun isminde "Çift Taraf" geçiyorsa, sistem form arayüzünü otomatik genişletir. **"2. Taraf - Makine ve Kalıp"** isminde yepyeni alanlar açılır. Bu sayede her iki tarafın kontak bilgisi, ölçümleri ve makine bilgisi aynı tek form üzerinde toplanır.
3. **Sihirli Otomatik Doldurma (Auto-fill):**
   - Krimp formunu doldururken verileri elle aramanıza gerek yoktur.
   - Form açılır açılmaz alt operasyonda seçilmiş olan **Kablo Kesiti**, **Hedef İletken/Yalıtkan Yükseklikleri**, 1. ve 2. Taraf **Kontak Kodları** form alanlarına anında doldurulur. Operatör sadece okuduğu mikrometre değerini ve kullandığı makine numarasını/kalıbı yazar.
   - Form kaydedilir kaydedilmez kalite onayı verilmiş sayılır ve Krimp tablosunda listelenir.

### Diğer Formlar ve Özellikler
- **IDC ve Enjeksiyon Formları:** Krimp işlemleri haricindeki alanlarda 120-IDC konnektörler için veya plastik enjeksiyon için (gramaj, çevrim süresi vb.) özel form tabloları mevcuttur.
- **Protokol Belgesi Olarak Yazdırılması (🖨️):** Kalite formları kaydedildikten sonra "Protokol" butonuna basılarak ilgili ölçüme ait resmi HTML tabanlı evrak oluşturulup ağdaki yazıcıdan etiketi/çıktısı alınabilir.

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
3. **Bekleyen Kartlar Uyarı Ekranı (Modal):** Bir kartı bitirdiğinizde, sistem arka planda sizin daha önceden başlattığınız ancak sistem tarafından otomatik olarak "Duruşta" bekletilen (askıda kalmış) başka kartlarınız olup olmadığını kontrol eder.
    - Eğer bekleyen kartlarınız varsa, işlemi tamamladıktan hemen sonra modern bir **uyarı ekranı (Modal)** açılır.
    - Bu ekranda bekleyen tüm kartlarınız liste halinde sunulur. Kartın yanındaki **"GİT"** butonuna basarak o karta hızlıca geçiş yapabilir ve işinize kaldığınız yerden devam edebilirsiniz.
    - Dilerseniz sağ üst köşedeki **Çarpı (X)** butonuyla uyarı ekranını kapatarak bulunduğunuz ekranda kalabilirsiniz.
    - **Akıllı Kontrol:** Eğer o an halihazırda "Çalışıyor" durumunda olan aktif başka bir kartınız varsa, sistem çalışmanızı bölmemek (sizi yeni bir kart seçmeye zorlamamak) adına bu uyarı ekranını **göstermeyecektir**.


### Otomatik Vardiya Sonu Kapatma (Akıllı Kapatma):
Kartı açık unutmanız durumunda sistem vardiya sonlarında (**16:00** ve **00:00**) kartları otomatik olarak kapatır:
- **Duruşta olan kartlar**, duruşa geçtikleri saat itibariyle kapatılır.
- **Çalışıyor olan kartlar**, vardiyanın tam bitiş saatinde (16:00 / 00:00) kapatılır.
- Kapatılan kartların net süreleri vardiya sınırı olan **430 dakika** ile kısıtlanır.
- **İptal Edildi (Cancelled) Durumu:** Eğer bir kart yönetici tarafından veya hatalı olduğu için "İptal Edildi" (docstatus=2) konumuna getirilirse, arayüzde **Gri** renkte ve "İptal Edildi" etiketiyle görünür. Bu durumdaki kartlarda herhangi bir işlem yapılamaz ve tüm aksiyon butonları gizlenir.

---

## 📊 8. İzleme, Dashboard ve Raporlama

Yöneticiler, amirler ve kalite sorumluları sistem üzerinden şu araçlarla gerçek zamanlı izleme yapabilir:

- **Çalışma Kartı Dashboard:** Günlük durum dağılımını (Çalışan, Duruşta, Bitmiş kart sayıları), operatör net çalışma sürelerini, kalite kontrol ve hurda dağılımlarını anlık gösterir.
- **Kullanıcı Paneli (User Dashboard) Entegrasyonu:** Her kullanıcının kendi profil sayfasında, kullanıcının bağlı olduğu `Employee` kaydı üzerinden açık ve tamamlanmış Çalışma Kartlarının adedi ve linkleri otomatik olarak listelenir.
- **Düşük Net Süre Grafiği (Operator Performance Chart):** Son N günde toplam net çalışma süresi en az olan operatörleri ve net sürelerini bar grafik olarak karşılaştırır.
- **Günlük Performans ve Hata Raporlama (E-posta):** Günlük net çalışma süresi 5 saatin altında kalan operatörler ve bu operatörlerin o günkü kart detayları, her sabah saat `08:30`'da KTA Settings'te tanımlanmış amir e-postalarına HTML raporu olarak otomatik gönderilir.

---

## 🔒 9. Yetki Yönetimi ve Konfigürasyon (Yöneticiler İçin)

Çalışma Kartı üzerindeki veri düzenleme yetkileri (alt işlem ekleme, hurda silme, kalite girme), kartların durumuna ve kullanıcının sahip olduğu rollere göre dinamik olarak yönetilir:

### A. Operatör Kısıtları (Normal Kullanıcılar)
- **Aktif Kart Şartı:** Normal operatörler, yalnızca "Çalışıyor" veya "Duruşta" olan aktif kartlarda veri girişi/silme yapabilir. Kart "Bitmiş" veya "İptal" statüsüne geçerse tüm butonlar ve arayüzler kilitlenir.
- **Kalite Kilit Mekanizması:** Modüler kalite sürecinde, kalite birimi tarafından "Onaylandı" durumuna getirilmiş bir alt operasyon satırı operatör tarafından değiştirilemez veya silinemez. Silmeye veya düzenlemeye çalışırsa sistem "Bu işlem kalite tarafından onaylanmıştır" uyarısı verir. Bu durumda kalite birimine haber verilmelidir.

### B. Kalite Birimi Yetkileri (QC Allowed Roles)
- "KTA Calisma Karti Settings" üzerinden ayarlanan kalite rollerine sahip kullanıcılar (Örn: Quality Manager), kalite onayı verilmiş satırlardaki kilidi (bypass) aşabilir. 
- Eğer kalite birimi onaylı bir satırı silerse veya değiştirirse, arka planda o satıra bağlı oluşturulmuş Kalite Kontrol Belgesi (Quality Inspection) otomatik olarak iptal edilir ve silinir (Clean-up).

### C. Yönetici ve Müdahale Yetkileri (Admin Roles)
- **Kilit Açma (Bypass):** Normalde "Bitmiş" statüsünde olan bir karta operatörler dokunamazken, "KTA Calisma Karti Settings" içindeki `admin_roles` alanında tanımlı olan yöneticiler (Örn: System Manager, Manufacturing Manager), kart bittikten sonra bile içine girip (bypass edip) verileri (Alt işlem, Hurda vb.) düzeltebilir.
- **Mutlak İptal Kısıtı:** Bir kart tamamen "İptal Edildi" (Cancelled / docstatus=2) konumuna getirildiyse, sistemde hangi role sahip olursanız olun hiçbir şekilde müdahale edilemez, veri girilemez veya silinemez.

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
7. **Otomatik Duraklatma Duruş Nedeni**: Yeni bir kart başlatıldığında, operatörün açıkta kalan eski kartlarının hangi duruş nedeniyle duraklatılacağını belirler (Örn: Otomatik Duraklatma).
8. **Zaman Aşımı Duruş Nedeni**: Vardiya sonunda veya 430 dk limitinde otomatik kapatılan kartlara eklenecek bilgi notu mahiyetindeki duruş nedeni (Örn: Zaman Aşımı).
9. **Admin Kontrol Rolleri (`admin_roles`):**
    - İçeriği virgülle ayırarak genişletilir (Örnek: `System Manager, Quality Manager, Manufacturing Manager`).
    - Bu alana sistemdeki rollerin isimlerini girdiğinizde, ilgili role sahip yöneticiler; **"Bitmiş"** durumda kilitlenen kartlardaki Düzenle/Sil/Ekle gibi butonlara yeniden erişip (bypass edip) verileri düzeltebilir. İptal edilmiş (docstatus=2) kartlara ise hiçbir rol müdahale edemez.


## 🛡️ 10. Sistem Güvenilirliği ve Test Otomasyonu

KTA Çalışma Kartı platformu, endüstriyel sahadaki veri bütünlüğünü korumak için **Otomatik Entegrasyon Testleri** ile korunmaktadır.
- **Kritik İş Akışları:** Kart başlatma, durdurma, bitirme ve kalite kontrol süreçleri her güncelleme öncesinde otomatik test senaryoları ile denetlenir.
- **Veri Senkronizasyonu:** Hurda girişlerinin Stok Kayıtları ile senkronizasyonu ve Alt Operasyon kayıtlarının tutarlılığı sistem tarafından anlık olarak izlenir ve doğrulanır.
- **Hata Önleme:** "Anti-double-click" gibi koruma mekanizmaları, operatörlerin yanlışlıkla mükerrer veri girişi yapmasını engeller ve bu özellikler düzenli olarak test edilir.

</main>
