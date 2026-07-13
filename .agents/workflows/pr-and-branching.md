---
description: 
---

# Branching & PR Strategy

* **Target Branch:** For production development, the target branch is `main`.
* **Zero Pending Policy:** Frappe has a strict review policy. PRs that do not meet guidelines or fail checks may be closed immediately (re-openable once fixed).
* **PR Checklist:**
  * **Test Cases:** Every fix or feature must include automated test cases to ensure stability and prevent regressions.
  * **UI Changes:** If changes affect the user interface, you must provide screenshots or a GIF demonstrating the visual differences.
  * **Documentation:** Ensure related documentation is updated if new APIs, fields, or configurations are introduced.

## Generating Pull Request Descriptions

When the user asks you to generate a PR description for the last `X` commits (or generally asks to create a PR description):
1. Run `git log -n <X>` (or examine the commits in question) to analyze the recent changes.
2. Read the `.github/PULL_REQUEST_TEMPLATE.md` file.
3. Fill out the template comprehensively based on the commit history:
   - Mark the correct `[x]` under **Tür (PR Type)** based on conventional commit types (e.g., `feat` -> Feature, `fix` -> Bug Fix).
   - Summarize the core problem solved under **Amaç**.
   - Create a bulleted list of actual changes under **Değişiklik Özeti**.
   - Infer test status and linked issues if mentioned in the commits.
4. Output the filled template as a clean markdown block for the user to copy.