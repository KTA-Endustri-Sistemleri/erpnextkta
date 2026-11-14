---
layout: default
title: "Kapasite Planlama Raporu (Capacity Planning Report)"
---

# ⚙️ Kapasite Planlama Raporu (Capacity Planning Report) Kullanım Kılavuzu

Bu rapor, **Üretime Başlama Haftası** raporundan gelen haftalık talep verilerini alarak, her ürün grubunun tanımlı haftalık üretim kapasitesine göre **üretimi haftalara dengeli bir şekilde dağıtır.** Bir hafta kapasiteyi aşan talep, sonraki haftalara taşınır veya önceki haftalardan çekilir.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Her ürün için **hangi hafta kaç adet üretileceğini**, kapasite sınırlarına uygun şekilde görürsünüz.
- Haftalık kapasite kullanım oranını renk kodlarıyla anlık değerlendirirsiniz (yeşil → normal, koyu yeşil → dolu, koyu gri → aşım).
- Geçmiş haftalardan devretmiş (backlog) üretim yükünü görürsünüz.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor, arka planda **Üretime Başlama Haftası (Production Start Week)** raporunu `group_by_item_only = 1` modunda çalıştırır. Sonuç olarak her ürünün hangi hafta kaç adet üretilmesi gerektiğini bilir.

### 🏭 Kapasite Tanımı
Her ürünün `Item` kaydındaki `custom_weekly_production` alanı, o ürünün haftalık üretim kapasitesini belirtir. Aynı ürün grubundaki en yüksek kapasite değeri, grubun haftalık üst limiti olarak kullanılır.

### 🔄 Dengeleme Algoritması (Kapasite Sınırlı İleri Planlama)
`Kapasite Dengeleme Yapılsın mı?` filtresi açık olduğunda:

1. **Backlog (Geçmiş Yük):** Geçmiş haftalardan kalan teslim edilememiş siparişler toplanır.
2. **Her hafta için sırasıyla:**
   - Önce backlog'daki birikmiş yük, o haftanın kapasitesiyle oranlanarak üretilir.
   - Kalan kapasite varsa, o haftanın kendi cari talebine geçilir.
   - Karşılanamayan talep otomatik olarak sonraki haftaya devredilir.
3. Dengeleme kapatılırsa, backlog sadece ilk haftaya eklenir ve kapasite aşımları olduğu gibi gösterilir.

