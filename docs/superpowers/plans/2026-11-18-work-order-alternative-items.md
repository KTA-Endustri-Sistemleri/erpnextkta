# Work Order Alternative Items Management & Backflush Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shopfloor Hub İş Emri Serbest Bırakma Panelinde (`WorkOrderReleasePanel.vue`) onaylı hammadde muadillerinin (`Item Alternative`) stok durumlarıyla listelenerek seçilebilmesini, orijinal reçete izinin korunmasını (`custom_original_item`), tek tıkla geri alınabilmesini ve CO11N operasyon teyidi tüketim motorunda (`BackflushService` & `KTAStockEntry`) hatasız backflush yapılabilmesini sağlamak.

**Architecture:** Backend tarafında `Item Alternative` çift yönlü ilişkilerini tarayan ve satır bazında muadil atayan/geri alan servisler `erpnextkta/kta_shopfloor/services/work_order_service.py` ve `api.py` altında inşa edilecek. Tüketim tarafında `BackflushService` seçili alternatifi tüketip `Stock Entry` üzerinde hem `original_item` hem `custom_original_item` alanlarını işleyecek; `KTAStockEntry` sınıfı standart `validate_components_quantities_per_bom` kontrolünü onaylı muadiller için esnetecektir. Frontend tarafında `ItemAlternativesModal.vue` bileşeni geliştirilerek `WorkOrderReleasePanel.vue` matrisine bağlanacaktır.

**Tech Stack:** Frappe v15, ERPNext, Vue 3 (`<script setup lang="ts">`), TypeScript, Python 3.12, Ruff, Frappe TestCase.

**Spec:** `docs/superpowers/specs/2026-11-18-work-order-alternative-items-design.md`

## Global Constraints

- Hiçbir DocType Türkçe adla oluşturulamaz (`.agents/AGENTS.md`).
- Arayüz metinleri Title Case kuralına uymalı, `__('Text')` ile sarılmalı ve TR, EN, DE sözlükleri güncellenmelidir.
- Frontend üretim derlemesi kesinlikle `bench build --app erpnextkta --production` komutuyla yapılmalıdır.
- Reçete uyumsuzluk doğrulaması esnetilirken onaylanmamış rastgele malzemelerin tüketilmesine izin verilmemeli (katı Poke-Yoke).
- Python kodları `/home/frappe/frappe-bench/env/bin/ruff check` ve `format` kurallarına uymalıdır.
- Dokümantasyon ve test verilerinde ticari gizlilik kurallarına uyulmalı; gerçek tedarikçi unvanları ve birim fiyatlar kullanılmamalıdır.

## Review Focus

1. **Çift Yönlü Muadil Eşleşmesi (`two_way=1`):** `Item Alternative` tablosunda B maddesi A'nın alternatifi ve `two_way=1` ise, A maddesi için de B'nin listelenebilmesi.
2. **Çoklu Değişimde Kök Kodun Korunması:** Orijinal A maddesi önce B'ye, ardından C'ye dönüştürüldüğünde `custom_original_item` değerinin B değil daima ilk orijinal A olarak muhafaza edilmesi.
3. **Kısmi Tüketim Blokajı (Poke-Yoke):** İlgili hammadde satırında `consumed_qty > 0` veya `transferred_qty > 0` olduğunda alternatif değişiminin ve geri almanın kesinlikle engellenmesi.
4. **Onaysız Malzeme Girişinin Engellenmesi:** API seviyesinde `Item Alternative` tablosunda eşleşmesi olmayan rastgele bir kod iletildiğinde `frappe.ValidationError` fırlatılması.
5. **Backflush ve Maliyet Doğruluğu:** CO11N operasyon teyidinde oluşturulan tüketim fişinde alternatif malzeme kodunun yer alması, alternatif malzemenin `actual_qty` ve `valuation_rate` değerlerinin doğru işlenmesi, `validate_components_quantities_per_bom` hatasının aşılması.

---

### Task 1: Şema Güncellemeleri (`Work Order Item` & `Stock Entry Detail` Özel Alanları)

**Files:**
- Create: `erpnextkta/erpnextkta/custom/work_order_item.json`
- Modify: `erpnextkta/erpnextkta/custom/stock_entry_detail.json`
- Create: `erpnextkta/kta_shopfloor/tests/test_alternative_schema.py`

