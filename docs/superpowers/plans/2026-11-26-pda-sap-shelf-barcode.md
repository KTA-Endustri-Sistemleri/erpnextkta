# PDA Eski SAP Raf Künyesi (`110-W1A-01-01`) Çözümleme Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable PDA warehouse barcode resolution (`resolve_warehouse_barcode`, `pda_material_transfer`, `pda_package_merge`, and `pda_stock_lookup`) to resolve SAP depot-prefixed shelf tags (such as `110-W1A-01-01` and `110-W1F-01-01`) to their unprefixed ERPNext leaf warehouses while preserving exact `170-W1F-*` matches and rejecting mismatched depot prefixes or disabled shelves.

**Architecture:** Extend `_lookup_warehouse_record()` in `erpnextkta/kta_stock/services/pda_service.py` with a 3rd fallback tier gated by `Warehouse` NestedSet (`lft`/`rgt`) ancestor verification. All tests run completely isolated on an empty Clean-CI `test_site` by dynamically creating unique-suffixed `110` and `170` test warehouse hierarchies without touching any live `Warehouse` records or schema.

**Tech Stack:** Python 3.11, Frappe ORM & `Warehouse` NestedSet (`lft`/`rgt`), `KTABaseTestCase` (`test_utils.py`), Ruff, Bench test runner, Frappe Web Portal Docs.

**Spec:** [2026-11-26-pda-sap-shelf-barcode-design.md](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-26-pda-sap-shelf-barcode-design.md)

## Global Constraints

- Zero hardcoded company (`KTA`) or warehouse names in production code; resolve solely via dynamic `Warehouse` NestedSet (`lft`/`rgt`) + `parent_warehouse` fallback.
- Zero schema changes, zero `Warehouse` renames, and zero database migrations.
- Clean-CI empty `test_site` safe: every test MUST construct its own unique-suffixed (`uid`) test `110` / `170` warehouse tree under `self._get_test_company()`, never assuming pre-seeded site warehouses exist.
- Strict `.agents/AGENTS.md` specialist ownership: `kta-stock` owns `erpnextkta/kta_stock/**`; `docs-i18n` owns `erpnextkta/www/**` and `docs/**`.
- Zero commercial/vendor/cost data anywhere; all Python functions concise and Ruff-compliant (`check` & `format --check`); Conventional Commits with all lines `<= 100` chars.

## Review Focus

- Wrong depot prefix (`170-W1F-01-01-{uid}` when `W1F-01-01-{uid}` only exists under `110`) -> must reject with `ValidationError` (`"Depo barkodu bulunamadı"`), never strip prefix blindly.
- Retired/disabled shelf under `110` (`110-W1F-12-01-{uid}`, `disabled=1`) coexisting with active `170-W1F-12-01-{uid}` -> scanning `110-W1F-12-01-{uid}` must match the disabled `110` leaf and throw `"Depo pasif durumda"`, never falling back to `170`.
- Same short `warehouse_name` under two different depots (`110` vs `170`) -> `110-` and `170-` must disambiguate cleanly to their respective leaves.
- Depot prefix boundary collision (`110` must NOT match an ancestor group named `1100 ...`) -> match only exact `depot_code`, `"{depot_code} "`, or `"{depot_code}-"` (case-insensitive).
- Whitespace/case normalization and non-warehouse numeric codes (`"  110-w1a-01-01-{uid}  "` resolves cleanly; unknown numeric-dash codes return `ValidationError`; `pda_stock_lookup` preserves box/batch priority).

---

### Task 1: SAP Prefix-Aware Warehouse Barcode Resolution & Clean-CI Tests (`kta-stock`)

**Files:**
- Modify: `erpnextkta/kta_stock/services/pda_service.py:562-628` (and top regex constant near lines `30-45`)
- Test: `erpnextkta/kta_stock/tests/test_pda_service.py:823-855`

