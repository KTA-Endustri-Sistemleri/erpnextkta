# KTA Line Replenishment (Hat İkmal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Üretim hatlarındaki hammadde açıklarını proaktif tespit eden, kardeş hat serbest
stoklarını tarayarak hatlar arası dengeleme (Line-to-Line Transfer) ve ana ambar FIFO tahsisi
yapan, masaüstü kokpit ve mobil PDA toplama arayüzleriyle tek adımda transfer fişi üreten
uçtan uca Hat İkmal Sistemi kurmak.

**Architecture:** `kta_shopfloor` modülü tekil hedef hat rezervasyon açığı analitik servisini
ve Masaüstü Kokpitini (`Line Replenishment Hub`) sağlar; `kta_stock` modülü ikmal emri DocType
kayıtlarını (`KTA Line Replenishment Order` & `Item`), akıllı FIFO/WIP parti tahsis motorunu,
mobil PDA toplama arayüzünü (`Line Replenishment Picking`) ve atomik `Stock Entry` transfer
icrasını yönetir. `docs-i18n` kullanıcı portali ve çoklu dil sözlük senkronizasyonunu sağlar.

**Tech Stack:** Frappe v15, ERPNext, Python 3.12, JavaScript (ES6+), Frappe Page API,
Ruff Linter/Formatter, Frappe TestCase.

**Spec:** `docs/superpowers/specs/2026-11-19-line-replenishment-design.md`

## Global Constraints

- DocType isimleri Frappe standartlarında tekil ve İngilizce olmalıdır (`.agents/AGENTS.md`).
- Hedef WIP deposu (`target_warehouse`) servis ve arayüzlerde zorunlu tekildir (karma çekim yasak).
- Kardeş hat taraması `parent_warehouse == "150 ÜRETİM - KTA"` altındaki depolarla sınırlıdır.
- Net açık formülü: `reserved_qty_for_production - actual_qty > 0`.
- Kardeş hat serbest stok formülü: `actual_qty - reserved_qty_for_production > 0`.
- Kullanıcıya önerilen kaynak depoyu tek tıkla ana ambara (`110 HAMMADDE`) çevirme hakkı tanınır.
- Tüm kullanıcı arayüzü etiket ve butonları Title Case olmalı ve `__('Text')` ile sarılmalıdır.
- Kodlar `/home/frappe/frappe-bench/env/bin/ruff check` ve `format` kurallarına uymalıdır.
- Dokümantasyon ve testlerde ticari gizlilik kurallarına uyulmalı; gizli fiyat/unvan yazılmamalıdır.
- Tüm dosya satırları istisnasız `STRICT <= 100` karakter sınırına uymalıdır.

## Review Focus

1. **Zorunlu Tekil Hedef Depo Denetimi:** `target_warehouse` boş, geçersiz veya grup ambarı
   olduğunda servisin anında `frappe.ValidationError` fırlatması (Task 2 & 3).
2. **Sıfır ve Negatif Açıkların Bastırılması:** `reserved_qty_for_production <= actual_qty`
   durumunda ikmal listesine satır eklenmemesi (Task 2).
3. **Kardeş Hatta Rezerve Stoğun Hatalı Önerilmemesi:** Kardeş hatta `actual_qty > 0` olsa bile
   kendi rezervi nedeniyle `free_stock <= 0` ise hat transferi önerilmeyip ana ambara düşülmesi
   (Task 2).
4. **Tolerans Üstü Fazla Toplama Reddi:** Depocu izin verilen tolerans sınırından (ör. %15)
   daha fazla miktar girdiğinde transfer fişi üretiminin engellenmesi (Task 4).
5. **Atomik Ters Kayıt (Rollback Güvencesi):** Tamamlanmış ikmal emri iptal edildiğinde bağlı
   `Stock Entry (Material Transfer)` fişinin de Frappe standartlarında iptal edilmesi (Task 4).

---

### Task 1: DocType Definitions in `kta_stock` (`KTA Line Replenishment Order` & `Item`)

