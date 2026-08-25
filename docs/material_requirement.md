---
layout: default
title: "Malzeme İhtiyaç Raporu (Material Requirement)"
---

# 🧱 Malzeme İhtiyaç Raporu (Material Requirement) Kullanım Kılavuzu

Bu rapor, **Kapasite Planlama** raporundan gelen haftalık üretim planını, ürünlerin Reçetesindeki (BOM - Bill of Materials) hammadde listesiyle çarparak **"Hangi hafta, hangi hammaddeden ne kadar tüketilecek?"** sorusunu cevaplar. İsteğe bağlı olarak mevcut stoklar ve açık satın alma siparişleri (PO) düşülebilir.

---

## 1. Raporun Temel Amacı

Bu ekran sayesinde:
- Her hammaddenin haftalık brüt tüketim miktarını görürsünüz.
- Stok ve PO teslimatlarını düşerek **net hammadde ihtiyacını** hafta bazında hesaplarsınız.
- Bitmiş ürün + hammadde kırılımı veya sadece hammadde bazında gruplama yapabilirsiniz.

---

## 2. Veri Kaynağı ve Hesaplama Mantığı

### 📦 Veri Kaynağı
Rapor, arka planda **Kapasite Planlama Raporu**'nu çalıştırarak haftalık planlanmış bitmiş ürün miktarlarını alır.

### 🧮 Hammadde İhtiyaç Hesaplaması
Her bitmiş ürün için:
1. Ürünün aktif ve varsayılan BOM'u bulunur.
2. BOM'un **Explosion Items** (patlatılmış malzeme listesi) tablosu okunur — bu, alt-BOM'ları da içeren en uç hammaddelere kadar iner.
3. Her hafta için: `Hammadde Miktarı = BOM'daki stock_qty × Planlanan Üretim Adedi`

### 📉 Aşamalar (Stok ve PO Düşme)

Rapor, seçilen **Aşama** filtresine göre üç farklı hesaplama yapar:

#### Aşama 1: Temel Hammadde İhtiyacı
Sadece brüt ihtiyaç hesaplanır. Stok ve PO dikkate alınmaz.

#### Aşama 2: Stokları Düş
- Her hammadde için `Kullanılabilir Stok` tipindeki depolardaki mevcut stok miktarı alınır.
- Stok, haftalara kronolojik sırayla dağıtılır. Stokun yettiği haftaların ihtiyacı sıfırlanır.
- Stok tükendiğinde kalan haftaların ihtiyacı aynen kalır.

#### Aşama 3: PO Teslimatlarını Düş
- Stok düşmeye ek olarak, açık Satın Alma Siparişlerindeki (Purchase Order) teslim alınmamış miktarlar da haftalara dağıtılır.
- PO'ların `schedule_date` (planlı teslim tarihi) baz alınır.
- Geçmiş tarihli PO'lar, raporun başlangıç haftasına eklenir.
- Her haftada: Stok + PO Teslimatı bakiyesinden talep düşülür. Bakiye yeterliyse ihtiyaç sıfırlanır.
- **MOQ ve Paketleme Yuvarlaması:** Net ihtiyaç varsa, `Item Price` üzerindeki MOQ (Minimum Sipariş Miktarı) ve paketleme miktarının katına yuvarlanır.
- Tüm haftalar bittikten sonra kalan bakiye "Fazla PO Miktarı" olarak gösterilir.

---

## 3. Filtreler

| Filtre | Açıklama | Varsayılan |
|--------|----------|------------|
| **Başlangıç Tarihi** | Planlama periyodunun başlangıcı | Bugün |
| **Bitiş Tarihi** | Planlama periyodunun bitişi | Bugünden 3 ay sonra |
| **Aşama** | Hesaplama derinliği (Brüt / Stok Düş / Stok+PO Düş) | 1 - Temel Hammadde İhtiyacı |
| **Gruplama Şekli** | "Bitmiş Ürün + Hammadde" veya "Sadece Hammadde" | Bitmiş Ürün + Hammadde |

---

## 4. Tablo Kolonları

### "Bitmiş Ürün + Hammadde" Gruplama Modunda

| Kolon | Açıklama |
|-------|----------|
| **Ürün** | Bitmiş ürün kodu (BOM'un sahibi) |
| **Müşteri Grubu** | Bitmiş ürünün tanımlı müşteri grubu |
| **BOM** | Kullanılan Reçete (Bill of Materials) |
| **Hammadde** | Hammadde kodu |
| **Ürün Açıklaması** | Hammaddenin adı |
| **Birim** | Stok birimi (Metre, Kg, Adet vb.) |
| **Varsayılan Tedarikçi** | Hammaddenin varsayılan tedarikçisi |
| **Haftalık Sütunlar** (Örn: 2026-W35) | O hafta tüketilecek hammadde miktarı |
| **Satır Toplamı** | (Stok/PO düşülmüş) net ihtiyaç toplamı |
| **Toplam İhtiyaç** | Brüt toplam ihtiyaç |

### "Sadece Hammadde" Gruplama Modunda
Bitmiş ürün kırılımı gösterilmez; aynı hammadde tüm ürünler üzerinden toplanarak tek satırda gösterilir.

### Stok/PO Düşme Aktifken Ek Kolonlar

| Kolon | Açıklama |
|-------|----------|
| **Stok** | Mevcut depo stok miktarı |
| **PO Teslimat** | Açık PO'lardan gelecek toplam miktar |
| **Net İhtiyaç** | Stok ve PO düşüldükten sonraki net ihtiyaç |
| **Fazla PO Miktarı** | Tüm haftalar karşılandıktan sonra kalan PO fazlası |

---

## 5. Özet Kartları

- **🔵 Toplam Brüt İhtiyaç:** Stok ve PO düşülmeden önceki toplam hammadde ihtiyacı.
- **🔴 Toplam Net İhtiyaç:** Stok ve PO düşüldükten sonraki gerçek ihtiyaç.

---

## 6. Bu Raporun Bağlantıları

```
Periyodik Satış Siparişleri → Üretime Başlama Haftası → Kapasite Planlama → [Malzeme İhtiyaç] → MRP Analiz / Önerilen PO
```

- **Girdi:** Kapasite Planlama raporundan kapasite dengelenmiş haftalık üretim planı.
- **Çıktı (1):** MRP Analiz raporu bu veriyi müşteri grubu kırılımıyla sunar.
- **Çıktı (2):** Önerilen Satın Alma Siparişleri raporu bu veriyi tedarik planlamasına dönüştürür.
