# PDA İki Satırlı Üst Bar ve Koli Birleştirme (Package Merge) Mimarisi (Design Spec)

**Tarih:** 2026-11-22  
**Durum:** Implemented — Kalite Kapısı Doğrulandı  
**Önkoşul:** [KTA PDA Depo Merkezi Tasarım Dokümanı](./2026-11-21-pda-warehouse-hub-design.md), [PDA Rol Bazlı Menü ve Operatör Yetkilendirme Mimarisi](./2026-11-22-pda-role-based-menu-design.md)  
**Kapsam:** `erpnextkta/kta_stock/setup.py`, `erpnextkta/kta_stock/services/relabeling_service.py`, `erpnextkta/kta_stock/services/pda_service.py`, `erpnextkta/kta_stock/label_manager.py`, `erpnextkta/overrides/KTAStockEntry.py`, `erpnextkta/public/pda-hub/**`, `erpnextkta/translations/{tr,en,de}.csv`, `erpnextkta/www/docs/stok-lojistik.html`, `docs/kta_stok_lojistik_kilavuzu.md`

---

## 1. Feature A: İki Satırlı PDA Üst Barı ve Adanmış Alt Bar (`PdaHubApp.vue`)

### 1.1 Problem
Dar mobil el terminali ekranlarında (`360px–420px`) tek satırlı `.pda-topbar` içinde hem `☰ Menü`, hem `← Geri`, hem uzun dinamik breadcrumb (`Stock › Hat İkmal Toplama`), hem operatör rozeti, hem geri sayım sayacı hem de `Devret ↩` butonu bulunduğunda öğeler yatayda sıkışmakta ve breadcrumb/butonlar taşmaktadır.

### 1.2 Tasarım
1. **Satır 1 (`.pda-topbar` — Sabit Sistem Çubuğu):**
   - **Sol grup:** Yalnızca `[☰ Menü]` butonu (`data-testid="topbar-menu-btn"`) ve statik marka etiketi `<span class="pda-brand">📱 {{ __("KTA PDA") }}</span>` yer alır. `.pda-topbar` içinde **hiç geri butonu (`←`) ve hiç dinamik breadcrumb bulunmaz**.
   - **Sağ grup:** `[👤 Operatör]` rozeti (`@media (max-width: 420px)` gizlenir), `[04:59]` (`data-testid="inactivity-timer"`) ve `[Devret ↩]` (`data-testid="handover-btn"`) butonları yer alır.
2. **Satır 2 (`.pda-subbar`, `data-testid="pda-subbar"` — Adanmış Bağlamsal Alt Bar):**
   - `.pda-topbar` hemen altında yapışkan (`position: sticky`) olarak **yalnızca** şu koşullardan biri sağlandığında render edilir:
     - `activeModule !== "home"`, **VEYA**
     - `menuCategories.length > 1 && selectedCategoryKey !== null` (çoklu kategori ortamında bir kategorinin içine girilmişse).
   - **İçerik:**
     - Sol tarafta `[← Geri]` butonu (`data-testid="topbar-back-btn"`): alt ekrandayken (`activeModule !== "home"`) ana ekrana (`activeModule = "home"`) döner; çoklu kategori içindeyken (`activeModule === "home"`) seçili kategoriyi temizleyerek (`selectedCategoryKey = null`) ana modüllere döner.
     - Yanında tam esneyebilen (`flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap`) breadcrumb (`data-testid="topbar-breadcrumb"`) gösterilir:
       - Çoklu kategoride bir kategori içindeyken: `Ana Modüller › Stock`
       - Bir alt ekrandayken (ör. `merge`): `Stock › Koli Birleştirme`
   - Ana açılış görünümündeyken (`activeModule === "home"` ve tek kategoride veya kategori seçim ekranında) `.pda-subbar` gizlenir; böylece ekran alanı korunur.

---

## 2. Feature B: `Stock` Altında 5. Ekran — `Koli Birleştirme` (`Package Merge`, Yaklaşım A)

### 2.1 `Stock Entry Type` & Merkezi Kayıt Defteri
1. **`Stock Entry Type = "Package Merge"` (`erpnextkta/kta_stock/setup.py`):**
   - `STOCK_ENTRY_TYPES` listesine idempotent olarak eklenir (`setup()` / `after_migrate`):
     - `name`: `"Package Merge"`
     - `purpose`: `"Repack"`
     - `is_standard`: `0`
     - `custom_etiket_basilabilir`: `1`
     - `custom_etiket_sablonu`: `"Depo Giriş Etiketi"`
