# Test Altyapısının Modülerleştirilmesi, Dizin Yapılanması ve Log Standardizasyonu — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test altyapısını 3 kademeli taban sınıf hiyerarşisine (`KTAUnitTestCase`, `KTABaseTestCase`, `KTATestCase`) kavuşturmak; dağınık test dosyalarını ait oldukları modüllere (`<module>/tests/`) taşımak; kopya fixture kodlarını ortaklaştırmak ve 159 testin istisnasız tamamının `🔍 [TEST]` formatında loglanmasını sağlamak.

**Architecture:** `test_utils.py` içinde `KTABaseTestCase` oluşturularak DB rollback, Administrator oturumu ve `log_test_start` genel testler için standartlaştırılır; `KTATestCase` ise `KTABaseTestCase`'den türer ve ağır Çalışma Kartı/Job Card altyapısını yönetir. Dağınık test dosyaları `git mv` ile `kta_stock/tests/`, `kta_mrp/tests/` ve `kta_calisma_karti/tests/` dizinlerine taşınır. Manuel script olan `test_qc_integration.py` adı `verify_qc_integration.py` olarak değiştirilerek test discovery temizlenir.

**Tech Stack:** Python 3.10 / 3.11, Frappe v15 / ERPNext v15, `unittest`, `FrappeTestCase`.

**Spec:** `docs/superpowers/specs/2026-11-15-test-altyapisi-modulerlesme-design.md`

## Global Constraints

- Tüm test dosyaları ve sınıfları `frappe.tests.utils.FrappeTestCase` yerine `KTABaseTestCase` veya `KTATestCase`; mock tabanlı olanlar ise `KTAUnitTestCase` kullanmalıdır.
- Mevcut test davranışları ve mantığı asla değiştirilmemeli; sadece taban sınıfları, fixture çağrıları ve dizin konumları güncellenmelidir (sıfır regresyon).
- Taşıma işlemleri Git geçmişinin korunması için mutlaka `git mv` ile yapılmalıdır.
- Commit formatı: Conventional Commits (`test(core): ...`, `refactor(tests): ...`).
- Çalıştırılan `bench run-tests --app erpnextkta` komutunda tüm testler başarılı (`OK`) olmalı ve çıktıda hiçbir `...................` nokta yığını kalmamalıdır.

## Review Focus

1. **Test Discovery Uyumluluğu:** `git mv` sonrasında Frappe test runner'ın tüm testleri bulabildiğini doğrula (`run_all_tests` taraması).
2. **Fixture İzolasyonu:** `ensure_test_injection_fixtures()` birden fazla kez çağrılsa bile idempotence (tekrarlanabilirlik) bozulmamalı, duplicate entry hatası vermemelidir.
3. **Log Format Bütünlüğü:** Tüm modüller için `module_tag` doğru çözümlenmeli (`[stock]`, `[mrp]`, `[calisma_karti]`, `[overrides]`).
4. **Manuel Script İzolasyonu:** `verify_qc_integration.py` dosyasının `bench run-tests` tarafından bir test modülü olarak görülmediğini doğrula.
5. **Gereksiz Job Card Yükü:** `KTABaseTestCase` kullanan testlerin gereksiz yere Çalışma Kartı ve İş Emri oluşturmadığını doğrula.

---

### Task 1: Üç Kademeli Test Taban Sınıfı Mimarisi ve Ortak Fixture'lar (`test_utils.py`)

**Files:**
- Modify: `erpnextkta/tests/test_utils.py`

**Interfaces:**
- Produces:
  - `KTABaseTestCase(FrappeTestCase)`
  - `KTATestCase(KTABaseTestCase)`
  - `ensure_test_injection_fixtures()`
  - `ensure_test_idc_fixtures()`

- [x] **Step 1: `test_utils.py` içinde `KTABaseTestCase` sınıfını tanımla**

`erpnextkta/tests/test_utils.py` içinde:
```python
class KTABaseTestCase(FrappeTestCase):
	"""Base TestCase for database-backed tests that do not need heavy Calisma Karti infrastructure."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.flags.use_serial_and_batch_fields = False
		log_test_start(self)
```

- [x] **Step 2: `KTATestCase` sınıfını `KTABaseTestCase`'den türet ve sadeleştir**

