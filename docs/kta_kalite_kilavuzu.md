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

## 📏 2. Krimp Yükseklik Parametreleri

Krimp Book'taki "Ansiklopedi" verisinin, sahada uygulanan "Onaylı Parametre" katmanına dönüştürülmüş halidir.

### Temel İşleyiş:
- **Dinamik Kısıt:** Bir terminal seçildiğinde, `KTA Quality Settings` altındaki tanımlı `Item Group` (Örn: 150-Terminals) filtreleri devreye girerek hatalı parça seçimi engellenir.
- **Veri Koparma (Decoupling):** Onaylı bir parametre oluşturulduğunda, veriler Krimp Book'tan kopyalanır ve dondurulur. Böylece ana kütüphane değişse bile üretimdeki "Onaylı Formül" sabit kalır.
- **Ölçüm Doğrulama:** Bu parametreler, üretimdeki `IDC Ölçüleri` ve standart kalite muayeneleri için temel referans noktası (Master Data) oluşturur.

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

</main>
