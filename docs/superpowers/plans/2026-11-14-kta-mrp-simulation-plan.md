# KTA MRP Görsel Simülasyon Senaryosu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a robust, idempotent visual simulation scenario for the `kta_mrp` module in Frappe/ERPNext (`erpnextkta`), complete with master data, flat BOMs, capacity limits, supply pipeline, demand, carry-over, console narrative walkthrough, and automated integration tests.

**Architecture:** A standalone Python package `erpnextkta.mrp_simulation` containing constants, dynamic date math, a reverse-dependency cleaner, a structured seeder, a narrative console output formatter, and automated tests. Executable via `bench execute` and VS Code tasks.

**Tech Stack:** Frappe Framework v15, ERPNext v15, Python 3.11, Docker, `kta_mrp` engine.

**Spec:** [2026-11-14-kta-mrp-simulation-design.md](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-14-kta-mrp-simulation-design.md)

## Global Constraints

- **No Sub-Assemblies (Yarı Mamul Yoktur):** All BOMs are strictly flat; all components attach directly to the Finished Good.
- **Work Order skip_transfer = 1:** All Work Orders must have `skip_transfer = 1`.
- **Capacity Source:** Capacity is read from `Item.custom_weekly_production` and `group_capacity`, never from `Workstation`.
- **Item Meta Flags:** `custom_ara_malzeme_grubu` must be `"ÜRÜN"` for FG and `"HAMMADDE"` for RM.
- **Supplier Strategy:** Single-supplier items must have `custom_sourcing_strategy = "Varsayılan Tedarikçi (%100)"`.
- **PR Logistics Overrides:** `workflow_state == 'Yolda'` requires `tahmini_varis_tarihi`; `Gümrüklemede` requires `custom_gumruk_islem_baslama_tarihi`.
- **Warehouse:** Use `Stores - TEST` (do not create temporary warehouses to avoid ORM deletion locks).
- **Naming Conventions:** Strict codes: `URUN-01`, `URUN-02`, `HAMMADDE-01` .. `HAMMADDE-07`, `MUSTERI-AVRUPA`, `MUSTERI-YERLI`, `TEDARIKCI-ITHALAT`, `TEDARIKCI-YERLI`.
- **Conventional Commits:** `<type>(<scope>): <subject>` format.

## Review Focus

1. **Idempotent Execution:** Calling `seed()` when simulation data already exists must not crash with duplicate record errors (must auto-clean first).
2. **Cancellation Before Deletion:** Cancelling submitted documents (`Stock Entry`, `Work Order`, `Sales Order`, `Purchase Order`, `Material Request`) before deleting to prevent Frappe ORM `DocstatusTransitionError`.
3. **Negative Stock Guard:** Temporarily setting `allow_negative_stock = 1` in `Stock Settings` during FG manufacture stock entry and restoring it in a `finally` block even on failure.
4. **Mandatory Logistics Fields:** Populating `tahmini_varis_tarihi` on `Yolda` PR and `custom_gumruk_islem_baslama_tarihi` on `Gümrüklemede` PR to satisfy `KTAPurchaseReceipt` validate hooks.
5. **Year Boundary ISO Week Math:** Handling ISO week transitions cleanly using `datetime.fromisocalendar()` and `isocalendar()` without string parsing assumptions.

---

### Task 1: Module Scaffold, Constants, and Date Helpers

**Files:**
- Create: `erpnextkta/mrp_simulation/__init__.py`
- Create: `erpnextkta/mrp_simulation/constants.py`
- Create: `erpnextkta/mrp_simulation/dates.py`
- Create: `erpnextkta/mrp_simulation/test_dates.py`

**Interfaces:**
- Consumes: `frappe.utils.getdate`, `datetime.date`, `datetime.timedelta`
- Produces: 
  - `constants.COMPANY`, `constants.WAREHOUSE`, `constants.CUSTOMERS`, `constants.SUPPLIERS`, `constants.ITEMS`, `constants.BOMS`
  - `dates.get_simulation_dates() -> SimulationSchedule` with `.w_current_monday`, `.w_next_monday`, `.w_plus_2_monday`, `.so_avrupa_delivery_date`, `.so_yerli_delivery_date`, `.po_schedule_date`, `.pr_yolda_eta`, `.pr_gumruk_start_date`, `.mr_schedule_date`

