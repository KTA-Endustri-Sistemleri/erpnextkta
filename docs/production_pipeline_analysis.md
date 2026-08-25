---
layout: default
title: "Üretim Pipeline Analizi (Production Pipeline Analysis)"
---

# 🔬 Üretim Pipeline Analizi (Production Pipeline Analysis) Kullanım Kılavuzu

Bu rapor, satış siparişlerinden fabrika çıkışına kadar tüm üretim hattını **tek bir ekranda, aşama aşama** görselleştiren stratejik bir analiz aracıdır. Her hafta için müşteri beklentisi, sevkiyat ihtiyacı, üretim planı, açık iş emirleri ve stok bakiyesini katman katman gösterir.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Üretim hattınızın **8 aşamasını** tek bir tabloda karşılaştırmalı olarak görürsünüz.
- Haftalık **stok evrimini** (stock evolution) izleyerek stok fazlası veya kıtlığı önceden tespit edersiniz.
- Kapasite sınırlarını dikkate alarak **yeni planlanması gereken üretimi** görürsünüz.
- Geçmiş sevkiyat gecikmelerinin (backlog) mevcut plana etkisini anlarsınız.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynakları
Rapor, doğrudan birden fazla kaynağı sorgular:
1. **Satış Siparişleri (Sales Order):** Teslimatı bekleyen tüm sipariş kalemleri.
2. **KTA Sevk Parametreleri:** Müşteriye özel üretim ve sevkiyat süreleri.
3. **Açık İş Emirleri (Work Order):** `Not Started` veya `In Process` durumundaki iş emirleri.
4. **Fiziksel Stok (Bin):** Seçilen depolardaki mevcut stok.
5. **Kapasite:** Ürün grubunun haftalık üretim kapasitesi.

### 🧮 Kapasite Tespiti
Kapasite üç katmanlı bir öncelik sırasıyla belirlenir:
1. **Tanımlı Kapasite:** Ürün grubundaki en yüksek `custom_weekly_production` değeri.
2. **Geçmiş Veri Kapasitesi:** Son 3 ayda tamamlanan iş emirlerinin haftalık ortalaması.
3. Hiçbiri yoksa **sınırsız (999999)** kabul edilir.

### 📊 8 Aşamalı Pipeline

| # | Aşama | Hesaplama |
|---|-------|-----------|
| 1 | **Müşteri Beklentisi (Teslimat)** | SO'daki teslimat tarihine göre haftalara dağıtılmış miktar |
| 2 | **Sevkiyat Haftası (Fabrika Çıkış)** | Teslimat − Sevkiyat Süresi |
| 3 | **Üretim Başlama (Teorik İhtiyaç)** | Teslimat − (Sevkiyat + Üretim Süresi) |
| 4 | **İdeal Haftalık Üretim (Hedef)** | Net toplam ihtiyacın haftalara eşit dağıtılmış hali |
| 5 | **Devam Eden Üretim (Açık İş Emirleri)** | WIP iş emirlerinin planlanan bitiş haftasına dağıtılmış miktarı |
| 6 | **Yeni Planlanacak Üretim (Ek Kapasite)** | Kalan kapasite dahilinde eklenmesi gereken yeni üretim |
| 7 | **Toplam Üretim Girişi** | Aşama 5 + Aşama 6 |
| 8 | **Beklenen Stok Bakiyesi** | (Önceki Stok + Toplam Üretim Girişi) − Sevkiyat |

### 🔄 Dengeleme Algoritması
Her hafta için:
1. Mevcut stok + devam eden üretim (WIP), sevkiyat talebini karşılıyor mu kontrol edilir.
2. **Eksik varsa:** Kalan kapasite (toplam kapasite − WIP) kadar yeni üretim planlanır.
3. **Yeterliyse:** Sadece teorik ihtiyaç kadar yeni üretim planlanır (kapasiteyi aşmadan).
4. Üretim miktarları müşteri paketleme biriminin katına yuvarlanır.

### 📦 Müşteri Paketleme
Sipariş miktarları, `Item Customer` tablosundaki `custom_musteri_paketleme_miktari` alanına göre yukarı yuvarlanır.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Analiz periyodunun başlangıcı | Bugün |
| **Bitiş Tarihi** | Analiz periyodunun bitişi | Bugünden 90 gün sonra |
| **Ürün Grubu** | Belirli bir ürün grubuna filtreleme (zorunlu değil ama önerilir) | (Hepsi) |
| **Müşteri** | Belirli bir müşteriye filtreleme | (Hepsi) |
| **Depolar** | Stok bakiyesi hesaplaması için kullanılacak depolar | (Boş = stok hesaplanmaz) |

---

## 4. Tablo Yapısı

Bu rapor diğerlerinden farklı olarak **satırlarda haftalar yerine aşamalar** yer alır:

| Kolon | Açıklama |
|-------|----------|
| **Aşama** | Pipeline'ın 8 aşamasından biri |
| **Haftalık Sütunlar** (Örn: 2026-W35) | Her aşama için o haftadaki değer |
| **Toplam** | Satır toplamı (Stok Bakiyesi satırı hariç — o son haftanın değerini gösterir) |

---

## 5. Grafik

**Karma Grafik (Axis-Mixed):** 4 katmanlı görselleştirme:
- 🔴 **Çubuk — Haftalık Sevkiyat:** O hafta sevk edilmesi gereken miktar.
- 🟢 **Çubuk — Haftalık Üretim:** O hafta yapılacak toplam üretim (WIP + Yeni).
- 🔵 **Çizgi — Stok Bakiyesi:** Hafta sonunda beklenen stok miktarı.
- 🔴 **Çizgi — Kapasite:** Haftalık üretim kapasite limiti.

---

## 6. Bilgi Mesajı

Grafik altında bir bilgi mesajı gösterilir:
```
Geçmiş Veri Kapasitesi: X | Tanımlı Kapasite: Y | Açık İ.E: Z | Toplam Backlog: W
```

---

## 7. Bu Raporun Bağlantıları

Bu rapor **bağımsız bir stratejik analiz aracıdır.** MRP zincirine doğrudan veri beslemez ancak aynı veri kaynaklarını (Satış Siparişleri, Sevk Parametreleri, İş Emirleri, Stok) kullanarak üst düzey bir bütünsel bakış sunar.
