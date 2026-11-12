# Enjeksiyon Kalıp Yönetimi Faz 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Operatörleri Çalışma Kartı alt operasyonlarında ve ölçümlerinde kalıp numarasını elle serbest metin yazmaktan kurtarmak için `KTA Enjeksiyon Kalibi` ana veri modelini oluşturmak, mevcut 46 kalıbı patch ile sisteme aktarmak ve arayüzde seçilebilir / doğrulanabilir Link alanına dönüştürmek.

**Architecture:** Frappe DocType (`KTA Enjeksiyon Kalibi`) oluşturulur; tek seferlik `post_model_sync` patch ile mevcut 146 QI şablonundan ilk 10 hanesi kalıp kodu olan 46 benzersiz kalıp çekilir. Alt operasyon ve enjeksiyon ölçüm child table'ları ile Vue dialogları (`alt_operasyon.ts`, `olcum.ts`) `Link` tipine çevrilerek backend API seviyesinde aktif kalıp varlığı doğrulanır.

**Tech Stack:** Frappe Framework v15, MariaDB, Python 3.12, Vue 3, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-11-12-enjeksiyon-kalip-mimarisi-design.md`

## Global Constraints

* Target Branch: Production development target is `feat/enjeksiyon-kalip-no` / `main`.
* Commit Message Convention: Conventional Commits (`feat(calisma-karti): ...`, `fix(calisma-karti): ...`).
* Translation Rule: All user-facing strings must be wrapped in `_()` (Python) and `__()` (JS), keeping sentences whole (no split strings), in Title Case. Translations must be populated in `en.csv`, `de.csv`, `tr.csv`.
* Build Rule: NEVER use `yarn build` directly. ALWAYS use `bench build --app erpnextkta --production`.
* Lint Rule: Python formatted/linted with `ruff`.

## Review Focus

1. **Non-existent or Disabled Mold Input:** When an operator enters or API receives an invalid or `disabled=1` mold number, backend must reject with a user-friendly validation error.
2. **Idempotent Patch Execution:** When `bench migrate` runs multiple times, the patch must not fail or create duplicate `KTA Enjeksiyon Kalibi` records.
3. **Template Match Fallback:** When a QI Template has no item suffix (e.g. `8710506150 Enjeksiyon KP Rev.00`), the 10-digit code must still be parsed correctly as the mold name.
4. **Existing Card Compatibility:** Existing Çalışma Kartı records must retain their historical `kalip_no` without data loss or schema conflict.
5. **Frontend Search Experience:** In Frappe dialogs, typing numbers or text must search both `kalip_no` and `kalip_adi` via Frappe's Link autocomplete.

---

### Task 1: Create `KTA Enjeksiyon Kalibi` DocType

**Files:**
- Create: `erpnextkta/kta_calisma_karti/doctype/kta_enjeksiyon_kalibi/__init__.py`
- Create: `erpnextkta/kta_calisma_karti/doctype/kta_enjeksiyon_kalibi/kta_enjeksiyon_kalibi.py`
- Create: `erpnextkta/kta_calisma_karti/doctype/kta_enjeksiyon_kalibi/kta_enjeksiyon_kalibi.json`
- Test: `erpnextkta/kta_calisma_karti/doctype/kta_enjeksiyon_kalibi/test_kta_enjeksiyon_kalibi.py`

**Interfaces:**
- Produces: DocType `KTA Enjeksiyon Kalibi` with fields:
  - `kalip_no` (Data, unique, mandatory)
  - `kalip_adi` (Data, mandatory)
  - `varsayilan_kalite_sablonu` (Link: `Quality Inspection Template`)
  - `mevcut_adet` (Int, default: 1)
  - `aciklama` (Small Text)
  - `disabled` (Check, default: 0)

- [x] **Step 1: Write the failing unit test for `KTA Enjeksiyon Kalibi`**
Create `test_kta_enjeksiyon_kalibi.py` asserting creation, duplicate check, and disabled state validation.

- [x] **Step 2: Run test to verify it fails**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.kta_calisma_karti.doctype.kta_enjeksiyon_kalibi.test_kta_enjeksiyon_kalibi`
Expected: FAIL with DocType does not exist.

- [x] **Step 3: Implement `kta_enjeksiyon_kalibi.json`, `kta_enjeksiyon_kalibi.py`, `__init__.py`**
Define standard Frappe DocType schema with `autoname: "field:kalip_no"`, `title_field: "kalip_adi"`, `search_fields: "kalip_adi"`.

- [x] **Step 4: Run bench migrate to create database table**
Run: `bench --site old.kta-endustri.com.tr migrate`
Expected: `KTA Enjeksiyon Kalibi` table created successfully.

