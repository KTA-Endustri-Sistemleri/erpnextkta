---
layout: default
title: "Sevkiyat Haftası (Shipment Week)"
---

# 🚚 Sevkiyat Haftası (Shipment Week) Kullanım Kılavuzu

Bu rapor, açık satış siparişlerinin teslimat tarihlerinden müşterinin sevkiyat süresini düşerek **"Bu ürünün fabrikadan en geç hangi hafta çıkması gerekiyor?"** sorusunu cevaplar. Lojistik ve depo ekipleri için tasarlanmıştır.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Her müşteri ve ürün için **fabrikadan sevk edilmesi gereken haftayı** görürsünüz.
- Teslimat tarihleri yerine **fiili sevkiyat tarihlerini** baz alarak lojistik planlamanızı yaparsınız.
- Haftalık sevkiyat yoğunluğunu grafik üzerinden takip edersiniz.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor, arka planda **Periyodik Satış Siparişleri** raporunu `show_pending_only = 1` ve `value_quantity = "Quantity"` modunda çalıştırır.

### 🧮 Sevkiyat Haftası Hesaplaması
Her sipariş kalemi için:

```
Sevkiyat Tarihi = Teslimat Haftasının Son Günü − Sevkiyat Süresi (gün)
```

- **Sevkiyat Süresi**, müşteri ve sevkiyat adresine göre **KTA Sevk Parametreleri** DocType'ından `delivery_time` alanı olarak alınır.
- Önce müşteri + adres eşleşmesi denenir, bulunamazsa sadece müşteri adına bakılır.
- Hesaplanan tarihin ISO hafta etiketi (`Yıl-WHafta`) sevkiyat haftasını belirler.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Analiz periyodunun başlangıcı | 1 ay önce |
| **Bitiş Tarihi** | Analiz periyodunun bitişi | 2 ay sonra |
| **Müşteri** | Belirli bir müşteriye filtreleme | (Hepsi) |

---

## 4. Tablo Kolonları

| Kolon | Açıklama |
|-------|----------|
| **Müşteri** | Siparişteki müşteri adı |
| **Ürün Kodu** | Sevk edilecek ürünün kodu |
| **Ürün Adı** | Sevk edilecek ürünün adı |
| **Adres** | Sevkiyat adresi |
| **Haftalık Sütunlar** (Örn: 2026-W35) | O hafta sevk edilmesi gereken miktar |
| **Toplam** | Tüm haftalar boyunca sevk edilecek toplam miktar |

---

## 5. Grafik ve Özet Kartları

- **📊 Çubuk Grafik:** Hafta bazında toplam sevkiyat miktarını görselleştirir.
- **🔵 Toplam Sevk Miktarı:** Tüm zaman aralığındaki sevk edilecek toplam adet.
- **🟢 Sevk Edilecek Kalem:** Rapordaki benzersiz müşteri-ürün-adres kombinasyon sayısı.

---

## 6. Bu Raporun Bağlantıları

Bu rapor bağımsız bir rapordur; doğrudan MRP zincirine besleme yapmaz. **Üretime Başlama Haftası** raporuyla aynı veri kaynağını (Satış Siparişleri) kullanır ancak farklı bir perspektif sunar:
- **Üretime Başlama Haftası:** "Ne zaman üretmeliyim?" (Üretim bakış açısı)
- **Sevkiyat Haftası:** "Ne zaman sevk etmeliyim?" (Lojistik bakış açısı)
