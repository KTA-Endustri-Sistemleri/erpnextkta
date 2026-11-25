---
layout: default
title: "KTA Stok ve Lojistik Kılavuzu"
---

<main class="container" markdown="1">

# 📦 KTA Stok ve Lojistik Kılavuzu

**KTA Stok Modülü**, ERPNext'in standart depo hareketlerini akıllı parti bölme (Smart Batch Splitting), Zebra (ZPL) entegrasyonu ve sıfır toleranslı Giriş Kalite Kontrol (GKK) kısıtlamalarıyla güçlendiren özel bir altyapıdır.

Bu kılavuz, depo personelinin ve lojistik yöneticilerinin günlük işlemlerde bu sistemi nasıl kullanması gerektiğini özetler.

---

## 📥 1. Mal Kabul (Purchase Receipt) İşlemleri

Tedarikçilerden gelen hammaddelerin fabrikaya alınması ve sisteme kaydedilmesi sürecidir.

### Lojistik Takip İş Akışı (Workflow)
Sistem, malzemenin fiziksel yolculuğunu takip etmeniz için bir iş akışı sunar. İlgili belge üzerinden şu statüleri seçerek ilerleyebilirsiniz:
1. **Yolda:** Tedarikçi ürünü kargoladı.
2. **Antrepoda:** Ürün gümrükte/antrepoda bekliyor.
3. **Mal Girişe Hazır:** Ürün yola çıktı, fabrikaya geliyor.
4. **Mal Giriş:** Ürün fiziksel olarak deponun kapısına yanaştı.
5. **[Kabul Et (Submit)]:** Depo personeli sayımı yapar ve belgeyi onaylar.

> **Önemli Not:** "Kabul Et" (Submit) butonuna basılana kadar sistem stokları artırmaz ve etiket basmaz.

---

## 🏷️ 2. Akıllı Parti Bölme ve Etiketleme

Sistem, ürünleri büyük bir "Tek Parti" olarak almak yerine fiziksel kutulara/paketlere bölerek yönetmenizi sağlar.

### Nasıl Çalışır?
- **Purchase Receipt (Mal Kabul):** Satır detayında bulunan `custom_split_qty` alanına kutu içi miktarı (Örn: 20) girdiğinizde, sistem 100 adetlik bir alımı otomatik olarak 5 ayrı partiye böler (`PARTI-0001`, `PARTI-0002` vb.).
- **Stock Entry (Repack/Transfer):** Ürün kartındaki (Item Customer Detail) `musteri_paketleme_miktari` baz alınarak ürünler transfer veya üretimden çıkış anında otomatik olarak yeni partilere bölünür.

### Zebra (SUT) Otomasyonu
Belge onaylandığı (Submit) **milisaniye** içinde parçalara ayrılan her bir kutu için Zebra yazıcılardan (ZPL formatında) SUT barkodları otomatik olarak dökülür. Personelin ekstra bir "Etiket Yazdır" tuşuna basmasına gerek yoktur.

---

## 🚫 3. Karantina ve Transfer Güvenlik Duvarı

Ürünlerin depoya girdikten sonra kalite onayı (GKK) almadan **kesinlikle** hareket ettirilmemesini sağlayan sistemdir.

### Kalite Onayı Öncesi Kısıtlamalar
Ürünler mal kabul ile sisteme girip etiketlendiğinde:
1. Sistem arka planda bu partiler için otomatik bir **"Taslak" Kalite Kontrol (Quality Inspection)** belgesi açar.
2. Kalite ekibi bu belgeyi **Accepted (Kabul Edildi)** statüsüne çekene kadar ürünler Karantinadadır.
3. Bir depo personeli, kalite onayı almamış bir barkodu okutarak `Stock Entry` (Depolar Arası Transfer/Üretime Çıkış) veya `Delivery Note` (İrsaliye) ile çıkarmak isterse:
   * **Sistem Anında Bloklar:** *"HATA: PARTI-XXXX numaralı koli henüz Kalite Kontrol (GKK) onayı almadığı için transfer edilemez!"* uyarısı fırlatır.

### Onay Sonrası Süreç
Kalite birimi "Kabul" butonuna bastığı an, sistem ilgili `PARTI` kodları üzerindeki tüm dijital kilitleri otomatik açar. Artık malzemeler serbestçe tüketilebilir ve transfer edilebilir.

---

## 🔄 4. Eksik Barkod Verisi Kurtarma (Fallback)

Taslak aşamasında olan işlemlerinizde (Henüz parti numarası ERPNext tarafından oluşturulmadığında), sistem etiketlerin boş çıkmasını engeller. Kaynak deponuzdaki veya satırdaki mevcut `Batch` bilgilerini "miras" (Fallback) olarak kullanarak, işlem gerçekleşmeden de doğru etiketi basabilmenizi sağlar.