**Interfaces:**
- Consumes: `frappe.db.get_value`, `frappe.get_all`, `Warehouse` fields (`name`, `warehouse_name`, `company`, `is_group`, `disabled`, `lft`, `rgt`, `parent_warehouse`)
- Produces:
  - `_SAP_PREFIXED_WAREHOUSE_RE = re.compile(r"^(\d{2,4})-(.+)$")`
  - `_ancestor_matches_depot_code(warehouse_name: str | None, depot_code: str) -> bool`
  - `_warehouse_has_prefix_ancestor(wh: dict, depot_code: str) -> bool`
  - `_select_warehouse_match(matches: list[dict], code: str) -> dict | None`
  - Updated `_lookup_warehouse_record(barcode: str, company: str | None = None) -> dict | None` (automatically covers `resolve_warehouse_barcode`, `pda_material_transfer`, `pda_package_merge`, and `pda_stock_lookup`)

- [x] **Step 1: Write failing Clean-CI self-contained tests in `erpnextkta/kta_stock/tests/test_pda_service.py`**

Add self-contained helper/test methods after `test_resolve_warehouse_barcode_exact_and_without_company_suffix_and_rejects_group` covering all spec and Review Focus scenarios using `uid`-isolated warehouses under `self._get_test_company()`:
- Build under `company`:
  - `110 HAMMADDE {uid}` (group) -> `W1A {uid}` (group) -> active leaf `W1A-01-01-{uid}`, plus `W1F {uid}` (group) -> active leaf `W1F-01-01-{uid}` and disabled leaf `W1F-12-01-{uid}` (`disabled=1`), plus shared leaf `SHARED-01-{uid}`.
  - `170 BİTMİŞ ÜRÜN {uid}` (group) -> active leaf `170-W1F-12-01-{uid}` and shared leaf `SHARED-01-{uid}` (created in another subgroup if company requires distinct `warehouse_name`, or using non-overlapping test setups for boundary `1100 KTA {uid}`).
  - Boundary group `1100 EXTRA {uid}` -> active leaf `B1A-01-01-{uid}` (verifies `"110-B1A-01-01-{uid}"` does NOT match ancestor `1100 EXTRA {uid}`).
- Test assertions:
  1. `resolve_warehouse_barcode(f"110-W1A-01-01-{uid}", company=company)` returns `W1A-01-01-{uid}`.
  2. Lowercase/whitespace `resolve_warehouse_barcode(f"  110-w1a-01-01-{uid}  ", company=company)` resolves cleanly via `110-` fallback (MySQL case-insensitive `warehouse_name` or normalized lookup).
  3. `resolve_warehouse_barcode(f"110-W1F-01-01-{uid}", company=company)` returns `W1F-01-01-{uid}`.
  4. `resolve_warehouse_barcode(f"170-W1F-12-01-{uid}", company=company)` returns exact `170-W1F-12-01-{uid}`.
  5. `resolve_warehouse_barcode(f"110-W1F-12-01-{uid}", company=company)` raises `frappe.ValidationError` containing `"Depo pasif durumda"`.
  6. `resolve_warehouse_barcode(f"170-W1F-01-01-{uid}", company=company)` raises `frappe.ValidationError` containing `"Depo barkodu bulunamadı"`.
  7. `resolve_warehouse_barcode(f"110-B1A-01-01-{uid}", company=company)` raises `frappe.ValidationError` containing `"Depo barkodu bulunamadı"` (`110` does not match `1100`).
  8. Cross-depot disambiguation (`110` vs `170` having distinct leaves or same leaf label in different test companies/trees): `110-...` and `170-...` resolve only under their matching depot ancestor.
  9. `pda_stock_lookup(f"110-W1A-01-01-{uid}")` returns `kind == "warehouse"` for `W1A-01-01-{uid}`, and `pda_material_transfer(..., target_warehouse_barcode=f"110-W1F-01-01-{uid}")` transfers a batch onto `W1F-01-01-{uid}`.

- [x] **Step 2: Run the new tests on `development.localhost` to confirm failure**

Run:
`bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service`
Expected: FAIL (`Depo barkodu bulunamadı: 110-W1A-01-01-...`).

- [x] **Step 3: Implement modular SAP prefix warehouse resolution in `erpnextkta/kta_stock/services/pda_service.py`**