**Interfaces:**
- Produces: `Work Order Item.custom_original_item` (Link -> Item), `Stock Entry Detail.custom_original_item` (Link -> Item).

- [ ] **Step 1: Write the failing test**
Create `erpnextkta/kta_shopfloor/tests/test_alternative_schema.py` to verify that `custom_original_item` is defined in both JSON schemas.
```python
import json
import os
from frappe.tests.utils import FrappeTestCase

class TestAlternativeItemSchema(FrappeTestCase):
    def test_work_order_item_custom_field_defined(self):
        path = "erpnextkta/erpnextkta/custom/work_order_item.json"
        self.assertTrue(os.path.exists(path), f"{path} must exist")
        with open(path) as f:
            data = json.load(f)
        fieldnames = [cf["fieldname"] for cf in data.get("custom_fields", [])]
        self.assertIn("custom_original_item", fieldnames)

    def test_stock_entry_detail_custom_field_defined(self):
        path = "erpnextkta/erpnextkta/custom/stock_entry_detail.json"
        with open(path) as f:
            data = json.load(f)
        fieldnames = [cf["fieldname"] for cf in data.get("custom_fields", [])]
        self.assertIn("custom_original_item", fieldnames)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_alternative_schema`
Expected: FAIL (file does not exist or field not in list).

- [ ] **Step 3: Implement custom fields in JSON files**
- Create `erpnextkta/erpnextkta/custom/work_order_item.json` with `custom_original_item`:
  - `fieldname`: `custom_original_item`
  - `fieldtype`: `Link`
  - `options`: `Item`
  - `label`: `Original Item`
  - `read_only`: 1
  - `no_copy`: 1
  - `insert_after`: `item_code`
- Modify `erpnextkta/erpnextkta/custom/stock_entry_detail.json` by adding `custom_original_item` to `custom_fields`.

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_alternative_schema`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/erpnextkta/custom/work_order_item.json erpnextkta/erpnextkta/custom/stock_entry_detail.json erpnextkta/kta_shopfloor/tests/test_alternative_schema.py
git commit -m "feat(schema): add custom_original_item to Work Order Item and Stock Entry Detail"
```

---

### Task 2: Backend Alternatif Yönetim Servisleri (`work_order_service.py`)

**Files:**
- Modify: `erpnextkta/kta_shopfloor/services/work_order_service.py`
- Test: `erpnextkta/kta_shopfloor/tests/test_work_order_service.py`

**Interfaces:**
- Consumes: `Item Alternative`, `Work Order Item.custom_original_item`, `Bin.actual_qty`, `Bin.reserved_qty_for_production`.
- Produces:
  - `get_item_alternatives(item_code: str, company: str | None = None, warehouse: str | None = None) -> list[dict]`
  - `get_work_order_item_alternatives(work_order: str, row_name: str) -> dict`
  - `set_work_order_item_alternative(work_order: str, row_name: str, alternative_item_code: str) -> dict`
  - `restore_work_order_item_original(work_order: str, row_name: str) -> dict`

