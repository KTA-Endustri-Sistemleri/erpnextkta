# Faz 3 Tasarım Dokümanı: `Shopfloor Hub` Üretim Tedarik Alanından İade, İsteğe Bağlı Koli Bölme ve Dokümantasyon

**Tarih:** 2026-11-21  
**Durum:** Implemented — Kalite Kapısı Doğrulandı (`shopfloor-hub` İade + Bölme, Temiz CI & Dokümantasyon)  
**Faz:** 3 / 3  
**Önkoşul:** Faz 1 ([Faz 1 Spec](./2026-11-21-faz1-kta-stock-relabeling-core-design.md)) tamamlanmış olmalı (`Return from Production Supply`, `Package Split`, `relabeling_service.py`).  
**Kapsam:** `erpnextkta/kta_shopfloor/**`, `erpnextkta/public/shopfloor-hub/**`, `erpnextkta/www/docs/**`, `docs/*.md`, `erpnextkta/translations/**`

---

## 3 Fazlı Program Yol Haritası

| Faz | Konu | Spec | Plan |
|---|---|---|---|
| **Faz 1** | `kta_stock` Çekirdek Etiket/Parti Motoru & `rest-api` Taşıması | [Faz 1 Spec](./2026-11-21-faz1-kta-stock-relabeling-core-design.md) | [Faz 1 Plan](../plans/2026-11-21-faz1-kta-stock-relabeling-core.md) |
| **Faz 2** | İki Sekmeli Vue 3 + TypeScript Sayım Merkezi (`stock-reco-dashboard`) | [Faz 2 Spec](./2026-11-21-faz2-stock-reco-hub-vue-ts-design.md) | [Faz 2 Plan](../plans/2026-11-21-faz2-stock-reco-hub-vue-ts.md) |
| **Faz 3 (Bu Doküman)** | `Shopfloor Hub` Üretim Tedarik Alanından İade, İsteğe Bağlı Koli Bölme ve Dokümantasyon | `2026-11-21-faz3-shopfloor-supply-return-and-split-design.md` | [Faz 3 Plan](../plans/2026-11-21-faz3-shopfloor-supply-return-and-split.md) |

---

## 1. Amaç ve Kapsam

Faz 1 çekirdek motoru ve Faz 2 sayım yeniden etiketlemesi depoyu temizledikten sonra, üretim sahasından doğacak iki fiziksel hareketin de düzeni bozmaması için **`Shopfloor Hub → Hatlar Arası Transfer`** sekmesine eklenmesi gereken operasyonları tanımlar:

1. **Üretim Tedarik Alanından İade (`150x → 110 HAMMADDE`):**
   - Üretimde artan tam veya yarım makara/kutuların `Atıl Hat Stoğu` sekmesinden merkez hammadde depo raflarına (`110`) geri alınması ve depo kapısından içeri giren her kutunun tekil barkod + gerçek miktarla (`Depo Giriş Etiketi`) etiketlenmesi.
2. **Hatlar Arası Transferde İsteğe Bağlı Koli Bölme (`150x ↔ 150x`):**
   - Mevcut hızlı/sessiz `Material Transfer` varsayılanını bozmadan (`Açık Karşılama` ve iş emri tüketimleri sessiz kalır), kullanıcı istediğinde bölünen kısmi koliyi sıradaki `000x` kutu numarasına bölüp etiketleyebilmesi.
3. **Portal Dokümantasyonu, Geliştirici Kılavuzları ve Çeviri Senkronu:**
   - Faz 1–3 boyunca eklenen tüm yeni iş kuralları, `Stock Entry Type` türleri, sayım merkezi ve iade akışlarının `/docs/` portalına, `docs/*.md` rehberlerine ve `tr/en/de.csv` sözlüklerine işlenmesi.

---

## 2. İş Kuralları

### 2.1 Üretim Tedarik Alanından İade (`150x → 110` Yaprak Raf)

