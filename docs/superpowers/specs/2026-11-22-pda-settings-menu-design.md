# PDA Ayarlar Menüsü (Self-Servis PIN, Yazıcı ve Terminal Tercihleri) (Design Spec)

**Tarih:** 2026-11-22  
**Durum:** Implemented — Kalite Kapısı Doğrulandı  
**Önkoşul:** [KTA PDA Depo Merkezi Tasarım Dokümanı](./2026-11-21-pda-warehouse-hub-design.md), [PDA Rol Bazlı Menü ve Operatör Yetkilendirme Mimarisi](./2026-11-22-pda-role-based-menu-design.md), [PDA İki Satırlı Üst Bar ve Koli Birleştirme Mimarisi](./2026-11-22-pda-subbar-and-package-merge-design.md)  
**Kapsam:** `erpnextkta/kta_stock/services/pda_service.py`, `erpnextkta/public/pda-hub/types.ts`, `erpnextkta/public/pda-hub/utils/frappeShim.ts`, `erpnextkta/public/pda-hub/utils/pdaPreferences.ts`, `erpnextkta/public/line-replenishment-pda/utils/audio.ts`, `erpnextkta/public/line-replenishment-pda/components/PickingItemCard.vue`, `erpnextkta/public/line-replenishment-pda/components/TransferFooter.vue`, `erpnextkta/public/line-replenishment-pda/components/OrderSelector.vue`, `erpnextkta/public/pda-hub/components/PdaMenuDrawer.vue`, `erpnextkta/public/pda-hub/components/LauncherHome.vue`, `erpnextkta/public/pda-hub/components/PdaPinSettingsCard.vue`, `erpnextkta/public/pda-hub/views/PdaSettingsView.vue`, `erpnextkta/public/pda-hub/PdaHubApp.vue`, `erpnextkta/translations/{tr,en,de}.csv`, `erpnextkta/www/docs/stok-lojistik.html`, `docs/kta_stok_lojistik_kilavuzu.md`

---

## 1. Amaç ve Problem Tanımı (Intent & Why)

`KTA PDA Stock User` (`desk_access = 0`) rolüne sahip saf `Website User` saha operatörlerinin `/app` Frappe Desk erişimi bulunmadığından günlük el terminali kullanımında üç temel self-servis eksikliği ortaya çıkmaktadır:

1. **Self-Servis PIN Kurulumu ve Yönetimi Eksikliği:** İlk kez `/login?redirect-to=/pda` ile giriş yapan bir operatör kendi 4 haneli `Employee.custom_pda_pin` kodunu belirleyememekte, mevcut PIN'ini güncelleyememekte veya unuttuğunda Desk yöneticisi olmadan sıfırlayamamaktadır (`PinLockScreen` üzerinde `PIN Yok` olarak kalmaktadır).
2. **Zebra Yazıcı Tercihi ve Bağlantı Testi Eksikliği:** `ZebraPrinterManager.get_printer_for_user()` tarafından okunan `KTA User Zebra Printers` (`printer`, `fallback_printer`) kayıtları yalnızca Desk üzerinden düzenlenebilmekte, saha operatörü yetkili olduğu yazıcılar arasından birincil/yedek yazıcı seçememekte ve boş etiket harcamadan bağlantı testi yapamamaktadır.
3. **Terminal & Görünüm Tercihlerinin Arayüze Açılmamış Olması:** Tüm `/pda` ekranlarında CSS düzeyinde hazır olan `[data-theme="dark"]` koyu tema, barkod okuma ses geri bildirimi (`audio.ts`) ve kullanıcı arayüz dili (`tr`, `en`, `de`) operatör tarafından doğrudan değiştirilememektedir.

---

## 2. Hedefler, Hedef Dışı ve Anti-Hedefler (Goals, Non-Goals, Anti-Goals)

