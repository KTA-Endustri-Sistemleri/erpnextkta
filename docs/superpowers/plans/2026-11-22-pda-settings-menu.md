# PDA Settings Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task, strictly routing each task to its owning specialist subagent in `.agents/AGENTS.md`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/pda` el terminali için **Yaklaşım A** doğrultusunda çekmece altı sabit `AYARLAR` girişini, self-servis 4 haneli PIN yönetimini (ilk kurulum, mevcut PIN değiştirme, hesap şifresiyle sıfırlama + RBAC sınırlı yönetici sıfırlama), yetkili Zebra yazıcı seçimi/bağlantı testini, cihaz bazlı açık/koyu tema ile ses tercihlerini ve sayfa yenilemesiz reaktif çoklu dil (`tr`/`en`/`de`) geçişini hayata geçirmek.

**Architecture:** Arka uçta `erpnextkta/kta_stock/services/pda_service.py` içinde `_require_pda_operator()` korumalı self-servis ve RBAC denetimli 6 yeni Ayarlar ucu ile `verify_pda_pin` / `pda_handover_logout` yanıtlarına gömülen `_build_pda_translations_payload()` yardımcısı tanımlanır (`Employee.save()` tetiklemeden `set_encrypted_password` ile yazar). Ön uçta `frappeShim.ts` üzerine eklenen Vue `reactive` `runtimeLocaleState` + `setRuntimeTranslations()` sayfa yenilemeden `0ms` dil değişimi sağlarken, `pdaPreferences.ts`, `audio.ts`, paylaşılan `line-replenishment-pda` koyu tema kontrast düzeltmeleri, `PdaPinSettingsCard.vue`, `PdaSettingsView.vue`, `PdaMenuDrawer.vue`, `LauncherHome.vue` ve `PdaHubApp.vue` bileşenleri tüm iş akışını tamamlar.

**Tech Stack:** Frappe v15, Python 3.11+, Vue 3 (`<script setup lang="ts">`), TypeScript, esbuild (`bench build --app erpnextkta --production`), Vitest + `@vue/test-utils` + `jsdom`, `KTABaseTestCase`, `ruff`.

**Spec:** [2026-11-22-pda-settings-menu-design.md](../specs/2026-11-22-pda-settings-menu-design.md)

---

## Global Constraints

- Saf `Website User` (`KTA PDA Stock User`, `desk_access = 0`) kullanıcılarına `Employee`, `User` veya `KTA User Zebra Printers` DocType'ları üzerinde **kesinlikle** doğrudan `write` veya `create` DocPerm verilmez.
- PIN yazma işlemlerinde `set_encrypted_password("Employee", emp.name, clean_pin, fieldname="custom_pda_pin")` kullanılır ve **asla** `Employee.save()` çağrılmaz.
- Yönetici PIN sıfırlamada katı RBAC hiyerarşisi uygulanır: kendi kendini sıfırlama yasaktır; `System Manager` rolü olmayan `Stock Manager` yalnızca üzerinde `Stock Manager` veya `System Manager` rolü bulunmayan aktif PDA operatörlerini sıfırlayabilir; `System Manager` ise kendisi dışındaki tüm aktif PDA operatörlerini sıfırlayabilir.
- Dil senkronizasyonu (`User.language` ∈ `("tr", "en", "de")`), Ayarlar ekranında dil değiştirme, `verify_pda_pin` ve `pda_handover_logout` akışlarında **sayfa yenilemesi olmadan** (`0ms`) Vue `reactive` `runtimeLocaleState` + `setRuntimeTranslations(lang, messages)` üzerinden çalışır.
- Tüm `.vue` dosyaları **strictly < 500 satır** kalır (`PickingItemCard.vue` gereksiz stil tekrarları konsolide edilerek `< 500` satıra indirilir; `PickingItemCard.vue`, `TransferFooter.vue` ve `OrderSelector.vue` koyu tema düzeltmeleri Desk `/app/line-replenishment-picking` aydınlık görünümünü bozmaz); her Vue bileşeninde `const __ = (...args: any[]) => (window as any).__(...args);` sarmalayıcısı bulunur.
- Çeviri sözlükleri (`erpnextkta/translations/{tr,en,de}.csv`) **strictly append-only (`0` silme)** güncellenir; Title Case ve tam cümle standartları korunur.
- Frontend üretim derlemesi yalnızca `bench build --app erpnextkta --production` ile yapılır; Python dosyaları `ruff check` ve `ruff format --check` ile doğrulanır.
- Dokümanlarda, testlerde ve örneklerde gerçek tedarikçi/müşteri firma adı veya ticari birim fiyat/maliyet bilgisi kesinlikle bulunmaz (yalnızca `ZEBRA-01`, `ZEBRA-02` gibi anonim örnekler kullanılır).

