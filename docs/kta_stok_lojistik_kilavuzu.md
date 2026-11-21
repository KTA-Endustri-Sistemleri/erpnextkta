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

Sistemdeki MRP ve stok seviyesi (Re-Order) kurallarına göre otomatik olarak açılan Üretim (Manufacture) tipi Malzeme Taleplerinin yönetimi için özel bir iş akışı oluşturulmuştur:
- **Otomatik Taslak (Draft) Oluşumu:** Sistem tarafından yaratılan üretim malzeme talepleri artık otomatik onaylanmak yerine "Taslak" (Draft) olarak bırakılır ve ilgili planlama personeline incelemesi için bir **ToDo (Görev)** atanır.
- **Dinamik Görev Aktarımı:** Personel talebi inceleyip "Onayla (Submit)" dediğinde, üzerindeki görev otomatik olarak kapanır ve üretim yöneticilerine "İş Emri Oluşturma" görevi açılır. (Görevli listesi *Assignment Rule* ekranından yönetilir.)
- **Otomatik Kapanış:** Üretim yöneticileri bu talep üzerinden **İş Emri (Work Order)** oluşturup %100 oranında onayladıklarında, üzerlerindeki görev arka planda otomatik olarak "Tamamlandı" statüsüne geçerek kapanır.

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
| `Package Split` | `Repack` | `1` | `Depo Giriş Etiketi` | Koli/parti bölme ve `LEGACY` dönüşümleri içindir (`create_package_split_repack`). **Tek belge = tek `item_code` ve tek kaynak kutu** kuralı `KTAStockEntry.validate()` ile korunur (`Package Split allows only one item per Stock Entry.`). Yeni `000x` kutulara etiket basılır, kaynak kutu kalan bakiyesi senkronize edilir. |
| Standart `Material Transfer` & Standart `Repack` | `Material Transfer` / `Repack` | `0` | *Yok* | Normal masaüstü transfer/repack belgeleri ile `110 → 150x` tam koli hat ikmalleri tamamen sessizdir (otomatik etiket basılmaz). |

> **Önemli ERPNext Çekirdek Kuralı (`set_stock_entry_type`):** ERPNext'te `se.set_stock_entry_type()` metodu `stock_entry_type` alanını `is_standard = 1` ile ezer. Bu nedenle `Return from Production Supply` veya `Package Split` oluşturan servisler `se.stock_entry_type` atandıktan sonra `set_stock_entry_type()` çağırmamalıdır.

---

## 📊 9. Sayım ve Etiket Merkezi (`/app/stock-reco-dashboard`)

### Kullanım Akışı ve Desk Kısayolu
- **Form Kısayolu (`erpnextkta/public/js/stock_reconciliation.js`):** `Stock Reconciliation` formu üzerindeki **Sayım ve Etiket Merkezinde Aç** butonu `frappe.route_options = { doc, tab: "operations" }` ile ilgili belgeyi doğrudan merkezin operasyon sekmesinde açar.
- **Toplu Sayım Oluşturma (`BulkCreateRecoModal.vue`):** Depo grubu (`is_group = 1`), tarih/saat ve `Boş Stokları Yoksay` seçimiyle tüm alt yaprak depolar için `create_stock_reco_docs_for_warehouse_group` arka plan görevini başlatır.
- **Etiket Sağlık Durumları (`get_stock_reconciliation_label_preview`):** ERPNext v15 `serial_and_batch_bundle` / `batch_no` satırlarını okuyarak her pozitif kalemi `valid` (`Uyumlu`), `qty_changed` (`Miktar Değişti`), `missing_label` (`Etiket Eksik`) veya `legacy_batch` (`LEGACY / Partisiz`) olarak sınıflar.
- **Mod 1 (Fiziksel Kutu Esas) vs. Mod 2 (Sistem Partisi Esas):** Mod 1 yalnızca `qty_changed`, `missing_label` ve `legacy_batch` satırlarını seçerken, Mod 2 belgedeki tüm pozitif stok satırlarını kapsar.
- **Taslak (`submit_and_print_stock_reconciliation`) & Onaylı (`relabel_submitted_stock_reconciliation`):**
  - Taslakta `LEGACY` dönüşümleri için eski partiyi sıfırlama satırı korunup yeni `7+4` satırlar yazılır; çoklu kutu kırılımında sıradaki `000x` satırları eklenir, belge submit edilir ve etiketler Zebra kuyruğuna gönderilir.
  - Onaylı belgede tekil standart kutular `upsert_box_label` ile güncellenir; bölme veya `LEGACY` dönüşümlerinde `create_package_split_repack(..., ignore_reco_lock=is_reco_manager)` ile `Stock Entry (Package Split)` kesilir. `ignore_reco_lock=True`, yalnızca sistem kaynaklı sayım düzeltmelerinde geçici `frappe.flags.kta_ignore_reco_lock` bayrağıyla `stock_reconciliation_lock` engelini güvenli biçimde aşar.
