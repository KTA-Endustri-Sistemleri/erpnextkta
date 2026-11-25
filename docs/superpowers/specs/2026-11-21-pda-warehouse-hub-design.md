# KTA PDA Depo Merkezi (Unified PDA Warehouse Hub) Tasarım Dokümanı

**Tarih:** 2026-11-21  
**Durum:** Implemented — Kalite Kapısı Doğrulandı (`/pda` PWA, `pda_service`, `pda-hub` SPA & Dokümantasyon)  
**Yazar:** Coordinator (Tech Lead) & Depo Operasyonları Ekibi  
**Hedef URL:** `https://site.kta-endustri.com.tr/pda`  
**Mimari Türü:** Frappe Web Portal Bağımsız PWA (HRMS Benzeri) + Vue 3 SPA  

---

## 1. Amaç ve İhtiyaç (Intent & The Why)

Fabrika sahasındaki depo operatörleri, el terminallerinde (PDA - Zebra, Honeywell vb.) dağınık Frappe Desk sayfaları (`/app/...`) arasında geçiş yaparken ciddi zorluklar yaşamaktadır. Desk'in getirdiği 15-20 MB'lık ağır arayüz, üst navbar, bildirimler ve menüler küçük PDA ekranlarında hem yavaş çalışmakta hem de operatörün yanlış yerlere tıklamasına yol açmaktadır.

Ayrıca halihazırda devreye alınmış olan Hat İkmal Toplama (Picking) dışında; depoda günlük olarak yürütülen:
1. **Koli/Paket Bölme (Package Split)** ve Zebra'dan anında yeni standart `7+4` etiket basımı,
2. **Serbest Raf/Lokasyon Transferi ve Rafa Yerleştirme (Putaway / Material Transfer)**,
3. **Hızlı Barkod / Stok ve Raf Sorgulama (Quick Lookup)**

gibi temel hareketler için mobil uyumlu, dokunmatik ve tek bir çatı altında çalışan bir el terminali deneyimine ihtiyaç duyulmaktadır.

Bu proje; Desk yükünden tamamen arındırılmış, şimşek hızında (~300 ms) açılan, paylaşımlı cihazlarda gerçek Frappe kullanıcı oturumu geçişini saniyeler içinde çözen ve 4 ana depo operasyonunu tek ekranda toplayan **bağımsız bir mobil web uygulaması (PWA)** geliştirmeyi hedefler.

---

## 2. Hedefler, Kapsam Dışı ve Karşı-Hedefler

### 2.1 Hedefler (Goals)
* **Bağımsız Web Uygulaması (`/pda`):** Frappe Desk'ten tamamen bağımsız, `erpnextkta/www/pda.html` üzerinden sunulan, PWA (Progressive Web App) manifestine sahip tam ekran mobil portal.
* **Paylaşımlı Cihaz & Yerleşik Oturumlu PIN Doğrulama:** Yetkilendirilmiş cihazlarda `AMBAR - KTA` ve `Sevk` personellerinin listelendiği dokunmatik seçim + 4 haneli şahsi PIN (`Employee.custom_pda_pin`) ile gerçek Frappe oturum geçişi (`LoginManager.login_as`).
* **4 Temel Depo Modülü:**
  * **Modül 1 (Hat İkmal / Toplama):** Açık replenishment emirlerine göre barkod okutarak hat ikmal toplama (mevcut `line-replenishment-pda` bileşenleri bu çatıya entegre edilir).
  * **Modül 2 (Koli Bölme & Etiketleme):** Kutu barkodu okutulur $\rightarrow$ ayrılacak veya kırılacak adetler girilir $\rightarrow$ `Package Split` fişi kesilip `KTA User Zebra Printers` mantığıyla `frappe.session.user` üzerinden yeni standart `7+4` etiketler basılır.
  * **Modül 3 (Serbest Raf Transferi / Yerleştirme):** Koli barkodu okutulur $\rightarrow$ hedef raf barkodu okutulur $\rightarrow$ tam kutu `Material Transfer` Stock Entry tek tıkla arka planda submit edilir.
  * **Modül 4 (Hızlı Barkod / Stok Sorgu):** Kutu, parti veya raf okutulduğunda anlık stok bakiyesi, parti ömrü ve lokasyon gösterilir.
* **Sesli Geri Bildirim & Donanım Entegrasyonu:** Lazer barkod okuyucu (`Enter` dinleyici) ve başarı/hata ses tonları (`beep/error`).
* **Otomatik Güvenlik Kilidi:** Sağ üstte her zaman görünür `[Devret / Çıkış ↩]` butonu ve 5 dakikalık (`300s`) hareketsizlik (inactivity) zaman aşımı kilidi.

