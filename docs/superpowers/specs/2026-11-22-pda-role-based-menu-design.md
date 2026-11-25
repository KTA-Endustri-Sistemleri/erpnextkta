# PDA Rol Bazlı Menü ve Operatör Yetkilendirme Mimarisi (Design Spec)

**Tarih:** 2026-11-22  
**Durum:** Implemented — Kalite Kapısı Doğrulandı  
**Önkoşul:** [KTA PDA Depo Merkezi Tasarım Dokümanı](./2026-11-21-pda-warehouse-hub-design.md)  
**Kapsam:** `erpnextkta/kta_stock/setup.py`, `erpnextkta/kta_stock/pda_user_guard.py`, `erpnextkta/kta_stock/services/pda_service.py`, `erpnextkta/kta_stock/line_replenishment_service.py`, `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py`, `erpnextkta/hooks.py`, `erpnextkta/www/pda.py`, `erpnextkta/patches/v4_4/**`, `erpnextkta/public/pda-hub/**`

---

## 1. Amaç ve Neden (Intent & Why)

`/pda` el terminali portalı (`erpnextkta/www/pda.py`, `erpnextkta/public/pda-hub/`), başlangıçta ambar ve sevkiyat işlemleri için tasarlanmış olsa da ileride yalnızca depo değil **Kalite**, **Üretim**, **Bakım** gibi farklı saha operasyonlarını da barındıracak çok-modüllü ana saha terminaline dönüşecektir.

Mevcut uygulamada iki temel mimari kısıt bulunmaktadır:
1. **Düz Menü ve Tek Seviyeli Ekran:** Mevcut 4 stok ekranı (`picking`, `split`, `transfer`, `lookup`) düz bir açılış ekranında (`LauncherHome.vue`) listelenmektedir; yeni bir saha alanı (ör. Kalite veya Üretim) eklendiğinde modülleri kategorize eden bir ana menü ve her ekrandan erişilebilen kalıcı gezinme çekmecesi bulunmamaktadır.
2. **Sabit Departman Filtresi ve Geniş `Stock User` Çakışması:** Operatör listesi (`get_pda_operators`), sabit `PDA_DEPARTMENTS = ("AMBAR - KTA", "Sevk")` departman filtresine ve ofis profillerinin (`KTA Satış`, `KTA Satınalma`, `KTA Üretim`, `KTA Standart Kullanıcı`) çoğunda halihazırda yer alan geniş `Stock User` (`desk_access = 1`) rolüne dayanmaktadır.

Bu tasarımın temel amacı:
- Sabit departman bağımlılığını (`PDA_DEPARTMENTS`) tamamen kaldırarak operatör ve menü yetkisini doğrudan rol merkezli yönetmek,
- Saf saha operatörlerini Frappe Desk (`/app`) arayüzünden tam olarak izole edebilmek (`Website User` / `desk_access = 0`),
- Depo yöneticilerinin ve sistem yöneticilerinin (`Stock Manager`, `System Manager`) ise hem Desk hem PDA kullanabilmesini korumak,
- Mevcut 4 depo ekranını ölçeklenebilir bir **Stock** ana menüsü altında toplayarak ileride Kalite/Üretim/Bakım gibi modüllerin tek kayıtla eklenebileceği temiz bir altyapı kurmaktır.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler (Goals, Non-Goals, Anti-Goals)