- [ ] **Step 1: Write the failing test for simulation dates**

```python
# erpnextkta/mrp_simulation/test_dates.py
import unittest
from datetime import date
from erpnextkta.mrp_simulation.dates import get_simulation_dates

class TestSimulationDates(unittest.TestCase):
    def test_dates_alignment(self):
        sched = get_simulation_dates(base_date=date(2026, 11, 16)) # Monday of W47
        self.assertEqual(sched.w_current_monday, date(2026, 11, 16))
        # MUSTERI-AVRUPA: delivery_date - 12 days = W_CURRENT_START
        self.assertEqual(sched.so_avrupa_delivery_date, date(2026, 11, 28)) # 16 + 12 = 28
        # MUSTERI-YERLI: delivery_date - 4 days = W_CURRENT_START
        self.assertEqual(sched.so_yerli_delivery_date, date(2026, 11, 20)) # 16 + 4 = 20
        # PO in W_NEXT (W+1)
        self.assertEqual(sched.w_next_monday, date(2026, 11, 23))
        self.assertEqual(sched.po_schedule_date, date(2026, 11, 25))
        # Yolda PR ETA in W+2
        self.assertEqual(sched.w_plus_2_monday, date(2026, 11, 30))
        self.assertEqual(sched.pr_yolda_eta, date(2026, 12, 2))
        # MR in W_NEXT (W+1)
        self.assertEqual(sched.mr_schedule_date, date(2026, 11, 24))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.mrp_simulation.test_dates`
Expected: FAIL with "ModuleNotFoundError" or "get_simulation_dates not found"

- [ ] **Step 3: Implement `dates.py`, `constants.py`, and `__init__.py`**

- Implement `erpnextkta/mrp_simulation/constants.py` with all simulation identifiers:
  - `COMPANY = "TEST"`
  - `WAREHOUSE = "Stores - TEST"`
  - Customer definitions (`MUSTERI-AVRUPA`, `MUSTERI-YERLI`) with lead times
  - Supplier definitions (`TEDARIKCI-ITHALAT`, `TEDARIKCI-YERLI`)
  - Workstations (`Kesim Hattı`, `Krimp Presi`, `Montaj Masası`) & Operations (`Kablo Kesim`, `Terminal Krimp`, `Grup Montaj`)
  - Items metadata:
    - `URUN-01`: cap 500, UOM "Adet", group "KABLO GRUBU", ara "ÜRÜN"
    - `URUN-02`: cap 400, UOM "Adet", group "KABLO GRUBU", ara "ÜRÜN"
    - `HAMMADDE-01`: UOM "Metre", ara "HAMMADDE", supplier "TEDARIKCI-YERLI"
    - `HAMMADDE-02`: UOM "Adet", ara "HAMMADDE", supplier "TEDARIKCI-YERLI"
    - `HAMMADDE-03`: UOM "Adet", ara "HAMMADDE", supplier "TEDARIKCI-ITHALAT"
    - `HAMMADDE-04`: UOM "Adet", ara "HAMMADDE", supplier "TEDARIKCI-ITHALAT"
    - `HAMMADDE-05`: UOM "Adet", ara "HAMMADDE", supplier "TEDARIKCI-ITHALAT"
    - `HAMMADDE-06`: UOM "Adet", ara "HAMMADDE", supplier "TEDARIKCI-YERLI"
    - `HAMMADDE-07`: UOM "Adet", ara "HAMMADDE", supplier "TEDARIKCI-ITHALAT", MOQ 1000, pack 250
- Implement `erpnextkta/mrp_simulation/dates.py`:
  - `get_simulation_dates(base_date=None) -> SimulationSchedule`
  - Calculates `w_current_monday` (Monday of ISO week for `base_date or today()`), `w_next_monday = w_current_monday + 7 days`, `w_plus_2_monday = w_current_monday + 14 days`.
  - Calculates delivery dates so `delivery_date - (prod_time + deliv_time)` lands exactly on `w_current_monday`.
