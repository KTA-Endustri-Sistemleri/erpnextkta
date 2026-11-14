# Frappe Framework Contribution Rules

These rules apply specifically to contributing to the `erpnextkta` repository on the `main` branch. Follow these guidelines for all modifications, commits, and pull requests.

## 1. Branching & PR Strategy
* **Target Branch:** For production development, the target branch is `main`.
* **Zero Pending Policy:** Frappe has a strict review policy. PRs that do not meet guidelines or fail checks may be closed immediately (re-openable once fixed).
* **PR Checklist:**
  * **Test Cases:** Every fix or feature must include automated test cases to ensure stability and prevent regressions.
  * **UI Changes:** If changes affect the user interface, you must provide screenshots or a GIF demonstrating the visual differences.
  * **Documentation:** Ensure related documentation is updated if new APIs, fields, or configurations are introduced.
* **PR Description Output Rule:** Whenever asked to write or update a PR description, always output the complete PR description in directly copy-pasteable Markdown format (enclosed in a ```markdown code block).

## 2. Documentation Architecture & Primary Source of Truth (CRITICAL)
* **Single Source of Truth (`erpnextkta/www/docs`):** The primary and most critical documentation in this repository resides under **`erpnextkta/www/docs/`** (accompanied by developer guides in `docs/`).
* **Desk Portal Serving:** `erpnextkta/www/docs/` is rendered directly to end-users, planners, warehouse operators, and management via the Frappe Web Portal (`/docs/`).
* **Mandatory Documentation Sync:** Whenever workflows, roles, permissions, DocTypes, custom fields, business logic, or MRP engine calculations are added, modified, or refactored:
  * You **MUST** review and update the corresponding HTML documentation pages under `erpnextkta/www/docs/`.
  * Technical developer guides under `docs/` must also be kept synchronized.
  * **Never consider a feature, workflow adjustment, or bugfix complete without updating `erpnextkta/www/docs/`.**

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

## 4. Code Style & Formatting
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
* **Defensive Null-Safety in Document Hooks & Expressions:**
  * Numerical Frappe document fields (`per_ordered`, `per_billed`, `qty`, `lead_time`, etc.) can be `None` on newly created or draft documents.
  * Never compare uninitialized fields directly against numbers (e.g. `self.per_ordered >= 100` throws `TypeError: '>=' not supported between 'NoneType' and 'int'`). Always guard with `(self.field or 0)` or wrap with `flt()` / `cint()`.
* **Function Length:** Keep methods and functions small and modular. Try to split functions if they exceed ~10 lines of core logic.

## 5. Naming Conventions
* **DocTypes:** Always singular, Title Case, separated by spaces (e.g., `Sales Invoice`).
* **Fields:** Slugged version of the label, lowercase, using underscores (e.g., label "Customer Name" -> field `customer_name`).
* **Link Fields:** The field name should match the name of the linked DocType in lowercase (e.g., link to `Employee` -> `employee`).
* **Variables:**
  * Use the slugged version of the DocType name for document objects (e.g., `sales_order = frappe.get_doc('Sales Order', ...)`).
  * Use `_name` suffix for variable names holding a document's key/ID (e.g., `sales_order_name`).
  * In loops over child tables, use `d` to reference the row object (e.g., `for d in self.items:`).

## 6. Security & Database
* Always write queries using the Frappe ORM (`frappe.db.get_value`, `frappe.get_doc`, etc.).
* Avoid direct raw SQL queries unless absolutely necessary. When using `frappe.db.sql`, always use parameterized queries to prevent SQL injection.

## 7. Manufacturing & MRP Domain Rules
* **No Sub-Assemblies (Yarı Mamul Yoktur):** KTA üretim mimarisinde yarı mamul (sub-assembly) katmanları kullanılmaz. Ürün ağaçları (BOM) düzdür; tüm hammadde ve bileşenler doğrudan nihai mamulün (Finished Good) reçetesinde yer alır.
* **Work Order skip_transfer = 1:** Üretim iş emirleri (Work Order) istisnasız `skip_transfer = 1` kuralıyla çalışır (malzeme transfer fişi zorunluluğu atlanır).
* **Talep & Kapasite Hesaplamaları:** MRP ve kapasite analizlerinde hem Satış Siparişleri (Sales Order - planlanan dış talep) hem de İş Emirleri (Work Order - fiili üretim yükü) birlikte ele alınır; mükerrer talep sayımı engellenerek net ihtiyaç hesaplanır.
* **Kapasite Tanımı (Item.custom_weekly_production):** KTA Kapasite Planlama ve MRP motorunda kapasite iş istasyonlarından (Workstation) ALINMAZ. Kapasite doğrudan her ürünün (Item) üzerindeki `custom_weekly_production` (Haftalık Üretim Kapasitesi) alanından ve ürün grubu (`item_group`) tavanından (`group_capacity`) okunur. İş istasyonları (Workstation) operasyonel süreçler ve rota için oluşturulsa da kapasite havuzunu `Item.custom_weekly_production` belirler.
* **Material Request & Re-Order Mantığı:** Re-order mekanizmasında Satış Siparişleri (`reserved_qty`) projeksiyon hesabına dahil edilmez (yalnızca fiili üretim rezervleri düşülür). Otomatik oluşturulan `Manufacture` tipindeki Material Request'ler doğrudan submit edilmez, plancı onayı için Taslak (`Draft`) kalır. Onaylanan `Manufacture` Material Request'ler, PSW ve Kapasite Planlama motorunda **Dahili Üretim Talebi (`internal_demand`)** olarak kapasiteyi ve MRP'yi besler.
* **Tedarik Boru Hattı & 5 Lojistik Durum Rozeti (Supply Pipeline & State-Aware Badges):**
  * Açık PO (`po`): İndigo (`#4f46e5`, `fa-file-text-o`) – Satınalma siparişindeki malzeme.
  * Yolda / In-Transit (`yolda`): Amber / Sarı (`#d97706`, `fa-ship`) – Sevk halindeki malzeme; `tahmini_varis_tarihi` (ETA) baz alınır.
  * Gümrüklemede (`gumruklemede`): Koyu Turuncu (`#c2410c`, `fa-hourglass-half`) – Millileştirme sürecindeki malzeme (`custom_gumruk_islem_baslama_tarihi + antrepo_clearance_days` günü depoya girer).
  * Antrepoda (`antrepoda`): Gök Mavisi (`#0284c7`, `fa-university`) – Bekleme havuzundaki malzeme (çekim emri verilene kadar haftalık takvime yapay yığılmaz, rezerv gösterilir).
  * Mal Kabul Uyuşmazlığı (`uyusmazlikta`): Kırmızı (`#991b1b`, `fa-exclamation-triangle`) – Kapıda bloke/karantina; kullanılabilir arza ve netleştirmeye **asla dahil edilmez**.
  * Çoklu Rozet Kuralı: Haftalık matris hücrelerinde birden fazla tedarik kaynağı olduğunda tekil jenerik kutu yerine durum bazlı çoklu rozetler (`.mrp-supplies-pills`) alt alta listelenir.
* **İki Eksenli Lead Time Mimarisi (Decoupled Production vs Shipping Lead Time):**
  * Üretim Süresi ($T_{\text{prod}}$): "Ne üretildiği" (Ürün/BOM) ile ilgilidir. Müşteriden bağımsız fabrika imalat süresidir. `Item.custom_manufacturing_lead_days` veya istisnai durumlarda `Item Customer Detail.custom_production_time_days` üzerinden okunur (Standart `Item.lead_time_days` alanı Purchasing/Satınalma sekmesinde olup hammadde tedarik süresine aittir; üretim süresi olarak kullanılmaz).
  * Sevk / Yol Süresi ($T_{\text{transit}}$): "Nereye gittiği" (Adres/Plant/Coğrafya) ile ilgilidir.
  * Geriye Doğru Çizelgeleme: $\text{Planlanan Üretim Başlangıç Tarihi (PSW)} = \text{Müşteri Teslim Tarihi} - (T_{\text{prod}} + T_{\text{transit}})$.
* **Kademeli Çözümleme Zinciri (Cascading Fallback Hierarchy):**
  * Sevk Süresi: `Address (Plant)` $\rightarrow$ `Customer` $\rightarrow$ `Customer Group` $\rightarrow$ `KTA MRP Settings.default_delivery_time_days`.
  * Üretim Süresi: `Item Customer Detail` $\rightarrow$ `Item` $\rightarrow$ `KTA MRP Settings.default_production_time_days`.
  * Sistem hiçbir zaman 0 gün süresine düşmemeli, tanımlanmamış alanlarda hiyerarşik olarak bir üst katmana başvurmalıdır.
* **Kapasite Dengeleme (Leveling) & Taşıma (Carry-over):**
  * `KTA MRP Settings.enable_leveling_by_default = 1`. Bir haftada toplam net talep (dış talep + dahili talep + iş emirleri) tavan kapasiteyi aşarsa, aşan miktar otomatik olarak bir sonraki haftaya **devreder (carry-over / forward scheduling)**.
* **Satınalma Lotlama (MOQ & Paket) ve Emniyet Stoğu:**
  * Net ihtiyaç doğduğunda önerilen sipariş miktarı $\max(\text{MOQ}, \lceil \text{Net} / \text{Paket} \rceil \times \text{Paket})$ formülüyle lotlanır. Parametreler `Item Price` üzerindeki `custom_minimum_order_quantity` ve `custom_minimum_paketleme_miktari` alanlarından okunur.
  * Emniyet stoğu (`warehouse_reorder_level`), müşterinin satış siparişine karşı kilitlenir; satış siparişi sadece serbest stoktan ($\text{Fiili Stok} - \text{Emniyet Stoğu}$) karşılanabilir.
* **Merkezi Konfigürasyon (`KTA MRP Settings`):**
  * Gümrük süresi, acil açık haftası, varsayılan üretim/sevk süresi, dengeleme varsayılanı gibi parametreler kod içerisine hardcode yazılamaz; `erpnextkta.kta_mrp.mrp_engine.settings.get_mrp_settings()` üzerinden çekilmelidir.
* **Çekirdek Motor ve Rapor Katmanı Ayrımı (Decoupled Engine & Presentation Layer):**
  * Raporlar (`report/`) sadece görsel sunum (presentation) katmanıdır. Çekirdek motorlar (`mrp_engine/`) rapor sınıflarını veya rapor dosyalarını import edemez.
  * Tüm iş mantığı ve hesaplamalar `mrp_engine/` altındaki saf servislerde (`lead_time.py`, `psw.py`, `capacity.py`, `service.py`) yaşar; raporlar bu servisleri çağırarak sadece tablo/grafik basar.

# Build Command Rule
When building the frontend or checking for build errors, NEVER use `yarn build` directly. ALWAYS use the following command instead:
`bench build --app erpnextkta --production`