- [x] **Step 5: Run unit test to verify it passes**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.kta_calisma_karti.doctype.kta_enjeksiyon_kalibi.test_kta_enjeksiyon_kalibi`
Expected: PASS.

- [x] **Step 6: Commit**
```bash
git add erpnextkta/kta_calisma_karti/doctype/kta_enjeksiyon_kalibi/
git commit -m "feat(calisma-karti): create KTA Enjeksiyon Kalibi doctype"
```

---

### Task 2: Migration Patch to Extract 46 Molds from QI Templates

**Files:**
- Create: `erpnextkta/patches/v3_0_3/extract_enjeksiyon_kaliplari.py`
- Create: `erpnextkta/patches/v3_0_3/__init__.py`
- Modify: `erpnextkta/patches.txt:24`
- Test: `erpnextkta/tests/test_mold_patch.py`

**Interfaces:**
- Consumes: `tabQuality Inspection Template` names matching `LIKE '%Enjeksiyon%'`
- Produces: `tabKTA Enjeksiyon Kalibi` records for all 46 unique 10-digit mold codes.

- [x] **Step 1: Write the failing test for the patch execution**
Create test verifying that running the patch function extracts 46 molds, sets `kalip_adi = f"{kalip_no} Enjeksiyon Kalıbı"`, assigns `varsayilan_kalite_sablonu`, and is idempotent when run twice.

- [x] **Step 2: Run test to verify it fails**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_mold_patch`
Expected: FAIL with ModuleNotFoundError for `extract_enjeksiyon_kaliplari`.

- [x] **Step 3: Implement `extract_enjeksiyon_kaliplari.py` and register in `patches.txt`**
Extract `^(\d{10})\b` from QI Template names. Insert records if `not frappe.db.exists("KTA Enjeksiyon Kalibi", mold_no)`.

- [x] **Step 4: Run test to verify it passes**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_mold_patch`
Expected: PASS.

- [x] **Step 5: Run patch on site via bench migrate**
Run: `bench --site old.kta-endustri.com.tr migrate`
Verify: `SELECT count(*) FROM \`tabKTA Enjeksiyon Kalibi\`` returns >= 46.

- [x] **Step 6: Commit**
```bash
git add erpnextkta/patches/v3_0_3/ erpnextkta/patches.txt erpnextkta/tests/test_mold_patch.py
git commit -m "feat(calisma-karti): add migration patch for 46 injection molds"
```

---

### Task 3: Update Alt Operasyon and Enjeksiyon Child Tables to Link Type

**Files:**
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti_alt_operasyon_kayitlari/calisma_karti_alt_operasyon_kayitlari.json:51-56`
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti_enjeksiyon_olcumleri/calisma_karti_enjeksiyon_olcumleri.json:56-62`

**Interfaces:**
- Changes `kalip_no` fieldtype from `"Data"` to `"Link"` with `"options": "KTA Enjeksiyon Kalibi"` on both child tables.

- [x] **Step 1: Update `calisma_karti_alt_operasyon_kayitlari.json` and `calisma_karti_enjeksiyon_olcumleri.json`**
Set `fieldtype: "Link"`, `options: "KTA Enjeksiyon Kalibi"` for `kalip_no`.

- [x] **Step 2: Run bench migrate to apply schema update**
Run: `bench --site old.kta-endustri.com.tr migrate`
Expected: Database columns updated to Link reference without error.

- [x] **Step 3: Commit**
```bash
git add erpnextkta/kta_calisma_karti/doctype/calisma_karti_alt_operasyon_kayitlari/ calisma_karti_enjeksiyon_olcumleri/
git commit -m "feat(calisma-karti): link kalip_no to KTA Enjeksiyon Kalibi in child tables"
```

---

### Task 4: Backend API Validation in `alt_operasyon.py` and `enjeksiyon.py`

**Files:**
- Modify: `erpnextkta/kta_calisma_karti/api_impl/alt_operasyon.py`
- Modify: `erpnextkta/kta_calisma_karti/api_impl/enjeksiyon.py`
- Test: `erpnextkta/tests/test_enjeksiyon_kalip_api.py`

**Interfaces:**
- Consumes: `KTA Enjeksiyon Kalibi` table
- Produces: `_assert_enjeksiyon_kalip_valid(kalip_no)` helper raising `frappe.ValidationError` if mold does not exist or is disabled.

- [x] **Step 1: Write failing unit tests for invalid and disabled mold inputs**
Test `add_alt_operasyon_kaydi` and `save_enjeksiyon_olcum` with non-existent mold (`"9999999999"`) and disabled mold, expecting `frappe.ValidationError`. Test valid mold passing cleanly.

