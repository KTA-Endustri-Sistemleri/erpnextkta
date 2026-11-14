# Satınalma İrsaliyesi (Purchase Receipt) İş Akışı, Yetkilendirme ve Mal Kabul Uyuşmazlığı Tasarım Dokümanı

**Tarih:** 2026-11-13  
**Durum:** Onay Bekliyor  
**Kapsam:** `erpnextkta/fixtures/`, `erpnextkta/custom/`, `erpnextkta/kta_mrp/mrp_engine/` ve `erpnextkta/public/js/`

---

## 1. Amaç ve Problem Tanımı (Intent & Why)

KTA Endüstri Sistemleri satın alma ve lojistik operasyonlarında:
1. **Görevler Ayrılığı (Segregation of Duties) İhlali:**  
   Mal henüz fabrikaya/depoya fiziken inmemişken (`Yolda`, `Antrepoda`, `Gümrüklemede`), bu aşamalar operasyonel ve hukuki olarak **Dış Ticaret / Satınalma (Ceren Keçici & Ömür Muslu)** sorumluluğundadır. Ancak mevcut sistemde depo personellerinde de `Purchase User` ve `Purchase Manager` rollerinin bulunması nedeniyle, depocular bu aşamalardaki evrakları tek tuşla reddedebilmekte (`Reject`) ve lojistik sürecini geri sarabilmektedir.
2. **Hatalı Geri Dönüş Rotası (Bozuk Rollback Zinciri):**  
   Mevcut iş akışında (`KTA Mal Giris Sureci`), gümrükten çekilip fabrika kapısına (`Mal Giriş`) gelmiş bir ithalat irsaliyesi reddedildiğinde, aradaki `Gümrüklemede` ve `Antrepoda` adımları hiçe sayılarak doğrudan `Yolda` statüsüne fırlatılmaktadır. Bu durum gümrük beyannamesi açılmış malı tekrar gemide göstermekte ve MRP teslimat takvimini haftalarca ileriye öteleyerek yanıltmaktadır.
3. **Kullanılamaz Malzemenin Gri Alanı (Karantina / Uyuşmazlık):**  
   İster yerli ister ithal olsun, fabrika kapısına inen bir hammadde üzerinde evrak uyumsuzluğu, eksiklik veya koli hasarı varsa o mal fiilen ve hukuken **kullanılamazdır (bloke)**. Ancak mal fabrika sahasında beklediği için MRP motorunun bunu nasıl ele alacağı plancı açısından belirsiz kalmaktadır.

Bu tasarım dokümanı; yetkileri net olarak izole eden, lojistik hiyerarşiye uygun adım adım geri dönüş (step-by-step rollback) sağlayan, kapıdaki sorunları **`Mal Kabul Uyuşmazlığı`** ara statüsünde şeffaflaştıran ve MRP motorunu güvenli tarafta tutan mimariyi tanımlar.

---

## 2. Kullanıcı Rolleri ve Sorumluluk Matrisi

| Rol | Sorumlu Kişiler | Sorumluluk Alanı |
|---|---|---|
| **`KTA Gümrük Sorumlusu`** *(Yeni)* | Ceren Keçici, Ömür Muslu, Administrator | İthalat başlatma, Antrepo, Gümrükleme, İthalat uyuşmazlık çözümü |
| **`Purchase User` / `Purchase Manager`** | Mahmut Ayyıldız, Elif Dilbaz, Emre Öcal vb. | Yurtiçi siparişler, Yurtiçi mal kabul uyuşmazlık çözümü |
| **`Stock User` / `Stock Manager`** | Depo Personeli (Mustafa Hayri Mahiroğlu vb.) | Fabrika kapısında fiziki sayım, kontrol, `Approve` veya `Uyuşmazlık Bildir` |

---

## 3. Mimari ve Detaylı Tasarım

### 3.1. Yeni Rol: `KTA Gümrük Sorumlusu`
* Sistemde `KTA Gümrük Sorumlusu` adında yeni bir Frappe Role oluşturulur.
* Sadece Ceren Keçici (`İTHALAT - KTA`) ve Ömür Muslu'ya (ve `Administrator`) atanır.
* Depo personeli (`Stock User`) bu role sahip olamaz.

---

