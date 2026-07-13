---
trigger: always_on
---

# Translation of Strings and UI Rules

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