---

## Review Focus

1. **Masada açık unutulan terminalde PIN ele geçirme veya kaba kuvvet şifre denemesi:** `has_pin == True` iken `current_pin` zorunlu olmalı; `"account_password"` modunda ayrı `pda_pwd_fail:{user}` cache anahtarı üzerinden 5 hatalı denemede 300 sn kilitleme uygulanmalı; yönetici `pda_admin_reset_operator_pin` ile kendi PIN'ini sıfırlamaya kalktığında `PermissionError` almalıdır (*Task 2*).
2. **`Stock Manager` rolünün eşdeğer `Stock Manager` veya üst `System Manager` kullanıcılarının PIN'ini görmesi/sıfırlaması:** `pda_get_settings_data()` içindeki `manageable_operators` listesinden hariç tutulmalı ve doğrudan RPC çağrısında `frappe.PermissionError` fırlatılmalıdır (*Task 2*).
3. **Aktif `Employee` kaydı bulunmayan yönetici hesaplarının (`Administrator` / `System Manager`) Ayarlar ekranını açması:** `pda_get_settings_data()` `has_employee=False` döndürerek `DoesNotExistError` fırlatmamalı; yönetici yine yazıcı, cihaz tercihleri ve alt personel PIN sıfırlama araçlarını kullanabilmelidir (*Task 2 & Task 3*).
4. **Paylaşımlı terminalde operatör devri (`verify_pda_pin` & `pda_handover_logout`) ve canlı dil değişimi:** Her iki uç da hedef kullanıcının (veya `Guest` için `"tr"`) `lang` ve `messages` sözlüğünü döndürmeli; `frappeShim.ts` içindeki `runtimeLocaleState` güncellenerek `/pda` yenilenmeden anında dil değiştirmelidir (*Task 2 & Task 3*).
5. **Koyu temada paylaşılan `line-replenishment-pda` bileşen kontrastı & sessiz mod `playBeep()`:** `PickingItemCard.vue` (`< 500` satır), `TransferFooter.vue` ve `OrderSelector.vue` `[data-theme="dark"]` altında okunabilir kalırken Desk aydınlık modunu korumalı; `playBeep()` `kta_pda_sound === "0"` iken sessiz kalmalı ve `localStorage` yoksa hata vermemelidir (*Task 3*).

---

## File Structure

- **Tasarım & Plan (`docs-i18n`):**
  - Modify: `docs/superpowers/specs/2026-11-22-pda-settings-menu-design.md` (`**Durum:** Onaylandı — Uygulamada`)
  - Create: `docs/superpowers/plans/2026-11-22-pda-settings-menu.md`
- **Backend Servis & Testler (`kta-stock`):**
  - Modify: `erpnextkta/kta_stock/services/pda_service.py` — `_build_pda_translations_payload`, `verify_pda_pin` & `pda_handover_logout` (`lang` + `messages`), `pda_get_settings_data`, `pda_update_own_pin`, `pda_admin_reset_operator_pin`, `pda_save_printer_preferences`, `pda_test_printer_connection`, `pda_update_user_language`.
  - Create (Test): `erpnextkta/kta_stock/tests/test_pda_settings.py`