- Expose entry points in `erpnextkta/mrp_simulation/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.mrp_simulation.test_dates`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/mrp_simulation/
git commit -m "feat(mrp_simulation): scaffold module, constants and date helpers"
```

---

### Task 2: Cleaner Service (Reverse-Dependency Teardown)

**Files:**
- Create: `erpnextkta/mrp_simulation/cleaner.py`
- Test: Integration step in `test_simulation.py`

**Interfaces:**
- Consumes: `frappe`, `constants`
- Produces: `cleaner.clean() -> dict` (summary of deleted document counts)

- [ ] **Step 1: Write `cleaner.py` with safe reverse deletion order**

Implement `cleaner.clean()`:
1. Cancel & delete `Stock Entry` where `purpose in ('Manufacture', 'Material Receipt')` and items in simulation items list.
2. Cancel & delete `Work Order` where `production_item in ('URUN-01', 'URUN-02')`.
3. Cancel & delete `Purchase Receipt` where `supplier in ('TEDARIKCI-ITHALAT', 'TEDARIKCI-YERLI')`.
4. Cancel & delete `Purchase Order` where `supplier in ('TEDARIKCI-ITHALAT', 'TEDARIKCI-YERLI')`.
5. Cancel & delete `Sales Order` where `customer in ('MUSTERI-AVRUPA', 'MUSTERI-YERLI')`.
6. Cancel & delete `Material Request` where `material_request_type = 'Manufacture'` and item in `('URUN-01', 'URUN-02')`.
7. Delete `BOM` where `item in ('URUN-01', 'URUN-02')` (cancelling first if submitted).
8. Delete `Item Price` for simulation items.
9. Delete `Item` for all 9 simulation items (`URUN-01`, `URUN-02`, `HAMMADDE-01`..`07`).
10. Delete `Workstation` (`Kesim Hattı`, `Krimp Presi`, `Montaj Masası`) and `Operation` (`Kablo Kesim`, `Terminal Krimp`, `Grup Montaj`).
11. Delete `KTA Sevk Parametreleri` for `MUSTERI-AVRUPA` and `MUSTERI-YERLI`.
12. Delete `Customer` (`MUSTERI-AVRUPA`, `MUSTERI-YERLI`) and their `Address` records.
13. Delete `Supplier` (`TEDARIKCI-ITHALAT`, `TEDARIKCI-YERLI`) and their `Address` records.
14. Ensure `frappe.db.commit()` is called and return summary dictionary.

- [ ] **Step 2: Verify `clean()` executes cleanly on empty/existing database**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost execute erpnextkta.mrp_simulation.cleaner.clean`
Expected: Output showing 0 records deleted (or clean run), no exceptions raised.

- [ ] **Step 3: Commit**

```bash
git add erpnextkta/mrp_simulation/cleaner.py
git commit -m "feat(mrp_simulation): implement reverse-dependency cleaner service"
```

---

### Task 3: Master Data & BOM Seeding

**Files:**
- Create: `erpnextkta/mrp_simulation/seeder.py` (master data + BOM sections)

**Interfaces:**
- Consumes: `constants`, `cleaner.clean`
- Produces:
  - `seeder.seed_master_data()` -> creates Customers, Sevk Parametreleri, Suppliers, Workstations, Operations, Items, Item Prices, Item Suppliers
  - `seeder.seed_boms()` -> creates and submits BOMs for `URUN-01` and `URUN-02`

- [ ] **Step 1: Implement `seed_master_data()` in `seeder.py`**

- Ensure Item Group `"KABLO GRUBU"` exists under `"All Item Groups"`.
- Ensure UOMs `"Adet"` and `"Metre"` exist.
- Create Suppliers:
  - `TEDARIKCI-ITHALAT` (supplier_group: "All Supplier Groups")
  - `TEDARIKCI-YERLI` (supplier_group: "All Supplier Groups")
