---
layout: default
title: "Üretime Başlama Haftası (Production Start Week)"
---

# 🏭 Üretime Başlama Haftası (Production Start Week) Kullanım Kılavuzu

Bu rapor, açık satış siparişlerindeki teslimat tarihlerini, müşteriye özgü üretim ve sevkiyat sürelerini hesaba katarak **"Bu ürünün üretimine en geç hangi hafta başlanmalı?"** sorusunu cevaplar. MRP zincirinin en kritik halkasıdır; Kapasite Planlama ve Malzeme İhtiyaç raporları bu raporun çıktısını kullanır.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Her ürünün, teslimatı yakalayabilmek için **üretime en geç ne zaman başlanması gerektiğini** hafta bazında görürsünüz.
- Bitmiş ürün stokunun hangi haftaların talebini karşıladığını, hangilerinin üretilmesi gerektiğini anlarsınız.
- Müşteri bazlı veya sadece ürün bazlı gruplama yaparak farklı bakış açıları elde edersiniz.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor, **Periyodik Satış Siparişleri** raporunu arka planda `show_pending_only = 1` (sadece teslim edilmemiş siparişler) ve `value_quantity = "Quantity"` (miktar modunda) çalıştırarak tüm açık satış siparişlerini çeker.

### ⏳ Üretime Başlama Tarihi Hesaplaması
Her sipariş kalemi için teslim tarihinden geriye doğru gidilir:

```
Üretime Başlama Tarihi = Teslimat Tarihi − (Üretim Süresi + Sevkiyat Süresi)
```

- **Üretim Süresi** ve **Sevkiyat Süresi** değerleri, her müşteri/sevk adresi için ayrı ayrı tanımlanan **KTA Sevk Parametreleri** DocType'ından alınır.
- Eşleşme bulunamazsa, teslimat tarihi olduğu gibi kullanılır ve rapor sonunda eşleşmeyen müşteriler listesi bildirilir.

### 📊 Stok Düşme Mantığı
Bitmiş ürünlerin deposundaki (`warehouse_type = "Kullanılabilir Stok"`) mevcut stok, haftalara kronolojik sırayla dağıtılır:
1. İlk haftanın talebi stoktan karşılanabildiği kadar karşılanır.
2. Kalan stok bir sonraki haftaya aktarılır.
3. Stok tükendiğinde, kalan talep "Üretilecek" olarak işaretlenir.

### 📦 Müşteri Paketleme Yuvarlaması
Üretilmesi gereken miktar belirlenirken, `Item Customer` tablosundaki `custom_musteri_paketleme_miktari` alanına bakılır. Eğer müşteriye özel bir paketleme miktarı tanımlıysa, üretim miktarı bu değerin katına yukarı yuvarlanır. Fazlalık sonraki haftalar için stok olarak kullanılır.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Analiz periyodunun başlangıcı | Bugün |
| **Bitiş Tarihi** | Analiz periyodunun bitişi | Bugünden 3 ay sonra |
| **Ürün Grubu** | Belirli bir ürün grubuna filtreleme | (Hepsi) |
| **Yalnızca Ürün Bazlı Grupla** | İşaretlenirse müşteri kırılımı gösterilmez, sadece ürün bazında toplanır | Kapalı |

---

## 4. Tablo Kolonları

| Kolon | Açıklama |
|-------|----------|
| **Ürün Grubu** | Ürünün ait olduğu Item Group |
| **Müşteri** | Siparişi veren müşteri (sadece ürün bazlı gruplama kapalıyken görünür) |
| **Ürün Kodu** | Bitmiş ürünün kodu |
| **Ürün Adı** | Bitmiş ürünün adı |
| **Haftalık Sütunlar** (Örn: 2026-W35) | O hafta üretilmesi gereken net miktar (stok düşülmüş) |
| **Stok Karşılanan** | Mevcut stoktan karşılanan toplam miktar |
| **Üretilecek** | Üretilmesi gereken toplam miktar |
| **Toplam** | Brüt toplam talep (stok düşülmeden önceki ham talep) |
| **Birim** | Ölçü birimi |

---

## 5. Grafik ve Özet Kartları

- **📊 Çubuk Grafik:** Hafta bazında üretilmesi gereken miktarları görselleştirir.
- **🟠 Toplam Üretilecek:** Stok düşüldükten sonra üretilmesi gereken toplam adet.
- **🟢 Stoktan Karşılanan:** Mevcut stokla karşılanan toplam adet.

---

## 6. Bu Raporu Kullanan Diğer Raporlar

Bu rapor, MRP zincirinin merkezinde yer alır:
- **Kapasite Planlama Raporu:** Bu raporun çıktısını alarak haftalık üretim kapasitesiyle dengeler.
- **Malzeme İhtiyaç Raporu:** Kapasite Planlama'nın çıktısını BOM ile çarparak hammadde ihtiyacını hesaplar.
