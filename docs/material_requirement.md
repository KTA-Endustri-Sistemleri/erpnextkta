---
layout: default
title: "Malzeme İhtiyaç Raporu (Material Requirement)"
---

# 🧱 Malzeme İhtiyaç Raporu (Material Requirement) Kullanım Kılavuzu

Bu rapor, **Kapasite Planlama** raporundan gelen haftalık üretim planını ürün reçeteleriyle (BOM) çarpar, mevcut stok ve açık satın alma siparişleriyle (PO) netleştirir ve **"Hangi hammaddeden, hangi hafta, ne kadar sipariş vermeliyim?"** sorusunu cevaplar.

---

## 1. Raporun Temel Amacı

- Her hammaddenin haftalık **brüt ihtiyacını**, **net ihtiyacını** ve MOQ/paket katına yuvarlanmış **önerilen siparişini** gösterir.
- Stoğun hangi hafta biteceğini (**İlk Eksik Hafta**, **Kapsama**) ve önerilen siparişlerin tutarını gösterir.
- Hammaddenin hangi bitmiş ürünler tarafından tüketildiğini ağaç yapısında açıp inceleyebilirsiniz.

---

## 2. Hesaplama Mantığı

Hesaplamalar `erpnextkta/kta_mrp/mrp_engine` servis katmanında yapılır. Material Requirement, MRP Analiz ve Önerilen PO raporları aynı servisi kullanır.

### 🧮 Brüt İhtiyaç ve İş Emri Düşümü (Mono-BOM & Carry-Over)
1. Kapasite Planlama'nın haftalık bitmiş ürün planı alınır.
2. Her bitmiş ürün için aktif ve varsayılan BOM'un **Explosion Items** tablosu okunur.
3. KTA operasyonlarında yarı mamul bulunmadığından ve tüm iş emirleri `skip_transfer = 1` ile açıldığından, hammaddeler ambar stokunda rezerve edilir (`Bin.reserved_qty_for_production`).
4. Çift sayımı önlemek için açık iş emirleri plandan düşülür:
   `Brüt İhtiyaç = BOM stock_qty × max(0, Planlanan Üretim − Açık İş Emri Miktarı)`
5. Kapasite dolduğunda devreye giren ileriye doğru planlama (`forward_scheduling`) algoritmasında, iş emirleri de taleple birlikte bir sonraki haftaya devredilir (`item_carry_over_wo`), böylece hiçbir açık iş emri kaybolmaz ve mükerrer hammadde sipariş önerisi oluşmaz.

### 🛡️ Emniyet Stoğu Desteği (Safety Stock)
Standart ERPNext `Item` kartı **Satın Alma (Purchasing)** sekmesinde tanımlı `safety_stock` alanı MRP motoruna entegre edilmiştir:
- Stok bakiyesi emniyet seviyesinin altına inmeden önce sipariş önerisi üretilir:
  `Net İhtiyaç = max(0, Brüt İhtiyaç + Emniyet Stoğu − (Önceki Bakiye + PO Girişi))`
- `safety_stock = 0` iken bugünkü dinamik netleştirme davranışı korunur.

### 📦 Tedarik Hattı ve Stok Kaynakları (Supply Pipeline Breakdown)
MRP motoru arz kaynaklarını gerçek lojistik akışına göre ayrıştırır:
- **Stok / Rezerve Stok:** Sadece `Kullanılabilir Stok` tipindeki depolardan okunur. `Serbest Stok = Stok − Rezerve Stok` (negatif olabilir).
- **Açık Satınalma Siparişi (PO):** Henüz yola çıkmamış açık PO'lar, planlanan teslim tarihine göre ilgili haftaya işlenir. Vadesi geçmiş siparişler acil tedarik sayılarak ilk haftaya yazılır.
- **Yolda (In Transit):** Satıcıdan sevk edilmiş `Purchase Receipt` belgeleridir. Belgedeki zorunlu **Tahmini Varış Tarihi (`tahmini_varis_tarihi` / ETA)** baz alınarak doğrudan varış haftasına yerleştirilir.
- **Antrepoda (In Bonded Warehouse):** Liman/antrepoya ulaşmış, millileştirilmeyi bekleyen stok havuzudur. Depoda acil açık oluştuğunda öncelikle antrepodaki partiler "İşlem Başlat" eylemiyle gümrüklemeye çekilebilir.
- **Gümrüklemede (In Customs Clearance):** Gümrükleme işlemleri başlatılmış sevkiyatlar. Sistem `antrepo_clearance_days` (+2 iş günü) süresini ekleyerek malzemenin ana ambar stokuna gireceği haftayı hesaplar.
- **Mal Kabul Uyuşmazlığı (Kapıda Bloke / Karantina):** Fabrika kapısında evrak, hasar veya eksik malzeme nedeniyle reddedilmiş irsaliyelerdir. Şüpheli ve kullanılamaz malzemenin üretime sokulmaması için **MRP netleştirmesinde kesinlikle arz sayılmaz (`receipts = 0`)**. Üretim hattının durmaması adına eksik kabul edilip yeni PO önerilir; ancak plancının mükerrer sipariş açmaması veya durumu teyit edebilmesi için rapor ve detay modalında `⚠️ Mal Kabul Uyuşmazlığı [Uyuşmazlık Nedeni]` şeklinde şeffafça gösterilir.