- **Frontend SPA, Tercihler & Paylaşılan Koyu Tema (`frontend-public`):**
  - Modify: `erpnextkta/public/pda-hub/types.ts`
  - Modify: `erpnextkta/public/pda-hub/utils/frappeShim.ts`
  - Create: `erpnextkta/public/pda-hub/utils/pdaPreferences.ts`
  - Modify: `erpnextkta/public/line-replenishment-pda/utils/audio.ts`
  - Modify: `erpnextkta/public/line-replenishment-pda/components/PickingItemCard.vue` (`< 500` satır)
  - Modify: `erpnextkta/public/line-replenishment-pda/components/TransferFooter.vue`
  - Modify: `erpnextkta/public/line-replenishment-pda/components/OrderSelector.vue`
  - Modify: `erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue`
  - Modify: `erpnextkta/public/pda-hub/components/LauncherHome.vue`
  - Create: `erpnextkta/public/pda-hub/components/PdaPinSettingsCard.vue` (`< 350` satır)
  - Create: `erpnextkta/public/pda-hub/views/PdaSettingsView.vue` (`< 350` satır)
  - Modify: `erpnextkta/public/pda-hub/PdaHubApp.vue`
  - Create / Modify (Vitest): `erpnextkta/public/pda-hub/__tests__/PdaSettingsView.spec.ts`, `PdaHubApp.spec.ts`, `PinLockAndLauncher.spec.ts`, `frappeShim.spec.ts`
- **Dokümantasyon & Çeviri (`docs-i18n`):**
  - Modify (append-only): `erpnextkta/translations/{tr,en,de}.csv`
  - Modify: `erpnextkta/www/docs/stok-lojistik.html`
  - Modify: `docs/kta_stok_lojistik_kilavuzu.md`

---

### Task 1: Design Spec Onayı & Implementation Plan (`docs-i18n`)

**Subagent:** `docs-i18n`  
**Files:**
- Modify: `docs/superpowers/specs/2026-11-22-pda-settings-menu-design.md:4`
- Create: `docs/superpowers/plans/2026-11-22-pda-settings-menu.md`

**Interfaces:**
- Produces: Onaylı mimari spec (`**Durum:** Onaylandı — Uygulamada`) ve Task 2–4 uygulama sözleşmeleri.

- [x] **Step 1: Update Design Spec status to `Onaylandı — Uygulamada`**

`docs/superpowers/specs/2026-11-22-pda-settings-menu-design.md` satır 4'ü `**Durum:** Onaylandı — Uygulamada` olarak güncelle.

- [x] **Step 2: Author `docs/superpowers/plans/2026-11-22-pda-settings-menu.md`**

`writing-plans` standardına uygun biçimde Global Constraints, Review Focus, File Structure ve Task 1–4 adımlarını oluştur.

- [x] **Step 3: Verify Spec & Plan status and privacy compliance**

Run: `git status --short -- docs/superpowers/`  
Expected: Yalnızca spec ve plan dosyaları listelenir; ticari veri veya uygulama kodu değişikliği yoktur.

- [x] **Step 4: Commit (Koordinatör)**

```bash
git add docs/superpowers/specs/2026-11-22-pda-settings-menu-design.md docs/superpowers/plans/2026-11-22-pda-settings-menu.md
git commit -m "docs(pda): add approved PDA settings menu spec and plan"
```

---

### Task 2: Backend Self-Servis PIN, RBAC Yönetici Sıfırlama, Zebra Yazıcı Tercihi/Testi ve Canlı Çeviri API'leri (`kta-stock`)

**Subagent:** `kta-stock`  
**Files:**
- Modify: `erpnextkta/kta_stock/services/pda_service.py:360-520,1200-1336`
- Create (Test): `erpnextkta/kta_stock/tests/test_pda_settings.py`

