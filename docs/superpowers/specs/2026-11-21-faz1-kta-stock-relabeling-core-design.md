# Faz 1 Tasarım Dokümanı: `kta_stock` Çekirdek Etiket/Parti Motoru ve `rest-api` Taşıması

**Tarih:** 2026-11-21  
**Durum:** Implemented  
**Faz:** 1 / 3  
**Kapsam:** `erpnextkta/rest-api/**` (taşıma & kaldırma), `erpnextkta/kta_stock/**`, `erpnextkta/overrides/**`, `erpnextkta/hooks.py`, `erpnextkta/public/js/stock_reconciliation.js` (geçici RPC yolu), `erpnextkta/public/stock-reco-dashboard/App.vue` (geçici RPC yolu)

---

## 3 Fazlı Program Yol Haritası

| Faz | Konu | Spec | Plan |
|---|---|---|---|
| **Faz 1 (Bu Doküman)** | `rest-api` → `kta_stock/services` taşıması, özel `Stock Entry Type` kurulumu, `7+4` Koli Bölme / `LEGACY` Dönüştürme ve `label_manager` / `KTAStockEntry` düzeltmeleri | `2026-11-21-faz1-kta-stock-relabeling-core-design.md` | `2026-11-21-faz1-kta-stock-relabeling-core.md` |
| **Faz 2** | 2 Sekmeli Vue 3 + TypeScript Sayım Merkezi (`stock-reco-dashboard`: Operasyon & Mod 1/2 Etiketleme + Canlı Fark/Anomali Analizi) | [Faz 2 Spec](./2026-11-21-faz2-stock-reco-hub-vue-ts-design.md) | [Faz 2 Plan](../plans/2026-11-21-faz2-stock-reco-hub-vue-ts.md) |
| **Faz 3** | `Shopfloor Hub` Üretim Tedarik Alanından İade (`150x → 110`), İsteğe Bağlı Koli Bölme ve Portal/Geliştirici Dokümantasyonu + TR/EN/DE Çevirileri | [Faz 3 Spec](./2026-11-21-faz3-shopfloor-supply-return-and-split-design.md) | [Faz 3 Plan](../plans/2026-11-21-faz3-shopfloor-supply-return-and-split.md) |

---

## 1. Amaç ve Problem Tanımı

### Neden Şimdi?
1. **Yaklaşan Fiziksel Depo Sayımı (`Stock Reconciliation`):** Geçmişte ERPNext çıkışları FIFO ve koli/parti disiplini olmadan ürün + miktar üzerinden yürütüldüğü için, sayımda raftaki fiziksel kutular ile sistemdeki `Batch` ve `qty` kayıtları arasında ciddi uyuşmazlıklar, açılmış yarım kutular/makaralar ve eski `LEGACY-...` partileri ortaya çıkacaktır.
2. **Sayım Sonrası Düzeni Koruma:** Sayımda düzeltilen etiket düzeninin üretim ve iade döngüsünde yeniden bozulmaması için:
   - `110 HAMMADDE` deposuna açılmış veya bölünmüş koli girerken tekil koli barkod disiplini korunmalı,
   - `Line Replenishment` (`110 → 150x`) toplama akışı tam koli ile çıktığı için **etiket basmadan** hızlı kalmalı,
   - Normal masaüstü (`Desk`) `Material Transfer` ve standart `Repack` işlemlerinde **%0 davranış değişikliği** olmalıdır.
3. **Mimari Dağınıklığın Giderilmesi:** Sayım kilidi, toplu sayım fişi üretimi ve sayım panosu API'leri şu anda modül dışı `erpnextkta/rest-api/` klasöründe durmaktadır; bunların `erpnextkta/kta_stock/services/` altında toplanması gerekmektedir.

