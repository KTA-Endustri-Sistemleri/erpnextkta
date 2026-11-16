# Frappe Framework & Subagent Orchestration Rules

These rules apply specifically to contributing to the `erpnextkta` repository on the `main` branch. Follow these guidelines for all modifications, commits, and pull requests.

## Role-Conditional Execution Policy (Coordinator vs. Specialist Subagent)
* **Top-Level Coordinator Session (Tech Lead):** When operating as the primary agent in this repository, you act as the orchestrator and technical lead. **You DO NOT write or modify application source code directly** under `erpnextkta/**`, `frontend/**`, or `docs/**`. You analyze requests, define/invoke specialist subagents via `define_subagent` and `invoke_subagent` (`Workspace="inherit"`), coordinate cross-module contracts, trigger documentation sync, and execute the final quality gate.
* **Specialist Subagent Session:** When dispatched as a specialist subagent for a specific domain, you are granted write permissions **strictly within your assigned `owned_paths`** as defined in `.agents/subagents/<agent-id>.md`. You must follow the domain invariants and universal rules, and communicate external needs back to the Coordinator via your `## Çapraz Modül Kontrat İhtiyacı` section.

---

## 1. Branching & PR Strategy
* **Target Branch:** For production development, the target branch is `main`.
* **Zero Pending Policy:** Frappe has a strict review policy. PRs that do not meet guidelines or fail checks may be closed immediately (re-openable once fixed).
* **PR Checklist:**
  * **Test Cases:** Every fix or feature must include automated test cases to ensure stability and prevent regressions.
  * **UI Changes:** If changes affect the user interface, you must provide screenshots or a GIF demonstrating the visual differences.
  * **Documentation:** Ensure related documentation is updated if new APIs, fields, or configurations are introduced.