**Interfaces:**
- Consumes: `_require_pda_operator()`, `_validate_pda_operator_record()`, `_verify_pin_with_rate_limit()`, `_employee_has_pda_pin()`, `_PDA_PIN_RE`, `get_pda_operators()`, `ZebraPrinterManager`, `frappe.boot.load_translations`, `set_encrypted_password`, `check_password`
- Produces (`erpnextkta/kta_stock/services/pda_service.py`):
  - `_build_pda_translations_payload(user_or_lang: str | None = None) -> dict` (`{"lang": str, "messages": dict[str, str]}`)
  - Updated `verify_pda_pin(employee: str, pin: str) -> dict` (`lang`, `messages` alanları dahil)
  - Updated `pda_handover_logout() -> dict` (`lang`, `messages` alanları dahil)
  - `pda_get_settings_data() -> dict` (`has_employee`, `employee`, `employee_name`, `has_pin`, `can_manage_operator_pins`, `authorized_printers`, `printer_preferences`, `user_language`, `manageable_operators`)
  - `pda_update_own_pin(new_pin: str, confirm_pin: str, mode: str = "initial", current_pin: str | None = None, account_password: str | None = None) -> dict` (`{"ok": True, "employee": str, "has_pin": True}`)
  - `pda_admin_reset_operator_pin(target_employee: str, new_pin: str, confirm_pin: str) -> dict` (`{"ok": True, "employee": str, "has_pin": True}`)
  - `pda_save_printer_preferences(printer: str | None = None, fallback_printer: str | None = None) -> dict` (`{"ok": True, "printer": str | None, "fallback_printer": str | None, "disabled": int}`)
  - `pda_test_printer_connection(printer_name: str) -> dict` (`{"ok": bool, "printer": str, "online": bool, "message": str}`)
  - `pda_update_user_language(language: str) -> dict` (`{"ok": True, "lang": str, "messages": dict[str, str]}`)

- [x] **Step 1: Write failing backend tests (`test_pda_settings.py`)**

`erpnextkta/kta_stock/tests/test_pda_settings.py` içinde `KTABaseTestCase` türevi test sınıfında aşağıdaki testleri yaz:

```python
def test_pda_get_settings_data_for_pure_operator_and_employeeless_admin(self):
    # 1) Pure Website User (KTA PDA Stock User) without Employee.write DocPerm:
    #    pda_get_settings_data() returns has_employee=True, has_pin=False/True,
    #    can_manage_operator_pins=False, manageable_operators=[], authorized_printers filtered by _user_can_print
    # 2) Employee-less Administrator / System Manager:
    #    pda_get_settings_data() returns has_employee=False, can_manage_operator_pins=True without DoesNotExistError

def test_pda_update_own_pin_initial_current_pin_and_password_reset_without_employee_save(self):
    # 1) Initial setup (has_pin=False): sets 4-digit PIN; patch Employee.save to assert it is NEVER called;
    #    rejects non-4-digit or mismatched confirm_pin with ValidationError
    # 2) Existing PIN (mode="current_pin"): requires valid current_pin; 5 failures lock pda_pin_fail:{emp}
    # 3) Forgot PIN (mode="account_password"): validates check_password; 5 wrong passwords lock
    #    pda_pwd_fail:{user} for 300s; valid password sets PIN & clears both pda_pwd_fail and pda_pin_fail

def test_pda_admin_reset_operator_pin_enforces_strict_rbac_and_clears_lockout(self):
    # 1) Plain KTA PDA Stock User -> PermissionError
    # 2) Self-reset (manager passing own employee) -> excluded from manageable_operators and PermissionError
    # 3) Stock Manager (without System Manager) -> manageable_operators excludes peer Stock Manager & System Manager;
    #    resetting either raises PermissionError; resetting non-manager KTA PDA operator succeeds & clears pda_pin_fail
    # 4) System Manager -> can reset peer Stock Manager and KTA PDA operator (except self)

def test_printer_preferences_and_connection_test_enforce_user_can_print_and_distinct_fallback(self):
    # 1) Unauthorized restricted printer -> PermissionError on save and test_connection
    # 2) Same printer and fallback_printer -> ValidationError
    # 3) Authorized ZEBRA-01 + ZEBRA-02 -> creates/updates KTA User Zebra Printers (disabled=0);
    #    clearing both sets disabled=1; test_connection invokes check_printer_status without printing labels

def test_live_language_sync_in_update_verify_pin_and_handover_logout(self):
    # 1) pda_update_user_language("en") updates User.language without User write DocPerm and returns lang="en" + non-empty messages
    #    invalid lang ("fr") raises ValidationError
    # 2) verify_pda_pin on operator with User.language="en" returns lang="en" + English messages
    # 3) pda_handover_logout() resets session to Guest and returns site default lang="tr" + Turkish messages
```

- [x] **Step 2: Run tests to verify they fail**

Run: `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_settings`  
Expected: FAIL with `ImportError` (`pda_get_settings_data`, `pda_update_own_pin` vb. henüz yok).