### 2.1 Hedefler (Goals)
* **`KTA PDA Stock User` Rolü (`desk_access = 0`):** `erpnextkta/kta_stock/setup.py` ve migration patch üzerinden idempotent olarak oluşturulması.
* **Kesintisiz Geçiş (Backfill):** Mevcut aktif `AMBAR - KTA` ve `Sevk` departmanlarındaki etkin stok kullanıcılarına geçiş anında kesinti yaşanmaması için tek seferlik migration patch ile `KTA PDA Stock User` rolünün eklenmesi (mevcut rollerini silmeden).
* **Merkezi Rol ve Menü Kayıt Defteri (`PDA_MODULE_REGISTRY`):** `PDA_DEPARTMENTS` filtresinin kaldırılması; hem PIN ekranındaki operatör listesinin hem de menü kategorileri/ekranlarının görünürlüğünün `PDA_MODULE_REGISTRY` üzerindeki rol kurallarıyla belirlenmesi.
* **Stock Ana Menüsü & Kalıcı Çekmece Navigasyonu:** Mevcut 4 ekranın (`Hat İkmal Toplama`, `Koli Bölme ve Etiketleme`, `Depo Raf Transferi`, `Stok ve Etiket Sorgula`) **Stock** (`__("Stock")`) ana menüsü altında gruplanması; üst barda her an erişilebilir **`☰ Menü` yan çekmecesi (slide-over drawer)** ve bağlamsal konum başlığı (`Stock › ...`) sunulması.
* **Saf `Website User` Saha Operatörü Uçtan Uca Desteği:** Üzerinde `Stock User` veya `Employee` rolü bulunmayan, yalnızca `KTA PDA Stock User` (`desk_access = 0`) rolüne sahip bir `Website User` operatörün `/app` Desk'e erişememesi; ancak `/pda` üzerindeki 4 Stock ekranının tamamını `PermissionError` almadan ve oluşan tüm belgelerde `owner` / `modified_by` kendi kullanıcı adı olacak şekilde uçtan uca çalıştırabilmesi.

### 2.2 Kapsam Dışı (Non-Goals)
* Bu aşamada Kalite, Üretim veya Bakım modüllerinin yeni iş ekranlarını geliştirmek (yalnızca bu modüllerin tek bir kayıt girdisiyle eklenebileceği çok-modüllü menü ve rol mimarisi kurulur).
* Stock altındaki 4 ekran için 4 ayrı rol oluşturmak (ancak kayıt şeması ilerisi için ekran bazlı `allowed_roles` tanımını doğal olarak destekler).
* Mevcut masaüstü Desk sayfası `/app/line-replenishment-picking` (`erpnextkta/public/line-replenishment-pda/`) davranışını veya Desk kullanıcılarının ikmal toplama erişimini bozmak.

### 2.3 Anti-Hedefler (Anti-Goals)
* Ofis profillerindeki genel `Stock User` rolüne sahip çalışanların otomatik olarak `/pda` PIN ekranındaki operatör listesine düşmesi veya `/pda` Stock menüsünü görmesi.
* Yalnızca `desk_access == 0` kontrolü yaparak `Stock Manager` veya `System Manager` gibi Desk yetkili depo sorumlularını `/pda` dışına itmek.
* Arka uç servislerinde `frappe.set_user("Administrator")` veya benzeri yetki yükseltmeleriyle belge sahipliğini (`owner`) ve denetim izini bozmak.

---

## 3. Kısıtlar ve Frappe Mimari Gerçekleri (Constraints)

1. **Frappe `User.set_system_user()` / `desk_access` Kuralı:**
   Frappe'de bir kullanıcının sahip olduğu rollerden **tek birinde bile `desk_access = 1`** varsa kullanıcı otomatik olarak `System User` olur ve `/app` Desk'e erişebilir; tüm rollerinde `desk_access = 0` ise kullanıcı `Website User` olarak kalır ve Desk erişimi engellenir. Bu nedenle saf saha operatörü rolü olan `KTA PDA Stock User` kesinlikle `desk_access = 0` tanımlanmalıdır (yöneticinin ilgili saha operatöründen `Stock User` / `Employee` gibi `desk_access = 1` rollerini kaldırması ve aşağıdaki `doc_events` (`pda_user_guard.py`) korumasının devrede olması yeterlidir).