```python
class KTATestCase(KTABaseTestCase):
	"""Base TestCase for Calisma Karti and shopfloor manufacturing integration tests."""

	def setUp(self):
		super().setUp()
		self.setup_kta_infrastructure()
```

- [x] **Step 3: `ensure_test_injection_fixtures` ve `ensure_test_idc_fixtures` fonksiyonlarını ekle**

`test_calisma_karti_enjeksiyon_olcumleri.py` ve `test_calisma_karti_idc_olcumleri.py` içinde yinelenen kalıp, tolerans ve operasyon oluşturma mantığını idempotant olarak `test_utils.py` içine al.

- [x] **Step 4: Doğrulama testini çalıştır**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti.test_calisma_karti_unit`
Expected: PASS (Tüm birim testler yeşil).

- [x] **Step 5: Commit**

```bash
git add erpnextkta/tests/test_utils.py
git commit -m "refactor(tests): introduce KTABaseTestCase and common injection/idc test fixtures"
```

---

### Task 2: Test Dosyalarının Modül Dizinlerine Taşınması (`git mv`)

**Files:**
- Move: `erpnextkta/tests/test_label_manager.py` ➡️ `erpnextkta/kta_stock/tests/test_label_manager.py`
- Move: `erpnextkta/tests/test_mrp_analysis.py` ➡️ `erpnextkta/kta_mrp/tests/test_mrp_analysis.py`
- Move: `erpnextkta/tests/test_api.py` ➡️ `erpnextkta/kta_calisma_karti/tests/test_api.py`
- Move: `erpnextkta/tests/test_qi_validation.py` ➡️ `erpnextkta/kta_calisma_karti/tests/test_qi_validation.py`
- Move: `erpnextkta/tests/test_enjeksiyon_kalip_api.py` ➡️ `erpnextkta/kta_calisma_karti/tests/test_enjeksiyon_kalip_api.py`
- Move: `erpnextkta/tests/test_enjeksiyon_kalip_full.py` ➡️ `erpnextkta/kta_calisma_karti/tests/test_enjeksiyon_kalip_full.py`
- Move: `erpnextkta/tests/test_mold_patch.py` ➡️ `erpnextkta/kta_calisma_karti/tests/test_mold_patch.py`
- Move/Rename: `erpnextkta/kta_calisma_karti/scripts/test_qc_integration.py` ➡️ `erpnextkta/kta_calisma_karti/scripts/verify_qc_integration.py`

- [x] **Step 1: Modül test klasörlerini oluştur ve dosyaları `git mv` ile taşı**

```bash
mkdir -p erpnextkta/kta_stock/tests
touch erpnextkta/kta_stock/tests/__init__.py
git mv erpnextkta/tests/test_label_manager.py erpnextkta/kta_stock/tests/test_label_manager.py

mkdir -p erpnextkta/kta_mrp/tests
touch erpnextkta/kta_mrp/tests/__init__.py
git mv erpnextkta/tests/test_mrp_analysis.py erpnextkta/kta_mrp/tests/test_mrp_analysis.py

mkdir -p erpnextkta/kta_calisma_karti/tests
touch erpnextkta/kta_calisma_karti/tests/__init__.py
git mv erpnextkta/tests/test_api.py erpnextkta/kta_calisma_karti/tests/test_api.py
git mv erpnextkta/tests/test_qi_validation.py erpnextkta/kta_calisma_karti/tests/test_qi_validation.py
git mv erpnextkta/tests/test_enjeksiyon_kalip_api.py erpnextkta/kta_calisma_karti/tests/test_enjeksiyon_kalip_api.py
git mv erpnextkta/tests/test_enjeksiyon_kalip_full.py erpnextkta/kta_calisma_karti/tests/test_enjeksiyon_kalip_full.py
git mv erpnextkta/tests/test_mold_patch.py erpnextkta/kta_calisma_karti/tests/test_mold_patch.py