### 3.2. Yeni İş Akışı Statüsü: `Mal Kabul Uyuşmazlığı`
* `KTA Mal Giris Sureci` iş akışına **`Mal Kabul Uyuşmazlığı`** statüsü eklenir.
* **DocStatus:** `0` (Taslak).
* **Anlamı:** Malzeme fiziken fabrika kapısına/sahasında beklemektedir ancak depoya kabulü durdurulmuştur (karantina/bloke).
* **Düzenleme Yetkisi (`allow_edit`):**  
  * İthalat ise: `KTA Gümrük Sorumlusu`  
  * Yurtiçi ise: `Purchase User`

---

### 3.3. Yeni Veri Alanları (`Purchase Receipt`)
Depocunun kapıda ret verirken neden ret verdiğini kaydetmesi ve MRP plancısının bu nedeni raporda görebilmesi için `Purchase Receipt` DocType'ına iki özel alan eklenir:
1. **`custom_uyusmazlik_nedeni`** (Select):
   * `Evrak / İrsaliye Uyuşmazlığı`
   * `Fiziki Hasar / Kalite Problemi`
   * `Eksik / Yanlış Malzeme`
2. **`custom_uyusmazlik_aciklamasi`** (Small Text): Depocunun yazdığı kısa açıklama.

---

### 3.4. Tam Lojistik ve Geri Dönüş (Rollback) Zinciri

```
[Mal Girişe Hazır]
       ⇅  İthalat Başlat (Gümrük Sor.)  /  Reject (Gümrük Sor.)
    [Yolda]
       ⇅  Antrepoya Al (Gümrük Sor.)    /  Reject (Gümrük Sor.)
  [Antrepoda]
       ⇅  İşlem Başlat (Gümrük Sor.)    /  Reject (Gümrük Sor.)
 [Gümrüklemede]
       ⇅  Antrepodan Çek (Gümrük Sor.)  /  Gümrüğe İade (Gümrük Sor.)
   [Mal Giriş]
       ⇅  Uyuşmazlık Bildir (Depocu)    /  Sorun Çözüldü (Gümrük Sor. veya Satınalma)
[Mal Kabul Uyuşmazlığı]
```

#### A. İleri Yöndeki Geçişler:
1. `Mal Girişe Hazır` ➔ `Yolda` (*İthalat Başlat*): SADECE `KTA Gümrük Sorumlusu`.
2. `Mal Girişe Hazır` ➔ `Mal Giriş` (*Mal Giriş Başlat - Yerli*): `Stock User`.
3. `Yolda` ➔ `Antrepoda` (*Antrepoya Al*): SADECE `KTA Gümrük Sorumlusu`.
4. `Yolda` ➔ `Mal Giriş` (*İthalatı Gerçekleştir - Direkt İthalat*): SADECE `KTA Gümrük Sorumlusu`.
5. `Antrepoda` ➔ `Gümrüklemede` (*İşlem Başlat*): SADECE `KTA Gümrük Sorumlusu`.
6. `Gümrüklemede` ➔ `Mal Giriş` (*Antrepodan Çek*): SADECE `KTA Gümrük Sorumlusu`.
7. `Mal Giriş` ➔ `Kabul Edildi` (*Approve*): `Stock User` (Depocu ambar girişini tamamlar, docstatus=1).

#### B. Geri Yöndeki Geçişler (Step-by-Step Rollback):
1. `Gümrüklemede` ➔ `Antrepoda` (*Reject*): SADECE `KTA Gümrük Sorumlusu`. (Tam bir önceki adım).
2. `Antrepoda` ➔ `Yolda` (*Reject*): SADECE `KTA Gümrük Sorumlusu`. (Tam bir önceki adım).
3. `Yolda` ➔ `Mal Girişe Hazır` (*Reject*): SADECE `KTA Gümrük Sorumlusu`. (Tam bir önceki adım).
4. `Mal Giriş` ➔ `Mal Kabul Uyuşmazlığı` (*Uyuşmazlık Bildir*):  
   * Yetkili: `Stock User` (Depocu).
   * Çalışma Mantığı: Depocu butona bastığında açılan diyalog penceresinde zorunlu `custom_uyusmazlik_nedeni` ve `custom_uyusmazlik_aciklamasi` girilir.
   * **ÖNEMLİ:** Depocu artık malı doğrudan `Yolda`ya fırlatamaz!

