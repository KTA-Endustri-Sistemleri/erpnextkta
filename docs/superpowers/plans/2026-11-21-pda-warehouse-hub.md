# KTA PDA Depo Merkezi (Unified PDA Warehouse Hub) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task, strictly routing each task to its owning specialist subagent in `.agents/AGENTS.md`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, zero-Desk-overhead `/pda` PWA Warehouse Hub unifying PIN-based Frappe session switching, Line Replenishment Picking, Package Splitting with Zebra printing, Ad-hoc Full-Box Material Transfer, and Quick Barcode/Shelf Lookup.

**Architecture:** Frappe `www/pda` standalone portal serves a single Vue 3 + TypeScript esbuild bundle (`pda-hub.bundle`) backed by a lightweight `window.frappe` fetch/i18n shim (avoiding 15MB Desk assets). Device authorization uses an HMAC-SHA256 signed HTTP-only `kta_pda_device` cookie while operator PIN login switches the actual Frappe user session via `LoginManager.login_as(employee.user_id)`, yielding native `owner`/`modified_by` audit trails and `KTA User Zebra Printers` resolution without adding any `custom_operator` field.

**Tech Stack:** Frappe v15, Python 3.12, Vue 3 (`<script setup lang="ts">`), TypeScript, esbuild (`bench build --app erpnextkta --production`), Vitest + `@vue/test-utils` + `jsdom`, `KTABaseTestCase` / `KTAUnitTestCase`.

**Spec:** `docs/superpowers/specs/2026-11-21-pda-warehouse-hub-design.md`

---

## Global Constraints

- Koordinatör hiçbir zaman doğrudan `erpnextkta/**` veya `docs/**` (`docs/superpowers/**` hariç) dosyalarını düzenlemez; her görev kendi uzman subagent'ına (`kta-stock`, `overrides-hooks`, `frontend-public`, `docs-i18n`) `Workspace="inherit"` ile devredilir.
- Tüm `.vue` dosyaları **500 satırın altında** kalmalıdır; `<script setup lang="ts">` içinde daima `const __ = (...args: any[]) => (window as any).__(...args);` tanımlanır ve metinler Title Case + tam cümle bütünlüğünde tutulur.
- `Stock Entry` veya `KTA Line Replenishment Order` DocType'larına kesinlikle `custom_operator` alanı eklenmez; yalnızca `LoginManager.login_as(employee.user_id)` üzerinden yerel Frappe `owner` / `modified_by` izlenebilirliği kullanılır.
- `1 Kutu = 1 Parti (7+4)` kuralı korunur: `pda_material_transfer` yalnızca tam kutu/bakiye transferine izin verir ve grup depolarını (`is_group=1`) reddeder.
- `Package Split` işlemlerinde `KTAStockEntry.on_submit()` hedef yeni kutuları zaten otomatik bastığı için `pda_package_split` hedef kutuları ikinci kez kuyruğa almaz; yalnızca `remaining_qty > 0` ve `reprint_source_label == 1` olduğunda güncellenen kaynak kutu etiketini bastırır.
- Frontend derlemesi yalnızca `bench build --app erpnextkta --production` ile yapılır; Python dosyaları `/home/frappe/frappe-bench/env/bin/ruff` ile check & format kontrolünden geçirilir.
- Tüm commit mesajları Conventional Commits formatında ve her satırı **$\le 100$ karakter** olmalıdır; ticari/tedarikçi/fiyat verisi içermez.

---

## Review Focus