2. **`Employee.on_update() -> update_user()` Otomatik `"Employee"` Rolü Riski:**
   ERPNext çekirdeğindeki `Employee.on_update() -> update_user()` (`hrms.overrides.employee_master.EmployeeMaster` tarafından miras alınır) her `Employee` kaydında (ör. `custom_pda_pin` alanı güncellendiğinde) koşulsuz olarak `user.append_roles("Employee")` çağırır. `"Employee"` rolü `desk_access = 1` taşıdığından, bu koruma olmazsa saf `Website User` saha operatörü ilk `Employee` güncellemesinde tekrar `System User` durumuna yükselir; bu nedenle `EmployeeMaster` sınıfını ezmeden `doc_events` (`pda_user_guard.py`) üzerinden korunur.
3. **`Serial and Batch Bundle` & `Stock Entry` Doğrudan İzin Zinciri:**
   ERPNext çekirdeğinde `StockEntry.on_submit()` içinde çalışan `SerialBatchCreation.make_serial_and_batch_bundle()`, `Serial and Batch Bundle` belgesi üzerinde `ignore_permissions` kullanmadan `doc.save()` ve `doc.submit()` çağırır; ayrıca `StockEntry.submit()` doğrudan `submit` izni arar. Bu nedenle `KTA PDA Stock User` rolüne `erpnextkta/kta_stock/setup.py` içinde `Custom DocPerm` kayıtları idempotent olarak verilmelidir:
   - `Stock Entry`: `read`, `write`, `create`, `submit`
   - `Serial and Batch Bundle`: `read`, `write`, `create`, `submit`
   - `Batch`: `read`, `write`, `create`
   - `Stock Ledger Entry`: `read`
   - `Item`: `read`
   - `Warehouse`: `read`
   - `KTA Stock Label`: `read`, `write`, `create`
   - `KTA Line Replenishment Order`: `read`, `write`
4. **Frontend & Kod Standartları:**
   - Tüm `.vue` dosyaları **< 500 satır** sınırında kalmalıdır.
   - Her `.vue` bileşeninde `const __ = (...args: any[]) => (window as any).__(...args);` sarmalayıcısı tanımlanmalı, Light & `[data-theme="dark"]` tema uyumu korunmalı ve modal/çekmece bileşenleri `<Teleport to="body">` içinde render edilmelidir.
   - Rol adı standart İngilizce (`KTA PDA Stock User`) olmalı; kullanıcıya dönük yeni metinler (TR/EN/DE) uygulama aşamasında `erpnextkta/translations/{tr,en,de}.csv` dosyalarına append-only (`0` silme) olarak eklenmelidir.

---

## 4. Değerlendirilen Yaklaşımlar ve Seçim (Approaches)

### 4.1 Rol ve Yetkilendirme Kurgusu

| Yaklaşım | Açıklama | Karar | Neden? |
| :--- | :--- | :--- | :--- |
| **1. Modül Bazlı `desk_access = 0` PDA Rolleri + Yönetici Rolleri** | `KTA PDA Stock User` (`desk_access = 0`) + sorumlular için `Stock Manager`, `System Manager` | ✅ **SEÇİLDİ** | Ofis `Stock User` profilleriyle çakışmaz; saf saha operatörünü `/app` Desk'ten izole ederken sorumluları da dışlamaz. |
| **2. Mevcut `Stock User` + `custom_pda_pin` Filtresi** | PIN tanımlı tüm `Stock User` hesaplarını listelemek | ❌ Reddedildi | `KTA Üretim` gibi ofis profillerinde `Stock User` zaten bulunduğundan modüller arası yetki sızıntısına yol açar. |
| **3. Sadece `desk_access == 0` Kullanıcı Kontrolü** | Yalnızca `Website User` hesaplarına PDA açmak | ❌ Reddedildi | Desk yetkili depo sorumlularını dışarıda bırakır ve bir kullanıcının gelecekteki Kalite vs. Stock erişimini ayıramaz. |
| **4. Özel User Type (`is_standard = 0`) Oluşturmak** | Yalnızca standart dışı özel `User Type` tanımlamak | ❌ Reddedildi | Frappe `www/app.py` yalnızca `Website User` tipini `/app` Desk'ten engeller; ayrıca `User.set_roles_and_modules_based_on_user_type()` her kayıtta `self.roles = []` çalıştırıp çoklu PDA modül rolünü siler ve zorunlu `User Permission` kısıtı getirir. |

