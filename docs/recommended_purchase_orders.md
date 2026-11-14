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
- Sipariş miktarları, Malzeme İhtiyaç raporundaki **Önerilen Sipariş** ile birebir aynıdır (MOQ ve paket katı orada uygulanır).

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor, Malzeme İhtiyaç raporuyla aynı servis katmanını (`erpnextkta/kta_mrp/mrp_engine`) kullanır ve stok + açık PO'larla netleştirilmiş, MOQ/paket katına yuvarlanmış **haftalık önerilen siparişleri** alır. Ürün Grubu filtresi talep tarafına (bitmiş ürünler) uygulanır.

### 🧮 Sipariş Zamanlaması
Her hammadde için:

```
Sipariş Haftası = İhtiyaç Haftası − Temin Süresi (gün)
```

**Temin Süresi (Lead Time)**, varsayılan tedarikçinin `Item Price` kaydındaki `lead_time_days` alanından alınır.

### 📦 MOQ ve Paketleme
Yuvarlama Malzeme İhtiyaç raporunda bir kez yapılır. Bu rapor miktarları tekrar yuvarlamaz; sadece temin süresi kadar öne alır.

### 🤝 Çoklu Tedarikçi ve Kotalı Dağıtım (Quota Share Lead Time & Satır Ayrıştırma)
Kalemde tanımlı bir `Item Sourcing Strategy` (örneğin %60 Tedarikçi A, %40 Tedarikçi B) bulunduğunda:
- Malzeme İhtiyaç motoru siparişi kotalara göre böler ve her tedarikçinin kendi MOQ/paket katına göre lot sizing yapar.
- Önerilen PO raporu, her tedarikçi için **bağımsız bir satır** açar.
- Her satırda o tedarikçiye ait **MOQ**, **Paketleme Miktarı** ve **kendi temin süresi (Lead Time)** listelenir.
- Sipariş haftaları o tedarikçinin temin süresi kadar geriye ötelenir; böylece uzun terminli tedarikçiye erken, kısa terminli tedarikçiye geç sipariş verilmesi sağlanır.

### ⚠️ Gecikmiş / Acil Siparişler (Past-Due Clamping)
- Eğer `İhtiyaç Haftası − Temin Süresi` sonucu planlama ufkundan (mevcut haftadan) önceye düşüyorsa, sistem geçmiş haftalara ait gereksiz kolonlar açmaz.
- Bu siparişler otomatik olarak **ilk geçerli haftaya (`first_valid_week`) kilitlenir**.
- İlgili satırda `Durum` kolonu **`Acil / Gecikmiş`** olarak işaretlenir (`is_past_due = 1`), böylece satın alma departmanı derhal aksiyon alması gerektiğini görür.

### 🔍 Tedarikçi Bilgisi
Tanımlı tedarikçisi veya alış fiyatı olmayan hammaddeler de listelenir (MOQ 0, paket 1, temin süresi 0 kabul edilir). Tedarikçi kolonu boş olan satırlar için kalem kartını tamamlayın.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Sistem tarafından otomatik olarak **bulunulan haftanın Pazartesi gününe** kilitlenir. Geçmiş tarih seçimi engellenmiştir. | Bu Haftanın Pazartesi Günü |
| **Bitiş Tarihi (Planlama Ufku)** | Planlama periyodunun bitişi. Varsayılan `KTA MRP Settings` (90 gün) ayarından gelir, 1 yıla kadar genişletilebilir. | Bugün + 90 gün |
| **Ürün Grubu** | Belirli bir ürün grubuna filtreleme | (Hepsi) |

> **📅 Sabit Başlangıç Kuralı:** Malzeme İhtiyaç raporuyla tam senkronizasyon için başlangıç tarihi filtresi kullanıcı girişine kapatılmış ve her zaman cari haftanın Pazartesi gününe sabitlenmiştir.

---

## 4. Tablo Kolonları

| Kolon | Açıklama |
|-------|----------|
| **Hammadde** | Hammadde item kodu |
| **Tedarikçi** | İlgili satırın tedarikçisi (kotalı ise her tedarikçi ayrı satır) |
| **Birim** | Stok birimi |
| **Lead Time (Gün)** | İlgili tedarikçinin temin süresi (gün) |
| **MOQ** | İlgili tedarikçinin minimum sipariş miktarı |
| **Paket Miktarı** | İlgili tedarikçinin paketleme birimi |
| **Durum** | Normal veya Acil / Gecikmiş (temin süresi bugünü aşanlar) |
| **Haftalık Sütunlar** (Örn: 2026-W35) | O hafta verilmesi önerilen sipariş miktarı |
| **Satır Toplamı** | Tüm haftalar için toplam önerilen sipariş miktarı |

---

## 5. Özet Kartları

- **🔵 Önerilen PO Sayısı:** Rapordaki benzersiz hammadde-tedarikçi kombinasyon sayısı.
- **🟢 Toplam Önerilen Miktar:** Tüm hammaddeler için önerilen toplam sipariş miktarı.

---

## 6. Bu Raporun Bağlantıları

```
... → Kapasite Planlama → Malzeme İhtiyaç (Önerilen Sipariş) → [Önerilen PO]
```

Bu rapor, MRP zincirinin **satın alma aksiyona dönüşen son çıktısıdır.**