- **Fark & Anomali Analizi (`RecoAnalyticsTab.vue` + `RecoItemDrawer.vue`):** Yıl/tarih/eşik/yön filtreleri, 7 KPI kartı, Taslak/Onaylı ilerleme barı, kural tabanlı anomali tespiti, risk puanlaması, CSV dışa aktarma ve Socket.IO (`stock_reco_dashboard_update`) canlı yenileme içerir.

---

## 🧱 10. Teknik Mimari, Servis Katmanı ve Dosya Yapısı

Eski `erpnextkta/rest-api/` klasörü kaldırılarak tüm stok ve sayım servisleri modül içi `erpnextkta/kta_stock/services/` altında birleştirilmiştir:

- **Backend Servisleri (`erpnextkta/kta_stock/`):**
  - `erpnextkta/kta_stock/setup.py`: `after_migrate` hook'u ile özel `Stock Entry Type` kayıtlarını güvenceye alır.
  - `erpnextkta/kta_stock/services/relabeling_service.py`: `is_standard_kta_box_batch`, `extract_base_lot`, `generate_new_base_lot`, `allocate_next_box_batches`, `resolve_batch_label_metadata`, `get_batch_ledger_balances`, `delete_labels_with_print_logs`, `upsert_box_label`, `sync_batch_label_to_ledger_balance`, `create_package_split_repack`.
  - `erpnextkta/kta_stock/services/stock_reconciliation_service.py`: `get_items_static`, `create_stock_reco_docs_for_warehouse_group`, `list_stock_reconciliations`, `get_stock_reconciliation_label_preview`, `submit_and_print_stock_reconciliation`, `relabel_submitted_stock_reconciliation`.
  - `erpnextkta/kta_stock/services/stock_reconciliation_dashboard_service.py`: `get_years`, `get_dashboard`, `get_item_details`.
  - `erpnextkta/kta_stock/services/stock_reconciliation_lock.py`: `validate_unique_draft_stock_reco_per_set_warehouse` ve `validate_stock_entry_warehouse_lock`.
  - `erpnextkta/kta_stock/label_manager.py` & `erpnextkta/overrides/KTAStockEntry.py`: v15 `serial_and_batch_bundle` kaynak depo çözümü, `enqueue_print_labels_by_names`, `Package Split` tek ürün validasyonu ve iptalde PR etiketlerinin defter bakiyesine geri senkronizasyonu (`erpnextkta/overrides/serial_batch_bundle_doc.py` `autoname()` genişletmesi dahil).
- **Frontend SPA (`erpnextkta/public/stock-reco-dashboard/`):**
  - `App.vue`, `types.ts`, `utils/analyticsHelpers.ts`, `components/BulkCreateRecoModal.vue`, `components/RecoDocumentsList.vue`, `components/RecoLabelingWorkspace.vue`, `components/RecoAnalyticsTab.vue`, `components/RecoItemDrawer.vue` (`erpnextkta/kta_stock/page/stock_reco_dashboard/`).
- **Otomatik Testler:**
  - `erpnextkta/kta_stock/tests/test_relabeling_service.py`
  - `erpnextkta/kta_stock/tests/test_label_manager.py`
  - `erpnextkta/kta_stock/tests/test_stock_reconciliation_relabeling.py`
  - `erpnextkta/tests/test_stock_entry_labeling.py`

</main>
