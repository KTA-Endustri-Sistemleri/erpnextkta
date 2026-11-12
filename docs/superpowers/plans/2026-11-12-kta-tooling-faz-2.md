# KTA Tooling (Kalıp & Aplikasyon Yönetimi) Faz 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kurumsal **KTA Tooling** (Enjeksiyon Kalıpları ve Krimp Aplikasyon Kalıpları) yönetimini devreye almak; `930-Tools` hiyerarşisi altında `933-Injection Molds` ve `934-Crimp Applicators` Item senkronizasyonu ile takım yatırımı, mülkiyet ve geri ödeme takibini kurmak; kalıphane kritik yedek parça tablosunu eklemek; krimp parametreleri setup föyü (`KTA Tooling Crimp Parameters`) ve makine uyumluluk tablosunu (`KTA Tooling Compatible Workstation`) devreye almak; Yaklaşım B ile mevcut 4.619 BOM'a dokunmadan terminalleri tarayarak İş Kartlarına (`Job Card Required Tooling`) otomatik takım havuzu bağlamak; tek Çalışma Kartı altında çift makine (tandem) çalışma ve kısmi arıza yönetimini (Senaryo B) devreye almak; otomatik tezgahlarda T1/T2 çift aplikatör kilidi ve manuel preslerde `OP11-0001` doppelkrimp akışını otomatikleştirmek; takım aşınma dengeleme (wear balancing) algoritmasını ve kalıphane statü/karantina kilidini kurmak; takım tipine göre (enjeksiyonda göz sayısı oranlı, krimpte parça adedi oranlı) kümülatif vuruş sayacı (`total_stroke_count`) ve canlı darboğaz kilidini (Concurrency Guard Seçenek C) kurmak.

**Architecture:**
- ERPNext `930-Tools` hiyerarşisi altına `933-Injection Molds` ve `934-Crimp Applicators` Item Group'ları eklenir.
- `KTA Tooling`, `KTA Tooling Spare Part`, `KTA Tooling Crimp Parameters` ve `KTA Tooling Compatible Workstation` DocType'ları oluşturulur. `tool_type` (`Injection Mold`, `Crimp Applicator`, vb.), `status` (`Kullanıma Hazır`, `Kalıphanede / Bakımda`, `Bilemede`, `Karantinada / Arızalı`, `Hurda / Devre Dışı`), mülkiyet ve yatırım/amortisman alanları tanımlanır. Faz 1'deki 46 `KTA Enjeksiyon Kalibi` ve `KTA Krimp Book`'taki 1.372 satır `KTA Tooling`'e taşınır. Kayıt anında `Item` kaydı otomatik senkronize edilir.
- `BOM Operation` üzerine `custom_tool_code` ve `custom_tool_code_2` eklenir (enjeksiyon için). `Job Card` üzerine `Job Card Required Tooling` alt tablosu eklenerek `before_insert` hook'u ile BOM malzemelerindeki terminaller taranıp takımlar otomatik doldurulur (Yaklaşım B).
- `create-calisma-karti` sihirbazında 2. makine (`is_istasyonu_2`) toggle'ı sunulur ve alt işlemler makine bazlı izlenir.
- `Calisma Karti Alt Operasyon Kayitlari` tablosunda `kalip_no` (T1 / 1. Takım) ve `kalip_no_2` (T2 / 2. Takım) doğrudan seçilir (Seçenek B); kalite ölçüm modalı bu değerleri otomatik devralır.
- Çift makinede kısmi arıza durumunda (Senaryo B) `release_machine_from_card` ile 2. makine serbest bırakılarak takım boşa çıkarılır, önceki üretim ve ölçüm kayıtları korunur.
- Takım vuruş sayacı enjeksiyonda `ceil(delta_qty / cavity_count)`, krimpte T1 ve T2 kalıpları için `delta_qty` formülüyle güncellenir.
- Açık kartlardaki takım meşguliyeti Seçenek C mantığıyla (sihirbazda soft uyarı rozeti, alt işlem kaydında hard kilit, amirler için loglu zorla serbest bırakma) yönetilir. Alternatif kalıplarda `total_stroke_count` en düşük olan önerilerek aşınma dengelenir.