### 🤝 Tedarikçi Dağıtımı ve Kotalı Satınalma (Item Sourcing Strategy)
Hammadde tedariğinde çoklu kaynak optimizasyonu için `Item Sourcing Strategy` kuralları uygulanır:
- **Default (%100 Tek Tedarikçi):** İhtiyacın tamamı kalemin varsayılan tedarikçisine yönlendirilir.
- **Quota Share (Kotalı Paylaşım):** Net ihtiyaç, tanımlı yüzdelere göre (ör. %60 Tedarikçi A, %40 Tedarikçi B) paylaştırılır. Her tedarikçinin kendi MOQ ve paket katı bağımsız işletilir.
- **Kamçı Etkisi ve Küçük İhtiyaç Koruması:** Eğer o haftaki net ihtiyaç tedarikçilerin MOQ toplamından küçükse (`shortage < sum(moqs)`), sistem gereksiz fazla stok yığılmasını önlemek amacıyla siparişi kotaya bölmek yerine en yüksek kotalı ana tedarikçiye konsolide eder.
- **Lowest Price (En Düşük Fiyat):** Aktif tedarikçiler arasında en ucuz birim fiyatı sunan satıcı tercih edilir.
- **Shortest Lead Time (En Kısa Temin Süresi):** En hızlı teslimat yapabilen tedarikçi seçilerek üretim riski azaltılır.
- **Hibrit Yerli / Yurt Dışı Sınıflandırması:** Tedarikçi kartında ülke bilgisi yanlışlıkla Türkiye bırakılmış olsa bile, tedarikçi grubu `YD-Hammadde` olan tüm tedarikçiler (`is_foreign_supplier`) otomatik olarak ithalat / yurt dışı statüsünde işlem görür.
- **Ağırlıklı Ortalama Fiyat:** Kotalı dağıtımda kalem farklı tedarikçilerden temin edildiğinde, rapordaki Birim Fiyat kotalarla ağırlıklandırılmış ortalama fiyat olarak hesaplanır.

### 📉 Netleştirme Formülasyonu

```text
Serbest Stok       = Fiili Stok − Rezerve Stok   (Depodaki net kullanılabilir miktar)
Net İhtiyaç        = max(0, Brüt İhtiyaç − (Önceki Bakiye + PO Girişi))
Önerilen Sipariş   = max(MOQ, ceil(Net İhtiyaç / Paket Katı) × Paket Katı)
Projeksiyon Bakiye = Önceki Bakiye + PO Girişi − Brüt İhtiyaç   (Yeni sipariş verilmezse)
```

> **⚠️ Negatif Serbest Stok Kuralı (Rezerve Açığı):** Açık iş emirlerinin talep ettiği malzeme miktarı ambardaki fiili stoktan fazlaysa serbest stok negatif çıkar. Bu miktar üretimin durmaması için **en geç 1. hafta kapatılması gereken acil açık** olarak kabul edilir ve 1. haftanın net ihtiyacına eklenir.

---

## 3. Uygulamalı Sayısal Örnek Senaryoları

### Senaryo 1: Rezerve Açığı ve Tedarikçi MOQ Yuvarlaması (Gerçek Veri Örneği)
Veritabanındaki `10023299` (AWG22 Tinned Kablo) hammaddesi üzerinden adım adım hesaplama akışı:

