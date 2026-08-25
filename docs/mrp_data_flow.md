---
layout: default
title: "MRP Veri Akışı (Genel Bakış)"
---

# 🔗 MRP Veri Akışı — Tüm Raporların Genel Bakışı

Bu belge, KTA MRP modülündeki tüm raporların birbirine nasıl bağlandığını, veri akışının nereden başlayıp nereye ulaştığını ve her raporun hangi soruyu cevapladığını tek bir sayfada açıklar.

---

## 1. Büyük Resim: Veri Akış Şeması

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SATIŞTAN ÜRETİME VERİ AKIŞI                     │
│                                                                         │
│  ┌──────────────────────┐                                               │
│  │  📈 Periyodik Satış  │  Açık satış siparişlerini haftalara dağıtır   │
│  │     Siparişleri      │                                               │
│  └──────────┬───────────┘                                               │
│             │                                                           │
│             ▼                                                           │
│  ┌──────────────────────┐                                               │
│  │  🏭 Üretime Başlama  │  Teslimat → Sevk − Üretim süreleriyle        │
│  │      Haftası         │  üretime başlama tarihini hesaplar            │
│  └──────────┬───────────┘  + Bitmiş ürün stokunu düşer                 │
│             │                                                           │
│             ▼                                                           │
│  ┌──────────────────────┐                                               │
│  │  ⚙️ Kapasite         │  Haftalık üretim kapasitesiyle               │
│  │     Planlama         │  dengeleme yapar                              │
│  └──────┬────────┬──────┘                                               │
│         │        │                                                      │
│    ┌────▼────┐   │                                                      │
│    │📋 İş   │   │                                                      │
│    │ Emri    │   │  Mevcut iş emirlerini planla                         │
│    │Planlama │   │  karşılaştırır                                       │
│    └─────────┘   │                                                      │
│                  ▼                                                      │
│  ┌──────────────────────┐                                               │
│  │  🧱 Malzeme İhtiyaç  │  BOM patlatarak hammadde                     │
│  │     Raporu           │  ihtiyacını hesaplar                          │
│  └──────┬────────┬──────┘                                               │
│         │        │                                                      │
│    ┌────▼────┐   └──────────┐                                           │
│    │📊 MRP  │         ┌────▼─────┐                                     │
│    │ Analiz  │         │🛒 Önerilen│                                    │
│    │         │         │   PO      │                                     │
│    └─────────┘         └──────────┘                                     │
│                                                                         │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│  BAĞIMSIZ RAPORLAR (Aynı veri kaynaklarını kullanır ama zincirsiz):     │
│                                                                         │
│  ┌──────────────────────┐    ┌──────────────────────┐                   │
│  │  🚚 Sevkiyat Haftası │    │  🔬 Üretim Pipeline  │                   │
│  │  (Lojistik bakışı)   │    │     Analizi           │                   │
│  └──────────────────────┘    └──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Rapor Zincirleme Tablosu

Aşağıdaki tablo, her raporun hangi raporu çağırdığını ve hangi soruyu cevapladığını özetler:

| # | Rapor | Beslediği Kaynak | Cevapladığı Soru |
|---|-------|-----------------|------------------|
| 1 | **Periyodik Satış Siparişleri** | Doğrudan `Sales Order` tablosu | "Hangi müşteriye, ne zaman, ne kadar teslim edeceğiz?" |
| 2 | **Üretime Başlama Haftası** | Rapor #1 + KTA Sevk Parametreleri + Bitmiş Ürün Stoku | "Bu ürünün üretimine en geç hangi hafta başlamalıyız?" |
| 3 | **Kapasite Planlama** | Rapor #2 + Item.custom_weekly_production | "Fabrika kapasitesine göre haftalık üretim planı nasıl olmalı?" |
| 4 | **Malzeme İhtiyaç** | Rapor #3 + BOM Explosion Items + Stok + PO | "Hangi hafta, hangi hammaddeden ne kadar lazım?" |
| 5 | **MRP Analiz** | Rapor #4 + Item bilgileri + Fiyat + Stok | "Hammadde portföyümüzün genel durumu nedir?" |
| 6 | **Önerilen PO** | Rapor #4 + Item Price (lead time, MOQ, paket) | "Tedarikçiye hangi hafta, ne kadar sipariş vermeliyiz?" |
| 7 | **İş Emri Planlama** | Rapor #3 + Mevcut Work Order'lar | "Hangi hafta için yeni iş emri açmalıyız?" |
| 8 | **Sevkiyat Haftası** | Rapor #1 + KTA Sevk Parametreleri | "Ürün fabrikadan hangi hafta çıkmalı?" |
| 9 | **Üretim Pipeline Analizi** | Doğrudan SO + WO + Stok + Sevk Param. | "Tüm pipeline'ı aşama aşama nasıl görürüm?" |

