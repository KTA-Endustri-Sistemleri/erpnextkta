# PDA Eski SAP Raf Künyesi (`110-W1A-01-01`) Barkod Çözümleme Tasarımı

**Tarih:** 2026-11-26
**Durum:** Implemented — Kalite Kapısı Doğrulandı
**Boyut:** Küçük Değişiklik
**Kapsam:** `erpnextkta/kta_stock/services/pda_service.py`, `erpnextkta/kta_stock/tests/test_pda_service.py`, `/docs/stok-lojistik`

---

## 1. Amaç ve Mevcut Durum (`development.localhost` Bulguları)

Depo raflarındaki fiziksel künyeler eski SAP düzenine göre basıldığı için (`110-W1A-01-01`, `110-W1F-01-01` vb.), PDA ekranlarında raf barkodu okutulduğunda ERPNext üzerindeki mevcut `Warehouse` kayıtlarıyla birebir ad eşleşmesi sağlanamamaktadır.

`development.localhost` veritabanı incelemesindeki gerçek depo ağacı şu şekildedir:

- **`110 HAMMADDE - KTA` Altındaki Raflar (`110-` öneksiz):**
  - `W1A - KTA` .. `W1E - KTA`: toplam **750** aktif yaprak raf (`W1A-01-01` .. `W1E-25-06`).
  - `W1F - KTA`: toplam **151** raf; bunların **85** adedi aktif (`W1F-01-01` .. `W1F-11-06`, `W1F-23-01` .. `W1F-25-06`, `W1F-38-01`), **66** adedi ise mamule devredildiği için pasif (`disabled = 1`, `W1F-12-01` .. `W1F-22-06`).
  - `OBS - KTA`: **18** aktif yaprak raf (`W1O-01-01` .. `W1O-06-03`).
- **`170 BİTMİŞ ÜRÜN - KTA` Altındaki Raflar (Zaten `170-` önekli):**
  - `170-W1F-12 - KTA` .. `170-W1F-22 - KTA`: **66** aktif yaprak raf (`warehouse_name` alanı doğrudan `170-W1F-12-01` .. `170-W1F-22-06`).
- **Mevcut PDA Çözümleyicisi ([pda_service.py](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_stock/services/pda_service.py)):**
  - `_lookup_warehouse_record()` yalnızca birebir `Warehouse.name` ve `Warehouse.warehouse_name` sorgusu yaptığı için `170-W1F-12-01` barkodunu bulabilirken, `110-W1A-01-01` veya `110-W1F-01-01` gibi önekli eski SAP künyelerinde hata fırlatmaktadır.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### Hedefler
- `110-W1A-01-01`, `110-W1F-01-01`, `110-W1O-01-01` gibi `<depo_kodu>-<raf_kodu>` formatındaki eski SAP künyelerini mevcut `Warehouse` kayıtlarına otomatik çözümlemek.
- `170-W1F-12-01` gibi `warehouse_name` alanı zaten birebir eşleşen raflarda hiçbir davranış değişikliği yaratmamak.
- **Üst Depo Ağacı Doğrulaması:** Önekli eşleşmede `Warehouse` NestedSet (`lft`/`rgt`) hiyerarşisini kontrol ederek yanlış depo önekini (örneğin `170-W1F-01-01`) reddetmek ve farklı ana depolar altındaki aynı raf kodlarını güvenle ayırmak.
- **Pasif Raf Koruması:** `W1F` içinde `170`’e devredilmiş pasif rafların eski künyesi (`110-W1F-12-01`) okutulursa kullanıcıya net biçimde `"Depo pasif durumda"` uyarısı dönmek.
- Tek merkez (`_lookup_warehouse_record` + `resolve_warehouse_barcode`) üzerinden **Depo Raf Transferi**, **Koli Birleştirme** ve **Hızlı Stok Sorgu (`pda_stock_lookup`)** ekranlarının üçünü birden otomatik olarak kapsamak.

### Kapsam Dışı ve Anti-Hedefler
- Mevcut 924+ `Warehouse` kaydının `name` veya `warehouse_name` alanlarını yeniden adlandırmamak (geçmiş `Stock Ledger Entry` ve `Bin` kayıtlarına dokunmamak).
- `Warehouse` üzerinde yeni bir custom field veya migration patch’i açmamak.
- Üst depo doğrulaması olmadan kör önek kesme (prefix stripping) yapmamak.

---

## 3. Değerlendirilen Yaklaşımlar

| Yaklaşım | Özet | Artıları | Eksileri | Karar |
|---|---|---|---|---|
| **Yaklaşım A (Seçilen)** | Akıllı SAP Önek Çözümleyici (`NestedSet` üst depo doğrulamalı) | Sıfır şema/patch maliyeti; yeni raflar otomatik desteklenir; `110` / `170` ayrımını ağaçtan doğrular. | SAP künyesi ERPNext adından tamamen farklı olan kural dışı raf varsa kapsamaz. | **Seçildi** |
| **Yaklaşım B** | Hibrit (Önce `custom_warehouse_barcode`, sonra Yaklaşım A) | Kural dışı özel barkodlara da izin verir. | Ekstra alan ve migration gerektirir; sahada kural dışı istisna bildirilmedi. | Elendi |
| **Yaklaşım C** | Tüm raflara patch ile statik barkod doldurmak | Sabit alan araması | Yeni eklenen her rafta elle veri girişi unutulursa hata verir. | Elendi |