Implement small, single-purpose helpers (~10-15 lines each) without hardcoded company/warehouse names:
- `_SAP_PREFIXED_WAREHOUSE_RE = re.compile(r"^(\d{2,4})-(.+)$")`
- `_ancestor_matches_depot_code(warehouse_name: str | None, depot_code: str) -> bool`: returns `True` iff normalized uppercase `warehouse_name` equals `depot_code`, starts with `f"{depot_code} "`, or starts with `f"{depot_code}-"`.
- `_warehouse_has_prefix_ancestor(wh: dict, depot_code: str) -> bool`: queries `Warehouse` ancestors via NestedSet (`lft <= wh.lft`, `rgt >= wh.rgt`, `is_group = 1`, `company == wh.company`), falling back to walking `parent_warehouse` links if `lft`/`rgt` are unpopulated; returns `True` if any ancestor passes `_ancestor_matches_depot_code`.
- `_select_warehouse_match(matches: list[dict], code: str) -> dict | None`: preserves existing active-leaf selection, multi-company disambiguation error, and disabled fallback (`matches[0]`) without duplicating logic across exact `warehouse_name` and SAP-prefixed fallback tiers.
- Update `_lookup_warehouse_record(barcode: str, company: str | None = None) -> dict | None`:
  - Fetch `fields = ["name", "warehouse_name", "company", "is_group", "disabled", "lft", "rgt", "parent_warehouse"]`.
  - Tier 1: exact `Warehouse.name == code` (respecting `company`).
  - Tier 2: exact `Warehouse.warehouse_name == code` via `_select_warehouse_match`.
  - Tier 3: match `code` against `_SAP_PREFIXED_WAREHOUSE_RE`; query `warehouse_name == shelf_code` (with optional `company`), filter candidates by `_warehouse_has_prefix_ancestor(m, depot_code)`, and return `_select_warehouse_match(scoped, code)`.

- [x] **Step 4: Run targeted tests and Ruff lint/format checks**

Run:
- `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service`
- `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_settings`
- `/home/frappe/frappe-bench/env/bin/ruff check --no-cache --ignore EXE002 erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py`
- `/home/frappe/frappe-bench/env/bin/ruff format --no-cache --check erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py`
Expected: All tests PASS and Ruff reports 0 issues.

- [x] **Step 5: Commit Task 1**

```bash
git add erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py
git commit -m "feat(kta_stock): resolve sap-prefixed shelf barcodes via warehouse tree"
```

---

### Task 2: Sync Stock Logistics Portal & Developer Documentation (`docs-i18n`)

**Files:**
- Modify: `erpnextkta/www/docs/stok-lojistik.html` (Section 10.C / Depo Raf Transferi & Stok Sorgu rules)
- Modify: `docs/kta_stok_lojistik_kilavuzu.md` (Section 10 / PDA API reference)
- Update: `docs/superpowers/specs/2026-11-26-pda-sap-shelf-barcode-design.md`, `docs/superpowers/plans/2026-11-26-pda-sap-shelf-barcode.md`

- [x] **Step 1: Update `erpnextkta/www/docs/stok-lojistik.html` and `docs/kta_stok_lojistik_kilavuzu.md`**

Document in both files:
- `<depo_kodu>-<raf_kodu>` SAP shelf barcode resolution (`110-W1A-01-01` -> `W1A-01-01`, `110-W1F-01-01` -> `W1F-01-01`) alongside exact `170-W1F-*` shelf tags.
- `Warehouse` NestedSet (`lft`/`rgt`) ancestor depot validation preventing wrong depot prefixes (`170-W1F-01-01`) and preserving `"Depo pasif durumda"` protection when retired `110` `W1F` shelf tags (`110-W1F-12-01`) are scanned.
- Coverage across Depo Raf Transferi (`pda_material_transfer`), Koli Birleştirme (`pda_package_merge`), and Stok/Etiket Sorgula (`pda_stock_lookup`).
- No new UI strings are introduced, so `tr.csv` / `en.csv` / `de.csv` require no changes.

- [x] **Step 2: Verify doc HTML balance, zero commercial data, and mark spec/plan complete**

Verify balanced HTML tags in `erpnextkta/www/docs/stok-lojistik.html`, mark Task 1 & Task 2 checkboxes `[x]` in this plan, and update spec status to `Implemented`.

- [x] **Step 3: Commit Task 2**

```bash
git add erpnextkta/www/docs/stok-lojistik.html docs/kta_stok_lojistik_kilavuzu.md docs/superpowers/specs/2026-11-26-pda-sap-shelf-barcode-design.md docs/superpowers/plans/2026-11-26-pda-sap-shelf-barcode.md
git commit -m "docs(pda): document sap-prefixed shelf barcode resolution"
```