- **Kaynak Kısıtı:** Yalnızca `is_valid_production_warehouse(source_warehouse)` ile doğrulanan aktif yaprak üretim hatları (`150x`).
- **Hedef Kısıtı (`is_valid_raw_material_return_warehouse` & `get_raw_material_return_warehouses`):**
  - Şirket bağımsız kök çözümleme: Öncelikle `KTA MRP Settings` (`central_warehouse` / `raw_material_warehouse` varsa) veya seçili şirketin `Warehouse` ağacında normalize adı `"110 hammadde"` / `"110 raw material"` eşleşen kök grup (`lft`, `rgt`) bulunur; bu alt ağaçtaki tüm `is_group = 0`, `disabled = 0`, `is_rejected_warehouse = 0` ve `150x` üretim deposu olmayan yaprak raflar listelenir ve doğrulanır.
  - Üretim depoları (`150x`), grup depolar ve hurda/red depoları (`is_rejected_warehouse = 1`) hedef olarak kabul edilmez.
- **Rezervasyon Koruması:** İade edilen miktar kaynak hattaki serbest stoğu (`free_qty = max(0, actual_qty - reserved_qty_for_production)`) aşarsa mevcut **Öncelik Kaydırma / Rezerve Onayı (`allow_reserved_override = 1`)** gerekir; `actual_qty` asla aşılamaz.
- **Parti ve Bölme Yönlendirmesi (Depo Kapısında Sıfır Taviz Kuralı):**
  `execute_production_supply_return` arka planda kullanıcının özellikle seçtiği `batch_no` (varsa ve kaynak hatta yeterli bakiyesi mevcutsa; yoksa `resolve_lifo_batches`) ile kaynak partiyi çözer ve her kaynak `(item_code, batch_no)` tahsisini 3 şarta göre otomatik yönlendirir:
  1. Tahsis edilen parti standart KTA kutusu (`is_standard_kta_box_batch == True`), **ve**
  2. İade miktarı o partinin kaynak hattaki toplam bakiyesine eşit (yani kutunun kalan tamamı dönüyor, hatta/başka yerde bölünmüş parçası kalmıyor), **ve**
  3. Hedef `110` deposunda (ve diğer depolarda) bu iade sonrası aynı `batch_no` için başka açık bakiye kalmayacak
  → **Sonuç A (Tam Kalan Kutu):** `stock_entry_type = "Return from Production Supply"` (`purpose = "Material Transfer"`) belgesi oluşturulur ve submit edilir. `KTAStockEntry.on_submit` üzerinden etiketin `qty` ve `target_warehouse` bilgisi güncellenip Zebra'dan `Depo Giriş Etiketi` basılır.
  - Aksi her durumda *(kutu kısmi bölünüyorsa, başka yerde aynı partiden stok kalıyorsa veya parti `LEGACY`/boşsa)*:
  → **Sonuç B (Bölünmüş Kutu / LEGACY İade):** Her kaynak kutu için Faz 1 `create_package_split_repack` çağrılarak `stock_entry_type = "Package Split"` (`purpose = "Repack"`, `150x → 110 Raf`) belgesi oluşturulur; sıradaki `000x` (veya `LEGACY` ise yeni `{7Hane}0001`) kutu açılarak etiketi otomatik basılır, kaynak kutudaki kalan bakiye etiketi güncellenir.
- **Yanıt & Sonuç Özeti:** Hem oluşturulan `Return from Production Supply` hem `Package Split` belge numaralarını ve basılan etiket adedini tek yanıtta döner (`stock_entries`, `return_stock_entry`, `split_stock_entries`, `printed_labels`).

---

### 2.2 Hatlar Arası Transferde İsteğe Bağlı Koli Bölme (`150x ↔ 150x`)

- Mevcut `execute_line_transfer(...)` imzasına geriye uyumlu **`split_packages: int | bool = 0`** parametresi eklenir:
  - **`split_packages = 0` (Varsayılan — Değişmez):** `Açık Karşılama`, `MaterialStagingModal` ve normal hat transferleri mevcut hızlı/sessiz `Material Transfer` olarak kalır; otomatik etiket basılmaz.
  - **`split_packages = 1` (Kullanıcı Seçtiğinde):**
    - `Atıl Hat Stoğu` veya `Manuel Hat Transferi` modalında kullanıcı **"Yeni Koliye Böl ve Etiket Bas"** kutucuğunu işaretlerse çalışır.
    - LIFO tahsis edilen her parti için kısmi ayrılma veya `LEGACY` durumu varsa 1 kaynaklı `Package Split` (`1501 → 1502`) kesilir ve yeni `000x` kutunun `Depo Giriş Etiketi` otomatik basılır.
    - Tam kutu taşınıyorsa gereksiz `Repack` açılmaz; mevcut `Material Transfer` yapılır ve kutu etiketini güncellemek için `enqueue_print_labels_by_names` çağrılır.

