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
    <span class="folder-tree__label">manufacturing_ext/</span>
  </div>

  <div class="folder-tree__children">

    <div class="folder-tree__item folder">
      <span class="folder-tree__icon">📁</span>
      <span class="folder-tree__label">doctype/</span>
    </div>

    <div class="folder-tree__children">
      <div class="folder-tree__item folder">
        <span class="folder-tree__icon">📁</span>
        <span class="folder-tree__label">kta_calisma_karti/</span>
      </div>
      <div class="folder-tree__item folder">
        <span class="folder-tree__icon">📁</span>
        <span class="folder-tree__label">kta_calisma_karti_operasyonlari/</span>
      </div>
    </div>

    <div class="folder-tree__item file">
      <span class="folder-tree__icon">📄</span>
      <span class="folder-tree__label">job_card_hooks.py</span>
    </div>

    <div class="folder-tree__item file">
      <span class="folder-tree__icon">📄</span>
      <span class="folder-tree__label">workflow_logic/</span>
    </div>

  </div>

</div>

</section>

<section class="module-card" markdown="1">

## 📦 Negative Stock Control

KTA’nın üretim modeli için gerekli olan özel “negatif stok izinleri” ve validasyon sistemi.

**Özellikler:**

- Negatif stok girişlerine kontrollü izin
- Çeşitli stok hareketleri için özel validasyonlar
- ERPNext’in varsayılan stok kurallarını genişletme

**Dosya yapısı (örnek):**

- `negative_stock_control/`
  - `allow_negative_stock_validation.py`

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

</main>
