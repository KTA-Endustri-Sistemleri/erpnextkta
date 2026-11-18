# SAP CO01 / CO11N Üretim Teyit Motoru (kta_shopfloor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `feat-partial-job-card-submit` dalındaki Job Card bölme (peel-off) karmaşasını temizleyip; Job Card'ı açık/pasif süre konteyneri olarak koruyarak, yetkili ekip arkadaşlarının kullanacağı yeni **`kta_shopfloor`** modülü altında SAP CO11N benzeri tek ekran, atomik malzeme sarfiyatlı (261 backflush / yerel FIFO) ve CORS iptal destekli modüler bir Üretim Teyit Motoru inşa etmek.

**Architecture:** 
- **Modül Ayrımı:** `kta_calisma_karti` atölye süre/duruş/krimp takibini yaparken, yeni **`kta_shopfloor`** resmi üretim teyidi ve stok sarfiyatını üstlenir.
- **Veri Modeli:** Operatör süreleri için açık `Job Card` (Draft `docstatus=0`), her yetkili teyit işlemi için değiştirilemez `KTA Uretim Teyidi` (Transaction / Submittable `docstatus=1`, `kta_shopfloor` altında).
- **Servis Katmanı (`erpnextkta/kta_shopfloor/services/`):** `BackflushService` (BOM oranlama, yerel FIFO sarfiyat ve mamul girişi), `ConfirmationService` (CO11N atomik teyit) ve `ReversalService` (CORS ters kayıt).
- **Entegrasyon:** `KTAStockEntry` ile Job Card kilitlerinin by-pass edilmesi, `job_card_sync.py` süre entegrasyonunun aynen korunması.
- **Arayüz:** Yetkili ekip için barkod destekli tek ekran CO11N arayüzü + yöneticiler için Frappe Desk görünümü.

**Tech Stack:** Python 3.12, Frappe Framework v15, ERPNext v15, Vue 3, Ruff.

**Spec:** [docs/superpowers/specs/2026-11-17-co01-co11n-production-confirmation-design.md](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/superpowers/specs/2026-11-17-co01-co11n-production-confirmation-design.md)

## Global Constraints

- Target branch: `feat-partial-job-card-submit` (merge to `main`).
- Coordinator writes NO code directly under `erpnextkta/**`, `frontend/**`, `docs/**` (dispatch specialist subagents per `.agents/AGENTS.md`).
- Formatting & Linting: Ruff (`/home/frappe/frappe-bench/env/bin/ruff`).
- Frontend Build: `bench build --app erpnextkta --production`.
- Zero Commercial Data in tests/docs/commits.
- Documentation sync with `erpnextkta/www/docs/` and translations (`tr.csv`, `en.csv`, `de.csv`).

## Review Focus

1. **BOM Orantısal Sarfiyat Hassasiyeti:** Kısmi teyitlerde `(yield_qty / wo_qty) * required_qty` hesabının küsürat hassasiyetinin doğruluğu.
2. **Reçetede Operasyonsuz Kalemler:** Ara operasyonlarda operasyonsuz kalemlerin tüketilmemesi; yalnızca son operasyonda orantısal sarf edilmesi.
3. **Son Teyit Bakiye Eşitlemesi:** "Son Teyit (Kalanı Kapat)" işaretlendiğinde yuvarlama farkı bırakmadan açık bakiyenin sıfırlanması.
4. **Job Card Frappe Kilitlenmemesi:** Job Card'ın `docstatus=0` kalarak `status="Completed"` olması; `Calisma Karti` süre yazımını veya CORS iptalini bozan kilitlerin oluşmaması.
5. **CORS İptalinde Stok Bütünlüğü:** Teyit iptal edildiğinde ilişkili `Stock Entry` fişinin eksiksiz ters kaydedilmesi (`cancel`).

---

### Task 1: Job Card Peel-Off Kodlarının Temizlenmesi