### 🚀 Ramp-up (Önden Üretim) Algoritması
`Ramp-up Yapılsın mı?` filtresi açık olduğunda:
- Bir sonraki haftanın yükü, bir önceki haftanın yüküne göre çok yüksekse, fark önceki haftaya çekilir.
- Artış hızı `Ramp-up Süresi` parametresine göre hesaplanır (örn: 3 hafta = kapasitenin 1/3'ü kadar artış).
- Bu, üretim hattının ani talep artışlarına hazırlanmasını sağlar.

---

### ⚡ Çok Aşamalı Dengeleme Sayısal Senaryosu (Multi-Pass)

Haftalık kapasitesi **1.000 Adet** olan bir ürün grubu için motorun 3 aşamalı yük dağıtım akışı:

### 📊 Sayısal Senaryo: Haftalık Tavan Kapasite = 1.000 Adet

| Hafta | Ham Talep | Pass 1 (Forward) | Pass 2 (Backward Fill) | Pass 3 (Ramp-up) | Sonuç Durumu |
|:------|:---------:|:----------------:|:---------------------:|:----------------:|:-------------|
| **2026-W45 (Geçmiş)** | 400 ad. | 0 ad. | 0 ad. | 0 ad. | `Backlog W46'ya Aktarıldı` |
| **2026-W46 (1. Hafta)** | 1.200 ad. | **1.000 ad.** (Dolu) | **1.000 ad.** (Dolu) | **1.000 ad.** (Dolu) | `Kapasite Tam Dolu (%100)` |
| **2026-W47 (2. Hafta)** | 300 ad. | 900 ad. (Taşan+Talep) | 800 ad. | **850 ad.** (Yumuşatıldı) | `Akıllı Yumuşatma` |
| **2026-W48 (3. Hafta)** | 200 ad. | 200 ad. | 300 ad. (Öne çekildi) | **250 ad.** | `Dengeli Üretim Eğrisi` |
| **TOPLAM** | **2.100 ad.** | **2.100 ad.** | **2.100 ad.** | **2.100 ad.** | `✓ %100 Karşılandı (0 Kayıp)` |

#### Adımların Çalışma Mantığı:
1. **Pass 1 — İleriye Taşırma (Forward Scheduling):**
   W45'ten devreden 400 adetlik geçmiş gecikme (backlog) ve W46'nın 1.200 adetlik talebi (toplam 1.600 ad.) W46'ya yüklenir. Kapasite tavanı 1.000 olduğu için taşan **600 adet W47'ye ötelenir**. W47 toplam yükü: 300 kendi talebi + 600 devir = 900 ad. üretilir (kapasite içi).
2. **Pass 2 — Geriye Doldurma (Backward Fill):**
   Sondan geriye doğru taranır; W47'deki yükün bir kısmı daha dengeli bir üretim eğrisi için önceki/sonraki haftaların boş kapasitesine yayılır.
3. **Pass 3 — Ramp-up (Akıllı Yumuşatma):**
   Ani talep sıçramaları pürüzsüzleştirilir. Üretim toplamı (2.100 adet) hiçbir aşamada 1 adet bile kaybolmaz.

> **⚙️ Merkezi Yönetim:** Kapasite dengeleme ve ramp-up parametreleri artık rapor filtrelerinde değil, merkezi **KTA MRP Settings** ekranında yapılandırılmaktadır.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Sistem tarafından otomatik olarak **bulunulan haftanın Pazartesi gününe** kilitlenir. Geçmiş tarih seçimi engellenmiştir. | Bu Haftanın Pazartesi Günü |
| **Bitiş Tarihi (Planlama Ufku)** | Planlama periyodunun bitişi. Varsayılan `KTA MRP Settings` (90 gün) ayarından gelir, 1 yıla kadar genişletilebilir. | Bugün + 90 gün |
| **Müşteri Grubu** | Belirli bir KTA müşteri grubuna filtreleme | (Hepsi) |
| **Ürün Grubu** | Belirli bir ürün grubuna filtreleme | (Hepsi) |

---

## 4. Tablo Kolonları

| Kolon | Açıklama |
|-------|----------|
| **Ürün Grubu** | Ürünün ait olduğu Item Group |
| **Ürün** | Bitmiş ürün kodu |
| **Haftalık Kapasite** | O ürün grubunun maksimum haftalık üretim miktarı |
| **Haftalık Sütunlar** (Örn: 2026-W35) | O hafta planlanmış üretim miktarı |
| **Toplam** | Tüm haftalar boyunca planlanmış toplam üretim |

---

## 5. Renk Kodlaması

Her hücre, o haftadaki üretim miktarının kapasiteye oranına göre renklendirilir:

| Renk | Anlam |
|------|-------|
| **Açık Yeşil** | Kapasite kullanımı düşük |
| **Koyu Yeşil** | Kapasite kullanımı yüksek ama sınır içinde |
| **Koyu Gri (#4B4B4B)** | ⚠️ Kapasite aşımı! |

---

## 6. Grafik ve Özet Kartları

- **📈 Çizgi Grafik:** Hafta bazında toplam planlanan üretim miktarını gösterir.
- **🟢 Toplam Planlanan:** Tüm zaman aralığındaki planlanan üretim toplamı.
- **🔵 Ürün Sayısı:** Rapordaki benzersiz ürün kalemi sayısı.

---

## 7. Bu Raporun Bağlantıları

```
Periyodik Satış Siparişleri → Üretime Başlama Haftası → [Kapasite Planlama] → Malzeme İhtiyaç
```

- **Girdi:** Üretime Başlama Haftası raporundan haftalık üretim ihtiyaçları.
- **Çıktı:** Kapasite dengelenmiş haftalık üretim planı → Malzeme İhtiyaç raporuna aktarılır.
