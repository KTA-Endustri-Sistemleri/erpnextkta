---
layout: default
title: "KTA Çalışma Kartı Kullanım Kılavuzu"
---

<main class="container" markdown="1">

# 📋 KTA Çalışma Kartı Kullanım Kılavuzu

**KTA Çalışma Kartı**, operatörlerin sahada üretim süreçlerini gerçek zamanlı olarak takip etmelerini, süreleri ölçmelerini, hurdaları ve ölçümleri kaydetmelerini sağlayan özel üretim arayüzüdür.

---

## 🚀 1. Çalışma Kartı Oluşturma ve Başlatma

Çalışma Kartı, ERPNext'teki İş Emri (Work Order) ve İş Kartı (Job Card) temel alınarak oluşturulur.

### Kart Oluşturma Adımları:
1. **İş Kartı Seçimi:** QR kod okutarak veya listeden "İş Kartı" (`Job Card`) seçerek başlayın. İş Emri ve Üretilecek Ürün bilgileri otomatik olarak gelecektir. (Sistem akıllı barkod desteği ile `2026-X` gibi kısa girişleri otomatik tamamlar).
2. **Operasyon Seçimi:** Yapılacak işlemi (örneğin: *Kablo Kesme ve Kontak Basma*) seçin.
3. **İş İstasyonu ve Operatör:** Hangi istasyonda çalışılacağını ve operatörü belirleyin.
4. **Oluştur:** "Oluştur" butonuna basarak kartı sisteme kaydedin. Kart, başlangıçta **"Hazır"** statüsünde bekleyecektir.

### Kartı Başlatma:
Kartı oluşturduktan sonra içine girip, üst kısımdaki **"Başlat"** butonuna basın. Durum **"Çalışıyor"** olarak güncellenecek ve süre sayacı başlayacaktır.
> **Not:** Bir operatör hesabında yeni bir kart başlatılırsa ve açıkta kalan, durdurulmamış başka kartlar varsa, onlar sistem tarafından otomatik olarak "Diğer" açıklamasıyla mola (Duruş) moduna alınır.

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

---

## 📊 8. İzleme ve Dashboard

Yöneticiler ve kalite sorumluları, **Çalışma Kartı Dashboard** ekranı üzerinden:
- Günlük durum dağılımını (Çalışan, Duruşta, Bitmiş kart sayıları),
- Operatör net çalışma sürelerini,
- Kalite kontrol ve hurda dağılımlarını anlık olarak takip edebilirler.

</main>