1. **Yetkisiz dış tarayıcıdan (`Guest` + geçersiz/yok `kta_pda_device` çerezi) `/pda` veya `verify_pda_pin` çağrılması:** `/pda` sayfası `/login?redirect-to=/pda` adresine yönlendirmeli, `get_pda_boot_data` ve `verify_pda_pin` ise `frappe.PermissionError` fırlatmalıdır (Task 2 & Task 4'te test edilir).
2. **PIN brute-force (`>= 5` hatalı deneme) veya tanımsız/eksik `custom_pda_pin`:** `frappe.cache()` üzerinde `pda_pin_fail:{employee}` sayacı 5 hatalı denemeden sonra 300 saniye kilit uygulamalı; boş veya 4 hane olmayan PIN kesinlikle geçmemelidir (Task 2'de test edilir).
3. **`pda_package_split` çift etiket baskısı riski:** Hedef kutular `KTAStockEntry.on_submit()` üzerinden tam 1 kez basılmalı; kaynak kutu yalnızca `remaining_qty > 0` ve `reprint_source_label=1` iken 1 kez yeniden basılmalı, tam tüketimde (`remaining_qty == 0`) veya `reprint_source_label=0` iken 0 kez basılmalıdır (Task 3'te test edilir).
4. **Kısmi miktar, grup depo (`is_group=1`), Taslak `Stock Reconciliation` kilidi veya bekleyen `Quality Inspection` ile `pda_material_transfer`:** Transfer atomik olarak `ValidationError` ile reddedilmeli ve arkada sıfır Stock Ledger Entry bırakmalıdır (Task 3'te test edilir).
5. **Devret (`pda_handover_logout`) ve yeniden PIN girişi (`verify_pda_pin`) sonrası bayat `csrf_token`:** Sunucu her oturum değişiminde güncel `csrf_token` döndürmeli, `frappeShim.ts` içindeki `updateCsrfToken` ile `window.csrf_token` anında yenilenerek sonraki POST isteklerinin sayfa yenilemeden çalışması sağlanmalıdır (Task 2 & Task 5'te test edilir).

---

## File Structure Overview

- **Şema & Migration (`overrides-hooks`, `kta-stock`):**
  - `erpnextkta/kta_stock/setup.py` — `setup_pda_custom_fields()` ve `setup()` entegrasyonu.
  - `erpnextkta/patches/v4_4/add_employee_pda_pin_field.py` + `erpnextkta/patches.txt` — idempotent migrate yaması.
  - `erpnextkta/hooks.py` — `Custom Field` fixture filtresine `"Employee-custom_pda_pin"` eklenmesi.
- **Backend Servis & Testler (`kta-stock`):**
  - `erpnextkta/kta_stock/services/pda_service.py` — cihaz çerezi, PIN/session yönetimi, depo barkodu çözümleme, koli bölme, serbest tam kutu transfer ve hızlı stok sorgu API'leri.
  - `erpnextkta/kta_stock/tests/test_pda_service.py` — auth + depo operasyon birim/entegrasyon testleri.
  - `erpnextkta/kta_stock/tests/test_pda_portal.py` — `/pda` web portal context ve yetki testleri.
  - `erpnextkta/kta_stock/tests/test_relabeling_service.py` — custom field setup testi.
- **Portal Girişi (`docs-i18n`, `frontend-public`):**
  - `erpnextkta/www/pda.py` & `erpnextkta/www/pda.html` — bağımsız PWA kabuğu (sıfır Desk yükü).
  - `erpnextkta/public/pda-hub/manifest.webmanifest` — Android/iOS standalone PWA manifesti.
- **Frontend SPA (`frontend-public`):**
  - `erpnextkta/public/pda-hub/` — `pda-hub.bundle.ts`, `PdaHubApp.vue`, `types.ts`, `utils/frappeShim.ts`, `composables/useInactivityLock.ts`, `components/{PdaOverlays,PinLockScreen,LauncherHome}.vue`, `views/{PickingModuleView,PackageSplitView,MaterialTransferView,StockLookupView}.vue`, Vitest yapılandırması ve `__tests__/`.
- **Dokümantasyon & Çeviri (`docs-i18n`):**
  - `erpnextkta/translations/{tr,en,de}.csv`
  - `erpnextkta/www/docs/stok-lojistik.html` & `docs/kta_stok_lojistik_kilavuzu.md`

---

### Task 1: `Employee-custom_pda_pin` Schema Setup, Patch & Fixture ✅ (Tamamlandı)

**Subagents:** `kta-stock` (setup + test) ve `overrides-hooks` (patch + `patches.txt` + `hooks.py`)  
**Files:**
- Modify: `erpnextkta/kta_stock/setup.py` (`setup()`, yeni `setup_pda_custom_fields()`)
- Modify: `erpnextkta/kta_stock/tests/test_relabeling_service.py`
- Create: `erpnextkta/patches/v4_4/add_employee_pda_pin_field.py`
- Modify: `erpnextkta/patches.txt`
- Modify: `erpnextkta/hooks.py` (Custom Field fixture listesi)

**Interfaces:**
- Consumes: `frappe.custom.doctype.custom_field.custom_field.create_custom_fields`
- Produces:
  - `setup_pda_custom_fields() -> None` in `erpnextkta/kta_stock/setup.py`
  - Custom Field `"Employee-custom_pda_pin"` (`fieldtype="Password"`, `label="PDA PIN"`, `insert_after="attendance_device_id"`, `max_length=4`)

- [x] **Step 1: Write the failing test (`kta-stock`)**

`erpnextkta/kta_stock/tests/test_relabeling_service.py` içine aşağıdaki testi ekle:

```python
def test_setup_creates_employee_pda_pin_custom_field(self):
    from frappe.utils.password import get_decrypted_password, set_encrypted_password
    from erpnextkta.kta_stock.setup import setup_pda_custom_fields

    setup_pda_custom_fields()
    cf = frappe.db.get_value(
        "Custom Field",
        "Employee-custom_pda_pin",
        ["dt", "fieldname", "fieldtype", "label", "insert_after"],
        as_dict=True,
    )
    self.assertIsNotNone(cf)
    self.assertEqual(cf.dt, "Employee")
    self.assertEqual(cf.fieldname, "custom_pda_pin")
    self.assertEqual(cf.fieldtype, "Password")
    self.assertEqual(cf.insert_after, "attendance_device_id")

    emp = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name", limit=1)[0]
    set_encrypted_password("Employee", emp, "4829", fieldname="custom_pda_pin")
    self.assertEqual(get_decrypted_password("Employee", emp, fieldname="custom_pda_pin"), "4829")
```

- [x] **Step 2: Run test to verify it fails**

Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service --test test_setup_creates_employee_pda_pin_custom_field`  
Expected: FAIL with `ImportError: cannot import name 'setup_pda_custom_fields'`

- [x] **Step 3: Implement `setup_pda_custom_fields()`, migration patch, and fixture registration**

1. (`kta-stock`) `erpnextkta/kta_stock/setup.py` içinde `setup_pda_custom_fields() -> None` tanımla ve `setup()` içinden çağır; `create_custom_fields({"Employee": [...]})` kullanarak `custom_pda_pin` alanını (`fieldtype="Password"`, `label="PDA PIN"`, `insert_after="attendance_device_id"`, `description="4 haneli PDA giriş PIN kodu"`) idempotent oluştur.
2. (`overrides-hooks`) `erpnextkta/patches/v4_4/add_employee_pda_pin_field.py` dosyasında `execute()` fonksiyonunu yazıp `setup_pda_custom_fields()` çağır.
3. (`overrides-hooks`) `erpnextkta/patches.txt` `[post_model_sync]` sonuna `erpnextkta.patches.v4_4.add_employee_pda_pin_field` ekle.
4. (`overrides-hooks`) `erpnextkta/hooks.py` içindeki `fixtures` -> `Custom Field` listesine `"Employee-custom_pda_pin"` ekle.

- [x] **Step 4: Run test & migrate verification**

Run:
`bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service`  
`/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/setup.py erpnextkta/patches/v4_4/add_employee_pda_pin_field.py erpnextkta/hooks.py erpnextkta/kta_stock/tests/test_relabeling_service.py`  
`/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/setup.py erpnextkta/patches/v4_4/add_employee_pda_pin_field.py erpnextkta/hooks.py erpnextkta/kta_stock/tests/test_relabeling_service.py`  
Expected: PASS (tüm testler OK ve ruff temiz).

- [x] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/tests/test_relabeling_service.py erpnextkta/patches/v4_4/add_employee_pda_pin_field.py erpnextkta/patches.txt erpnextkta/hooks.py
git commit -m "feat(pda): add Employee custom_pda_pin field and migration"
```

---

### Task 2: PDA Device Token, Operator Discovery, PIN Verification (`login_as`) & Handover Service ✅ (Tamamlandı)

**Subagent:** `kta-stock`  
**Files:**
- Create: `erpnextkta/kta_stock/services/pda_service.py`
- Create: `erpnextkta/kta_stock/tests/test_pda_service.py`

**Interfaces:**
- Consumes: `"Employee-custom_pda_pin"` from Task 1 (`frappe.utils.password.get_decrypted_password`)
- Produces in `erpnextkta/kta_stock/services/pda_service.py`:
  - `ALLOWED_PDA_ROLES = {"Stock User", "Stock Manager", "System Manager"}`
  - `PDA_DEVICE_COOKIE = "kta_pda_device"`
  - `PDA_DEVICE_TTL_SECONDS = 30 * 24 * 3600`
  - `PDA_INACTIVITY_TIMEOUT_SEC = 300`
  - `PDA_DEPARTMENTS = ("AMBAR - KTA", "Sevk")`
  - `issue_pda_device_token(device_id: str | None = None) -> str`
  - `verify_pda_device_token(token: str | None) -> bool`
  - `has_valid_pda_device_cookie() -> bool`
  - `set_pda_device_cookie(device_id: str | None = None) -> str`
  - `get_pda_operators() -> list[dict]`
  - `get_pda_boot_data() -> dict` (`@frappe.whitelist(allow_guest=True)`)
  - `verify_pda_pin(employee: str, pin: str) -> dict` (`@frappe.whitelist(allow_guest=True, methods=["POST"])`)
  - `pda_handover_logout() -> dict` (`@frappe.whitelist(allow_guest=True, methods=["POST"])`)

- [x] **Step 1: Write the failing auth & session tests (`test_pda_service.py`)**

`erpnextkta/kta_stock/tests/test_pda_service.py` içinde `KTABaseTestCase` sınıfı altında şu 6 testi yaz:
- `test_device_token_roundtrip_and_tamper_rejection`: `issue_pda_device_token()` çıktısının `verify_pda_device_token()` ile `True` döndüğünü; imzası bozulmuş veya süresi geçmiş token'ların `False` döndüğünü doğrular.
- `test_guest_without_device_cookie_rejected_on_boot_and_pin`: `frappe.set_user("Guest")` ve çerezsiz durumda `get_pda_boot_data()` ile `verify_pda_pin()` çağrılarının `frappe.PermissionError` fırlattığını doğrular.
- `test_get_pda_operators_filters_active_ambar_sevk_with_enabled_stock_user`: Yalnızca `status="Active"`, `department IN ("AMBAR - KTA", "Sevk")`, etkin (`enabled=1`) ve `ALLOWED_PDA_ROLES` rolüne sahip `user_id`'li çalışanların (`name`, `employee_name`, `department`, `user_id`) döndüğünü; `user_id` boş veya pasif kullanıcıların filtrelendiğini doğrular.
- `test_verify_pda_pin_switches_frappe_session_and_returns_csrf`: Geçerli `kta_pda_device` çerezi taklit edilirken (`verify_pda_device_token` mock veya request cookie) 4 haneli doğru PIN ile `verify_pda_pin()` çağrıldığında `frappe.session.user == emp.user_id` olduğunu ve yanıtın `{"ok": True, "user": emp.user_id, "employee": emp.name, "employee_name": emp.employee_name, "csrf_token": ...}` içerdiğini doğrular.
- `test_verify_pda_pin_rate_limits_after_five_failures_and_rejects_missing_pin`: PIN tanımlı olmayan çalışanda veya hatalı 4 hane formatında `ValidationError` döndüğünü; 5 ardışık hatalı PIN denemesinden sonra cache anahtarı `pda_pin_fail:{employee}` üzerinden 6. denemenin doğru PIN ile bile bloklandığını doğrular.
- `test_pda_handover_logout_ends_user_session_and_preserves_device_flow`: Oturum açıkken `pda_handover_logout()` çağrısının `frappe.local.login_manager.logout()` işlemini tetiklediğini, yeni `csrf_token` ve `{"ok": True, "device_authorized": True, ...}` döndürdüğünü doğrular.

- [x] **Step 2: Run tests to verify they fail**

Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service`  
Expected: FAIL with `ModuleNotFoundError: No module named 'erpnextkta.kta_stock.services.pda_service'`

- [x] **Step 3: Implement auth & operator session APIs in `erpnextkta/kta_stock/services/pda_service.py`**

Aşağıdaki kurallarla temiz, modüler helper'lara bölünmüş şekilde yaz:
1. **Token İmzalama:** `frappe.local.conf.secret_key` (yoksa `frappe.get_site_config().get("encryption_key")` veya `frappe.db.get_value("System Settings", None, "modified")`) ile HMAC-SHA256 imza üret (`payload_b64.sig_hex`); süre kontrolünde `exp` damgasını ve `hmac.compare_digest`'ı kullan.
2. **Yetki Bekçisi (`_require_authorized_device_or_user`):** Kullanıcı `Guest` değilse ve `ALLOWED_PDA_ROLES` kesişimi varsa geçir; `Guest` ise yalnızca `has_valid_pda_device_cookie()` `True` ise geçir, aksi halde `frappe.PermissionError` fırlat.
3. **PIN Doğrulama (`verify_pda_pin`):**
   - `pin` tam olarak 4 sayısal rakam (`^[0-9]{4}$`) değilse reddet.
   - `frappe.cache().get_value(f"pda_pin_fail:{employee}")` $\ge 5$ ise Türkçe hata mesajıyla 5 dakika kilit uygula (`expires_in_sec=300`).
   - Çalışanı (`status == "Active"`, `department in PDA_DEPARTMENTS`, `user_id` etkin ve stok rollü) doğrula.
   - `get_decrypted_password("Employee", employee, fieldname="custom_pda_pin", raise_exception=False)` ile PIN'i oku; boşsa `"Bu personel için henüz PDA PIN kodu tanımlanmamış."` hatası fırlat; uyuşmazsa fail sayacını artırıp reddet.
   - Başarıda fail sayacını temizle, `frappe.local.login_manager.login_as(user_id)` çağır (`frappe.local.login_manager` test/worker bağlamında yoksa `LoginManager()` ilklendir), `csrf_token = frappe.sessions.get_csrf_token()` üret ve döndür.
4. **`get_pda_boot_data()`:** Cihaz/kullanıcı kapısını kontrol et; `current_user`, `current_employee`, `inactivity_timeout_sec=300`, `operators=get_pda_operators()`, `open_picking_count` (açık `KTA Line Replenishment Order` sayısı) ve `device_authorized` döndür.
5. **`pda_handover_logout()`:** Geçerli cihaz/kullanıcı kontrolü sonrası kullanıcı `Guest` değilse `frappe.local.login_manager.logout()`, ardından yeni `csrf_token = frappe.sessions.get_csrf_token()` döndür.

- [x] **Step 4: Run tests and lint checks**

Run:
`bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service`  
`/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py`  
`/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py`  
Expected: PASS (6/6 tests OK, ruff clean).

- [x] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py
git commit -m "feat(pda): add device token, PIN login_as session, and handover service"
```

---

### Task 3: PDA Warehouse Operations Backend (`scan_box`, `package_split`, `material_transfer`, `stock_lookup`) ✅ (Tamamlandı)

**Subagent:** `kta-stock`  
**Files:**
- Modify: `erpnextkta/kta_stock/services/pda_service.py`
- Modify: `erpnextkta/kta_stock/tests/test_pda_service.py`

**Interfaces:**
- Consumes:
  - `erpnextkta.kta_stock.services.relabeling_service`: `create_package_split_repack`, `get_batch_ledger_balances`, `is_standard_kta_box_batch`, `sync_batch_label_to_ledger_balance`, `upsert_box_label`
  - `erpnextkta.kta_stock.label_manager`: `enqueue_print_labels_by_names`
- Produces in `erpnextkta/kta_stock/services/pda_service.py`:
  - `resolve_warehouse_barcode(barcode: str, company: str | None = None) -> dict`
  - `pda_scan_box(barcode: str) -> dict` (`@frappe.whitelist()`)
  - `pda_package_split(item_code: str, source_warehouse: str, source_batch: str, split_qtys: list[float] | str, reprint_source_label: int = 1) -> dict` (`@frappe.whitelist(methods=["POST"])`)
  - `pda_material_transfer(item_code: str, batch_no: str, source_warehouse: str, target_warehouse_barcode: str, qty: float | None = None) -> dict` (`@frappe.whitelist(methods=["POST"])`)
  - `pda_stock_lookup(barcode: str) -> dict` (`@frappe.whitelist()`)

- [x] **Step 1: Write the failing warehouse operation tests in `test_pda_service.py`**

Aşağıdaki 7 testi `erpnextkta/kta_stock/tests/test_pda_service.py` dosyasına ekle:
- `test_resolve_warehouse_barcode_exact_and_without_company_suffix_and_rejects_group`: Hem tam depo adı (`name`), hem şirket soneksiz (`warehouse_name` / `prefix - ABBR`) hem de grup depo (`is_group=1` -> `ValidationError`) durumlarını doğrular.
- `test_pda_scan_box_returns_balances_and_rejects_empty_batch`: `KTA Stock Label.sut_barcode` ve doğrudan `Batch` adı okutulduğunda `item_code`, `item_name`, `stock_uom`, `batch_no`, `label_name`, `label_type`, `balances` (pozitif depolar + qty listesi) döndüğünü; sıfır stoklu partide `ValidationError` verdiğini doğrular.
- `test_pda_package_split_prints_targets_once_and_reprints_remaining_source_selectively`: 100 adetlik kutu `[30]` bölündüğünde 1 `Package Split` Stock Entry oluştuğunu (`owner == session.user`), hedef yeni kutu için `KTAStockEntry.on_submit()` dışında `enqueue_print_labels_by_names` çağrılmadığını; `reprint_source_label=1` iken ve `remaining_qty=70 > 0` iken yalnızca güncellenen kaynak etiketinin `enqueue_print_labels_by_names([source_label])` ile 1 kez kuyruğa alındığını; `reprint_source_label=0` veya tam bölmede `[100]` ise hiç çağrılmadığını doğrular.
- `test_pda_package_split_rejects_noop_single_full_qty_on_standard_batch`: Standart `7+4` kutuda `[total_qty]` (tam miktar tek parça) bölmenin `ValidationError` ile engellendiğini doğrular.
- `test_pda_material_transfer_moves_full_box_syncs_label_and_records_session_owner`: PIN veya aktif `user` oturumu altında `pda_material_transfer()` çağrıldığında `Material Transfer` `Stock Entry` belgesinin submit edildiğini, `owner == frappe.session.user` olduğunu, kaynağın 0 ve hedefin tam kutu miktarına çıktığını ve `KTA Stock Label.target_warehouse` alanının hedef depoya güncellendiğini doğrular.
- `test_pda_material_transfer_rejects_partial_qty_same_wh_and_draft_reco_lock`: Kısmi miktar (`qty < available`), aynı kaynak/hedef depo ve depoda Taslak `Stock Reconciliation` varken `ValidationError` fırlattığını (hiç SLE oluşmadığını) doğrular.
- `test_pda_stock_lookup_resolves_batch_warehouse_and_item`: Barkoda göre `kind` (`"batch"` / `"warehouse"` / `"item"`) ve ilgili bakiye/parti/etiket özetini salt-okunur döndüğünü doğrular.

- [x] **Step 2: Run tests to verify they fail**

Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service`  
Expected: FAIL with `ImportError` / missing functions.

- [x] **Step 3: Implement warehouse operations in `erpnextkta/kta_stock/services/pda_service.py`**

Aşağıdaki kurallarla temiz, modüler helper'lara bölünmüş şekilde yaz:
1. **`resolve_warehouse_barcode(barcode, company=None)`:**
   - Tam ad `name = clean_code` kontrol et; yoksa `warehouse_name = clean_code` (varsa `company` filtresiyle); yoksa aktif şirket kısaltmasıyla (`get_cached_value("Company", company, "abbr")` veya tek şirket üzerinden `f"{clean_code} - {abbr}"`) ara.
   - Bulunan deponun `disabled == 1` veya `is_group == 1` olması durumunda Türkçe `ValidationError` fırlat.
2. **`pda_scan_box(barcode)`:**
   - Önce `_require_pda_operator()` (`frappe.session.user != "Guest"` ve `ALLOWED_PDA_ROLES` kontrolü).
   - `KTA Stock Label` (`sut_barcode` veya `name` üzerinden) ve/veya `Batch` (`name` veya `batch_id`) çözümle.
   - `get_batch_ledger_balances(item_code, batch_no)` ile `qty > _EPSILON` depoları topla; pozitif bakiye yoksa `ValidationError` fırlat.
   - Ürün bilgisi, etiket meta verileri, `is_standard_batch` ve depo bakiye listesini döndür.
3. **`pda_package_split(item_code, source_warehouse, source_batch, split_qtys, reprint_source_label=1)`:**
   - `_require_pda_operator()` kontrolü; `split_qtys` listesini parse et (`flt(q) > 0`).
   - `source_warehouse` içindeki mevcut bakiyeyi doğrula.
   - Standart `7+4` kutuda `len(qtys) == 1` ve `abs(qtys[0] - available) <= _EPSILON` ise anlamlı bir bölme olmadığı için `ValidationError` fırlat.
   - `create_package_split_repack(..., target_warehouse=source_warehouse)` çağır (dikkat: `KTAStockEntry.on_submit()` zaten hedef etiketleri oluşturup basar).
   - Kalan bakiye (`remaining_qty = flt(available - sum(qtys))`) hesapla; `remaining_qty > _EPSILON` ve `cint(reprint_source_label) == 1` ise kaynak kutunun güncel etiket adını bul (`KTA Stock Label`, `Depo Giriş Etiketi` / `İş Emri Etiketi`) ve yalnız onu `enqueue_print_labels_by_names([src_label_name], user=frappe.session.user)` ile kuyruğa al.
   - Hedef etiketleri tekrar kuyruğa ALMA (`queued_reprint_count` yalnızca opsiyonel kaynak etiketi sayar).
4. **`pda_material_transfer(item_code, batch_no, source_warehouse, target_warehouse_barcode, qty=None)`:**
   - `_require_pda_operator()` kontrolü.
   - `target = resolve_warehouse_barcode(target_warehouse_barcode)` çözümlenir; `target["name"] == source_warehouse` ise reddet.
   - `get_batch_ledger_balances(item_code, batch_no)` üzerinden `source_warehouse` tam bakiyesini bul; `available <= 0` ise reddet; `qty is not None` ise `abs(flt(qty) - available) <= _EPSILON` şartını ara (kısmi miktarda `Package Split` yönlendirmeli `ValidationError` fırlat).
   - Standart `Stock Entry` (`purpose="Material Transfer"`, `stock_entry_type="Material Transfer"`, `s_warehouse=source_warehouse`, `t_warehouse=target["name"]`, `qty=available`, `batch_no=batch_no`, `use_serial_batch_fields=1`) oluşturup `se.insert()` + `se.submit()` çalıştır (`validate_stock_entry_warehouse_lock` ve `validate_batch_qi_on_transfer` doğal olarak çalışır).
   - Transfer sonrası `sync_batch_label_to_ledger_balance(item_code, batch_no)` çağırarak etiketin `target_warehouse` ve `qty` alanını güncelle.
5. **`pda_stock_lookup(barcode)`:**
   - `_require_pda_operator()` kontrolü.
   - Sırasıyla `KTA Stock Label` / `Batch` -> `kind="batch"` (etiket detayları + depo bakiye dağılımı), `Warehouse` (grup hariç veya dahil bilgi) -> `kind="warehouse"` (`Bin` + `Actual Qty` pozitif ilk 50 satır), `Item` / `Item Barcode` -> `kind="item"` (depo stokları + parti özetleri) döndür.

- [x] **Step 4: Run tests and lint checks**

Run:
`bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service`  
`/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py`  
`/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py`  
Expected: PASS (13/13 tests in `test_pda_service.py` OK, ruff clean).

- [x] **Step 5: Commit**

```bash
git add erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_service.py
git commit -m "feat(pda): add package split, full-box transfer, and stock lookup APIs"
```

---

### Task 4: Standalone `/pda` Web Portal Route, HTML Shell & PWA Manifest ✅ (Tamamlandı)

**Subagents:** `docs-i18n` (`www/pda.py`, `www/pda.html`), `frontend-public` (`public/pda-hub/manifest.webmanifest`), `kta-stock` (`tests/test_pda_portal.py`)  
**Files:**
- Create: `erpnextkta/www/pda.py`
- Create: `erpnextkta/www/pda.html`
- Create: `erpnextkta/public/pda-hub/manifest.webmanifest`
- Create: `erpnextkta/kta_stock/tests/test_pda_portal.py`

**Interfaces:**
- Consumes: `get_pda_boot_data`, `has_valid_pda_device_cookie`, `set_pda_device_cookie`, `ALLOWED_PDA_ROLES` from `erpnextkta/kta_stock/services/pda_service.py`
- Produces: Route `/pda` injecting `csrf_token`, `build_version`, `boot` (with translations via `frappe.boot.load_translations`), and `pda_boot_data` JSON cleanly for SPA mount `#pda-app`.

- [x] **Step 1: Write the failing portal context tests (`kta-stock` -> `test_pda_portal.py`)**

`erpnextkta/kta_stock/tests/test_pda_portal.py` içinde:
- `test_pda_guest_without_device_cookie_redirects_to_login`: `frappe.set_user("Guest")` ve çerezsiz iken `get_context({})` çağrısının `frappe.Redirect` fırlattığını ve `frappe.local.flags.redirect_location == "/login?redirect-to=/pda"` olduğunu doğrular.
- `test_pda_guest_with_valid_device_cookie_renders_locked_boot`: Geçerli `kta_pda_device` çerezi mevcutken `Guest` kullanıcısında yönlendirme yapmadan `pda_boot_data` içine `current_user="Guest"`, `device_authorized=True` ve operatör listesini koyduğunu doğrular.
- `test_pda_unauthorized_logged_in_user_throws_permission_error`: Stok rolü olmayan normal kullanıcıda `frappe.PermissionError` fırlattığını doğrular.
- `test_pda_authorized_stock_user_populates_boot_and_sets_device_cookie`: `Stock User` kullanıcısında `csrf_token`, `boot.__messages` ve `pda_boot_data` alanlarının eksiksiz dolduğunu ve `set_pda_device_cookie` çağrıldığını doğrular.

- [x] **Step 2: Run tests to verify they fail**

Run: `bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal`  
Expected: FAIL with `ModuleNotFoundError: No module named 'erpnextkta.www.pda'`

- [x] **Step 3: Implement `www/pda.py`, `www/pda.html`, and `manifest.webmanifest`**

1. (`docs-i18n`) `erpnextkta/www/pda.py`:
   - `no_cache = 1`, `sitemap = 0`.
   - `get_context(context)`:
     - Kullanıcı `Guest` ise: `has_valid_pda_device_cookie()` kontrol et; yoksa `frappe.local.flags.redirect_location = "/login?redirect-to=/pda"` ve `raise frappe.Redirect`.
     - Kullanıcı `Guest` değilse: `ALLOWED_PDA_ROLES` kesişimi (veya `Stock Entry` read izni) yoksa `frappe.throw(_("Bu sayfaya erişim yetkiniz bulunmamaktadır."), frappe.PermissionError)`. Yetkisi varsa `set_pda_device_cookie()` ile cihaz çerezini ver/yenile.
     - `bootinfo = frappe._dict({"lang": frappe.local.lang, "site_name": frappe.local.site})`, `load_translations(bootinfo)`.
     - `context.csrf_token = frappe.sessions.get_csrf_token()`, `context.build_version = frappe.utils.get_build_version()`, `context.boot_json = frappe.as_json(bootinfo)`, `context.pda_boot_json = frappe.as_json(get_pda_boot_data())`.
2. (`docs-i18n`) `erpnextkta/www/pda.html`:
   - Saf HTML5 PWA kabuğu (`<!DOCTYPE html><html lang="{{ lang or 'tr' }}">`). Desk base template'inden (`web.html`) **extends ETMEZ** ki gereksiz portal header/footer veya Desk JS yüklenmesin.
   - `<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />`, Apple/Android web-app meta etiketleri, `<link rel="manifest" href="/assets/erpnextkta/pda-hub/manifest.webmanifest" />`.
   - `{{ include_style("pda-hub.bundle.css") }}` (koşullu veya Frappe `bundled_asset` yardımcısı ile), `<div id="pda-app"></div>`.
   - `<script>window.csrf_token = "{{ csrf_token }}"; window.frappe = window.frappe || {}; window.frappe.boot = {{ boot_json }}; window.frappe._messages = (window.frappe.boot && window.frappe.boot.__messages) || {}; window.__KTA_PDA_BOOT__ = {{ pda_boot_json }};</script>`
   - `{{ include_script("pda-hub.bundle.js") }}`.
3. (`frontend-public`) `erpnextkta/public/pda-hub/manifest.webmanifest`:
   - `name`: `"KTA Depo Terminali"`, `short_name`: `"KTA PDA"`, `start_url`: `"/pda"`, `scope`: `"/pda"`, `display`: `"standalone"`, `orientation`: `"portrait"`, `theme_color`: `"#1e293b"`, `background_color`: `"#f8fafc"`.

- [x] **Step 4: Run tests and lint checks**

Run:
`bench --site old.kta-endustri.com.tr run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal`  
`/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/www/pda.py erpnextkta/kta_stock/tests/test_pda_portal.py`  
`/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/www/pda.py erpnextkta/kta_stock/tests/test_pda_portal.py`  
Expected: PASS (4/4 tests OK, ruff clean).

- [x] **Step 5: Commit**

```bash
git add erpnextkta/www/pda.py erpnextkta/www/pda.html erpnextkta/public/pda-hub/manifest.webmanifest erpnextkta/kta_stock/tests/test_pda_portal.py
git commit -m "feat(pda): add standalone /pda web portal shell and PWA manifest"
```

---

### Task 5: Frontend Core Shell (`pda-hub`), Frappe Shim, PIN Keypad, Launcher & Picking View ✅ (Tamamlandı)

**Subagent:** `frontend-public`  
**Files:**
- Create: `erpnextkta/public/pda-hub/tsconfig.json`, `frappe.d.ts`, `types.ts`, `package.json`, `vitest.config.js`, `vitest.setup.js`
- Create: `erpnextkta/public/pda-hub/utils/frappeShim.ts`
- Create: `erpnextkta/public/pda-hub/composables/useInactivityLock.ts`
- Create: `erpnextkta/public/pda-hub/components/PdaOverlays.vue`
- Create: `erpnextkta/public/pda-hub/components/PinLockScreen.vue`
- Create: `erpnextkta/public/pda-hub/components/LauncherHome.vue`
- Create: `erpnextkta/public/pda-hub/views/PickingModuleView.vue`
- Create: `erpnextkta/public/pda-hub/PdaHubApp.vue`
- Create: `erpnextkta/public/pda-hub/pda-hub.bundle.ts`
- Create: `erpnextkta/public/pda-hub/__tests__/frappeShim.spec.ts`
- Create: `erpnextkta/public/pda-hub/__tests__/PinLockAndLauncher.spec.ts`

**Interfaces:**
- Consumes: Task 2 backend RPCs (`get_pda_boot_data`, `verify_pda_pin`, `pda_handover_logout`), existing `../../line-replenishment-pda/components/{OrderSelector,BarcodeScannerBar,PickingItemCard,TransferFooter}.vue` & `../../line-replenishment-pda/utils/audio`.
- Produces:
  - `initFrappeShim(options?: { onAuthExpired?: () => void }): void`
  - `updateCsrfToken(token: string): void`
  - `useInactivityLock(options: { timeoutMs?: number; enabled: Ref<boolean>; onLock: () => void })`
  - Mount entry `pda-hub.bundle.ts` exposing CSS + JS under `pda-hub.bundle`.

- [x] **Step 1: Write Vitest tests first (`frappeShim.spec.ts` & `PinLockAndLauncher.spec.ts`)**

1. `frappeShim.spec.ts`:
   - `window.frappe.call` isteğinin `/api/method/<method>` ucuna `X-Frappe-CSRF-Token: window.csrf_token` header'ıyla `POST`/`GET` gönderdiğini doğrular.
   - `updateCsrfToken("new-tok")` sonrası sıradaki `POST` isteğinin güncellenmiş token ile gittiğini doğrular.
   - `_server_messages` parse edip okunabilir hata mesajı döndürdüğünü; `401` veya `403` yanıtında `onAuthExpired` callback'ini tetiklediğini doğrular.
2. `PinLockAndLauncher.spec.ts`:
   - `PinLockScreen.vue`: Ambar personel kartına tıklandığında 4 haneli tuş takımının açıldığını, 4 hane dolduğunda `verify_pda_pin` çağrıldığını ve `csrf_token` + aktif operatör ile `unlocked` olayı emit ettiğini doğrular.
   - `LauncherHome.vue`: 4 modül kartını (`picking`, `split`, `transfer`, `lookup`) açık ikmal sayısı rozetiyle render ettiğini ve karta basıldığında ilgili modüle geçildiğini doğrular.
   - `useInactivityLock`: Fake timers ile 300s (`300_000ms`) hareketsizlikte `onLock` çağrıldığını, kullanıcı etkileşiminde sayacın sıfırlandığını doğrular.

- [x] **Step 2: Run Vitest to verify tests fail**

Run: `npm --prefix erpnextkta/public/pda-hub install --no-package-lock && npm --prefix erpnextkta/public/pda-hub test` (veya mevcut `node_modules` yoksa önce kurulum).  
Expected: FAIL because source modules do not exist yet.

- [x] **Step 3: Implement core shell, shim, auth UI, launcher & picking module**

Her `.vue` dosyası **< 450 satır** kalacak şekilde aşağıdaki bileşenleri yaz:
1. `utils/frappeShim.ts`: Standart Desk olmadan çalışan hafif `window.frappe` + `window.__` (yerelleştirilmiş `frappe._messages` formatlama `{0}` destekli) uyumluluk katmanı. `frappe.call` `fetch(..., { credentials: "same-origin", headers: { "X-Frappe-CSRF-Token": window.csrf_token } })` kullanır; `frappe.confirm`, `frappe.msgprint`, `frappe.show_alert` çağrılarını reaktif `overlayState` üzerine bağlar (böylece `PickingModuleView` içindeki mevcut `line-replenishment-pda` bileşenleri ve modüller tek satır değişiklik gerektirmeden aynı şekilde çalışır!). `401`/`403` yanıtında `onAuthExpired()` tetikler.
2. `composables/useInactivityLock.ts`: `pointerdown`, `keydown`, `touchstart`, `click` olaylarını dinler; `300_000ms` (5 dk) dolduğunda `onLock()` çalıştırır.
3. `components/PdaOverlays.vue`: `<Teleport to="body">` içinde yüksek kontrastlı toast ve mobil Onay/Bilgi modalları.
4. `components/PinLockScreen.vue`: Operatör arama + dokunmatik kart listesi (`AMBAR - KTA` / `Sevk`) + büyük ATM tarzı 4 haneli PIN keypad + `/login?redirect-to=/pda` standart giriş bağlantısı.
5. `components/LauncherHome.vue`: 4 ana modül için eldiven dostu büyük dokunmatik kartlar.
6. `views/PickingModuleView.vue`: Mevcut `../../line-replenishment-pda/components/*` bileşenlerini sarmalayarak Açık Emir Seçimi -> Barkod Okutma -> Tolerans Kontrollü Tamamlama akışını sunar (mevcut `line-replenishment-picking` sayfasını bozmaz).
7. `PdaHubApp.vue` + `pda-hub.bundle.ts`: Sabit üst şerit (`[← Menü]`, `👤 Operatör Adı`, `[Devret ↩]` + inaktivite sayacı) ve view switcher; `<div id="pda-app">` üzerine mount edilir.

- [x] **Step 4: Run Vitest & esbuild check**

Run:
`npm --prefix erpnextkta/public/pda-hub test`  
`bench build --app erpnextkta --production`  
Expected: All Vitest specs PASS and `pda-hub.bundle.*.js` / `.css` generated cleanly in `erpnextkta/public/dist/`.

- [x] **Step 5: Commit**

```bash
git add erpnextkta/public/pda-hub/
git commit -m "feat(pda): add standalone SPA shell, PIN keypad, launcher, and picking"
```

---

### Task 6: Frontend Warehouse Modules (`PackageSplitView`, `MaterialTransferView`, `StockLookupView`) ✅ (Tamamlandı)

**Subagent:** `frontend-public`  
**Files:**
- Create: `erpnextkta/public/pda-hub/views/PackageSplitView.vue` (< 400 satır)
- Create: `erpnextkta/public/pda-hub/views/MaterialTransferView.vue` (< 360 satır)
- Create: `erpnextkta/public/pda-hub/views/StockLookupView.vue` (< 340 satır)
- Modify: `erpnextkta/public/pda-hub/PdaHubApp.vue` (3 modülü bağla), `types.ts`, `pda-hub.bundle.css`
- Create: `erpnextkta/public/pda-hub/__tests__/WarehouseModules.spec.ts`

**Interfaces:**
- Consumes: Task 3 backend RPCs (`pda_scan_box`, `pda_package_split`, `pda_material_transfer`, `pda_stock_lookup`), `BarcodeScannerBar.vue`, `playBeep`, `frappeShim`.
- Produces: Tam işlevsel 3 yeni saha operasyonu ekranı.

- [x] **Step 1: Write Vitest tests (`WarehouseModules.spec.ts`)**

`erpnextkta/public/pda-hub/__tests__/WarehouseModules.spec.ts` içinde:
- `PackageSplitView`: Barkod tarama sonrası kutu kartının açıldığını, toplamı mevcut bakiyeyi aşan bölme adetlerinde veya `<= 0` girişlerde butonun kilitlendiğini, kalan miktarın canlı hesaplandığını, geçerli bölmede (`[200]`) `pda_package_split` API'sine doğru argümanlarla (`reprint_source_label`) çağrı yaptığını doğrular.
- `MaterialTransferView`: Adım 1 kutu barkodu okutulduğunda Adım 2 hedef raf alanına odaklanıldığını, hedef raf okutulduktan sonra tam kutu miktarı korunarak `pda_material_transfer` çağrıldığını ve başarıda ses + yeni işlem sıfırlaması yaptığını doğrular.
- `StockLookupView`: `batch`, `warehouse` ve `item` türündeki `pda_stock_lookup` yanıtlarının her biri için doğru kart/tablo bilgisinin görüntülendiğini doğrular.

- [x] **Step 2: Run Vitest to verify tests fail**

Run: `npm --prefix erpnextkta/public/pda-hub test`  
Expected: FAIL because view components do not exist yet.

- [x] **Step 3: Implement the 3 warehouse module views & wire into `PdaHubApp.vue`**

1. **`views/PackageSplitView.vue`:**
   - Adım 1: `BarcodeScannerBar` ile kutu barkodu okut -> `pda_scan_box`. Birden fazla depoda bakiye varsa kaynak depo seçimi; tek depodaysa otomatik seçim.
   - Adım 2: Bölünecek alt kutu adetleri listesi (hızlı kısmi ayırma için tek satır `[200]` veya `+ Kutu Ekle` ile çoklu kırılım) + canlı `Kalan Kaynak Miktar` göstergesi + `"Kalan kaynak etiketini de yeniden bas"` (`reprint_source_label`) onay kutusu.
   - Adım 3: `[✂️ Koli Böl ve Etiket Bas]` -> `pda_package_split` -> oluşan Stock Entry ve yeni parti numaralarını büyük başarı kartında göster + `playBeep(true)`.
2. **`views/MaterialTransferView.vue`:**
   - Adım 1: Kutu barkodu okut (`pda_scan_box`) -> ürün, parti, mevcut raf (`source_warehouse`) ve salt-okunur tam kutu miktarını (`1 Kutu = 1 Parti` kuralı uyarısıyla) göster.
   - Adım 2: Hedef raf barkodu inputuna otomatik odaklan (`170-W1F-xx-xx`) -> `[🔄 Transferi Tamamla]` ile `pda_material_transfer` çağır -> başarılı olunca `playBeep(true)` ve sonraki kutu için Adım 1'e otomatik sıfırla.
3. **`views/StockLookupView.vue`:**
   - Tek barkod tarayıcı -> `pda_stock_lookup` yanıt tipine göre (`batch` / `warehouse` / `item`) sade yüksek kontrastlı kartlarla stok lokasyonları ve etiket özetini göster.
4. **`PdaHubApp.vue`:** `activeModule` durumuna göre `PickingModuleView`, `PackageSplitView`, `MaterialTransferView`, `StockLookupView` geçişlerini bağla (her dosya `< 500` satır).

- [x] **Step 4: Run Vitest & production build**

Run:
`npm --prefix erpnextkta/public/pda-hub test`  
`bench build --app erpnextkta --production`  
Expected: All Vitest specs PASS and production bundle builds with 0 errors.

- [x] **Step 5: Commit**

```bash
git add erpnextkta/public/pda-hub/
git commit -m "feat(pda): implement package split, material transfer, and lookup views"
```

---

### Task 7: Portal Documentation, Developer Guide, Translations & Coordinator Quality Gate ✅ (Tamamlandı)

**Subagents:** `docs-i18n` + Coordinator Final Quality Gate  
**Files:**
- Modify: `erpnextkta/translations/tr.csv`, `erpnextkta/translations/en.csv`, `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/www/docs/stok-lojistik.html`
- Modify: `docs/kta_stok_lojistik_kilavuzu.md`

- [x] **Step 1: Dispatch `docs-i18n` for translations and documentation sync**

1. **Çeviriler (`tr.csv`, `en.csv`, `de.csv`):** PDA Hub (`PdaHubApp.vue`, `PinLockScreen.vue`, `LauncherHome.vue`, `PackageSplitView.vue`, `MaterialTransferView.vue`, `StockLookupView.vue`, `pda_service.py`) içerisindeki tüm kullanıcıya dönük `__()` ve `_()` metinlerini Title Case ve tam cümle bütünlüğüyle ekle. Mevcut satırları bozma ve CSV kaçış kurallarına uy.
2. **Portal ve Geliştirici Dokümantasyonu:** [stok-lojistik.html](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/www/docs/stok-lojistik.html) ve `docs/kta_stok_lojistik_kilavuzu.md` içine bağımsız `/pda` PWA Depo Merkezi bölümünü ekle: cihaz yetkilendirme (`kta_pda_device`), 4 haneli PIN + `login_as` oturum geçişi, 5 dakikalık kilit + Devret akışı, `KTA User Zebra Printers` otomatik eşleşmesi ve 4 depo modülünün kullanım kuralları (hiçbir ticari veri / firma adı ekleme).

- [x] **Step 2: Run full Coordinator Final Quality Gate**

Run:
```bash
/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/services/pda_service.py erpnextkta/www/pda.py erpnextkta/patches/v4_4/add_employee_pda_pin_field.py erpnextkta/hooks.py erpnextkta/kta_stock/tests/test_pda_service.py erpnextkta/kta_stock/tests/test_pda_portal.py erpnextkta/kta_stock/tests/test_relabeling_service.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/setup.py erpnextkta/kta_stock/services/pda_service.py erpnextkta/www/pda.py erpnextkta/patches/v4_4/add_employee_pda_pin_field.py erpnextkta/hooks.py erpnextkta/kta_stock/tests/test_pda_service.py erpnextkta/kta_stock/tests/test_pda_portal.py erpnextkta/kta_stock/tests/test_relabeling_service.py
npm --prefix erpnextkta/public/pda-hub test
bench build --app erpnextkta --production
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_relabeling_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_line_replenishment_picking_page
```
Expected: Tüm lint, format, build, Vitest ve Frappe testleri 0 hata ile geçer.

- [x] **Step 3: Commit documentation & translations**

```bash
git add erpnextkta/translations/tr.csv erpnextkta/translations/en.csv erpnextkta/translations/de.csv erpnextkta/www/docs/stok-lojistik.html docs/kta_stok_lojistik_kilavuzu.md
git commit -m "docs(pda): document unified PDA hub and sync TR/EN/DE translations"
```

---

## Self-Review Checklist

1. **Spec coverage:** Standalone `/pda` PWA (Task 4), zero `custom_operator` / native `login_as` + `kta_pda_device` + 5-min lock + rate limit (Task 1 & 2), Zebra auto-resolution via `session.user` (Task 2 & 3), 4 modules (Picking, Package Split without double-print, Full-Box Material Transfer, Quick Lookup) (Task 3, 5, 6), Docs & TR/EN/DE (Task 7). Boşluk yok.
2. **Type & Signature consistency:** `get_pda_boot_data()`, `verify_pda_pin(employee, pin)`, `pda_handover_logout()`, `pda_scan_box(barcode)`, `pda_package_split(item_code, source_warehouse, source_batch, split_qtys, reprint_source_label=1)`, `pda_material_transfer(item_code, batch_no, source_warehouse, target_warehouse_barcode, qty=None)`, `pda_stock_lookup(barcode)` adları hem spec, hem Task 2-3 hem de frontend Task 5-6'da birebir aynıdır.
3. **Review Focus coverage:** 5 kritik hata modu (yetkisiz Guest, brute-force, çift etiket baskısı, kısmi transfer/kilit, bayat CSRF token) doğrudan testlerle sabitlenmiştir.