#### C. `Mal Kabul Uyuşmazlığı`ndan Çıkış Yolları:
* **İthalat Alımları İçin (`is_import_purchase_receipt == 1`):**  
  Yetkili: SADECE `KTA Gümrük Sorumlusu` (Ceren Keçici & Ömür Muslu).
  1. *Sorun Çözüldü ➔ `Mal Giriş`:* Evrak düzeltilmiş veya mutabakat sağlanmıştır. Mal tekrar depocunun önüne kabul için düşer.
  2. *Gümrüğe İade ➔ `Gümrüklemede` (veya direkt ithalatsa `Yolda`):* Mal gümrük sahasına geri çekilir.
  3. *İptal / Mahreç İadesi ➔ `İptal Edildi`.*
* **Yurtiçi Alımları İçin (`is_import_purchase_receipt == 0`):**  
  Yetkili: `Purchase User` / `Purchase Manager` (Mahmut Ayyıldız, Elif Dilbaz vb. Yurtiçi Satınalma).
  1. *Sorun Çözüldü ➔ `Mal Giriş`:* Yerli satıcıdan revize irsaliye temin edilmiş veya eksik teslimat mutabakatı yapılmıştır.
  2. *Tedarikçiye İade ➔ `İptal Edildi` (veya `Mal Girişe Hazır`).*

---

### 3.5. MRP Motoru ve Raporlama Entegrasyonu

1. **`supply.py` (Güvenli Netleştirme):**
   * `Mal Kabul Uyuşmazlığı` statüsündeki irsaliyeler `resolve_pr_receipt_info()` fonksiyonunda `receipt_date = None` olarak değerlendirilir.
   * **Sonuç:** Net ihtiyaç hesabında **haftalık arz (`receipts`) miktarı 0 kabul edilir**. Şüpheli/hasarlı mal kullanılabilir sayılmaz; üretim hattı riske atılmaz.
2. **`service.py` & Tedarik Kırılımı (`supply_breakdown`):**
   * Plancının kör kalmaması için `supply_breakdown` sözlüğüne `uyusmazlikta_total` eklenir.
   * `open_supplies` listesinde ilgili irsaliyenin statüsü, uyuşmazlık nedeni ve açıklaması şeffaf olarak döner.
3. **Malzeme İhtiyaç Raporu & RPO Görünürlüğü:**
   * Malzeme İhtiyaç detay modalında ve RPO ekranında ilgili hammadde satırında uyarı rozeti gösterilir:
     `⚠️ Mal Kabul Uyuşmazlığı: {miktar} {uom} [{Uyuşmazlık Nedeni}] - {Tedarikçi}`
   * Plancı bu bilgiyi görerek:
     * Neden *"Evrak Uyuşmazlığı"* ise: Satınalma/Gümrük ile teyit edip siparişi bekletir (mükerrer alım önlenir).
     * Neden *"Fiziki Hasar"* ise: Malın kullanılamayacağını bilerek önerilen PO'yu derhal onaylar.

---

## 4. Test ve Doğrulama Planı

1. **Workflow & Yetki İzolasyon Testleri:**
   * Bir `Stock User` kullanıcısının `Yolda`, `Antrepoda` veya `Gümrüklemede` statüsündeki bir irsaliyede hiçbir geçiş butonunu (özellikle `Reject`) tetikleyemediğinin doğrulanması.
   * Yalnızca `KTA Gümrük Sorumlusu` rolüne sahip kullanıcının (`ceren.kecici`, `omur.muslu`) bu butonları çalıştırabildiğinin testi.
   * `Mal Giriş` aşamasında depocu ret verdiğinde evrakın `Yolda`ya değil, zorunlu gerekçe ile `Mal Kabul Uyuşmazlığı`na geçtiğinin testi.
   * İthalat uyuşmazlığında sadece `KTA Gümrük Sorumlusu`nun, yerli uyuşmazlığında ise `Purchase User`ın çözebildiğinin testi.
2. **Step-by-Step Rollback Testleri:**
   * `Gümrüklemede` ➔ `Antrepoda`
   * `Antrepoda` ➔ `Yolda`
   * `Yolda` ➔ `Mal Girişe Hazır` geçişlerinin sırayla çalıştığının ve hiçbir aşamanın atlanmadığının testi.
3. **MRP Motoru Doğrulama Testi:**
   * `Mal Kabul Uyuşmazlığı` statüsünde açık irsaliyesi olan bir hammadde için MRP çalıştırıldığında, bu irsaliyenin netleştirmede 0 sayıldığının ve eksik doğurarak sipariş önerdiğinin testi.
   * Tedarik kırılımında uyuşmazlık tipi ve miktarının doğru raporlandığının testi.