---

## 3. Ortak Veri Kaynakları

Tüm raporların beslediği ortak DocType'lar ve alanlar:

| DocType | Alan | Kullanım |
|---------|------|----------|
| **Sales Order / Sales Order Item** | `qty`, `delivered_qty`, `delivery_date` | Açık sipariş talebi |
| **KTA Sevk Parametreleri** | `production_time`, `delivery_time` | Müşteriye özel üretim ve sevk süreleri |
| **Item** | `custom_weekly_production`, `custom_ara_malzeme_grubu`, `custom_musteri_grubu` | Kapasite, gruplama |
| **Item Customer** | `custom_musteri_paketleme_miktari` | Müşteriye özel paketleme yuvarlaması |
| **BOM / BOM Explosion Item** | `stock_qty`, `stock_uom` | Hammadde çarpanları |
| **Bin** | `actual_qty`, `stock_value` | Mevcut stok |
| **Warehouse** | `warehouse_type = 'Kullanılabilir Stok'` | Stok hesaplama filtresi |
| **Item Default** | `default_supplier` | Varsayılan tedarikçi |
| **Item Price** | `price_list_rate`, `lead_time_days`, `custom_minimum_order_quantity`, `custom_minimum_paketleme_miktari` | Fiyat, temin süresi, MOQ |
| **Purchase Order Item** | `qty`, `received_qty`, `schedule_date` | Açık PO teslimatları |
| **Work Order** | `qty`, `produced_qty`, `planned_start_date`, `planned_end_date` | Açık iş emirleri |
| **KTA Customer Group** | `name` | Müşteri grubu kırılımı |

---

## 4. Tipik Kullanım Senaryoları

### Senaryo 1: "Önümüzdeki 3 ayda ne üretmeliyiz?"
→ **Kapasite Planlama** raporunu açın. Dengeleme aktif olduğunda, kapasite sınırlarına göre her hafta ne üretmeniz gerektiğini görürsünüz.

### Senaryo 2: "Hammadde stokumuz yeterli mi?"
→ **MRP Analiz** raporunu "Yıllık" periyotla açın. Her hammaddenin depo stoku ve tahmini tüketimi yan yana görünür. Eksik Kalem sayısı kart üzerinde gösterilir.

### Senaryo 3: "Bu hafta hangi PO'ları vermeliyim?"
→ **Önerilen Satın Alma Siparişleri** raporunu açın. MOQ, paketleme ve temin süresine göre otomatik öneriler oluşur.

### Senaryo 4: "Hangi haftalar için iş emri açmalıyım?"
→ **İş Emri Planlama** raporunu açın. Mevcut iş emirleriyle planlanmış üretim karşılaştırılarak eksik miktarlar gösterilir.

### Senaryo 5: "Sevkiyat takvimim nasıl?"
→ **Sevkiyat Haftası** raporunu açın. Her müşteri için fabrika çıkış haftasını görürsünüz.

### Senaryo 6: "Stok erimini ve üretim dengesini stratejik olarak nasıl izlerim?"
→ **Üretim Pipeline Analizi** raporunu ürün grubuna göre filtreleyin. 8 aşamalı pipeline ve stok evrimi grafiği ile tüm hattı görürsünüz.

---

## 5. Rapor Detay Sayfaları

Her raporun filtreler, kolonlar, hesaplama mantığı ve örnekleriyle dolu detaylı kullanım kılavuzları:

1. [📈 Periyodik Satış Siparişleri](periodic_sales_orders.html)
2. [🏭 Üretime Başlama Haftası](production_start_week.html)
3. [⚙️ Kapasite Planlama](capacity_planning_report.html)
4. [🧱 Malzeme İhtiyaç](material_requirement.html)
5. [📊 MRP Analiz](mrp_analysis.html)
6. [🛒 Önerilen Satın Alma Siparişleri](recommended_purchase_orders.html)
7. [📋 İş Emri Planlama](work_order_planning.html)
8. [🚚 Sevkiyat Haftası](shipment_week.html)
9. [🔬 Üretim Pipeline Analizi](production_pipeline_analysis.html)