### 2.2 Kapsam Dışı (Non-Goals)
* Masaüstü ERPNext Desk sayfalarını veya standart listeleri kaldırmak.
* `Stock Entry` veya `KTA Line Replenishment Order` üzerine ayrıca `custom_operator` alanı eklemek (gerçek oturum geçişi sayesinde standart `owner` ve `modified_by` denetim izi doğal olarak kaydedilir).
* Bu aşamada zorunlu bir iş emrine/transfer emrine bağlı liste tabanlı raf transferi (operatörler serbest okutma yapacaktır; ancak altyapı ileride liste tabanlı transfere hazır esneklikte kurulacaktır).
* Yaka kartı barkodu okutma (KTA personellerinin yaka kartlarında barkod bulunmadığı teyit edildiği için dokunmatik liste + PIN yöntemi kullanılacaktır).

### 2.3 Karşı-Hedefler (Anti-Goals)
* Operatörü asla standart Frappe formlarına veya Desk navigasyonuna yönlendirmemek.
* Modüller arasında gezinirken tarayıcıyı veya Desk sayfasını yeniden yüklememek (tüm geçişler SPA içinde anlık 0 ms olmalıdır).
* Kutu bütünlüğünü bozacak şekilde tek partiyi bölmeden iki farklı rafa dağıtmak (1 Kutu = 1 Parti kuralı tavizsiz korunur).
* Yetkisiz dış tarayıcılardan `/pda` veya PIN doğrulama servislerine anonim erişim/PIN taraması yapılmasına izin vermek.

---

## 3. Kısıtlar ve Teknik Standartlar

* **Platform:** Frappe v15, Linux, Python 3.12.
* **Frontend:** Vue 3 + TypeScript, esbuild ile derlenen bundle (`erpnextkta/public/pda-hub/`), `bench build --app erpnextkta --production`.
* **Portal Sunumu:** `erpnextkta/www/pda.html` ve `erpnextkta/www/pda.py` (Desk JS/CSS bağımlılığı sıfır).
* **Güvenlik & Yetkilendirme:** Frappe session cookie, `csrf_token`, HMAC-SHA256 imzalı `kta_pda_device` cihaz çerezi ve `ALLOWED_PDA_ROLES = {"Stock User", "Stock Manager", "System Manager"}` rol kontrolü.
* **Yazıcı Entegrasyonu:** `kta_system_utils` altındaki `ZebraPrinterManager.get_printer_for_user()` altyapısı ve `KTA User Zebra Printers` tablosu (doğrudan `frappe.session.user` üzerinden).
* **Kod Standartları:** `.agents/AGENTS.md` kuralları, ruff lint/format, conventional commits (satır uzunluğu $\le 100$).

---

## 4. Değerlendirilen Yaklaşımlar ve Karar

| Yaklaşım | Açıklama | Karar | Neden? |
| :--- | :--- | :--- | :--- |
| **1. Desk İçi Ayrı Sayfalar** | Her işlem için ayrı Frappe Page (`/app/...`) | ❌ Reddedildi | PDA donanımında sayfa geçişleri çok yavaş, Desk yükü ağır, barkod odağı kayboluyor. |
| **2. Tek Sekmeli Desk Sayfası** | Mevcut picking sayfasını sekmeli hale getirmek | ❌ Reddedildi | Desk yükü devam ediyor, sayfa adı semantik olarak yanıltıcı, yetki dağılımı karışıyor. |
| **3. Bağımsız Portal / PWA (`/pda`)** | HRMS benzeri bağımsız `www/pda.html` + Vue 3 SPA | ✅ **SEÇİLDİ** | Şimşek hızında açılış (~300ms), sıfır Desk yükü, tam ekran PWA, paylaşımlı cihaz ve tek çatı operasyon için mükemmel uyum. |

---

## 5. Kararlaştırılan Detaylı Tasarım ve Mimari Kararlar

### 5.1 Portal & PWA Yapısı (`www/pda`)
* **URL:** `/pda` (örn: `https://old.kta-endustri.com.tr/pda`)
* **HTML Kabuğu (`erpnextkta/www/pda.html`):**
  * `viewport-fit=cover, user-scalable=no, initial-scale=1.0` mobil meta etiketleri.
  * PWA webmanifest bağlantısı (`/assets/erpnextkta/pda-hub/manifest.webmanifest`).
  * Desk scriptleri yüklenmez; yalnızca `pda-hub.bundle` varlıkları (`include_style`, `include_script`), `csrf_token`, `build_version` ve `frappe.boot` nesnesi enjekte edilir.