### 2.1 Hedefler (Goals)
* **Self-Servis PIN Yaşam Döngüsü:** Operatörün `/pda` içinden ilk kez 4 haneli PIN'ini kurması, mevcut PIN'i doğrulayarak güncellemesi veya PIN'ini unuttuğunda kendi ERPNext hesap şifresiyle güvenli biçimde sıfırlaması.
* **Yetkili Yönetici PIN Sıfırlama & Kilit Açma:** `Stock Manager` veya `System Manager` yetkili yöneticilerin, şifresini veya PIN'ini unutan saha operatörlerinin PIN'ini Ayarlar ekranı içinden sıfırlayabilmesi ve `pda_pin_fail:{emp}` 300 sn kilidini kaldırabilmesi.
* **Zebra Yazıcı Tercihleri & Bağlantı Testi:** Operatörün yalnızca kendi yetkili olduğu (`ZebraPrinterManager._user_can_print`) Zebra yazıcılardan varsayılan (`printer`) ve yedek (`fallback_printer`) seçebilmesi; tek dokunuşla boş etiket harcamadan yazıcı durumu/bağlantı testi yapabilmesi.
* **Terminal, Ses & Dil Tercihleri:** Açık/Koyu tema (`light` / `dark`), barkod okuma sesi (açık/kapalı) ve kullanıcı dili (`tr`, `en`, `de`) seçeneklerinin sunulması.

### 2.2 Hedef Dışı (Non-Goals)
* Yeni `KTA Zebra Printers` IP/port tanımı oluşturmak veya `KTA Printer Permission` rol yetkilerini değiştirmek (bu işlemler Desk sistem/depo yöneticisinin sorumluluğunda kalır).
* Saf `Website User` (`KTA PDA Stock User`) rolüne `Employee`, `User` veya `KTA User Zebra Printers` üzerinde doğrudan `write` / `create` DocPerm vermek.

### 2.3 Anti-Hedefler (Anti-Goals)
* `PDA_MODULE_REGISTRY` içine `Ayarlar` adında ikinci bir iş kategori klasörü ekleyip tek modüllü (`Stock`) depo çalışanının her PIN girişinde fazladan klasör seçmek zorunda kalmasına yol açmak.
* Masada açık unutulmuş bir el terminalinde mevcut PIN veya hesap şifresi doğrulaması olmadan PIN değiştirilmesine izin vermek.
* PIN kaydederken `Employee.save()` çalıştırıp gereksiz `Employee.on_update()` / `update_user()` yan etkileri doğurmak.

---

## 3. Değerlendirilen Yaklaşımlar ve Seçilen Mimari (`Yaklaşım A`)

| Yaklaşım | Açıklama | Karar | Neden? |
| :--- | :--- | :--- | :--- |
| **Yaklaşım A: Menü Çekmecesinde Alt Sabit `AYARLAR` Başlığı** | `PDA_MODULE_REGISTRY` yalnızca iş modüllerini (`Stock` vb.) tutar; `PdaMenuDrawer.vue` altında ayrı sabit `AYARLAR` grubu (`⚙️ Kullanıcı & Cihaz Ayarları`, `activeModule = "settings"`) gösterilir. | ✅ **SEÇİLDİ** | Tek kategorili (`Stock`) kullanıcılar PIN girişinden sonra yine doğrudan 5 depo kartına düşer; ekstra klasör tıklaması doğmaz. |
| **Yaklaşım B: `PDA_MODULE_REGISTRY` İçinde 2. Klasör** | `Ayarlar` ekranını kayıt defterinde 2. kategori klasörü olarak tanımlamak. | ❌ Reddedildi | `menu_categories.length > 1` olacağından tek iş modüllü tüm depo personeline her açılışta fazladan bir klasör tıklaması ekler. |

### `Yaklaşım A` Kullanıcı Deneyimi Akışı
1. **Çekmeceden Erişim:** `PdaMenuDrawer.vue` içinde yetkili iş kategorilerinin (`📦 Stock` vb.) altında ayırıcı çizgi sonrası sabit **`AYARLAR`** başlığı ve `[data-testid="drawer-item-settings"]` (`⚙️ Kullanıcı & Cihaz Ayarları`) butonu yer alır.
2. **Alt Bar (`PdaHubApp.vue` `.pda-subbar`):** `"settings"` açıldığında `.pda-subbar` üzerinde `← Geri | Ayarlar` başlığı görünür; `[← Geri]` ana ekrana (`activeModule = "home"`) döner.
3. **Eksik PIN Uyarı Bandı (*[Builder Call]*):** `LauncherHome.vue` üzerinde giriş yapan kullanıcının aktif çalışan kaydı (`activeOperator`) bulunup `activeOperator.has_pin === false` ise üstte tek satırlık `[data-testid="missing-pin-banner"]` (`"PIN kodunuz henüz tanımlı değil → [Şimdi Belirle]"`) bandı gösterilir ve tek dokunuşla doğrudan `settings` ekranına geçirir.

---

## 4. Teknik Mimari, Yetki Sınırları ve Builder Kararları (*Builder Calls*)