```text
1. BAŞLANGIÇ STOK VE İŞ EMRİ REZERVASYONLARI:
   Fiili Stok (Kullanılabilir Depolar) :  1.920,20 Metre
   Rezerve Stok (Açık İş Emirleri)     :  2.552,20 Metre  (MFG-WO-05164: 2.520 m + MFG-WO-04684: 230 m)
   --------------------------------------------------------------------------------------------------
   Serbest Stok (Free Stock)          =  Fiili Stok - Rezerve Stok
                                      =  1.920,20 - 2.552,20 = -632,00 Metre  (AÇIK!)

2. TEDARİKÇİ ALIŞ KOŞULLARI VE AÇIK SİPARİŞ (PO):
   Varsayılan Tedarikçi               :  Başoğlu Kablo (Item Price)
   Minimum Sipariş Miktarı (MOQ)      :  5.000,00 Metre
   Minimum Paketleme Katı (Pack)      :  5.000,00 Metre
   Yolda Olan Açık Sipariş (Open PO)  :  0 Metre

3. HAFTALIK MRP NETLEŞTİRME VE BAKİYE DEVİR TABLOSU:
   Hafta      Brüt İhtiyaç    Kullanılabilir Bakiye    Net İhtiyaç    Önerilen Sipariş    Devreden Bakiye
   --------   ------------    ---------------------    -----------    ----------------    ---------------
   Başlangıç             -                -632,00 m              -                   -          -632,00 m
   2026-W45         4,70 m                -632,00 m       636,70 m          5.000,00 m        +4.363,30 m
   2026-W50       326,00 m              +4.363,30 m           0,00 m              0,00 m        +4.037,30 m
   --------   ------------    ---------------------    -----------    ----------------    ---------------
   TOPLAM         330,70 m                                636,70 m          5.000,00 m

4. BU HESAPLAMANIN ÖNEMLİ ÇIKARIMLARI:
   • Soru: "Brüt ihtiyaç 330,70 m iken 1. haftanın net ihtiyacı neden 636,70 m çıktı?"
     Cevap: 1. haftanın brüt ihtiyacı 4,70 m'dir. Ancak geçmişten gelen 632 m rezerve açığı
            ilk haftaya acil açık olarak eklendiği için net ihtiyaç: 4,70 - (-632) = 636,70 m olur.
   • Soru: "Net ihtiyaç 636,70 m iken önerilen sipariş neden 5.000 m oldu?"
     Cevap: Tedarikçi MOQ ve paket katı 5.000 m'dir. Sistem 636,70 m'yi 5.000'in tam katına yukarı yuvarlar.
   • Soru: "50. haftada 326 m talep varken neden önerilen sipariş 0 gözüküyor?"
     Cevap: 1. haftada verilen 5.000 m siparişten geriye 4.363,30 m fazlalık stok kalmıştır. 50. haftadaki
            326 m ihtiyaç bu devreden stoktan karşılandığı için ek siparişe gerek kalmaz.
```

### Senaryo 2: Planlama Ufkunun (Tarih Aralığı) Etkisi: 90 Gün vs 1 Yıl

```text
Filtre 1: 90 Günlük Standart Planlama Ufku (04-11-2026 / 04-02-2027)
  Kapsanan Haftalar : 2026-W45 .. 2027-W05 (13 Hafta)
  Brüt İhtiyaç      : 4,70 m (W45) + 326,00 m (W50) = 330,70 Metre
  Net İhtiyaç       : 636,70 Metre
  Önerilen Sipariş  : 5.000,00 Metre

Filtre 2: 1 Yıllık Genişletilmiş Ufuk (04-11-2026 / 04-11-2027)
  Kapsanan Haftalar : 2026-W45 .. 2027-W45 (52 Hafta)
  Yeni Giren Talep  : 2027-W20 (Mayıs 2027) haftasındaki 163,00 Metrelik satış siparişi.
  Brüt İhtiyaç      : 4,70 m (W45) + 326,00 m (W50) + 163,00 m (W20) = 493,70 Metre
  Net İhtiyaç       : 636,70 Metre (Değişmedi!)
  Önerilen Sipariş  : 5.000,00 Metre (Değişmedi!)

Neden Net İhtiyaç ve Sipariş Değişmedi?
1. haftada verilen 5.000 metrelik tek sipariş; 632 m rezerve açığını ve 2026-W45, 2026-W50 ile
Mayıs 2027'deki 163 m siparişi kapatıp yıl sonunda hala 3.874,30 Metre stok bıraktığı için ek sipariş gerekmez.
```

### Senaryo 3: Açık Satın Alma Siparişlerinin (PO) Netleştirmeye Etkisi ve Haftalık Drill-Down (10023109 Gerçek Veri Örneği)
Veritabanındaki `10023109` hammaddesi üzerinden açık PO girişlerinin ve netleştirmenin adım adım işleyişi:

