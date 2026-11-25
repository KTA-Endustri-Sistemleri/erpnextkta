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

---

## 📐 8. 7+4 Kutu Barkod Standardı, LEGACY Dönüşümü ve Özel Stock Entry Tipleri

Fiziksel kutu izlenebilirliğinin mal kabul, sayım ve üretim iade döngüleri boyunca bozulmadan sürmesi için **7 Hane Lot + 4 Hane Kutu No** standardı ile özel `Stock Entry Type` ayrımı uygulanır:

### 7+4 Standart Kutu Formatı ve LEGACY Dönüşümü
- **Format Kuralı (`is_standard_kta_box_batch`):** `^[A-Z0-9]{7}(?!0000)[0-9]{4}$` (tam 7 haneli büyük harf/rakam Lot kökü + `0001..9999` 4 haneli Kutu soneki, ör. `6640A670001`). Sistemde `Batch == sut_barcode` birebir eşleşmesi korunur.
- **Kısmi Bölme & FIFO/GKK Mirası (`allocate_next_box_batches`):** Standart bir kutu bölündüğünde aynı 7 haneli lottan sıradaki `000x` kutu üretilir. Kaynak `Batch` üzerindeki `supplier`, `reference_doctype` / `reference_name` (mal kabul ve GKK kilidi izlenebilirliği), `manufacturing_date` (FIFO yaşı) ve `expiry_date` alanları birebir kopyalanır.
- **LEGACY ve Partisiz Stok Standardizasyonu (`generate_new_base_lot`):** `LEGACY-...` veya standart dışı partilerde benzersiz yeni 7 haneli kök lot ve `{7Hane}0001..N` kutular oluşturulur.
- **Boş Etiket Temizliği (`clear_empty_labels`):** Yalnızca SABE kaydı hiç olmayanlar değil, hareket görüp tüm depolardaki net `SLE + SBE` bakiyesi `<= 0` seviyesine düşen tüm `Depo Giriş Etiketi` kayıtları da güvenle temizlenir.

### Özel Stock Entry Type Kuralları (`erpnextkta/kta_stock/setup.py`)
`hooks.py:after_migrate` üzerinden idempotent kurulan ve etiket davranışını yöneten tipler:

| Stock Entry Type | Purpose | `custom_etiket_basilabilir` | Şablon | İş Kuralı ve Davranış |
|---|---|---|---|---|
| `Return from Production Supply` | `Material Transfer` | `1` | `Depo Giriş Etiketi` | Üretim hatlarından (`150x`) hammadde raflarına (`110`) **tam kalan** standart kutuların iadesidir. `upsert_box_label` mevcut `Purchase Receipt` referansını silmeden miktar/depo alanlarını günceller ve etiket basar; iptalde etiket defter bakiyesine geri senkronlanır. |
| `Package Split` | `Repack` | `1` | `Depo Giriş Etiketi` | Koli/parti bölme ve `LEGACY` dönüşümleri içindir (`create_package_split_repack`). **Tek belge = tek `item_code` ve tek kaynak kutu** kuralı `KTAStockEntry.validate()` ile korunur (`{0} allows only one item per Stock Entry.`). Yeni `000x` kutulara etiket basılır, kaynak kutu kalan bakiyesi senkronize edilir. |
| `Package Merge` | `Repack` | `1` | `Depo Giriş Etiketi` | Aynı ürüne ait `>= 2` tam kutuyu tek partide birleştirmek içindir (`create_package_merge_repack`). **Tek belge = tek `item_code`** kuralı `KTAStockEntry.validate()` ile korunur; aynı lot kesintisiz birleşir, karma/standart dışı lot `allow_mixed_lots=1` onayıyla yeni `7+4` lot ve `KARMA LOT` etiket referansı alır. İptal/silmede tüketilen kaynak etiketler geri yüklenir. |
| Standart `Material Transfer` & Standart `Repack` | `Material Transfer` / `Repack` | `0` | *Yok* | Normal masaüstü transfer/repack belgeleri ile `110 → 150x` tam koli hat ikmalleri tamamen sessizdir (otomatik etiket basılmaz). |

> **Önemli ERPNext Çekirdek Kuralı (`set_stock_entry_type`):** ERPNext'te `se.set_stock_entry_type()` metodu `stock_entry_type` alanını `is_standard = 1` ile ezer. Bu nedenle `Return from Production Supply`, `Package Split` veya `Package Merge` oluşturan servisler `se.stock_entry_type` atandıktan sonra `set_stock_entry_type()` çağırmamalıdır.

---

## 📊 9. Sayım ve Etiket Merkezi (`/app/stock-reco-dashboard`)