### Hedefler, Hedef Dışı ve Anti-Hedefler
- **Hedefler:**
  - KTA'nın mevcut `7 hane Lot (Serial and Batch Bundle / kök Batch) + 4 hane Kutu No (Batch == sut_barcode)` hiyerarşisini (`örn. 6640A67` → `6640A670001..N`) sayım, `LEGACY` dönüşüm, koli bölme ve depoya iade akışlarının tamamında standartlaştırmak.
  - Yalnızca özel `Stock Entry Type` kayıtlarında (`Return from Production Supply` ve `Package Split`) otomatik Zebra etiket basımını devreye almak; standart `Material Transfer` ve standart `Repack` fişlerini tamamen sessiz tutmak.
  - `label_manager.py` içindeki ERPNext v15 `serial_and_batch_bundle` ve kaynak depo okuma hatalarını düzeltmek.
- **Hedef Dışı (Faz 1 Kapsamında Değil):**
  - Sayım Merkezi Vue + TypeScript arayüzü (Faz 2).
  - `Shopfloor Hub` içinden `Depoya İade` modalı ve `Hatlar Arası Koli Bölme` arayüzü (Faz 3).
  - `Line Replenishment` (`110 → 150x`) veya `Manufacture` iş emri etiket akışını değiştirmek.
- **Anti-Hedefler (Kesin Kaçınılacaklar):**
  - Aynı `Repack` (`Package Split`) belgesi içine birden fazla farklı ürün veya belirsiz çoklu kaynak kutu sıkıştırmak (maliyet havuzu karışması ve ERPNext `Set Basic Rate Manually` hatası doğurur).
  - Sayımdan *önce* teorik stoğa göre önden toplu etiket basmak (miktar uyumsuz çöp etiket riski).
  - Kutu bölünmeden yapılan bir iade fişi iptal edildiğinde, orijinal mal kabul (`Purchase Receipt`) etiketini silmek.

---

## 2. Değerlendirilen Yaklaşımlar ve Seçilen Mimari

### Alternatif 1: ERPNext `Batch` Sabit Kalır, Sadece `KTA Stock Label` İçinde Kutu Barkodu Bölünür
- Muhasebedeki `Batch` değişmez, yalnızca `KTA Stock Label` tablosunda sanal `sut_barcode` kırılımı tutulur.
- **Reddedilme Nedeni:** KTA'da `BatchSplitManager` ve `SerialandBatchBundle` doğrudan `1 Fiziksel Kutu = 1 11-hane Batch = 1 SUT` üzerine kuruludur; `quality_inspection_validator.py` ve `find_bins_of_sut()` bu birebir eşleşmeyi varsayar. Sanal barkod eklemek iki kutuyu aynı `Batch` altında görünmez kılar.

### Alternatif 2: Özel `Stock Entry Type` + Kalem/Kutu Bazlı `Package Split` (`Repack`) Motoru **(Seçilen)**
- **Nasıl Çalışır:**
  1. Kutu bölünmüyorsa (`qty` değişimi veya tam kalan kutunun depoya iadesi): `Batch` ve `sut_barcode` sabit kalır; `KTA Stock Label` kaydının `qty` ve depo bilgisi defter bakiyesiyle eşitlenir.
  2. Kutu fiziksel olarak bölünüyorsa veya `LEGACY` / partisiz stok standartlaştırılıyorsa: **Her kaynak kutu için bağımsız bir `Package Split` (`purpose="Repack"`)** belgesi kesilir; standart lottan sıradaki `000x` (`6640A670006`) veya yeni 7 haneli lottan `0001..N` (`{7Hane}0001`) kutular üretilir, ilk mal kabul `manufacturing_date`, GKK referansı ve maliyeti miras alınır.
  3. Otomatik etiket basımı depo adı tahminleriyle değil doğrudan iki özel `Stock Entry Type` (`Return from Production Supply` ve `Package Split`) üzerinden kontrol edilir.

---

## 3. Teknik Tasarım ve Modül Sözleşmeleri

### 3.1 `erpnextkta/rest-api/` Klasörünün `kta_stock/services/` Altına Taşınması