- [x] **Step 3: Implement backend settings, PIN, printer & live translation APIs in `pda_service.py`**

1. `_build_pda_translations_payload(user_or_lang: str | None = None) -> dict`:
   - Kullanıcının `User.language` bilgisini (veya doğrudan dil kodu/Guest için `"tr"`) çözüp `frappe.boot.load_translations` ile `{"lang": resolved_lang, "messages": dict(bootinfo.get("__messages") or {})}` döner.
2. `verify_pda_pin()` & `pda_handover_logout()`:
   - `verify_pda_pin`: `login_manager.login_as(emp.user_id)` sonrası `_build_pda_translations_payload(emp.user_id)` alanlarını (`lang`, `messages`) dönüş sözlüğüne ekle.
   - `pda_handover_logout`: logout sonrası `_build_pda_translations_payload("Guest")` alanlarını (`lang`, `messages`) dönüş sözlüğüne ekle.
3. `pda_get_settings_data()`:
   - `_require_pda_operator()` sonrası aktif kullanıcının aktif `Employee` kaydını, `can_manage_operator_pins` flag'ini, `ZebraPrinterManager._user_can_print` filtresinden geçen `authorized_printers` listesini, `KTA User Zebra Printers` tercihlerini, `user_language` değerini ve RBAC filtrelenmiş `manageable_operators` listesini döner (kendisi, `Stock Manager` için başka `Stock Manager`/`System Manager` hariç).
4. `pda_update_own_pin()` & `pda_admin_reset_operator_pin()`:
   - `_PDA_PIN_RE` (`^[0-9]{4}$`), `new_pin == confirm_pin`, 3 kendi-PIN modu (`initial`, `current_pin`, `account_password` + `pda_pwd_fail:{user}` 5-deneme/300s kilidi), RBAC kontrolleri ve `Employee.save()` çağırmadan `set_encrypted_password("Employee", emp.name, clean_pin, fieldname="custom_pda_pin")` uygula.
5. `pda_save_printer_preferences()` & `pda_test_printer_connection()`:
   - Varlık + `ZebraPrinterManager._user_can_print` + `printer != fallback_printer` doğrulaması; `KTA User Zebra Printers` idempotent `disabled = 1` (boşsa) / `0` güncellemesi; `ZebraPrinterManager().check_printer_status(printer_name)` ile etiketsiz bağlantı kontrolü.
6. `pda_update_user_language(language: str)`:
   - `_require_pda_operator()`, `language in ("tr", "en", "de")`, `frappe.db.set_value("User", user, "language", language)`, `frappe.clear_cache(user=user)`, `frappe.local.lang = language` ve `{"ok": True, **_build_pda_translations_payload(language)}`.

- [x] **Step 4: Run backend tests and ruff checks**

Run:
```bash
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_settings
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
/home/frappe/frappe-bench/env/bin/ruff check --ignore EXE002 erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_settings.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_settings.py
```
Expected: PASS (tüm testler ve ruff 0 hata).

- [x] **Step 5: Commit (Koordinatör)**

```bash
git add erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_settings.py
git commit -m "feat(pda): add backend settings, PIN, printer, and translation APIs"
```

---

### Task 3: Frontend Ayarlar Menüsü, Reaktif Çeviri Deposu, Tema/Ses Tercihleri & Paylaşılan Koyu Tema Uyumu (`frontend-public`)

**Subagent:** `frontend-public`  
**Files:**
- Modify: `erpnextkta/public/pda-hub/types.ts`
- Modify: `erpnextkta/public/pda-hub/utils/frappeShim.ts`
- Create: `erpnextkta/public/pda-hub/utils/pdaPreferences.ts`
- Modify: `erpnextkta/public/line-replenishment-pda/utils/audio.ts`
- Modify: `erpnextkta/public/line-replenishment-pda/components/PickingItemCard.vue` (`< 500` satır)
- Modify: `erpnextkta/public/line-replenishment-pda/components/TransferFooter.vue`
- Modify: `erpnextkta/public/line-replenishment-pda/components/OrderSelector.vue`
- Modify: `erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue`
- Modify: `erpnextkta/public/pda-hub/components/LauncherHome.vue`
- Create: `erpnextkta/public/pda-hub/components/PdaPinSettingsCard.vue` (`< 350` satır)
- Create: `erpnextkta/public/pda-hub/views/PdaSettingsView.vue` (`< 350` satır)
- Modify: `erpnextkta/public/pda-hub/PdaHubApp.vue`
- Create / Modify (Tests): `erpnextkta/public/pda-hub/__tests__/PdaSettingsView.spec.ts`, `PdaHubApp.spec.ts`, `PinLockAndLauncher.spec.ts`, `frappeShim.spec.ts`

