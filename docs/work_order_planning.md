---
layout: default
title: "İş Emri Planlama (Work Order Planning)"
---

# 📋 İş Emri Planlama (Work Order Planning) Kullanım Kılavuzu

Bu rapor, **Kapasite Planlama** raporundan gelen haftalık üretim planını, mevcut açık İş Emirleri (Work Order) ile karşılaştırarak **"Hangi hafta için yeni iş emri oluşturulması gerekiyor?"** sorusunu cevaplar. Üretim planlamacılarının operasyonel iş emri yönetimi için tasarlanmıştır.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Her ürün ve hafta için **planlanan üretim miktarını** görürsünüz.
- Mevcut açık iş emirlerinin bu planı **ne kadar karşıladığını** görürsünüz.
- Eksik kalan miktarlar için **yeni iş emri ihtiyacını** otomatik olarak tespit edersiniz.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor iki farklı kaynaktan beslenir:
1. **Kapasite Planlama Raporu:** Haftalık planlanmış üretim miktarları.
2. **Work Order (İş Emri):** Sistemdeki iptal edilmemiş ve tamamlanmamış tüm açık iş emirleri.

### 🧮 Hesaplama Mantığı
Her ürün için:

1. **Geçmiş İş Emirleri (Backlog):** `planned_start_date` bugünden önceki iş emirlerinin kalan miktarları (`qty - produced_qty`) toplanır.
2. **Gelecek İş Emirleri:** ISO hafta etiketine göre haftalara dağıtılır.
3. **Her hafta için:**
   - `Planlanan Üretim (P)` = Kapasite Planlama raporundan gelen miktar.
   - `Açık İş Emri (O)` = O haftaya atanmış iş emirlerinin kalan miktarı + geçmiş backlog'dan kullanılabilir miktar.
   - `Yeni İş Emri İhtiyacı (R)` = `max(P − O, 0)` — plan ile mevcut iş emirleri arasındaki fark.

4. Backlog öncelikli olarak ilk haftalara dağıtılır ve tükendikçe sonraki haftalara geçilir.

### 📋 Sayısal Netleştirme Örnek Senaryosu

| Hafta | Planlanan Üretim | Mevcut Açık İş Emri (WIP) | Kalan / Devreden WIP | Yeni Açılacak İş Emri | Durum / Açıklama |
|:------|:----------------:|:-------------------------:|:--------------------:|:---------------------:|:-----------------|
| **2026-W45 (Bu Hafta)** | 500 ad. | 300 ad. `(MFG-05164)` | 0 ad. | **200 ad.** | `⚠️ Eksik — Yeni İş Emri Açılmalı` |
| **2026-W46 (Gelecek)** | 400 ad. | 500 ad. `(MFG-04684)` | **+100 ad. devir** | **0 ad.** | `✓ WIP Karşıladı (+100 Devretti)` |
| **2026-W47 (2 Hafta Sonra)** | 300 ad. | 0 ad. | 0 ad. | **200 ad.** | `100 Devirden Düştü, 200 Yeni Açık` |
| **TOPLAM** | **1.200 ad.** | **800 ad.** | - | **400 ad.** | `✓ %66,7 WIP / %33,3 Yeni İş Emri` |

> **💡 Devir Mantığı:** W46'da 500 adet açık iş emri varken talep 400 adettir. Kalan 100 adetlik WIP fazlalığı silinmez; otomatik olarak W47'ye devredilir. Böylece W47'nin 300 adetlik talebinin 100'ü bu devirden karşılanır ve sadece 200 adetlik yeni iş emri ihtiyacı doğar.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|---|---|---|
| **Başlangıç Tarihi** | Sistem tarafından otomatik olarak **bulunulan haftanın Pazartesi gününe** kilitlenir. Geçmiş tarih seçimi engellenmiştir. | Bu Haftanın Pazartesi Günü |
| **Bitiş Tarihi (Planlama Ufku)** | Planlama periyodunun bitişi. Varsayılan `KTA MRP Settings` (90 gün) ayarından gelir, 1 yıla kadar genişletilebilir. | Bugün + 90 gün |
| **Müşteri Grubu** | Belirli bir müşteri grubuna filtreleme | (Hepsi) |
| **Ürün Grubu** | Belirli bir ürün grubuna filtreleme | (Hepsi) |

> **⚙️ Kapasite Parametreleri:** Bu raporun dayandığı kapasite planlama algoritması, **KTA MRP Settings** altındaki merkezi ayarlarla çalışmaktadır.

---

## 4. Tablo Kolonları

| Kolon | Açıklama |
|-------|----------|
| **Ürün Grubu** | Ürünün ait olduğu Item Group |
| **Ürün** | Bitmiş ürün kodu |
| **Hafta** | ISO hafta etiketi (Örn: 2026-W35) |
| **Planlanan Üretim** | Kapasite Planlama'dan gelen planlı miktar |
| **Açık İş Emri Miktarı** | O hafta için mevcut açık iş emirlerinin kalan miktarı |
| **Yeni İş Emri İhtiyacı** | Açılması gereken yeni iş emri miktarı (Planlanan − Açık) |

---

## 5. Grafik ve Özet Kartları

- **📊 Çubuk Grafik:** Hafta bazında üç katmanlı görselleştirme:
  - 🟢 **Planlanan:** Kapasite planından gelen miktar.
  - 🔵 **Açık İş Emri:** Mevcut iş emirlerinin karşıladığı miktar.
  - 🔴 **Yeni İhtiyaç:** Ek iş emri gereken miktar.
- **🔴 Toplam Yeni İş Emri İhtiyacı:** Tüm haftalar için toplam yeni iş emri adedi.
- **🔵 Planlama Satırı:** Rapordaki toplam satır sayısı.

---

## 6. Bu Raporun Bağlantıları

```
... → Kapasite Planlama → [İş Emri Planlama]
                        → Malzeme İhtiyaç → ...
```

Bu rapor, Kapasite Planlama'nın çıktısını **üretim yürütme aksiyonuna** (iş emri oluşturma) dönüştüren rapordur.