| Eski Yol | Yeni Yol | Not |
|---|---|---|
| `erpnextkta/rest-api/__init__.py` | *(Silinir)* | `erpnextkta/kta_stock/services/__init__.py` açılır |
| `erpnextkta/rest-api/stock_reconciliation.py` | `erpnextkta/kta_stock/services/stock_reconciliation_service.py` | İçindeki `frappe.enqueue` worker yolu yeni modüle güncellenir |
| `erpnextkta/rest-api/stock_reconciliation_dashboard.py` | `erpnextkta/kta_stock/services/stock_reconciliation_dashboard_service.py` | Mevcut `@frappe.whitelist()` imzaları (`get_years`, `get_dashboard`, `get_item_details`) korunur |
| `erpnextkta/rest-api/stock_reconciliation_lock.py` | `erpnextkta/kta_stock/services/stock_reconciliation_lock.py` | Kilit mantığı + sistem destekli sayım sonrası bölme için kilit istisnası kancası |

**Eşzamanlı Bağlantı Güncellemeleri (`Faz 1` içinde kırılmama garantisi):**
- `erpnextkta/hooks.py`:
  - `Stock Reconciliation.validate` → `erpnextkta.kta_stock.services.stock_reconciliation_lock.validate_unique_draft_stock_reco_per_set_warehouse`
  - `Stock Entry.validate` → `erpnextkta.kta_stock.services.stock_reconciliation_lock.validate_stock_entry_warehouse_lock`
  - `after_migrate` listesine `erpnextkta.kta_stock.setup.setup` eklenir.
- `erpnextkta/public/js/stock_reconciliation.js`: `get_items_static` ve `create_stock_reco_docs_for_warehouse_group` RPC yolları yeni servis modülüne çevrilir.
- `erpnextkta/public/stock-reco-dashboard/App.vue`: Mevcut panodaki 3 `rest-api` RPC çağrısı Faz 2'deki tam TS dönüşümüne kadar çalışır kalsın diye yeni modül yoluna çevrilir.

---

### 3.2 Özel `Stock Entry Type` Kurulumu (`erpnextkta/kta_stock/setup.py`)

`setup()` (`hooks.py:after_migrate` üzerinden idempotent çağrılır) şu 3 kaydı güvenceye alır:

1. **`Return from Production Supply`**
   - `purpose`: `"Material Transfer"`
   - `is_standard`: `0`
   - `custom_etiket_basilabilir`: `1`
   - `custom_etiket_sablonu`: `"Depo Giriş Etiketi"`
   - TR/EN/DE çeviri anahtarı: `Return from Production Supply` ↔ `Üretim Tedarik Alanından İade` ↔ `Rückgabe aus Produktionsversorgungsbereich`
2. **`Package Split`**
   - `purpose`: `"Repack"`
   - `is_standard`: `0`
   - `custom_etiket_basilabilir`: `1`
   - `custom_etiket_sablonu`: `"Depo Giriş Etiketi"`
   - TR/EN/DE çeviri anahtarı: `Package Split` ↔ `Koli Bölme` ↔ `Gebindeteilung`
3. **Standart `Repack` (`is_standard = 1`) Temizliği:**
   - Mevcut canlı veritabanında standart `Repack` üzerinde `custom_etiket_basilabilir = 1` ve sistemde olmayan `"Repack Etiketi"` tanımlıdır (submit sonrası sessiz hata logu üretmektedir).
   - `setup()` içinde standart `"Repack"` kaydı `custom_etiket_basilabilir = 0`, `custom_etiket_sablonu = None` yapılır; böylece standart masaüstü `Material Transfer` ve `Repack` %100 sessiz kalır.