* **Python Controller (`erpnextkta/www/pda.py`):**
  * Cihaz veya kullanıcı oturumunu doğrular; hem `Guest` hem de geçerli `kta_pda_device` çerezi yoksa `/login?redirect-to=/pda` sayfasına yönlendirir.
  * Oturumu açık kullanıcı `ALLOWED_PDA_ROLES` yetkisine sahipse 30 gün ömürlü HMAC imzalı `kta_pda_device` çerezini yazar/yeniler.
  * Aktif ambar operatörlerini, kullanıcı oturum durumunu ve çevirileri `pda_boot_json` nesnesine ekler.

### 5.2 Operatör Kimlik, PIN ve Yerleşik Oturum Yönetimi
* **Şema Değişikliği (Minimal):**
  * Yalnızca `Employee` DocType'ına `custom_pda_pin` (`Password`, 4 haneli sayısal PIN, `attendance_device_id` sonrasına yerleşik) alanı eklenir.
  * `Stock Entry` veya `KTA Line Replenishment Order` DocType'larına `custom_operator` eklenmez.
* **Cihaz Yetkilendirme Çerezi (`kta_pda_device`):**
  * Yetkili (`Stock User`, `Stock Manager`, `System Manager`) bir kullanıcı `/pda` sayfasını ilk kez açtığında sunucu, HMAC-SHA256 ile imzalanmış HTTP-only bir `kta_pda_device` çerezi (30 gün ömürlü) tanımlar.
  * Geçerli `kta_pda_device` çerezi taşımayan `Guest` istekleri `/pda` üzerinde `/login?redirect-to=/pda` adresine yönlendirilir; `get_pda_boot_data` ve `verify_pda_pin` RPC çağrılarında `frappe.PermissionError` ile reddedilir. Böylece dış ağdan veya yetkisiz tarayıcıdan PIN denemesi yapılması engellenir.
* **PIN Doğrulama = Gerçek Frappe Oturumu (`LoginManager.login_as`):**
  * Listede yalnızca `department IN ('AMBAR - KTA', 'Sevk') AND status = 'Active'` koşulunu sağlayan, aktif ve stok rolüne (`ALLOWED_PDA_ROLES`) sahip `Employee.user_id` eşleşmesi bulunan çalışanlar listelenir.
  * Operatör 4 haneli PIN'i girdiğinde `verify_pda_pin(employee, pin)` çalışır:
    * Brute-force koruması: `frappe.cache()` üzerinde `pda_pin_fail:{employee}` anahtarı ile 5 dakika içinde en fazla 5 hatalı denemeye izin verilir; eşik aşılırsa hesap geçici olarak kilitlenir.
    * Şifre karşılaştırması `hmac.compare_digest` ile sabit zamanlı yapılır.
    * Doğrulama başarılı olduğunda `frappe.local.login_manager.login_as(employee.user_id)` ile gerçek Frappe oturumu operatörün kendi hesabına geçirilir ve istemciye yeni `csrf_token` ile kullanıcı profili döndürülür.
* **Doğal Denetim İzi ve Yazıcı Çözümlemesi:**
  * Gerçek kullanıcı oturumu aktif olduğu için kesilen her `Stock Entry`, `KTA Stock Label` ve `KTA Line Replenishment Order` belgesinde standart `owner` ve `modified_by` alanlarına operatörün kendi kullanıcısı otomatik işlenir.
  * `ZebraPrinterManager.get_printer_for_user()` herhangi bir ek parametreye gerek duymadan doğrudan `frappe.session.user` üzerinden ilgili kullanıcının `KTA User Zebra Printers` kaydını çözümler.
* **Devret ve 5 Dakika Hareketsizlik Kilidi:**
  * Operatör sağ üstteki `[Devret / Çıkış ↩]` butonuna bastığında veya 5 dakika (`300s`) boyunca işlem yapmadığında `pda_handover_logout()` çağrılır; Frappe kullanıcı oturumu sonlandırılır (`logout()`), ancak `kta_pda_device` cihaz çerezi korunur ve yeni `csrf_token` dönülür. Cihaz anında PIN kilit ekranına döner.

### 5.3 Zebra Yazıcı Çözümleme Mantığı (`KTA User Zebra Printers`)
* Koli bölme ve etiket basımında hedef yazıcı KTA altyapısındaki mevcut `KTA User Zebra Printers` tablosundan otomatik çözümlenir:
  1. PIN doğrulaması `frappe.session.user` değerini doğrudan operatörün kendi Frappe kullanıcısına geçirdiği için `LabelPrinter` ve `KTAStockEntry` kancaları standart akışla `ZebraPrinterManager.get_printer_for_user()` çağırır.
  2. Kullanıcının birincil yazıcısı (`printer`) ayaktaysa oraya gönderilir; kapalıysa `fallback_printer` devreye girer.
  3. **Sonuç:** Ekranda manuel yazıcı seçicisine veya ek yazıcı parametresine ihtiyaç yoktur.

