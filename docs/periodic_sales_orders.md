---
layout: default
title: "Periyodik Satış Siparişleri (MRP)"
---

# 📈 Periyodik Satış Siparişleri (MRP) Kullanım Kılavuzu

Bu rapor, firmanızın aldığı satış siparişlerinin teslimat tarihlerine göre geleceğe yönelik dağılımını gösteren stratejik bir analiz ekranıdır. Üretim planlama (MRP), nakit akışı ve kapasite öngörüleri için tasarlanmıştır.

## 1. Raporun Temel Amacı
Bu ekran sayesinde:
- Hangi müşteriye, hangi ay ne kadarlık ürün teslim etmeniz gerektiğini,
- Önümüzdeki haftalarda/aylarda kasanıza girecek paranın (EUR/TRY vb.) kur bazlı dağılımını,
- Bekleyen sipariş yükünüzü tek bir ekranda, modern grafiklerle görebilirsiniz.

---

## 2. Filtreler ve Kullanımı

Raporu kendi ihtiyaçlarınıza göre şekillendirmek için üst bölümdeki filtreleri kullanabilirsiniz:

### 📅 Tarih Aralığı (From Date - To Date)
Analiz etmek istediğiniz zaman aralığını seçin (Örn: 1 Ocak - 31 Aralık). Rapor sadece **teslimat tarihi** bu aralığa düşen siparişleri getirecektir.

### ⏱️ Periyot (Range)
Zaman çizelgesinin (sağdaki sütunların) nasıl bölüneceğini belirler:
- **Haftalık:** Verileri hafta hafta gösterir (Örn: 2026-W37). Üretime haftalık plan verenler için idealdir.
- **Aylık:** Her sütunda 1 aylık veriyi gösterir (Oca, Şub, Mar...).
- **Üç Aylık:** Yılı çeyrek bazında (Q1, Q2, Q3, Q4) değerlendirmenizi sağlar. Yöneticiler için idealdir.
- **Yıllık:** Uzun vadeli projeksiyonlar için yılı tek sütunda toplar (2026, 2027).

### 🌳 Ağaç Kırılımı (Tree Type)
Tablodaki satırların neye göre gruplanacağını seçersiniz:
- **Müşteri:** Müşterileri listeler, müşteri isminin solundaki ok işaretine (►) basarak o müşterinin hangi ürünleri aldığını alt satırlarda görebilirsiniz.
- **Müşteri Grubu:** Önce İç Piyasa / İhracat gibi grupları, sonra altındaki müşterileri listeler.
- **Ürün Grubu:** Talebi ürün bazlı (Örn: Kablo, Terminal) değerlendirmek için kullanılır.

### 💰 Değer Türü (Value/Quantity)
Raporda neyi görmek istediğinizi belirler:
- **Miktar:** Satış siparişlerindeki adet/metre gibi birimleri gösterir (Üretim planlamacılar için).
- **Tutar:** Satışların finansal karşılığını, yani parayı gösterir (Yöneticiler/Finans için).

### 💱 Hedef Döviz (Target Currency)
Eğer raporda hem TRY hem EUR siparişler varsa ve siz tüm bu tabloyu **tek bir para birimi** üzerinden okumak isterseniz (Örn: "Tüm sipariş portföyümün toplam Euro karşılığı nedir?"), bu alanı kullanabilirsiniz. Sistem arkaplanda güncel çapraz kurları (cross-rate) kullanarak tüm tabloyu seçtiğiniz dövize otomatik olarak çevirir. Boş bırakırsanız siparişler kendi orijinal dövizlerinde gösterilir.

---

## 3. Ekran Bölümleri

### 📊 Renkli Özet Kartları
Ekranın en üstünde yer alan gösterge paneli size anlık özet sunar:
- Seçili tarih aralığındaki toplam sipariş tutarlarını **TRY**, **EUR** veya diğer dövizler olarak birbirine karıştırmadan, tamamen ayrı kartlar halinde gösterir.
- Toplam müşteri/ürün satır sayısını belirtir.

### 📈 Çoklu Çizgi Grafiği
Tablodaki verilerin görselleştirilmiş halidir. Eğer tabloda birden fazla döviz varsa, grafik üzerinde her bir döviz türü farklı renkte (örneğin TRY turuncu, EUR mavi) ayrı bir çizgi olarak belirir. Böylece cironuzun döviz dengesini görsel olarak takip edebilirsiniz.

### 📋 Veri Tablosu ve Akıllı Özellikler
Ekranın en altındaki tablo bölümü detaylı verileri barındırır. Bu tablonun bazı "akıllı" özellikleri vardır:

- **Otomatik EUR Fiyat Algılama:** Henüz faturası kesilmemiş (üretimi bekleyen) siparişlerinizde, müşterinin anlaştığı standart bir EUR fiyatı varsa; sipariş sisteme yanlışlıkla TRY girilmiş olsa bile rapor akıllı bir şekilde devreye girer ve size **gerçek EUR fiyatını** yansıtır. Bu sayede kur dalgalanmalarından kaynaklı kâr/zarar illüzyonuna düşmezsiniz.
- **Hatasız Genel Toplamlar:** Tablonun en alt satırında dövizler asla elma-armut gibi birbirine toplanmaz. Tablo altına "Genel Toplam (TRY)" ve "Genel Toplam (EUR)" olarak döviz sayısına göre otomatik çoğalan yepyeni satırlar açılır. Hiçbir finansal veriniz birbirine karışmaz.
