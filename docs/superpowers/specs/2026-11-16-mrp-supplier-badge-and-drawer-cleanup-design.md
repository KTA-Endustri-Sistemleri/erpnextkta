# MRP Tedarikçi Rozeti, Çift Yüzde Temizliği, Çekmece Antrepo Sadeleştirmesi ve Çeviri Senkronizasyonu — Tasarım

- **Durum:** Onaylandı
- **Tarih:** 2026-11-16
- **Kapsam:** `erpnextkta/patches/**`, `erpnextkta/kta_mrp/**`, `erpnextkta/public/material-requirement/**`, `erpnextkta/translations/**`

---

## 1. Amaç ve Kök Nedenler

Kullanıcı tarafından tespit edilen 4 temel problem ve kök neden analizleri:

1. **`Varsayılan Tedarikçi (%%100)` Çift Yüzde Hatası:**
   - **Kök Neden:** `tabItem` tablosunda yer alan 13.627 kalemde `custom_sourcing_strategy` alanı veritabanına literal olarak `'Varsayılan Tedarikçi (%%100)'` şeklinde kaydedilmiştir.
   - **Sonuç:** `MrpItemIdentity.vue` içindeki `material.sourcing_strategy !== 'Varsayılan Tedarikçi (%100)'` koşulu `True` dönmekte ve sistem bunu özel bir strateji zannederek mor rozetle "Varsayılan Tedarikçi (%%100)" basmaktadır.

2. **10024373 Kodlu Kalemde Varsayılan Tedarikçi Rozetinin Çıkmaması:**
   - **Kök Neden:** İlk problem nedeniyle `MrpItemIdentity.vue`'da `v-else-if="material.sourcing_strategy ..."` bloğuna girilmekte, altındaki `v-else-if="material.supplier"` bloğuna hiçbir zaman ulaşılamamaktadır. Oysa kalem kartında `Stocko Contact GmbH & Co. KG` tanımlıdır.
   - **Sonuç:** Kalemin gerçek tedarikçisi arayüzde gizlenmektedir.

3. **Drawer'da İç İçe Akordiyon Karmaşası:**
   - **Kök Neden:** `MrpDetailDrawer.vue` içindeki ana "Açık Siparişler ve Teslimatlar" akordiyonunun altında çağrılan `MrpPoReceiptList.vue` bileşeni, en altında "Gümrüklü Antrepoda Bekleyen Teslimatlar" adında ikinci bir açılır-kapanır akordiyon butonu (`mrp-antrepo-toggle-btn`) barındırmaktadır.
   - **Sonuç:** Akordiyon içinde akordiyon açılması UX açısından saçma ve karmaşık bir görüntü oluşturmaktadır.

4. **Eksik ve Karışık Çeviriler (TR / EN Karışımı):**
   - **Kök Neden:** `MrpPoReceiptList.vue`, `MrpDetailDrawer.vue` vb. bileşenlerdeki Türkçe metinlerin birçoğu `translations/en.csv` ve `de.csv` dosyalarında yer almamakta veya parantezli farklı sürümleri bulunmaktadır. Frappe `__("...")` fonksiyonu eşleşme bulamadığında orijinal Türkçe metni döndürmektedir.

---

## 2. Alınan Tasarım Kararları

### 2.1 Veritabanı ve MRP Motoru Çift Yüzde Düzeltmesi
- **Kalıcı Patch (`patches/v15_0/fix_item_sourcing_strategy_percent.py`):**
  `tabItem` tablosundaki `custom_sourcing_strategy = 'Varsayılan Tedarikçi (%%100)'` olan 13.627 kaydı `UPDATE tabItem SET custom_sourcing_strategy = 'Varsayılan Tedarikçi (%100)'` ile güncelleyecek ve `patches.txt`'ye kaydedilecektir.
- **MRP Motoru Savunması (`kta_mrp/mrp_engine/supply.py`):**
  `custom_sourcing_strategy` derlenirken `.replace("%%100", "%100")` ile çift yüzdeler otomatik tek yüzdeye normalize edilecektir.

### 2.2 Frontend Tedarikçi Rozeti ve Defansif Eşleme (`MrpItemIdentity.vue`)
- `v-else-if` koşulu:
  `material.sourcing_strategy && !material.sourcing_strategy.startsWith('Varsayılan Tedarikçi')`
  şeklinde güncellenecektir. Strateji "Varsayılan Tedarikçi" olduğunda bu koşul atlanacak ve doğrudan `material.supplier` (örn. `Stocko Contact GmbH & Co. KG`) yeşil/gri tedarikçi rozeti olarak görünecektir.

### 2.3 Çekmece Açık Teslimatlar Tek ve Düz Liste (`MrpPoReceiptList.vue`)
- `MrpPoReceiptList.vue` içerisindeki iç içe açılır-kapanır buton (`mrp-antrepo-toggle-btn`) tamamen kaldırılacaktır.
- Antrepo havuzundaki teslimatlar (`antrepoPoolSupplies`) da diğer açık siparişler ve teslimatlarla birlikte aynı kart listesinde, kendilerine ait açık mavi `Antrepoda` rozetiyle doğal bir şekilde listelenecektir.

### 2.4 Çok Dilli Çeviri Senkronizasyonu (`translations/**`)
- `MrpPoReceiptList.vue` ve `MrpDetailDrawer.vue` içindeki tüm etiketler `en.csv`, `de.csv` ve `tr.csv` dosyalarına eklenecektir:
  - `Gümrüklü Antrepoda Bekleyen Teslimatlar` -> `Deliveries Pending in Bonded Warehouse`
  - `Gümrüğe Geliş` -> `Arrival at Customs`
  - `Belge` -> `Document`
  - `Tüm açık siparişleri göster` -> `Show all open orders`
  - `ETA girilmediği için tahmini hesaplanmıştır` -> `Estimated because ETA is not provided`
  - `Antrepoda bekleyen malzemeler çekim işlemi başlatılana kadar haftalık plana dahil edilmez. Gümrükleme başlatıldığında (+2 gün) fabrikaya sevk edilir.` -> `Materials pending in bonded warehouse are not included in the weekly plan until customs clearance begins. Once clearance starts (+2 days), they are dispatched to the factory.`