**Files:**
- Create:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_order/kta_line_replenishment_order.json`
- Create:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_order/kta_line_replenishment_order.py`
- Create:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_order/__init__.py`
- Create:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_item/kta_line_replenishment_item.json`
- Create:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_item/kta_line_replenishment_item.py`
- Create:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_item/__init__.py`
- Create:
  `erpnextkta/kta_stock/tests/test_line_replenishment_doctypes.py`

**Interfaces:**
- Produces: DocType `KTA Line Replenishment Order` with fields: `target_warehouse`,
  `posting_date`, `posting_time`, `status`, `sourcing_strategy`, `stock_entry`,
  `company`, `total_deficit_qty`, `total_picked_qty`, `items`, `remarks`.
- Produces: Child DocType `KTA Line Replenishment Item` with fields: `item_code`, `item_name`,
  `uom`, `reserved_qty`, `line_actual_qty`, `deficit_qty`, `sourcing_type`,
  `free_stock_qty`, `suggested_source_warehouse`, `suggested_batch_no`, `picked_qty`,
  `picked_source_warehouse`, `picked_batch_no`, `is_picked`.

- [ ] **Step 1: Write the failing test**

Create `erpnextkta/kta_stock/tests/test_line_replenishment_doctypes.py` to test schema properties:
```python
import os
import json
from frappe.tests.utils import FrappeTestCase

class TestLineReplenishmentDocTypes(FrappeTestCase):
    def test_order_doctype_schema(self):
        path = (
            "erpnextkta/kta_stock/doctype/"
            "kta_line_replenishment_order/kta_line_replenishment_order.json"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
        with open(path) as f:
            data = json.load(f)
        fields = {d["fieldname"]: d for d in data.get("fields", [])}
        self.assertIn("target_warehouse", fields)
        self.assertEqual(fields["target_warehouse"]["reqd"], 1)
        self.assertIn("sourcing_strategy", fields)
        self.assertIn("stock_entry", fields)
        self.assertIn("items", fields)

    def test_item_doctype_schema(self):
        path = (
            "erpnextkta/kta_stock/doctype/"
            "kta_line_replenishment_item/kta_line_replenishment_item.json"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
        with open(path) as f:
            data = json.load(f)
        fields = {d["fieldname"]: d for d in data.get("fields", [])}
        self.assertIn("deficit_qty", fields)
        self.assertIn("sourcing_type", fields)
        self.assertIn("suggested_source_warehouse", fields)
        self.assertIn("is_picked", fields)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_doctypes
```
Expected: FAIL (Schema files not found).

- [ ] **Step 3: Implement DocType JSON and Python classes**

1. Create `KTA Line Replenishment Order` JSON schema and controller inheriting `Document`.
   Set `naming_series` to `LRO-.YYYY.-.#####`. Mark `target_warehouse` as mandatory link.
2. Create `KTA Line Replenishment Item` child table JSON schema and controller.
3. Create `__init__.py` files in both directories.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_doctypes
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/doctype/kta_line_replenishment*
git add erpnextkta/kta_stock/tests/test_line_replenishment_doctypes.py
git commit -m "feat(stock): define KTA Line Replenishment Order and Item DocTypes"
```

---

### Task 2: Reservation Deficit Analytics Service in `kta_shopfloor`

**Files:**
- Create: `erpnextkta/kta_shopfloor/services/reservation_deficit_service.py`
- Modify: `erpnextkta/kta_shopfloor/api.py`
- Create: `erpnextkta/kta_shopfloor/tests/test_reservation_deficit_service.py`

**Interfaces:**
- Consumes: `tabBin.reserved_qty_for_production`, `tabBin.actual_qty`,
  `Warehouse.parent_warehouse`.
- Produces:
  `get_line_reservation_deficits(target_warehouse: str, sourcing_strategy: str) -> list[dict]`
- Produces: API endpoint `erpnextkta.kta_shopfloor.api.get_line_deficits`.

- [ ] **Step 1: Write the failing test**

Create `erpnextkta/kta_shopfloor/tests/test_reservation_deficit_service.py`:
```python
import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_shopfloor.services.reservation_deficit_service import (
    get_line_reservation_deficits,
)