git mv erpnextkta/kta_calisma_karti/scripts/test_qc_integration.py erpnextkta/kta_calisma_karti/scripts/verify_qc_integration.py
```

- [x] **Step 2: Taşınan testlerin çalıştığını tek tek doğrula**

Run:
```bash
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_stock.tests.test_label_manager
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.tests.test_mrp_analysis
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.tests.test_api
```
Expected: PASS.

- [x] **Step 3: Commit**

```bash
git add erpnextkta/
git commit -m "refactor(tests): relocate test files into respective module test directories"
```

---

### Task 3: Test Sınıflarını Yeni Taban Sınıflara Bağlama ve Kod Sadeleştirmesi

**Files:**
- Modify: `erpnextkta/kta_stock/tests/test_label_manager.py` (switch to `KTAUnitTestCase`)
- Modify: `erpnextkta/kta_mrp/tests/test_mrp_analysis.py` (switch to `KTABaseTestCase`, cleanup manual company setup)
- Modify: `erpnextkta/kta_calisma_karti/tests/test_enjeksiyon_kalip_api.py` (switch to `KTABaseTestCase`)
- Modify: `erpnextkta/kta_calisma_karti/tests/test_enjeksiyon_kalip_full.py` (switch to `KTATestCase`, use `ensure_test_injection_fixtures`)
- Modify: `erpnextkta/kta_calisma_karti/tests/test_mold_patch.py` (switch to `KTABaseTestCase`)
- Modify: `erpnextkta/kta_stock/doctype/iade_edilebilir_ambalaj_fisi/test_iade_edilebilir_ambalaj_fisi.py` (switch to `KTABaseTestCase`)
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti_enjeksiyon_olcumleri/test_calisma_karti_enjeksiyon_olcumleri.py` (switch to `KTATestCase`, use `ensure_test_injection_fixtures`, remove 60 lines of duplicate setup)
- Modify: `erpnextkta/kta_calisma_karti/doctype/calisma_karti_idc_olcumleri/test_calisma_karti_idc_olcumleri.py` (switch to `KTATestCase`, use `ensure_test_idc_fixtures`, remove duplicate setup)
- Modify: `erpnextkta/kta_calisma_karti/doctype/kta_enjeksiyon_kalibi/test_kta_enjeksiyon_kalibi.py` (switch to `KTABaseTestCase`)

- [x] **Step 1: Test sınıflarının miras aldığı sınıfları güncelle**
  - `TestLabelManager(KTAUnitTestCase)`
  - `TestMrpAnalysisReservationsAndFilters(KTABaseTestCase)`
  - `TestEnjeksiyonKalipApi(KTABaseTestCase)`
  - `TestEnjeksiyonKalipFull(KTATestCase)`
  - `TestMoldPatch(KTABaseTestCase)`
  - `TestIadeEdilebilirAmbalajFisi(KTABaseTestCase)`
  - `TestCalismaKartiEnjeksiyonOlcumleri(KTATestCase)`
  - `TestCalismaKartiIdcOlcumleri(KTATestCase)`
  - `TestKTAEnjeksiyonKalibi(KTABaseTestCase)`

- [x] **Step 2: `test_calisma_karti_enjeksiyon_olcumleri.py` ve `test_calisma_karti_idc_olcumleri.py` içindeki kopya setup kodlarını ortak fixture çağrısıyla değiştir**

- [x] **Step 3: Testleri modül bazında çalıştır ve log formatlarını doğrula**

Run:
```bash
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_calisma_karti.doctype.calisma_karti_enjeksiyon_olcumleri.test_calisma_karti_enjeksiyon_olcumleri
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_stock.doctype.iade_edilebilir_ambalaj_fisi.test_iade_edilebilir_ambalaj_fisi
```
Expected: PASS, her test `🔍 [TEST] [<modül>] [...]` formatında log basmalıdır.

- [x] **Step 4: Commit**

```bash
git add erpnextkta/
git commit -m "refactor(tests): migrate test classes to KTABaseTestCase and deduplicate fixtures"
```

---

### Task 4: Tüm Test Süiti Doğrulaması (159/159 Zengin Loglama)

**Files:**
- Verification only

- [x] **Step 1: Tüm uygulama test süitini çalıştır**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --app erpnextkta`
Expected: `Ran 159 tests in ... OK`. Hiçbir `...................` kalmamış olmalı, her test zengin log etiketiyle konsola basılmış olmalıdır.

- [x] **Step 2: Git status ve diff kontrolü**

Run: `git status` ve `git diff main..HEAD --stat`
Expected: Temiz, düzenli dizin yapısı ve azalan kod hacmi.