- [ ] **Step 1: Write the failing test**
Add test methods in `erpnextkta/kta_shopfloor/tests/test_work_order_service.py`:
- `test_get_item_alternatives_bidirectional`: verifies one-way and two-way alternatives are resolved.
- `test_set_work_order_item_alternative_success`: verifies setting approved alternative, populating `custom_original_item`, and adding comment.
- `test_set_work_order_item_alternative_unapproved_fails`: raises `frappe.ValidationError` for unauthorized item.
- `test_set_work_order_item_alternative_consumed_fails`: raises `frappe.ValidationError` when `consumed_qty > 0`.
- `test_restore_work_order_item_original`: verifies restoring original item and clearing `custom_original_item`.

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --doctype "Work Order" --test test_get_item_alternatives_bidirectional`
Expected: FAIL (AttributeError: `get_item_alternatives` not implemented).

- [ ] **Step 3: Implement services in `work_order_service.py`**
- Implement `get_item_alternatives(item_code, company=None, warehouse=None)`:
  - Query `Item Alternative` matching `item_code == item` OR (`alternative_item_code == item` and `two_way == 1`).
  - Calculate `line_available_qty` and `other_warehouses_qty` for each alternative.
- Implement `get_work_order_item_alternatives(work_order, row_name)`:
  - Identify root item code (`row.custom_original_item` or `row.item_code`).
  - Return current row status, `can_swap: (row.consumed_qty or 0) <= 0`, and alternatives list.
- Implement `set_work_order_item_alternative(work_order, row_name, alternative_item_code)`:
  - Validate work order docstatus (cannot be 2 or stopped).
  - Validate `consumed_qty == 0`.
  - Validate `alternative_item_code` is in approved alternatives for root item.
  - Set `row.custom_original_item = root_item`, update `row.item_code = alternative_item_code`, fetch item defaults (name, description, stock_uom).
  - Update DB and add Frappe Comment.
- Implement `restore_work_order_item_original(work_order, row_name)`:
  - Validate `row.custom_original_item` exists and `row.consumed_qty == 0`.
  - Revert `row.item_code = row.custom_original_item`, set `row.custom_original_item = None`.
  - Update DB and add Frappe Comment.
- In `check_work_order_material_availability(work_order)`:
  - Append `row_name: d.name`, `custom_original_item: d.get("custom_original_item")`, `is_alternative: bool(d.get("custom_original_item"))`, `has_alternatives: bool(...)`, `alternative_count: int(...)` to each item entry.

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_work_order_service`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/kta_shopfloor/services/work_order_service.py erpnextkta/kta_shopfloor/tests/test_work_order_service.py
git commit -m "feat(shopfloor): add work order item alternative services with poke-yoke and restore support"
```

---

### Task 3: API Uçları (`erpnextkta/kta_shopfloor/api.py`)

**Files:**
- Modify: `erpnextkta/kta_shopfloor/api.py`
- Modify: `erpnextkta/kta_shopfloor/tests/test_api.py`

**Interfaces:**
- Consumes: `work_order_service` alternative functions.
- Produces:
  - `@frappe.whitelist() def get_work_order_item_alternatives(work_order: str, row_name: str) -> dict`
  - `@frappe.whitelist() def set_work_order_item_alternative(work_order: str, row_name: str, alternative_item_code: str) -> dict`
  - `@frappe.whitelist() def restore_work_order_item_original(work_order: str, row_name: str) -> dict`

- [ ] **Step 1: Write the failing test**
In `erpnextkta/kta_shopfloor/tests/test_api.py`, add:
- `test_api_get_work_order_item_alternatives`
- `test_api_set_work_order_item_alternative`
- `test_api_restore_work_order_item_original`

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_api`
Expected: FAIL (AttributeError: endpoint not found).

- [ ] **Step 3: Implement endpoints in `api.py`**
Expose whitelisted wrapper functions delegating to `work_order_service.py` methods with permission checks:
```python
@frappe.whitelist()
def get_work_order_item_alternatives(work_order: str, row_name: str) -> dict:
    return _get_wo_item_alternatives_service(work_order, row_name)

@frappe.whitelist()
def set_work_order_item_alternative(work_order: str, row_name: str, alternative_item_code: str) -> dict:
    return _set_wo_item_alternative_service(work_order, row_name, alternative_item_code)

@frappe.whitelist()
def restore_work_order_item_original(work_order: str, row_name: str) -> dict:
    return _restore_wo_item_original_service(work_order, row_name)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_api`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/kta_shopfloor/api.py erpnextkta/kta_shopfloor/tests/test_api.py
git commit -m "feat(api): expose work order item alternative endpoints in kta_shopfloor"
```

---

### Task 4: CO11N Backflush Tüketim & `KTAStockEntry` Reçete Doğrulama Override'ı

**Files:**
- Modify: `erpnextkta/kta_shopfloor/services/backflush_service.py`
- Modify: `erpnextkta/overrides/KTAStockEntry.py`
- Modify: `erpnextkta/tests/test_stock_entry_override.py`

**Interfaces:**
- Consumes: `wo.required_items` with substituted `item_code` and `custom_original_item`.
- Produces: Stock Entry items containing `original_item` and `custom_original_item`; `KTAStockEntry.validate_components_quantities_per_bom()` matching approved alternatives against BOM items.

- [ ] **Step 1: Write the failing test**
In `erpnextkta/tests/test_stock_entry_override.py`, add `test_backflush_with_alternative_item()`:
- Create BOM with Item A.
- Create Work Order, swap Item A to approved alternative Item B.
- Create CO11N production confirmation with backflush consumption.
- Verify Stock Entry submits without `Incorrect Component Quantity` or `Missing Item` error.
- Verify bin stock for Item B is deducted and valuation reflects Item B.

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_override`
Expected: FAIL (Missing Item or Incorrect Component Quantity error from ERPNext standard validation).