---

### 2.3 Frontend Değişiklikleri (`erpnextkta/public/shopfloor-hub/`)

- **Satır Sınırı Korunması:** `LineIdleStockTable.vue` şu anda 440 satırdır. 500 satır sınırını aşmamak için iade formu ayrı bileşene alınır:
  1. **`ProductionSupplyReturnModal.vue` (`<Teleport to="body">`, yeni):**
     - `LineIdleStockTable.vue` içindeki **`Depoya İade`** aksiyonundan seçili satırlarla açılır.
     - Hedef `110` yaprak depo seçicisi (`get_raw_material_return_warehouses`), satır bazlı iade miktarı ve isteğe bağlı belirli `batch_no` seçimi, rezerve uyarısı banner'ı ve açıklama (`remarks`) içerir.
     - Onaylandığında `execute_shopfloor_supply_return` çağrılır; dönen `Stock Entry` belgeleri ve etiket bilgisi toast/banner olarak gösterilir. (`110` iadelerinde Bölüm 2.1'deki sıfır taviz kuralı her zaman otomatik çalışır.)
  2. **`LineIdleStockTable.vue` (Küçük Güncelleme — `< 500` satır kalır):**
     - Alt aksiyon çubuğuna **`↩️ Depoya İade (110)`** ikincil butonu + **yalnızca `150x ↔ 150x` (`Seçilenleri Gönder`)** yönünü etkileyen opsiyonel **"Yeni Koliye Böl ve Etiket Bas"** anahtarı eklenir.
  3. **`ManualLineTransferModal.vue` (`< 500` satır kalır):**
     - Alt alana isteğe bağlı **"Yeni Koliye Böl ve Etiket Bas"** checkbox'ı eklenir (`split_packages` payload'a geçirilir).
  4. **`LineTransfersPanel.vue` & `types.ts`:**
     - `RawMaterialReturnWarehouseOption`, `ProductionSupplyReturnPayloadItem` (`batch_no?: string | null` dahil), `ProductionSupplyReturnResponse`, `LineTransferPayloadItem` (`split_packages?: boolean`) tipleri eklenir; `ProductionSupplyReturnModal` bağlanır.

---

### 2.4 Zorunlu Dokümantasyon ve Çoklu Dil Senkronu (`docs-i18n`)

1. **Portal HTML Sayfaları (`erpnextkta/www/docs/`):**
   - `stok-lojistik.html`: Yeni `Return from Production Supply` (`Üretim Tedarik Alanından İade`), `Package Split` (`Koli Bölme`), `7 hane Lot + 4 hane Kutu` standardı ve `Sayım ve Etiket Merkezi` (Mod 1 / Mod 2, `LEGACY` dönüşümü) dokümante edilir.
   - `shopfloor-hub.html`: *Hatlar Arası Transfer* bölümüne `Üretim Tedarik Alanından İade (150x → 110)` ve isteğe bağlı `Yeni Koliye Böl ve Etiket Bas` akışları eklenir.
2. **Geliştirici Kılavuzları (`docs/`):**
   - `docs/kta_stok_lojistik_kilavuzu.md`: Teknik mimari, `rest-api` → `kta_stock/services` yolu ve `Stock Entry Type` kuralları güncellenir.
   - `docs/kta_shopfloor_hub_kilavuzu.md`: İade ve koli bölme API uçları ile yönlendirme kuralları eklenir.
3. **Çeviriler (`erpnextkta/translations/{tr,en,de}.csv`):**
   - Tüm yeni `Stock Entry Type` adları (`Return from Production Supply`, `Package Split`), Faz 2 Sayım Merkezi metinleri ve Faz 3 `Shopfloor Hub` metinleri tam cümle ve Title Case kurallarına uygun eklenir.
   - Hiçbir doküman veya örnekte gerçek firma unvanı ya da birim fiyat yer almaz.
