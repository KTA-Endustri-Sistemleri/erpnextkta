# PDA Yalnızca Barkod Okuyucu (`scanOnly`) Zorunluluğu Tasarımı

**Tarih:** 2026-11-26
**Durum:** Tasarım Onaylandı — Faz 0 Donanım Tanısı & Uygulama Bekliyor
**Boyut:** Orta Değişiklik (Backend Politika + RBAC + Paylaşımlı Frontend Bileşeni)
**Kapsam:** `KTA Warehouse Settings` (planlanan ayar DocType), `erpnextkta/kta_stock/services/pda_service.py`, `erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py`, `erpnextkta/public/line-replenishment-pda/components/BarcodeScannerBar.vue` ve 6 PDA ekranı, Vitest birim testleri, `/docs/` & `translations/`

---

## 1. Amaç ve Gerekçe

Mevcut PDA barkod giriş alanı (`#pda-barcode-input`), herhangi bir standart metin kutusu gibi hem fiziksel el terminali okuyucusundan gelen veriyi hem de sanal klavyeden elle yazılan veya panodan kopyala-yapıştır (`Ctrl+V` / uzun basıp `Yapıştır`) ile aktarılan metinleri kabul etmektedir.

Bu durum aşağıdaki operasyonel ve stok bütünlüğü risklerini doğurmaktadır:
- Operatörün fiziksel olarak rafa gitmeden masaüstü listeden, WhatsApp/not ekranından veya ekran görüntüsünden okuduğu ürün/parti kodunu kopyalayıp yapıştırması veya elle tuşlaması.
- Yanlış raf veya yanlış parti kolisinin fiilen okutulmadan sistemde toplanmış/transfer edilmiş görünmesi.

Bu tasarımın amacı; stok hareketi üreten PDA ekranlarında normal operatörlerin elle yazmasını ve kopyala-yapıştır yapmasını teknik olarak engelleyerek, kullanıcının fiziksel olarak rafa gidip koli/raf etiketini el terminalinin donanım barkod okuyucusuyla okuttuğunu doğrulamaktır.

---

## 2. Donanım ve Teknik Bağlam

- **Saha Donanımı:** Depoda üzerinde dahili donanım barkod okuyucusu bulunan Android tabanlı **HYATTA** el terminalleri kullanılmaktadır.
- **Tarayıcı–Okuyucu Sınırı:** Web tarayıcıları Android cihaz üzerindeki dahili donanım okuyucuyu doğrudan USB/Serial cihazı olarak tanıyamaz. Donanım okuyucu, cihazın *Scanner Settings* yapılandırmasına bağlı olarak tarayıcıya iki farklı biçimde veri gönderir:
  1. **HID Klavye Emülasyonu (Keystroke Wedge):** Çok hızlı art arda `keydown` / `keypress` / `keyup` ve sonunda `Enter` veya `Tab` tuşu gönderir.
  2. **Metin Enjeksiyonu (Clipboard / Intent / CommitText):** Tüm barkod metnini tek seferde input alanına enjekte eder (tarayıcı tarafında `beforeinput` / `input` / `paste` veya tek adımda değer değişimi olarak görünebilir).
- **Etkilenen Paylaşımlı Bileşen:** [BarcodeScannerBar.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/line-replenishment-pda/components/BarcodeScannerBar.vue) (`#pda-barcode-input`) şu an toplam **6 PDA ekranında** ortak olarak kullanılmaktadır:
  1. [PickingModuleView.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/pda-hub/views/PickingModuleView.vue) (`/pda` Hat İkmal Toplama)
  2. [PdaApp.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/line-replenishment-pda/PdaApp.vue) (Legacy Desk `/app/line-replenishment-picking`)
  3. [MaterialTransferView.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/pda-hub/views/MaterialTransferView.vue) (Depo Raf Transferi)
  4. [PackageSplitView.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/pda-hub/views/PackageSplitView.vue) (Koli Bölme)
  5. [PackageMergeView.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/pda-hub/views/PackageMergeView.vue) (Koli Birleştirme)
  6. [StockLookupView.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/pda-hub/views/StockLookupView.vue) (Hızlı Stok Sorgu)

