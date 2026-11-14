---
layout: default
title: "KTA Stok ve Lojistik Kılavuzu"
---

<main class="container" markdown="1">

# 📦 KTA Stok ve Lojistik Kılavuzu

**KTA Stok Modülü**, ERPNext'in standart depo hareketlerini akıllı parti bölme (Smart Batch Splitting), Zebra (ZPL) entegrasyonu ve sıfır toleranslı Giriş Kalite Kontrol (GKK) kısıtlamalarıyla güçlendiren özel bir altyapıdır.

Bu kılavuz, depo personelinin ve lojistik yöneticilerinin günlük işlemlerde bu sistemi nasıl kullanması gerektiğini özetler.

---

## 📥 1. Mal Kabul (Purchase Receipt) İşlemleri ve KTA Mal Giriş Süreci

Tedarikçilerden gelen hammaddelerin fabrikaya alınması, uluslararası lojistik aşamaları, antrepo bekleme havuzu ve gümrük millileştirme süreçlerinin uçtan uca takip edildiği resmi iş akışıdır (Workflow).

### 🗺️ Lojistik ve İthalat İş Akışı (KTA Mal Giriş Süreci)

`Mal Girişe Hazır` ➔ `🚢 Yolda (ETA Zorunlu)` ➔ `🏛️ Antrepoda (Bekleme Havuzu)` ➔ `⚡ Gümrüklemede (+2 Gün)` ➔ `🏭 Mal Giriş` ➔ `✅ Kabul Edildi (GKK)`  
*(Kapıda Ret Durumunda: `Mal Giriş` ➔ `⚠️ Mal Kabul Uyuşmazlığı`)*

| Aşama (State) | Tetikleyici / Buton | Yetkili Rol | Açıklama, Zorunlu Alanlar ve Planlama Etkisi |
| :--- | :--- | :--- | :--- |
| **Mal Girişe Hazır** | İrsaliye Açılışı | Purchase User | Yurtiçi satınalmalar veya tedarikçiye iade irsaliyeleri (`is_return = 1`) için başlangıç aşamasıdır. |
| **Yolda (In Transit)** | `İthalat Başlat` | **KTA Gümrük Sorumlusu** | Yurtdışından sevk edilen malzemeler içindir. Yalnızca Ceren Keçici ve Ömür Muslu tarafından başlatılabilir. **İthalat sekmesindeki `tahmini_varis_tarihi` (ETA) zorunludur.** Ret (`Reject`) halinde `Mal Girişe Hazır`a döner. |
| **Antrepoda** | `Antrepoya Al` | **KTA Gümrük Sorumlusu** | Malzeme gümrük sahasına/antrepoya ulaşmış ve `gumruge_gelis_tarihi` işlenmiştir. Henüz çekim kararı verilmediği için MRP'de takvime yığılmaz, **"Antrepoda Bekliyor"** rezervi olarak izlenir. Ret (`Reject`) halinde `Yolda`ya döner. |
| **Gümrüklemede** | `İşlem Başlat` | **KTA Gümrük Sorumlusu** | Gümrükleme başlatıldığında tetiklenir. `antrepo_clearance_days` (2 gün tampon) eklenerek fabrikaya kesin varış tarihi hesaplanır. Ret (`Reject`) halinde tam bir önceki adım olan `Antrepoda`ya döner. |
| **Mal Giriş** | `Antrepodan Çek` / `İthalatı Gerçekleştir` | **KTA Gümrük Sorumlusu** | İthalat tamamlanmış, kamyon fabrika mal kabul kapısına yanaşmıştır. Depocu fiziki sayım ve kontrolünü yapar. |
| **Mal Kabul Uyuşmazlığı** | `Uyuşmazlık Bildir` | **Stock User** (Depocu) | Sayımda evrak, miktar veya hasar uyuşmazlığı tespit edildiğinde tetiklenir. Açılan diyalogdan **Uyuşmazlık Nedeni** ve **Açıklaması** girilmesi zorunludur. MRP'de arz kesinlikle **0** kabul edilir. |
| **Kabul Edildi (Submit)** | `Onayla (Submit)` | Quality / Stock User | Sayım tamamlanıp onaylandığında stoklar artar, Smart Batch Splitting ile partilenir, Zebra SUT barkodları basılır ve GKK karantinası başlar. |

### 🔒 Görevler Ayrılığı ve Adım Adım Geri Dönüş (Rollback) Zinciri
1. **Gümrük Yetkisi İzolasyonu:** Depo personeli (`Stock User`), `Purchase User` rolüne sahip olsa dahi `Yolda`, `Antrepoda` ve `Gümrüklemede` statülerindeki hiçbir butonu göremez ve tetikleyemez.
2. **Sıralı Geri Dönüş Zinciri:**
   - `Gümrüklemede` Reject ➔ `Antrepoda`
   - `Antrepoda` Reject ➔ `Yolda`
   - `Yolda` Reject ➔ `Mal Girişe Hazır`
3. **Uyuşmazlık Çözümü (`Mal Kabul Uyuşmazlığı`):**
   - **İthalat Belgelerinde (`is_import = 1`):** Yalnızca `KTA Gümrük Sorumlusu` çözebilir (`Sorun Çözüldü` ➔ `Mal Giriş`, `Gümrüğe İade` ➔ `Gümrüklemede` / `Yolda`).
   - **Yurtiçi Belgelerinde (`is_import = 0`):** `Purchase User` çözebilir (`Sorun Çözüldü` ➔ `Mal Giriş`).

> **⚠️ Önemli Not:** "Onayla" (Submit) butonuna basılana kadar sistem stokları artırmaz ve etiket basmaz. Ancak onay öncesindeki tüm aşamalar (Yolda, Antrepoda, Gümrüklemede) MRP Malzeme İhtiyaç Raporunda açık teslimat arzı olarak anlık izlenir.

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

</main>