**Interfaces:**
- Consumes: `pda_get_settings_data`, `pda_update_own_pin`, `pda_admin_reset_operator_pin`, `pda_save_printer_preferences`, `pda_test_printer_connection`, `pda_update_user_language`, `verify_pda_pin`, `pda_handover_logout` (Task 2)
- Produces:
  - `types.ts`: `PdaUtilityScreenKey = "settings"`, `PdaModuleKey = "home" | PdaScreenKey | PdaUtilityScreenKey`, `PdaPrinterOption`, `PdaPrinterPreferences`, `PdaSettingsPayload`, `PdaLanguageUpdateResponse`, `lang?` & `messages?` on `VerifyPdaPinResponse` / `HandoverLogoutResponse`
  - `frappeShim.ts`: `runtimeLocaleState`, `setRuntimeTranslations(lang: string, messages: Record<string, string>)`, reactive `translate()`
  - `pdaPreferences.ts`: `getStoredTheme()`, `setStoredTheme(theme)`, `applyTheme(theme)`, `isSoundEnabled()`, `setSoundEnabled(enabled)`
  - `PdaMenuDrawer.vue`: alt sabit `AYARLAR` grubu, `[data-testid="drawer-item-settings"]`, `emit("select-utility", "settings")`
  - `LauncherHome.vue`: `[data-testid="missing-pin-banner"]`, `emit("open-settings")`
  - `PdaSettingsView.vue` (`@pin-updated`) & `PdaPinSettingsCard.vue` (`@pin-updated`)

- [x] **Step 1: Write failing Vitest specs (`frappeShim.spec.ts`, `PinLockAndLauncher.spec.ts`, `PdaHubApp.spec.ts`, `PdaSettingsView.spec.ts`)**

1. `frappeShim.spec.ts`: `setRuntimeTranslations("en", {"Menü": "Menu"})` çağrısı sonrası `translate("Menü")` `"Menu"`, `document.documentElement.lang` `"en"`, `window.frappe._messages["Menü"]` `"Menu"` olduğunu doğrular; `audio.ts` `playBeep()` `localStorage.getItem("kta_pda_sound") === "0"` iken `AudioContext` başlatmaz.
2. `PinLockAndLauncher.spec.ts`: `activeOperator.has_pin === false` iken `[data-testid="missing-pin-banner"]` görünür ve `[Şimdi Belirle]` tıklanınca `open-settings` emit edilir; `has_pin === true` iken gizlidir. `PdaMenuDrawer.vue` altında `AYARLAR` bölümü ve `[data-testid="drawer-item-settings"]` `select-utility("settings")` emit eder.
3. `PdaHubApp.spec.ts`: Çekmeceden `[data-testid="drawer-item-settings"]` seçilince `.pda-subbar` üzerinde `← Geri | Ayarlar` açılır; `verify_pda_pin` ve `pda_handover_logout` yanıtlarındaki `lang` / `messages` alanları sayfa yenilenmeden tüm UI metinlerini canlı günceller; açılışta `kta_pda_theme = "dark"` ise `<html data-theme="dark">` uygulanır.
4. `PdaSettingsView.spec.ts`:
   - `has_pin === false` iken ilk kurulum formu (`mode="initial"`), `has_pin === true` iken `"current_pin"` / `"account_password"` sekme geçişi; `has_employee === false` iken bilgilendirme kartı; `can_manage_operator_pins === true` iken `manageable_operators` listesi (ve boşsa bilgilendirme metni).
   - Yazıcı seçimi/kaydetme & bağlantı testi (`pda_test_printer_connection`), tema/ses toggle (`localStorage` & `data-theme`) ve canlı dil seçimi (`pda_update_user_language` → `setRuntimeTranslations` çağrılır, `PdaSettingsView` açık kalır).