**Tech Stack:** Frappe Framework v15, MariaDB, Python 3.12, Vue 3, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-11-12-enjeksiyon-kalip-mimarisi-design.md`

## Global Constraints

* **Target Branch:** `feat/enjeksiyon-kalip-no` / `main`.
* **Commit Message Convention:** Conventional Commits (`feat(calisma-karti): ...`, `fix(calisma-karti): ...`, `chore(translations): ...`, `test(calisma-karti): ...`).
* **Translation Rule:** All user-facing strings must be wrapped in `_()` (Python) and `__()` (JS), keeping sentences whole (no split strings), in Title Case. Translations must be populated in `en.csv`, `de.csv`, `tr.csv`.
* **Build Rule:** NEVER use `yarn build` directly. ALWAYS use `bench build --app erpnextkta --production`.
* **Non-Goal Guarantee:** Job Card completed quantity calculation (`doc.total_completed_qty = doc.for_quantity`) must remain completely untouched.

## Review Focus

1. **Dual Machine Concurrency with Single Available Copy (`available_qty: 1`):** When an operator configures 2 machines on a card and tries to add the same tool on both machines, if `available_qty == 1`, backend must block the second sub-operation with a clear error.
2. **Partial Machine Detachment Data Preservation (Senaryo B):** When `release_machine_from_card` is called for `is_istasyonu_2`, existing production quantity and measurement rows on that machine must be preserved in the card, but their concurrency lock on the tool must be freed.
3. **Cavity Calculation for Stroke Counter:** When `tool_type == "Injection Mold"` and `cavity_count` is 2, producing 500 pcs must increment `total_stroke_count` by 250. Odd quantities like 501 must ceiling to 251. For `tool_type == "Crimp Applicator"`, 500 pcs must increment by 500.
4. **Admin Override Audit Trail:** When an authorized supervisor unlocks an open tool via `admin_force_release_tool`, an audit log entry must be recorded with user ID and card name.
5. **Idempotent Item & Group Creation:** When saving `KTA Tooling`, if the linked `Item` already exists, it must be updated without throwing `DuplicateEntryError`.
6. **Zero Data Loss Migration:** The 46 existing injection molds from Faz 1 must be migrated to `KTA Tooling` with `tool_type = "Injection Mold"`, preserving all fields and relationships.

---

### Task 1: `kta_tooling` Module, `933/934` Item Groups, `KTA Tooling` Master, Crimp Parameters, Compatible Workstations & Item Sync

**Files:**
- Modify: `erpnextkta/modules.txt` (add `kta_tooling`)
- Create: `erpnextkta/patches/v3_0_3/create_933_and_934_tooling_groups.py`
- Modify: `erpnextkta/patches.txt`
- Create: `erpnextkta/kta_tooling/__init__.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling/__init__.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling/kta_tooling.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling/kta_tooling.json`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_spare_part/__init__.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_spare_part/kta_tooling_spare_part.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_spare_part/kta_tooling_spare_part.json`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_crimp_parameters/__init__.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_crimp_parameters/kta_tooling_crimp_parameters.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_crimp_parameters/kta_tooling_crimp_parameters.json`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_compatible_workstation/__init__.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_compatible_workstation/kta_tooling_compatible_workstation.py`
- Create: `erpnextkta/kta_tooling/doctype/kta_tooling_compatible_workstation/kta_tooling_compatible_workstation.json`
- Create: `erpnextkta/patches/v3_0_3/migrate_enjeksiyon_kalip_to_kta_tooling.py`
- Create: `erpnextkta/patches/v3_0_3/migrate_krimp_book_to_kta_tooling.py`
- Test: `erpnextkta/tests/test_kta_tooling_sync.py`

**Interfaces:**
- Consumes: `KTA Tooling` document events (`after_insert`, `on_update`), `KTA Enjeksiyon Kalibi` existing records, `KTA Krimp Book` existing records
- Produces: Synced `Item` record (`item_code == tool_code`, `item_group in ["933-Injection Molds", "934-Crimp Applicators"]`), migrated `KTA Tooling` records with crimp parameter sheets