> [!CAUTION]
> **ERPNext Core Tuzağı (`set_stock_entry_type`):** ERPNext'te `se.set_stock_entry_type()` metodu, `stock_entry_type` alanını `{"purpose": self.purpose, "is_standard": 1}` ile ezer. Bu yüzden `Return from Production Supply` veya `Package Split` türünde belge oluşturan hiçbir servis `se.stock_entry_type = ...` atamasından sonra `se.set_stock_entry_type()` çağırmamalıdır!

---

### 3.3 Çekirdek Koli Bölme, `LEGACY` Dönüştürme ve Etiket Motoru (`relabeling_service.py`)

Yeni modül: `erpnextkta/kta_stock/services/relabeling_service.py`

#### 3.3.1 Lot ve Koli Numarası Standardı
- **`is_standard_kta_box_batch(batch_no)`:** Kesin biçim kuralı `^[A-Z0-9]{7}(?!0000)[0-9]{4}$` (tam 7 büyük harf/rakam Lot kökü + `0001..9999` 4 haneli Kutu soneki, tire/boşluk içermez; `"LEGACY-10040004"`, `"R202400035-..."`, `"T101660-..."` veya `"6640A670000"` gibi kayıtlar `False` döner).
- **`extract_base_lot(batch_no)`:** Standart 11 haneli kutularda `batch_no[:7]` döner (`6640A67`); ayrıca kök/bölünmemiş lot tam 7 karakterli `[A-Z0-9]{7}` ise (`2124E11`) mevcut lot kökünü koruyacak şekilde yardımcı olarak okunabilir.
- **`generate_new_base_lot(item_code, preferred_prefix=None, ...) -> str`:**
  - `LEGACY-...` veya standart dışı partilerde yeni 7 karakterli büyük harf alfanümerik kök üretir (`frappe.generate_hash("", 7).upper()`). Çakışma varsa (`Batch` veya `Serial and Batch Bundle` adı olarak mevcutsa) benzersiz olana kadar tekrar üretir.
  - Kök `Batch` (`batch_qty = 0`, `reference_doctype`, `reference_name`, `supplier`, `manufacturing_date`, `expiry_date`) oluşturulur.
- **`allocate_next_box_batches(base_lot, count, source_batch_meta) -> list[str]`:**
  - `BatchSplitManager._get_last_batch_number_for_base(base_lot)` üzerinden mevcut en yüksek 4 haneli soneki bulur ve sıradaki `count` adet `{base_lot}{seq:04d}` `Batch` kaydını açar (ör. `6640A670006`).
  - **FIFO Yaşı ve Kalite Mirası (Kritik Kural):** Yeni açılan her `000x` `Batch` kaydı, bölündüğü kaynak `Batch` kaydından şunları birebir kopyalar:
    - `supplier`
    - `reference_doctype` ve `reference_name` (böylece GKK / `quality_inspection_validator.py` kilidi ve PR izlenebilirliği kesintisiz sürer)
    - `manufacturing_date` (böylece bugün bölünen poşet FIFO sıralamasında bugünün malı gibi en arkaya atılmaz)
    - `expiry_date`

#### 3.3.2 `SerialandBatchBundle` İsimlendirme Genişletmesi
- `erpnextkta/overrides/serial_batch_bundle_doc.py` içindeki hem `autoname()` hem `_kta_get_preferred_name()` şu an yalnızca `voucher_type == "Purchase Receipt"` için bundle adına 7 haneli `base_lot` vermektedir (`Purchase Receipt Item.batch_no` okuyarak).
- Faz 1'de `autoname()` kapsamı `("Purchase Receipt", "Stock Entry", "Stock Reconciliation")` olarak genişletilir; `Purchase Receipt` için mevcut mantık korunur, `Inward` yönlü `Package Split` (`Stock Entry`) ve `Stock Reconciliation` bundle'larında ise `SerialBatchCreation` tarafından `save()` öncesinde doldurulmuş `self.entries` içindeki 7 haneli ortak `base_lot = batch_no[:-4]` okunur. DB'de henüz bu adda bundle yoksa seçilir; varsa çakışmasız şekilde `None` dönülerek ERPNext varsayılan benzersiz adına düşülür.