### 4.2 Çok-Modüllü Menü ve Navigasyon UX

| Yaklaşım | Açıklama | Karar | Neden? |
| :--- | :--- | :--- | :--- |
| **A. İki Seviyeli Kategori Hub + Sol Üst `☰ Menü` Çekmecesi + Akıllı Açılış** | Tek yetkili kategoride doğrudan ekranları açar; `☰ Menü` her ekrandan kategori/ekran geçişi sağlar | ✅ **SEÇİLDİ** | Bugün yalnızca `Stock` varken ekstra tıklama yaratmaz; yarın Kalite/Üretim eklendiğinde çekmece ve hub kendiliğinden ölçeklenir. |
| **B. Çekmecesiz Akordiyon Tek Ekran** | Tüm kategorileri ve ekranları ana sayfada katlanır başlıklarla göstermek | ❌ Reddedildi | Modül sayısı arttıkça mobil ekran uzar; aktif ekran içindeyken kardeş ekranlara hızlı geçişi zorlaştırır. |

---

## 5. Kararlaştırılan Tasarım Detayları (How It Works)

### 5.1 Merkezi Modül ve Menü Kayıt Defteri (`PDA_MODULE_REGISTRY`)
`erpnextkta/kta_stock/services/pda_service.py` içinde modül ve alt ekran hiyerarşisi merkezi sabit veri yapısıyla yönetilir:

```python
PDA_STOCK_ROLES = {"KTA PDA Stock User", "Stock Manager", "System Manager"}

PDA_MODULE_REGISTRY = [
    {
        "key": "stock",
        "title": "Stock",
        "icon": "📦",
        "allowed_roles": PDA_STOCK_ROLES,
        "items": [
            {
                "key": "picking",
                "title": "Hat İkmal Toplama",
                "subtitle": "Açık ikmal emirlerini okutarak topla ve hatta aktar",
                "icon": "📦",
                "accent": "accent-blue",
                "allowed_roles": PDA_STOCK_ROLES,
            },
            {
                "key": "split",
                "title": "Koli Bölme ve Etiketleme",
                "subtitle": "Mevcut koliyi böl, yeni parti oluştur ve etiket bas",
                "icon": "✂️",
                "accent": "accent-amber",
                "allowed_roles": PDA_STOCK_ROLES,
            },
            {
                "key": "transfer",
                "title": "Depo Raf Transferi",
                "subtitle": "Koli ve hedef raf okutarak raflar arası tam kutu taşı",
                "icon": "🔄",
                "accent": "accent-green",
                "allowed_roles": PDA_STOCK_ROLES,
            },
            {
                "key": "lookup",
                "title": "Stok ve Etiket Sorgula",
                "subtitle": "Koli, raf veya ürün barkodu ile anlık bakiye görüntüle",
                "icon": "🔍",
                "accent": "accent-indigo",
                "allowed_roles": PDA_STOCK_ROLES,
            },
        ],
    }
]
```

- **`ALL_PDA_ROLES`:** `PDA_MODULE_REGISTRY` içindeki tüm kategori ve alt ekran `allowed_roles` kümelerinin dinamik birleşimidir. Genel ofis rolü `Stock User` bu kümede yer **almaz**.
- **`_get_authorized_menu_categories(user)`:** Kullanıcının etkin rollerini (`frappe.get_roles(user)`) kayıt defterindeki kategori ve ekranların `allowed_roles` kümeleriyle kesiştirir; yalnızca kullanıcının en az bir ekranına yetkili olduğu kategorileri ve o kategorideki yetkili alt ekranları döner.

### 5.2 Cihaz Yetkilendirme, Operatör Listesi ve PIN Akışı (`www/pda.py` & `pda_service.py`)