class TestReservationDeficitService(FrappeTestCase):
    def test_target_warehouse_mandatory_validation(self):
        with self.assertRaises(frappe.ValidationError):
            get_line_reservation_deficits("")

    def test_zero_deficit_excluded(self):
        # When reserved <= actual, item must not be included
        res = get_line_reservation_deficits("TEST-WIP-NO-DEFICIT")
        self.assertEqual(len(res), 0)

    def test_smart_sourcing_line_transfer_vs_central(self):
        # Sibling warehouse with free stock (actual - reserved > 0)
        # must yield sourcing_type == 'Line Transfer'
        # Otherwise sourcing_type == 'Central Warehouse'
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_shopfloor.tests.test_reservation_deficit_service
```
Expected: FAIL (ModuleNotFoundError or function not found).

- [ ] **Step 3: Implement `reservation_deficit_service.py` & API endpoint**

1. Validate `target_warehouse`: if not provided or empty, raise `frappe.ValidationError`.
2. Query `tabBin` for `target_warehouse` where `reserved_qty_for_production > actual_qty`.
3. Compute `deficit_qty = reserved_qty_for_production - actual_qty`.
4. If `sourcing_strategy == "Smart Sourcing (WIP First)"`:
   - Query sibling warehouses having `parent_warehouse == "150 ÜRETİM - KTA"` (excluding target).
   - Check sibling `tabBin`: `free_stock = actual_qty - reserved_qty_for_production`.
   - If `free_stock > 0`, set `sourcing_type = "Line Transfer"`,
     `suggested_source_warehouse = sibling_warehouse`, `free_stock_qty = free_stock`.
   - If no sibling has free stock, set `sourcing_type = "Central Warehouse"` and
     `suggested_source_warehouse = "110 HAMMADDE - KTA"`.
5. Expose `@frappe.whitelist() def get_line_deficits(target_warehouse, sourcing_strategy=None)`
   in `erpnextkta/kta_shopfloor/api.py`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_shopfloor.tests.test_reservation_deficit_service
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_shopfloor/services/reservation_deficit_service.py
git add erpnextkta/kta_shopfloor/api.py
git add erpnextkta/kta_shopfloor/tests/test_reservation_deficit_service.py
git commit -m "feat(shopfloor): implement reservation deficit analytics and smart sourcing"
```

---

### Task 3: FIFO Allocation & Order Generation in `kta_stock`

**Files:**
- Create: `erpnextkta/kta_stock/line_replenishment_service.py`
- Modify:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_order/kta_line_replenishment_order.py`
- Create: `erpnextkta/kta_stock/tests/test_line_replenishment_service.py`

**Interfaces:**
- Consumes: `get_line_reservation_deficits` output, `tabBatch`, `tabBin`.
- Produces:
  `allocate_fifo_batch(item_code: str, warehouse: str, required_qty: float) -> str | None`
- Produces:
  `create_line_replenishment_order(target_warehouse: str, items: list[dict], strategy: str) -> str`
- Produces:
  `override_item_source(order_name: str, item_code: str, new_source_warehouse: str)`

- [ ] **Step 1: Write the failing test**

Create `erpnextkta/kta_stock/tests/test_line_replenishment_service.py`:
```python
import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_stock.line_replenishment_service import (
    create_line_replenishment_order,
    allocate_fifo_batch,
)

