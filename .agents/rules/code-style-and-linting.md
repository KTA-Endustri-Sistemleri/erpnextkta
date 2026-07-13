---
trigger: always_on
---

# Code Style & Formatting

* **Linting & Formatting Tools:**
  * **Python:** Formatted and linted using `ruff` (which handles formatting, linting, and import sorting).
  * **JavaScript:** Formatted with `Prettier` and linted with `ESLint`.
  * Run `pre-commit run --all-files` before staging/committing to ensure all files comply.

* **Function Length:** 
  * Keep methods and functions small and modular. Try to split functions if they exceed ~10 lines of core logic.