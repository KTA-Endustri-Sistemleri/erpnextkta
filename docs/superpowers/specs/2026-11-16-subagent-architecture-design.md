# Modül Bazlı Alt-Ajan (Subagent) Orkestrasyon Mimarisi — Tasarım

- **Durum:** Onaya Hazır
- **Tarih:** 2026-11-16
- **Temel Alınan Kod Ağacı:** `feat/mrp-modular-refactor` (`mrp_engine/` ve `mrp_simulation/` dahil güncel ağaç; genel üretim PR hedef kuralı `main` olarak korunur)
- **Kapsam:** `.agents/`, kök `AGENTS.md`, eski `.clinerules` ve `memory-bank/` yapıları

---

## 1. Amaç ve Neden

`erpnextkta` kod tabanı büyüdükçe tek bir kök `.agents/AGENTS.md` dosyası içinde hem evrensel katkı kurallarını hem de modüllere özgü ağır iş mantığını (ör. MRP motor formülleri, lojistik durum rozetleri) bir arada tutmak üç temel sorun üretmektedir:

1. **Bağlam Kirliliği ve Odak Kaybı:** Kalite, satış veya çalışma kartı üzerinde çalışan tekil bir ajan gereksiz yere ~70 satırlık MRP formüllerini okumakta; buna karşın `kta_stock`, `overrides`, `kta_sales` veya `public/` Vue SPA katmanlarının güncel kuralları kök dosyada yer almamaktadır.
2. **Dağınık ve Çelişkili Kural Mirası:** Üretim sahası kuralları `erpnextkta/kta_calisma_karti/.clinerules` içinde, genel notlar kök `.clinerules` dosyasında, eski mimari notlar ise üç ayrı `memory-bank/` klasöründe dağınık durmaktadır. Bazı eski notlar (ör. `kta_mrp/memory-bank/systemPatterns.md` içindeki raporların birbirini çağırdığı Mayıs 2026 diyagramı) güncel `mrp_engine/` ayrım kuralıyla doğrudan çelişmektedir.
3. **Modül Zihin Modeli Eksikliği:** Her modülün kendine özgü değişmezleri (invariants), test taban sınıfları ve mimari sınırları vardır. Görevlerin ilgili modülün kurallarıyla düşünen izole uzman alt-ajanlar tarafından yürütülmesi hedeflenmektedir.

Bu tasarım, kök `AGENTS.md` dosyasını **kod yazmayan bir Tech Lead / Koordinatör** rolüne dönüştürür ve kod tabanının tamamını **klasör kilidiyle korunan 11 uzman alt-ajana** (`.agents/subagents/<ajan>.md`) ayırır.

---

## 2. Hedefler, Kapsam Dışı ve Anti-Hedefler

### Hedefler
- Ana ajanı (`AGENTS.md`) yalnızca analiz, görev parçalama, alt-ajan başlatma (`define_subagent` + `invoke_subagent`), çapraz modül kontrat yönetimi ve final kalite kapısından sorumlu bir **Tech Lead** yapmak.
- Kod tabanındaki her modül ve yatay katman için sınırları kesişmeyen **11 uzman alt-ajan sistem promptu** (`.agents/subagents/*.md`) oluşturmak.
- Mevcut kök `AGENTS.md`, `.clinerules` ve `memory-bank/` içindeki hala geçerli kuralları ilgili alt-ajan dosyalarına damıtmak; güncelliğini yitirmiş `.clinerules` ve `memory-bank/` dosyalarını repodan temizlemek.
- İş mantığı, akış, DocType veya kullanıcı metni değiştiğinde `docs-i18n` alt-ajanının (`erpnextkta/www/docs/`, `docs/`, `translations/*.csv`) otomatik devreye girmesini garanti altına almak.