1. **Portal & Cihaz Kapısı (`erpnextkta/www/pda.py` & `_is_authorized_pda_user`):**
   - `www/pda.py` ve `pda_service._is_authorized_pda_user(user)` kullanıcının rollerinin `ALL_PDA_ROLES` ile kesişimini doğrular.
   - `KTA PDA Stock User` (`desk_access = 0`) rolündeki bir `Website User`, `/login?redirect-to=/pda` üzerinden giriş yaptığında `/pda` açılır ve `kta_pda_device` cihaz çerezi yazılır; aynı kullanıcı `/app` Desk'e gitmek istediğinde Frappe çekirdeği tarafından engellenir.
2. **Departmansız Operatör Listesi (`get_pda_operators()`):**
   - Sabit `PDA_DEPARTMENTS` filtresi tamamen kaldırılır.
   - `Employee.status == "Active"` ve `user_id` alanı dolu çalışanlar sorgulanır; bağlı `User.enabled == 1` ve rolleri `ALL_PDA_ROLES` ile kesişenler PIN ekranında listelenir.
   - İlgili yardımcı `_validate_pda_operator_record(employee)` kontrolü de departman şartı yerine `_is_authorized_pda_user(emp.user_id)` doğrular.
3. **Dinamik Menü Ağacı ve Yetki Koruması:**
   - `get_pda_boot_data()` yanıtına aktif kullanıcının rol kesişimine göre filtrelenmiş `menu_categories` listesi eklenir (`Guest` kilitli durumda `[]` döner).
   - `verify_pda_pin()` başarısı sonrasında yanıt içinde (ve `handleUnlocked` → `refreshBootState` çağrısında) güncel `menu_categories` ve `open_picking_count` alınarak operatörün göreceği menü anlık güncellenir.
   - Backend RPC uçları ekran bazlı yetki helper'ı (`_require_pda_screen_access("split" | "transfer" | "lookup")`) ile korunur.
   - **[Öneri / Varsayılan Karar]** Hat İkmal Desk & PDA Yetki Sınırı:
     - `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py:get_context`, mevcut `has_permission("Stock Entry", "read") or has_permission("KTA Line Replenishment Order", "read")` kontrolünü korurken `allowed_roles` kümesine `"KTA PDA Stock User"` rolünü ekler.
     - İkmal toplama RPC uçları (`get_open_replenishment_orders`, `get_replenishment_order_details`, `resolve_scanned_barcode`, `complete_line_replenishment_picking`), oturum açmış kullanıcıda `{"KTA PDA Stock User", "Stock User", "Stock Manager", "System Manager"}` rollerinden en az birini veya `KTA Line Replenishment Order` okuma/yazma iznini zorunlu kılar (`Guest` veya yetkisiz `Website User` istekleri reddedilir).
     - `override_item_source` ve `cancel_line_replenishment_order` mevcut Desk (`Manufacturing` / `Stock`) iş akışıyla uyumlu kalır; yeni PDA uçları (`pda_scan_box`, `pda_package_split`, `pda_material_transfer`, `pda_stock_lookup`) ise yalnızca `PDA_STOCK_ROLES` (`ALL_PDA_ROLES`) ile sınırlandırılır.

### 5.3 Kurulum, Geçiş ve `Employee` Rol Koruması (`setup.py`, Patch & `pda_user_guard.py`)

