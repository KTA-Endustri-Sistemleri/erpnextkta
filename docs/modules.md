---
layout: default
title: "Modüller"
---

<main class="container modules-page" markdown="1">

# 🧬 Modüller

Aşağıda **erpnextkta** uygulamasının modül yapısı, her modülün amacı ve sağlayacağı faydalar
detaylı biçimde listelenmiştir. Bu sayfa, geliştirici ve kullanıcı bazlı dokümantasyon için
temel referans niteliğindedir.

<hr class="modules-divider" />

<section class="module-card" markdown="1">

## 🏭 Manufacturing Extensions

ERPNext’in standart üretim akışlarını gerçek atölye senaryolarına uyarlamak için geliştirilmiş
özel fonksiyonlar içerir.

**Öne çıkan özellikler:**

- [KTA Çalışma Kartı Kullanım Kılavuzu](kta_calisma_karti_kilavuzu.html) (Arayüz kullanım detayları) 🚀
- Job Card alt operasyonları (KTA Çalışma Kartı Operasyonları)
- **Dinamik Duruş Yönetimi & Standardizasyonu**: Duruşların merkezi tablodan (`KTA Durus Sebebi`) kategorize edilerek yönetilmesi.
- **KTA Çalışma Kartı Ayarları**: Sistem limitleri, otomatik duruş nedenleri ve yetki bypass kontrollerinin merkezi yönetimi.
- Zaman loglarını ve üretim miktarlarını daha detaylı işleyen yapı
- İş Emri → İş Kartı dönüşümünde gelişmiş validasyonlar ve Real-Time İş Emri Durum & Operasyon Güncellemesi

**Dosya yapısı (örnek):**

<div class="folder-tree">

  <div class="folder-tree__item folder">
    <span class="folder-tree__icon">📁</span>
    <span class="folder-tree__label">kta_calisma_karti/</span>
  </div>

  <div class="folder-tree__children">

    <div class="folder-tree__item folder">
      <span class="folder-tree__icon">📁</span>
      <span class="folder-tree__label">doctype/</span>
    </div>

    <div class="folder-tree__children">
      <div class="folder-tree__item folder">
        <span class="folder-tree__icon">📁</span>
        <span class="folder-tree__label">calisma_karti/</span>
      </div>
      <div class="folder-tree__item folder">
        <span class="folder-tree__icon">📁</span>
        <span class="folder-tree__label">kta_calisma_karti_operasyonlari/</span>
      </div>
      <div class="folder-tree__item folder">
        <span class="folder-tree__icon">📁</span>
        <span class="folder-tree__label">kta_calisma_karti_settings/</span>
      </div>
    </div>

    <div class="folder-tree__item file">
      <span class="folder-tree__icon">📄</span>
      <span class="folder-tree__label">api.py (Dış Facade)</span>
    </div>

    <div class="folder-tree__item folder">
      <span class="folder-tree__icon">📁</span>
      <span class="folder-tree__label">api_impl/</span>
    </div>

  </div>

</div>

</section>

<section class="module-card" markdown="1">

## ⚡ KTA Shopfloor (CO11N Üretim Teyit Motoru)

SAP CO11N yaklaşımıyla tasarlanmış bağımsız üretim teyit ve stok tüketim modülüdür. Atölye süre kayıtlarını tutan `kta_calisma_karti` modülünü zorlamadan yetkili onaylı orantısal hammadde sarfiyatı (261 Backflush) ve mamul girişi (101 GR) gerçekleştirir.

**Öne çıkan özellikler:**

- [Shopfloor Hub (CO11N) Üretim Teyit Kılavuzu](kta_shopfloor_hub_kilavuzu.html) ⚡
- **Çoklu Görünüm Üretim Kokpiti (Vue 3 SPA):** `Work Orders` (iş emri açma/uygunluk matrisi/serbest bırakma), `Operations` (hızlı barkodlu teyit), `Work Cards` (alt operasyon analitiği) ve `Line Transfers` (hatlar arası `150x ↔ 150x` LIFO stok aktarımı).
- **Orantısal Hammadde Sarfiyatı (261 Backflush):** Ara operasyonlarda yalnızca operasyona bağlı hammaddelerin BOM oranına göre sarf edilmesi.
- **Mamul Girişi (101 GR) & WIP Rollup:** Son operasyonda ara operasyon maliyetlerini mamule yansıtarak mamul ambarına devir alma.
- **Son Teyit (Kalanı Kapat):** Fire veya eksik üretimde kalan reçete bakiyesini küsurat yuvarlamasız kapatma ve Job Card / Work Order tamamlama.
- **SAP CORS Yetkili İptali:** Hatalı teyitlerin yetkili kullanıcılarca iptal edilmesi ve bağlı `Stock Entry` fişlerinin otomatik ters kaydı (`cancel`).

**Dosya yapısı (örnek):**

- `kta_shopfloor/`
  - `doctype/kta_production_confirmation/` (Submittable Teyit Dokümanı)
  - `services/`
    - `confirmation_service.py` (Teyit Koordinatörü)
    - `backflush_service.py` (Reçete Sarfiyat & Mamul Girişi)
    - `reversal_service.py` (CORS İptal ve Ters Kayıt)
    - `line_transfer_service.py` (Hatlar Arası LIFO Transfer & Rezerve Koruması)
    - `work_order_service.py` & `reservation_deficit_service.py`
  - `page/shopfloor_hub/` & `page/line_replenishment_hub/` (Desk Sayfaları)
  - `api.py` (Whitelisted API Facade)
