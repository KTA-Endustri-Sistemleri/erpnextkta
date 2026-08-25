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

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Planlama periyodunun başlangıcı (geçmiş tarih seçilemez) | Bugün (haftanın Pazartesi'si) |
| **Bitiş Tarihi** | Planlama periyodunun bitişi (min 90 gün) | Bugünden 3 ay sonra |
| **Kapasite Dengeleme Yapılsın mı?** | Açıkken kapasite sınırlı dengeleme algoritmasını aktif eder | Açık |
| **Ramp-up (Önden Üretim) Yapılsın mı?** | Gelecek haftaların yükünü önceki haftalara yayar | Kapalı |
| **Ramp-up Süresi (Hafta)** | Ramp-up aktifken artış hızını belirler | 3 |
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