2. **`PDA_MODULE_REGISTRY` (`erpnextkta/kta_stock/services/pda_service.py`):**
   - `PDA_MODULE_REGISTRY[0]["items"]` içinde `"split"` öğesinin **hemen ardından** 5. stok ekranı olarak kaydedilir:
     - `key`: `"merge"`
     - `title`: `"Koli Birleştirme"`
     - `subtitle`: `"Mevcut kolileri tek partide birleştir ve etiket bas"`
     - `icon`: `"🔗"`
     - `accent`: `"accent-purple"`
     - `allowed_roles`: `PDA_STOCK_ROLES` (`{"KTA PDA Stock User", "Stock Manager", "System Manager"}`)
   - `KTA PDA Stock User` rolü mevcut 8 DocType `Custom DocPerm` izinleriyle (`Stock Entry`, `Serial and Batch Bundle`, `Batch`, `Stock Ledger Entry`, `Item`, `Warehouse`, `KTA Stock Label`, `KTA Line Replenishment Order`) bu akışı ek izin gerektirmeden `Website User` olarak çalıştırır.

### 2.2 Birleştirme Kuralları ve Doğrulamalar (`create_package_merge_repack` & `pda_package_merge`)
- **En Az 2 Farklı Kutu & Aynı Malzeme:** En az `2` adet benzersiz `(batch_no, warehouse)` kutu girdisi zorunludur (`len < 2` veya yinelenen `(batch_no, warehouse)` çifti `frappe.ValidationError` ile reddedilir). Tüm kaynak kutuların **aynı `item_code`** değerine sahip olması gerekir; farklı `item_code` tarandığında anında reddedilir.
- **1 Kutu = 1 Parti (Tam Kutu Tüketimi):** Her kaynak kutunun ilgili kaynak deposundaki **tüm pozitif defter bakiyesi** (`get_batch_ledger_balances`) tüketilir. Kaynak deposunda pozitif bakiye yoksa işlem reddedilir.
- **Depo, Şirket & Kalite Kilitleri:**
  - Tüm kaynak depolar ve hedef depo aktif (`disabled = 0`) yaprak (`is_group = 0`) depo olmalı ve aynı `company` altında bulunmalıdır.
  - Opsiyonel `target_warehouse_barcode` verilmişse `resolve_warehouse_barcode(..., company=company)` ile çözülür; verilmemişse ilk kaynak kutunun deposu hedef depo kabul edilir.
  - Taslak `Stock Reconciliation` depo kilidi (`validate_stock_entry_warehouse_lock`, `ignore_reco_lock=False`) ve GKK onayı (`validate_batch_qi_on_transfer`, onaysız GKK'lı kutu engellenir) doğal olarak uygulanır.

### 2.3 Aynı Ana Lot vs. Karma Lot / Legacy Kuralı
1. **Aynı Ana Lot (`is_mixed_lot = False`):**
   - Tüm kaynak kutular standart `7+4` formatındadır ve 7 karakterlik lot ön ekleri (`extract_base_lot`) birebir aynıdır (ör. `ABC12340002` + `ABC12340005`).
   - Uyarı onayı gerekmez (`allow_mixed_lots` gerekmez).
   - Aynı `base_lot` altında ardışık bir sonraki `7+4` kutu partisi tahsis edilir (`ABC12340002` + `ABC12340005` → `ABC12340006`).
   - Orijinal `Purchase Receipt` / `Work Order` meta verileri (`reference_doctype`, `reference_name`, `supplier`, `manufacturing_date`), `quality_ref` (GKK), `supplier_delivery_note` ve kaynak kutuların en erken `min(expiry_date)` tarihi devralınır.
2. **Karma Lot / Legacy Parti (`is_mixed_lot = True`):**
   - Kaynak kutular farklı 7 haneli lot ön eklerine sahipse (ör. `ABC12340001` + `XYZ56780003`) **veya** en az biri standart `7+4` formatında değilse (Legacy) `is_mixed_lot = True` olur.
   - **Backend Zorunluluğu:** `allow_mixed_lots = 1` açıkça gönderilmedikçe çapraz/karma lot birleştirme `frappe.ValidationError` ile reddedilir.
   - **Frontend Karma Lot Uyarı Modalı (`PackageMergeView.vue`, `<Teleport to="body">`):** Kullanıcı onay butonuna bastığında karma lot tespit edilmişse gönderim öncesi modal açılır ve kullanıcıya 6 sonucu net biçimde bildirir:
     1. Tekil Mal Kabul (PR) / GKK lot soy kütüğü kaybedilir,
     2. Yeni `7+4` karma ana lot ve kutu partisi üretilir (`generate_new_base_lot` + `allocate_next_box_batches`),
     3. Kaynak kutular arasındaki en erken son kullanma tarihi (`min(expiry_date)`) devralınır,
     4. Kaynak kalemlerin ağırlıklı ortalama değerleme maliyeti (`weighted-average valuation rate`) hedef partiye uygulanır,
     5. Yeni kutu etiketinin `quality_ref` alanına **`"KARMA LOT"`** basılır,
     6. Tüm kaynak kutu dökümü `Stock Entry.remarks` ve hedef `Batch.description` alanlarına işlenir.
   - Kullanıcı **"Riskleri Kabul Ediyorum, Birleştir"** onayı verdiğinde `allow_mixed_lots = 1` ile API çağrısı yapılır.

### 2.4 Üç Katmanlı Denetim İzi ve Etiket Basımı
1. **Katman 1 — Belge Tipi:** `Stock Entry Type = "Package Merge"` (`purpose = "Repack"`).
2. **Katman 2 — `Stock Entry.remarks`:**
   - Aynı lot: `[KOLİ BİRLEŞTİRME] Kaynaklar: ABC12340002 (40 Nos @ Depo A), ABC12340005 (60 Nos @ Depo A) -> Hedef: ABC12340006 (100 Nos @ Depo A)`
   - Karma lot: `[KARMA LOT BİRLEŞTİRME] Kaynaklar: ABC12340001 (40 Nos @ Depo A), XYZ56780003 (60 Nos @ Depo B) -> Hedef: NEWLOT10001 (100 Nos @ Depo A)`
3. **Katman 3 — Hedef `Batch` Kaydı:**
   - `Batch.description` alanına aynı kaynak/hedef dökümü yazılır.
   - Karma lot durumunda hedef `Batch.reference_doctype = "Stock Entry"` ve `Batch.reference_name = se.name` bağlanır.
4. **Etiket Basımı:** `KTAStockEntry.on_submit()` → `print_stock_entry_labels(se.name)` akışı hedef yeni kutunun `KTA Stock Label` kaydını oluşturup Zebra'ya tek sefer basar (`pda_package_merge` ikinci kez basmaz). Karma lot birleştirmesinde hedef etiket kaydında `quality_ref = "KARMA LOT"` yazılır (aynı lot birleştirmesinde kardeş/kaynak `quality_ref` korunur). Tüm tüketilen kaynak kutular `sync_batch_label_to_ledger_balance` ile sıfır bakiyeye güncellenip temizlenir.

### 2.5 `KTAStockEntry` Tek Ürün Koruması ve İptal/Silme Geri Alma
1. **Tek Ürün Koruması (`validate`):** `_validate_single_item_package_split()` metodu hem `"Package Split"` hem `"Package Merge"` tipleri için tek `item_code` zorunluluğunu denetler; çoklu ürün varsa hata fırlatır.
2. **İptal (`on_cancel`) ve Silme (`on_trash`) Geri Alma:**
   - `relabeling_types = ("Return from Production Supply", "Package Split", "Package Merge")` olarak genişletilir.
   - İptal ve silmede `_delete_associated_labels()` hedef etiketi ve yazdırma loglarını temizler; `_sync_relabeling_on_cleanup(..., disable_empty_targets=(self.stock_entry_type in ("Package Split", "Package Merge")))` sıfıra düşen hedef kutu partisini `disabled = 1, batch_qty = 0` yapar.
   - **Tüketilmiş Kaynak Kutu Etiketlerini Geri Yükleme:** Birleştirme sırasında sıfırlandığı için silinen kaynak `KTA Stock Label` kayıtları, belge iptal edilip kaynak parti defter bakiyeleri tekrar `> 0` olduğunda `upsert_box_label` (orijinal PR/WO/kardeş meta verileri korunarak) ile otomatik yeniden oluşturulur/senkronlanır.
   - **`LinkExistsError` Koruması:** Karma lot hedef `Batch` üzerinde `reference_doctype == "Stock Entry"` ve `reference_name == self.name` bağı varsa, `on_cancel` / `on_trash` (`super().on_trash()` öncesinde) bu bağlantıyı temizleyerek `se.delete()` çağrısının `LinkExistsError` vermesini engeller.

---

## 3. Gizlilik ve Güvenlik Kuralları
- Dokümantasyon ve örneklerde gerçek tedarikçi/müşteri firma adı veya gerçek birim fiyat/maliyet bilgisi kesinlikle yer almaz (yalnızca `ITEM-001`, `ABC12340001`, `XYZ56780003` gibi anonim örnekler kullanılır).
- Tüm PDA uçları (`pda_package_merge`) `_require_pda_screen_access("merge")` ile korunur; genel ofis `Stock User` veya yetkisiz kullanıcılar `frappe.PermissionError` alır ve oluşan `Stock Entry.owner` daima oturumdaki operatördür.