#### 3.3.3 Etiket Meta Verisi ve Tekil Kutu Etiketi Senkronu
- **`resolve_batch_label_metadata(item_code, batch_no)`:**
  1. Aynı `batch_no` için mevcut `KTA Stock Label` kaydı varsa onun `quality_ref`, `supplier_delivery_note`, `gr_posting_date`, `reference_doctype`, `reference_name` değerlerini alır.
  2. Yoksa aynı 7 haneli lot altındaki kardeş etiketlerden (`batch LIKE "{base_lot}%"`) veya `Batch.reference_doctype == "Purchase Receipt"` üzerinden PR irsaliyesi + onaylı `Quality Inspection` numarasını bulur.
  3. Hiçbiri yoksa güvenli varsayılanları döner: `quality_ref = "SAYIM"` (sayım kaynaklıysa) veya `"-"` / `"ATLA 5/1"`, `supplier_delivery_note = "-"`.
- **`upsert_box_label(...)`:**
  - `KTA Stock Label` içinde `{sut_barcode: batch_no, label_type: "Depo Giriş Etiketi"}` için tekil aktif kayıt tutar (aynı `sut_barcode` için 2. bir kopya yaratmaz; `LabelPrinter.get_label_item_batch()` tekil kayıt invariantını korur).
  - Mevcut kayıt `reference_doctype == "Purchase Receipt"` ise **orijinal mal kabul referansını korur**; yalnızca `qty`, `target_warehouse`, `source_warehouse`, `gr_posting_date` ve varsa eksik meta alanları günceller. Böylece `Return from Production Supply` belgesi iptal edilse bile mal kabul etiketi silinmez, defter bakiyesine geri senkronlanır.
- **`sync_batch_label_to_ledger_balance(item_code, batch_no)`:**
  - Verilen `item_code + batch_no` ikilisinin tüm aktif depolardaki net defter toplamını (`SLE + SBE`) hesaplar:
    - Net toplam `> 0` ise `KTA Stock Label.qty` alanını bu net toplamla (ve pozitif stoğun bulunduğu hedef depoyla) günceller.
    - Net toplam `<= 0` ise ilgili `KTA Stock Label` kaydını (bağlı `KTA Print Log` kayıtlarıyla birlikte veya güvenli şekilde) siler.

#### 3.3.4 Kalem/Kutu Bazlı Atomik `Package Split` (`create_package_split_repack`)
- **Tek Kaynak Kutu = Tek `Package Split` (`Repack`) Belgesi Kuralı:**
  - Girdi: `item_code`, `source_warehouse`, `target_warehouse`, `source_batch`, `split_qtys: list[float]`, `remarks`, `posting_date`, `ignore_reco_lock: bool = False`.
  - Çıkış satırı: `1` satır (`s_warehouse = source_warehouse`, `batch_no = source_batch`, `qty = sum(split_qtys)`, `use_serial_batch_fields = 1`).
  - Giriş satırları: `split_qtys` sayısı kadar satır; her biri aynı `item_code` için yeni üretilmiş tekil `{base_lot}{seq:04d}` `Batch` ile (`t_warehouse = target_warehouse`, `use_serial_batch_fields = 1`). Tüm giriş satırları tek `item_code` paylaştığı için ERPNext `fg_items` sayısı `1` olur (`Set Basic Rate Manually` hatası tetiklenmez); kaynak batch/depo değerleme oranı (`basic_rate`) birebir miras alınarak `abs(se.value_difference) < 0.01` korunur.
  - `stock_entry_type = "Package Split"`, `purpose = "Repack"` atanır; `set_stock_entry_type()` **çağrılmaz**.
  - `ignore_reco_lock=True` parametresi yalnızca sistem kaynaklı sayım/dönüşüm çağrılarında `try ... finally` bloğu içinde geçici `frappe.flags.kta_ignore_reco_lock = True` bayrağı set ederek `stock_reconciliation_lock.validate_stock_entry_warehouse_lock()` kilidini aşar (rol gereksinimini bozmadan).
  - Kaynak kutunun defterdeki kalan bakiyesi `> 0` ise `sync_batch_label_to_ledger_balance` ile kaynak kutu etiketi kalan bakiyeye güncellenir; `0` olduysa (`LEGACY` tamamen dönüştürüldüyse) eski etiket temizlenir.
  - Eğer birden fazla ürün veya birden fazla kaynak kutu bölünecekse, çağırıcı döngü içinde her kaynak kutu için ayrı `create_package_split_repack` çağırır ve dönen yeni `Stock Entry` isim listesini döner.