- [ ] **Step 1: Write failing test for 933/934 Item Groups, KTA Tooling and Item synchronization**

```python
class TestKTAToolingSync(FrappeTestCase):
    def test_item_sync_for_injection_mold(self):
        doc = frappe.get_doc({
            "doctype": "KTA Tooling",
            "tool_code": "TEST-INJ-01",
            "tool_name": "Test Injection Mold",
            "tool_type": "Injection Mold",
            "status": "Kullanıma Hazır",
            "cavity_count": 2,
            "ownership_type": "Müşteri Mülkiyeti (Doğrudan)",
            "available_qty": 1,
        }).insert(ignore_permissions=True)

        item = frappe.get_doc("Item", "TEST-INJ-01")
        self.assertEqual(item.item_group, "933-Injection Molds")
        self.assertEqual(item.stock_uom, "Adet")
        self.assertEqual(item.is_purchase_item, 1)
        self.assertEqual(item.is_sales_item, 1)
        self.assertEqual(item.is_stock_item, 0)
        self.assertEqual(doc.linked_item_code, "TEST-INJ-01")

    def test_item_sync_for_crimp_applicator(self):
        doc = frappe.get_doc({
            "doctype": "KTA Tooling",
            "tool_code": "TEST-CRIMP-01",
            "tool_name": "Test Crimp Applicator",
            "tool_type": "Crimp Applicator",
            "status": "Kullanıma Hazır",
            "feed_type": "Yandan Besleme (Side-feed)",
            "ownership_type": "KTA Özkaynağı",
            "available_qty": 2,
            "crimp_parameters": [
                {
                    "wire_cross_section": "0.50 mm²",
                    "crimp_height_target": 1.15,
                    "crimp_height_tolerance": 0.03,
                    "min_pull_force_n": 70,
                },
                {
                    "wire_cross_section": "2 x 0.50 mm²",
                    "crimp_height_target": 1.28,
                    "crimp_height_tolerance": 0.03,
                    "min_pull_force_n": 85,
                }
            ]
        }).insert(ignore_permissions=True)

        item = frappe.get_doc("Item", "TEST-CRIMP-01")
        self.assertEqual(item.item_group, "934-Crimp Applicators")
        self.assertEqual(item.is_stock_item, 1)
        self.assertEqual(len(doc.crimp_parameters), 2)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -c "import os; os.chdir('/home/frappe/frappe-bench/sites'); import frappe; frappe.init('old.kta-endustri.com.tr'); frappe.connect(); import unittest; from erpnextkta.tests.test_kta_tooling_sync import TestKTAToolingSync; suite = unittest.TestLoader().loadTestsFromTestCase(TestKTAToolingSync); unittest.TextTestRunner(verbosity=2).run(suite)"`
Expected: FAIL.

- [ ] **Step 3: Implement patch `create_933_and_934_tooling_groups.py`**
Ensure `933-Injection Molds` and `934-Crimp Applicators` are created under parent `930-Tools`.

- [ ] **Step 4: Create `KTA Tooling`, `KTA Tooling Spare Part`, `KTA Tooling Crimp Parameters`, and `KTA Tooling Compatible Workstation` DocTypes**
Define fields: `tool_code`, `tool_name`, `tool_type`, `status` (`Kullanıma Hazır`, `Kalıphanede / Bakımda`, `Bilemede`, `Karantinada / Arızalı`, `Hurda / Devre Dışı`), `available_qty`, `ownership_type`, `customer`, `linked_item_code`, `total_investment_amount`, `reimbursement_status`, `total_stroke_count`, `maintenance_stroke_period`, `cavity_count`, `default_quality_template`, `linked_terminal`, `wire_cross_section_range`, `feed_type`, `is_primary_mold`, `spare_parts` (Table: `KTA Tooling Spare Part`), `crimp_parameters` (Table: `KTA Tooling Crimp Parameters`), `compatible_workstations` (Table: `KTA Tooling Compatible Workstation`), `disabled`, `description`.