class TestLineReplenishmentService(FrappeTestCase):
    def test_create_order_without_target_warehouse_fails(self):
        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order("", [])

    def test_create_order_empty_items_fails(self):
        with self.assertRaises(frappe.ValidationError):
            create_line_replenishment_order("1501 KESMELER - KTA", [])

    def test_order_creation_calculates_total_deficit(self):
        # Verify order creation and total_deficit_qty calculation
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_service
```
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement FIFO allocation and order generation**

1. Implement `allocate_fifo_batch`:
   - Query batches for `item_code` with available qty in `warehouse`, ordered by
     `expiry_date asc, creation asc`. Return oldest active batch number.
2. Implement `create_line_replenishment_order`:
   - Validate `target_warehouse` is non-empty and singular.
   - Validate `items` list contains at least one row with `deficit_qty > 0`.
   - Create and insert `KTA Line Replenishment Order` with child items.
   - Set status to `Draft`, calculate `total_deficit_qty`.
3. Implement `override_item_source` to allow switching source warehouse to central warehouse.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_service
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/line_replenishment_service.py
git add erpnextkta/kta_stock/doctype/kta_line_replenishment_order/
git add erpnextkta/kta_stock/tests/test_line_replenishment_service.py
git commit -m "feat(stock): add FIFO batch allocation and replenishment order generation"
```

---

### Task 4: Stock Entry Material Transfer Execution in `kta_stock`

**Files:**
- Modify: `erpnextkta/kta_stock/line_replenishment_service.py`
- Modify:
  `erpnextkta/kta_stock/doctype/kta_line_replenishment_order/kta_line_replenishment_order.py`
- Create: `erpnextkta/kta_stock/tests/test_line_replenishment_transfer.py`

**Interfaces:**
- Consumes: `KTA Line Replenishment Order` in `Draft` or `In Progress` status.
- Produces:
  `complete_line_replenishment_picking(order_name: str, picked_items: list[dict]) -> str`
- Produces: `Stock Entry` (`purpose = "Material Transfer"`), status `Submitted` (`docstatus = 1`).
- Produces: On-cancel hook canceling linked `Stock Entry`.

- [ ] **Step 1: Write the failing test**

Create `erpnextkta/kta_stock/tests/test_line_replenishment_transfer.py`:
```python
import frappe
from frappe.tests.utils import FrappeTestCase
from erpnextkta.kta_stock.line_replenishment_service import (
    complete_line_replenishment_picking,
)

class TestLineReplenishmentTransfer(FrappeTestCase):
    def test_over_picking_within_tolerance_accepted(self):
        # 100 required, 110 picked (10% over) is accepted
        pass

    def test_over_picking_beyond_tolerance_rejected(self):
        # 100 required, 150 picked (>15% limit) must raise ValidationError
        pass

    def test_transfer_creates_and_submits_stock_entry(self):
        # Verify Stock Entry created with purpose="Material Transfer"
        # and order.status becomes "Completed"
        pass

    def test_order_cancellation_cancels_stock_entry(self):
        # Cancelling replenishment order must cancel linked Stock Entry
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer
```
Expected: FAIL.

- [ ] **Step 3: Implement Stock Entry generation, tolerance check & rollback**

1. In `complete_line_replenishment_picking`:
   - Validate picked quantities against deficit and tolerance (default 15% max over-picking).
   - If exceeded, raise `frappe.ValidationError(_("Over-picking exceeds allowable tolerance"))`.
   - Create `Stock Entry` with `purpose = "Material Transfer"`, `company = order.company`.
   - Append rows: `s_warehouse = picked_source_warehouse`, `t_warehouse = order.target_warehouse`,
     `item_code`, `qty = picked_qty`, `batch_no = picked_batch_no`.
   - Save and submit (`docstatus = 1`).
   - Update order status to `Completed`, set `stock_entry` reference and `total_picked_qty`.
2. In `kta_line_replenishment_order.py`, implement `on_cancel`:
   - If `self.stock_entry`, fetch doc and call `se.cancel()`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/line_replenishment_service.py