### 4.1 Yetki Sınırları ve Backend API Kapsamı (`erpnextkta/kta_stock/services/pda_service.py`)
* **Self-Service Güvenlik Kuralı:** `KTA PDA Stock User` (`desk_access = 0`) kullanıcılarının `Employee`, `User` ve `KTA User Zebra Printers` DocType'ları üzerinde doğrudan `write` / `create` DocPerm izni **bulunmaz**. Yeni Ayarlar API uçlarının tamamı `_require_pda_operator()` ile oturumu doğrular ve yalnızca aktif `frappe.session.user` hesabının kendi kayıtları üzerinde çalışır (`pda_admin_reset_operator_pin` hariç — bu uç ek olarak `{"Stock Manager", "System Manager"}` rolünü zorunlu kılar).
* **Okuma Sözleşmesi (*[Builder Call]*):**
  * `LauncherHome.vue` eksik PIN uyarısı için ek ağ çağrısı yapmaz; `get_pda_boot_data()` ve `verify_pda_pin()` içinde `active_operator.has_pin` alanı halihazırda gelmektedir.
  * Ayarlar ekranı açıldığında çağrılan bağımsız **`GET pda_get_settings_data() -> dict`** ucu tanımlanarak `PdaBootData` yükünün şişmesi önlenir:
    - `has_employee: bool`, `employee: str | None`, `employee_name: str | None`, `has_pin: bool`
    - `can_manage_operator_pins: bool` (`bool(set(frappe.get_roles()) & {"Stock Manager", "System Manager"})`)
    - `authorized_printers: list[{name, ip, port}]`
    - `printer_preferences: {printer: str | None, fallback_printer: str | None, disabled: int}`
    - `user_language: str` (`"tr" | "en" | "de"`)
    - `manageable_operators: list[PdaOperator]` (yalnızca `can_manage_operator_pins == True` ise dolu döner; standart operatörlerde `[]` döner ve aşağıdaki katı RBAC sınırına göre yalnızca çağıran yöneticinin sıfırlamaya yetkili olduğu hedef operatörleri içerir).

### 4.2 PIN Güvenlik Modeli (`pda_update_own_pin` & `pda_admin_reset_operator_pin`)
* **Ortak Kurallar:** Tüm yeni PIN değerleri `^[0-9]{4}$` (`_PDA_PIN_RE`) desenine ve `new_pin == confirm_pin` eşleşmesine uymalıdır; aksi durumda `frappe.ValidationError` fırlatılır.
* **4 Doğrulama Modu & Katı RBAC Sınırı:**
  1. **Durum 1 — İlk Kurulum (`has_pin == False`):** Kullanıcı `/login?redirect-to=/pda` üzerinden kendi hesabına giriş yaptığı için ek mevcut-PIN doğrulaması gerekmeden ilk 4 haneli PIN'ini oluşturur (`mode = "initial"`).
  2. **Durum 2 — Mevcut PIN Güncelleme (`has_pin == True`, `mode = "current_pin"`):** Terminal masada açık kalmış olabileceğinden `current_pin` zorunludur ve `_verify_pin_with_rate_limit(emp.name, current_pin)` ile doğrulanır (5 hatalı denemede 300 sn kilitleme kuralı geçerlidir).
  3. **Durum 3 — PIN'imi Unuttum (`has_pin == True`, `mode = "account_password"`):** Operatör kendi ERPNext hesap şifresini girerek `frappe.utils.password.check_password(frappe.session.user, account_password)` ile doğrular. Açık terminalde kaba kuvvet şifre denemelerini önlemek için ayrı `pda_pwd_fail:{user}` önbellek anahtarıyla **5 hatalı denemede 300 sn kilitleme** uygulanır. Başarılı doğrulamada hem `pda_pwd_fail:{user}` hem `pda_pin_fail:{emp.name}` kilit sayacı temizlenir.
  4. **Durum 4 — Vardiya Amiri / Yönetici Sıfırlama (`POST pda_admin_reset_operator_pin(target_employee, new_pin, confirm_pin)`):** Yalnızca `{"Stock Manager", "System Manager"}` rolleri çağırabilir (aksi halde `frappe.PermissionError`). Hedef çalışan `_validate_pda_operator_record(target_employee)` ile doğrulanır, yeni 4 haneli PIN atanır ve varsa `pda_pin_fail:{target_employee}` kilidi temizlenir. Ek olarak hem `manageable_operators` listelemesinde hem `pda_admin_reset_operator_pin` içinde aşağıdaki **katı RBAC yetki sınırı** uygulanır:
     - **Kendi Kendini Sıfırlama Yasağı:** `target.user_id == frappe.session.user` her zaman `manageable_operators` dışındadır ve `pda_admin_reset_operator_pin` çağrısında `frappe.PermissionError` ile reddedilir; kilidi açık yönetici kendi PIN'ini yalnızca kendi kartından `current_pin` veya `account_password` doğrulamasıyla değiştirebilir.
     - **`Stock Manager` (`System Manager` rolü olmadan):** Yalnızca bağlı `User` hesabında **ne `"Stock Manager"` ne de `"System Manager"`** rolü bulunan aktif saha PDA operatörlerini (`KTA PDA *`) `manageable_operators` listesinde görür ve sıfırlayabilir. Bir `Stock Manager` veya `System Manager` kullanıcısının PIN'ini sıfırlama girişimi `frappe.PermissionError` fırlatır.
     - **`System Manager`:** Kendisi dışındaki tüm aktif PDA operatörlerini listeleyebilir ve sıfırlayabilir.