- `public/shopfloor-hub/` & `public/line-replenishment-hub/` (Vue 3 SPA Arayüzleri)

</section>

<section class="module-card" markdown="1">

## 📦 KTA Stock & Logistics

KTA’nın depo, etiketleme ve lojistik modeli için geliştirilmiş kritik kısıtlama ve otomasyon modülüdür.

**Öne çıkan özellikler:**

- [KTA Stok ve Lojistik Kılavuzu](kta_stok_lojistik_kilavuzu.html) (Depo süreçleri, Etiketleme ve Karantina detayları) 📦
- [Hat İkmal Kılavuzu](developer_guides/line_replenishment_guide.html) (Line Replenishment) 🚛
- **Hat İkmal Sistemi (Line Replenishment):** Proaktif rezervasyon açığı tarama, yalnızca `110 HAMMADDE` yaprak raflarından tam koli/makara FIFO parti tahsisi ve mobil PDA ile barkodlu atomik transfer fişi üretimi (`150x ↔ 150x` hatlar arası transferler ise `Shopfloor Hub → Hatlar Arası Transfer` sekmesinden yürütülür).
- **Akıllı Parti Bölme (Smart Batch Splitting):** Mal kabul ve depo içi işlemlerde (Repack/Manufacture) ürünleri paket miktarlarına göre anında böler ve Zebra yazıcılardan otomatik SUT etiketleri basar.
- **GKK Transfer Kısıtı (Güvenlik Duvarı):** Kalite onayı almamış (GKK Bekleyen) partilerin `Stock Entry` ve `Delivery Note` ile transferini kesin bir dille engeller.
- **Negatif Stok Kontrolü:** KTA'nın üretim modeline uygun olarak negatif stok girişlerine kontrollü izin verir ve standart ERPNext stok kurallarını genişletir.

**Dosya yapısı (örnek):**

- `kta_stock/`
  - `label_manager.py` (Etiketleme Motoru)
  - `batch_manager.py` (Parti Bölme Lojiği)
  - `quality_inspection_validator.py` (GKK Güvenlik Duvarı)
- `overrides/`
  - `KTAPurchaseReceipt.py`
  - `KTAStockEntry.py`

</section>

<section class="module-card" markdown="1">

## 🔍 QR Scanner Integration

KTA QR tarama sistemi (qr_scanner app & mobil uygulama) ile ERPNext arasında köprü görevi görür.

**Özellikler:**

- İş Kartı’nı QR ile doğrulama
- Duplicate detection
- Job Card → QR scanner workflow uyarlamaları
- Gerekirse ek API endpoint’leri

**Dosya yapısı (örnek):**

- `qr_integration/`
  - `doctype/qr_settings/`
  - `utils/qr_flow.py`

> İleride QR Scanner mobil/web dokümantasyonuna dış bağlantı da buradan verilebilir.

</section>

<section class="module-card" markdown="1">

## 📊 Reports & Dashboards

ERPNext’in üretim ekranlarını daha anlamlı hale getiren özel raporlar ve gösterge panelleri.

**Örnekler:**

- Operatör Performans Raporu
- Günlük Üretim Hızı

**Dosya yapısı (örnek):**

- `reports/`
- `dashboard/`

</section>

<section class="module-card" markdown="1">

## 🔍 KTA Quality Control

Üretim sahasındaki kritik kalite kontrol noktalarını (Krimp, Test Masası vb.) dijitalleştiren ve Poke-Yoke sistemlerini yöneten modüldür.

**Öne çıkan özellikler:**

- [KTA Kalite Yönetimi Kılavuzu](kta_kalite_kilavuzu.html) (Test ve Krimp detayları) 📏
- **Krimp Teknik Kütüphanesi**: 1500+ kayıtlık üretici referans veri seti (KTA Krimp Book).
- **Test Masası Doğrulama**: 17 maddelik otomatik Poke-Yoke ve Pin kontrol listesi.
- **Dinamik Krimp Parametreleri**: Terminal bazlı otomatik kısıtlamalar ve ölçüm limitleri.
- **Cross-Module Sync**: Test sonuçlarının anlık olarak `Calisma Karti`'na işlenmesi.

**Dosya yapısı (örnek):**

- `kta_quality/`
  - `doctype/test_masasi_dogrulama_kaydi/`
  - `doctype/kta_krimp_book/`
  - `doctype/kta_krimp_yukseklik_parametreleri/`

</section>

<section class="module-card" markdown="1">

## 📈 KTA MRP (Material Requirements Planning)

Satış ve üretim verilerini entegre ederek ileriye dönük periyodik öngörüler ve raporlamalar sunan veri analiz modüldür.

**Öne çıkan özellikler:**

- [Periyodik Satış Siparişleri Raporu Kılavuzu](periodic_sales_orders.html) (Müşteri ve ürün bazlı finansal/miktarsal öngörüler) 📈
- Dinamik kur çevrimi (Cross-rate) ve Çoklu Döviz (Multi-Currency) desteği.
- Açık siparişlerde akıllı fiyat (EUR) algılama algoritması.
- Frappe standartlarının ötesinde, modern ve Premium arayüzlere (Rich Aesthetics) sahip özet gösterge panelleri.

**Dosya yapısı (örnek):**

- `kta_mrp/`
  - `report/periodic_sales_orders/`
    - `periodic_sales_orders.py` (Ana Veri Motoru)
    - `periodic_sales_orders.js` (Arayüz ve Filtre Yönetimi)

</section>

</main>
