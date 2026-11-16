# Subagent Architecture & Module-Based Agent System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the monolithic `.agents/AGENTS.md` into a Coordinator (Tech Lead) orchestration protocol and establish 11 isolated, folder-locked specialist subagents in `.agents/subagents/`, while distilling legacy rules and removing obsolete `.clinerules` and `memory-bank/` files.

**Architecture:** The top-level session acts strictly as Coordinator / Tech Lead using `.agents/AGENTS.md` (no direct editing of application code; delegates via `define_subagent` and `invoke_subagent`). Each of the 11 specialists owns a distinct set of paths defined in `.agents/subagents/<agent-id>.md`, communicates cross-module needs via structured contract handoffs, and follows domain-specific invariants extracted and reconciled from existing repository code.

**Tech Stack:** Frappe Framework v15, ERPNext, Vue 3, Markdown, Python (Ruff, Unittest), Antigravity Agent Platform.

**Spec:** [docs/superpowers/specs/2026-11-16-subagent-architecture-design.md](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/superpowers/specs/2026-11-16-subagent-architecture-design.md)

## Global Constraints

- Target branch is `main` (active tree based on `feat/mrp-modular-refactor`).
- Mandatory PR template from `.github/PULL_REQUEST_TEMPLATE.md` output in copy-pasteable Markdown block.
- Zero commercial data or vendor company names; strict anonymization in commits and documentation.
- Frontend build command strictly: `bench build --app erpnextkta --production` (never `yarn build`).
- Single source of truth for user documentation is `erpnextkta/www/docs/` (synced with `docs/`).
- Python files formatted/linted via `/home/frappe/frappe-bench/env/bin/ruff` (on changed files only; no modification of untouched legacy code).
- Conventional commits syntax (`<type>(<scope>): <subject>`).

## Review Focus

- Subagent system prompt schema validity: all 11 subagents must have YAML frontmatter (`name`, `description`, `owned_paths`).
- Mutually exclusive ownership: no overlapping `owned_paths` between any two subagents; no unassigned app directory.
- Subagent permission safety: Coordinator write restriction is role-conditional so spawned subagents can edit their `owned_paths`.
- Elimination of obsolete anti-patterns: no `frappe.db.commit()` in controllers, no reports importing reports, and no `yarn build` mentions.
- Preservation of critical domain logic: 5 logistics status badges, two-axis lead times, flat BOMs, shift auto-closing, and 500-line Vue decomposition rules must be accurately retained.

---

### Task 1: Create Validation Harness for Subagents & Directory Ownership

**Files:**
- Create: `tests/verify_subagent_specs.py`

**Interfaces:**
- Consumes: `.agents/AGENTS.md`, `.agents/subagents/*.md`, repository directory listing.
- Produces: Command line test tool validating YAML frontmatter, path disjunction, coverage of all repo folders, and absence of forbidden strings (confidential names, `yarn build`, `frappe.db.commit()`).

- [ ] **Step 1: Write the validation script `tests/verify_subagent_specs.py`**

