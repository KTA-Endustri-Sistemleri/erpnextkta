---
layout: default
title: "Önerilen Satın Alma Siparişleri (Recommended Purchase Orders)"
---

# 🛒 Önerilen Satın Alma Siparişleri (Recommended Purchase Orders) Kullanım Kılavuzu

Bu rapor, **Malzeme İhtiyaç** raporunun çıktısını alarak, tedarikçi bilgilerini (temin süresi, MOQ, paketleme miktarı) dikkate alıp **"Bu hammadde için hangi hafta, ne kadar satın alma siparişi verilmeli?"** sorusunu cevaplar. Satın alma departmanının operasyonel karar mekanizmasıdır.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Her hammadde için **sipariş verilmesi gereken haftayı** (temin süresi düşülerek) görürsünüz.
- Siparişlerin **MOQ (Minimum Sipariş Miktarı)** ve **paketleme katlarına** uygun şekilde otomatik yuvarlandığını görürsünüz.
- Küçük haftalık ihtiyaçların birleştirilerek verimli sipariş miktarlarına dönüştürüldüğünü görürsünüz.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor, arka planda **Malzeme İhtiyaç Raporu**'nu `stage = "Stokları Düş + PO Teslimatlarını Düş"` ve `group_by = "Sadece Hammadde"` modunda çalıştırır. Bu, mevcut stok ve açık PO'lar düşüldükten sonraki **net haftalık hammadde ihtiyacını** verir.

### 🧮 Sipariş Zamanlaması
Her hammadde için:

```
Sipariş Haftası = İhtiyaç Haftası − Temin Süresi (gün)
```

**Temin Süresi (Lead Time)**, varsayılan tedarikçinin `Item Price` kaydındaki `lead_time_days` alanından alınır.

### 📦 MOQ ve Paketleme Yuvarlaması
1. Eğer bir haftanın ihtiyacı MOQ'nun altındaysa, sonraki haftaların ihtiyaçları çekilerek MOQ'ya ulaşılmaya çalışılır.
2. Toplam miktar, paketleme miktarının (`custom_minimum_paketleme_miktari`) katına yukarı yuvarlanır.
3. Yuvarlamadan kaynaklı fazlalık, sonraki haftaların ihtiyacından düşürülür.
4. Son haftadaysa ve MOQ karşılanamıyorsa, ihtiyaç olduğu gibi sipariş olarak önerilir.

### 🔍 Tedarikçi Koşulu
Varsayılan tedarikçisi (`Item Default.default_supplier`) olmayan veya o tedarikçi için `Item Price` kaydı bulunmayan hammaddeler raporda yer almaz.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Planlama periyodunun başlangıcı | Bugün |
| **Bitiş Tarihi** | Planlama periyodunun bitişi | Bugünden 3 ay sonra |
| **Ürün Grubu** | Belirli bir ürün grubuna filtreleme | (Hepsi) |

---

## 4. Tablo Kolonları

| Kolon | Açıklama |
|-------|----------|
| **Hammadde** | Hammadde item kodu |
| **Tedarikçi** | Varsayılan tedarikçi |
| **Birim** | Stok birimi |
| **Lead Time (Gün)** | Temin süresi (gün) |
| **MOQ** | Minimum sipariş miktarı |
| **Paket Miktarı** | Paketleme birimi (sipariş bu katın çarpanına yuvarlanır) |
| **Haftalık Sütunlar** (Örn: 2026-W35) | O hafta verilmesi önerilen sipariş miktarı |
| **Satır Toplamı** | Tüm haftalar için toplam önerilen sipariş miktarı |

---

## 5. Özet Kartları

- **🔵 Önerilen PO Sayısı:** Rapordaki benzersiz hammadde-tedarikçi kombinasyon sayısı.
- **🟢 Toplam Önerilen Miktar:** Tüm hammaddeler için önerilen toplam sipariş miktarı.

---

## 6. Bu Raporun Bağlantıları

```
... → Kapasite Planlama → Malzeme İhtiyaç (Stok+PO Düş) → [Önerilen PO]
```

Bu rapor, MRP zincirinin **satın alma aksiyona dönüşen son çıktısıdır.**