- Create Customers:
  - `MUSTERI-AVRUPA` (customer_group: "All Customer Groups")
  - `MUSTERI-YERLI` (customer_group: "All Customer Groups")
- Create `KTA Sevk Parametreleri`:
  - `MUSTERI-AVRUPA`: `production_time = 7`, `delivery_time = 5`
  - `MUSTERI-YERLI`: `production_time = 3`, `delivery_time = 1`
- Create Workstations & Operations:
  - Workstations: `Kesim Hattı`, `Krimp Presi`, `Montaj Masası`
  - Operations: `Kablo Kesim`, `Terminal Krimp`, `Grup Montaj`
- Create Finished Goods Items:
  - `URUN-01`: `item_group = "KABLO GRUBU"`, `stock_uom = "Adet"`, `is_stock_item = 1`, `custom_weekly_production = 500`, `custom_ara_malzeme_grubu = "ÜRÜN"`, `include_item_in_manufacturing = 1`.
  - `URUN-02`: `item_group = "KABLO GRUBU"`, `stock_uom = "Adet"`, `is_stock_item = 1`, `custom_weekly_production = 400`, `custom_ara_malzeme_grubu = "ÜRÜN"`, `include_item_in_manufacturing = 1`.
- Create Raw Material Items:
  - For each `HAMMADDE-01` .. `HAMMADDE-07`: `stock_uom` (Metre for 01, Adet for others), `custom_ara_malzeme_grubu = "HAMMADDE"`, `custom_sourcing_strategy = "Varsayılan Tedarikçi (%100)"`, supplier linked in `Item Supplier` child table.
  - For `HAMMADDE-07`: `min_order_qty = 1000`, `custom_paket_miktari = 250`, `lead_time_days = 14`.
- Create Item Prices (buying price list = "Standard Buying", rate = 1.0, currency = "EUR").

- [ ] **Step 2: Implement `seed_boms()` in `seeder.py`**

- Create flat BOM for `URUN-01` (1 Adet):
  - Items: `HAMMADDE-01` (2.0 Mtr), `HAMMADDE-02` (4 Nos), `HAMMADDE-03` (1 Nos), `HAMMADDE-06` (1 Nos).
  - Operations: Kesim (2 min), Krimp (3 min), Montaj (5 min) mapped to Workstations.
  - Set `is_default = 1`, `is_active = 1`, submit (`docstatus = 1`).
- Create flat BOM for `URUN-02` (1 Adet):
  - Items: `HAMMADDE-01` (1.5 Mtr), `HAMMADDE-04` (2 Nos), `HAMMADDE-05` (1 Nos), `HAMMADDE-07` (2 Nos).
  - Operations: Kesim (2 min), Krimp (3 min), Montaj (4 min) mapped to Workstations.
  - Set `is_default = 1`, `is_active = 1`, submit (`docstatus = 1`).