- [x] **Step 2: Run Vitest to verify it fails**

Run: `npm --prefix erpnextkta/public/pda-hub test`  
Expected: FAIL (`PdaSettingsView.vue`, `pdaPreferences.ts`, `setRuntimeTranslations` henüz yok).

- [x] **Step 3: Implement frontend utilities, shared dark mode fixes, components & integration**

1. `types.ts`: Yeni tip ve yanıt alanlarını ekle.
2. `frappeShim.ts`: `runtimeLocaleState` (`reactive`), `initFrappeShim()` içinde başlangıç sözlüğü yükleme, `setRuntimeTranslations(lang, messages)` ve `translate()`.
3. `pdaPreferences.ts` & `audio.ts`: SSR/Vitest korumalı `localStorage` yardımcıları ve `playBeep()` başında `kta_pda_sound === "0"` erken çıkışı.
4. Paylaşılan `line-replenishment-pda/components/{PickingItemCard,TransferFooter,OrderSelector}.vue`: Desk aydınlık stili korunarak `[data-theme="dark"]` kontrast düzeltmelerini yap; `PickingItemCard.vue` gereksiz tekrarlı CSS kurallarını sadeleştirerek `< 500` satırda tut.
5. `PdaMenuDrawer.vue` (`AYARLAR` sabit alt grup + `select-utility`) & `LauncherHome.vue` (`missing-pin-banner` + `open-settings`).
6. `PdaPinSettingsCard.vue` (`< 350` satır) & `PdaSettingsView.vue` (`< 350` satır).
7. `PdaHubApp.vue`: `applyTheme(getStoredTheme())`, `"settings"` rota/başlık/breadcrumb desteği, `@pin-updated="refreshBootState"`, `handleUnlocked` ve `handleHandoverLogout` içinde `setRuntimeTranslations` çağrıları.

- [x] **Step 4: Run Vitest, `< 500` line-count check, and production build**

Run:
```bash
npm --prefix erpnextkta/public/pda-hub test
wc -l erpnextkta/public/pda-hub/PdaHubApp.vue erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue erpnextkta/public/pda-hub/components/LauncherHome.vue erpnextkta/public/pda-hub/components/PdaPinSettingsCard.vue erpnextkta/public/pda-hub/views/PdaSettingsView.vue erpnextkta/public/line-replenishment-pda/components/PickingItemCard.vue erpnextkta/public/line-replenishment-pda/components/TransferFooter.vue erpnextkta/public/line-replenishment-pda/components/OrderSelector.vue
bench build --app erpnextkta --production
```
Expected: Tüm Vitest testleri PASS, listedeki tüm `.vue` dosyaları `< 500` satır, `bench build` 0 hata.

- [x] **Step 5: Commit (Koordinatör)**

```bash
git add erpnextkta/public/pda-hub/ erpnextkta/public/line-replenishment-pda/
git commit -m "feat(pda): add PDA settings UI, reactive i18n, and shared dark mode"
```

---

### Task 4: Append-Only TR/EN/DE Çeviriler, Portal & Geliştirici Kılavuzu Senkronizasyonu ve Final Kalite Kapısı (`docs-i18n` & Koordinatör)

**Subagents:** `docs-i18n` ve Koordinatör  
**Files:**
- Modify (append-only): `erpnextkta/translations/{tr,en,de}.csv`
- Modify: `erpnextkta/www/docs/stok-lojistik.html`
- Modify: `docs/kta_stok_lojistik_kilavuzu.md`
- Modify: `docs/superpowers/plans/2026-11-22-pda-settings-menu.md` & `docs/superpowers/specs/2026-11-22-pda-settings-menu-design.md`

**Interfaces:**
- Consumes: Task 2 ve Task 3 kaynaklarındaki tüm yeni `_()` / `__()` metinleri ve yeni RPC/UI mimarisi
- Produces: Tam eşleşmiş TR/EN/DE CSV sözlükleri (`0` silme), senkronize `/docs/stok-lojistik` portal sayfası ve geliştirici kılavuzu