```text
1. BAŞLANGIÇ STOK VE İŞ EMRİ REZERVASYONLARI:
   Fiili Stok (Kullanılabilir Depolar) :  2.217,00 Adet
   Rezerve Stok (Açık İş Emirleri)     :  3.040,00 Adet  (MFG-WO-2026-04701, 05322, 05009)
   --------------------------------------------------------------------------------------------------
   Serbest Stok (Free Stock)          =  Fiili Stok - Rezerve Stok
                                      =  2.217,00 - 3.040,00 = -823,00 Adet  (AÇIK!)

2. TEDARİKÇİ ALIŞ KOŞULLARI:
   Varsayılan Tedarikçi               :  Şener Kauçuk/Silikon Plastik &
   Minimum Sipariş Miktarı (MOQ)      :  2.000,00 Adet
   Paketleme Katı (Pack Multiple)     :    500,00 Adet
   Temin Süresi (Lead Time)           :  14 Gün

3. 2026-W46 HAFTASI VE AÇIK PO GİRİŞİ ADIM ADIM HESABI:
   • Bu Haftaya Gelen Açık PO          :  +2.000,00 Adet (PUR-ORD-2026-05850)
   • Netleştirme Öncesi Kullanılabilir :  -823,00 (Geçmiş Açık) + 2.000,00 (PO Girişi) = +1.177,00 Adet
   • Bu Haftanın Brüt İhtiyacı        :  -1.800,00 Adet (87172080640 Mamulü / BOM-8717208064-0-L-002)
   • Açık Bakiye (Net İhtiyaç)        :  1.800,00 - 1.177,00 = 623,00 Adet
   • Tedarikçi Önerilen Sipariş       :  2.000,00 Adet (623 Adet net açık MOQ olan 2.000'e yuvarlanır)
   • Dönem Sonu Projeksiyon Bakiye    :  1.177,00 - 1.800,00 = -623,00 Adet (Yeni sipariş açılmazsa)
   • Sipariş Verildiğinde Devir       :  1.177,00 + 2.000,00 - 1.800,00 = +1.377,00 Adet

4. SONRAKİ HAFTALARA PLANLANMIŞ AÇIK PO SEVKİYATLARI:
   • 2026-W47:  +3.500,00 Adet (PUR-ORD-2026-05870)
   • 2026-W48:  +5.000,00 Adet (PUR-ORD-2026-05949: 3.000 + PUR-ORD-2026-05884: 2.000)
   • 2026-W49:  +3.000,00 Adet (PUR-ORD-2026-05972)
   • 2026-W50:  +3.000,00 Adet (PUR-ORD-2026-05900)

5. BU HESAPLAMANIN ÖNEMLİ ÇIKARIMLARI:
   • Soru: "Açık PO girişi olmasaydı ne olurdu?"
     Cevap: PO girişi olmasaydı kullanılabilir stok -823 Adet kalacak; 1.800 adet brüt taleple
            birlikte net ihtiyaç 2.623 Adet ve önerilen sipariş 3.000 Adet (500 katı) olacaktı.
            Açık PO girişi sayesinde mükerrer satın alma önlenmiş ve öneri 2.000 adede inmiştir.
   • Soru: "Gecikmiş PO'lar nasıl işlenir?"
     Cevap: Vadesi (Teslim Tarihi) bugünden veya ilk haftadan önce kalmış açık PO'lar acil
            teslimat kabul edilerek ilk planlama haftasının PO girişine dahil edilir.
```

---

## 4. Filtreler

| Filtre | Açıklama | Varsayılan |
|---|---|---|
| **Başlangıç Tarihi** | Sistem tarafından otomatik olarak **bulunulan haftanın Pazartesi gününe** kilitlenir. Geçmiş tarih seçimi engellenmiştir. | Bu Haftanın Pazartesi Günü |
| **Bitiş Tarihi (Planlama Ufku)** | Planlama periyodunun bitişi. Varsayılan `KTA MRP Settings` (90 gün) ayarından gelir, 1 yıla kadar genişletilebilir. | Bugün + 90 gün |
| **Haftalık Gösterim** | Hafta kolonlarında gösterilecek ölçü: Önerilen Sipariş, Net İhtiyaç, Brüt İhtiyaç, Projeksiyon Bakiye. | Önerilen Sipariş |
| **Gruplama Şekli** | "Bitmiş Ürün + Hammadde" (ağaç) veya "Sadece Hammadde" (düz liste) | Bitmiş Ürün + Hammadde |
| **PO Teslimatlarını Dahil Et** | Kapalıysa yoldaki ve antrepodaki açık arz kaynakları hesap dışı bırakılır (stok ihtiyacı brüte eşitlenir) | Açık |
| **Sadece Eksik Olanlar** | Net ihtiyacı olmayan hammaddeleri gizler | Kapalı |
| **Tedarikçi / Hammadde** | Hammadde tarafında filtre | (Hepsi) |
| **Müşteri Grubu / Ürün Grubu** | Bitmiş ürün (talep) tarafında filtre | (Hepsi) |

