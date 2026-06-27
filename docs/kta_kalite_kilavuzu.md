---
layout: default
title: "KTA Kalite Yönetimi (Krimp & Test Masası) Kılavuzu"
---

<main class="container" markdown="1">

# 🔍 KTA Kalite Yönetimi Kılavuzu

**KTA Kalite Modülü**, üretim sahasındaki en kritik operasyonlardan olan **Krimp (Kontak Basma)** ve **Test Masası** süreçlerinde hata payını sıfıra indirmek (Poke-Yoke) ve standartlara tam uyumu sağlamak için geliştirilmiştir.

## 📥 Veri Aktarımı (Krimp Book Setup)

Krimp Book kütüphanesinin (1500+ kayıt) sistem performansını etkilememesi ve `bench migrate` sırasında zaman aşımı (timeout) oluşturmaması için manuel aktarılması önerilir.

Yeni bir kurulumda şu komutu terminalden çalıştırınız:

```bash
bench --site [site-adı] execute erpnextkta.kta_quality.scripts.import_krimp_data.execute
```

---

## 📚 1. Krimp Teknik Kütüphanesi (Krimp Book)

Krimp operasyonlarında kullanılan terminal, kablo ve kalıp (`Amboss`) eşleşmeleri için devasa bir referans ansiklopedisidir.

- **Kapsam:** Sistemde 1500+ adet onaylı üretici standardı (Tyco, Molex, Delphi vb.) yüklüdür.
- **İçerik:** Her kayıt; kablo kesiti, terminal part no, krimp yüksekliği/genişliği ve ilgili kalıp ismini barındırır.
- **Kullanım Amacı:** Operatör ve kalite teknisyenlerinin, hangi terminalin hangi ölçülerle basılması gerektiğini manuel aramadan, sistem üzerinden doğrulamasını sağlar.

---

## 📏 2. Krimp Yükseklik Parametreleri ve Ölçüm Doğrulama

Krimp Book'taki "Ansiklopedi" verisinin, sahada uygulanan "Onaylı Parametre" katmanına dönüştürülmüş halidir.

### Temel İşleyiş ve Cascade Seçim Aşamaları:
1. **Dinamik Kısıt ve Cascade Seçim**: Operatör veri girişi yaparken *Kesit Seçimi* -> *Kablo Seçimi* (kesite ait BOM kalıpları) -> *Kontak Seçimi* -> *Makine Seçimi (Asset)* şeklinde adım adım daralan bağımlı bir seçim akışı (Cascade Selection) izler. Bu sayede hatalı eşleşmeler daha giriş aşamasında elenir.
2. **Otomatik Tolerans Algılama**: Seçilen üçlüye (Kablo + Kontak + Kesit) göre `KTA Krimp Book` veritabanından minimum/maksimum tolerans limitleri otomatik olarak çekilir.
3. **Canlı Gösterge (MeasureGauge)**: Arayüzde ölçüm değerleri girildiğinde ±10 mm segment göstergesi canlı olarak çalışır. Girilen değer hedefe göre *Kısa*, *Uzun* veya *OK* olarak anlık işaretlenir. Limitlerin aşılması durumunda ekran "LIMIT AŞILDI" uyarısı verir.
4. **Veri Koparma (Decoupling)**: Onaylı bir parametre oluşturulduğunda, veriler Krimp Book'tan kopyalanır ve dondurulur. Böylece ana kütüphane değişse bile üretimdeki "Onaylı Formül" sabit kalır.

---

## 🏗️ 3. Test Masası Doğrulama Kaydı (Poke-Yoke)

Harness/Kablo gruplama (Board) işlemlerine başlamadan önce makine ve test donanımının doğruluğunu garanti altına alan kontrol sistemidir.

### 🛡️ Poke-Yoke Kontrol Listesi (17 Madde)
Her yeni doğrulama kaydında, sistem otomatik olarak **17 maddelik standart bir kontrol listesi** oluşturur:
- "Test programı doğru mu?"
- "Board üzerindeki klipsler çalışıyor mu?"
- "Etiket yazıcısı bağlı mı?" gibi kritik soruların cevaplanması zorunludur.

### 🔗 Bağlantı Noktası Kontrolü
Board üzerindeki fiziksel bağlantı noktalarının (Connector pinleri vb.) tek tek doğrulanması için özel bir tablo sunar.

### 🔄 Çalışma Kartı (Work Card) Senkronizasyonu
- **Otomatik Linkage:** Bir doğrulama kaydı oluşturulduğunda ve `Çalışma Kartı` referansı girildiğinde, sistem bu sonucu anlık olarak ilgili üretim kartına işler.
- **Bypass Engeli:** Test masası doğrulaması yapılmayan işlerde, ileri aşamalara geçiş kısıtlanabilir (Sıkı Mod).

---

## ⚙️ 4. Kalite Ayarları (Yöneticiler İçin)

`KTA Quality Settings` üzerinden şu konfigürasyonlar yapılabilir:
1. **İzin Verilen Terminal Grupları:** Krimp Parametreleri tablosunda hangi Item Group'ların (Örn: 110-Connector, 150-Terminals) seçilebileceği belirlenir.
2. **Kriter Yönetimi:** Test masası doğrulamasındaki sabit kriterlerin (PTR form referansları) varsayılan değerleri izlenir.

---

## 📈 5. Raporlama ve İzlenebilirlik

Sistem, kaydedilen tüm krimp ölçümlerini ve test masası doğrulama sonuçlarını geriye dönük olarak saklar. Bu veriler:
- **DÇF (Düzeltici Önleyici Faaliyet)** gerektiren durumların tespiti,
- Müşteri şikayetlerinde üretilen partinin kalite verilerine ulaşılması,
- Operatör bazlı ölçüm hassasiyeti analizleri için kullanılır.

---

## 🔍 6. Giriş Kalite Kontrol (GKK) ve Karantina Süreci

Dışarıdan (tedarikçilerden) gelen hammaddelerin kalite onayı almadan üretime veya satışa çıkışını engelleyen entegre karantina sistemidir.

### Temel İşleyiş:
- **Anında Etiketleme:** Mal Kabul (Purchase Receipt) onaylandığı an ürünler otomatik olarak kutu içi miktarlarına bölünür (`PARTI-0001`, `PARTI-0002` vb.) ve **Zebra SUT etiketleri** yazdırılır. Depo personeli ürünleri etiketleyip rafa kaldırır.
- **Otomatik GKK Belgesi:** Etiketlenen ürünler için sistem arka planda otomatik olarak "Taslak" statüsünde bir Kalite Kontrol belgesi (Quality Inspection) oluşturur.
- **Transfer Kısıtı (Sıfır Tolerans):** Kalite teknisyeni bu belgeyi inceleyip **"Accepted (Kabul)"** durumuna çekene kadar, bu partilerin hiçbir şekilde depodan çıkışına (Stock Entry, Delivery Note vb.) izin verilmez. Sistem `frappe.throw` ile kesin bir güvenlik duvarı oluşturur.

</main>