---

## 🖨️ 5. Zebra Etiket Yazdırma Kuyruk Yönetimi (Print Queue)

Zebra etiket basım işlemlerinde sunucu tıkanıklıklarını önlemek ve yazıcıların stabil çalışmasını sağlamak için kuyruk yönetimi (Print Queue) entegre edilmiştir:
- **Asenkron İşleme**: Yazdırma talepleri doğrudan yazıcıya gönderilip beklemek yerine arka planda kuyruğa atılır.
- **Yazıcı İzleme**: Kuyruktaki etiketlerin yazdırılma durumları (Beklemede, Yazdırılıyor, Tamamlandı, Hatalı) kuyruk paneli üzerinden takip edilebilir ve başarısız gönderimler tek tuşla yeniden denenebilir (Retry).

---

## ⚡ 6. Stok Mutabakatı Toplu Veri Optimizasyonu (Bulk Optimization)

Stock Reconciliation (Stok Mutabakatı) işlemlerinde binlerce satırlık veri güncellemelerinin sebep olduğu veritabanı darboğazları ve timeout sorunları için özel optimizasyon geliştirilmiştir:
- **Toplu Sorgu Yükleme (Bulk Loading)**: Satırlar tek tek sorgulanmak yerine bellek üzerinde gruplanarak toplu şekilde veritabanından çekilir. Bu sayede veritabanı gidiş-dönüş (Round-Trip) maliyeti %90 oranında düşürülmüş ve arka plan işlem yükü minimize edilmiştir.

---

## 🔄 7. Otomatik Malzeme Talebi (Re-Order) ve Görev Atama Sistemi

Sistemdeki MRP ve stok seviyesi (Re-Order) kurallarına göre otomatik olarak açılan Üretim (`Manufacture`) tipi Malzeme Taleplerinin hesaplanması, onaylanması ve temizlenmesi için KTA'ya özgü bir iş akışı ve hesaplama kuralı uygulanır:

### Üretim (`Manufacture`) Tipi Otomatik Hesaplama Kuralı
- **Hariç Tutulan Miktarlar ve Depolar:** `Manufacture` tipi otomatik malzeme taleplerinde Satış Siparişi rezervleri (`reserved_qty`) ve red depoları projeksiyon hesabından hariç tutulur.
- **Tetikleme Koşulu ve Talep Miktarı:** Projeksiyon miktarı `reorder_level` değerinin kesin olarak altına (`<`) düştüğünde (eşitlik durumunda talep oluşturulmaz), en az `reorder_qty` olmak üzere oluşan açık miktar (`reorder_level - projected_qty`) kadar üretim talebi açılır.
- **Çekirdek Sürüm Bağımsızlığı:** Bu hesaplama mantığı ERPNext çekirdek sürüm değişikliklerinden bağımsız olarak KTA kuralına göre çalışır; `Purchase`, `Material Transfer` gibi diğer talep tipleri standart kurallarla işlenmeye devam eder.

### Taslak Oluşumu ve Dinamik Görev Aktarımı
- **Otomatik Taslak (Draft) Oluşumu:** Sistem tarafından yaratılan üretim malzeme talepleri otomatik onaylanmak yerine "Taslak" (`Draft`) olarak bırakılır ve ilgili planlama personeline incelemesi için bir **ToDo (Görev)** atanır.
- **Dinamik Görev Aktarımı:** Personel talebi inceleyip "Onayla (Submit)" dediğinde, üzerindeki görev otomatik olarak kapanır ve üretim yöneticilerine "İş Emri Oluşturma" görevi açılır (görevli listesi *Assignment Rule* ekranından yönetilir).
- **Otomatik Kapanış:** Üretim yöneticileri bu talep üzerinden **İş Emri (Work Order)** oluşturup %100 oranında onayladıklarında, üzerlerindeki görev arka planda otomatik olarak "Tamamlandı" statüsüne geçerek kapanır.

### Onaylanmamış Eski Otomatik Taslakların Temizlenmesi
- **Günlük Otomatik Temizlik:** Önceki günlerden onaylanmadan taslakta (`Draft`) kalan otomatik üretim malzeme talepleri ve bunlara bağlı görevler (`ToDo`), bir sonraki günün otomatik hesaplaması çalışırken sistem tarafından otomatik olarak temizlenir.
- **Kapsam Dışı Kayıtlar:** Kullanıcıların manuel olarak açtığı taslaklara veya `Purchase`, `Material Transfer` gibi diğer talep tiplerine dokunulmaz.

</main>