---

## 3. Hedefler, Kapsam Dışı ve Anti-Hedefler

### Hedefler
- **Stok Hareketi Ekranlarında Zorunlu Okutma:** Stok hareketi üreten 5 ekranda (`PickingModuleView`, `PdaApp`, `MaterialTransferView`, `PackageSplitView`, `PackageMergeView`) normal operatörler (`KTA PDA Stock User`) için elle yazma ve kopyala-yapıştır engellenecektir.
- **`StockLookupView` İstisnası:** Yalnızca bilgi sorgulama yapan [StockLookupView.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/pda-hub/views/StockLookupView.vue) ekranında manuel ürün/parti/raf kodu arama özelliği açık kalacaktır (`scanOnly = false`).
- **Rol Bazlı İstisna (`can_manual_barcode_entry`):** Hat ikmal toplamada mevcut `Atla (Skip)` yetki modeline (`_SKIP_ALLOWED_ROLES`) paralel biçimde rol bazlı **`can_manual_barcode_entry`** izni tanımlanacaktır. **`KTA PDA Supervisor`**, **`Stock Manager`** ve **`System Manager`** rollerine sahip yetkililer (ve test/destek senaryoları) gerektiğinde manuel barkod girişi yapabilecektir.

### Kapsam Dışı (Ayrı Başlık)
- **Yırtık / Silik Etiket Yeniden Basım Akışı:** Fiziksel etiketi yırtılmış, ıslanmış veya okunamaz hale gelmiş koliler için normal operatörlere özel "etiket yeniden bas / doğrula" akışı bu tasarımın kapsamı dışındadır; ayrı bir tasarım dokümanında ele alınacaktır.

### Anti-Hedefler
- **Cuma Saha Testinde Okuyucu Blokajı Riski:** HYATTA cihazının varsayılan donanım okuyucu modunu doğrulamadan katı kurallar dayatarak Cuma saha testinde gerçek barkod okutmayı yanlışlıkla kilitlemek/bloklamak **kesinlikle kabul edilmez**.

---

## 4. Değerlendirilen Yaklaşımlar ve Seçilen Yol

| Yaklaşım | Özet | Avantajlar | Dezavantajlar | Karar |
|---|---|---|---|---|
| **Yaklaşım 1 — Donanım Prefix / Suffix Doğrulaması ("Cihaz İmzası")** | HYATTA *Scanner Settings* üzerinden okuyucuya gizli bir ön ek/son ek (prefix/suffix) tanımlanıp yalnızca o imzayı taşıyan girişlerin kabul edilmesi. | En güvenli yöntem; HID veya metin enjeksiyonu modundan bağımsız çalışır. | Her HYATTA cihazında bir defalık servis/okuyucu ayarı gerektirir; ayarsız yeni cihazda doğrudan çalışmaz. | İsteğe Bağlı Üst Katman |
| **Yaklaşım 2 — Saf Tarayıcı Koruması (`inputmode="none"` + `paste`/`drop` Engeli + Hız Ölçümü)** | Tarayıcıda sanal klavyeyi kapatıp pano yapıştırmasını engellemek ve karakterler arası süreyi (ms) ölçerek yavaş insan yazımını reddetmek. | Sıfır cihaz ayarı; mevcut cihazlarla hemen devreye alınabilir. | Cihaz metin enjeksiyonu/clipboard modunda çalışıyorsa gerçek donanım okuyucusunu da engelleyebilir. | Tek Başına Riskli |
| **Yaklaşım 3 — Hibrit ve Ayarlanabilir Yapı (Seçilen)** | Önce HYATTA üzerinde 30 saniyelik donanım tanı testi (**Faz 0**) yapılarak gerçek browser event ve hız profili ölçülür; ardından `KTA Warehouse Settings` + `can_manual_barcode_entry` RBAC üzerinden varsayılan tarayıcı koruması (`inputmode="none"` + `paste`/`drop` engeli + karakter hızı eşiği) çalıştırılır. HYATTA prefix destekliyorsa kod değişikliği olmadan ayardan gizli prefix zorunluluğuna geçilebilir. | Sıfır kod değişikliğiyle saf korumadan donanım imzasına geçiş esnekliği; Faz 0 sayesinde Cuma testinde blokaj riskini sıfırlar. | Kısa bir Faz 0 ölçümü ve ayar şeması gerektirir. | **Seçildi** |