**Files:**
- Modify: `erpnextkta/overrides/job_card.py`
- Modify: `erpnextkta/public/js/job_card.js`
- Test: `erpnextkta/kta_calisma_karti/tests/test_api.py`

**Interfaces:**
- Consumes: ERPNext `Job Card`.
- Produces: Clean `KTAJobCard` without `peel_off_partial_production` or Job Card splitting logic.

- [ ] **Step 1: Write verification test for clean Job Card**
Ensure `KTAJobCard` does not expose `peel_off_partial_production` and retains normal time log handling.

- [ ] **Step 2: Run test to verify current state**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_calisma_karti.tests.test_api`

- [ ] **Step 3: Remove peel-off and splitting logic**
In `erpnextkta/overrides/job_card.py`, remove `peel_off_partial_production`, remove Job Card-level `_create_consumption_entry_if_needed`, remove `_cancel_consumption_entries`. Remove "Kısmi Üretim Bildir" button in `public/js/job_card.js`.

- [ ] **Step 4: Run tests to verify clean pass**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_calisma_karti.tests.test_api`

- [ ] **Step 5: Lint and commit**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/overrides/job_card.py`
Commit: `refactor(job_card): remove peel-off partial production logic`

---

### Task 2: `kta_shopfloor` Modülünün Kurulumu, `Module Def` ve `KTA Uretim Teyidi` DocType

**Files:**
- Modify: `erpnextkta/modules.txt`
- Create: `erpnextkta/kta_shopfloor/__init__.py`
- Create: `erpnextkta/kta_shopfloor/module_def/__init__.py`
- Create: `erpnextkta/kta_shopfloor/module_def/kta_shopfloor/__init__.py`
- Create: `erpnextkta/kta_shopfloor/module_def/kta_shopfloor/kta_shopfloor.json`
- Create: `.agents/subagents/kta-shopfloor.md`
- Create: `erpnextkta/kta_shopfloor/doctype/kta_uretim_teyidi/kta_uretim_teyidi.json`
- Create: `erpnextkta/kta_shopfloor/doctype/kta_uretim_teyidi/kta_uretim_teyidi.py`
- Create: `erpnextkta/kta_shopfloor/doctype/kta_uretim_teyidi/__init__.py`
- Test: `erpnextkta/kta_shopfloor/doctype/kta_uretim_teyidi/test_kta_uretim_teyidi.py`

**Interfaces:**
- Consumes: `Work Order`, `Job Card`.
- Produces: 
  - `Module Def` document: `kta_shopfloor`.
  - Submittable DocType `KTA Uretim Teyidi` (Module: `kta_shopfloor`) with fields: `work_order`, `job_card`, `operation`, `posting_date`, `posting_time`, `yield_qty`, `is_final_confirmation`, `stock_entry`, `confirmed_by`.

- [ ] **Step 1: Register module in `modules.txt` and define `Module Def` JSON**
Append `kta_shopfloor` to `erpnextkta/modules.txt`. Create `erpnextkta/kta_shopfloor/module_def/kta_shopfloor/kta_shopfloor.json` with `doctype: "Module Def"`, `app_name: "erpnextkta"`, `module_name: "kta_shopfloor"`. Create `.agents/subagents/kta-shopfloor.md` to define specialist agent ownership.

- [ ] **Step 2: Write failing test for `KTA Uretim Teyidi`**
Verify creation and submission of `KTA Uretim Teyidi` under `kta_shopfloor` module.

- [ ] **Step 3: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.doctype.kta_uretim_teyidi.test_kta_uretim_teyidi`

- [ ] **Step 4: Implement DocType schema and controller**
Create JSON schema (`is_submittable=1`, `module="kta_shopfloor"`) and Python controller with validation logic.

- [ ] **Step 5: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.doctype.kta_uretim_teyidi.test_kta_uretim_teyidi`
Expected: PASS.

- [ ] **Step 6: Lint and commit**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_shopfloor/`
Commit: `feat(shopfloor): initialize kta_shopfloor module, module_def and kta uretim teyidi doctype`