- [ ] **Step 5: Implement `sync_item` in `kta_tooling.py`**
In `after_insert` and `on_update`, create or update matching Item in `933-Injection Molds` or `934-Crimp Applicators`. Set `is_stock_item = 0` if customer-owned, `1` if KTA-owned.

- [ ] **Step 6: Implement migration patches**
1. `migrate_enjeksiyon_kalip_to_kta_tooling.py`: Copy all existing `KTA Enjeksiyon Kalibi` records to `KTA Tooling` (`tool_type = "Injection Mold"`, `available_qty = mevcut_adet`, `cavity_count = 1`, `status = "Kullanıma Hazır"`).
2. `migrate_krimp_book_to_kta_tooling.py`: Parse `tabKTA Krimp Book` (1,372 records), create unique `KTA Tooling` applicators with their cross-sections and C/H, pull force parameters in `crimp_parameters` child table.

- [ ] **Step 7: Run test to verify it passes**
Run test suite command.
Expected: PASS.

- [ ] **Step 8: Commit**
```bash
git add erpnextkta/patches/v3_0_3/ erpnextkta/patches.txt erpnextkta/kta_calisma_karti/doctype/kta_tooling* erpnextkta/tests/test_kta_tooling_sync.py
git commit -m "feat(calisma-karti): add KTA Tooling master data model, crimp parameters and item sync"
```

---

### Task 2: BOM Operation Tooling Fields, `Job Card Required Tooling` Table & Smart Terminal Scanner (Yaklaşım B)

**Files:**
- Create: `erpnextkta/kta_calisma_karti/doctype/job_card_required_tooling/__init__.py`
- Create: `erpnextkta/kta_calisma_karti/doctype/job_card_required_tooling/job_card_required_tooling.py`
- Create: `erpnextkta/kta_calisma_karti/doctype/job_card_required_tooling/job_card_required_tooling.json`
- Create: `erpnextkta/patches/v3_0_3/add_tooling_fields_to_bom_and_job_card.py`
- Create: `erpnextkta/patches/v3_0_3/map_tooling_to_default_boms.py`
- Modify: `erpnextkta/patches.txt`
- Modify: `erpnextkta/overrides/job_card.py`
- Test: `erpnextkta/tests/test_bom_tooling_mapping.py`

**Interfaces:**
- Consumes: Active default BOMs (`is_default = 1, docstatus = 1`), `BOM Item` terminals, `KTA Tooling.linked_terminal`
- Produces: `custom_tool_code`, `custom_tool_code_2` on `BOM Operation` (enjeksiyon için); `required_tooling` child table on `Job Card` (krimp havuzu için)

- [ ] **Step 1: Write failing test for BOM and Job Card tooling mapping and smart terminal scan**

```python
class TestBomToolingMapping(FrappeTestCase):
    def test_job_card_copies_injection_tool_from_bom_operation(self):
        # Create test BOM with custom_tool_code on OP40
        # Create Job Card and verify custom_tool_code is populated

    def test_job_card_scans_bom_terminals_into_required_tooling(self):
        # Create test BOM with OP10 and items in 150-Terminals
        # Create Job Card and verify required_tooling child table is populated with matching KTA Tooling applicators
```

- [ ] **Step 2: Run test to verify it fails**
Run test command.
Expected: FAIL.

- [ ] **Step 3: Create `Job Card Required Tooling` DocType & implement custom fields patch**
Create child DocType `Job Card Required Tooling` with fields: `tool_code` (Link: `KTA Tooling`), `tool_name`, `terminal_code` (Link: `Item`), `is_primary`, `status`.
Add `custom_tool_code` and `custom_tool_code_2` (Link: `KTA Tooling`) to `BOM Operation` and `Job Card` via Frappe Custom Field API. Run auto-match for default injection BOMs (`30-0800`).