### Kullanım Akışı ve Desk Kısayolu
- **Form Kısayolu (`erpnextkta/public/js/stock_reconciliation.js`):** `Stock Reconciliation` formu üzerindeki **Sayım ve Etiket Merkezinde Aç** butonu `frappe.route_options = { doc, tab: "operations" }` ile ilgili belgeyi doğrudan merkezin operasyon sekmesinde açar.
- **Toplu Sayım Oluşturma (`BulkCreateRecoModal.vue`):** Depo grubu (`is_group = 1`), tarih/saat ve `Boş Stokları Yoksay` seçimiyle tüm alt yaprak depolar için `create_stock_reco_docs_for_warehouse_group` arka plan görevini başlatır.
- **Etiket Sağlık Durumları (`get_stock_reconciliation_label_preview`):** ERPNext v15 `serial_and_batch_bundle` / `batch_no` satırlarını okuyarak her pozitif kalemi `valid` (`Uyumlu`), `qty_changed` (`Miktar Değişti`), `missing_label` (`Etiket Eksik`) veya `legacy_batch` (`LEGACY / Partisiz`) olarak sınıflar.
- **Dinamik Etiket Tipi Çözümlemesi (`Depo Giriş Etiketi` vs. `İş Emri Etiketi`):**
  - **Malzeme Kökenine Göre Otomatik Eşleşme:** Hammaddeler (`Purchase Receipt` kökenli veya satın alma kalemleri) için varsayılan olarak **Depo Giriş Etiketi**, mamul ve yarı mamuller (`Work Order` / `Stock Entry` kökenli veya BOM'lu / `ÜRÜNLER` grubu kalemleri) için otomatik olarak **İş Emri Etiketi** şablonu çözümlenir (`resolve_item_default_label_type`).
  - **Etiket Eşleşme Bütünlüğü:** Mamul partiler daha önce yalnızca mal kabul etiketleri sorgulandığı için hatalı olarak `missing_label` ("Etiket Eksik") durumuna düşebilmekteydi. Yapılan dinamik çözümleme sayesinde mamul partiler sistemdeki mevcut `İş Emri Etiketi` kayıtlarıyla eksiksiz eşleşir.
  - **Dashboard Görsel Rozetleri:** Sayım ve Etiketleme tablosunda her parti kodunun yanında ürünün kökenine uygun olarak `🏭 İş Emri` veya `📦 Depo` rozeti gösterilir; böylece operatör hangi etiket şablonunun basılacağını önizleme ekranında anında doğrular.
- **Mod 1 (Fiziksel Kutu Esas) vs. Mod 2 (Sistem Partisi Esas):** Mod 1 yalnızca `qty_changed`, `missing_label` ve `legacy_batch` satırlarını seçerken, Mod 2 belgedeki tüm pozitif stok satırlarını kapsar.
- **Belge Durumuna Göre İşlem Akışı:**
  - **Taslak (`Draft / docstatus = 0`) Belgede Kullanıcı Seçenekleri (`submit_and_print_stock_reconciliation`):**
    - **Taslakta Kaydet & Etiket Bas (`submit_doc=0`):** Sayım belgesini kapatmadan/onaylamadan (`docstatus = 0` kalarak), yalnızca seçili satırlar için standart `7+4` parti atamasını / kutu bölmesini taslak belgeye kaydeder ve Zebra yazıcıdan etiketleri basar. Sayım devam ederken kutuları hemen etiketlemek için kullanılır. Taslak aşamasındaki partiler defter bakiyesi henüz oluşmadığı için `clear_empty_labels` koruması altındadır.
    - **Sayımı Onayla ve Tamamla (`submit_doc=1`):** Sayım operasyonunun tamamı bittiğinde `LEGACY` sıfırlama ve yeni kutu kırılımlarını kesinleştirir, belgeyi `docstatus = 1` ile resmi olarak stok defterine (`Stock Ledger`) işler ve etiketleri Zebra yazıcı kuyruğuna gönderir.
  - **Onaylı (`Submitted / docstatus = 1`) Belgede (`relabel_submitted_stock_reconciliation`):**
    - Tekil standart kutular `upsert_box_label` ile güncellenir; bölme veya `LEGACY` dönüşümlerinde `create_package_split_repack(..., ignore_reco_lock=is_reco_manager)` ile `Stock Entry (Package Split)` kesilir. `ignore_reco_lock=True`, yalnızca sistem kaynaklı sayım düzeltmelerinde geçici `frappe.flags.kta_ignore_reco_lock` bayrağıyla `stock_reconciliation_lock` engelini güvenli biçimde aşar.
- **Sayım Belgesi İptali ve Silinmesinde Etiket/Parti Otomatik Temizliği (Rollback):**
  - **Otomatik Etiket ve Yazdırma Günlüğü Temizliği (`delete_labels_with_print_logs`):** `Stock Reconciliation` belgesi iptal edildiğinde (`Cancel / docstatus = 2`) veya silindiğinde (`Delete / Trash`), bu belgeye bağlı olarak oluşturulmuş tüm `KTA Stock Label` ve `KTA Print Log` kayıtları sistem tarafından otomatik olarak silinir.
  - **Bağlantı Hatasının (`LinkExistsError`) Önlenmesi:** Kullanıcılar daha önce sayım belgesini iptal ederken veya silerken karşılaştıkları `LinkExistsError` (*"Cannot delete or cancel because linked with KTA Stock Label"*) hatasıyla artık karşılaşmaz. Sistemin tüm geri alma (rollback) sürecini otomatik ve güvenli biçimde yönetmesi sağlanmıştır.
  - **Sıfır Bakiyeli Partilerin Pasife Alınması veya Silinmesi:** Sayım esnasında üretilmiş olup defter bakiyesi sıfıra düşen (`Stock Ledger Entry` net bakiyesi `0` olan) bölünmüş partiler, belge silindiğinde (`on_trash`) sistemden tamamen silinir; belge iptal edildiğinde (`on_cancel`) ise stok defteri tarihsel hareket izlenebilirliğini korumak amacıyla pasife alınarak miktarı sıfırlanır (`disabled = 1, batch_qty = 0`). Ayrıca `LabelPrinter.clear_empty_labels()` çağrılarak yetim kalan etiketler de sistemden ayıklanır.
- **Fark & Anomali Analizi (`RecoAnalyticsTab.vue` + `RecoItemDrawer.vue`):** Yıl/tarih/eşik/yön filtreleri, 7 KPI kartı, Taslak/Onaylı ilerleme barı, kural tabanlı anomali tespiti, risk puanlaması, CSV dışa aktarma ve Socket.IO (`stock_reco_dashboard_update`) canlı yenileme içerir.

---

## 📱 10. Bağımsız PDA Depo Merkezi (`/pda`)

El terminalleri (Zebra, Honeywell vb.) için Desk yükünden tamamen izole edilmiş, bağımsız HTML5 PWA + Vue 3 SPA saha operasyon portalıdır.

### Rol Modeli, Saf `Website User` İzolasyonu ve Cihaz Güvenliği
- **Standalone PWA Kabuğu (`erpnextkta/www/pda.html`, `erpnextkta/www/pda.py`):** `web.html` şablonundan türemez; yalnızca `manifest.webmanifest`, `pda-hub.bundle`, `csrf_token`, `boot_json` (`load_translations`) ve `pda_boot_json` enjekte edilir. Portal giriş kapısı `ALL_PDA_ROLES` kümesini kullanır.
- **Merkezi Rol ve Modül Kayıt Defteri (`PDA_MODULE_REGISTRY` & `ALL_PDA_ROLES`):** Sabit `PDA_DEPARTMENTS` filtresi kaldırılmıştır. Stok modülü yetkisi `PDA_STOCK_ROLES = {"KTA PDA Stock User", "Stock Manager", "System Manager"}` ile tanımlanır; genel ofis `Stock User` rolü `ALL_PDA_ROLES` içinde yer almaz ve `/pda` ile tüm PDA uçlarından `frappe.PermissionError` ile reddedilir.
- **Saf `Website User` Rolü (`KTA PDA Stock User`):** `erpnextkta/kta_stock/setup.py` (`setup_pda_roles_and_permissions()`) üzerinden `desk_access = 0` ve `home_page = "/pda"` ayarlarıyla oluşturulur; doğrudan `/login` sonrası `/me` yerine `/pda` ekranına yönlendirir ve `/app` Desk erişimini engeller. 8 çekirdek belge (`Stock Entry`, `Serial and Batch Bundle`, `Batch`, `Stock Ledger Entry`, `Item`, `Warehouse`, `KTA Stock Label`, `KTA Line Replenishment Order`) için `Custom DocPerm` tanımlanır.
- **`pda_user_guard.py` (`doc_events`) Koruması:** `override_doctype_class["Employee"]` (`hrms.overrides.employee_master.EmployeeMaster`) ezilmeden `hooks.py` `doc_events` (`Employee.before_save`, `User.before_validate`, `Employee.on_update`) üzerinden çalışır. Yalnızca `KTA PDA *` (`desk_access = 0`) rolüne sahip ve hiç `desk_access = 1` rolü olmayan kullanıcıların `Employee` kaydı güncellendiğinde `Employee.update_user()` tarafından otomatik eklenen `"Employee"` rolünü bellekten çıkarır; Desk rollü kullanıcılara ve `User` formundaki manuel atamalara dokunmaz.
- **30 Günlük Cihaz Çerezi (`kta_pda_device`):** Yetkili bir PDA kullanıcısı `/pda` rotasını açtığında HMAC-SHA256 imzalı HTTP-only çerez set edilir (`set_pda_device_cookie`). Geçerli çerez taşımayan `Guest` istekleri `/login?redirect-to=/pda` yönlendirmesi alır; RPC uçlarında `frappe.PermissionError` fırlatılır.
- **Departmansız PIN Doğrulama & Oturum Geçişi (`verify_pda_pin`):** Departman kısıtı olmaksızın aktif `Employee`, etkin `User` (`enabled = 1`) ve `ALL_PDA_ROLES` kesişimine sahip operatörler listelenir (`get_pda_operators`). 4 haneli `Employee.custom_pda_pin` sabit zamanlı (`hmac.compare_digest`) doğrulanır; `pda_pin_fail:{employee}` cache anahtarı üzerinden 5 hatalı denemede 300 saniye kilit uygulanır. Başarılı girişte `LoginManager.login_as(emp.user_id)` ile gerçek Frappe oturumu açılır.
- **Otomatik Kilit (`300s`) ve Devret (`pda_handover_logout`):** 5 dakika hareketsizlikte (`useInactivityLock`) veya `[Devret ↩]` butonunda Frappe oturumu sonlandırılır, `clearMenuSessionState()` ile menü/kategori/çekmece durumu sıfırlanır, cihaz çerezi korunur, `_build_pda_translations_payload("Guest")` ile varsayılan Türkçe sözlük paketi dönülerek taze `csrf_token` ile PIN ekranına dönülür.
- **Yazıcı Eşleşmesi & `KTA Printer Permission`:** `setup_pda_roles_and_permissions()`, `KTA Printer Permission` (`istable: 0`; `printer`, `role`, `can_print`) üzerinde `role = "Stock User", can_print = 1` kaydı olan kısıtlı Zebra yazıcılara idempotent olarak `role = "KTA PDA Stock User", can_print = 1` belgesi ekler; izin kaydı olmayan herkese açık yazıcılara dokunmaz. Çalışma anında `ZebraPrinterManager.get_printer_for_user()` aktif oturum kullanıcısının `KTA User Zebra Printers` (`printer`, `fallback_printer`) tercihini ve `ZebraPrinterManager._user_can_print(user, printer_name)` yetkisini kullanır.
- **Backfill Migration (`erpnextkta.patches.v4_4.setup_pda_stock_role_and_backfill`):** Rol ve izin kurulumunu çalıştırır; mevcut aktif `AMBAR`/`Sevk` çalışanlarından etkin `Stock User` veya `Stock Manager` hesabına sahip olanlara eski Desk rollerini silmeden tahribatsız biçimde `KTA PDA Stock User` rolünü ekler.

### İki Satırlı Üst Bar, Çok-Modüllü Menü (`Stock`), 5 Saha Modülü ve Ayarlar (`PdaSettingsView`)
- **İki Satırlı Üst Bar & Çekmece (`PdaHubApp.vue`, `PdaMenuDrawer.vue`, `LauncherHome.vue`, `types.ts`):** `get_pda_boot_data()` ve `verify_pda_pin()` yanıtlarındaki `menu_categories` ağacını kullanır (`Stock` menüsü altında 5 ekran; `LauncherHome.vue` `accent-purple` kart kenarlığını destekler). Tek yetkili kategoride (`Stock`) doğrudan 5 ekran kartı açılır; çoklu kategoride kategori seçim ekranı, `0` kategoride `"Yetkili Modül Bulunamadı"` ekranı gösterilir. Dar mobil ekranlarda taşmayı önlemek için `.pda-topbar` içinde yalnızca `[data-testid="topbar-menu-btn"]` (`☰ Menü`), statik `[data-testid="topbar-brand"]` (`📱 KTA PDA`) ve sağdaki operatör/sayaç/devret öğeleri bulunur; `activeModule !== "home"` veya çoklu kategoride kategori seçiliyken hemen altında açılan `.pda-subbar` (`[data-testid="pda-subbar"]`) üzerinde `[data-testid="topbar-back-btn"]` (`← Geri`) ve tam esneyen `[data-testid="topbar-breadcrumb"]` (`KTA PDA` / `Ana Modüller › Stock` / `Stock › ...` / `Ayarlar`) render edilir (`<PdaMenuDrawer>` `<Teleport to="body">` içindedir). Çekmecenin altındaki sabit `AYARLAR` (`[data-testid="drawer-settings-group"]` → `[data-testid="drawer-item-settings"]`) tüm PDA rollerine açıktır (`PdaUtilityScreenKey = "settings"`). `activeOperator && !activeOperator.has_pin` durumunda `LauncherHome.vue` içinde `[data-testid="missing-pin-banner"]` ve `[data-testid="missing-pin-cta"]` (`Şimdi Belirle`) banner'ı gösterilir.
- **Self-Servis Ayarlar, PIN Yönetimi, Yazıcı Tercihi ve Canlı Dil/Tema (`PdaSettingsView.vue`, `PdaPinSettingsCard.vue`, `pdaPreferences.ts`, `frappeShim.ts`):**
  1. *Kişisel PIN & Yönetici Sıfırlama:* `PdaPinSettingsCard.vue` `has_employee = false` durumunda bilgi kutusu gösterir; `has_pin = false` ise ilk kurulum (`mode="initial"`), `has_pin = true` ise `Mevcut PIN İle` (`mode="current_pin"`) veya `PIN'imi Unuttum (Şifre İle)` (`mode="account_password"`, cache `pda_pwd_fail:{user}` ile 5 deneme / 300s kilit) modlarını sunar. PIN yazımları `Employee.save()` yan etkilerinden kaçınmak için doğrudan `set_encrypted_password("Employee", emp.name, clean_new, fieldname="custom_pda_pin")` üzerinden yapılır ve ilgili kilit anahtarlarını temizler. `pda_admin_reset_operator_pin` kendi kendine sıfırlamayı reddeder; `_get_manageable_pda_operators(caller_user)` `Stock Manager` için yalnızca yönetici olmayan saf PDA operatörlerini (`not (Stock Manager | System Manager)`), `System Manager` için ise kendisi dışındaki tüm aktif PDA operatörlerini döndürür.
  2. *Zebra Yazıcı Seçimi & Bağlantı Testi:* Yalnızca `ZebraPrinterManager._user_can_print(user, printer_name)` filtresinden geçen yazıcılar listelenir; `printer == fallback_printer` reddedilir ve `KTA User Zebra Printers` kaydı `ignore_permissions=True` ile güncellenir (her iki alan boşaltılırsa `disabled = 1`). `pda_test_printer_connection` çıktı/log üretmeden `ZebraPrinterManager().check_printer_status(clean_name)` ile anlık durum döner.
  3. *Cihaz Tercihleri & Sayfa Yenilemesiz Dil Değişimi:* `pdaPreferences.ts` tema (`kta_pda_theme` → `<html data-theme="dark">`) ve sesli uyarı (`kta_pda_sound`) tercihlerini fiziksel terminale `localStorage` üzerinden kaydeder; `line-replenishment-pda/utils/audio.ts` içindeki `playBeep()` `localStorage.getItem("kta_pda_sound") === "0"` olduğunda sessiz döner. `frappeShim.ts` içindeki reaktif `runtimeLocaleState` ve `setRuntimeTranslations(lang, messages)` yardımcıları `verify_pda_pin`, `pda_handover_logout` ve `pda_update_user_language` dönüşlerindeki `lang` + `messages` sözlüğünü anında Vue arayüzüne yansıtır; ortak `line-replenishment-pda/components/{PickingItemCard,TransferFooter,OrderSelector}.vue` bileşenleri `[data-theme="dark"]` ile uyumludur (`PickingItemCard.vue` sadeleştirilerek 248 satıra indirildi).
1. **Hat İkmal Toplama (`PickingModuleView.vue`):** `line_replenishment_picking` ve `complete_line_replenishment_picking` uçları `_require_replenishment_picking_access()` (`_PICKING_ALLOWED_ROLES` + `KTA Line Replenishment Order` izni) ile korunur; `Guest` ve yetkisiz kullanıcılar reddedilirken saf `KTA PDA Stock User` sorunsuz toplama yapabilir (`override_item_source` ve `cancel_line_replenishment_order` mevcut Desk akışını korur).
2. **Koli Bölme ve Etiketleme (`PackageSplitView.vue` → `pda_package_split`):** `_require_pda_screen_access("split")` ile korunur; tek kısmi ayırma veya çoklu kutu kırılımı destekler (`create_package_split_repack`). Hedef kutular `KTAStockEntry.on_submit()` ile tek sefer basılır; kalan bakiye `> 0` ve `reprint_source_label = 1` ise yalnız kaynak etiket yeniden kuyruğa eklenir.
3. **Koli Birleştirme (`PackageMergeView.vue` → `pda_package_merge` & `create_package_merge_repack`):** `PDA_MODULE_REGISTRY` içinde `"split"` ardından `"merge"` anahtarıyla (`accent-purple`) tanımlıdır ve `_require_pda_screen_access("merge")` ile korunur (`setup.py` `STOCK_ENTRY_TYPES` içinde `Package Merge` / `purpose="Repack"`). Aynı `item_code` için `>= 2` benzersiz `(batch_no, warehouse)` kutusunun kaynak deposundaki tam pozitif defter bakiyesi birleştirilir (`1 Kutu = 1 Parti`); aktif yaprak depo, aynı `company`, `resolve_warehouse_barcode` (hedef raf barkodu için), `validate_stock_entry_warehouse_lock` ve `validate_batch_qi_on_transfer` tam uygulanır, opsiyonel `target_warehouse_barcode` verilmezse ilk kutunun deposu kullanılır. Tüm standart `7+4` kutular aynı 7 haneli lot ön ekindeyse uyarı olmadan sıradaki kutu partisi ve PR/WO/GKK + `min(expiry_date)` meta verisi devralınır; farklı lot veya standart dışı partide (`is_mixed_lot = True`) frontend `<Teleport to="body">` Karma Lot Onay Modalı (`[data-testid="mixed-lot-confirm-modal"]`) açılır ve backend `allow_mixed_lots=1` olmadan işlemi reddeder. Onaylı karma lotlarda ağırlıklı ortalama değerleme uygulanır, yeni `7+4` karma lot üretilip `Batch.reference_doctype = "Stock Entry"` / `Batch.reference_name = se.name` bağlanır, `resolve_batch_label_metadata()` `"KARMA LOT"` dalıyla hedef etikete `quality_ref = "KARMA LOT"` basılır ve 3 katmanlı denetim izi (`Stock Entry Type`, `Stock Entry.remarks`, `Batch.description`) kaydedilir. `KTAStockEntry` tek ürün koruması (`_validate_single_item_package_split`) `"Package Merge"` belgesine de uygulanır; `on_cancel` / `on_trash` sırasında `_clear_batch_reference_links()` ile `LinkExistsError` önlenir ve `_sync_relabeling_on_cleanup()` bakiye dönen tüketilmiş kaynak kutuların `KTA Stock Label` kayıtlarını `upsert_box_label` ile geri yükler.
4. **Depo Raf Transferi (`MaterialTransferView.vue` → `pda_material_transfer`):** `_require_pda_screen_access("transfer")` ile korunur; `1 Kutu = 1 Parti` tam kutu transferi zorunludur. `resolve_warehouse_barcode` şirket soneksiz/ekli ve SAP önekli raf barkodlarını çözer, taslak sayım kilidi ve GKK kalite onayını uygular ve etiket depo alanlarını senkronlar.
5. **Stok ve Etiket Sorgula (`StockLookupView.vue` → `pda_stock_lookup`):** `_require_pda_screen_access("lookup")` ile korunur; kutu/parti (`KTA Stock Label` / `Batch`), raf (`Bin`, `resolve_warehouse_barcode` üzerinden) veya malzeme (`Item` / `Item Barcode`) barkodları için anlık bakiye özetini döner (`pda_scan_box` ise `("split", "merge", "transfer", "lookup")` ekran izinlerini denetler ve `base_lot` alanını döner).
- **SAP Önekli Raf Barkodu Çözümleme (`resolve_warehouse_barcode` — `pda_material_transfer`, `pda_package_merge`, `pda_stock_lookup`):**
  - *Birebir Eşleşme Önceliği:* Önce `Warehouse.name` ve `warehouse_name` üzerinden tam eşleşme aranır; böylece adı zaten önekli olan mamul rafları (örn. `170-W1F-12-01`) doğrudan kendi adıyla korunur.
  - *NestedSet (`lft`/`rgt`) Üst Depo Doğrulaması:* Doğrudan eşleşme yoksa `<depo_kodu>-<raf_kodu>` biçimindeki eski SAP künye barkodları (örn. `110-W1A-01-01` → `W1A-01-01`, `110-W1F-01-01` → `W1F-01-01`) ayrıştırılır ve `Warehouse` NestedSet (`lft`/`rgt`) ağacında ilgili `<depo_kodu>` önekli üst depo altında yer aldığı doğrulanarak çözümlenir.
  - *Yanlış Önek & Devredilip Pasife Alınmış Raf Koruması:* Yanlış depo öneki taşıyan künyeler (örn. `170-W1F-01-01`) üst depo doğrulamasından geçemeyerek reddedilir. `110` altında yer alıp `170`'e devredilerek pasife alınmış rafların eski künyesi (`110-W1F-12-01`) okutulduğunda ise `170-W1F-12-01` rafına kayma olmadan net `"Depo pasif durumda"` uyarısı üretilir.

### Whitelisted PDA API Uçları (`erpnextkta/kta_stock/services/pda_service.py`)

| Metot | Parametreler | Açıklama |
|---|---|---|
| `get_pda_boot_data` | *(Yok)* | Yetkili cihaz/kullanıcı doğrulaması sonrası kilit durumu, operatör listesi, yetkili `menu_categories` ağacı ve `open_picking_count` döner (`allow_guest=True`). |
| `verify_pda_pin` | `employee`, `pin` | 5 deneme / 300s korumalı 4 haneli PIN doğrular, `login_as` ile oturumu geçirip taze `csrf_token`, `menu_categories`, `open_picking_count` ve `_build_pda_translations_payload(emp.user_id)` (`lang`, `messages`) döner (`POST`, `allow_guest=True`). |
| `pda_handover_logout` | *(Yok)* | Operatör oturumunu kapatır, `kta_pda_device` çerezini korur, yeni `csrf_token` ve `_build_pda_translations_payload("Guest")` (`lang`, `messages`) döner (`POST`, `allow_guest=True`). |
| `pda_get_settings_data` | *(Yok)* | Operatör `Employee`/PIN durumunu (`has_employee`, `has_pin`), RBAC filtreli `manageable_operators` listesini, `ZebraPrinterManager._user_can_print` filtreli `authorized_printers` listesini, `KTA User Zebra Printers` tercihlerini ve `user_language` değerini döner (`GET`). |
| `pda_update_own_pin` | `new_pin`, `confirm_pin`, `mode="initial"`, `current_pin=None`, `account_password=None` | İlk PIN kurulumu, mevcut PIN ile değişim (`_verify_pin_with_rate_limit`) veya hesap şifresiyle sıfırlama (`_verify_account_password_with_rate_limit`, `pda_pwd_fail:{user}`) işlemlerini `Employee.save()` çağırmadan `set_encrypted_password` ile kaydeder (`POST`). |
| `pda_admin_reset_operator_pin` | `target_employee`, `new_pin`, `confirm_pin` | Sıkı RBAC hiyerarşisi altında (kendi kendine sıfırlama yasak; `Stock Manager` yalnız yönetici olmayan saf PDA operatörlerini, `System Manager` kendisi dışındaki tüm aktif operatörleri sıfırlar) hedef PIN'i günceller ve `pda_pin_fail` + `pda_pwd_fail` kilitlerini temizler (`POST`). |
| `pda_save_printer_preferences` | `printer=None`, `fallback_printer=None` | Varsayılan ve yedek yazıcı ayrılığını (`printer != fallback_printer`) ve `_user_can_print` iznini doğrulayarak `KTA User Zebra Printers` kaydını günceller/oluşturur (`POST`). |
| `pda_test_printer_connection` | `printer_name` | Yazıcı varlığı ve `_user_can_print` kontrolünden sonra etiket/log oluşturmadan `ZebraPrinterManager().check_printer_status()` durumunu döner (`POST`). |
| `pda_update_user_language` | `language` | Desteklenen diller (`tr`, `en`, `de`) içinde `User.language` alanını kalıcı günceller, önbelleği temizler ve `_build_pda_translations_payload(clean_lang)` (`lang`, `messages`) döner (`POST`). |
| `pda_scan_box` | `barcode` | `_require_pda_screen_access(("split", "merge", "transfer", "lookup"))` sonrası `sut_barcode` veya `Batch` üzerinden ürün, `base_lot`, standart parti bilgisi ve depo bakiyelerini döner. |
| `pda_package_split` | `item_code`, `source_warehouse`, `source_batch`, `split_qtys`, `reprint_source_label=1` | `_require_pda_screen_access("split")` sonrası `Package Split` keser ve kalan kaynak kutu varsa isteğe bağlı kaynak etiketi yeniden basar (`POST`). |
| `pda_package_merge` | `source_boxes`, `target_warehouse_barcode=None`, `allow_mixed_lots=0` | `_require_pda_screen_access("merge")` sonrası `resolve_warehouse_barcode` ile hedef rafı çözer ve `>= 2` aynı ürünlü tam kutuyu `create_package_merge_repack` ile tek partide birleştirir (`POST`). |
| `pda_material_transfer` | `item_code`, `batch_no`, `source_warehouse`, `target_warehouse_barcode`, `qty=None` | `_require_pda_screen_access("transfer")` sonrası `resolve_warehouse_barcode` ile hedef rafı çözer, tam kutu `Material Transfer` belgesini submit eder ve etiket depo alanlarını senkronlar (`POST`). |
| `pda_stock_lookup` | `barcode` | `_require_pda_screen_access("lookup")` sonrası kutu/parti, raf (`resolve_warehouse_barcode`) veya malzeme barkoduna göre `kind` (`batch`/`warehouse`/`item`) stok özeti döner. |

---

## 🧱 11. Teknik Mimari, Servis Katmanı ve Dosya Yapısı

Eski `erpnextkta/rest-api/` klasörü kaldırılarak tüm stok ve sayım servisleri modül içi `erpnextkta/kta_stock/services/` altında birleştirilmiştir:

- **Backend Servisleri (`erpnextkta/kta_stock/` & PDA Portal):**
  - `erpnextkta/overrides/stock_reconciliation.py`: `StockReconciliation` DocType sınıf geçersiz kılması (override); `remove_items_with_no_change` ile sıfır fark satır koruması, `on_cancel` ve `on_trash` kancalarıyla `_cleanup_associated_labels_and_batches` ve `delete_labels_with_print_logs` rollback otomasyonu.
  - `erpnextkta/kta_stock/setup.py`: `after_migrate` hook'u ile özel `Stock Entry Type` kayıtlarını, `Employee.custom_pda_pin` özel alanını (`setup_pda_custom_fields`) ve `setup_pda_roles_and_permissions()` (`KTA PDA Stock User`, `Custom DocPerm`, `KTA Printer Permission`) kurulumunu güvenceye alır.
  - `erpnextkta/kta_stock/pda_user_guard.py` & `erpnextkta/hooks.py`: `Employee.before_save`, `User.before_validate` ve `Employee.on_update` `doc_events` kancalarıyla saf `Website User` (`KTA PDA *`) hesaplarında otomatik `"Employee"` rolü eklenmesini engeller (`EmployeeMaster` ezilmeden).
  - `erpnextkta/patches/v4_4/add_employee_pda_pin_field.py` & `setup_pda_stock_role_and_backfill.py`: `Employee.custom_pda_pin` alanını ekleyen ve `KTA PDA Stock User` kurulumunu / aktif depo operatör backfill'ini çalıştıran veritabanı migration yamaları.
  - `erpnextkta/kta_stock/services/pda_service.py` & `erpnextkta/www/{pda.py, pda.html}`: Bağımsız `/pda` portalı, `PDA_MODULE_REGISTRY`, `ALL_PDA_ROLES`, 30 günlük HMAC cihaz çerezi, PIN/şifre rate-limit / `login_as` oturum yönetimi, `set_encrypted_password` ile doğrudan PIN güncelleme, RBAC filtreli yönetici PIN sıfırlama (`_get_manageable_pda_operators`), `KTA User Zebra Printers` tercih/test servisleri, `_build_pda_translations_payload` canlı çeviri üreteci ve saha operasyon servisleri.
  - `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py` & `erpnextkta/kta_stock/line_replenishment_service.py`: Hat ikmal toplama ve `_require_replenishment_picking_access()` yetki doğrulaması.
  - `erpnextkta/kta_stock/services/relabeling_service.py`: `is_standard_kta_box_batch`, `extract_base_lot`, `generate_new_base_lot`, `allocate_next_box_batches`, `resolve_item_default_label_type`, `resolve_batch_label_metadata` (`KARMA LOT` dahil), `get_batch_ledger_balances`, `delete_labels_with_print_logs`, `upsert_box_label`, `sync_batch_label_to_ledger_balance`, `create_package_split_repack`, `create_package_merge_repack`.
  - `erpnextkta/kta_stock/services/stock_reconciliation_service.py`: `get_items_static`, `create_stock_reco_docs_for_warehouse_group`, `list_stock_reconciliations`, `get_stock_reconciliation_label_preview`, `submit_and_print_stock_reconciliation`, `relabel_submitted_stock_reconciliation`.
  - `erpnextkta/kta_stock/services/stock_reconciliation_dashboard_service.py`: `get_years`, `get_dashboard`, `get_item_details`.
  - `erpnextkta/kta_stock/services/stock_reconciliation_lock.py`: `validate_unique_draft_stock_reco_per_set_warehouse` ve `validate_stock_entry_warehouse_lock`.
  - `erpnextkta/kta_stock/label_manager.py` & `erpnextkta/overrides/KTAStockEntry.py`: v15 `serial_and_batch_bundle` kaynak depo çözümü, `enqueue_print_labels_by_names`, `Package Split` / `Package Merge` tek ürün validasyonu (`_validate_single_item_package_split`), iptal/silmede `_clear_batch_reference_links` (`LinkExistsError` koruması) ve `_sync_relabeling_on_cleanup` (tüketilen kaynak kutu etiketlerinin geri yüklenmesi + PR etiketlerinin defter bakiyesine geri senkronizasyonu; `erpnextkta/overrides/serial_batch_bundle_doc.py` `autoname()` genişletmesi dahil).
- **Frontend SPA (`erpnextkta/public/stock-reco-dashboard/`, `erpnextkta/public/pda-hub/` & Paylaşılan Hat İkmal Bileşenleri):**
  - `stock-reco-dashboard/`: `App.vue`, `types.ts`, `utils/analyticsHelpers.ts`, `components/BulkCreateRecoModal.vue`, `components/RecoDocumentsList.vue`, `components/RecoLabelingWorkspace.vue`, `components/RecoAnalyticsTab.vue`, `components/RecoItemDrawer.vue` (`erpnextkta/kta_stock/page/stock_reco_dashboard/`).
  - `pda-hub/`: `manifest.webmanifest`, `types.ts`, `pda-hub.bundle.js`, `pda-hub.bundle.css`, `PdaHubApp.vue` (iki satırlı `.pda-topbar` + `.pda-subbar`), `utils/{frappeShim.ts, pdaPreferences.ts}` (`runtimeLocaleState`, `setRuntimeTranslations`, `kta_pda_theme`, `kta_pda_sound`), `composables/useInactivityLock.ts`, `components/{PinLockScreen.vue, LauncherHome.vue, PdaMenuDrawer.vue, PdaPinSettingsCard.vue, PdaOverlays.vue}`, `views/{PickingModuleView.vue, PackageSplitView.vue, PackageMergeView.vue, MaterialTransferView.vue, StockLookupView.vue, PdaSettingsView.vue}`.
  - `line-replenishment-pda/`: `utils/audio.ts` (`kta_pda_sound` sessize alma koruması) ve `[data-theme="dark"]` uyumlu paylaşılan bileşenler (`components/{PickingItemCard.vue, TransferFooter.vue, OrderSelector.vue}`; `PickingItemCard.vue` 248 satır).
- **Otomatik Testler:**
  - `erpnextkta/kta_stock/tests/{test_pda_role_setup.py, test_pda_service.py, test_pda_portal.py, test_pda_settings.py}`
  - `erpnextkta/kta_stock/tests/{test_line_replenishment_picking_page.py, test_line_replenishment_service.py, test_line_replenishment_transfer.py}`
  - `erpnextkta/public/pda-hub/__tests__/{frappeShim.spec.ts, PdaHubApp.spec.ts, PinLockAndLauncher.spec.ts, WarehouseModules.spec.ts, PdaSettingsView.spec.ts}` (Vitest)
  - `erpnextkta/kta_stock/tests/test_relabeling_service.py`
  - `erpnextkta/kta_stock/tests/test_label_manager.py`
  - `erpnextkta/kta_stock/tests/test_stock_reconciliation_relabeling.py`
  - `erpnextkta/tests/test_stock_reconciliation_override.py`
  - `erpnextkta/tests/test_stock_entry_labeling.py`

</main>