---

## 5. Mimari Taslak ve Uygulama Fazları

### Faz 0 — 30 sn Donanım Tanı Testi (Spike)
Uygulama koduna geçmeden önce gerçek **HYATTA** el terminalinde tarayıcı içinde barkod okutularak şu 4 veri doğrulanır:
1. **Event Sırası:** Okutma sırasında tarayıcının ürettiği gerçek event sırası (`keydown` → `input` akışı mı, yoksa `beforeinput` / `paste` / toplu `input` enjeksiyonu mu?).
2. **Karakter Arası Süre (ms):** HID modundaysa ardışık karakterler arası ortalama ve tepe gecikme süresi (`ms`).
3. **Sonlandırma Tuşu:** Barkod sonunda gönderilen tuş (`Enter`, `Tab` veya hiçbiri).
4. **Prefix / Suffix Desteği:** HYATTA *Scanner Settings* uygulamasında özel Prefix/Suffix tanımlanıp tanımlanamadığı.

### Faz 1 — Backend Politikası & RBAC
- **`KTA Warehouse Settings` Alanları:**
  - `pda_enforce_scanner_only` (`Check`): PDA stok hareketi ekranlarında yalnızca okuyucu politikasını açar/kapatır (acil saha geri alma anahtarı).
  - `pda_scanner_max_char_interval_ms` (`Int`): Karakter arası izin verilen azami süre eşiği (ms); Faz 0 ölçümüne göre varsayılan belirlenir.
  - `pda_scanner_required_prefix` (`Data` / `Password`, opsiyonel): Doluysa tüm okutmaların bu gizli önek ile başlamasını zorunlu kılar; doğrulama sonrası önek backend'e gönderilmeden önce temizlenir.
- **`pda_service.py` & Sayfa Bağlamı Entegrasyonu:**
  - [pda_service.py](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_stock/services/pda_service.py) içinde `get_pda_boot_data()` ve `verify_pda_pin()` yanıtlarına iki alan eklenir:
    - `can_manual_barcode_entry` (`bool`): Kullanıcının rolleri `{"KTA PDA Supervisor", "Stock Manager", "System Manager"}` kümesiyle kesişiyorsa `True`.
    - `scanner_policy` (`dict`): `{ enforce_scanner_only, max_char_interval_ms, has_required_prefix / required_prefix }` yapılandırması.
  - Legacy `/app/line-replenishment-picking` sayfası için [line_replenishment_picking.py](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/kta_stock/page/line_replenishment_picking/line_replenishment_picking.py) bağlamında da (`can_skip_items` ile paralel biçimde) `can_manual_barcode_entry` ve `scanner_policy` değerleri `PdaApp.vue` başlangıç verisine aktarılır.

### Faz 2 — Frontend `BarcodeScannerBar.vue` ve 6 Ekran Entegrasyonu
- **Yeni Prop'lar ([BarcodeScannerBar.vue](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/line-replenishment-pda/components/BarcodeScannerBar.vue)):**
  - `scanOnly?: boolean` — `StockLookupView.vue` için `false`; diğer 5 ekran (`PickingModuleView`, `PdaApp`, `MaterialTransferView`, `PackageSplitView`, `PackageMergeView`) için `scanner_policy.enforce_scanner_only && !can_manual_barcode_entry` koşuluyla `true`.
  - `scannerPolicy?: ScannerPolicy` — zaman aşımı eşiği (`max_char_interval_ms`) ve opsiyonel önek (`required_prefix`) bilgisini taşır.