- [ ] **Step 4: Implement auto-copy and smart terminal scanner in `KTAJobCard.before_insert`**
In `KTAJobCard.before_insert`:
1. If `custom_tool_code` is not set on Job Card, copy from corresponding `BOM Operation` (Enjeksiyon).
2. For crimp/wire processing (`OP10-0000`): scan `BOM Item` records for terminals (`item_group == "150-Terminals"` or linked items), find matching `KTA Tooling` records where `linked_terminal == item_code`, and append them to `doc.required_tooling` (Yaklaşım B - Sıfır BOM Yükü).

- [ ] **Step 5: Run test to verify it passes**
Run test command.
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add erpnextkta/kta_calisma_karti/doctype/job_card_required_tooling/ erpnextkta/patches/v3_0_3/ erpnextkta/patches.txt erpnextkta/overrides/job_card.py erpnextkta/tests/test_bom_tooling_mapping.py
git commit -m "feat(calisma-karti): link tooling to BOM operations and job cards with smart terminal scanner"
```

---

### Task 3: Dual Workstation & Dual Tooling Data Model (`kalip_no_2`, `is_istasyonu_2`) & Sub-Operation Assignment (Seçenek B)

**Files:**
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti/calisma_karti.json`
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti_alt_operasyon_kayitlari/calisma_karti_alt_operasyon_kayitlari.json`
- Modify: `erpnextkta/kta_calisma_karti/api_impl/create.py`
- Modify: `erpnextkta/kta_calisma_karti/api_impl/alt_operasyon.py`
- Test: `erpnextkta/tests/test_dual_workstation_card.py`

**Interfaces:**
- Consumes: `create_calisma_karti(is_istasyonu, is_istasyonu_2, ...)`, `add_alt_operasyon_kaydi(kalip_no, kalip_no_2, ...)`
- Produces: Sub-operation row with assigned `is_istasyonu` (`Makine 1` or `Makine 2`) and mounted tools (`kalip_no` T1, `kalip_no_2` T2)

- [ ] **Step 1: Write failing test for dual workstation and dual tooling card creation**

```python
class TestDualWorkstationCard(FrappeTestCase):
    def test_create_card_with_two_workstations(self):
        # Must fail if is_istasyonu == is_istasyonu_2
        with self.assertRaises(frappe.ValidationError):
            create_calisma_karti(..., is_istasyonu="30-0801", is_istasyonu_2="30-0801")

        # Must succeed with distinct workstations
        card = create_calisma_karti(..., is_istasyonu="30-0801", is_istasyonu_2="30-0802")
        self.assertEqual(card.is_istasyonu, "30-0801")
        self.assertEqual(card.is_istasyonu_2, "30-0802")

    def test_sub_operation_stores_dual_tools_t1_and_t2(self):
        # Sub-op on OP10 records kalip_no (T1) and kalip_no_2 (T2)
        # Verify both tools are saved and point to KTA Tooling
```

- [ ] **Step 2: Run test to verify it fails**
Run test command.
Expected: FAIL.

- [ ] **Step 3: Update `calisma_karti.json` and `calisma_karti_alt_operasyon_kayitlari.json`**
Add `is_istasyonu_2` to `Calisma Karti`. In `Calisma Karti Alt Operasyon Kayitlari`, add `is_istasyonu`, `kalip_no_2` (Link: `KTA Tooling`), and ensure `kalip_no` option points to `KTA Tooling`.

- [ ] **Step 4: Update `create.py` and `alt_operasyon.py`**
Validate `is_istasyonu != is_istasyonu_2`. When adding sub-op on dual-station card, validate selected machine is either `is_istasyonu` or `is_istasyonu_2`. If single station card, auto-assign `is_istasyonu`. Save both `kalip_no` and `kalip_no_2`.

- [ ] **Step 5: Run test to verify it passes**
Run test command.
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add erpnextkta/kta_calisma_karti/doctype/ erpnextkta/kta_calisma_karti/api_impl/ erpnextkta/tests/test_dual_workstation_card.py
git commit -m "feat(calisma-karti): add dual workstation and dual tooling support on sub-operations"
```

---

