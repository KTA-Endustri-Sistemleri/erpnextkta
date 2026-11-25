# PDA İki Satırlı Üst Bar ve Koli Birleştirme (`Package Merge`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task, strictly routing each task to its owning specialist subagent in `.agents/AGENTS.md`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/pda` mobil başlığını iki satırlı adanmış alt bar (`.pda-subbar`) ile taşma yapmayacak hale getirmek ve `Stock` menüsünün 5. ekranı olarak aynı lot / karma lot uyarılı tam-kutu `Koli Birleştirme` (`Package Merge`) iş akışını uçtan uca hayata geçirmek.

**Architecture:** Arka uçta `setup.py` içine `"Package Merge"` (`Repack`) tipi eklenir; `relabeling_service.py` içinde `create_package_merge_repack()` tek ürün, yaprak depo, aynı/karma lot kuralları, ağırlıklı ortalama değerleme ve 3 katmanlı denetim izini uygular; `pda_service.py` içinde `PDA_MODULE_REGISTRY` `"merge"` ekranı ve `pda_package_merge` ucu tanımlanır; `KTAStockEntry.py` ise tek ürün koruması ve iptal/silmede kaynak kutu etiketlerini geri yükleyen rollback yaşam döngüsünü yönetir. Ön uçta `PdaHubApp.vue` üst barı sadeleştirilip `.pda-subbar` ayrılır ve `PackageMergeView.vue` çoklu kutu tarama + Karma Lot Uyarı Modalı ile geliştirilir.