> **📅 Akıllı Başlangıç Tarihi Kuralı:** Kullanıcıların geçmiş tarihlere yönelik rapor çekip hatalı netleştirme yapmasını önlemek için başlangıç tarihi filtresi arayüzden kaldırılmış; hesaplamanın her daim bulunulan ISO haftasının Pazartesi gününden başlatılması kurala bağlanmıştır.

> **⚙️ Kapasite Parametreleri:** Kapasite dengeleme ve ramp-up parametreleri artık rapor filtrelerinde değil, merkezi **KTA MRP Settings** ekranında yapılandırılmaktadır.

---

## 5. Tablo Yapısı ve Hiyerarşik Ağaç Mantığı

- **Bitmiş Ürün + Hammadde:** Hammadde satırının altında, o hammaddeyi tüketen bitmiş ürünler listelenir.
  - **Hammadde Satırı (Ana Satır):** Stok, Rezerve Stok, Açık PO, Net İhtiyaç ve Önerilen Sipariş verileri bu satırda gösterilir.
  - **Bitmiş Ürün Satırları (Alt Satırlar):** Sadece o mamulün haftalık brüt tüketimini gösterir. Mükerrerliği önlemek adına stok ve sipariş hücreleri bilinçli olarak boş bırakılmıştır.
- **Sadece Hammadde:** Her hammadde tek satırdır.

| Kolon | Açıklama |
|---|---|
| **Stok / Rezerve Stok / Serbest Stok** | Kullanılabilir Stok depolarındaki miktarlar |
| **Açık PO** | Dönem içinde gelecek PO miktarı (stok biriminde) |
| **Brüt İhtiyaç / Net İhtiyaç** | Dönem toplamları |
| **Önerilen Sipariş** | MOQ ve paket katına yuvarlanmış toplam sipariş miktarı |
| **İlk Eksik Hafta** | Stok + PO'nun yetmediği ilk hafta (ilk 4 hafta kırmızı, sonrası turuncu) |
| **Kapsama (Hafta)** | Yeni sipariş gerekmeden karşılanan hafta sayısı |
| **Fazla PO Miktarı** | Dönem ihtiyacını aşan PO miktarı |
| **Birim Fiyat / Para Birimi / Önerilen Sipariş Tutarı** | Varsayılan tedarikçinin en güncel Item Price alış fiyatı ve kendi para birimi |
| **Haftalık Sütunlar** (Örn: 2026-W45) | Haftalık Gösterim filtresinde seçilen ölçü |

---

## 6. Özet Kartları ve Grafik

- **🔵 Toplam Kalem:** Rapordaki hammadde sayısı.
- **🔴 Eksik Kalem:** Net ihtiyacı olan hammadde sayısı.
- **🟠 4 Hafta İçinde Eksik:** İlk eksik haftası acil eşik (`urgent_shortage_weeks`) içinde olanlar.
- **🟢 Önerilen Sipariş Tutarı (EUR / USD / TRY …):** Para birimi bazında toplam sipariş maliyeti.
- **🟣 Fiyatı Olmayan Kalem:** Sipariş önerilen ama alış fiyatı bulunmayan kalem sayısı.

Grafik, her hafta için net ihtiyacı olan hammadde sayısını gösterir.

---

## 7. Haftalık Netleştirme Detay Penceresi (Drill-Down Modal)

Kullanıcıların **"Bu haftadaki rakam nereden geldi? Hangi PO'lar var? Hangi bitmiş ürünler tüketiyor?"** sorularına anında ve şeffaf cevap verebilmek için haftalık detay modal penceresi geliştirilmiştir.