### Task 4: Concurrency Guard (Option C), Maintenance Status Lock & Wear Balancing

**Files:**
- Create: `erpnextkta/kta_calisma_karti/api_impl/concurrency.py`
- Modify: `erpnextkta/kta_calisma_karti/api_impl/alt_operasyon.py`
- Modify: `erpnextkta/kta_calisma_karti/api.py`
- Test: `erpnextkta/tests/test_tooling_concurrency_guard.py`

**Interfaces:**
- Consumes: `KTA Tooling.available_qty`, `KTA Tooling.status`, `KTA Tooling.total_stroke_count`, active cards in `tabCalisma Karti Alt Operasyon Kayitlari`
- Produces: `assert_tooling_concurrency(tool_code, current_card_name, workstation)`, `check_tool_availability`, `get_wear_balanced_tool_recommendation`, `admin_force_release_tool`

- [ ] **Step 1: Write failing test for concurrency guard and admin force release**

```python
class TestToolingConcurrencyGuard(FrappeTestCase):
    def test_single_copy_tool_cannot_run_concurrently(self):
        # Tool with available_qty = 1
        # Card 1 adds sub-op with Tool X -> Success
        # Card 2 attempts to add sub-op with Tool X -> Must fail with ValidationError
        # Card 1 finishes -> Card 2 can now add Tool X -> Success

    def test_admin_force_release_with_audit_trail(self):
        # Supervisor releases tool from hung card
        # Audit log written, tool becomes available
```

- [ ] **Step 2: Run test to verify it fails**
Run test command.
Expected: FAIL.

- [ ] **Step 3: Implement `concurrency.py`**
Implement `assert_tooling_concurrency`, `check_tool_availability`, and `admin_force_release_tool` with role check `KTA Çalışma Kartı Yöneticisi` and logger entry.

- [ ] **Step 4: Integrate guard into `alt_operasyon.py`**
Call `assert_tooling_concurrency` on `add_alt_operasyon_kaydi` and `update_alt_operasyon_kaydi`.

- [ ] **Step 5: Run test to verify it passes**
Run test command.
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add erpnextkta/kta_calisma_karti/api_impl/ erpnextkta/kta_calisma_karti/api.py erpnextkta/tests/test_tooling_concurrency_guard.py
git commit -m "feat(calisma-karti): implement tooling concurrency guard and admin force release"
```

---

### Task 5: Cumulative Stroke Counter (`total_stroke_count`) with Cavity & Unit Scaling

**Files:**
- Modify: `erpnextkta/kta_calisma_karti/api_impl/alt_operasyon.py`
- Test: `erpnextkta/tests/test_tooling_stroke_counter.py`

**Interfaces:**
- Consumes: `islem_adedi_1` updates on `alt_operasyon_kayitlari`, `KTA Tooling.cavity_count`, `KTA Tooling.tool_type`
- Produces: Incremented `KTA Tooling.total_stroke_count`

- [ ] **Step 1: Write failing test for stroke counter calculation**

```python
class TestToolingStrokeCounter(FrappeTestCase):
    def test_injection_stroke_counter_scaled_by_cavity_count(self):
        # Injection Mold with cavity_count = 2, initial baski = 0
        # Produce 500 pcs -> baski must become 250
        # Produce additional 101 pcs -> delta 101 / 2 = ceil(50.5) = 51 -> total 301

    def test_crimp_stroke_counter_unit_based(self):
        # Crimp Applicator: 500 pcs -> baski must become 500
```

- [ ] **Step 2: Run test to verify it fails**
Run test command.
Expected: FAIL.

- [ ] **Step 3: Implement `update_tool_stroke_counter` in `alt_operasyon.py`**
Calculate delta quantity between old and new `islem_adedi_1`. If `tool_type == "Injection Mold"`, compute `math.ceil(delta / cavity_count)`. Else compute `delta`. Update `total_stroke_count` atomically via parameterized SQL.

- [ ] **Step 4: Run test to verify it passes**
Run test command.
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/kta_calisma_karti/api_impl/alt_operasyon.py erpnextkta/tests/test_tooling_stroke_counter.py
git commit -m "feat(calisma-karti): increment tooling stroke counter based on tool type and cavity"
```