- [ ] **Step 3: Implement Backflush & KTAStockEntry override**
- In `erpnextkta/kta_shopfloor/services/backflush_service.py`:
  - In `calculate_operation_raw_materials`: include `"original_item": d.get("custom_original_item")`.
  - In `create_consumption_entry`: pass `"original_item": rm.get("original_item")` and `"custom_original_item": rm.get("original_item")` into Stock Entry Detail rows.
- In `erpnextkta/overrides/KTAStockEntry.py`:
  - Override `validate_components_quantities_per_bom(self)`:
    - When checking BOM components against Stock Entry items, check if a Stock Entry row has `original_item` or `custom_original_item` equal to the BOM component, OR if the row's `item_code` is an approved `Item Alternative` for the BOM component.
    - If matched, map it as the BOM component and validate quantity.
    - If valid, bypass the missing item exception.

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_override`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/kta_shopfloor/services/backflush_service.py erpnextkta/overrides/KTAStockEntry.py erpnextkta/tests/test_stock_entry_override.py
git commit -m "feat(stock): support alternative items in BackflushService and KTAStockEntry validation"
```

---

### Task 5: Frontend Arayüzü (`ItemAlternativesModal.vue` & `WorkOrderReleasePanel.vue` Entegrasyonu)

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/types.ts`
- Create: `erpnextkta/public/shopfloor-hub/components/ItemAlternativesModal.vue`
- Modify: `erpnextkta/public/shopfloor-hub/components/WorkOrderReleasePanel.vue`

**Interfaces:**
- Consumes: Backend API endpoints (`get_work_order_item_alternatives`, `set_work_order_item_alternative`, `restore_work_order_item_original`).
- Produces: Interactive alternative selection modal, matrix table alternative badges, restore button, and responsive mobile-ready table layout.

- [ ] **Step 1: Update TypeScript interfaces in `types.ts`**
Add:
```typescript
export interface ItemAlternativeOption {
  item_code: string;
  item_name: string;
  description?: string;
  stock_uom: string;
  line_available_qty: number;
  other_warehouses_qty: number;
  total_available_qty: number;
  two_way: boolean;
}

export interface WorkOrderItemAlternativesResponse {
  work_order: string;
  row_name: string;
  current_item_code: string;
  original_item_code?: string | null;
  is_swapped: boolean;
  consumed_qty: number;
  can_swap: boolean;
  alternatives: ItemAlternativeOption[];
}
```
Extend `MaterialAvailabilityItem` with `row_name: string`, `custom_original_item?: string | null`, `is_alternative?: boolean`, `has_alternatives?: boolean`, `alternative_count?: number`.

- [ ] **Step 2: Create `ItemAlternativesModal.vue`**
- Create modal component with:
  - Header: Material code, name, and original item notice if swapped.
  - Alternatives table: Columns for Alternative Code, Name, Stock on Line, Stock in Other WHs, Total Available, and Action button (`[ Seç ]` / `[ Seçili ]`).
  - Restore action button: `[ ↩️ Orijinal Reçete Koduna Dön ]` (visible when `is_swapped` is true).
  - Poke-Yoke warning if `consumed_qty > 0`.
  - Loading and empty states (`Tanımlı alternatif bulunmuyor`).

- [ ] **Step 3: Integrate modal into `WorkOrderReleasePanel.vue`**
- In `WorkOrderReleasePanel.vue`:
  - Import `ItemAlternativesModal.vue`.
  - In `matrix-table`:
    - Add badge in Hammadde cell when `item.is_alternative` is true (`Muadil: {item.item_code} | Asıl: {item.custom_original_item}`).
    - Add action button `[ 🔄 Muadil ]` if `item.has_alternatives` or `item.is_alternative`.
    - Add direct quick-action `[ ↩️ Orijinale Dön ]` when `item.is_alternative` and `!isReleased`.
  - Wire up `openAlternativesModal(item)`, `handleSelectAlternative(altCode)`, `handleRestoreOriginal()`.
  - Upon success, trigger `fetchAvailability()` to refresh the readiness percentage and table rows.

- [ ] **Step 4: Verify frontend production build**
Run: `bench build --app erpnextkta --production`
Expected: Build succeeds with 0 errors.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/types.ts erpnextkta/public/shopfloor-hub/components/ItemAlternativesModal.vue erpnextkta/public/shopfloor-hub/components/WorkOrderReleasePanel.vue
git commit -m "feat(ui): add ItemAlternativesModal and integrate into WorkOrderReleasePanel"
```