- [ ] **Step 3: Test master data & BOM creation via execution**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost execute erpnextkta.mrp_simulation.seeder.test_seed_master`
Expected: Output showing master data and BOMs created without errors.

- [ ] **Step 4: Commit**

```bash
git add erpnextkta/mrp_simulation/seeder.py
git commit -m "feat(mrp_simulation): implement master data and flat BOM seeding"
```

---

### Task 4: Supply Pipeline Seeding (Stock, PO, PR Yolda, Antrepo, Gümrük)

**Files:**
- Modify: `erpnextkta/mrp_simulation/seeder.py` (supply pipeline section)

**Interfaces:**
- Consumes: `dates.get_simulation_dates()`, `constants`
- Produces: `seeder.seed_supply_pipeline(sched)`

- [ ] **Step 1: Implement `seed_supply_pipeline(sched)` in `seeder.py`**

1. **Free Stock:**
   - Create submitted `Stock Entry` (purpose: `"Material Receipt"`):
     - `HAMMADDE-01`: 500 Metre at `Stores - TEST` (valuation rate 1.0)
     - `HAMMADDE-06`: 2000 Adet at `Stores - TEST` (valuation rate 1.0)
2. **Open Purchase Order:**
   - Create submitted `Purchase Order` (`docstatus = 1`):
     - Supplier: `TEDARIKCI-YERLI`
     - Item: `HAMMADDE-02`, qty = 1000 Adet, rate = 1.0, schedule_date = `sched.po_schedule_date` (in W+1)
3. **In-Transit Purchase Receipt (Yolda):**
   - Create draft `Purchase Receipt` (`docstatus = 0`):
     - Supplier: `TEDARIKCI-ITHALAT`
     - Workflow state: `"Yolda"`
     - `tahmini_varis_tarihi` = `sched.pr_yolda_eta` (in W+2)
     - Item: `HAMMADDE-03`, qty = 500 Adet, rate = 1.0
4. **Bonded Warehouse Purchase Receipt (Antrepoda):**
   - Create draft `Purchase Receipt` (`docstatus = 0`):
     - Supplier: `TEDARIKCI-ITHALAT`
     - Workflow state: `"Antrepoda"`
     - Item: `HAMMADDE-04`, qty = 800 Adet, rate = 1.0
5. **Customs Clearance Purchase Receipt (Gümrüklemede):**
   - Create draft `Purchase Receipt` (`docstatus = 0`):
     - Supplier: `TEDARIKCI-ITHALAT`
     - Workflow state: `"Gümrüklemede"`
     - `custom_gumruk_islem_baslama_tarihi` = `sched.pr_gumruk_start_date`
     - Item: `HAMMADDE-05`, qty = 400 Adet, rate = 1.0

- [ ] **Step 2: Test supply pipeline creation via execution**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost execute erpnextkta.mrp_simulation.seeder.test_seed_supply`
Expected: All 5 supply transactions created with correct workflow states and quantities.

- [ ] **Step 3: Commit**

```bash
git add erpnextkta/mrp_simulation/seeder.py
git commit -m "feat(mrp_simulation): implement 7-state raw material supply pipeline"
```

---

### Task 5: Demand, WIP, Stock-Covered & Carry-Over Seeding

**Files:**
- Modify: `erpnextkta/mrp_simulation/seeder.py` (demand & WIP section)

**Interfaces:**
- Consumes: `dates.get_simulation_dates()`, `constants`
- Produces: `seeder.seed_demand_and_wip(sched)`

- [ ] **Step 1: Implement `seed_demand_and_wip(sched)` in `seeder.py`**

1. **Finished Goods Stock Creation (`stock_covered = 100` for URUN-01):**
   - Create completed `Work Order` for `URUN-01` (qty = 100, `skip_transfer = 1`).
   - Temporarily toggle `allow_negative_stock = 1` in `Stock Settings`.
   - In `try-finally`: create and submit `Stock Entry (Manufacture)` for 100 pcs of `URUN-01` to `Stores - TEST`.
   - Update Work Order `produced_qty = 100`, status = `"Completed"`.
   - Restore original `allow_negative_stock` value.
2. **Sales Orders (Week 1 Demand):**
   - `MUSTERI-AVRUPA`: SO for `URUN-01`, qty = 500 Adet, `delivery_date = sched.so_avrupa_delivery_date`. Submit (`docstatus = 1`).
   - `MUSTERI-YERLI`: SO for `URUN-02`, qty = 300 Adet, `delivery_date = sched.so_yerli_delivery_date`. Submit (`docstatus = 1`).
3. **Open Work Order (WIP for URUN-02):**
   - Create and submit `Work Order` (`docstatus = 1`):
     - Item: `URUN-02`, qty = 150 Adet, `skip_transfer = 1`, status = `"In Process"`.
     - Planned start date = `sched.w_current_monday`.
4. **Internal Demand Material Request (Week 2 for URUN-02):**
   - Create and submit `Material Request` (`docstatus = 1`):
     - Type: `"Manufacture"`, item: `URUN-02`, qty = 100 Adet, `schedule_date = sched.mr_schedule_date` (in W+1).

