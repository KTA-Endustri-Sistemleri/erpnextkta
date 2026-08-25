---
layout: default
title: "MRP Analiz Raporu (MRP Analysis)"
---

# 📊 MRP Analiz Raporu (MRP Analysis) Kullanım Kılavuzu

Bu rapor, MRP zincirinin **en üst düzey özet ekranıdır.** Malzeme İhtiyaç raporundan gelen tüm hammadde tüketim verilerini alarak, bunları **hammadde bazında**, **müşteri grubu kırılımıyla** ve mevcut **stok değerleriyle** birlikte sunar. Satın alma departmanının stratejik karar vermesi için tasarlanmıştır.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Her hammaddenin toplam tahmini tüketimini ve mevcut stokla karşılama durumunu görürsünüz.
- Tüketimin **hangi müşteri grubundan** (İç Piyasa, İhracat vb.) geldiğini analiz edersiniz.
- Hammaddelerin birim fiyatları, stok değerleri ve tedarikçi bilgileriyle birlikte bütünsel bir tablo elde edersiniz.
- Stokta olup hiç tüketimi olmayan kalemleri de görerek ölü stok analizi yapabilirsiniz.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor, arka planda **Malzeme İhtiyaç Raporu**'nu `stage = "1 - Temel Hammadde İhtiyacı"` ve `group_by = "Bitmiş Ürün + Hammadde"` modunda çalıştırır. Bu sayede her hammaddenin hangi bitmiş üründen ve hangi müşteri grubundan tüketildiğini bilir.

### 🧮 Müşteri Grubu Kırılımı
1. Her bitmiş ürünün `custom_musteri_grubu` alanından müşteri grubu belirlenir.
2. Hammadde tüketimi, bu müşteri gruplarına göre dağıtılır.
3. Raporda her KTA Customer Group için ayrı bir sütun oluşturulur.

### 💰 Fiyat Bilgisi
- **Varsayılan tedarikçi fiyatı:** `Fiyat Varsayılan Tedarikçi` filtresi açıkken, sadece varsayılan tedarikçinin son fiyatı gösterilir.
- **Genel son fiyat:** Filtre kapalıyken, tüm tedarikçiler arasından en son girilen alış fiyatı gösterilir.

### 📦 Stok Verisi
`Kullanılabilir Stok` tipindeki depolardaki toplam miktar (`actual_qty`) ve stok değeri (`stock_value`) çekilir.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Periyot** | Zaman aralığını belirler: Yıllık, 3 Aylık, 6 Aylık, Süresiz | Yıllık |
| **Ürün Grubu** | Belirli bir ürün grubuna göre filtreleme | (Hepsi) |
| **Ara Malzeme Grubu** | Hammaddeleri ara malzeme grubuna göre filtreleme | (Hepsi) |
| **Müşteri Grubu** | Birden fazla müşteri grubu seçilebilir (MultiSelect) | (Hepsi) |
| **Varsayılan Tedarikçi** | Belirli bir tedarikçiye göre filtreleme | (Hepsi) |
| **Sıfır Tüketimi Göster** | Tüketimi olmayan ama depoda stoku olan hammaddeleri de gösterir | Kapalı |
| **Fiyat Varsayılan Tedarikçi** | Açıkken sadece varsayılan tedarikçinin fiyatını gösterir | Kapalı |

---

## 4. Tablo Kolonları

| Kolon | Açıklama |
|-------|----------|
| **Hammadde Kodu** | Hammadde item kodu |
| **Grup** | Hammaddenin ürün grubu (Item Group) |
| **Hammadde Adı** | Hammaddenin tanım adı |
| **Varsayılan Tedarikçi** | Item Default'taki varsayılan tedarikçi |
| **Fiyat** | Son alış fiyatı |
| **Para Birimi** | Fiyatın para birimi (EUR, TRY vb.) |
| **Depo Stok** | Mevcut stok miktarı (Kullanılabilir Stok depoları) |
| **Bakiye Değeri** | Mevcut stokun toplam parasal değeri |
| **Müşteri Grubu Dağılımı** | Tüketimin müşteri gruplarına göre yüzde dağılımı (Örn: "İhracat%65.2-İç Piyasa%34.8") |
| **Ara Malzeme Grubu** | Hammaddenin ara malzeme grubu sınıflandırması |
| **[Müşteri Grubu] Sütunları** | Her KTA Customer Group için ayrı tüketim miktarı |
| **Genel Toplam** | Tüm müşteri gruplarındaki toplam tüketim |
| **Müşteri Grubu** | Hammaddenin kendi Item kaydındaki müşteri grubu atanması |
| **Toplam Tüketim (Kapasite)** | Kapasite planından gelen toplam brüt tüketim |
| **Fark Oran** | Toplam Tüketim ile Genel Toplam arasındaki fark yüzdesi |

---

## 5. Sıralama ve Toplam Satırı

- Veriler **bakiye değerine göre büyükten küçüğe** sıralanır (en değerli stoku olan hammadde en üstte).
- Son satırda tüm kolonlar için **TOPLAM** satırı gösterilir.

---

## 6. Özet Kartları

- **🔵 Toplam Kalem:** Rapordaki benzersiz hammadde sayısı.
- **🔴 Eksik Kalem:** Depo stoğu, tahmini tüketimden az olan hammadde sayısı.
- **🟢 Toplam Stok Değeri:** Tüm hammaddelerin toplam parasal stok değeri.

---

## 7. Bu Raporun Bağlantıları

```
Periyodik Satış Siparişleri → Üretime Başlama Haftası → Kapasite Planlama → Malzeme İhtiyaç → [MRP Analiz]
```

Bu rapor MRP zincirinin **son halkasıdır** ve tüketim verilerini stratejik bir özet olarak sunar.