- [x] **Step 2: Run test to verify it fails**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_enjeksiyon_kalip_api`
Expected: FAIL.

- [x] **Step 3: Implement validation in `alt_operasyon.py` and `enjeksiyon.py`**
In `add_alt_operasyon_kaydi`, `update_alt_operasyon_kaydi`, and `save_enjeksiyon_olcum`, validate `kalip_no` against active `KTA Enjeksiyon Kalibi`.

- [x] **Step 4: Run test to verify it passes**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_enjeksiyon_kalip_api`
Expected: PASS.

- [x] **Step 5: Commit**
```bash
git add erpnextkta/kta_calisma_karti/api_impl/ erpnextkta/tests/test_enjeksiyon_kalip_api.py
git commit -m "feat(calisma-karti): enforce active mold validation in injection APIs"
```

---

### Task 5: Frontend Vue Dialogs (`alt_operasyon.ts`, `olcum.ts`)

**Files:**
- Modify: `erpnextkta/public/view-calisma-karti/composables/prompts/alt_operasyon.ts:103-111,246-254`
- Modify: `erpnextkta/public/view-calisma-karti/composables/prompts/olcum.ts:287-293`

**Interfaces:**
- Changes prompt dialog fields `kalip_no` to `fieldtype: "Link"`, `options: "KTA Enjeksiyon Kalibi"`.

- [x] **Step 1: Update `alt_operasyon.ts`**
In both `altOperasyonFieldsMulti` and `altOperasyonSingleField`, update `kalip_no`:
```typescript
{
    fieldtype: "Link",
    label: __("Kalıp No"),
    fieldname: "kalip_no",
    options: "KTA Enjeksiyon Kalibi",
    reqd: (parentOperationLabel === "OP40" || !!defaults.has_enjeksiyon) ? 1 : 0,
    read_only: isTechLocked ? 1 : 0,
    depends_on: () => parentOperationLabel === "OP40" || !!defaults.has_enjeksiyon,
    default: defaults.kalip_no || "",
}
```

- [x] **Step 2: Update `olcum.ts`**
In `getEnjeksiyonMeasurementFields`, update `kalip_no`:
```typescript
{
    fieldtype: "Link",
    label: __("Kalıp No"),
    fieldname: "kalip_no",
    options: "KTA Enjeksiyon Kalibi",
    reqd: 1,
    default: defaults.kalip_no || "",
    read_only: defaults.alt_operasyon_kaydi ? 1 : 0,
}
```

- [x] **Step 3: Run existing frontend test suite**
Run: `npm test` inside `erpnextkta`
Expected: PASS.

- [x] **Step 4: Commit**
```bash
git add erpnextkta/public/view-calisma-karti/composables/prompts/
git commit -m "feat(calisma-karti): change kalip_no to Link field in dialog prompts"
```

---

### Task 6: Translations and Production Build

**Files:**
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/translations/tr.csv`

- [x] **Step 1: Add all new strings in Title Case to translation CSVs**
- "KTA Enjeksiyon Kalibi" -> "KTA Injection Mold" (EN) / "KTA Spritzgussform" (DE)
- "Mevcut Kalıp Adedi" -> "Available Mold Quantity" (EN) / "Verfügbare Formmenge" (DE)
- "Varsayılan Kalite Şablonu" -> "Default Quality Template" (EN) / "Standard-Qualitätsvorlage" (DE)
- "Seçilen kalıp numarası ({0}) sistemde tanımlı değil veya devre dışı." -> translated in full without string splitting.

- [x] **Step 2: Execute production build**
Run: `bench build --app erpnextkta --production`
Expected: Exit code 0, no compilation errors.

- [x] **Step 3: Commit**
```bash
git add erpnextkta/translations/
git commit -m "chore(translations): add dictionary entries for KTA Enjeksiyon Kalibi"
```

---

### Task 7: Comprehensive Automated Verification

**Files:**
- Test: `erpnextkta/tests/test_enjeksiyon_kalip_full.py`

- [x] **Step 1: Write and run end-to-end integration test**
Test full lifecycle:
1. Verifying 46 molds populated.
2. Creating a test Çalışma Kartı with injection operation.
3. Adding alt operasyon with valid `KTA Enjeksiyon Kalibi`.
4. Saving enjeksiyon olcum with valid `KTA Enjeksiyon Kalibi`.
5. Verifying rejection with non-existent mold.

- [x] **Step 2: Run all test suites**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_enjeksiyon_kalip_full`
Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti_enjeksiyon_olcumleri`
Expected: ALL PASS.

- [x] **Step 3: Commit final verification**
```bash
git add erpnextkta/tests/test_enjeksiyon_kalip_full.py
git commit -m "test(calisma-karti): add end-to-end test suite for injection mold integration"
```