---

### Task 3: BackflushService (`kta_shopfloor/services/`)

**Files:**
- Create: `erpnextkta/kta_shopfloor/services/__init__.py`
- Create: `erpnextkta/kta_shopfloor/services/backflush_service.py`
- Test: `erpnextkta/kta_shopfloor/tests/test_backflush_service.py`

**Interfaces:**
- Consumes: `Work Order`, BOM Items, `Stock Entry`.
- Produces:
  - `calculate_operation_raw_materials(work_order, operation, yield_qty, is_final) -> list[dict]`
  - `create_consumption_entry(work_order, operation, yield_qty, is_final, confirmation_name) -> str (SE Name)`
  - `create_finished_goods_entry(work_order, yield_qty, is_final, confirmation_name) -> str (SE Name)`

- [ ] **Step 1: Write failing test**
Test BOM consumption:
1. Intermediate operation consumes only raw materials assigned to that operation.
2. Unassigned materials are skipped on intermediate operations, consumed on final operation.
3. Native ERPNext FIFO is leveraged (`auto_create_serial_and_batch_bundle_for_outward`).
4. Final operation creates `Manufacture` Stock Entry with finished good.

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_backflush_service`
Expected: FAIL.

- [ ] **Step 3: Implement `BackflushService`**
Build stock entry payloads, handle zero-material operations gracefully (skip empty SE), attach confirmation reference.

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_backflush_service`
Expected: PASS.

- [ ] **Step 5: Lint and commit**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_shopfloor/services/backflush_service.py`
Commit: `feat(shopfloor): implement backflush service with fifo allocation`

---

### Task 4: ConfirmationService (`kta_shopfloor/services/`)

**Files:**
- Create: `erpnextkta/kta_shopfloor/services/confirmation_service.py`
- Test: `erpnextkta/kta_shopfloor/tests/test_confirmation_service.py`

**Interfaces:**
- Consumes: `BackflushService`, `KTA Uretim Teyidi`, `Job Card`, `Work Order`.
- Produces: `confirm_operation(payload: dict) -> dict(success=bool, confirmation=str, stock_entry=str)`.

- [ ] **Step 1: Write failing test**
1. Validates inputs (`work_order`, `operation`, `yield_qty`).
2. Creates and submits `KTA Uretim Teyidi`.
3. Triggers `BackflushService`.
4. Increments `Job Card.total_completed_qty` and `Work Order Operation.completed_qty`.
5. If `is_final` is True: sets `Job Card.status = "Completed"` (keeps `docstatus=0`), marks Work Order completed if final op.

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_confirmation_service`
Expected: FAIL.

- [ ] **Step 3: Implement `ConfirmationService`**
Orchestrate atomic transaction with DB savepoint.

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_confirmation_service`
Expected: PASS.

- [ ] **Step 5: Lint and commit**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_shopfloor/services/confirmation_service.py`
Commit: `feat(shopfloor): implement co11n confirmation service`

---

### Task 5: ReversalService (SAP CORS İptal ve Geri Alma)

**Files:**
- Create: `erpnextkta/kta_shopfloor/services/reversal_service.py`
- Test: `erpnextkta/kta_shopfloor/tests/test_reversal_service.py`

**Interfaces:**
- Consumes: `KTA Uretim Teyidi`, `Stock Entry`.
- Produces: `cancel_confirmation(confirmation_name: str, user: str) -> dict(success=bool)`.

- [ ] **Step 1: Write failing test**
1. Non-manager role is rejected.
2. Cancelling confirmation cancels linked Stock Entry (`docstatus=2`).
3. Rolls back `Job Card.total_completed_qty` and Work Order operation quantities.
4. Marks confirmation `docstatus=2`.