* **Mandatory PR Template Rule:** Whenever asked to create, prepare, draft, or update a Pull Request (PR) description (or when PR creation is mentioned), you **MUST ALWAYS** use and fill out the repository's official template located at `.github/PULL_REQUEST_TEMPLATE.md`. Never invent or generate an arbitrary, ad-hoc PR template. Every section defined in `.github/PULL_REQUEST_TEMPLATE.md` (`Tür (PR Type)`, `Amaç`, `Değişiklik Özeti`, `Test Durumu`, `İlgili Issue`, `Ek Notlar`) must be properly filled out.
* **PR Description Output Rule:** Whenever asked to write or update a PR description, always output the complete PR description in directly copy-pasteable Markdown format (enclosed in a ```markdown code block).
* **Confidentiality & Privacy in PRs & Commits:** PR descriptions, commit messages, and documentation must **NEVER** contain commercial or confidential data, such as real purchase prices, unit costs, or specific vendor/partner company names (e.g. spesifik tedarikçi/müşteri firma unvanları ve özel birim maliyet bilgileri asla bulunmamalıdır). Always anonymize or generalize such information (e.g., `"varsayılan tedarikçi"`, `"örnek birim fiyat"`) or omit them entirely.

---

## 2. Documentation Architecture & Primary Source of Truth (CRITICAL)
* **Single Source of Truth (`erpnextkta/www/docs`):** The primary and most critical documentation in this repository resides under **`erpnextkta/www/docs/`** (accompanied by developer guides in `docs/`).
* **Desk Portal Serving:** `erpnextkta/www/docs/` is rendered directly to end-users, planners, warehouse operators, and management via the Frappe Web Portal (`/docs/`).
* **Mandatory Documentation Sync:** Whenever workflows, roles, permissions, DocTypes, custom fields, business logic, or MRP engine calculations are added, modified, or refactored:
  * You **MUST** review and update the corresponding HTML documentation pages under `erpnextkta/www/docs/`.
  * Technical developer guides under `docs/` must also be kept synchronized.
  * **Never consider a feature, workflow adjustment, or bugfix complete without updating `erpnextkta/www/docs/`.**

---

## 3. Commit Message Conventions (Conventional Commits)
All commit messages must follow the Conventional Commits specification. They are validated via `commitlint.config.js`.
* **Format:** `<type>(<scope>): <subject>` (e.g., `fix(core): resolve db connection leak`)
* **Allowed Types:**
  * `feat`: A new feature
  * `fix`: A bug fix
  * `docs`: Documentation only changes
  * `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
  * `refactor`: A code change that neither fixes a bug nor adds a feature
  * `perf`: A code change that improves performance
  * `test`: Adding missing tests or correcting existing tests
  * `build`: Changes that affect the build system or external dependencies
  * `ci`: Changes to CI configuration files and scripts
  * `chore`: Other changes that don't modify src or test files
  * `revert`: Reverts a previous commit
* **Rules:**
  * The type must be lowercase.
  * The subject must not be empty.
  * Write the subject in the imperative, present tense: "change", not "changed" or "changes".
  * Keep the subject line short (ideally under 72 characters).
  * **Line Length Limit (STRICT):** No line in a commit message (subject or body) may exceed 100 characters. Wrap long sentences, bullet points, and descriptions so that every line is strictly <= 100 characters.

---

## 4. Code Style & Formatting
* **Linting & Formatting Tools:**
  * Python: Formatted and linted using `ruff` (located at `/home/frappe/frappe-bench/env/bin/ruff`).
  * JavaScript: Formatted with `Prettier` and linted with `ESLint`.
  * Run ruff check/format on modified files before committing.
* **Translation of Strings:**
  * All user-facing strings must be wrapped in translation helpers.
  * **Python:** `_("Your string here")`
  * **JavaScript:** `__("Your string here")`
  * **Vue/JS Components Scope:** In Vue components, always define a lazy global wrapper in the `<script setup>` block to avoid runtime `__ is not a function` compiler errors:
    ```javascript
    const __ = (...args) => window.__(...args);
    ```
  * **Sentence Unification:** Never split sentences/strings (e.g. wrapping partial words or inserting dynamic tags in-between translation fragments). Keep sentences whole in `__("Whole sentence here")` to preserve proper grammar and avoid translation bugs across different languages (EN/DE/TR).
  * **Title Case Standard:** All buttons, page headers, placeholders, and UI field labels must use Title Case (first letter capitalized, rest lowercase unless proper nouns). Check translation CSV files (`en.csv`, `de.csv`, `tr.csv`) to ensure they comply with this capitalization rule.
  * **Dynamic Data Translation:** Dynamic values loaded from database fields (such as workstation names, operation titles, sub-operation names, etc.) must be dynamically wrapped in `__(variable)` before rendering, and their translation mappings must be added to the CSV files.
* **Defensive Null-Safety in Document Hooks & Expressions:**
  * Numerical Frappe document fields (`per_ordered`, `per_billed`, `qty`, `lead_time`, etc.) can be `None` on newly created or draft documents.
  * Never compare uninitialized fields directly against numbers (e.g. `self.per_ordered >= 100` throws `TypeError: '>=' not supported between 'NoneType' and 'int'`). Always guard with `(self.field or 0)` or wrap with `flt()` / `cint()`.
* **Function Length:** Keep methods and functions small and modular. Try to split functions if they exceed ~10 lines of core logic.

---

## 5. Naming Conventions
* **DocTypes:** Always singular, Title Case, separated by spaces (e.g., `Sales Invoice`).
* **DocType Language Invariant (STRICT & CRITICAL):** DocTypes MUST NEVER be created with Turkish names or Turkish characters (e.g., NEVER `KTA Uretim Teyidi`, `KTA Calisma Karti`, `Hurda Kaydi`). DocTypes must ALWAYS use standard English terminology (Title Case, singular, e.g., `KTA Production Confirmation`, `KTA Work Card`, `KTA Scrap Entry`). User-facing labels can be translated into Turkish via translation dictionaries (`tr.csv`), but the DocType name itself, its folder name, and its fieldnames must strictly be in English.
* **Fields:** Slugged version of the label, lowercase, using underscores (e.g., label "Customer Name" -> field `customer_name`). All fieldnames must strictly be in English.
* **Link Fields:** The field name should match the name of the linked DocType in lowercase (e.g., link to `Employee` -> `employee`).
* **Variables:**
  * Use the slugged version of the DocType name for document objects (e.g., `sales_order = frappe.get_doc('Sales Order', ...)`).
  * Use `_name` suffix for variable names holding a document's key/ID (e.g., `sales_order_name`).
  * In loops over child tables, use `d` to reference the row object (e.g., `for d in self.items:`).

---

## 6. Security & Database
* Always write queries using the Frappe ORM (`frappe.db.get_value`, `frappe.get_doc`, etc.).
* Avoid direct raw SQL queries unless absolutely necessary. When using `frappe.db.sql`, always use parameterized queries to prevent SQL injection.

---

## 7. Tech Lead Orchestration & Subagent Routing Protocol

When executing tasks as the Coordinator, follow this routing protocol:

### 7.1 Specialist Subagents Directory (`.agents/subagents/`)

| Subagent ID | Spec File | Owned Paths | Core Specialty |
|---|---|---|---|
| `kta-mrp` | `.agents/subagents/kta-mrp.md` | `erpnextkta/kta_mrp/**` | Safe MRP engine services (`lead_time`, `psw`, `capacity`, `leveling`, `netting`), MRP reports, settings. |
| `kta-calisma-karti` | `.agents/subagents/kta-calisma-karti.md` | `erpnextkta/kta_calisma_karti/**`, `erpnextkta/tasks.py`, `erpnextkta/dry_run/**` | Shopfloor work cards, shift auto-closing cron, scrap & Job Card sync, crimp/injection records. |
| `kta-asset-maintenance` | `.agents/subagents/kta-asset-maintenance.md` | `erpnextkta/kta_asset_maintenance/**` | Asset maintenance event handlers, breakdown tracking, team user notifications. |
| `kta-stock` | `.agents/subagents/kta-stock.md` | `erpnextkta/kta_stock/**`, `erpnextkta/rest-api/**` | Batch splitting, Zebra label printing, QI transfer validation, stock reconciliation warehouse lock. |
| `kta-quality` | `.agents/subagents/kta-quality.md` | `erpnextkta/kta_quality/**` | Krimp Book library, crimp parameters, test bench validation records (17 poke-yoke items). |
| `kta-sales` | `.agents/subagents/kta-sales.md` | `erpnextkta/kta_sales/**` | Sales order revision comparison, SO sync logs, customer item selling rates. |
| `erpnextkta-core` | `.agents/subagents/erpnextkta-core.md` | `erpnextkta/erpnextkta/**`, `api.py`, `boot.py`, `middlewares.py`, `config/**`, `templates/**`, `__init__.py`, `modules.txt` | Core DocTypes (8D, capability study, customs declarations, mobil depo), custom JSON schemas, central utilities. |
| `frontend-public` | `.agents/subagents/frontend-public.md` | `erpnextkta/public/**`, `frontend/**` | Vue 3 SPAs (5 SPAs), Desk JavaScript scripts (`kta_report_utils.js` etc.), UI components, CSS styles. |
| `overrides-hooks` | `.agents/subagents/overrides-hooks.md` | `erpnextkta/overrides/**`, `hooks.py`, `patches/**`, `patches.txt`, `fixtures/**`, `tests/**` | Standard DocType class overrides, central hooks lifecycle, schema patches, 3-tier test utilities (`test_utils.py`). |
| `docs-i18n` | `.agents/subagents/docs-i18n.md` | `erpnextkta/www/**`, `docs/**`, `translations/**`, `README.md` | Portal user documentation (`/docs/`), developer guides, multi-lingual translations (TR/EN/DE). |

### 7.2 Dispatch & Contract Handoff Workflow
1. **Analyze Scope:** Identify which folders will be touched.
2. **Read Subagent Spec:** Read `.agents/subagents/<agent-id>.md`.
3. **Dispatch:** Call `define_subagent` and `invoke_subagent` with `Workspace="inherit"`. Instruct the subagent to respect its folder lock and output its `## Çapraz Modül Kontrat İhtiyacı`.
4. **Contract Handoff:** If subagent A reports a need for subagent B (e.g., backend creates new field, frontend needs to render it, hooks needs to register an event), Coordinator dispatches subagent B with the exact contract parameters.
5. **Smart `docs-i18n` Trigger:** Whenever business logic, doctypes/fields, workflows, or UI strings are modified, the Coordinator automatically dispatches `docs-i18n` before closing the task. Pure internal refactors or test-only fixes skip this step.

### 7.3 Coordinator Final Quality Gate
Before declaring any task or feature complete, the Coordinator executes:
1. **Frontend Production Build (if `public/` was affected):**
   `bench build --app erpnextkta --production`
2. **Targeted Module Tests:**
   `bench --site <site> run-tests --app erpnextkta --module <affected_module>`
3. **Changed Python Lint & Format Checks:**
   `/home/frappe/frappe-bench/env/bin/ruff check <modified_files>`
   `/home/frappe/frappe-bench/env/bin/ruff format --check <modified_files>`
4. **Backend Service Restart & Cache Clear (if backend/Python was affected):**
   `bench restart`
   `bench --site <site> clear-cache`

---

## 8. Build Command Rule
When building the frontend or checking for build errors, NEVER use direct package manager build commands. ALWAYS use the following command instead:
`bench build --app erpnextkta --production`

---

## 9. Backend Modification & Cache Refresh Rule
Whenever any backend Python code, controller, hook, API endpoint, patch, or MRP engine logic is added or modified, you **MUST ALWAYS** restart the bench services and clear the site cache to ensure that workers, web processes, and cache stores immediately pick up the changes:
```bash
bench restart
bench --site <site> clear-cache
```