* **Veri Yazma Yöntemi (*[Builder Call]*):** `Employee.save()` yerine doğrudan `set_encrypted_password("Employee", emp.name, clean_pin, fieldname="custom_pda_pin")` kullanılır; böylece `Employee.on_update()` ve `update_user()` kancaları tetiklenmeden yalnızca `__Auth` PIN kaydı güncellenir. Güncelleme sonrası istemcide `activeOperator.has_pin` ve `operators` listesi senkronize edilir (ek `refreshBootState()` çağrısıyla sunucu ile eşitlenir).
* **Çalışan Kaydı Olmayan Yönetici Hesapları (*[Builder Call]*):** Aktif `Employee` eşleşmesi bulunmayan `Administrator` / `System Manager` kullanıcılarında `"Kendi PIN Yönetimi"` kartı salt bilgilendirme durumuyla gösterilir; yazıcı tercihi, terminal tercihi ve yönetici `"Personel PIN Sıfırla"` araçları tam olarak çalışmaya devam eder.

### 4.3 Zebra Yazıcı Tercihleri & Bağlantı Testi
* **Yetkili Yazıcı Listesi:** `KTA Zebra Printers` kayıtları `ZebraPrinterManager._user_can_print(frappe.session.user, printer_name)` ile filtrelenir (üzerinde hiç `KTA Printer Permission` satırı olmayan herkese açık yazıcılar + kullanıcının rolüne izin verilmiş yazıcılar listelenir).
* **Kaydetme (`POST pda_save_printer_preferences(printer: str | None = None, fallback_printer: str | None = None)`):**
  - `_require_pda_operator()` kontrolü uygulanır.
  - Boş olmayan her yazıcı adının `KTA Zebra Printers` tablosunda mevcut olması ve `ZebraPrinterManager._user_can_print` ile kullanıcıya açık olması zorunludur (yetkisiz yazıcıda `frappe.PermissionError`, olmayan yazıcıda `frappe.ValidationError`).
  - Hem `printer` hem `fallback_printer` seçilmişse aynı yazıcı olamaz (`frappe.ValidationError`).
  - `KTA User Zebra Printers` (`autoname = field:user`) kaydı `frappe.session.user` için idempotent oluşturulur veya güncellenir: her iki alan boş bırakılırsa `disabled = 1`, en az biri seçiliyse `disabled = 0` kaydedilir.
* **Bağlantı Testi (`POST pda_test_printer_connection(printer_name: str)`):**
  - `_require_pda_operator()`, yazıcı varlığı ve `_user_can_print` doğrulaması sonrası `ZebraPrinterManager().check_printer_status(printer_name)` çağrılır.
  - Boş etiket veya ZPL komutu yazdırmadan yalnızca bağlantı/durum sonucunu (`{ok, printer, online, message}`) döner (test ortamında mocklanabilir).