### 5.4 Raf Barkodu Çözümleme Kuralı
* Sahada okutulan raf barkodları (`170-W1F-12-02` veya `170-W1F-12-02 - KTA`):
  * Backend `resolve_warehouse_barcode(barcode, company=None)` servisi önce tam adla (`name = barcode`), bulunamazsa `warehouse_name = barcode`, yine bulunamazsa şirket soneki ekleyerek (`name = f"{barcode} - {company_abbr}"`) sorgular; grup depoları (`is_group = 1`) reddeder.
  * Hem şirket ekli hem de eksiz tüm fiziksel raf etiketleri %100 sorunsuz çözümlenir.

### 5.5 Modül 3: Serbest Raf Transferinde Kutu Bütünlüğü Kuralı
* KTA hiyerarşik parti standardı (**1 Kutu = 1 Parti/Etiket**) gereği, raf transferi **Tam Kutu / Parti Bütünlüğü (Full Box Transfer)** esasına dayanır.
* Operatör bir raftan diğer rafa kutu taşırken transfer miktarı kaynak depodaki parti bakiyesinin tamamıdır (`qty` opsiyonel olarak doğrulama için gönderilebilir ve tam bakiyeye eşit değilse reddedilir). Bir kutunun yarısını rafta bırakıp yarısını başka rafa taşımak istiyorsa, önce **Modül 2: Koli Bölme** ekranını kullanarak yeni bir alt kutu/etiket türetmelidir.

### 5.6 Modül 2: Koli Bölme Esnekliği ve Tekil Yazdırma Kuralı
* Operatör kutuyu bölmek istediğinde iki modu da kullanabilir:
  1. **Kısmi Ayırma (Hızlı):** 1.000 adetlik kutudan 200 adet ayırmak için sadece `200` yazar. Kalan 800 mevcut partide kalır, ayrılan 200 için tek bir yeni `7+4` etiket basılır.
  2. **Tam Kırılım (Çoklu Kutu):** `500, 300, 200` şeklinde çoklu kutu adetleri girilirse, sistem her kutu için yeni etiketler basar.
* **Çift Yazdırmayı Önleme Kuralı:** `Package Split` tipindeki `Stock Entry` onaylandığında `KTAStockEntry.on_submit()` yeni oluşan hedef kutuların etiketlerini zaten otomatik olarak basmaktadır. Bu nedenle `pda_package_split` hedef kutular için tekrar yazdırma kuyruğu açmaz; yalnızca kaynak kutuda kalan bakiye (`remaining_qty > 0`) varsa ve `reprint_source_label == 1` ise güncellenmiş kaynak kutu etiketini tekil olarak yeniden yazdırma kuyruğuna ekler.

### 5.7 Backend API Endpoint'leri (`erpnextkta/kta_stock/services/pda_service.py`)
1. `get_pda_boot_data()`: Yetkili cihaz doğrulaması sonrası aktif operatör listesini, şirket bilgisini ve mevcut oturum durumunu döner.
2. `verify_pda_pin(employee: str, pin: str)`: Brute-force korumalı 4 haneli PIN doğrulaması sonrası `login_as(employee.user_id)` ile oturumu geçirir ve taze `csrf_token` döner.
3. `pda_handover_logout()`: Mevcut kullanıcı oturumunu kapatır, `kta_pda_device` çerezini korur ve yeni `csrf_token` döner.
4. `pda_scan_box(barcode: str)`: Kutu barkodundan ürün, parti, depo bakiyeleri ve etiket bilgilerini döner.
5. `pda_package_split(item_code: str, source_warehouse: str, source_batch: str, split_qtys: list[float] | str, reprint_source_label: int = 1)`: `create_package_split_repack` üzerinden koli böler; hedef etiketler `on_submit` ile basılırken kalan kaynak etiketi isteğe bağlı yeniler.
6. `pda_material_transfer(item_code: str, batch_no: str, source_warehouse: str, target_warehouse_barcode: str, qty: float | None = None)`: Tam kutu `Material Transfer` Stock Entry oluşturup submit eder ve etiket hedef deposunu günceller.
7. `pda_stock_lookup(barcode: str)`: Kutu, raf veya ürün barkodu için salt-okunur anlık stok detayını döner.

---

## 6. Geliştiriciye Bırakılan Detaylar (What's Left to the Builder)

* Keypad dokunmatik butonlarının pixel/rem boyutları ve mobil renk paleti uyumu.
* Başarı/hata ses tonlarının tam frekans değerleri (`playBeep(success=true/false)`).
* Çeviri sözlüklerinin (TR/EN/DE) CSV dosyalarına eklenmesi.
* Test süitlerinin `test_pda_service.py`, `test_pda_portal.py` ve Vitest altında uçtan uca doğrulanması.