---

### 3.4 `label_manager.py`, `batch_manager.py` ve `KTAStockEntry.py` Düzeltmeleri

1. **`erpnextkta/kta_stock/label_manager.py`:**
   - `_extract_stock_entry_batch_allocations(doc, row)`: Hem klasik `row.batch_no` hem de ERPNext v15 `row.serial_and_batch_bundle` (`Serial and Batch Entry` içindeki `is_outward = 0` ve `warehouse = row.t_warehouse`) kayıtlarını okur.
   - `_resolve_source_warehouse_for_row(doc, row, batch_no)`:
     - `Material Transfer` (`Return from Production Supply`) satırlarında doğrudan `row.s_warehouse` kullanır.
     - `Repack` (`Package Split`) giriş satırlarında önce `(row.item_code + batch[:-4] lot kökü)` eşleşen çıkış satırının `s_warehouse` alanını, yoksa aynı `row.item_code` çıkış satırının `s_warehouse` alanını kullanır.
   - `print_stock_entry_labels(stock_entry, enqueue=False)`:
     - `doc.purpose == "Manufacture"` ise mevcut `print_kta_wo_labels_of_stock_entry` akışı aynen korunur.
     - `doc.stock_entry_type in ("Return from Production Supply", "Package Split")` (veya diğer `custom_etiket_basilabilir = 1` olan `Depo Giriş Etiketi` tipleri) için hatalı `custom_musteri_paketleme_miktari` bölmesi **kaldırılır**, gerçek `batch_no` / bundle girişlerinden `relabeling_service.upsert_box_label(...)` ile etiketler güncellenir ve `ZebraPrinterManager` üzerinden (`_print_pr_labels_by_names`) basılır.
   - `LabelPrinter.clear_empty_labels()`:
     - Mevcut kodda `get_bins_of_item` + `get_sabe_parents_of_bins_for_batch` yalnızca SABE kaydı *hiç* yoksa siliyordu (hareket görmüş ama bakiyesi `0` olmuş partileri temizlemiyordu).
     - Net stok bakiyesi (`SLE + SBE` toplamı) `<= 0` olan tüm `Depo Giriş Etiketi` kayıtlarını güvenle temizleyecek şekilde güncellenir.
2. **`erpnextkta/overrides/KTAStockEntry.py`:**
   - `validate()`: Kullanıcı masaüstünden manuel olarak `stock_entry_type == "Package Split"` belgesinde **tek belgeye birden fazla farklı `item_code` (giriş)** koyarsa açıklayıcı hata fırlatır (*"Her ürün/kaynak koli için ayrı bir Koli Bölme belgesi oluşturun."*).
   - `on_submit()`: Mevcut `print_labels_on_submit` kuyruğu, yeni iki özel tip için de `custom_etiket_basilabilir = 1` üzerinden otomatik çalışır.
   - `on_cancel()` / `on_trash()`:
     - Yalnızca `reference_doctype == "Stock Entry"` ve `reference_name == self.name` olan etiketleri siler (PR kökenli etiketlere dokunmaz).
     - `Return from Production Supply` veya `Package Split` iptal edildiğinde dokunulan kaynak/hedef `(item_code, batch_no)` çiftleri için `sync_batch_label_to_ledger_balance()` çalıştırır; böylece eski etiket bakiyesi defterle birebir eşleşmeye geri döner.
     - `Package Split` iptalinde açılmış yeni `000x` kutu partilerinin bakiyesi `0` ise `disabled = 1` işaretlenir.