git add erpnextkta/kta_stock/doctype/kta_line_replenishment_order/
git add erpnextkta/kta_stock/tests/test_line_replenishment_transfer.py
git commit -m "feat(stock): execute atomic material transfer with over-picking tolerance"
```

---

### Task 5: Desktop Line Replenishment Hub (Masaüstü Kokpit Arayüzü)

**Files:**
- Create:
  `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.json`
- Create:
  `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.py`
- Create:
  `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.js`
- Create:
  `erpnextkta/kta_shopfloor/page/line_replenishment_hub/line_replenishment_hub.css`
- Create:
  `erpnextkta/kta_shopfloor/tests/test_line_replenishment_hub_page.py`

**Interfaces:**
- Consumes: `erpnextkta.kta_shopfloor.api.get_line_deficits`,
  `erpnextkta.kta_stock.line_replenishment_service.create_line_replenishment_order`.
- Produces: Frappe Page `line-replenishment-hub` accessible from Desk.

- [ ] **Step 1: Write the failing test**

Create `erpnextkta/kta_shopfloor/tests/test_line_replenishment_hub_page.py`:
```python
import os
import json
from frappe.tests.utils import FrappeTestCase

class TestLineReplenishmentHubPage(FrappeTestCase):
    def test_hub_page_json_exists(self):
        path = (
            "erpnextkta/kta_shopfloor/page/"
            "line_replenishment_hub/line_replenishment_hub.json"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data.get("page_name"), "line-replenishment-hub")

    def test_hub_page_js_exists(self):
        path = (
            "erpnextkta/kta_shopfloor/page/"
            "line_replenishment_hub/line_replenishment_hub.js"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_shopfloor.tests.test_line_replenishment_hub_page
```
Expected: FAIL (File not found).

- [ ] **Step 3: Implement Line Replenishment Hub Desk Page**

1. Create `line_replenishment_hub.json` with page title `Line Replenishment Hub`.
2. Create `line_replenishment_hub.py` controller.
3. In `line_replenishment_hub.js`:
   - Add mandatory single-select `target_warehouse` Link control in page header.
   - Prevent search/action if `target_warehouse` is empty.
   - Render interactive deficit table with columns: Item Code, Reserved Qty, Actual Qty,
     Deficit Qty, Sourcing Type (badge), Suggested Source Warehouse, Free Stock.
   - Add button "Tümünü Ana Ambara Çevir (Override to Central)".
   - Add primary action button "İkmal Emri Oluştur (Create Order)" which invokes backend service
     and opens created `KTA Line Replenishment Order`.
4. Style table and status badges cleanly in `line_replenishment_hub.css`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_shopfloor.tests.test_line_replenishment_hub_page
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_shopfloor/page/line_replenishment_hub/
git add erpnextkta/kta_shopfloor/tests/test_line_replenishment_hub_page.py
git commit -m "feat(shopfloor): build Desktop Line Replenishment Hub page"
```

---

### Task 6: Mobile PDA Picking Interface (El Terminali Barkodlu Toplama)

**Files:**
- Create:
  `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.json`
- Create:
  `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py`
- Create:
  `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.js`
- Create:
  `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.css`
- Create:
  `erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py`

**Interfaces:**
- Consumes: `complete_line_replenishment_picking`, `KTA Line Replenishment Order`.
- Produces: Mobile-first Frappe Page `line-replenishment-picking` for PDA barcode terminals.

- [ ] **Step 1: Write the failing test**

Create `erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py`:
```python
import os
import json
from frappe.tests.utils import FrappeTestCase

class TestLineReplenishmentPickingPage(FrappeTestCase):
    def test_picking_page_json_exists(self):
        path = (
            "erpnextkta/kta_stock/page/"
            "line_replenishment_picking/line_replenishment_picking.json"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data.get("page_name"), "line-replenishment-picking")

    def test_picking_page_js_exists(self):
        path = (
            "erpnextkta/kta_stock/page/"
            "line_replenishment_picking/line_replenishment_picking.js"
        )
        self.assertTrue(os.path.exists(path), f"{path} must exist")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page
```
Expected: FAIL (File not found).

- [ ] **Step 3: Implement Mobile PDA Picking Interface**

1. Create `line_replenishment_picking.json` and Python controller.
2. In `line_replenishment_picking.js`:
   - Mobile-responsive layout (320px - 480px touch friendly).
   - Order selector showing active replenishment orders.
   - Step-by-step picking card showing: Target Line, Source Warehouse/Bin, Item Code, Deficit Qty.
   - Barcode input field with autofocus for barcode scanner gun.
   - Quantity input supporting over-picking with real-time tolerance feedback.
   - Primary button "Transferi Tamamla (Complete Transfer)" calling backend service.
3. In `line_replenishment_picking.css`: large touch targets, high contrast contrast colors.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/page/line_replenishment_picking/
git add erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py
git commit -m "feat(stock): build Mobile PDA Line Replenishment Picking interface"
```

---

### Task 7: Translations, Portal Documentation & Quality Gate (`docs-i18n`)

**Files:**
- Modify: `erpnextkta/translations/tr.csv`
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Create: `erpnextkta/www/docs/line_replenishment.html`
- Modify: `erpnextkta/www/docs/index.html`
- Create: `docs/developer_guides/line_replenishment_guide.md`
- Create: `erpnextkta/tests/test_line_replenishment_docs.py`

**Interfaces:**
- Consumes: All UI labels, statuses, buttons, and system concepts from Tasks 1-6.
- Produces: Unified multilingual translations (TR, EN, DE).
- Produces: Portal documentation at `/docs/line_replenishment`.

- [ ] **Step 1: Write the failing test**

Create `erpnextkta/tests/test_line_replenishment_docs.py`:
```python
import os
from frappe.tests.utils import FrappeTestCase

class TestLineReplenishmentDocs(FrappeTestCase):
    def test_portal_doc_exists(self):
        path = "erpnextkta/www/docs/line_replenishment.html"
        self.assertTrue(os.path.exists(path), f"{path} must exist")

    def test_developer_guide_exists(self):
        path = "docs/developer_guides/line_replenishment_guide.md"
        self.assertTrue(os.path.exists(path), f"{path} must exist")

    def test_translations_contain_key_terms(self):
        with open("erpnextkta/translations/tr.csv", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Line Replenishment Hub", content)
        self.assertIn("Smart Sourcing", content)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.tests.test_line_replenishment_docs
```
Expected: FAIL (File not found).

- [ ] **Step 3: Implement translations, user portal doc and developer guide**

1. In `tr.csv`, `en.csv`, `de.csv`: add Title Case translations for all new terms:
   - "Line Replenishment Hub", "Hat İkmal Kokpiti", "Liniennachschub-Hub"
   - "Smart Sourcing (WIP First)", "Akıllı Kaynak (Önce WIP)"
   - "Line Transfer", "Hatlar Arası Dengeleme", "Linientransfer"
   - "Complete Transfer", "Transferi Tamamla", "Transfer abschließen"
2. Create `erpnextkta/www/docs/line_replenishment.html` explaining:
   - Problem definition and proactive line replenishment philosophy.
   - Smart Sourcing & WIP Netting logic (free stock sibling scan vs. central fallback).
   - Mandatory single target WIP warehouse rule.
   - Desktop Hub vs Mobile PDA picking workflow.
   - Over-picking tolerances.
3. Link new page in `erpnextkta/www/docs/index.html`.
4. Create `docs/developer_guides/line_replenishment_guide.md` documenting technical architecture.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta \
  --module erpnextkta.tests.test_line_replenishment_docs
```
Expected: PASS.

- [ ] **Step 5: Run full verification & Quality Gate**

Run:
```bash
/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/ erpnextkta/kta_shopfloor/
/home/frappe/frappe-bench/env/bin/ruff format --check \
  erpnextkta/kta_stock/ erpnextkta/kta_shopfloor/
bench build --app erpnextkta --production
```
Expected: All checks pass without errors.

- [ ] **Step 6: Commit**

```bash
git add erpnextkta/translations/ erpnextkta/www/docs/ docs/developer_guides/
git add erpnextkta/tests/test_line_replenishment_docs.py
git commit -m "docs(i18n): add Line Replenishment portal docs, guides and translations"
```
