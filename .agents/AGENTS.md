# Frappe Framework Contribution Rules

These rules apply specifically to contributing to the `erpnextkta` repository on the `main` branch. Follow these guidelines for all modifications, commits, and pull requests.

## 1. Branching & PR Strategy
* **Target Branch:** For production development, the target branch is `main`.
* **Zero Pending Policy:** Frappe has a strict review policy. PRs that do not meet guidelines or fail checks may be closed immediately (re-openable once fixed).
* **PR Checklist:**
  * **Test Cases:** Every fix or feature must include automated test cases to ensure stability and prevent regressions.
  * **UI Changes:** If changes affect the user interface, you must provide screenshots or a GIF demonstrating the visual differences.
  * **Documentation:** Ensure related documentation is updated if new APIs, fields, or configurations are introduced.

## 2. Commit Message Conventions (Conventional Commits)
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

## 3. Code Style & Formatting
* **Linting & Formatting Tools:**
  * Python: Formatted and linted using `ruff` (which handles formatting, linting, and import sorting).
  * JavaScript: Formatted with `Prettier` and linted with `ESLint`.
  * Run `pre-commit run --all-files` before staging/committing to ensure all files comply.
* **Translation of Strings:**
  * All user-facing strings must be wrapped in translation helpers.
  * **Python:** `_("Your string here")`
  * **JavaScript:** `__("Your string here")`
  * **Vue/JS Components Scope:** In Vue components, always define a lazy global wrapper in the `<script setup>` block to avoid runtime `__ is not a function` compiler errors:
    ```javascript
    const __ = (...args) => window.__(...args);
    ```
  * **Sentence Unification:** Never split sentences/strings (e.g. wrapping partial words or inserting dynamic tags in-between translation fragments). Keep sentences whole in `__("Whole sentence here")` to preserve proper grammar and avoid translation bugs across different languages (EN/DE/TR).
  * **Title Case Standard:** All buttons, page headers, placeholders, and UI field labels must use Title Case (first letter capitalized, rest lowercase unless proper nouns). Check translation CSV files (`en.csv`, `de.csv`) to ensure they comply with this capitalization rule.
  * **Dynamic Data Translation:** Dynamic values loaded from database fields (such as workstation names, operation titles, sub-operation names, etc.) must be dynamically wrapped in `__(variable)` before rendering, and their translation mappings must be added to the CSV files.
* **Function Length:** Keep methods and functions small and modular. Try to split functions if they exceed ~10 lines of core logic.

## 4. Naming Conventions
* **DocTypes:** Always singular, Title Case, separated by spaces (e.g., `Sales Invoice`).
* **Fields:** Slugged version of the label, lowercase, using underscores (e.g., label "Customer Name" -> field `customer_name`).
* **Link Fields:** The field name should match the name of the linked DocType in lowercase (e.g., link to `Employee` -> `employee`).
* **Variables:**
  * Use the slugged version of the DocType name for document objects (e.g., `sales_order = frappe.get_doc('Sales Order', ...)`).
  * Use `_name` suffix for variable names holding a document's key/ID (e.g., `sales_order_name`).
  * In loops over child tables, use `d` to reference the row object (e.g., `for d in self.items:`).

## 5. Security & Database
* Always write queries using the Frappe ORM (`frappe.db.get_value`, `frappe.get_doc`, etc.).
* Avoid direct raw SQL queries unless absolutely necessary. When using `frappe.db.sql`, always use parameterized queries to prevent SQL injection.

# Build Command Rule
When building the frontend or checking for build errors, NEVER use `yarn build` directly. ALWAYS use the following command instead:
`bench build --app erpnextkta --production`