---

## 4. Teknik Tasarım Özeti

### 4.1 Desen ve Üst Depo Kontrolü
- **Düzenli İfade:** `_SAP_PREFIXED_WAREHOUSE_RE = re.compile(r"^(\d{2,4})-(.+)$")`
- **Yardımcı Fonksiyon `_warehouse_has_prefix_ancestor(wh: dict, depot_code: str) -> bool`:**
  - `Warehouse` NestedSet indeksleri (`lft <= wh.lft`, `rgt >= wh.rgt`, `is_group = 1`, aynı `company`) üzerinden adayın tüm üst grup depolarını sorgular.
  - Üst gruplardan en az birinin `warehouse_name` değeri `depot_code` ile birebir eşit veya `"{depot_code} "` ya da `"{depot_code}-"` ile başlıyorsa (case-insensitive) `True` döner (örneğin `110 HAMMADDE` üst grubu `110` önekini doğrular).

### 4.2 `_lookup_warehouse_record(barcode, company=None)` Akışı
1. **Birebir `Warehouse.name`:** `name == code` eşleşmesi (`170-W1F-12-01 - KTA` veya `W1A-01-01 - KTA`).
2. **Birebir `Warehouse.warehouse_name`:** `warehouse_name == code` eşleşmesi (`170-W1F-12-01` veya `W1A-01-01`; aktif yaprak önceliği ve şirket ayrımı korunur).
3. **SAP Önekli Geri Dönüş (Fallback):**
   - `code` değeri `_SAP_PREFIXED_WAREHOUSE_RE` ile eşleşirse `(depot_code, shelf_code)` ayrıştırılır.
   - `warehouse_name == shelf_code` koşuluyla aday `Warehouse` kayıtları çekilir; yalnızca `_warehouse_has_prefix_ancestor(m, depot_code)` doğrulamasından geçenler tutulur.
   - Elenen liste üzerinden mevcut tekil/çoklu seçim kuralları işletilir (aktif yaprak önceliği; hiç aktif yoksa pasif eşleşmeyi dönerek `resolve_warehouse_barcode()` içinde net `"Depo pasif durumda"` hatası üretilmesi sağlanır).
   - Çoklu şirket belirsizliği yoksa `None` yerine doğrulanmış kayıt döner; `pda_stock_lookup` içinde de geçerli olur.

### 4.3 Etkilenen Dosyalar
- **Backend:** [pda_service.py](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_stock/services/pda_service.py) (`_SAP_PREFIXED_WAREHOUSE_RE`, `_warehouse_has_prefix_ancestor`, `_select_warehouse_match`, `_lookup_warehouse_record`).
- **Testler:** [test_pda_service.py](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_stock/tests/test_pda_service.py).
- **Dokümantasyon:** [stok-lojistik.html](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/www/docs/stok-lojistik.html) ve [kta_stok_lojistik_kilavuzu.md](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/kta_stok_lojistik_kilavuzu.md).

---

## 5. Doğrulama Senaryoları (Test Matrisi)

1. `110-W1A-01-01` → `110 HAMMADDE` altındaki aktif `W1A-01-01` yaprak rafına çözülür.
2. `110-W1F-01-01` → `110 HAMMADDE / W1F` altındaki aktif `W1F-01-01` yaprak rafına çözülür.
3. `170-W1F-12-01` → doğrudan `warehouse_name == "170-W1F-12-01"` üzerinden `170` altındaki aktif mamul rafına çözülür.
4. `110-W1F-12-01` → `W1F` altındaki pasif (`disabled=1`) rafı eşleştirip `resolve_warehouse_barcode` üzerinden `"Depo pasif durumda"` hatası verir (`170-W1F-12-01`'e karışmaz).
5. `170-W1F-01-01` → `170` altında `W1F-01-01` bulunmadığı ve `W1F-01-01` yalnızca `110` altında olduğu için üst depo doğrulamasından geçemez ve `"Depo barkodu bulunamadı"` hatası verir.
6. `pda_stock_lookup("110-W1A-01-01")` → `kind == "warehouse"` olarak raftaki stok listesini döner.

> [!IMPORTANT]
> **Clean-CI Boş `test_site` İzolasyon Kuralı:** Üretim kodunda şirket adı (`KTA`) veya sabit raf adları kesinlikle hardcoded yazılmaz; tüm çözümleme yalnızca dinamik `Warehouse` NestedSet (`lft`/`rgt`) ve `parent_warehouse` üzerinden çalışır. Tüm birim/entegrasyon testleri, boş bir Clean-CI `test_site` üzerinde çalışacak şekilde kendi benzersiz ekli (`uid`) `110 HAMMADDE ...` / `170 BİTMİŞ ÜRÜN ...` test depo hiyerarşisini `self._get_test_company()` altında dinamik olarak kurar ve mevcut `development.localhost` verisine dayanmaz.