---

## 4. Test Stratejisi (TDD)

1. **`erpnextkta/kta_stock/tests/test_label_manager.py` & `test_relabeling_service.py` (Birim & Entegrasyon):**
   - `allocate_next_box_batches`: `6640A670001..0005` varken `0006` üretimi ve `manufacturing_date` / `reference_name` / `supplier` mirası.
   - `LEGACY` dönüşümü: 7 haneli yeni kök lot + `0001, 0002` kutularının üretimi ve eski `LEGACY` etiketinin sıfırlanması.
   - `upsert_box_label`: PR etiketinin miktar güncellenmesi ve `reference_doctype == "Purchase Receipt"` referansının korunması.
   - `create_package_split_repack`: Tek belge 1 çıkış → N giriş `Package Split`, `set_stock_entry_type()` ezmesinin yaşanmaması, kaynak kutu kalan etiketinin güncellenmesi.
   - Çoklu ürünlü manuel `Package Split` validasyon engeli.
   - `clear_empty_labels`: Bakiyesi `0`'a inmiş SABE geçmişli partinin etiketini silmesi, pozitif bakiyeliye dokunmaması.
   - `rest-api` → `kta_stock/services` taşıması sonrası `stock_reconciliation_lock` ve `stock_reconciliation_service` regresyonları.
2. **`erpnextkta/tests/test_stock_entry_labeling.py`:**
   - Standart `Material Transfer` ve standart `Repack` (`is_standard = 1`) üzerinde **0** etiket üretildiği doğrulaması.
   - `Return from Production Supply` submit & cancel döngüsü: PR etiketinin silinmemesi ve miktarının defter bakiyesine dönmesi.
   - ERPNext v15 `serial_and_batch_bundle` üzerinden okunan transferlerde kaynak depo ve lot bazlı etiket eşleştirmesi.

---

## 5. Faz 2 ve Faz 3'e Sağlanan Kontrat

Faz 1 tamamlandığında Faz 2 ve Faz 3 şu kararlı Python API'lerini doğrudan tüketir:
- `erpnextkta.kta_stock.services.relabeling_service`:
  - `is_standard_kta_box_batch(batch_no: str | None) -> bool`
  - `extract_base_lot(batch_no: str | None) -> str | None`
  - `generate_new_base_lot(item_code: str, reference_doctype: str | None = None, reference_name: str | None = None, manufacturing_date: str | None = None, supplier: str | None = None, expiry_date: str | None = None) -> str`
  - `allocate_next_box_batches(base_lot: str, count: int, item_code: str, source_meta: dict | None = None) -> list[str]`
  - `resolve_batch_label_metadata(item_code: str, batch_no: str | None, fallback_ref: str = "SAYIM") -> dict`
  - `upsert_box_label(item_code: str, batch_no: str, qty: float, target_warehouse: str | None = None, source_warehouse: str | None = None, reference_doctype: str | None = None, reference_name: str | None = None, posting_date: str | None = None, quality_ref: str | None = None, supplier_delivery_note: str | None = None) -> str`
  - `sync_batch_label_to_ledger_balance(item_code: str, batch_no: str) -> None`
  - `create_package_split_repack(item_code: str, source_warehouse: str, target_warehouse: str, source_batch: str | None, split_qtys: list[float], remarks: str | None = None, posting_date: str | None = None, ignore_reco_lock: bool = False) -> dict`
- `erpnextkta.kta_stock.label_manager.enqueue_print_labels_by_names(label_names: list[str], user: str | None = None) -> dict`
- `Stock Entry Type`: `"Return from Production Supply"`, `"Package Split"`