### 4.4 Terminal, Ses, Canlı Dil Senkronizasyonu ve Paylaşılan Koyu Tema Düzeltmeleri
* **Cihaz Bazlı Tercihler — Tema & Ses (*[Builder Call]*):**
  - Tema (`kta_pda_theme`: `"light" | "dark"`) ve Barkod Sesi (`kta_pda_sound`: `"1" | "0"`, varsayılan `"1"`) fiziksel el terminalinin bulunduğu ışık/gürültü ortamına bağlı olduğu için tarayıcı `localStorage` üzerinde tutulur.
  - `PdaHubApp.vue` mount sırasında `applyTheme(getStoredTheme())` ile `document.documentElement.setAttribute("data-theme", "dark")` uygular (aydınlıkta kaldırır veya `"light"` yazar).
  - `erpnextkta/public/line-replenishment-pda/utils/audio.ts` içindeki `playBeep()` başında `try { if (typeof localStorage !== "undefined" && localStorage.getItem("kta_pda_sound") === "0") return; } catch {}` kontrolü eklenerek tüm PDA modüllerindeki bip/hata sesleri sessiz moda uyarlanır.
* **Kullanıcı Bazlı Reaktif Sayfa Yenilemesiz Canlı Dil Senkronizasyonu (*[Builder Call]*):**
  - Arka uç yardımcısı **`_build_pda_translations_payload(user_or_lang: str) -> dict`**, kullanıcının `User.language` ayarını (veya `"Guest"` için site varsayılanı `"tr"` dilini) okuyup `frappe.boot.load_translations` çalıştırır ve `{"lang": resolved_lang, "messages": dict}` sözlüğünü üretir.
  - Üç backend ucu JSON yanıtlarında `"lang"` ve `"messages"` alanlarını döndürür:
    1. **`POST pda_update_user_language(language: str)`:** `_require_pda_operator()` sonrası yalnızca `("tr", "en", "de")` kodlarını kabul eder (`frappe.ValidationError` aksinde), `frappe.db.set_value("User", frappe.session.user, "language", language)`, `frappe.clear_cache(user=frappe.session.user)` ve `frappe.local.lang = language` çalıştırıp `{"ok": True, "lang": resolved_lang, "messages": ...}` döner.
    2. **`POST verify_pda_pin(employee, pin)`:** `login_manager.login_as(emp.user_id)` sonrasında giriş yapan operatörün `User.language` çevirilerini yükleyerek `VerifyPdaPinResponse` (`types.ts`) içine `lang` ve `messages` ekler.
    3. **`POST pda_handover_logout()`:** Oturumu `Guest` durumuna çektikten sonra site/varsayılan `"tr"` çevirilerini yükleyerek `HandoverLogoutResponse` (`types.ts`) içinde `lang` ve `messages` döndürür.
  - Ön uçta `erpnextkta/public/pda-hub/utils/frappeShim.ts` içinde Vue `reactive` yerel ayar deposu (`runtimeLocaleState: { lang: string; messages: Record<string, string> }`) tutulur; başlangıçta `window.frappe.boot` / `window.frappe._messages` üzerinden hidratlanır. Yeni `setRuntimeTranslations(lang, messages)` yardımcısı `runtimeLocaleState`'i günceller, `window.frappe._messages` ve `window.frappe.boot.__messages` alanlarını eşitler ve `document.documentElement.lang = lang` ayarlar; `translate()` doğrudan `runtimeLocaleState.messages` üzerinden okur. Böylece **sayfa yenilemesi (`window.location.reload()`) olmadan**, Ayarlar ekranında dil değiştirildiğinde (`PdaSettingsView` açık kalarak), başka bir operatör PIN ile açılış yaptığında veya `[Devret ↩]` tıklandığında tüm `__(...)` metinleri `0ms` içinde reaktif olarak güncellenir.
* **Paylaşılan `line-replenishment-pda` Koyu Tema Kontrast Düzeltmeleri (*[Builder Call]*):**
  - `PickingModuleView.vue`, `erpnextkta/public/line-replenishment-pda/components/` altındaki **`PickingItemCard.vue`**, **`TransferFooter.vue`** ve **`OrderSelector.vue`** bileşenlerini doğrudan içe aktarır. Bu 3 paylaşılan bileşende yer alan sabit aydınlık renkler (`#f0fdf4`, `#334155`, `#475569`, `--btn-default-bg` vb.) `[data-theme="dark"]` altında okunmaz hale gelmektedir.
  - Desk `/app/line-replenishment-picking` aydınlık görünümü %100 korunarak bu 3 bileşene tema uyumlu CSS değişkenleri / `[data-theme="dark"]` kuralları eklenir (`PickingItemCard.vue` tekrarlı stil kuralları konsolide edilerek `< 500` satır sınırının altına indirilir).