- **İstemci Tarafı Koruma Mekanizması (`scanOnly === true` iken):**
  - `#pda-barcode-input` üzerinde `inputmode="none"` uygulanır; operatör dokunduğunda Android sanal klavye açılmaz, fiziksel odak korunur.
  - `paste`, `drop` ve `contextmenu` olayları engellenir (`preventDefault()`).
  - **Hız / Enjeksiyon Denetimi & Prefix Doğrulaması:**
    - Faz 0'da HID klavye doğrulandıysa: ilk karakterden sonra ardışık karakterler arası süre `max_char_interval_ms` sınırını aşarsa biriken tampon sıfırlanır ve uyarı gösterilir.
    - `required_prefix` tanımlıysa: giriş belirlenen önekle başlamıyorsa `onEnter` / `onTabKey` aşamasında reddedilir; geçerliyse önek kırpılarak temiz barkod `emit("scan", cleanCode)` ile üst ekrana iletilir.
  - Reddedilen girişlerde input temizlenir ve net Türkçe uyarı gösterilir: `__("Lütfen barkod okuyucu ile okutun.")` (çeviri sözlükleriyle senkronize).
- **Testler:** `erpnextkta/public/pda-hub/__tests__/` altında `BarcodeScannerBar` için Vitest birim testleri eklenir (sanal klavye `inputmode="none"`, `paste`/`drop` engeli, yavaş elle yazma reddi, hızlı okuyucu okutması kabulü, prefix doğrulama/kırpma, `scanOnly=false` / yetkili rol bypass senaryoları).

### Builder'a Bırakılan Uygulama Detayları
- `KTA Warehouse Settings` DocType'ının sıfırdan oluşturulması veya mevcut `kta_stock` ayar yapısına yerleştirilme biçimi ve varsayılan `pda_scanner_max_char_interval_ms` değeri (Faz 0 ölçümüne göre belirlenecek).
- HYATTA'nın Faz 0 sonucuna göre toplu metin enjeksiyonu (IME `commitText` / tek `input` olayı) kullanması durumunda, tek seferde gelen barkod ile pano yapıştırmasını ayırt etme eşiği veya doğrudan Prefix modunun varsayılana çekilmesi.
- `required_prefix` değerinin tarayıcı tarafında ham istemci yanıtında açık metin yerine nasıl taşınacağı veya maskeleneceği ve hata sonrası `focusInput()` zamanlaması.
- Mevcut `PdaBootData` / `VerifyPdaPinResponse` TypeScript arayüzlerinin ([types.ts](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/erpnextkta/public/pda-hub/types.ts)) ve 5 stok hareketi view'ının prop bağlantılarının güncellenmesi.

---

## 6. Doğrulama Kriterleri

1. **Normal Operatör (`KTA PDA Stock User`) — Stok Hareketi Ekranları (`PickingModuleView`, `PdaApp`, `MaterialTransferView`, `PackageSplitView`, `PackageMergeView`):**
   - HYATTA cihazında `#pda-barcode-input` alanına dokunulduğunda Android sanal klavye açılmamalı, odak aktif kalmalıdır.
   - Kopyala-yapıştır (`paste`), sürükle-bırak (`drop`) veya uzun basma bağlam menüsü (`contextmenu`) engellenmelidir.
   - Harici klavye veya sanal klavyeden yavaş elle yazma denemesi reddedilmeli, input alanı temizlenmeli ve `"Lütfen barkod okuyucu ile okutun."` uyarısı görüntülenmelidir.
   - HYATTA donanım tetiğiyle gerçek barkod okutma akıcı biçimde çalışmalı ve mevcut raf/koli/SUT çözümleyicilerine temiz barkod iletilmelidir.
2. **`StockLookupView` Ekranı:**
   - Rol fark etmeksizin manuel ürün/parti/raf aramaya açık kalmalıdır (`scanOnly = false`).
3. **Yetkili Roller (`KTA PDA Supervisor` / `Stock Manager` / `System Manager`):**
   - `can_manual_barcode_entry === true` ile tüm ekranlarda manuel yazma ve yapıştırma serbest kalmalıdır.
4. **Kalite Kapısı:**
   - Vitest birim testleri ve backend Clean-CI testleri (`test_pda_service.py`) yeşil geçmelidir.
   - `bench build --app erpnextkta --production` hatasız tamamlanmalıdır.
   - Kullanıcı dokümantasyonu (`erpnextkta/www/docs/`), geliştirici kılavuzu (`docs/`) ve çok dilli çeviri sözlükleri (`tr.csv`, `en.csv`, `de.csv`) güncellenmelidir.