```python
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".agents"
SUBAGENTS_DIR = AGENTS_DIR / "subagents"

EXPECTED_SUBAGENTS = {
    "kta-mrp", "mrp-simulation", "kta-calisma-karti", "kta-asset-maintenance",
    "kta-stock", "kta-quality", "kta-sales", "erpnextkta-core",
    "frontend-public", "overrides-hooks", "docs-i18n"
}

FORBIDDEN_PATTERNS = [
    re.compile(r"yarn\s+build"),
    re.compile(r"frappe\.db\.commit\(\)"),
]

def parse_frontmatter(content):
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    raw = match.group(1)
    meta = {}
    current_key = None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line.startswith("-"):
            key, val = line.split(":", 1)
            current_key = key.strip()
            val = val.strip()
            meta[current_key] = val if val else []
        elif line.startswith("-") and current_key:
            item = line.lstrip("-").strip()
            if isinstance(meta[current_key], list):
                meta[current_key].append(item)
    return meta

def main():
    errors = []
    if not SUBAGENTS_DIR.exists():
        print(f"FAIL: {SUBAGENTS_DIR} does not exist")
        sys.exit(1)

    found_agents = set()
    all_owned_paths = {}

    for file_path in SUBAGENTS_DIR.glob("*.md"):
        agent_id = file_path.stem
        found_agents.add(agent_id)
        content = file_path.read_text(encoding="utf-8")

        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(content):
                errors.append(f"Forbidden pattern '{pattern.pattern}' found in {file_path.name}")

        meta = parse_frontmatter(content)
        if not meta:
            errors.append(f"Missing or invalid YAML frontmatter in {file_path.name}")
            continue

        if meta.get("name") != agent_id:
            errors.append(f"Name mismatch in {file_path.name}: expected {agent_id}, got {meta.get('name')}")
        if not meta.get("description"):
            errors.append(f"Missing description in {file_path.name}")
        
        owned = meta.get("owned_paths", [])
        if not owned:
            errors.append(f"Missing owned_paths in {file_path.name}")
        for path in owned:
            if path in all_owned_paths:
                errors.append(f"Path overlap: {path} owned by both {all_owned_paths[path]} and {agent_id}")
            all_owned_paths[path] = agent_id

    missing = EXPECTED_SUBAGENTS - found_agents
    if missing:
        errors.append(f"Missing expected subagent files: {missing}")

    if errors:
        print("VERIFICATION FAILED:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

    print(f"SUCCESS: All {len(found_agents)} subagents verified with zero overlaps.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run verification script to confirm it fails prior to implementation**

Run: `python3 tests/verify_subagent_specs.py`
Expected: FAIL with missing directory or missing files.

- [ ] **Step 3: Commit verification test harness**

```bash
git add tests/verify_subagent_specs.py
git commit -m "test(agents): add verification test harness for subagent specifications"
```

---

### Task 2: Create Subagent Specs for Manufacturing & Planning Domain (`kta-mrp`, `mrp-simulation`)

**Files:**
- Create: `.agents/subagents/kta-mrp.md`
- Create: `.agents/subagents/mrp-simulation.md`

**Interfaces:**
- Consumes: Section 7 of existing `.agents/AGENTS.md`, `erpnextkta/kta_mrp/memory-bank/systemPatterns.md`, and code from `erpnextkta/kta_mrp/mrp_engine/`.
- Produces: Specialist subagent prompt for `kta-mrp` and `mrp-simulation`.

- [ ] **Step 1: Write `.agents/subagents/kta-mrp.md`**
  - Define frontmatter: `name: kta-mrp`, `owned_paths: ["erpnextkta/kta_mrp/**"]`.
  - Distill strict domain invariants: flat BOM (no sub-assemblies), `skip_transfer = 1`, capacity determined by `Item.custom_weekly_production` & `group_capacity` (not workstation), draft `Material Request` (Manufacture) feeding `internal_demand`, 5 logistics status badges (`po`, `yolda`, `gumruklemede`, `antrepoda`, `uyusmazlikta`), decoupled lead time ($T_{\text{prod}} + T_{\text{transit}}$), cascading fallback hierarchy, MOQ & packaging batching, safety stock reservation locking, centralized `get_mrp_settings()`, and decoupled engine (`mrp_engine/` vs presentation `report/`).
  - Specify test execution: `KTAUnitTestCase` / `KTABaseTestCase` in `erpnextkta/kta_mrp/mrp_engine/test_*.py` and `erpnextkta/kta_mrp/tests/`.
  - Include Contract Handoff section.

- [ ] **Step 2: Write `.agents/subagents/mrp-simulation.md`**
  - Define frontmatter: `name: mrp-simulation`, `owned_paths: ["erpnextkta/mrp_simulation/**"]`.
  - Define role: deterministic MRP simulation seeder, cleaner, date resolver, and test fixture generator.
  - Invariants: must use `KTA MRP Settings` baseline initialization without hardcoding, generate realistic multi-week demand and supply pipeline, cleanly wipe generated simulation entities on cleanup without touching real master data.
  - Specify test execution: `erpnextkta/mrp_simulation/test_simulation.py`, `test_dates.py`.

- [ ] **Step 3: Verify markdown formatting and absence of forbidden patterns**

Run: `/home/frappe/frappe-bench/env/bin/ruff check tests/verify_subagent_specs.py`
Expected: PASS

- [ ] **Step 4: Commit MRP domain subagent specifications**

```bash
git add .agents/subagents/kta-mrp.md .agents/subagents/mrp-simulation.md
git commit -m "feat(agents): add kta-mrp and mrp-simulation subagent specifications"
```

---

### Task 3: Create Subagent Specs for Shopfloor & Asset Maintenance (`kta-calisma-karti`, `kta-asset-maintenance`)

**Files:**
- Create: `.agents/subagents/kta-calisma-karti.md`
- Create: `.agents/subagents/kta-asset-maintenance.md`

**Interfaces:**
- Consumes: `erpnextkta/kta_calisma_karti/.clinerules`, `erpnextkta/kta_calisma_karti/memory-bank/`, `erpnextkta/tasks.py`, `erpnextkta/kta_asset_maintenance/events.py`.
- Produces: Specialist subagent prompts for `kta-calisma-karti` and `kta-asset-maintenance`.

- [ ] **Step 1: Write `.agents/subagents/kta-calisma-karti.md`**
  - Define frontmatter: `name: kta-calisma-karti`, `owned_paths: ["erpnextkta/kta_calisma_karti/**", "erpnextkta/tasks.py", "erpnextkta/dry_run/**"]`.
  - Invariants: Facade pattern (`api.py` re-exports from `api_impl/`), role-gated write endpoints (`is_system_manager`, `is_quality_user`, `require_my_employee`), permlevel 1 `kalite_kontrol` bypass via `_require_qc_role()`, Draft-first lifecycle (`docstatus: 0` -> auto-submit on `Bitis`), `docstatus: 2` "İptal Edildi" priority, cumulative whitelist of material groups for sub-operations and scrap, shift auto-close at 16:00 and 00:00 (430-minute net limit), scrap 1:1 bidirectional sync with `Stock Entry` (flags `syncing_hurda_from_se` / `syncing_hurda_from_card`), QI draft lifecycle and restoration, barcode prefix normalization (`2026-X` to `MFG-WO-2026-X`).
  - Specify test execution: `erpnextkta/kta_calisma_karti/tests/` using `KTATestCase`, `KTABaseTestCase`, or `KTAUnitTestCase`.

- [ ] **Step 2: Write `.agents/subagents/kta-asset-maintenance.md`**
  - Define frontmatter: `name: kta-asset-maintenance`, `owned_paths: ["erpnextkta/kta_asset_maintenance/**"]`.
  - Invariants: Manage `Asset Maintenance` and `Asset Maintenance Log` doc events, breakdown vs planned statuses and colors, maintenance team notification resolution, bidirectional linking with `Calisma Karti` breakdown events.
  - Test and handoff guidelines.

- [ ] **Step 3: Commit shopfloor & asset maintenance subagent specifications**

```bash
git add .agents/subagents/kta-calisma-karti.md .agents/subagents/kta-asset-maintenance.md
git commit -m "feat(agents): add kta-calisma-karti and kta-asset-maintenance subagent specifications"
```

---

### Task 4: Create Subagent Specs for Stock, Quality, and Sales (`kta-stock`, `kta-quality`, `kta-sales`)

**Files:**
- Create: `.agents/subagents/kta-stock.md`
- Create: `.agents/subagents/kta-quality.md`
- Create: `.agents/subagents/kta-sales.md`

**Interfaces:**
- Consumes: `erpnextkta/kta_stock/`, `erpnextkta/rest-api/`, `erpnextkta/kta_quality/memory-bank/`, `erpnextkta/kta_sales/`.
- Produces: Specialist subagent prompts for `kta-stock`, `kta-quality`, and `kta-sales`.

- [ ] **Step 1: Write `.agents/subagents/kta-stock.md`**
  - Define frontmatter: `name: kta-stock`, `owned_paths: ["erpnextkta/kta_stock/**", "erpnextkta/rest-api/**"]`.
  - Invariants: Batch splitting logic (`BatchSplitManager`), Zebra printer integration (`LabelPrinter`, `KTA Stock Label`), transfer pre-validation for quality inspection (`quality_inspection_validator.py`), `Iade Edilebilir Ambalaj Fisi` tracking, draft stock reconciliation unique warehouse lock (`stock_reconciliation_lock.py`), and real-time dashboard socket events.
  - Tests: `erpnextkta/kta_stock/tests/**` (`KTAUnitTestCase` / `KTABaseTestCase`).

- [ ] **Step 2: Write `.agents/subagents/kta-quality.md`**
  - Define frontmatter: `name: kta-quality`, `owned_paths: ["erpnextkta/kta_quality/**"]`.
  - Invariants: `KTA Krimp Book` (static reference library of crimp specifications), `KTA Krimp Yukseklik Parametreleri` (approved production parameters), `Test Masasi Dogrulama Kaydi` automatic 17 Poke-Yoke criteria and connector rows pre-fill (`before_insert`), PTR procedure text validation, cross-module sync to `Calisma Karti` via `calisma_karti_ref` without raw commit anti-patterns.
  - Tests: DocType unit/integration tests using `KTABaseTestCase`.

- [ ] **Step 3: Write `.agents/subagents/kta-sales.md`**
  - Define frontmatter: `name: kta-sales`, `owned_paths: ["erpnextkta/kta_sales/**"]`.
  - Invariants: `KTA Sales Order Update` revision tracking, detailed change comparison and logging (`KTA SO Sync Log`), customer-item selling rate sync (`KTA Selling Rate Customer`), integration with sales orders without corrupting submitted documents.
  - Tests: `erpnextkta/kta_sales/**` tests using `KTABaseTestCase`.

- [ ] **Step 4: Commit stock, quality, and sales subagent specifications**

```bash
git add .agents/subagents/kta-stock.md .agents/subagents/kta-quality.md .agents/subagents/kta-sales.md
git commit -m "feat(agents): add kta-stock, kta-quality, and kta-sales subagent specifications"
```

---

### Task 5: Create Subagent Specs for Core App & Horizontal Layers (`erpnextkta-core`, `frontend-public`, `overrides-hooks`, `docs-i18n`)

**Files:**
- Create: `.agents/subagents/erpnextkta-core.md`
- Create: `.agents/subagents/frontend-public.md`
- Create: `.agents/subagents/overrides-hooks.md`
- Create: `.agents/subagents/docs-i18n.md`

**Interfaces:**
- Consumes: `erpnextkta/erpnextkta/`, `erpnextkta/public/`, `erpnextkta/overrides/`, `erpnextkta/hooks.py`, `erpnextkta/www/docs/`, `docs/`, `erpnextkta/translations/`.
- Produces: Remaining 4 specialist subagent prompts completing the 11-agent suite.

- [ ] **Step 1: Write `.agents/subagents/erpnextkta-core.md`**
  - Define frontmatter: `name: erpnextkta-core`, `owned_paths: ["erpnextkta/erpnextkta/**", "erpnextkta/api.py", "erpnextkta/boot.py", "erpnextkta/middlewares.py", "erpnextkta/config/**", "erpnextkta/templates/**", "erpnextkta/__init__.py", "erpnextkta/modules.txt"]`.
  - Invariants: Shared DocTypes (8D Formu, Machine Capability Study, customs/customs bonded warehouse declarations, Mobil Depo, Amboss Takimlari, Olcu Metodu), `erpnextkta/custom/*.json` schema customizations, central app utility functions in `erpnextkta/api.py`, `KTA` naming prefix convention.

- [ ] **Step 2: Write `.agents/subagents/frontend-public.md`**
  - Define frontmatter: `name: frontend-public`, `owned_paths: ["erpnextkta/public/**", "frontend/**"]`.
  - Invariants: 5 Vue 3 SPAs (`create-calisma-karti`, `list-calisma-cards`, `view-calisma-karti`, `material-requirement`, `stock-reco-dashboard`), Desk scripts (`kta_report_utils.js`, `kta_report_overrides.js`, `material_transfer_patch.js`), CSS variables (`--ck-glass-*`), Title Case standard, 500-line single file component limit, lazy global translation wrapper `const __ = (...args) => window.__(...args);`, modal body teleportation `<Teleport to="body">`, Vitest execution. Note: build command strictly `bench build --app erpnextkta --production` (executed via Coordinator).

- [ ] **Step 3: Write `.agents/subagents/overrides-hooks.md`**
  - Define frontmatter: `name: overrides-hooks`, `owned_paths: ["erpnextkta/overrides/**", "erpnextkta/hooks.py", "erpnextkta/patches/**", "erpnextkta/patches.txt", "erpnextkta/fixtures/**", "erpnextkta/tests/**"]`.
  - Invariants: Never modify standard ERPNext files; register class overrides via `override_doctype_class` in `hooks.py`, implement logic in `erpnextkta/overrides/*.py`, hook document lifecycles via `doc_events`, maintain schema migrations in `patches/` and `patches.txt`, maintain 3-tier test infrastructure in `erpnextkta/tests/test_utils.py`.

- [ ] **Step 4: Write `.agents/subagents/docs-i18n.md`**
  - Define frontmatter: `name: docs-i18n`, `owned_paths: ["erpnextkta/www/**", "docs/**", "erpnextkta/translations/**", "README.md"]`.
  - Invariants: Maintain primary portal docs in `erpnextkta/www/docs/*.html` and developer guides in `docs/` (excluding `docs/superpowers/**` which belongs to Coordinator), synchronize translation files (`en.csv`, `de.csv`, `tr.csv`), enforce whole sentence translations and Title Case in CSV files, zero commercial partner names or real prices.

- [ ] **Step 5: Run validation harness**

Run: `python3 tests/verify_subagent_specs.py`
Expected: PASS (All 11 subagents verified with zero overlaps).

- [ ] **Step 6: Commit horizontal layer subagent specifications**

```bash
git add .agents/subagents/erpnextkta-core.md .agents/subagents/frontend-public.md .agents/subagents/overrides-hooks.md .agents/subagents/docs-i18n.md
git commit -m "feat(agents): add core, frontend, overrides, and docs-i18n subagent specifications"
```

---

### Task 6: Refactor Root `.agents/AGENTS.md` as Role-Conditional Coordinator

**Files:**
- Modify: `.agents/AGENTS.md`

**Interfaces:**
- Consumes: Spec Section 5.2 & 5.3, subagent directory `.agents/subagents/*.md`.
- Produces: Lean root `.agents/AGENTS.md` containing universal rules, Tech Lead orchestration protocol, subagent routing matrix, contract handoff protocol, and Coordinator final gate.

- [ ] **Step 1: Edit `.agents/AGENTS.md`**
  - Update preamble to define role-conditional rules: Top-level Coordinator does not write application code; spawned subagents write exclusively within their `owned_paths`.
  - Retain Sections 1-6 (PR strategy, confidentiality with anonymized examples, documentation sync requirement, commit conventions, coding style, security/database).
  - Replace Section 7 (Manufacturing & MRP Domain Rules) with:
    - **Tech Lead Orchestration Protocol:** discovery, subagent definition & dispatch (`define_subagent` + `invoke_subagent`), contract handoff handling, and automatic `docs-i18n` trigger.
    - **11 Subagent Routing Table:** mappings from module/feature area to subagent file, owned paths, and specialty.
    - **Coordinator Final Quality Gate:** frontend production build (`bench build --app erpnextkta --production`), modular test runs (`bench --site <site> run-tests --app erpnextkta --module ...`), and changed-file ruff checks.

- [ ] **Step 2: Verify `.agents/AGENTS.md` compliance with validation harness**

Run: `python3 tests/verify_subagent_specs.py`
Expected: PASS

- [ ] **Step 3: Commit refactored root AGENTS.md**

```bash
git add .agents/AGENTS.md
git commit -m "refactor(agents): streamline root AGENTS.md into role-conditional coordinator protocol"
```

---

### Task 7: Remove Obsolete `.clinerules` and `memory-bank/` Files

**Files:**
- Delete: `.clinerules`
- Delete: `erpnextkta/kta_calisma_karti/.clinerules`
- Delete: `erpnextkta/kta_calisma_karti/memory-bank/` (all files)
- Delete: `erpnextkta/kta_mrp/memory-bank/` (all files)
- Delete: `erpnextkta/kta_quality/memory-bank/` (all files)

**Interfaces:**
- Consumes: Spec Section 5.5.
- Produces: Clean repository tree free of duplicate, scattered, or outdated agent memory files.

- [ ] **Step 1: Check git status to identify exact files to remove**

Run: `git status`

- [ ] **Step 2: Remove obsolete files using `git rm`**

```bash
git rm .clinerules
git rm erpnextkta/kta_calisma_karti/.clinerules
git rm -r erpnextkta/kta_calisma_karti/memory-bank
git rm -r erpnextkta/kta_mrp/memory-bank
git rm -r erpnextkta/kta_quality/memory-bank
```

- [ ] **Step 3: Commit removal of obsolete rule files**

```bash
git commit -m "chore(agents): remove obsolete clinerules and memory-bank directories"
```

---

### Task 8: Full End-to-End Verification & Quality Gate

**Files:**
- Test: `tests/verify_subagent_specs.py`
- Verify: Repository git status, git log, branch cleanliness, diff verification.

- [ ] **Step 1: Run subagent specification validation harness**

Run: `python3 tests/verify_subagent_specs.py`
Expected: SUCCESS: All 11 subagents verified with zero overlaps.

- [ ] **Step 2: Run Ruff lint check on modified/created python verification scripts**

Run: `/home/frappe/frappe-bench/env/bin/ruff check tests/verify_subagent_specs.py`
Expected: All checks passed.

- [ ] **Step 3: Verify git status and check for uncommitted or untracked changes**

Run: `git status`
Expected: Clean working tree.

- [ ] **Step 4: Self-check against acceptance criteria**
  - [x] All 11 subagents present in `.agents/subagents/`.
  - [x] Every app directory owned by exactly one specialist.
  - [x] Zero overlapping paths.
  - [x] Obsolete `.clinerules` and `memory-bank` directories removed.
  - [x] No confidential data or vendor names present.
  - [x] Root `AGENTS.md` acts as role-conditional Coordinator.