### 4.5 Frontend Bileşen Mimarisi (`erpnextkta/public/pda-hub/`, her `.vue` `< 500` satır)
* **`types.ts`:**
  - `PdaUtilityScreenKey = "settings"`
  - `PdaModuleKey = "home" | PdaScreenKey | PdaUtilityScreenKey` (`PdaScreenKey` yalnızca iş ekranlarını temsil etmeye devam eder)
  - `VerifyPdaPinResponse` ve `HandoverLogoutResponse` tiplerine `lang?: string` ve `messages?: Record<string, string>` alanları eklenir; `PdaPrinterOption`, `PdaPrinterPreferences`, `PdaLanguageUpdateResponse` ve `PdaSettingsPayload` (`manageable_operators: PdaOperator[]` dahil) tipleri tanımlanır.
* **`utils/frappeShim.ts` & `utils/pdaPreferences.ts`:**
  - `frappeShim.ts`: `runtimeLocaleState`, `setRuntimeTranslations(lang, messages)` ve reaktif `translate()`.
  - `pdaPreferences.ts`: `getStoredTheme()`, `setStoredTheme(theme)`, `applyTheme(theme)`, `isSoundEnabled()`, `setSoundEnabled(enabled)` yardımcıları (SSR ve Vitest `jsdom` için `try/catch` korumalı `localStorage` sarmalayıcısı).
* **`components/PdaMenuDrawer.vue`:**
  - İş kategorilerinin altında sabit **`AYARLAR`** bölümü ve `[data-testid="drawer-item-settings"]` (`⚙️ Kullanıcı & Cihaz Ayarları`) butonu eklenir; tıklandığında `select-utility` / `select-screen` aracılığıyla `activeModule = "settings"` açılır ve çekmece kapanır.
* **`views/PdaSettingsView.vue` (`< 350` satır) & `components/PdaPinSettingsCard.vue` (`< 350` satır):**
  - `PdaPinSettingsCard.vue`: İlk PIN kurulumu, Mevcut PIN ile değiştirme, Hesap Şifresi ile sıfırlama modu ve yalnızca `can_manage_operator_pins == True` iken görünen `"Personel PIN Sıfırla"` kartını barındırır; `manageable_operators` listesi boşsa (ör. sıfırlama yetkisi kapsamında uygun operatör bulunmadığında) temiz bir bilgilendirme mesajı gösterir.
  - `PdaSettingsView.vue`: `PdaPinSettingsCard`, Zebra Yazıcı Seçimi + Bağlantı Testi kartı ve Görünüm (Açık/Koyu Tema), Barkod Sesi (Açık/Kapalı) ve sayfa yenilemesiz canlı Dil (`Türkçe / English / Deutsch` → `setRuntimeTranslations`) kartlarını Light & `[data-theme="dark"]` uyumlu dokunmatik düzende sunar.
* **`components/LauncherHome.vue`:**
  - `activeOperator && !activeOperator.has_pin` ise ana kartların üstünde tek satırlık `[data-testid="missing-pin-banner"]` uyarısı ve `[Şimdi Belirle]` butonu (`@open-settings`) gösterilir.
* **`PdaHubApp.vue`:**
  - `"settings"` durumu için `activeModuleTitle = __("Ayarlar")`, breadcrumb = `__("Ayarlar")` (`.pda-subbar` üzerinde `← Geri | Ayarlar`), `<PdaSettingsView />` bağlanması (`@pin-updated="refreshBootState"`), `handleUnlocked` ve `handleHandoverLogout` içinde sunucudan dönen `lang` / `messages` varsa `setRuntimeTranslations(res.lang, res.messages)` çalıştırılması ve bileşen başlangıcında `applyTheme(getStoredTheme())` uygulanması sağlanır.

---

## 5. Uygulayıcıya Bırakılan Detaylar ve Gizlilik Kuralı

* Test dosyaları (`erpnextkta/kta_stock/tests/test_pda_settings.py` veya `test_pda_service.py` eklemeleri + Vitest `PdaSettingsView.spec.ts` / `PdaHubApp.spec.ts`), `PdaSettingsView.vue` / `PdaPinSettingsCard.vue` iç CSS yerleşimi (`360px–480px`) ve Title Case TR/EN/DE çeviri eklemeleri (append-only, `0` silme) uygulama planında belirlenir.
* Dokümantasyon ve örneklerde kesinlikle gerçek tedarikçi/müşteri firma adı veya birim fiyat/maliyet bilgisi yer almaz (yalnızca anonim yazıcı/operatör örnekleri kullanılır: ör. `ZEBRA-01`, `ZEBRA-02`).