**Tech Stack:** Frappe v15, Python 3.11+, Vue 3 (`<script setup lang="ts">`), TypeScript, esbuild (`bench build --app erpnextkta --production`), Vitest + `@vue/test-utils` + `jsdom`, `KTABaseTestCase`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-11-22-pda-subbar-and-package-merge-design.md`

---

## Global Constraints

- Koordinatör `erpnextkta/**` veya `docs/**` (`docs/superpowers/**` hariç) dosyalarını doğrudan düzenlemez; her görev ilgili uzman subagent'a (`docs-i18n`, `kta-stock`, `overrides-hooks`, `frontend-public`) `Workspace="inherit"` ile devredilir.
- Tüm `.vue` dosyaları **< 500 satır** kalır; `<script setup lang="ts">` içinde `const __ = (...args: any[]) => (window as any).__(...args);`, `<Teleport to="body">`, Light & `[data-theme="dark"]` tema uyumu, tam cümle bütünlüğü ve Title Case standartları korunur.
- `1 Kutu = 1 Parti` kuralı korunur; her kaynak kutunun kaynak deposundaki tam pozitif defter bakiyesi birleştirilir, grup/pasif depo ve onaysız GKK reddedilir.
- Karma lot / Legacy birleştirme (`is_mixed_lot = True`), `allow_mixed_lots=1` açıkça verilmeden backend'de `frappe.ValidationError` ile engellenir; etiket `quality_ref` alanı `"KARMA LOT"` alır.
- Çeviri sözlükleri (`erpnextkta/translations/{tr,en,de}.csv`) yalnızca **append-only (`0` silme)** güncellenir; gerçek tedarikçi/müşteri firma adı veya birim fiyat/maliyet bilgisi dokümanlarda ve test örneklerinde kesinlikle kullanılmaz.
- Frontend derlemesi yalnızca `bench build --app erpnextkta --production` ile yapılır; Python dosyaları `ruff check` ve `ruff format --check` ile doğrulanır.

---

## Review Focus

1. **Aynı lot sanılan farklı `item_code` veya aynı `(batch_no, warehouse)` kutusunun iki kez okutulması:** `create_package_merge_repack` ve `pda_package_merge`, farklı ürün kodu veya mükerrer `(batch_no, warehouse)` girdilerini `ValidationError` ile reddetmelidir (*Task 2*).
2. **Karma lot / Legacy birleştirmenin `allow_mixed_lots=0` iken arka kapıdan geçmesi veya onaylı karma lot etiketinde `"KARMA LOT"` yazmaması:** Backend `allow_mixed_lots != 1` iken reddetmeli, `allow_mixed_lots=1` iken `Batch.description`, `Stock Entry.remarks` ve hedef `KTA Stock Label.quality_ref == "KARMA LOT"` oluşturmalıdır (*Task 2*).
3. **Karma lot `Package Merge` belgesi silinirken (`se.delete()`) hedef `Batch.reference_name == se.name` yüzünden `LinkExistsError` patlaması veya kaynak kutu etiketinin geri gelmemesi:** `KTAStockEntry.on_cancel()` / `on_trash()` referans bağını temizlemeli, hedef etiketi silip hedef partiyi pasife almalı ve bakiye dönen kaynak kutular için `KTA Stock Label` kaydını geri yüklemelidir (*Task 3*).
4. **Dar (`360px–420px`) PDA ekranında `.pda-topbar` taşması ve ana ekranda `.pda-subbar` görünmesi:** `.pda-topbar` yalnızca `[☰ Menü]` + marka ve sağ durum öğelerini taşımalı; `.pda-subbar` yalnız alt ekrandayken veya çoklu kategori içindeyken görünmelidir (*Task 4*).
5. **Karma lot birleştirmede kullanıcının Uyarı Modalını kapatıp vazgeçmesi veya onaysız GKK kutusunun birleştirilmesi:** Uyarı modalı iptalinde API çağrısı atılmamalı; GKK onaysız kutuda `validate_batch_qi_on_transfer` birleştirmeyi atomik reddetmelidir (*Task 2 & Task 4*).

---

## File Structure Overview

- **Tasarım & Plan (`docs-i18n`):**
  - `docs/superpowers/specs/2026-11-22-pda-subbar-and-package-merge-design.md`
  - `docs/superpowers/plans/2026-11-22-pda-subbar-and-package-merge.md`
- **Backend Kurulum, Birleştirme & Etiketleme (`kta-stock`):**
  - `erpnextkta/kta_stock/setup.py` — `STOCK_ENTRY_TYPES` içine `"Package Merge"` eklenmesi.
  - `erpnextkta/kta_stock/services/relabeling_service.py` — `create_package_merge_repack()` ve yardımcı lot/değerleme/audit yardımcıları.
  - `erpnextkta/kta_stock/services/pda_service.py` — `PDA_MODULE_REGISTRY` `"merge"` ekranı ve `pda_package_merge()` RPC ucu.
  - `erpnextkta/kta_stock/label_manager.py` — karma lot `Package Merge` için hedef etiket `quality_ref = "KARMA LOT"` koruması.
  - `erpnextkta/kta_stock/tests/{test_relabeling_service,test_pda_service}.py` — same-lot, mixed-lot, GKK, lock ve tek-sefer baskı testleri.
- **Document Lifecycle & Overrides (`overrides-hooks`):**
  - `erpnextkta/overrides/KTAStockEntry.py` — `"Package Merge"` tek ürün doğrulaması, `on_cancel` / `on_trash` `LinkExistsError` koruması ve kaynak kutu etiketi geri yükleme.
  - `erpnextkta/tests/test_stock_entry_labeling.py` — `Package Merge` tek ürün, iptal ve silme yaşam döngüsü testleri.
- **Frontend SPA (`frontend-public`):**
  - `erpnextkta/public/pda-hub/types.ts` — `"merge"` ekran anahtarı, `PackageMergeSourceInput`, `PackageMergeResponse`.
  - `erpnextkta/public/pda-hub/PdaHubApp.vue` — sadeleştirilmiş `.pda-topbar`, adanmış `.pda-subbar` ve `PackageMergeView` yönlendirmesi.
  - `erpnextkta/public/pda-hub/components/LauncherHome.vue` — `accent-purple` kart kenarlık stili.
  - `erpnextkta/public/pda-hub/views/PackageMergeView.vue` — çoklu kutu tarama, aynı/karma lot algılama, Karma Lot Uyarı Modalı ve sonuç ekranı.
  - `erpnextkta/public/pda-hub/__tests__/{PdaHubApp,WarehouseModules}.spec.ts` — subbar, navigasyon ve merge modal Vitest testleri.
- **Dokümantasyon & Çeviri (`docs-i18n`):**
  - `erpnextkta/www/docs/stok-lojistik.html` & `docs/kta_stok_lojistik_kilavuzu.md`
  - `erpnextkta/translations/{tr,en,de}.csv`

---

### Task 1: Design Spec & Implementation Plan Oluşturma (`docs-i18n`)

**Subagent:** `docs-i18n`  
**Files:**
- Create: `docs/superpowers/specs/2026-11-22-pda-subbar-and-package-merge-design.md`
- Create: `docs/superpowers/plans/2026-11-22-pda-subbar-and-package-merge.md`

- [x] **Step 1: Author Design Spec (`2026-11-22-pda-subbar-and-package-merge-design.md`)**

Two-Row `.pda-topbar` + `.pda-subbar` tasarımını ve `Stock` altında 5. ekran `Koli Birleştirme` (`Package Merge`: same-lot vs mixed-lot, 3-katmanlı audit trail, `KTAStockEntry` rollback) mimarisini sıfır ticari veriyle yaz.

- [x] **Step 2: Author Implementation Plan (`2026-11-22-pda-subbar-and-package-merge.md`)**

Task 1–6 adımlarını TDD, net `Interfaces` blokları ve kesin doğrulama komutlarıyla oluştur.

- [x] **Step 3: Verify Spec & Plan paths and privacy compliance**

Run: `git status --short -- docs/superpowers/`  
Expected: İki yeni dosya untracked/hazır ve ticari veri taraması `0` eşleşme.

---

### Task 2: Backend `Package Merge` Kurulumu, `create_package_merge_repack`, `pda_package_merge` ve Birim Testleri

**Subagent:** `kta-stock`  
**Files:**
- Modify: `erpnextkta/kta_stock/setup.py:19-42` (`STOCK_ENTRY_TYPES`)
- Modify: `erpnextkta/kta_stock/services/relabeling_service.py` (`create_package_merge_repack`)
- Modify: `erpnextkta/kta_stock/label_manager.py:1045-1075` (`print_stock_entry_labels`)
- Modify: `erpnextkta/kta_stock/services/pda_service.py:25-67` (`PDA_MODULE_REGISTRY`), `pda_package_merge()`
- Modify (Tests): `erpnextkta/kta_stock/tests/test_relabeling_service.py`, `erpnextkta/kta_stock/tests/test_pda_service.py`

**Interfaces:**
- Consumes: `resolve_warehouse_barcode`, `get_batch_ledger_balances`, `generate_new_base_lot`, `allocate_next_box_batches`, `sync_batch_label_to_ledger_balance`, `_require_pda_screen_access("merge")`
- Produces:
  - `Stock Entry Type = "Package Merge"` (`purpose="Repack"`, `is_standard=0`, `custom_etiket_basilabilir=1`, `custom_etiket_sablonu="Depo Giriş Etiketi"`)
  - `PDA_MODULE_REGISTRY[0]["items"]` öğesi `key="merge"` (`"split"` sonrası, `"transfer"` öncesi)
  - `create_package_merge_repack(item_code: str, sources: list[dict], target_warehouse: str | None = None, allow_mixed_lots: int | bool = 0, remarks: str | None = None, posting_date: str | None = None, ignore_reco_lock: bool = False) -> dict` (`stock_entry`, `target_batch`, `base_lot`, `total_qty`, `target_warehouse`, `is_mixed_lot`, `sources`)
  - `pda_package_merge(item_code: str, sources: list[dict] | str, target_warehouse_barcode: str | None = None, allow_mixed_lots: int = 0) -> dict` (yukarıdakilere ek `ok: True`, `quality_ref`, `owner`, `label_name`)

- [x] **Step 1: Write failing tests (`test_relabeling_service.py`, `test_pda_service.py`)**

Aşağıdaki senaryoları yaz:
1. `test_setup_creates_package_merge_stock_entry_type`: `"Package Merge"` tipinin `purpose == "Repack"`, `is_standard == 0`, `custom_etiket_basilabilir == 1` ve `custom_etiket_sablonu == "Depo Giriş Etiketi"` ile oluştuğunu doğrular.
2. `test_create_package_merge_repack_same_base_lot_inherits_meta_and_min_expiry`: Aynı 7 haneli lot altındaki 2 kutu (`ABC12340001` + `ABC12340002`) birleşince `ABC12340003` partisi oluşur, `is_mixed_lot == False`, PR/GKK meta verisi + `min(expiry_date)` devralınır, `Stock Entry.remarks` ve `Batch.description` dolar.
3. `test_create_package_merge_repack_mixed_lots_requires_ack_and_sets_karma_lot`: Farklı 7 haneli lot veya Legacy kutularda `allow_mixed_lots=0` iken `frappe.ValidationError` fırlatır; `allow_mixed_lots=1` ile yeni `7+4` karma lot üretir, `Batch.reference_doctype == "Stock Entry"`, `Batch.reference_name == se.name`, `KTA Stock Label.quality_ref == "KARMA LOT"` basar ve ağırlıklı ortalama değerlemeyi korur.
4. `test_pda_package_merge_validates_duplicates_items_qi_lock_and_prints_once`: Yinelenen kutu / farklı `item_code` / `< 2` kutu / onaysız GKK / Taslak `Stock Reconciliation` kilidi / yetkisiz ofis `Stock User` durumlarını reddeder; saf `Website User` (`KTA PDA Stock User`) ile başarılı birleştirmede `Stock Entry.owner == operator_user`, hedef etiket yalnızca 1 kez basılır ve kaynak kutu etiketleri sıfır bakiyede temizlenir.

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
```
Expected: FAIL (`ImportError: cannot import name 'create_package_merge_repack'` / `"Package Merge"` missing).

- [x] **Step 3: Implement `Package Merge` type, `create_package_merge_repack`, label handling & `pda_package_merge`**

1. `erpnextkta/kta_stock/setup.py`: `STOCK_ENTRY_TYPES` içine `"Package Merge"` kaydını ekle.
2. `erpnextkta/kta_stock/services/relabeling_service.py`: `create_package_merge_repack(...)` ve modüler yardımcıları (`_normalize_merge_sources`, `_analyze_merge_lots`, `_build_merge_audit_remarks`, `_resolve_weighted_merge_rate`) yaz; ağırlıklı ortalama oranı hesapla, `Stock Entry` (`stock_entry_type="Package Merge"`, `purpose="Repack"`) submit et, `Batch.description` (ve karma lot ise `reference_doctype="Stock Entry", reference_name=se.name`) güncelle ve kaynak kutuları `sync_batch_label_to_ledger_balance` ile senkronize et.
3. `erpnextkta/kta_stock/label_manager.py`: `print_stock_entry_labels` içinde `doc.stock_entry_type == "Package Merge"` ve karma lot (ör. `doc.remarks` `[KARMA LOT BİRLEŞTİRME]` başlığı veya `Batch.reference_name == doc.name`) durumunda hedef `upsert_box_label` çağrısına `quality_ref="KARMA LOT"` geçirerek etiket basımında `"KARMA LOT"` yazdır.
4. `erpnextkta/kta_stock/services/pda_service.py`: `PDA_MODULE_REGISTRY[0]["items"]` içinde `"split"` sonrasına `merge` ekranını ekle (`accent="accent-purple"`); `@frappe.whitelist(methods=["POST"]) def pda_package_merge(...)` yaz (`_require_pda_screen_access("merge")`, `target_warehouse_barcode` çözümü, `create_package_merge_repack` çağrısı).

- [x] **Step 4: Run tests & lint checks**

Run:
```bash
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
/home/frappe/frappe-bench/env/bin/ruff check --ignore EXE002 erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/services/relabeling_service.py erpnextkta/kta_stock/label_manager.py erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_relabeling_service.py erpnextkta/kta_stock/tests/test_pda_service.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/services/relabeling_service.py erpnextkta/kta_stock/label_manager.py erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_relabeling_service.py erpnextkta/kta_stock/tests/test_pda_service.py
```
Expected: PASS.

---

### Task 3: `KTAStockEntry` Tek Ürün Koruması & İptal/Silme Etiket Geri Alma + Yaşam Döngüsü Testleri

**Subagent:** `overrides-hooks`  
**Files:**
- Modify: `erpnextkta/overrides/KTAStockEntry.py:222-480`
- Modify (Tests): `erpnextkta/tests/test_stock_entry_labeling.py`

**Interfaces:**
- Consumes: `upsert_box_label`, `sync_batch_label_to_ledger_balance`, `delete_labels_with_print_logs`, `get_batch_ledger_balances` (`relabeling_service.py`)
- Produces:
  - `KTAStockEntry._validate_single_item_relabeling()` (`Package Split` ve `Package Merge` tek ürün kontrolü; geriye dönük `_validate_single_item_package_split` uyumlu)
  - `KTAStockEntry.on_cancel()` & `on_trash()`: `Package Merge` hedef etiketi siler, boş hedef partiyi pasife alır, `Batch.reference_name == self.name` bağını temizleyerek `LinkExistsError`'ı önler ve bakiye dönen kaynak kutuların `KTA Stock Label` kayıtlarını geri yükler.

- [x] **Step 1: Write failing lifecycle tests (`test_stock_entry_labeling.py`)**

1. `test_package_merge_rejects_multiple_items_in_stock_entry`: `stock_entry_type == "Package Merge"` belgesinde 2 farklı `item_code` satırı varsa `validate()` sırasında `ValidationError` fırlatıldığını doğrular.
2. `test_package_merge_cancel_and_trash_restores_source_labels_without_link_error`: Karma lot `Package Merge` belgesi submit edildikten sonra `se.cancel()` ve ardından `se.delete()` hatasız (`LinkExistsError` olmadan) tamamlanır; hedef etiket silinir, hedef `Batch` `disabled == 1, batch_qty == 0` olur ve tüketilmiş kaynak kutuların `KTA Stock Label` kayıtları pozitif defter bakiyeleriyle geri gelir.

- [x] **Step 2: Run test to verify it fails**

Run: `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_labeling`  
Expected: FAIL (`LinkExistsError` veya kaynak kutu etiketi geri gelmiyor / multi-item engellenmiyor).

- [x] **Step 3: Implement `KTAStockEntry` single-item guard & rollback cleanup**

1. `erpnextkta/overrides/KTAStockEntry.py`:
   - `_validate_single_item_package_split` kontrolünü `("Package Split", "Package Merge")` için genelleştir.
   - `relabeling_types` içine `"Package Merge"` ekle; `on_cancel` ve `on_trash` içinde `_clear_batch_stock_entry_links(target_pairs)` ile `Batch.reference_doctype == "Stock Entry"` ve `Batch.reference_name == self.name` bağlarını temizle.
   - `_sync_relabeling_on_cleanup` içinde kaynak (`touched_pairs - target_pairs`) partilerin defter bakiyesi `> _EPSILON` olup mevcut `KTA Stock Label` kaydı silinmişse `upsert_box_label(...)` ile yeniden oluştur (`target_warehouse` en yüksek bakiye deposuyla).

- [x] **Step 4: Run tests & lint checks**

Run:
```bash
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_labeling
/home/frappe/frappe-bench/env/bin/ruff check --ignore EXE002 erpnextkta/overrides/KTAStockEntry.py erpnextkta/tests/test_stock_entry_labeling.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/overrides/KTAStockEntry.py erpnextkta/tests/test_stock_entry_labeling.py
```
Expected: PASS.

---

### Task 4: Frontend İki Satırlı `.pda-subbar`, `PackageMergeView.vue`, Karma Lot Uyarı Modalı ve Vitest Testleri

**Subagent:** `frontend-public`  
**Files:**
- Modify: `erpnextkta/public/pda-hub/types.ts`
- Modify: `erpnextkta/public/pda-hub/PdaHubApp.vue`
- Modify: `erpnextkta/public/pda-hub/components/LauncherHome.vue` (`accent-purple` CSS)
- Create: `erpnextkta/public/pda-hub/views/PackageMergeView.vue` (`< 500` satır)
- Modify (Tests): `erpnextkta/public/pda-hub/__tests__/PdaHubApp.spec.ts`, `erpnextkta/public/pda-hub/__tests__/WarehouseModules.spec.ts`

**Interfaces:**
- Consumes: `pda_scan_box`, `pda_package_merge` (`pda_service.py`)
- Produces:
  - `types.ts`: `PdaScreenKey = "picking" | "split" | "merge" | "transfer" | "lookup"`, `PackageMergeSourceInput`, `PackageMergeResponse`
  - `PdaHubApp.vue`: İki satırlı `.pda-topbar` (geri/breadcrumb yok) + `.pda-subbar` (`[data-testid="pda-subbar"]`, `[data-testid="topbar-back-btn"]`, `[data-testid="topbar-breadcrumb"]`)
  - `PackageMergeView.vue`: Çoklu kutu tarama, toplam miktar/SKT önizleme, opsiyonel hedef raf barkodu, Karma Lot Uyarı Modalı (`<Teleport to="body">`) ve sonuç kartı

- [x] **Step 1: Write failing Vitest specs (`PdaHubApp.spec.ts`, `WarehouseModules.spec.ts`)**

1. `PdaHubApp.spec.ts`:
   - Ana açılışta `.pda-subbar` görünmez; `.pda-topbar` içinde `[data-testid="topbar-back-btn"]` ve `[data-testid="topbar-breadcrumb"]` yer almaz.
   - Bir ekrana (`merge` veya `split`) geçildiğinde `[data-testid="pda-subbar"]` görünür, içinde `[data-testid="topbar-back-btn"]` ve `[data-testid="topbar-breadcrumb"]` (`"Stock › Koli Birleştirme"`) yer alır; geri tıklandığında ana menüye döner ve subbar kapanır.
   - Çoklu kategoride kategori seçilince subbar `"Ana Modüller › Stock"` gösterir.
2. `WarehouseModules.spec.ts`:
   - Aynı lot iki kutu (`ABC12340001`, `ABC12340002`) tarandığında uyarı modalı açılmadan doğrudan `pda_package_merge(..., allow_mixed_lots: 0)` çağrılır.
   - Farklı lot iki kutu (`ABC12340001`, `XYZ56780003`) tarandığında birleştirme butonuna basınca `[data-testid="mixed-lot-confirm-modal"]` açılır; iptal edilirse API çağrılmaz, onaylanırsa `allow_mixed_lots: 1` ile `pda_package_merge` çağrılır ve sonuçta `"KARMA LOT"` etiketi / yeni kutu gösterilir.
   - Farklı `item_code` veya aynı kutunun ikinci kez okutulmasında hata mesajı gösterilir.

- [x] **Step 2: Run Vitest to verify it fails**

Run: `npm --prefix erpnextkta/public/pda-hub test`  
Expected: FAIL.

- [x] **Step 3: Implement `types.ts`, two-row `PdaHubApp.vue`, and `PackageMergeView.vue`**

1. `erpnextkta/public/pda-hub/types.ts`: `"merge"` ekranını `PdaScreenKey` içine ekle; `PackageMergeSourceInput`, `PackageMergeResponse` tiplerini tanımla.
2. `erpnextkta/public/pda-hub/PdaHubApp.vue`:
   - `.pda-topbar` içindeki `[data-testid="topbar-back-btn"]` ve `[data-testid="topbar-breadcrumb"]` öğelerini çıkarıp `.pda-topbar` hemen altına adanmış `<div v-if="showSubbar" class="pda-subbar" data-testid="pda-subbar">` satırını ekle (`handleSubbarBack()` ekle; `PackageMergeView` bağla; `activeModuleTitle` içine `case "merge": return __("Koli Birleştirme")` ekle).
   - `LauncherHome` içinde `accent-purple` CSS sınıfını/desteğini (varsa `LauncherHome.vue` stil bloğunda mor sol kenarlık `#9333ea`) ekle.
3. `erpnextkta/public/pda-hub/views/PackageMergeView.vue`: `< 500` satır, `const __`, `<Teleport to="body">` Karma Lot Uyarı Modalı, Light & `[data-theme="dark"]` tema desteği ve Title Case etiketlerle geliştir.

- [x] **Step 4: Run Vitest, line-count check, and production build**

Run:
```bash
npm --prefix erpnextkta/public/pda-hub test
wc -l erpnextkta/public/pda-hub/PdaHubApp.vue erpnextkta/public/pda-hub/views/PackageMergeView.vue
bench build --app erpnextkta --production
```
Expected: Tüm Vitest testleri PASS, her `.vue` dosyası `< 500` satır, `bench build` 0 hata.

---

### Task 5: Portal Dokümantasyonu (`/docs/stok-lojistik`), Geliştirici Kılavuzu ve Append-Only TR/EN/DE Çeviriler (`docs-i18n`)

**Subagent:** `docs-i18n`  
**Files:**
- Modify (append-only): `erpnextkta/translations/{tr,en,de}.csv`
- Modify: `erpnextkta/www/docs/stok-lojistik.html`
- Modify: `docs/kta_stok_lojistik_kilavuzu.md`

- [x] **Step 1: Extract new strings & append-only sync `tr.csv`, `en.csv`, `de.csv`**

`setup.py`, `relabeling_service.py`, `pda_service.py`, `label_manager.py`, `KTAStockEntry.py`, `PdaHubApp.vue`, `PackageMergeView.vue` ve `PDA_MODULE_REGISTRY` içindeki tüm yeni `_()` / `__()` dizgelerini Title Case ve tam cümle standardıyla append-only (`0` silme) ekle; `git diff --numstat` ve `csv.reader` ile doğrula.

- [x] **Step 2: Synchronize `erpnextkta/www/docs/stok-lojistik.html` & `docs/kta_stok_lojistik_kilavuzu.md`**

İki satırlı `.pda-topbar` + `.pda-subbar` navigasyon yapısını ve 5. ekran **Koli Birleştirme (`Package Merge`)** (aynı lot vs karma lot uyarı akışı, `"KARMA LOT"`, ağırlıklı ortalama değerleme, 3 katmanlı audit trail, `KTAStockEntry` iptal/silme geri alma) kurallarını ticari/gizli veri olmadan her iki dokümana işle.

- [x] **Step 3: Validate HTML tags, privacy check, and CSV coverage**

Run: CSV `0`-deletion check (`git diff --numstat -- erpnextkta/translations/`), `csv.reader`, HTML tag balance ve gizlilik taraması.  
Expected: `0` silme, `0` eksik anahtar, `0` etiket/gizlilik hatası.

---

### Task 6: Yerel Kalite Kapısı, Tek Commit, CI Doğrulaması (`PR #185`) ve Resmi PR Açıklaması Senkronizasyonu

**Subagents:** Koordinatör & `docs-i18n`  
**Files:**
- Read-only / Output: `.github/PULL_REQUEST_TEMPLATE.md`

- [x] **Step 1: Run full Local Quality Gate**

Run:
```bash
bench --site development.localhost migrate
bench build --app erpnextkta --production
/home/frappe/frappe-bench/env/bin/ruff check --ignore EXE002 <all_modified_py_files>
/home/frappe/frappe-bench/env/bin/ruff format --check <all_modified_py_files>
npm --prefix erpnextkta/public/pda-hub test
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_labeling
```
Expected: Tüm migrate, build, lint, Vitest ve Frappe testleri 0 hata ile geçer.

- [x] **Step 2: Create single clean Conventional Commit & verify CI on `PR #185`**

Conventional Commit formatında (`<= 100` karakter satır sınırı) değişiklikleri commit et, push sonrası `PR #185` CI durumunu doğrula.

- [x] **Step 3: Sync Official PR Description (`.github/PULL_REQUEST_TEMPLATE.md`)**

`docs-i18n` / Koordinatör tarafından `.github/PULL_REQUEST_TEMPLATE.md` şablonuna uygun, gizli/ticari veri içermeyen güncel PR açıklamasını hazırla.

---

## Self-Review Checklist

1. **Spec coverage:** İki satırlı `.pda-topbar` + `.pda-subbar` (Task 4), `Package Merge` tipi + `create_package_merge_repack` + `pda_package_merge` + `"KARMA LOT"` etiket basımı (Task 2), `KTAStockEntry` tek ürün koruması ve iptal/silmede kaynak kutu etiketi geri alma + `LinkExistsError` koruması (Task 3), `PackageMergeView.vue` + Karma Lot Uyarı Modalı (Task 4), Dokümantasyon + Append-Only TR/EN/DE (Task 5), Kalite Kapısı + Commit + PR #185 senkronizasyonu (Task 6). Boşluk yok.
2. **Type & Signature consistency:** `create_package_merge_repack`, `pda_package_merge`, `PackageMergeSourceInput`, `PackageMergeResponse`, `pda-subbar`, `topbar-back-btn`, `topbar-breadcrumb`, `mixed-lot-confirm-modal` ve `Package Merge` adları spec ve tüm görevlerde birebir aynıdır.
3. **Review Focus coverage:** 5 kritik uç durumun tamamı (mükerrer/farklı ürün reddi, karma lot onaysız red + `"KARMA LOT"` etiketi, iptal/silmede `LinkExistsError` & kaynak etiket geri yükleme, dar ekran taşma/subbar görünürlük kuralları, modal iptali & GKK kilidi) Task 2–4 testleriyle sabitlenmiştir.