- [ ] **Step 2: Test demand and WIP seeding via execution**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost execute erpnextkta.mrp_simulation.seeder.test_seed_demand`
Expected: FG stock created, SOs submitted, Open WO created, MR submitted.

- [ ] **Step 3: Commit**

```bash
git add erpnextkta/mrp_simulation/seeder.py
git commit -m "feat(mrp_simulation): implement demand, WIP, stock-covered and carry-over data"
```

---

### Task 6: Narrative Console Walkthrough & Top-level Orchestrator

**Files:**
- Modify: `erpnextkta/mrp_simulation/seeder.py`
- Modify: `erpnextkta/mrp_simulation/__init__.py`
- Modify: `.vscode/tasks.json`

**Interfaces:**
- Consumes: `seeder.seed()`, `cleaner.clean()`
- Produces:
  - Top-level `erpnextkta.mrp_simulation.seeder.seed()` with full rich narrative output.
  - VS Code tasks: `Bench: Seed MRP Simulation` and `Bench: Clean MRP Simulation`.

- [ ] **Step 1: Implement the narrative console output in `seeder.seed()`**

Format the console banner with:
- Summary of created records (Customers, Items, BOMs, Orders, Receipts).
- 4-point narrative explanation ("çocuğa anlatır gibi"):
  1. Müşteriler ve Sevk Süreleri (Avrupa 12 gün, Yerli 4 gün önce PSW başlangıcı).
  2. Fabrika Kapasitesi ve Devir (700 talep, 500 tavan, 200 sonraki haftaya carry-over).
  3. Stoktan Karşılama (URUN-01 için 500 sipariş - 100 hazır mamul = 400 üretilecek).
  4. 7 Hammadde Nerede? (Ortak kablo pegging, Açık PO, Yolda ETA, Antrepo havuzu, Gümrükleme, Serbest stok, Kritik açık -> Önerilen PO).
- Actionable next steps pointing to Desk pages:
  - "Kapasite Planlama Raporu"
  - "Material Requirement" Matrisi

- [ ] **Step 2: Add VS Code tasks to `.vscode/tasks.json`**

Add tasks:
- `Bench: Seed MRP Simulation`: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost execute erpnextkta.mrp_simulation.seeder.seed`
- `Bench: Clean MRP Simulation`: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost execute erpnextkta.mrp_simulation.cleaner.clean`

- [ ] **Step 3: Commit**

```bash
git add erpnextkta/mrp_simulation/seeder.py erpnextkta/mrp_simulation/__init__.py .vscode/tasks.json
git commit -m "feat(mrp_simulation): add console narrative output and VS Code tasks"
```

---

### Task 7: Automated Integration Tests & End-to-End Verification

**Files:**
- Create: `erpnextkta/mrp_simulation/test_simulation.py`

**Interfaces:**
- Consumes: `seeder.seed()`, `cleaner.clean()`, `capacity.build_capacity_plan()`, `service.get_material_requirements()`
- Produces: Passing automated test asserting all mathematical and supply states against live DB.

- [ ] **Step 1: Write integration test `test_simulation.py`**

```python
# erpnextkta/mrp_simulation/test_simulation.py
import unittest
import frappe
from erpnextkta.mrp_simulation.seeder import seed
from erpnextkta.mrp_simulation.cleaner import clean
from erpnextkta.mrp_simulation.dates import get_simulation_dates
from erpnextkta.kta_mrp.mrp_engine.weeks import week_key
from erpnextkta.kta_mrp.mrp_engine.capacity import build_capacity_plan
from erpnextkta.kta_mrp.mrp_engine.service import get_material_requirements

class TestMrpSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        clean()
        seed()

    @classmethod
    def tearDownClass(cls):
        clean()

    def test_capacity_plan_700_500_200(self):
        sched = get_simulation_dates()
        w_cur = week_key(sched.w_current_monday)
        w_next = week_key(sched.w_next_monday)
        
        plan_data = build_capacity_plan()
        # Verify Week 1 Group Capacity
        self.assertEqual(plan_data["group_capacity"].get("KABLO GRUBU"), 500)
        
        # Verify Week 1 Total Demand = 700 (400 URUN-01 + 150 URUN-02 + 150 WO URUN-02)
        total_w1_demand = plan_data["item_week_demand"]["URUN-01"][w_cur] + plan_data["item_week_demand"]["URUN-02"][w_cur] + plan_data["wo_plan"]["URUN-02"][w_cur]
        self.assertEqual(total_w1_demand, 700)
        
        # Verify Week 1 Cap Leveling Produces 500, Carries 200 to Week 2
        w1_level = sum(plan_data["plan"][item][w_cur] for item in ("URUN-01", "URUN-02"))
        self.assertEqual(w1_level, 500)
        
        # Verify Week 2 Internal Demand = 100 for URUN-02
        self.assertEqual(plan_data["kanban_plan"]["URUN-02"][w_next], 100)

    def test_material_requirements_and_pegging(self):
        result = get_material_requirements({}, include_po=True)
        materials = result.materials
        
        # 1. HAMMADDE-01 (Shared RM, pegging competition)
        self.assertIn("HAMMADDE-01", materials)
        m1 = materials["HAMMADDE-01"]
        self.assertEqual(m1.free_stock, 500)
        
        # 2. HAMMADDE-02 (Open PO)
        self.assertIn("HAMMADDE-02", materials)
        m2 = materials["HAMMADDE-02"]
        self.assertTrue(any(qty > 0 for qty in m2.open_pos.values()))
        
        # 3. HAMMADDE-03 (Yolda PR)
        self.assertIn("HAMMADDE-03", materials)
        m3 = materials["HAMMADDE-03"]
        self.assertTrue(any(qty > 0 for qty in m3.in_transit_prs.values()))
        
        # 4. HAMMADDE-04 (Antrepoda)
        self.assertIn("HAMMADDE-04", materials)
        
        # 5. HAMMADDE-05 (Gümrüklemede)
        self.assertIn("HAMMADDE-05", materials)
        
        # 6. HAMMADDE-06 (Full free stock)
        self.assertIn("HAMMADDE-06", materials)
        self.assertEqual(m6.free_stock, 2000)
        
        # 7. HAMMADDE-07 (Critical deficit, planned orders with MOQ & pack size)
        self.assertIn("HAMMADDE-07", materials)
        m7 = materials["HAMMADDE-07"]
        self.assertEqual(m7.free_stock, 0)
        self.assertTrue(sum(m7.netting.planned_orders.values()) >= 1000)
```

- [ ] **Step 2: Run test suite inside container**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.mrp_simulation.test_simulation`
Expected: PASS

- [ ] **Step 3: Test clean() leaves zero artifacts in DB**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost execute erpnextkta.mrp_simulation.cleaner.clean`
Check that no `URUN-01`, `URUN-02`, `HAMMADDE-%` items or simulation SO/PO/PR/WO remain in the database.

- [ ] **Step 4: Commit**

```bash
git add erpnextkta/mrp_simulation/test_simulation.py
git commit -m "test(mrp_simulation): add automated integration tests for simulation"
```

---

### Task 8: Documentation Sync (`erpnextkta/www/docs/`)

**Files:**
- Create/Modify: `erpnextkta/www/docs/mrp-simulation.html` (or link inside `erpnextkta/www/docs/` MRP section)
- Modify: `docs/superpowers/specs/2026-11-14-kta-mrp-simulation-design.md`

**Interfaces:**
- Consumes: AGENTS.md Rule 2 (Mandatory Documentation Sync under `erpnextkta/www/docs/`)
- Produces: User-facing portal documentation explaining how planners and developers run the simulation, what each row/status means in Desk, and how to clean it up.

- [ ] **Step 1: Check existing documentation structure under `erpnextkta/www/docs/`**
- [ ] **Step 2: Update/create the MRP simulation guide in `erpnextkta/www/docs/` explaining the 7 hammadde scenario, carry-over, and commands**
- [ ] **Step 3: Commit**

```bash
git add erpnextkta/www/docs/ docs/
git commit -m "docs(mrp): document MRP visual simulation guide and scenario walkthrough"
```