---

### Task 6: Çok Dilli Çeviriler (TR / EN / DE) ve Portal Dokümantasyonu

**Files:**
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/www/docs/shopfloor-hub.html`

**Interfaces:**
- Consumes: New UI terms and workflow descriptions.
- Produces: Complete translations (Title Case, unified sentences) and end-user portal documentation under `/docs/shopfloor-hub`.

- [ ] **Step 1: Add translation dictionary entries**
In `tr.csv`, `en.csv`, and `de.csv`, add entries for all new strings:
- "Alternatif Hammadde", "Alternative Item", "Alternatives Material"
- "Muadil Seçimi", "Select Alternative", "Alternative Auswählen"
- "Orijinal Kaleme Dön", "Restore Original Item", "Originales Material Wiederherstellen"
- "Tanımlı Alternatif Bulunmuyor", "No Defined Alternatives", "Keine Definierten Alternativen"
- "Bileşen alternatifi başarıyla değiştirildi.", "Component alternative successfully updated.", "Materialalternative erfolgreich aktualisiert."
- "Kısmi tüketim yapılmış hammadde için alternatif seçilemez.", "Cannot select alternative for partially consumed material.", "Für teilweise verbrauchtes Material kann keine Alternative ausgewählt werden."
- "Eski Lot / Stok Eritme", "Lot Depletion / Clear Stock", "Chargenabbau / Bestand Abbauen"

- [ ] **Step 2: Update Portal Documentation in `shopfloor-hub.html`**
Under Section "İş Emri Serbest Bırakma ve Malzeme Hazırlık", add subsection:
`### 4. Alternatif Hammadde (Muadil) Yönetimi ve Tüketim Kuralları`
- Explaining the Katı Poke-Yoke rule (only officially approved items in `Item Alternative`).
- Proactive selection for lot depletion (stoğu tam olsa bile muadil seçebilme).
- Preserving original recipe integrity via `custom_original_item` and single-click restore.
- Seamless CO11N backflushing and financial valuation.
- Include a Mermaid diagram illustrating the selection and backflush flow.

- [ ] **Step 3: Verify formatting and links**
Ensure all tags and Jinja template blocks in `erpnextkta/www/docs/shopfloor-hub.html` render cleanly.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/translations/tr.csv erpnextkta/translations/en.csv erpnextkta/translations/de.csv erpnextkta/www/docs/shopfloor-hub.html
git commit -m "docs(i18n): update translations and portal documentation for alternative items management"
```

---

### Task 7: Uçtan Uca Doğrulama ve Otomatik Test Koşumu

**Files:**
- Verify: `erpnextkta/kta_shopfloor/tests/test_work_order_service.py`
- Verify: `erpnextkta/kta_shopfloor/tests/test_api.py`
- Verify: `erpnextkta/tests/test_stock_entry_override.py`

**Interfaces:**
- Validates the complete pipeline: Schema -> Service -> API -> CO11N Backflush -> Stock Entry Override.

- [ ] **Step 1: Run shopfloor module test suite**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_work_order_service`
Expected: PASS with 0 failures.

- [ ] **Step 2: Run shopfloor API test suite**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_api`
Expected: PASS with 0 failures.

- [ ] **Step 3: Run stock entry override test suite**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_override`
Expected: PASS with 0 failures.

- [ ] **Step 4: Run linter and formatting checks**
Run:
`/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_shopfloor erpnextkta/overrides`
`/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_shopfloor erpnextkta/overrides`
Expected: Clean output with 0 lint violations.

- [ ] **Step 5: Run production frontend build gate**
Run: `bench build --app erpnextkta --production`
Expected: Successful build.

- [ ] **Step 6: Final clean commit**
```bash
git status
```
Verify working directory is clean.
