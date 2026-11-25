# PDA Rol Bazlı Menü ve Operatör Yetkilendirme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task, strictly routing each task to its owning specialist subagent in `.agents/AGENTS.md`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sabit `PDA_DEPARTMENTS` filtresini kaldırarak `/pda` terminalini `KTA PDA Stock User` (`desk_access = 0`) rol tabanlı yetkilendirmeye ve `Stock` ana menüsü + her ekrandan erişilebilen `☰ Menü` çekmecesi mimarisine geçirmek.

**Architecture:** Arka uçta `PDA_MODULE_REGISTRY` üzerinden kategori/ekran bazlı yetki ağacı ve dinamik `ALL_PDA_ROLES` kesişimi tanımlanır; `setup.py`, backfill migration patch'i, `KTA Printer Permission` eşitlemesi, `Role.home_page = "/pda"` ve `EmployeeMaster` sınıfını ezmeyen `pda_user_guard.py` (`doc_events`) koruması ile saf `Website User` operatörlerin `/app` Desk'ten izole biçimde çalışması sağlanır. Ön uçta `PdaMenuDrawer.vue`, bağlamsal breadcrumb üst barı ve `LauncherHome.vue` akıllı açılış akışı sunulur.

**Tech Stack:** Frappe v15, Python 3.11+, Vue 3 (`<script setup lang="ts">`), TypeScript, esbuild (`bench build --app erpnextkta --production`), Vitest + `@vue/test-utils` + `jsdom`, `KTABaseTestCase`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-11-22-pda-role-based-menu-design.md`

---

## Global Constraints

- Koordinatör `erpnextkta/**` veya `docs/**` (`docs/superpowers/**` hariç) dosyalarını doğrudan düzenlemez; her görev ilgili uzman subagent'a (`kta-stock`, `overrides-hooks`, `frontend-public`, `docs-i18n`) `Workspace="inherit"` ile devredilir.
- Tüm `.vue` dosyaları **< 500 satır** kalır; `<script setup lang="ts">` içinde `const __ = (...args: any[]) => (window as any).__(...args);` sarmalayıcısı, `<Teleport to="body">`, Light & `[data-theme="dark"]` tema uyumu, tam cümle bütünlüğü ve Title Case standartları korunur.
- `override_doctype_class["Employee"]` kesinlikle kullanılmaz (`hrms.overrides.employee_master.EmployeeMaster` sınıfı ezilmez); saf `Website User` koruması yalnızca `doc_events` (`erpnextkta/kta_stock/pda_user_guard.py`) üzerinden yapılır.
- `frappe.set_user("Administrator")` gibi belge sahipliğini (`owner`) veya denetim izini bozan yetki yükseltmesi yapılmaz.
- `Role` ve teknik adlar standart İngilizce (`KTA PDA Stock User`) kalır; yeni kullanıcıya dönük metinler (TR/EN/DE) `erpnextkta/translations/{tr,en,de}.csv` dosyalarına yalnızca **append-only (`0` silme)** olarak eklenir.
- Frontend derlemesi yalnızca `bench build --app erpnextkta --production` ile yapılır; Python dosyaları `/home/frappe/frappe-bench/env/bin/ruff check` ve `/home/frappe/frappe-bench/env/bin/ruff format --check` ile doğrulanır.
- Tüm commit mesajları Conventional Commits formatında, her satırı **<= 100 karakter** ve gizli/ticari veri (gerçek tedarikçi/müşteri firma adı veya birim fiyat/maliyet) içermeyecek şekilde oluşturulur.

---

## Review Focus

1. **Saf `Website User` (`KTA PDA Stock User`) personelinin `Employee` kaydı güncellendiğinde (`custom_pda_pin` değişimi vb.) ERPNext `Employee.update_user()`'ın `"Employee"` (`desk_access = 1`) rolünü geri ekleyip `/app` erişimi açması:** Desk rollü kullanıcıya (`KTA Çalışma Kartı Kullanıcısı`) veya doğrudan `User` formundan `"Employee"` atanmasına dokunmamalı, yalnızca saf PDA kullanıcısında engellemelidir (*Task 1*).
2. **Ofis kullanıcısının (`KTA Satış` / `KTA Standart Kullanıcı` -> yalnızca genel `Stock User` rolü) `/pda` veya PIN listesine sızması:** `get_pda_operators()` dışında kalmalı, `/pda` ve `pda_*` uçlarında `frappe.PermissionError` almalıdır (*Task 2*).
3. **Üzerinde `Stock User` olmayan saf `Website User` (`KTA PDA Stock User`) operatörün `picking`, `split`, `transfer` veya `lookup` sırasında `Stock Entry` / `Serial and Batch Bundle` izin hatası alması:** 8 DocType `Custom DocPerm` ile tüm akış hatasız çalışmalı ve oluşan `Stock Entry.owner` operatörün kendi kullanıcısı olmalıdır (*Task 2*).
4. **Kısıtlı Zebra yazıcılarda (`KTA Printer Permission` içinde `Stock User` satırı bulunan yazıcılar) `KTA PDA Stock User` kullanıcısının yazdıramaması ve izin satırı olmayan açık yazıcıların yanlışlıkla kısıtlanması:** `setup_pda_roles_and_permissions()` yalnızca `Stock User` (`can_print = 1`) satırı olan yazıcılara `KTA PDA Stock User` eklemeli, açık yazıcıları boş bırakmalıdır (*Task 1*).
5. **Paylaşımlı cihazda iki operatör arası Devret (`pda_handover_logout`) ve yeniden PIN girişi sonrası eski `menuCategories` / seçili kategori / açık çekmece state'inin asılı kalması:** Kilitlenme ve yeni operatör açılışında tüm gezinme state'i temizlenip yeni operatörün yetkili menüsüne göre akıllı açılış çalışmalıdır (*Task 3*).

---

## File Structure Overview

- **Kurulum, Koruma & Migration (`kta-stock`, `overrides-hooks`):**
  - `erpnextkta/kta_stock/setup.py` — `PDA_ROLE_STOCK_USER`, `setup_pda_roles_and_permissions()`, `Custom DocPerm` ve `KTA Printer Permission` eşitlemesi.
  - `erpnextkta/kta_stock/pda_user_guard.py` — `Employee` & `User` `doc_events` koruma kancaları (`EmployeeMaster` ezilmeden).
  - `erpnextkta/hooks.py` — `doc_events["Employee"]` ve `doc_events["User"]` kayıtları.
  - `erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py` + `erpnextkta/patches.txt` — rol kurulumu ve tek seferlik tahribatsız backfill yaması.
  - `erpnextkta/kta_stock/tests/test_pda_role_setup.py` — rol, `Custom DocPerm`, yazıcı izni, `pda_user_guard` ve backfill testleri.
- **Kayıt Defteri, Servisler & Portal (`kta-stock`, `docs-i18n`):**
  - `erpnextkta/kta_stock/services/pda_service.py` — `PDA_MODULE_REGISTRY`, `ALL_PDA_ROLES`, `get_authorized_menu_categories()`, `_require_pda_screen_access()`, departmansız `get_pda_operators()`, güncellenmiş boot/PIN yanıtları ve ekran guard'ları.
  - `erpnextkta/www/pda.py` — `ALL_PDA_ROLES` kesişimi ile `/pda` giriş kapısı.
  - `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py` & `erpnextkta/kta_stock/line_replenishment_service.py` — `KTA PDA Stock User` erişimi ve picking RPC yetki kontrolleri.
  - `erpnextkta/kta_stock/tests/{test_pda_service,test_pda_portal,test_line_replenishment_picking_page}.py` — departmansız liste, yetki izolasyonu ve saf `Website User` uçtan uca testleri.
- **Frontend SPA (`frontend-public`):**
  - `erpnextkta/public/pda-hub/types.ts` — `PdaScreenKey`, `PdaMenuScreenItem`, `PdaMenuCategory` sözleşmeleri.
  - `erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue` — `<Teleport to="body">` yan çekmece.
  - `erpnextkta/public/pda-hub/components/LauncherHome.vue` — akıllı kategori/ekran/yetki açılışı.
  - `erpnextkta/public/pda-hub/PdaHubApp.vue` — `☰ Menü` butonu, breadcrumb ve Devret state temizliği.
  - `erpnextkta/public/pda-hub/__tests__/{PinLockAndLauncher,PdaHubApp}.spec.ts` — bileşen ve entegrasyon testleri.
- **Dokümantasyon & Çeviriler (`docs-i18n`):**
  - `erpnextkta/translations/{tr,en,de}.csv` — append-only (`0` silme) çeviri senkronizasyonu.
  - `erpnextkta/www/docs/stok-lojistik.html` & `docs/kta_stok_lojistik_kilavuzu.md` — portal ve geliştirici kılavuzu güncellemesi.

---

### Task 1: `KTA PDA Stock User` Rolü, `Custom DocPerm`, Yazıcı İzni, `pda_user_guard` (`doc_events`) ve Backfill Patch

**Subagents:** `kta-stock` (`setup.py`, `pda_user_guard.py`, `test_pda_role_setup.py`) ve `overrides-hooks` (`hooks.py`, `patches/v4_4/setup_pda_stock_role_and_backfill.py`, `patches.txt`)

**Files:**
- Modify: `erpnextkta/kta_stock/setup.py:22-43` (`setup()`, yeni `PDA_ROLE_STOCK_USER`, `setup_pda_roles_and_permissions()`)
- Create: `erpnextkta/kta_stock/pda_user_guard.py`
- Modify: `erpnextkta/hooks.py:159-202` (`doc_events`)
- Create: `erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py`
- Modify: `erpnextkta/patches.txt:25-27`
- Create (Test): `erpnextkta/kta_stock/tests/test_pda_role_setup.py`

**Interfaces:**
- Consumes: `frappe.permissions.{add_permission, update_permission_property}`, `KTA Printer Permission`, `Employee` / `User` `doc_events`
- Produces:
  - `PDA_ROLE_STOCK_USER = "KTA PDA Stock User"` (`erpnextkta/kta_stock/setup.py`)
  - `setup_pda_roles_and_permissions() -> None` (`erpnextkta/kta_stock/setup.py`)
  - `mark_pure_pda_website_user_before_employee_save(doc, method=None) -> None` (`erpnextkta/kta_stock/pda_user_guard.py`)
  - `strip_auto_employee_role_for_pure_pda_user(doc, method=None) -> None` (`erpnextkta/kta_stock/pda_user_guard.py`)
  - `clear_pure_pda_website_user_flag_after_employee_save(doc, method=None) -> None` (`erpnextkta/kta_stock/pda_user_guard.py`)
  - `execute() -> None` & `backfill_existing_pda_stock_operators() -> int` (`erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py`)

- [x] **Step 1: Write the failing tests (`kta-stock` -> `test_pda_role_setup.py`)**

`erpnextkta/kta_stock/tests/test_pda_role_setup.py` dosyasında `KTABaseTestCase` türevi test sınıfı ve aşağıdaki 4 testi yaz:

```python
def test_setup_creates_pda_stock_role_docperms_and_home_page(self):
    setup_pda_roles_and_permissions()
    setup_pda_roles_and_permissions()  # Idempotent second call

    role = frappe.get_doc("Role", PDA_ROLE_STOCK_USER)
    self.assertEqual(cint(role.desk_access), 0)
    self.assertEqual(role.home_page, "/pda")

    expected_perms = {
        "Stock Entry": ("read", "write", "create", "submit"),
        "Serial and Batch Bundle": ("read", "write", "create", "submit"),
        "Batch": ("read", "write", "create"),
        "Stock Ledger Entry": ("read",),
        "Item": ("read",),
        "Warehouse": ("read",),
        "KTA Stock Label": ("read", "write", "create"),
        "KTA Line Replenishment Order": ("read", "write"),
    }
    for dt, rights in expected_perms.items():
        perm = frappe.db.get_value(
            "Custom DocPerm",
            {"parent": dt, "role": PDA_ROLE_STOCK_USER, "permlevel": 0},
            ["read", "write", "create", "submit"],
            as_dict=True,
        )
        self.assertIsNotNone(perm, f"Missing Custom DocPerm for {dt}")
        for right in ("read", "write", "create", "submit"):
            self.assertEqual(cint(perm[right]), 1 if right in rights else 0)
```

```python
def test_setup_mirrors_printer_permissions_only_for_restricted_printers(self):
    # Test double-checks KTA Printer Permission (skipTest only if DocType absent).
    # Create restricted printer with Stock User (can_print=1) and open printer with 0 rows.
    setup_pda_roles_and_permissions()
    setup_pda_roles_and_permissions()

    restricted_rows = frappe.get_all(
        "KTA Printer Permission",
        filters={"printer": restricted_printer.name, "role": PDA_ROLE_STOCK_USER},
        fields=["can_print"],
    )
    self.assertEqual(len(restricted_rows), 1)
    self.assertEqual(cint(restricted_rows[0].can_print), 1)

    open_rows = frappe.get_all(
        "KTA Printer Permission",
        filters={"printer": open_printer.name},
        pluck="role",
    )
    self.assertEqual(open_rows, [])
```

```python
def test_employee_save_preserves_website_user_for_pure_pda_operator_only(self):
    # 1) Pure Website User holding only KTA PDA Stock User: Employee.save() must keep
    #    user_type == "Website User", sync first_name, and NOT append "Employee" role.
    pure_emp.first_name = "Güncel Saha"
    pure_emp.save(ignore_permissions=True)
    pure_user = frappe.get_doc("User", pure_emp.user_id)
    self.assertEqual(pure_user.user_type, "Website User")
    self.assertNotIn("Employee", frappe.get_roles(pure_user.name))
    self.assertEqual(pure_user.first_name, "Güncel Saha")

    # 2) Desk operator holding "KTA Çalışma Kartı Kullanıcısı" (desk_access=1):
    #    Employee.save() retains System User + Employee behavior untouched.
    desk_emp.first_name = "Desk Operatör"
    desk_emp.save(ignore_permissions=True)
    self.assertEqual(frappe.db.get_value("User", desk_emp.user_id, "user_type"), "System User")

    # 3) Explicit admin edit directly on User form adding "Employee" is NOT stripped.
    pure_user.append("roles", {"role": "Employee"})
    pure_user.save(ignore_permissions=True)
    self.assertIn("Employee", frappe.get_roles(pure_user.name))
    self.assertEqual(frappe.db.get_value("User", pure_user.name, "user_type"), "System User")
```

```python
def test_backfill_adds_pda_stock_role_non_destructively(self):
    # Active AMBAR - KTA employee with enabled Stock User user gets KTA PDA Stock User,
    # keeping existing Stock User role intact. Non-AMBAR or disabled users are skipped.
    added_first = backfill_existing_pda_stock_operators()
    self.assertGreaterEqual(added_first, 1)
    self.assertIn(PDA_ROLE_STOCK_USER, frappe.get_roles(ambar_user))
    self.assertIn("Stock User", frappe.get_roles(ambar_user))
    self.assertNotIn(PDA_ROLE_STOCK_USER, frappe.get_roles(other_dept_user))
    self.assertEqual(backfill_existing_pda_stock_operators(), 0)
```

- [x] **Step 2: Run test to verify it fails**

Run: `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_role_setup`  
Expected: FAIL with `ImportError` (`setup_pda_roles_and_permissions`, `pda_user_guard` ve backfill patch henüz yok).

- [x] **Step 3: Implement role setup, printer permission mirror, `pda_user_guard`, hooks & backfill patch**

1. (`kta-stock`) `erpnextkta/kta_stock/setup.py`:
   - `PDA_ROLE_STOCK_USER = "KTA PDA Stock User"` ve `PDA_STOCK_USER_DOCPERMS` sabitini tanımla (`permlevel = 0`, 8 DocType ve tam izin matrisi).
   - `setup_pda_roles_and_permissions() -> None` fonksiyonunu yaz ve `setup()` içinden çağır:
     - `Role` üzerinde `PDA_ROLE_STOCK_USER` yoksa oluştur, varsa `desk_access = 0` ve `home_page = "/pda"` değerlerini güncelle.
     - Her DocType için `Custom DocPerm` satırını (`add_permission` + `update_permission_property`) idempotent olarak garanti et (`read`/`write`/`create`/`submit` haklarını hedef matrise göre set et; diğer rollerin izinlerine dokunma).
     - `frappe.db.exists("DocType", "KTA Printer Permission")` varsa (`istable: 0`; alanları `printer`, `role`, `can_print`), `role = "Stock User"` ve `can_print = 1` kaydı bulunan her `printer` için idempotent olarak bağımsız bir `KTA Printer Permission` belgesi (`{"doctype": "KTA Printer Permission", "printer": printer_name, "role": PDA_ROLE_STOCK_USER, "can_print": 1}`) ekle; hiç `KTA Printer Permission` kaydı bulunmayan yazıcılara dokunma.
2. (`kta-stock`) `erpnextkta/kta_stock/pda_user_guard.py`:
   - `mark_pure_pda_website_user_before_employee_save(doc, method=None) -> None`: `doc.user_id` varsa kullanıcının mevcut rollerini (`Role.desk_access`) denetle; en az bir `desk_access = 0` `"KTA PDA *"` rolüne sahipse ve üzerinde hiç `desk_access = 1` rolü yoksa (`not has_desk_role`) `frappe.local.flags._kta_preserve_pda_website_users` kümesine `doc.user_id` ekle.
   - `strip_auto_employee_role_for_pure_pda_user(doc, method=None) -> None`: `doc.name` bu geçici kümede ise bellekten çıkar ve `doc.roles` içinden `role == "Employee"` satırını temizle (böylece `User.set_system_user()` çalışmadan önce `Website User` korunur; doğrudan `User` formundan `"Employee"` eklenirse küme boş olduğu için dokunulmaz).
   - `clear_pure_pda_website_user_flag_after_employee_save(doc, method=None) -> None`: `finally`/güvenlik temizliği olarak `doc.user_id` kaydını geçici kümeden çıkar.
3. (`overrides-hooks`) `erpnextkta/hooks.py` içinde `doc_events` sözlüğüne `"Employee"` (`before_save`, `on_update`) ve `"User"` (`before_validate`) kancalarını ekle (`override_doctype_class["Employee"]` KESİNLİKLE ekleme).
4. (`overrides-hooks`) `erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py` ve `erpnextkta/patches.txt`:
   - `execute()` önce `setup_pda_roles_and_permissions()`, ardından `backfill_existing_pda_stock_operators()` çalıştırır.
   - `backfill_existing_pda_stock_operators() -> int`: `Employee.status == "Active"` ve `department IN ("AMBAR - KTA", "Sevk")` olan, `user_id` dolu ve `User.enabled == 1` kullanıcısında `"Stock User"` veya `"Stock Manager"` bulunan hesaplara tahribatsız biçimde `"KTA PDA Stock User"` rolünü ekler (zaten varsa atlar, mevcut Desk rollerini silmez), eklenen kullanıcı sayısını döner.
   - `patches.txt` `[post_model_sync]` sonuna `erpnextkta.patches.v4_4.setup_pda_stock_role_and_backfill` satırını ekle.

- [x] **Step 4: Run tests & lint checks**

Run:
```bash
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_role_setup
/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/pda_user_guard.py erpnextkta/hooks.py erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py erpnextkta/kta_stock/tests/test_pda_role_setup.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/pda_user_guard.py erpnextkta/hooks.py erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py erpnextkta/kta_stock/tests/test_pda_role_setup.py
```
Expected: PASS (4/4 tests PASS, ruff check & format exit code 0).

- [x] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/pda_user_guard.py erpnextkta/hooks.py erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py erpnextkta/patches.txt erpnextkta/kta_stock/tests/test_pda_role_setup.py
git commit -m "feat(pda): add KTA PDA Stock User role, user guard, and backfill patch"
```

---

### Task 2: Merkezi `PDA_MODULE_REGISTRY`, Departmansız Operatör Listesi, Dinamik Menü & Saf `Website User` Uçtan Uca Operasyon Testleri

**Subagents:** `kta-stock` (`pda_service.py`, `line_replenishment_picking.py`, `line_replenishment_service.py`, `test_pda_service.py`, `test_pda_portal.py`, `test_line_replenishment_picking_page.py`), `docs-i18n` (`erpnextkta/www/pda.py`)

**Files:**
- Modify: `erpnextkta/kta_stock/services/pda_service.py:23-415,593-1096`
- Modify: `erpnextkta/www/pda.py:1-30`
- Modify: `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py:9-161`
- Modify: `erpnextkta/kta_stock/line_replenishment_service.py:786-815`
- Modify (Tests): `erpnextkta/kta_stock/tests/test_pda_service.py`, `erpnextkta/kta_stock/tests/test_pda_portal.py`, `erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py`

**Interfaces:**
- Consumes: `PDA_ROLE_STOCK_USER` from `erpnextkta/kta_stock/setup.py` (Task 1)
- Produces (`erpnextkta/kta_stock/services/pda_service.py`):
  - `PDA_STOCK_ROLES = {PDA_ROLE_STOCK_USER, "Stock Manager", "System Manager"}`
  - `PDA_MODULE_REGISTRY: list[dict]` (`key="stock"`, `title="Stock"`, `icon="📦"`, `allowed_roles=PDA_STOCK_ROLES`, 4 ekran: `picking`, `split`, `transfer`, `lookup`)
  - `ALL_PDA_ROLES: set[str]` ve `ALLOWED_PDA_ROLES = ALL_PDA_ROLES` (genel `"Stock User"` yer ALMAZ)
  - `get_authorized_menu_categories(user: str | None = None) -> list[dict]` (JSON-serileştirilebilir `list[dict]`, `allowed_roles` kümelerini dışarı sızdırmadan döndürür)
  - `_require_pda_screen_access(screen_keys: str | tuple[str, ...]) -> str`
  - `get_pda_operators() -> list[dict]` (`PDA_DEPARTMENTS` filtresi olmadan)
  - `get_pda_boot_data() -> dict` (`menu_categories` alanı dahil)
  - `verify_pda_pin(employee: str, pin: str) -> dict` (`menu_categories` ve `open_picking_count` alanları dahil)
- Produces (`line_replenishment_picking.py` & `line_replenishment_service.py`):
  - `_require_replenishment_picking_access() -> None` (`{"KTA PDA Stock User", "Stock User", "Stock Manager", "System Manager"}` rol veya `KTA Line Replenishment Order` okuma/yazma izni kontrolü)

- [x] **Step 1: Update fixtures and write failing tests (`kta-stock` -> `test_pda_service.py`, `test_pda_portal.py`, `test_line_replenishment_picking_page.py`)**

1. `test_pda_service.py` ve `test_pda_portal.py` içindeki test yardımcılarını (`_ensure_test_pda_operator`, `_ensure_user_with_roles`) varsayılan `["KTA PDA Stock User"]` ve opsiyonel `user_type="Website User"` destekleyecek biçimde güncelle; mevcut `test_get_pda_operators_...` testini departmansız rol modeline göre uyarla.
2. Aşağıdaki yeni / güncellenmiş testleri ekle:

```python
# test_pda_service.py
def test_get_pda_operators_uses_pda_roles_without_department_and_excludes_plain_stock_user(self):
    self.assertNotIn("Stock User", ALL_PDA_ROLES)
    pda_emp = self._ensure_test_pda_operator(
        email="pda_other_dept@example.com",
        department="_Test Üretim Hattı",
        roles=["KTA PDA Stock User"],
        user_type="Website User",
    )
    office_emp = self._ensure_test_pda_operator(
        email="office_stock_only@example.com",
        department="AMBAR - KTA",
        roles=["Stock User"],
    )
    user_ids = {op["user_id"] for op in get_pda_operators()}
    self.assertIn("pda_other_dept@example.com", user_ids)
    self.assertNotIn("office_stock_only@example.com", user_ids)

    self._set_device_cookie_request()
    frappe.set_user("Guest")
    with self.assertRaises(frappe.ValidationError):
        verify_pda_pin(office_emp, "4829")
    res = verify_pda_pin(pda_emp, "4829")
    self.assertTrue(res["ok"])
    self.assertEqual([c["key"] for c in res["menu_categories"]], ["stock"])
    self.assertEqual(len(res["menu_categories"][0]["items"]), 4)
    self.assertIn("open_picking_count", res)
```

```python
# test_pda_service.py
def test_pure_website_user_executes_picking_split_transfer_lookup_end_to_end(self):
    # Pure Website User holding ONLY ["KTA PDA Stock User"] (no Stock User, no Employee role)
    # 1. get_pda_boot_data() includes menu_categories (Guest -> []) and Stock category after login
    # 2. get_open_replenishment_orders() + complete_line_replenishment_picking() succeeds,
    #    creating Material Transfer Stock Entry with owner == operator_user
    # 3. pda_scan_box(), pda_package_split(), pda_material_transfer(), pda_stock_lookup()
    #    all succeed as pure Website User without PermissionError, and Stock Entry.owner == operator_user
    # 4. Plain office user holding only ["Stock User"] gets PermissionError on pda_scan_box() / pda_stock_lookup()
```

```python
# test_pda_portal.py & test_line_replenishment_picking_page.py
def test_pda_portal_allows_pure_pda_stock_user_and_rejects_plain_stock_user(self):
    # Pure Website User ("KTA PDA Stock User") -> www/pda.py get_context() succeeds & sets device cookie
    # Office user holding only "Stock User" -> www/pda.py get_context() raises frappe.PermissionError

def test_replenishment_picking_rpcs_allow_pda_stock_user_and_reject_guest_or_unauthorized(self):
    # Guest & non-stock Website User -> PermissionError on get_open_replenishment_orders /
    # get_replenishment_order_details / resolve_scanned_barcode / complete_line_replenishment_picking
    # Pure Website User ("KTA PDA Stock User") -> picking page get_context & RPCs succeed
```

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page
```
Expected: FAIL (`PDA_MODULE_REGISTRY` / `ALL_PDA_ROLES` eksik, `Stock User` hâlâ listede ve `/pda`'da yetkili, `menu_categories` dönmüyor, picking RPC'leri `Guest`'i reddetmiyor).

- [x] **Step 3: Implement registry, role-based filtering, portal gate & picking permissions**

1. (`kta-stock`) `erpnextkta/kta_stock/services/pda_service.py`:
   - `PDA_DEPARTMENTS` sabitini kaldır; `PDA_STOCK_ROLES = {PDA_ROLE_STOCK_USER, "Stock Manager", "System Manager"}`, `PDA_MODULE_REGISTRY` (`stock` kategorisi ve 4 ekran), `ALL_PDA_ROLES` ve `ALLOWED_PDA_ROLES = ALL_PDA_ROLES` tanımla.
   - `get_authorized_menu_categories(user: str | None = None) -> list[dict]` fonksiyonunu yaz: kullanıcının `frappe.get_roles()` kümesini kategori/ekran `allowed_roles` kümeleriyle kesiştirir; `Guest` için `[]`, yetkili kullanıcı için yalnızca en az 1 yetkili ekranı olan kategorileri (`key`, `title`, `icon`, `items`) döner.
   - `_is_authorized_pda_user(user: str | None = None) -> bool` (ve geriye dönük uyumlu alias `_is_authorized_stock_user`) ve `_require_pda_screen_access(screen_keys: str | tuple[str, ...]) -> str` yaz; `pda_scan_box` (`("split", "transfer")`), `pda_package_split("split")`, `pda_material_transfer("transfer")`, `pda_stock_lookup("lookup")` içinde çağır.
   - `get_pda_operators()` ve `_validate_pda_operator_record()` üzerinden `department` filtresini tamamen kaldır; yalnızca `Employee.status == "Active"`, `User.enabled == 1` ve `_is_authorized_pda_user(emp.user_id)` koşullarını uygula.
   - `get_pda_boot_data()` çıktısına `"menu_categories": get_authorized_menu_categories(current_user)` ekle.
   - `verify_pda_pin()` başarılı dönüşüne `"menu_categories": get_authorized_menu_categories(emp.user_id)` ve `"open_picking_count": cint(...)` ekle.
2. (`docs-i18n`) `erpnextkta/www/pda.py`:
   - `ALLOWED_PDA_ROLES` yerine doğrudan `ALL_PDA_ROLES` (aynı küme) kontrolüyle ofis `Stock User` kullanıcısını `PermissionError` ile reddet, `KTA PDA Stock User` (`Website User`) kullanıcısını kabul edip cihaz çerezini yaz.
3. (`kta-stock`) `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py` ve `erpnextkta/kta_stock/line_replenishment_service.py`:
   - `line_replenishment_picking.py:get_context` içinde `allowed_roles` kümesine `"KTA PDA Stock User"` ekle (mevcut `has_permission("Stock Entry", "read") or has_permission("KTA Line Replenishment Order", "read")` kontrolünü koru).
   - `_require_replenishment_picking_access()` helper'ını tanımla (`{"KTA PDA Stock User", "Stock User", "Stock Manager", "System Manager"}` rollerinden biri VEYA `frappe.has_permission("KTA Line Replenishment Order", "read"|"write")`; aksi halde `frappe.PermissionError`); `get_open_replenishment_orders`, `get_replenishment_order_details`, `resolve_scanned_barcode` ve `line_replenishment_service.py:complete_line_replenishment_picking` başında çağır. (`override_item_source` ve `cancel_line_replenishment_order` mevcut Desk akışıyla uyumlu kalır.)

- [x] **Step 4: Run tests & lint checks**

Run:
```bash
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer
/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/services/pda_service.py erpnextkta/www/pda.py erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py erpnextkta/kta_stock/line_replenishment_service.py erpnextkta/kta_stock/tests/test_pda_service.py erpnextkta/kta_stock/tests/test_pda_portal.py erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/services/pda_service.py erpnextkta/www/pda.py erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py erpnextkta/kta_stock/line_replenishment_service.py erpnextkta/kta_stock/tests/test_pda_service.py erpnextkta/kta_stock/tests/test_pda_portal.py erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py
```
Expected: PASS (tüm test modülleri ve ruff kontrolleri 0 hata).

- [x] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/services/pda_service.py erpnextkta/www/pda.py erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py erpnextkta/kta_stock/line_replenishment_service.py erpnextkta/kta_stock/tests/test_pda_service.py erpnextkta/kta_stock/tests/test_pda_portal.py erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py
git commit -m "feat(pda): switch PDA auth and menu tree to role-based registry"
```

---

### Task 3: Frontend `Stock` Ana Menüsü, `PdaMenuDrawer.vue` (`☰ Menü`), Breadcrumb Üst Bar & Vitest Testleri

**Subagent:** `frontend-public`

**Files:**
- Modify: `erpnextkta/public/pda-hub/types.ts:1-35`
- Create: `erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue`
- Modify: `erpnextkta/public/pda-hub/components/LauncherHome.vue:1-111`
- Modify: `erpnextkta/public/pda-hub/PdaHubApp.vue:1-332`
- Modify (Tests): `erpnextkta/public/pda-hub/__tests__/PinLockAndLauncher.spec.ts`, `erpnextkta/public/pda-hub/__tests__/PdaHubApp.spec.ts`

**Interfaces:**
- Consumes: `PdaBootData.menu_categories`, `VerifyPdaPinResponse.{menu_categories, open_picking_count}` (Task 2)
- Produces:
  - `types.ts`: `PdaScreenKey = "picking" | "split" | "transfer" | "lookup"`, `PdaModuleKey = "home" | PdaScreenKey`, `PdaMenuScreenItem`, `PdaMenuCategory`, güncellenmiş `PdaBootData` & `VerifyPdaPinResponse`
  - `PdaMenuDrawer.vue`: props (`isOpen`, `categories`, `activeScreen`, `selectedCategoryKey`, `openPickingCount`) & emits (`close`, `select-screen`, `select-category`, `select-all-modules`)
  - `LauncherHome.vue`: props (`menuCategories`, `selectedCategoryKey`, `openPickingCount`, `operatorName`) & emits (`select`, `select-category: string | null`)
  - `PdaHubApp.vue`: `[data-testid="topbar-menu-btn"]` (`☰ Menü`) + alt ekrandayken mevcut `[data-testid="topbar-back-btn"]`, breadcrumb başlığı (`KTA PDA` / `Stock` / `Stock › Koli Bölme`), handover/unlock gezinme state sıfırlaması

- [x] **Step 1: Write failing Vitest specs (`frontend-public` -> `PinLockAndLauncher.spec.ts`, `PdaHubApp.spec.ts`)**

Aşağıdaki beklentileri ve mevcut fixture uyumunu Vitest dosyalarına ekle (`menuCategories = []` artık yetkisiz kullanıcı ekranını gösterdiğinden `PinLockAndLauncher.spec.ts` ve `PdaHubApp.spec.ts` içindeki mevcut `LauncherHome` / `makeBoot()` / `verify_pda_pin` test fixture'ları varsayılan `Stock` kategorisi (`menu_categories`) içerecek biçimde güncellenir):

```typescript
// PinLockAndLauncher.spec.ts
it("renders screen cards directly for single category, category cards for multiple, and empty state for zero", async () => {
  // 1) menuCategories = [stockCategory] -> module-card-picking..lookup directly visible, emits select("split")
  // 2) menuCategories = [stockCategory, qualityCategory], selectedCategoryKey = null ->
  //    renders category cards [data-testid="category-card-stock"], [data-testid="category-card-quality"]; clicking emits select-category("stock")
  // 3) menuCategories = [] -> shows empty state [data-testid="no-authorized-modules"] ("Yetkili Modül Bulunamadı")
});

it("PdaMenuDrawer navigates between categories/screens and closes on selection, Escape, and backdrop", async () => {
  // Renders inside <Teleport to="body"> when isOpen=true
  // Shows picking badge, Ana Modüller button only when categories.length > 1
  // Clicking screen item emits select-screen("transfer") and close; Escape / backdrop emit close
});
```

```typescript
// PdaHubApp.spec.ts
it("opens slide-over drawer from topbar-menu-btn, updates breadcrumb, and resets menu state on operator handover", async () => {
  // 1) Login as Operator A (Stock category only):
  //    - LauncherHome shows Stock screens directly, breadcrumb displays "Stock"
  //    - Selecting "split" sets breadcrumb to "Stock › Koli Bölme"
  //    - Clicking [data-testid="topbar-menu-btn"] opens drawer; switching to "picking" closes drawer and updates breadcrumb to "Stock › Hat İkmal Toplama"
  // 2) Handover (pda_handover_logout) -> verify_pda_pin as Operator B (returning updated menu_categories=[]):
  //    - Stale Operator A menuCategories, selectedCategoryKey, activeModule and drawer open state are completely cleared
  //    - Operator B immediately sees [data-testid="no-authorized-modules"] instead of Operator A's Stock cards
});
```

- [x] **Step 2: Run Vitest to verify it fails**

Run: `npm --prefix erpnextkta/public/pda-hub test`  
Expected: FAIL (`PdaMenuDrawer.vue` mevcut değil, `topbar-menu-btn` ve yeni `LauncherHome` prop sözleşmesi eksik).

- [x] **Step 3: Implement TypeScript types, `PdaMenuDrawer.vue`, `LauncherHome.vue`, and `PdaHubApp.vue`**

1. `erpnextkta/public/pda-hub/types.ts`: `PdaScreenKey`, `PdaMenuScreenItem`, `PdaMenuCategory` (`key`, `title`, `icon`, `items`), güncellenmiş `PdaBootData` (`menu_categories: PdaMenuCategory[]`) ve `VerifyPdaPinResponse` (`menu_categories?: PdaMenuCategory[]`, `open_picking_count?: number`) alanlarını ekle.
2. `erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue`: `< 500` satır, `<Teleport to="body">`, Light & `[data-theme="dark"]` uyumlu dokunmatik sol çekmece. Escape tuşu (`keydown` listener lifecycle temizliğiyle) ve backdrop tıklamasıyla kapanır; `categories.length > 1` iken üstte `Ana Modüller` bağlantısı, altında tüm yetkili kategoriler (`__(cat.title)`) ve ekran öğeleri (`picking` yanında canlı `openPickingCount` rozeti) listelenir; bir ekrana dokunulduğunda `select-screen` + `close` emit edilir.
3. `erpnextkta/public/pda-hub/components/LauncherHome.vue`: Sabit 4-kart dizisini kaldır; gelen `menuCategories` dizisine göre:
   - `length === 0`: `[data-testid="no-authorized-modules"]` ile `"Yetkili Modül Bulunamadı"` bilgilendirme kartı,
   - `length > 1` ve `selectedCategoryKey === null`: ana kategori kartları (`[data-testid="category-card-${cat.key}"]`),
   - Tek kategori veya seçili kategori aktifken: ilgili kategorinin yetkili alt ekran kartları (`[data-testid="module-card-${item.key}"]`) ve çoklu kategori varsa `select-category(null)` emit eden `"← Ana Modüller"` dönüş butonu render edilir.
4. `erpnextkta/public/pda-hub/PdaHubApp.vue`:
   - `menuCategories` (`boot.menu_categories ?? []`), `selectedCategoryKey` (`string | null`), `isDrawerOpen` (`ref(false)`) state'lerini ekle.
   - Üst barda her görünümde erişilebilir yeni `[data-testid="topbar-menu-btn"]` (`☰ Menü`) butonunu ve alt ekrandayken mevcut `[data-testid="topbar-back-btn"]` geri butonunu koruyarak bağlamsal breadcrumb (`KTA PDA` / `Stock` / `Stock › ...`) göster (`<PdaMenuDrawer>` bağla).
   - Mevcut test fixture uyumluluğu: `PinLockAndLauncher.spec.ts` ve `PdaHubApp.spec.ts` içindeki mevcut `LauncherHome` / `makeBoot()` / `verify_pda_pin` fixture'larını varsayılan `Stock` kategorisi (`menu_categories`) içerecek biçimde güncelle (aksi halde `menuCategories = []` ile yetkisiz ekranı görünür).
   - `handleUnlocked`: `verify_pda_pin` yanıtındaki `menu_categories` ve `open_picking_count` alanlarını anında uygula (ardından `refreshBootState` ile tazele), `selectedCategoryKey = menuCategories.value.length === 1 ? menuCategories.value[0].key : null`, `activeModule = "home"`, `isDrawerOpen = false` sıfırla.
   - `handleHandoverLogout` ve `handleAuthExpired`: `menuCategories = []`, `selectedCategoryKey = null`, `activeModule = "home"`, `isDrawerOpen = false` ile eski operatör izlerini tamamen temizle.

- [x] **Step 4: Run Vitest, line-count check, and production build**

Run:
```bash
npm --prefix erpnextkta/public/pda-hub test
wc -l erpnextkta/public/pda-hub/PdaHubApp.vue erpnextkta/public/pda-hub/components/LauncherHome.vue erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue
bench build --app erpnextkta --production
```
Expected: Tüm Vitest testleri PASS, tüm `.vue` dosyaları `< 500` satır, `bench build` 0 hata.

- [x] **Step 5: Commit**

```bash
git add erpnextkta/public/pda-hub/types.ts erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue erpnextkta/public/pda-hub/components/LauncherHome.vue erpnextkta/public/pda-hub/PdaHubApp.vue erpnextkta/public/pda-hub/__tests__/PinLockAndLauncher.spec.ts erpnextkta/public/pda-hub/__tests__/PdaHubApp.spec.ts
git commit -m "feat(pda): add Stock main menu, slide-over drawer, and breadcrumbs"
```

---

### Task 4: Portal Dokümantasyonu, Geliştirici Kılavuzu, Append-Only TR/EN/DE Çeviriler ve Final Kalite Kapısı

**Subagents:** `docs-i18n` ve Koordinatör (Final Quality Gate)

**Files:**
- Modify (append-only): `erpnextkta/translations/tr.csv`, `erpnextkta/translations/en.csv`, `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/www/docs/stok-lojistik.html:225-290`
- Modify: `docs/kta_stok_lojistik_kilavuzu.md:139-175`

**Interfaces:**
- Consumes: Task 1–3 içindeki tüm yeni `_()` / `__()` metinleri (`PDA_MODULE_REGISTRY`, `pda_service.py`, `line_replenishment_picking.py`, `PdaMenuDrawer.vue`, `LauncherHome.vue`, `PdaHubApp.vue`) ve rol/guard mimarisi
- Produces: Geçerli CSV sözlükleri (`0` silme) ve senkronize `/docs/stok-lojistik` + geliştirici kılavuzu

- [x] **Step 1: Append-only sync TR/EN/DE translation dictionaries (`docs-i18n`)**

1. Task 1–3 dosyalarındaki tüm yeni `_()` ve `__()` dizgelerini çıkar (`Stock`, `Ana Modüller`, `Menü`, `Menüyü Kapat`, `Yetkili Modül Bulunamadı`, `Size atanmış aktif bir PDA modülü bulunmamaktadır. Yöneticinizle iletişime geçin.`, yeni ekran/hata mesajları vb.).
2. `erpnextkta/translations/{tr,en,de}.csv` mevcut satırlarına KESİNLİKLE dokunmadan, yalnızca eksik yeni anahtarları **strictly append-only** olarak sona ekle (Title Case, tam cümle bütünlüğü, virgül içeren satırlarda CSV tırnaklama).
3. Doğrula: `git diff --numstat -- erpnextkta/translations/` çıktısında deletion `0` olmalı ve Python `csv.reader` 3 dosyayı da hatasız parse etmelidir.

- [x] **Step 2: Synchronize Portal HTML & Developer Guide (`docs-i18n`)**

1. `erpnextkta/www/docs/stok-lojistik.html` (Bölüm 10 `📱 10. Bağımsız PDA Depo Merkezi (/pda)`) ve `docs/kta_stok_lojistik_kilavuzu.md` (Bölüm 10) dosyalarını güncelle:
   - Departmansız rol tabanlı operatör listesi (`KTA PDA Stock User`, `Stock Manager`, `System Manager`), genel `Stock User` profilinin ayrıştırılması.
   - `KTA PDA Stock User` (`desk_access = 0`, `home_page = "/pda"`) ile saf `Website User` izolasyonu ve `pda_user_guard.py` (`doc_events`) koruması.
   - `KTA Printer Permission` eşitlemesi ve `Stock` ana menüsü + her ekrandan erişilebilen `☰ Menü` çekmecesi / breadcrumb akışı.
   - Kesinlikle gerçek tedarikçi/müşteri firma adı veya birim fiyat/maliyet bilgisi ekleme.

- [x] **Step 3: Run full Coordinator Final Quality Gate**

Run:
```bash
bench --site development.localhost migrate
bench build --app erpnextkta --production
/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/pda_user_guard.py erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py erpnextkta/kta_stock/line_replenishment_service.py erpnextkta/www/pda.py erpnextkta/hooks.py erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py erpnextkta/kta_stock/tests/test_pda_role_setup.py erpnextkta/kta_stock/tests/test_pda_service.py erpnextkta/kta_stock/tests/test_pda_portal.py erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/pda_user_guard.py erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py erpnextkta/kta_stock/line_replenishment_service.py erpnextkta/www/pda.py erpnextkta/hooks.py erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py erpnextkta/kta_stock/tests/test_pda_role_setup.py erpnextkta/kta_stock/tests/test_pda_service.py erpnextkta/kta_stock/tests/test_pda_portal.py erpnextkta/kta_stock/tests/test_line_replenishment_picking_page.py
npm --prefix erpnextkta/public/pda-hub test
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_role_setup
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_transfer
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service
git diff --numstat -- erpnextkta/translations/
```
Expected: Migrate, production build, ruff check/format, Vitest, tüm Frappe test modülleri 0 hata ile geçer; CSV diff'lerinde silinen satır sayısı `0` olur.

- [x] **Step 4: Commit documentation & translations**

```bash
git add erpnextkta/translations/tr.csv erpnextkta/translations/en.csv erpnextkta/translations/de.csv erpnextkta/www/docs/stok-lojistik.html docs/kta_stok_lojistik_kilavuzu.md
git commit -m "docs(pda): document role-based PDA menu and sync TR/EN/DE translations"
```

---

## Self-Review Checklist

1. **Spec coverage:** `KTA PDA Stock User` (`desk_access=0`, `home_page="/pda"`), 8 DocType `Custom DocPerm`, `KTA Printer Permission` eşitlemesi ve backfill patch (Task 1); `EmployeeMaster` ezmeden `pda_user_guard.py` `doc_events` koruması (Task 1); `PDA_MODULE_REGISTRY`, `ALL_PDA_ROLES`, departmansız `get_pda_operators()`, dinamik `menu_categories`, `www/pda.py` ve `line_replenishment_picking` yetki sınırları ile saf `Website User` uçtan uca testleri (Task 2); `PdaMenuDrawer.vue`, breadcrumb üst bar ve akıllı açılış `LauncherHome.vue` (Task 3); append-only TR/EN/DE çeviri + `/docs/stok-lojistik` + kılavuz senkronizasyonu (Task 4). Boşluk yok.
2. **Type & Signature consistency:** `PDA_ROLE_STOCK_USER`, `setup_pda_roles_and_permissions()`, `pda_user_guard.{mark_pure_pda_website_user_before_employee_save,strip_auto_employee_role_for_pure_pda_user,clear_pure_pda_website_user_flag_after_employee_save}`, `PDA_MODULE_REGISTRY`, `ALL_PDA_ROLES`, `get_authorized_menu_categories()`, `_require_pda_screen_access()`, `PdaMenuCategory`, `PdaMenuScreenItem`, `menu_categories` ve `topbar-menu-btn` adları hem spec hem Task 1–4 içinde birebir aynıdır.
3. **Review Focus coverage:** 5 kritik uç durumun tamamı (saf `Website User` `Employee` kaydı koruması, ofis `Stock User` izolasyonu, 8 DocType uçtan uca `owner` uyumu, kısıtlı/açık Zebra yazıcı ayrımı, operatör devri sonrası menü state temizliği) ilgili Task testleriyle doğrudan sabitlenmiştir.