### ⚡ Sıfır Gecikmeli Mimari (Instant 0ms Rendering)
- **Tıklanabilir Aktif Hücreler:** Tabloda sıfır/boş hücreler performans için hafif `-` tire olarak gösterilirken, sayısal değeri olan hücreler `mr-cell-action` stiliyle tıklanabilir mavi bir köprü olarak sunulur.
- **İki Kademeli Yükleme:**
  1. **Anında Gösterim (0ms):** Kullanıcı bir hücreye tıkladığında, tarayıcıda önceden hazır bulunan `row._week_details` verisi kullanılarak modal ve 6 adımlı netleştirme tablosu bekleme olmadan anında ekrana gelir.
  2. **Asenkron Arka Plan Yüklemesi (~80ms):** Eşzamanlı olarak sunucudaki Redis önbelleğinden (`mrp_result_{user}`) tekil malzeme verisi çekilir. O haftaya ait açık PO listesi ve tüketen mamul listesi saniyenin onda birinde modal içine doldurulur.

### 📋 Detay Penceresi İçeriği

1. **Malzeme Künyesi:**
   - Malzeme Kodu ve Adı
   - Varsayılan Tedarikçi
   - Temin Süresi (Lead Time)
   - Minimum Sipariş Miktarı (MOQ)
   - Minimum Paketleme Katı (Pack Multiple)
   - Stok Ölçü Birimi (UOM - İngilizce birimler TR/DE standartlarına dinamik çevrilir)

2. **6 Adımlı Netleştirme Özeti:**
   | Adım | Alan | Açıklama |
   |---|---|---|
   | **1** | **Önceki Devir / Rezerve Açığı** | Önceki haftadan devreden stok veya 1. haftadaki acil rezerve açığı |
   | **2** | **Açık PO Girişi** | İlgili haftaya planlanmış yoldaki satınalma siparişleri |
   | **3** | **Kullanılabilir Bakiye** | Netleştirme öncesi toplam kullanılabilir miktar (Adım 1 + Adım 2) |
   | **4** | **Brüt İhtiyaç** | O hafta üretilecek ürünlerin reçetelerinden kaynaklanan toplam tüketim |
   | **5** | **Net İhtiyaç (Eksik)** | Karşılanamayan açık miktar: `max(0, Brüt İhtiyaç − Kullanılabilir Bakiye)` |
   | **6** | **Önerilen Sipariş** | Tedarikçi MOQ ve paketleme katına yukarı yuvarlanmış sipariş adedi |
   | *Dipnot* | *Dönem Sonu Projeksiyon Bakiye* | Yeni sipariş verilmediği takdirde dönem sonunda kalacak teorik bakiye |

3. **Açık Satın Alma Siparişleri ve Tedarik Hattı (Açık PO Tablosu):**
   - İlgili haftaya düşen tüm açık satınalma siparişleri ve lojistik aşamaları (Onaylı PO, Yolda ETA, Antrepoda, Gümrüklemede) listelenir.
   - Sipariş Numarası (`PUR-ORD-...`) veya İrsaliye Numarası (`MAT-PRE-...`) doğrudan tıklanabilir bağlantıdır; ilgili ERPNext formunu yeni sekmede açar.
   - Tedarikçi Adı, Bekleyen Sipariş Miktarı, Tahmini Varış Tarihi (ETA) ve Aşama Durumu gösterilir.

4. **Tüketen Bitmiş Ürünler ve BOM Reçeteleri (Mamul Kırılımı Tablosu):**
   - O haftada bu hammaddeyi talep eden bitmiş ürünlerin listesi.
   - Bitmiş Ürün Kodu, Ürün Adı, Aktif BOM Kodu (tıklanabilir reçete bağlantısı).
   - Planlanan Mamul Üretim Miktarı, Reçete Birim Çarpanı ve Brüt Hammadde İhtiyaç Katkısı.

5. **Tam Dil Desteği:**
   - Modal içerisindeki tüm etiketler, butonlar, uyarılar ve ölçü birimleri TR, EN ve DE dillerinde Title Case standartlarına tam uyumludur.

---

## 8. Bu Raporun Bağlantıları

```
Periyodik Satış Siparişleri → Üretime Başlama Haftası → Kapasite Planlama → [Malzeme İhtiyaç] → Önerilen PO
                                                                         ↘ MRP Analiz (brüt ihtiyaç)
```

- **Girdi:** Kapasite Planlama'nın haftalık üretim planı (`build_capacity_plan`).
- **MRP Analiz:** Aynı servisten brüt ihtiyacı müşteri grubu kırılımıyla alır.
- **Önerilen PO:** Bu raporun önerilen siparişlerini tedarikçi temin süresi kadar öne alır.