1. **`erpnextkta/kta_stock/setup.py` (`setup_pda_roles_and_permissions()`):**
   - `setup()` (ve `hooks.py:after_migrate`) akışına `setup_pda_roles_and_permissions()` eklenir.
   - **[Öneri / Varsayılan Karar]** `Role` tablosunda `"KTA PDA Stock User"` yoksa oluşturulur, varsa güncellenir ve `desk_access = 0` yanında `home_page = "/pda"` ayarlanır. Böylece saf `Website User` bir operatör doğrudan `/login` ekranından (`?redirect-to=/pda` parametresi olmadan bile) giriş yaptığında `/me` yerine doğrudan `/pda` ekranına yönlendirilir; `/app` isteği ise Frappe çekirdeğinin standart `403` Desk engeliyle reddedilmeye devam eder.
   - **[Öneri / Varsayılan Karar]** Bölüm 3'te listelenen 8 DocType (`Stock Entry`, `Serial and Batch Bundle`, `Batch`, `Stock Ledger Entry`, `Item`, `Warehouse`, `KTA Stock Label`, `KTA Line Replenishment Order`) için `Custom DocPerm` kayıtlarını `frappe.permissions.add_permission` / `update_permission_property` veya doğrudan idempotent kontrolle tanımlar (`permlevel = 0`, mevcut çekirdek diğer rollerin izinlerine dokunmaz).
   - **[Öneri / Varsayılan Karar]** **Zebra Yazıcı İzni Eşitlemesi (`KTA Printer Permission`):** `ZebraPrinterManager._user_can_print()` (`kta_system_utils`) bir yazıcıda `KTA Printer Permission` satırları varsa kullanıcının rolünü denetler (`in_test` modunda `MockZebraPrinter` döndüğü için testlerde gizlenir). `setup_pda_roles_and_permissions()` (ve migration patch çalıştığında), `KTA Printer Permission` tablosunda `role = "Stock User"` ve `can_print = 1` kaydı bulunan her yazıcı için idempotent olarak `role = "KTA PDA Stock User"`, `can_print = 1` satırı ekler; hiç `KTA Printer Permission` kaydı bulunmayan herkese açık yazıcılara ise dokunmaz.
2. **Migration Patch (`erpnextkta/patches/v4_4/setup_pda_stock_role_and_backfill.py` + `erpnextkta/patches.txt`):**
   - Önce `setup_pda_roles_and_permissions()` çalıştırır (rol, `home_page`, `Custom DocPerm` ve `KTA Printer Permission` eşitlemesi dahil).
   - **[Öneri / Varsayılan Karar]** Geçiş sırasında mevcut saha operasyonlarının durmaması için o an `Employee` kaydı `status = "Active"` ve `department IN ("AMBAR - KTA", "Sevk")` olan, bağlı `User.enabled = 1` kullanıcısında `Stock User` veya `Stock Manager` bulunan hesaplara tek seferlik tahribatsız biçimde `KTA PDA Stock User` rolünü ekler; mevcut Desk rollerini silmez (yönetici dilediği operatörden `Stock User` / `Employee` rollerini kaldırarak hesabı saf `Website User` durumuna çekebilir).
3. **`Employee.on_update()` Otomatik `"Employee"` Rolü Koruması (`doc_events` & `pda_user_guard.py`):**
   - `override_doctype_class["Employee"]` yerine `erpnextkta/kta_stock/pda_user_guard.py` + `erpnextkta/hooks.py` (`doc_events`) kullanılır; böylece `hrms.overrides.employee_master.EmployeeMaster` sınıfı hiç ezilmez.
   - `Employee.before_save`: `mark_pure_pda_website_user_before_employee_save` — bağlı `User` en az bir `desk_access = 0` PDA rolüne (`KTA PDA *`) sahipse ve üzerinde hiç `desk_access = 1` rolü yoksa (`not has_desk_role`), `frappe.local.flags._kta_preserve_pda_website_users` kümesine eklenir.
   - `User.before_validate`: `strip_auto_employee_role_for_pure_pda_user` — kullanıcı bu geçici kümedeyse (`Employee.update_user()` içindeki `user.save()` sırasında `User.set_system_user()` hesaplanmadan hemen önce) otomatik eklenen `"Employee"` rol satırını bellekten çıkarır ve işareti temizler; böylece ad/soyad/fotoğraf senkronizasyonu sürerken kullanıcı `Website User` kalır. Yönetici `User` formundan bilerek `"Employee"` eklerse dokunulmaz.
   - `Employee.on_update`: `clear_pure_pda_website_user_flag_after_employee_save` — güvenlik amaçlı bayrağı temizler.