- [ ] **Step 2: Run test to verify it fails**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_reversal_service`
Expected: FAIL.

- [ ] **Step 3: Implement `ReversalService`**
Enforce role check, cancel Stock Entries, decrement quantities, update confirmation docstatus.

- [ ] **Step 4: Run test to verify it passes**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_shopfloor.tests.test_reversal_service`
Expected: PASS.

- [ ] **Step 5: Lint and commit**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_shopfloor/services/reversal_service.py`
Commit: `feat(shopfloor): implement cors reversal service`

---

### Task 6: `KTAStockEntry` Override Güncellemesi

**Files:**
- Modify: `erpnextkta/overrides/KTAStockEntry.py`
- Test: `erpnextkta/tests/test_stock_entry_override.py`

**Interfaces:**
- Overrides: `check_if_operations_completed(self)`.
- Validates operation completed quantities against `fg_completed_qty` without crashing on draft Job Cards.

- [ ] **Step 1: Write test for Stock Entry validation**
Verify `Stock Entry (Manufacture)` submits cleanly when operations have `completed_qty` satisfied even if Job Cards are draft (`docstatus=0`).

- [ ] **Step 2: Run test to verify failure/behavior**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_override`

- [ ] **Step 3: Update `check_if_operations_completed` in `KTAStockEntry.py`**
Inspect operation row completed quantities directly instead of enforcing submitted Job Cards.

- [ ] **Step 4: Run test to verify pass**
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.tests.test_stock_entry_override`
Expected: PASS.

- [ ] **Step 5: Lint and commit**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/overrides/KTAStockEntry.py`
Commit: `fix(stock): decouple stock entry validation from job card submission`

---

### Task 7: CO11N Whitelist API & Single Screen Arayüzü

**Files:**
- Create: `erpnextkta/kta_shopfloor/api.py`
- Create/Modify: CO11N UI Component (Desk Page / SPA)
- Build: `bench build --app erpnextkta --production`

**Interfaces:**
- Whitelisted endpoints:
  - `erpnextkta.kta_shopfloor.api.get_co11n_context(barcode)`
  - `erpnextkta.kta_shopfloor.api.submit_co11n_confirmation(payload)`
  - `erpnextkta.kta_shopfloor.api.cancel_co11n_confirmation(confirmation_name)`

- [ ] **Step 1: Write API tests**
Test barcode resolution and confirmation endpoint in `erpnextkta/kta_shopfloor/tests/test_api.py`.

- [ ] **Step 2: Implement whitelist API methods in `kta_shopfloor/api.py`**
Expose endpoints routing to `ConfirmationService` and `ReversalService`.

- [ ] **Step 3: Create CO11N fast single-screen UI**
Add touch-friendly inputs: Barcode scan, Operation selector, Yield Qty, "Son Teyit" checkbox, "Teyit Et" button.

- [ ] **Step 4: Build frontend bundle**
Run: `bench build --app erpnextkta --production`
Expected: Build passes with exit code 0.

- [ ] **Step 5: Commit**
Commit: `feat(ui): add co11n single screen confirmation cockpit in kta_shopfloor`

---

### Task 8: Portal Dokümantasyonu ve Çeviriler (`docs-i18n`)

**Files:**
- Modify: `erpnextkta/www/docs/`
- Modify: `erpnextkta/translations/tr.csv`, `en.csv`, `de.csv`

**Interfaces:**
- Publishes user portal guide on `/docs/` explaining CO11N confirmation, partial confirmations, and CORS reversal.
- Ensures all UI strings are translated in Title Case.

- [ ] **Step 1: Update portal documentation**
Add detailed user manual section for CO11N Single Screen Confirmation.

- [ ] **Step 2: Update translation files**
Add translations for new buttons, fields, and messages in `tr.csv`, `en.csv`, and `de.csv`.

- [ ] **Step 3: Verification & Commit**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/`
Commit: `docs(portal): update docs and translations for kta_shopfloor co11n cockpit`