- [x] **Step 1: Extract & append-only sync `tr.csv`, `en.csv`, `de.csv` (`docs-i18n`)**

`pda_service.py`, `PdaHubApp.vue`, `PdaMenuDrawer.vue`, `LauncherHome.vue`, `PdaPinSettingsCard.vue` ve `PdaSettingsView.vue` içindeki tüm `_()` / `__()` metinlerini çıkar; eksik anahtarları Title Case ve tam cümle kurallarıyla append-only ekle; `git diff --numstat -- erpnextkta/translations/` (`0` silme) ve Python `csv.reader` ile doğrula.

- [x] **Step 2: Synchronize `erpnextkta/www/docs/stok-lojistik.html` & `docs/kta_stok_lojistik_kilavuzu.md` (`docs-i18n`)**

Çekmece altı sabit `AYARLAR` menüsü, `LauncherHome` eksik PIN uyarı bandı, self-servis PIN kurulumu/değiştirme/`account_password` sıfırlama (`pda_pwd_fail`), RBAC sınırlı yönetici sıfırlama, `KTA User Zebra Printers` seçimi/bağlantı testi, cihaz bazlı koyu tema/ses ve sayfa yenilemesiz canlı dil senkronizasyonunu ticari/gizli veri olmadan her iki dokümana işle; HTML etiket dengesini ve gizlilik taramasını doğrula.

- [x] **Step 3: Mark Task 1–4 plan checkboxes `[x]` and Spec status `Implemented — Kalite Kapısı Doğrulandı` (`docs-i18n`)**

- [x] **Step 4: Run Coordinator Final Quality Gate & Commit**

Run:
```bash
bench build --app erpnextkta --production
/home/frappe/frappe-bench/env/bin/ruff check --ignore EXE002 erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_settings.py
/home/frappe/frappe-bench/env/bin/ruff format --check erpnextkta/kta_stock/services/pda_service.py erpnextkta/kta_stock/tests/test_pda_settings.py
npm --prefix erpnextkta/public/pda-hub test
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_settings
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_service
bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_stock.tests.test_pda_portal
git diff --numstat -- erpnextkta/translations/
```
```bash
git add erpnextkta/translations/ erpnextkta/www/docs/stok-lojistik.html docs/kta_stok_lojistik_kilavuzu.md docs/superpowers/plans/2026-11-22-pda-settings-menu.md docs/superpowers/specs/2026-11-22-pda-settings-menu-design.md
git commit -m "docs(pda): document PDA settings menu and sync TR/EN/DE translations"
```

---

## Self-Review Checklist

1. **Spec coverage:** Çekmece altı sabit `AYARLAR` + eksik PIN uyarı bandı (Task 3), self-servis PIN (`initial` / `current_pin` / `account_password` + `pda_pwd_fail`) & RBAC sınırlı `pda_admin_reset_operator_pin` (`Employee.save()` yok) (Task 2–3), Zebra yazıcı tercihi/bağlantı testi (`_user_can_print` / `check_printer_status`) (Task 2–3), cihaz bazlı tema/ses (`pdaPreferences.ts` + `audio.ts`) + paylaşılan `line-replenishment-pda` koyu tema düzeltmeleri (`PickingItemCard.vue < 500`) (Task 3), sayfa yenilemesiz reaktif dil (`_build_pda_translations_payload` + `frappeShim.ts`) (Task 2–3), append-only TR/EN/DE çeviri + portal/geliştirici dokümanları (Task 4). Boşluk yok.
2. **Type & Signature consistency:** `PdaUtilityScreenKey`, `manageable_operators`, `pda_get_settings_data`, `pda_update_own_pin`, `pda_admin_reset_operator_pin`, `pda_save_printer_preferences`, `pda_test_printer_connection`, `pda_update_user_language`, `_build_pda_translations_payload`, `runtimeLocaleState`, `setRuntimeTranslations`, `missing-pin-banner`, `drawer-item-settings` adları spec ve plan içinde birebir aynıdır.
3. **Review Focus coverage:** 5 kritik uç durumun tamamı Task 2 ve Task 3 testleriyle doğrudan sabitlenmiştir.