### 5.4 Frontend Navigasyon ve Çekmece Mimarisi (`erpnextkta/public/pda-hub/`)

1. **Üst Bar (`PdaHubApp.vue`):**
   - Sol tarafta tüm görünümlerde (ana menü, kategori içi, alt ekran) her zaman erişilebilir **`☰ Menü`** butonu (`data-testid="topbar-menu-btn"`) yer alır.
   - Yanında bağlamsal konum başlığı (breadcrumb) gösterilir:
     - Çoklu kategori seçim ekranındayken: `KTA PDA`
     - Tek veya seçili kategori içinde (`Stock` menüsü): `Stock`
     - Alt ekrandayken: `Stock › Koli Bölme` (kategori + aktif alt ekran adı)
   - Kullanıcının birden fazla yetkili kategorisi varsa üst bar veya alt ekrandan ana modül/kategori seviyesine geri dönüş desteklenir.
2. **Yan Çekmece (`PdaMenuDrawer.vue`, `<Teleport to="body">`):**
   - Sol kenardan açılan dokunmatik slide-over çekmece; Escape tuşu ve arka plan tıklamasıyla kapanır; Light & Dark tema desteği sunar.
   - Yetkili tüm kategorileri (`📦 Stock`, ileride eklenecek diğer modüller) başlık olarak, altındaki yetkili ekranları ise dokunmatik menü öğesi olarak listeler (`picking` öğesinin yanında canlı `openPickingCount` rozeti görünür).
   - Herhangi bir alt ekran öğesine dokunulduğunda doğrudan o ekrana geçiş yapılır ve çekmece kapanır. Birden fazla kategori yetkisi varsa çekmecenin üstünde `Ana Modüller` bağlantısı yer alır.
3. **Akıllı Açılış (`LauncherHome.vue`):**
   - Giriş/kilit açma sonrası `menu_categories` dizisine göre akıllı yönlendirme uygular:
     - `menu_categories.length > 1` ve henüz kategori seçilmediyse: Ana kategori kartlarını gösterir (tıklanınca o kategorinin alt ekranlarını açar).
     - `menu_categories.length == 1`: Bugünkü durumda yalnızca `Stock` yetkisi olduğundan ekstra kategori tıklaması gerektirmeden doğrudan o tek kategorinin alt ekran kartlarını gösterir.
     - `menu_categories.length == 0`: Kullanıcıya yetkili PDA modülü tanımlanmadığını belirten net bilgilendirme kartı sunar.

---

## 6. Uygulayıcıya Bırakılan Detaylar (Left to the Builder)

* Çekmece açılış/kapanış animasyonu, dokunmatik hedef yükseklikleri, ikon/rozet boşlukları ve `360px`–`480px` mobil CSS ayarları.
* `setup_pda_roles_and_permissions()` içindeki `Custom DocPerm` oluşturucu yardımcı fonksiyonların modüler parçalanması.
* Frappe backend (`test_pda_role_setup.py`, `test_pda_service.py`, `test_pda_portal.py` — saf `Website User` uçtan uca izin testleri, `pda_user_guard` `doc_events` koruması ve `KTA Printer Permission` rol eşitleme testleri dahil) ve Vitest (`PinLockAndLauncher.spec.ts`, `PdaHubApp.spec.ts`) test fixture isimlendirmeleri.
* Uygulama aşamasında `PDA_MODULE_REGISTRY` başlıkları (`Stock`, `Ana Modüller`, `Yetkili Modül Bulunamadı` vb.) ile yeni hata mesajlarının TR/EN/DE çevirilerinin `erpnextkta/translations/{tr,en,de}.csv` dosyalarına append-only olarak eklenmesi ve `erpnextkta/www/docs/stok-lojistik.html` / `docs/kta_stok_lojistik_kilavuzu.md` güncellemesi.
