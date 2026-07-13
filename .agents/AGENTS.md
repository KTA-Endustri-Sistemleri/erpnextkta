# Frappe Framework Contribution Rules (Router)

This `erpnextkta` repository has specific contribution guidelines, rules, and workflows. 
Please refer to the appropriate markdown files below depending on your task. 

**IMPORTANT:** You must actively read these files using your file reading tools if you are about to perform any related action.

## Workflows (Actions & Processes)
* **Creating Commits:** Follow `.agents/workflows/commit_conventions.md`
* **Creating PRs & Branching:** Follow `.agents/workflows/pr_and_branching.md`
* **Building Frontend:** Follow `.agents/workflows/bench_build.md`
* **Restarting Bench:** Follow `.agents/workflows/bench_restart.md`

## Rules (Code Constraints & Standards)
* **Code Style & Linting:** Follow `.agents/rules/code_style_and_linting.md`
* **UI Strings & Translations:** Follow `.agents/rules/translations_and_ui.md`
* **Naming Conventions:** Follow `.agents/rules/naming_conventions.md`
* **Security & DB:** Follow `.agents/rules/security_and_db.md`
* **Module Memory Bank:** Follow `.agents/rules/module_memory_bank.md`

## Project Context & Memory
* **Sanal Yarımamül Grafik Altyapısı (WIP Graph Engine):**
  * Bu sistemin mimarisi, davranış tipleri ve UI/UX detayları oldukça kapsamlıdır. 
  * Yeni oturumlarda, özellikle `wip_graph_engine.py`, `CkGraphViewerModal.vue` veya `AltOperasyonView.vue` dosyalarında değişiklik yapmadan önce **MUTLAKA** proje dizinindeki `erpnextkta/kta_calisma_karti/memory-bank/graph_wip_plan.md` dosyasını okuyun ve mimariye tam olarak hakim olun.