---

### Task 6: Partial Machine Detachment API (Senaryo B)

**Files:**
- Create/Modify: `erpnextkta/kta_calisma_karti/api_impl/cards.py`
- Modify: `erpnextkta/kta_calisma_karti/api.py`
- Test: `erpnextkta/tests/test_partial_machine_release.py`

**Interfaces:**
- Consumes: `release_machine_from_card(calisma_karti_name, machine_name)`
- Produces: Cleared `is_istasyonu_2`, preserved production quantities & QC logs, freed tool lock

- [ ] **Step 1: Write failing test for partial machine release**

```python
class TestPartialMachineRelease(FrappeTestCase):
    def test_release_machine_preserves_records_and_frees_tool(self):
        # Card with 2 machines (30-0801, 30-0802).
        # Sub-op on 30-0802 with 100 pcs and QC measurements.
        # Call release_machine_from_card(..., "30-0802")
        # Assert is_istasyonu_2 is None
        # Assert sub-op on 30-0802 is preserved with islem_durumu = "Makine Ayrıldı"
        # Assert tool from 30-0802 can now be used on another card
```

- [ ] **Step 2: Run test to verify it fails**
Run test command.
Expected: FAIL.

- [ ] **Step 3: Implement `release_machine_from_card` in `cards.py`**
Validate machine is `is_istasyonu_2`, mark child rows as detached (`islem_durumu = "Makine Ayrıldı"`), set `doc.is_istasyonu_2 = None`, save card.

- [ ] **Step 4: Run test to verify it passes**
Run test command.
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/kta_calisma_karti/api_impl/cards.py erpnextkta/kta_calisma_karti/api.py erpnextkta/tests/test_partial_machine_release.py
git commit -m "feat(calisma-karti): add partial machine release API preserving logs"
```

---

### Task 7: Frontend UI Updates (`create-calisma-karti` & `view-calisma-karti`)

**Files:**
- Modify: `erpnextkta/public/create-calisma-karti/components/StepWorkstation.vue`
- Modify: `erpnextkta/public/create-calisma-karti/App.vue`
- Modify: `erpnextkta/public/view-calisma-karti/composables/prompts/alt_operasyon.ts`
- Modify: `erpnextkta/public/view-calisma-karti/composables/dialogs/useKrimpDialogs.ts`
- Modify: `erpnextkta/public/view-calisma-karti/composables/dialogs/useHurdaDialogs.ts`
- Modify: `erpnextkta/public/view-calisma-karti/views/AltOperasyonView.vue`

**Interfaces:**
- Consumes: `check_tool_availability`, `release_machine_from_card`, `get_kta_tooling_crimp_details`, `get_wear_balanced_tool_recommendation`
- Produces: Dual workstation selector in wizard with soft warning badge, machine and T1/T2 tool selection in sub-op dialog, auto-prefilled krimp dialog with color badges, scrap machine attribution, release button in header

- [ ] **Step 1: Update `StepWorkstation.vue` in `create-calisma-karti`**
Add toggle for second machine, filter dropdown for workstations (excluding 1st machine). Show soft warning badge if suggested tool is currently active in another card.

- [ ] **Step 2: Update `App.vue` in `create-calisma-karti`**
Send `is_istasyonu_2` in payload to `create_calisma_karti`.

- [ ] **Step 3: Update `alt_operasyon.ts` in `view-calisma-karti` (Seçenek B)**
1. If card has `is_istasyonu_2`, add `is_istasyonu` field to dialog options (`[Makine 1, Makine 2]`).
2. Expose `kalip_no` (T1 / 1. Takım) and `kalip_no_2` (T2 / 2. Takım) fields with contextual labels:
   - For OP40: "1. Makine Kalıp No" and "2. Makine Kalıp No" (filtered by `tool_type == 'Injection Mold'`).
   - For OP10: "T1 Kalıp No (Sol Uç)" and "T2 Kalıp No (Sağ Uç)" (filtered by `tool_type == 'Crimp Applicator'`).
   - For OP11: "Manuel Pres Kalıp No" (filtered by `tool_type == 'Crimp Applicator'`).

- [ ] **Step 4: Update `useKrimpDialogs.ts` in `view-calisma-karti`**
1. When krimp measurement dialog opens, prefill `kalip_no` and `yon_2_kalip_no` directly from the parent alt operation row (`satir.kalip_no`, `satir.kalip_no_2`).
2. Populate kalıp options with color-coded status badges: `🟢 {kalip_no} (Boşta - Önerilen)`, `🟡 {kalip_no} (Alternatif)`, `🔴 {kalip_no} (Meşgul: {makine})`.
3. Fetch setup parameters from `KTA Tooling Crimp Parameters` via `get_kta_tooling_crimp_details`, auto-filling C/H, tolerance, pull force, and dial step.

- [ ] **Step 5: Update `useHurdaDialogs.ts` and `AltOperasyonView.vue`**
In `useHurdaDialogs.ts`, add machine selection if dual workstation. In `AltOperasyonView.vue`, add "2. Makineyi Serbest Bırak" action in header for dual machine cards.

- [ ] **Step 6: Run production build check**
Run: `bench build --app erpnextkta --production`
Expected: Exit code 0, 0 build errors.

- [ ] **Step 7: Commit**
```bash
git add erpnextkta/public/create-calisma-karti/ erpnextkta/public/view-calisma-karti/
git commit -m "feat(calisma-karti): add dual machine UI controls, sub-op tooling fields and krimp setup prefill"
```

---

### Task 8: Translations, Comprehensive Verification & Test Suite

**Files:**
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/translations/tr.csv`
- Create: `erpnextkta/tests/test_kta_tooling_faz2_e2e.py`