### Kapsam Dışı (Non-Goals)
- Uygulama çalışma zamanı (Python/Vue üretim kodu, veritabanı şeması veya Frappe DocType'ları) üzerinde herhangi bir fonksiyonel değişiklik yapmak.
- `frontend/` altındaki kullanılmayan Frappe-UI başlangıç şablonunu silmek veya yeniden yazmak (yalnızca sahipliği tanımlanır).

### Anti-Hedefler (Başarısızlık Kriterleri)
- Ana ajanın küçük görevlerde "hızlıca kendim düzelteyim" diyerek modül koduna doğrudan yazması.
- Bir alt-ajanın kendi klasör kilidi dışındaki bir dosyayı (ör. `kta-calisma-karti` ajanının `hooks.py` veya `public/` altındaki bir `.vue` dosyasını) doğrudan düzenlemesi.
- Eski `memory-bank/` dosyalarındaki geçersiz mimari ifadelerin (ör. raporların birbirini import etmesi) doğrulama yapılmadan yeni alt-ajan dosyalarına kopyalanması.
- PR açıklamalarında, dokümanlarda veya örneklerde gerçek tedarikçi/müşteri şirket isimlerinin veya ticari birim fiyatların yer alması.

---

## 3. Kısıtlar ve Korunacak Evrensel İlkeler

1. **Hedef Dal ve PR Disiplini:** Hedef dal `main`'dir. PR açıklamaları istisnasız `.github/PULL_REQUEST_TEMPLATE.md` şablonuna göre ve doğrudan kopyalanabilir `markdown` kod bloğu içinde üretilir.
2. **Gizlilik Kuralı:** Commit mesajları, PR açıklamaları, test verileri ve dokümanlarda ticari fiyat veya gerçek tedarikçi/iş ortağı şirket adı kesinlikle bulunamaz; her zaman anonimleştirilir (`"varsayılan tedarikçi"`, `"örnek birim fiyat"`).
3. **Tek Doğruluk Kaynağı (`erpnextkta/www/docs/`):** Son kullanıcıya `/docs/` üzerinden sunulan HTML dokümantasyonu birincil doğruluk kaynağıdır (`docs/` altındaki geliştirici rehberleriyle senkron tutulur).
4. **Build Kuralı:** Frontend derlemesi için asla doğrudan `yarn build` çalıştırılmaz; yalnızca `bench build --app erpnextkta --production` kullanılır.
5. **Kodlama Standartları:**
   - Conventional Commits (`<type>(<scope>): <subject>`, küçük harf tip, emir kipi).
   - Python için `/home/frappe/frappe-bench/env/bin/ruff` (`ruff check` ve `ruff format --check`, değiştirilen dosyalar üzerinde), JS/Vue için `Prettier` + `ESLint`; depoda `.pre-commit-config.yaml` tanımlıysa commit öncesi `pre-commit run --all-files`.
   - Null-güvenliği: Frappe sayısal alanları (`qty`, `per_ordered`, `lead_time` vb.) doğrudan sayılarla karşılaştırılmaz; `flt()`, `cint()` veya `(self.field or 0)` ile korunur.
   - Veritabanı erişiminde Frappe ORM esastır; zorunlu olmadıkça ham SQL yazılmaz, yazıldığında parametreli sorgu kullanılır.
   - Fonksiyon boyutu küçük ve modüler tutulur (~10 satır çekirdek mantık hedefi).
   - Çeviri: Python'da `_("...")`, JS/Vue'da tam cümle bütünlüğüyle `__("...")` ve Title Case standardı uygulanır.

---

## 4. Değerlendirilen Yaklaşımlar ve Seçim

| Yaklaşım | Açıklama | Artıları / Eksileri | Karar |
|---|---|---|---|
| **Yaklaşım A: `.agents/subagents/<ajan>.md` (Saf Alt-Ajan Şablonları)** | Kök `.agents/AGENTS.md` Tech Lead yönlendiricisi olur; 11 uzmanın sistem promptu `.agents/subagents/` altında tutulur ve `define_subagent` + `invoke_subagent` ile yüklenir. | **+** Ana ajanın `<skills>` listesini şişirmez.<br>**+** Ana ajanın skill'i kendisi okuyup kod yazma riskini ortadan kaldırır.<br>**−** Doğrudan `/skill` kısayolu olarak görünmez. | **Seçildi** |
| **Yaklaşım B: `.agents/skills/<ajan>/SKILL.md`** | 11 modül uzmanı Antigravity yerel skill formatında tanımlanır. | **+** Sohbetten `/kta-mrp` gibi çağrılabilir.<br>**−** Her oturumda 11 skill açıklaması bağlama yüklenir; "önce kendin oku" kuralı saf koordinatör modeliyle sürtüşür. | Elendi |
| **Yaklaşım C: Klasör İçi `erpnextkta/<modül>/AGENTS.md`** | Alt-ajan başlatılmaz; tek ajan klasöre göre pasif kural okur. | **+** Kurulumu basittir.<br>**−** Bağımsız alt-ajan muhakemesi ve görev izolasyonu sağlamaz. | Elendi |

---

## 5. Mimari Tasarım

### 5.1 `.agents/` Dizin Yapısı

```text
.agents/
├── AGENTS.md                          # Tech Lead / Koordinatör kuralları + Evrensel ilkeler + Yönlendirme matrisi
└── subagents/
    ├── kta-mrp.md                     # MRP motoru, kapasite, PSW ve MRP raporları uzmanı
    ├── mrp-simulation.md              # MRP simülasyon veri üretimi ve doğrulama uzmanı
    ├── kta-calisma-karti.md           # Üretim sahası (Çalışma Kartı), vardiya görevleri ve ölçüm uzmanı
    ├── kta-asset-maintenance.md       # Varlık/makine bakım ve arıza-duruş entegrasyon uzmanı
    ├── kta-stock.md                   # Stok, parti/etiket, ambalaj fişi ve sayım kilidi uzmanı
    ├── kta-quality.md                 # Krimp kütüphanesi, kalite parametreleri ve test masası uzmanı
    ├── kta-sales.md                   # Satış siparişi güncelleme/karşılaştırma ve fiyat senkron uzmanı
    ├── erpnextkta-core.md             # Çekirdek uygulama DocType'ları (8D, gümrük/antrepo, mobil depo) ve ortak api.py uzmanı
    ├── frontend-public.md             # Vue 3 SPA'lar, Desk JS/CSS ve Vitest arayüz uzmanı
    ├── overrides-hooks.md             # ERPNext DocType override'ları, hooks.py, patch, fixture ve kök test altyapısı uzmanı
    └── docs-i18n.md                   # Portal dokümantasyonu (www/docs), teknik rehberler (docs/) ve çeviri (translations/) uzmanı
```

### 5.2 Kök `.agents/AGENTS.md` — Rol Koşullu Tech Lead Orkestrasyon Protokolü

> **Teknik Mimari Kararı (`<user_rules>` Kalıtımı):** Antigravity çalışma zamanında kök `.agents/AGENTS.md` dosyası hem üst seviye Koordinatör oturumuna hem de `Workspace="inherit"` ile başlatılan alt-ajan oturumlarına en yüksek öncelikli kural (`<user_rules>`) olarak enjekte edilir. Alt-ajanların yazma yetkisinin kilitlenmemesi için `AGENTS.md` içindeki orkestrasyon kuralları **oturum rolüne koşullu** yazılacaktır:
> - **Üst Seviye Oturum (Koordinatör / Tech Lead — alt-ajan olarak başlatılmamış ana oturum):** Uygulama kaynak dosyalarına (`erpnextkta/**`, `docs/**`, `frontend/**`) doğrudan yazmaz; işi ilgili uzman alt-ajana delege eder.
> - **Uzman Alt-Ajan Oturumu (Subagent — kendi sistem promptunda `owned_paths` atanmış oturum):** Yalnızca kendi `owned_paths` dizinlerine yazma yetkisine sahiptir; `AGENTS.md` içindeki evrensel kodlama, gizlilik, null-safety ve isimlendirme kurallarına uyar, ancak Koordinatörün "kod yazmama / alt-ajan başlatma" kısıtından muaftır.

Koordinatör her konuşmada aşağıdaki protokole uyar:

1. **Kod Yazmama Kuralı (Yalnızca Üst Seviye Koordinatör):** Koordinatör modül veya uygulama kaynak dosyalarını (`erpnextkta/**`, `docs/**`, `frontend/**`) doğrudan düzenlemez (`write_file` / `edit_file` kullanmaz). Yalnızca depo üst-veri/altyapı ve planlama dosyaları (`.agents/**`, `.github/**`, `docker/**`, `pyproject.toml`, `setup.py`, `ch-templates/**`, `CHANGELOG.md`, `.gitignore`, `docs/superpowers/**`) açıkça istendiğinde Koordinatörün kendi yazma alanındadır.
2. **Keşif ve Yönlendirme:**
   - Salt-okunur geniş kod taraması gerektiğinde yerleşik `research` alt-ajanını veya hedefli dosya okumalarını kullanır.
   - Görevin hangi klasörleri etkilediğini belirler, ilgili `.agents/subagents/<ajan-id>.md` dosyasını okur ve `define_subagent` (`EnableWriteTools=True`, `EnableSubagentTools=False`) ile tanımlayıp `invoke_subagent` (`Workspace="inherit"`) ile görevlendirir.
   - Aynı konuşmada aynı uzmanla devam edilecekse yeni alt-ajan açmak yerine mevcut `conversationId` üzerinden `send_message` ile devam eder.
3. **Paralel ve Sıralı Çalışma (`Workspace: inherit`):**
   - Yazma alanları ayrık (disjoint) olduğu için birden fazla alt-ajan (ör. `kta-mrp` ve `frontend-public`) aynı çalışma ağacında (`inherit`) paralel başlatılabilir.
   - Ancak veritabanı şeması veya ortak API imzası önce netleşmeliyse Koordinatör önce kontratı belirler (veya önce backend ajanını çalıştırır), ardından tüketici ajana net kontratı iletir.
   - Alt-ajanlar paralel çalışırken ağır global komutları (`bench build`, tüm uygulama testleri) kendi başlarına çalıştırmaz; yalnızca kendi modül kapsamındaki hızlı birim/entegrasyon testlerini çalıştırır.
4. **Kontrat Devri (Contract Handoff):**
   - Bir alt-ajan kendi klasörü dışında değişiklik gerektiğinde (ör. `hooks.py` içine yeni `doc_events` eklenmesi, `public/` altındaki Vue bileşeninin yeni alanı göstermesi, `www/docs/` güncellemesi) o dosyaya dokunmaz; çıktısında yapılandırılmış bir **`## Çapraz Modül Kontrat İhtiyacı`** bölümü döner. Koordinatör bu kontratı ilgili diğer alt-ajana görev olarak iletir.
5. **Akıllı `docs-i18n` Kapısı:**
   - İş mantığı, iş akışı, rol/yetki, DocType/özel alan, MRP/üretim hesaplaması veya kullanıcıya görünen metin değiştiğinde Koordinatör görevi kapatmadan önce **otomatik olarak `docs-i18n` alt-ajanını** devreye sokar.
   - Saf iç refactor, performans iyileştirmesi veya yalnızca test düzeltmelerinde `docs-i18n` adımı atlanır.
6. **Koordinatör Final Doğrulama Kapısı:**
   - Tüm alt-ajanlar tamamlandığında Koordinatör:
     1. Frontend/public etkilenmişse `bench build --app erpnextkta --production` komutunu çalıştırır.
     2. Etkilenen modüllerin ve çapraz entegrasyonların `bench --site <site> run-tests --app erpnextkta --module ...` testlerini doğrular.
     3. Değiştirilen Python dosyaları üzerinde `/home/frappe/frappe-bench/env/bin/ruff check` ve `ruff format --check` kontrollerini (ve depoda `.pre-commit-config.yaml` mevcutsa `pre-commit run --all-files` komutunu) çalıştırır.

---

### 5.3 11 Alt-Ajan Sahiplik ve Klasör Kilidi Matrisi

Her alt-ajan kod tabanının tamamını **salt-okunur** inceleyebilir; ancak **yalnızca kendi `Yazma Alanı (Owned Paths)` altındaki dosyaları** oluşturabilir, düzenleyebilir veya silebilir.

| Alt-Ajan ID | Yazma Alanı (`owned_paths`) | Birincil Sorumluluk ve Zihin Modeli | Test Sorumluluğu |
|---|---|---|---|
| `kta-mrp` | `erpnextkta/kta_mrp/**` | Saf `mrp_engine/` servisleri (`lead_time`, `psw`, `capacity`, `demand`, `supply`, `leveling`, `netting`, `bom`, `settings`), `KTA MRP Settings`, `KTA Sevk Parametreleri`, `report/` sunum katmanı ve `report_utils.py`. | `erpnextkta/kta_mrp/mrp_engine/test_*.py`, `erpnextkta/kta_mrp/tests/**` (`KTAUnitTestCase` / `KTABaseTestCase`) |
| `mrp-simulation` | `erpnextkta/mrp_simulation/**` | Deterministik MRP test/simülasyon veri üretimi (`seeder.py`, `cleaner.py`, `dates.py`, `constants.py`) ve `KTA MRP Settings` simülasyon başlangıç parametreleri. | `erpnextkta/mrp_simulation/test_*.py` |
| `kta-calisma-karti` | `erpnextkta/kta_calisma_karti/**`<br>`erpnextkta/tasks.py`<br>`erpnextkta/dry_run/**` | Shopfloor üretim kartı yaşam döngüsü (`api.py` facade + `api_impl/`), taslak-öncelikli (`docstatus=0` -> `Bitis` anında submit) akış, alt operasyon/hammadde grup beyaz listesi, hurda `Stock Entry` çift yönlü senkronu, QI ve Job Card senkronu, krimp/IDC/enjeksiyon kalıp ölçümleri, vardiya sonu otomatik kapatma cron görevleri. | `erpnextkta/kta_calisma_karti/tests/**` ve DocType içi testler (`KTATestCase` / `KTABaseTestCase` / `KTAUnitTestCase`) |
| `kta-asset-maintenance` | `erpnextkta/kta_asset_maintenance/**` | `Asset Maintenance` ve `Asset Maintenance Log` olay dinleyicileri (`events.py`), arıza kaynaklı duruş bildirimleri, bakım ekibi çözümleme ve `Calisma Karti` arıza referans entegrasyonu. | İlgili bakım birim/entegrasyon testleri (kök test gerekiyorsa `overrides-hooks` ile kontrat üzerinden) |
| `kta-stock` | `erpnextkta/kta_stock/**`<br>`erpnextkta/rest-api/**` | Parti bölme (`BatchSplitManager`), Zebra barkod/etiket basımı (`LabelPrinter`, `KTA Stock Label`), transfer öncesi parti kalite kontrol doğrulaması (`quality_inspection_validator.py`), `Iade Edilebilir Ambalaj Fisi`, depo bazlı tekil taslak sayım kilidi (`stock_reconciliation_lock.py`) ve realtime sayım yayını. | `erpnextkta/kta_stock/tests/**` ve DocType testleri (`KTAUnitTestCase` / `KTABaseTestCase`) |
| `kta-quality` | `erpnextkta/kta_quality/**` | `KTA Krimp Book` (referans katalog), `KTA Krimp Yukseklik Parametreleri` (onaylı uygulama standardı), `Test Masasi Dogrulama Kaydi` (17 sabit Poke-Yoke kriteri ve bağlantı noktası kontrolleri, `Calisma Karti` yansıtması) ve `KTA Quality Settings`. | `erpnextkta/kta_quality/**` altındaki DocType/modül testleri (`KTABaseTestCase`) |
| `kta-sales` | `erpnextkta/kta_sales/**` | Müşteri sipariş güncelleme ve karşılaştırma motoru (`KTA Sales Order Update` ve alt tabloları, `KTA SO Sync Log`), müşteri bazlı satış fiyat listesi eşleştirme (`KTA Selling Rate Customer`). | `erpnextkta/kta_sales/**` altındaki DocType/modül testleri (`KTABaseTestCase`) |
| `erpnextkta-core` | `erpnextkta/erpnextkta/**`<br>`erpnextkta/api.py`<br>`erpnextkta/boot.py`<br>`erpnextkta/middlewares.py`<br>`erpnextkta/config/**`<br>`erpnextkta/templates/**`<br>`erpnextkta/__init__.py`<br>`erpnextkta/modules.txt` | Çekirdek `erpnextkta` modülü altındaki paylaşılan DocType'lar (`Kalite 8D Formu`, `KTA Machine Capability Study`, gümrük/antrepo beyanname ve idare kayıtları, `KTA Mobil Depo`, `KTA Amboss Takimlari`, `KTA Olcu Metodu`), `erpnextkta/custom/*.json` şema özelleştirmeleri, uygulama geneli yardımcılar (`erpnextkta/api.py`), ciro/sipariş analiz raporları ve yazdırma şablonları. | `erpnextkta/erpnextkta/**` altındaki DocType/rapor testleri (`KTABaseTestCase`) |
| `frontend-public` | `erpnextkta/public/**`<br>`frontend/**` | 5 Vue 3 SPA (`create-calisma-karti`, `list-calisma-cards`, `view-calisma-karti`, `material-requirement`, `stock-reco-dashboard`), Desk JS betikleri (`kta_report_utils.js`, `kta_report_overrides.js`, `material_transfer_patch.js`, `item.js`), global CSS (`erpnextkta.bundle.css`, `kta_docs.css`), TypeScript tipleri ve Vitest testleri. | `erpnextkta/public/*/__tests__/**` (Vitest) |
| `overrides-hooks` | `erpnextkta/overrides/**`<br>`erpnextkta/hooks.py`<br>`erpnextkta/patches/**`<br>`erpnextkta/patches.txt`<br>`erpnextkta/fixtures/**`<br>`erpnextkta/tests/**` | Standart ERPNext DocType sınıf ezme katmanı (`override_doctype_class`), merkezi `doc_events` / `scheduler_events` / `fixtures` kayıtları (`hooks.py`), veritabanı göç betikleri (`patches/`), paylaşılan üç kademeli test altyapısı (`test_utils.py`) ve çekirdek override entegrasyon testleri. | `erpnextkta/tests/**` (`test_utils.py`, `test_job_card_sync.py`, `test_purchase_receipt*.py`) |
| `docs-i18n` | `erpnextkta/www/**`<br>`docs/**`<br>`erpnextkta/translations/**`<br>`README.md` | Frappe Web Portalı dokümantasyonu (`erpnextkta/www/docs/*.html` ve `kta_docs_base.html`), `docs/` altındaki geliştirici kılavuzları (Not: `docs/superpowers/**` tasarım/plan belgeleri hariçtir; onlar planlama sürecine aittir) ve çok dilli çeviri CSV dosyaları (`en.csv`, `de.csv`, `tr.csv`) ile Title Case / cümle bütünlüğü denetimi. | HTML şablon bütünlüğü, kırık link ve CSV format/başlık doğrulaması |

> **Özel Not (`docs/superpowers/**`):** Brainstorming ve planlama süreçlerinin ürettiği `docs/superpowers/specs/**` ve `docs/superpowers/plans/**` belgeleri doğrudan Koordinatör (Tech Lead) tarafından yönetilir.

---

### 5.4 Alt-Ajan Dosya Şablonu Standardı (`.agents/subagents/<ajan-id>.md`)

Her alt-ajan dosyası aşağıdaki standart bölümlerle yazılacaktır:

```markdown
---
name: <ajan-id>
description: <Koordinatörün ne zaman bu uzmanı seçeceğini belirten 1-2 cümlelik net tanım>
owned_paths:
  - <yazma izni olan glob yolları>
---

# Rol ve Zihin Modeli
<Bu modülün iş dünyasındaki amacı ve uzmanın karar verirken öncelediği temel bakış açısı>

# Klasör Kilidi (Kesin Sınır)
- **Yazma İzni Olan Yollar:** ...
- **Salt-Okunur Yollar:** Depodaki diğer tüm dosyalar.
- Kendi yazma alanın dışındaki hiçbir dosyayı düzenleme. Dış katman değişikliği gerekiyorsa yanıtının sonundaki "Çapraz Modül Kontrat İhtiyacı" bölümünde belirt.

# Mimari Kurallar ve Değişmezler (Domain Invariants)
<Modüle özgü kesin iş ve kod kuralları — eski dosyalardan damıtılmış ve güncel kodla doğrulanmış maddeler>

# Evrensel Kodlama ve Güvenlik Kuralları (Özet)
- Null-safety (`flt()`, `cint()`, `(self.field or 0)`), Frappe ORM kullanımı, küçük/modüler fonksiyonlar, `_()` / `__()` tam cümle çeviri sarmalayıcısı, gizlilik/anonimlik kuralı.

# Test ve Doğrulama Protokolü
- Kullanılacak taban sınıf (`KTAUnitTestCase` / `KTABaseTestCase` / `KTATestCase` veya Vitest).
- Çalıştırılacak hedefli test komutu (`bench run-tests --module ...` veya `npx vitest run`).
- Paralel çalışmada `bench build` veya tüm uygulama test suite'ini çalıştırmama kuralı.

# Çıktı ve Çapraz Modül Kontrat Formatı
1. Yapılan Değişiklikler (dosya ve özet)
2. Çalıştırılan Testler ve Sonuçları
3. Çapraz Modül Kontrat İhtiyacı (`overrides-hooks`, `frontend-public`, `docs-i18n` vb. için gereken somut adımlar; yoksa "Yok")
```

---

### 5.5 Damıtılacak Kurallar ve Temizlenecek Eski Dosyalar

#### Kök `.agents/AGENTS.md` İçinden Taşınacaklar
- **Bölüm 1–6 ve Build Kuralı** kök `AGENTS.md` içinde korunur; üzerine **Tech Lead Orkestrasyon Protokolü** ve **11 Alt-Ajan Yönlendirme Tablosu** eklenir. (Bölüm 1.6'daki gizlilik kuralında yer alan gerçek şirket adı örneği anonimleştirilerek genel ifadeye çevrilir.)
- **Bölüm 7 (Manufacturing & MRP Domain Rules)** kök `AGENTS.md` içinden çıkarılır:
  - Düz BOM (yarı mamul yok), `Work Order.skip_transfer = 1`, `Item.custom_weekly_production` / `group_capacity`, `Manufacture` tipindeki `Material Request` (`Draft` oluşturma ve `internal_demand` beslemesi), 5 lojistik durum rozeti (`po`, `yolda`, `gumruklemede`, `antrepoda`, `uyusmazlikta`), iki eksenli lead time ($T_{\text{prod}} + T_{\text{transit}}$) ve kademeli çözümleme zinciri, kapasite dengeleme/taşıma (`carry-over`), MOQ/paket lotlama ve emniyet stoğu kilidi, `get_mrp_settings()` zorunluluğu ve `mrp_engine/` ile `report/` ayrımı eksiksiz olarak **`.agents/subagents/kta-mrp.md`** içine taşınır.
  - Çoklu rozet CSS/UI gösterimi (`.mrp-supplies-pills`) ayrıca **`.agents/subagents/frontend-public.md`** içine, `skip_transfer = 1` ve `Material Request` / `Purchase Receipt` durum kuralları ise ilgili yönleriyle **`.agents/subagents/overrides-hooks.md`** içine de referans olarak işlenir.

#### Eski Dosyalardan Damıtılıp Silinecek Kaynaklar
Aşağıdaki dosyaların geçerli teknik kuralları ilgili alt-ajanlara aktarıldıktan sonra dosyalar `git rm` ile repodan kaldırılacaktır:

1. **`.clinerules` (kök):**
   - `override_doctype_class` ve `doc_events` prensipleri → `overrides-hooks.md`
   - `erpnextkta/api.py` merkezi yardımcı kontrolü ve `KTA` önek standardı → `erpnextkta-core.md` ve `overrides-hooks.md`
2. **`erpnextkta/kta_calisma_karti/.clinerules` ve `erpnextkta/kta_calisma_karti/memory-bank/**`:**
   - `api.py` facade + `api_impl/` ayrımı, rol kapıları (`is_system_manager`, `is_quality_user`, `require_my_employee`, permlevel 1 `kalite_kontrol`), taslak-öncelikli (`docstatus=0` -> `Bitis` auto-submit) yaşam döngüsü, `docstatus=2` "İptal Edildi" önceliği, alt operasyon ve hurda kümülatif malzeme grubu beyaz listesi, 16:00/00:00 vardiya kapanışı ve 430 dk net süre limiti, hurda `Stock Entry` çift yönlü bayraklı senkronu, QI taslak/kabul/red durum restorasyonu ve barkod önek normalizasyonu → `kta-calisma-karti.md`
   - 500 satır Vue bileşen bölme kuralı, `--ck-glass-*` Light/Dark değişkenleri, `<Teleport to="body">`, sihirbaz aktifken `frappe.msgprint` bastırma ve `const __ = (...args) => window.__(...args);` kuralı → `frontend-public.md`
3. **`erpnextkta/kta_mrp/memory-bank/**`:**
   - Hala geçerli olan `report_utils.py::get_report_filters()` ortak filtre yapısı → `kta-mrp.md`; `kta_report_utils.js` ve `kta_report_overrides.js` dinamik rapor enjeksiyon kalıbı → `frontend-public.md`.
   - *Atılacak çelişkili bilgi:* Raporların birbirine hesaplama delege ettiği eski mimari anlatım kesin olarak **aktarılmaz**.
4. **`erpnextkta/kta_quality/memory-bank/**`:**
   - `TestMasasiDogrulamaKaydi` 17 sabit kriter / bağlantı noktası otomatik doldurma (`before_insert`), PTR uygulama metni doğrulaması, `calisma_karti_ref` senkronu, `KTA Krimp Book` (referans katalog) ile `KTA Krimp Yukseklik Parametreleri` (onaylı uygulama) ayrımı → `kta-quality.md` (Not: eski örnekteki manuel `frappe.db.commit()` anti-pattern olarak kopyalanmaz; güncel controller davranışı esas alınır).

---

## 6. Uygulayıcıya (Builder) Bırakılan Kararlar

- Her `.agents/subagents/<ajan-id>.md` dosyasının iç başlık sıralamasındaki üslup inceltmeleri ve ilgili modülün güncel kodundan çıkarılacak ek yardımcı dosya/DocType listesinin detay seviyesi (her dosya öz, net ve ~80–160 satır bandında kalacak şekilde).
- Koordinatörün kontrat devir şablonundaki alan adlarının birebir metin formatı.

---

## 7. Doğrulama ve Kabul Kriterleri

1. **Eksiksiz Dosya Kurulumu:** `.agents/AGENTS.md` güncellenmiş ve `.agents/subagents/` altında 11 alt-ajan dosyasının tamamı oluşturulmuş olmalıdır.
2. **Sıfır Sahipsiz Klasör:** Depodaki her uygulama klasörü tam olarak bir alt-ajanın (veya üst-veri dosyaları için Koordinatörün) `owned_paths` listesinde yer almalı; iki alt-ajanın yazma alanı kesişmemelidir.
3. **Eski Dosya Temizliği:** Kök `.clinerules`, `erpnextkta/kta_calisma_karti/.clinerules` ve 3 adet `memory-bank/` klasörü repodan tamamen kaldırılmış olmalıdır.
4. **Gizlilik ve Tutarlılık Denetimi:** Yeni `.agents/**` dosyalarında hiçbir ticari fiyat, gerçek tedarikçi firma adı veya güncel kodla çelişen eski mimari kural (ör. raporun raporu import etmesi, `frappe.db.commit()` anti-pattern'i, `yarn build`) bulunmamalıdır.
5. **Biçim, Sahiplik ve Tutarlılık Doğrulaması:** Tüm `.agents/subagents/*.md` dosyalarının geçerli YAML frontmatter (`name`, `description`, `owned_paths`) içerdiği, `owned_paths` glob'larının kesişmediği ve değiştirilen dosyalarda format/lint ihlali bulunmadığı doğrulanmalıdır (bu çalışma yalnızca `.md` dosyaları ve eski kural temizliği içerdiğinden Python çalışma zamanı dosyalarına dokunulmaz).