**Interfaces:**
- End-to-end verification of all Phase 2 features

- [ ] **Step 1: Add all new strings in Title Case to translation CSVs**
- "933-Injection Molds" -> "933-Enjeksiyon Kalıpları" / "933-Spritzgussformen"
- "934-Crimp Applicators" -> "934-Krimp Aplikasyon Kalıpları" / "934-Crimp-Applikatoren"
- "KTA Tooling" -> "KTA Takım / Kalıp" / "KTA Werkzeug"
- "2. İş İstasyonu" -> "2nd Workstation" / "2. Arbeitsplatz"
- "Göz Sayısı / Cavity" -> "Cavity Count" / "Kavitätenanzahl"
- "Toplam Baskı Adedi (Vuruş)" -> "Total Stroke Count" / "Gesamthubzahl"
- "2. Makineyi Serbest Bırak" -> "Release 2nd Machine" / "2. Maschine freigeben"
- "Takım/Kalıp {0} şu anda {1} numaralı çalışma kartında ({2} operatörü, {3} makinesi) kullanımdadır. Fabrikadaki mevcut adet: {4}." -> Full translated sentence without splitting.

- [ ] **Step 2: Write end-to-end integration test suite `test_kta_tooling_faz2_e2e.py`**
Test full lifecycle:
1. Dual machine card creation with `is_istasyonu` and `is_istasyonu_2`.
2. Sub-operation 1 on Machine 1, Sub-operation 2 on Machine 2.
3. Concurrency guard blocking 3rd card with same single-copy tool.
4. Stroke counter incrementing scaled by cavity count for injection mold and 1:1 for applicator.
5. Machine 2 release (Senaryo B) freeing tool while preserving historical production and QC logs.
6. Admin force release audit trail.

- [ ] **Step 3: Run all backend test suites**
Run test command for both existing tests and `test_kta_tooling_faz2_e2e.py`.
Expected: ALL PASS.

- [ ] **Step 4: Execute production build check**
Run: `bench build --app erpnextkta --production`
Expected: Exit code 0, 0 build errors.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/translations/ erpnextkta/tests/test_kta_tooling_faz2_e2e.py
git commit -m "test(calisma-karti): add end-to-end test suite and translations for KTA Tooling Phase 2"
```
