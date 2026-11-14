# Satınalma İrsaliyesi (Purchase Receipt) İş Akışı, Yetkilendirme ve Mal Kabul Uyuşmazlığı Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Satınalma İrsaliyesi (Purchase Receipt) iş akışında (`KTA Mal Giris Sureci`) gümrük ve transit süreçlerini yeni `KTA Gümrük Sorumlusu` rolüne kilitlemek, adım adım geri dönüş (step-by-step rollback) zincirini kurmak, kapıdaki retler için `Mal Kabul Uyuşmazlığı` ara statüsünü entegre etmek ve bu statüdeki malzemeleri MRP motorunda güvenli şekilde (arz = 0) ele almak.

**Architecture:** Frappe Workflow fixtures (`workflow.json`, `workflow_state.json`, `workflow_action_master.json`), DocType Customizations (`purchase_receipt.json`), `purchase_receipt.js` diyalog tetikleyicisi ve `supply.py`/`service.py` MRP arz hattı kuralları güncellenir. TDD yaklaşımı ile her aşama otomatik birim testleriyle doğrulanır.

**Tech Stack:** Frappe Framework v15, Python 3.12, JavaScript / Frappe UI, unittest.

**Spec:** [docs/superpowers/specs/2026-11-13-purchase-receipt-workflow-authorization-design.md](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/superpowers/specs/2026-11-13-purchase-receipt-workflow-authorization-design.md)

## Global Constraints
- `KTA Gümrük Sorumlusu` rolü yalnızca `ceren.kecici@kta-endustri.com.tr`, `omur.muslu@kta-endustri.com.tr` ve `Administrator` kullanıcılarına atanır.
- `Stock User` (depocular), `Purchase User` rolüne sahip olsalar dahi `Yolda`, `Antrepoda` ve `Gümrüklemede` statülerindeki hiçbir geçişi tetikleyemez.
- İthalat irsaliyesi `Mal Giriş` aşamasında reddedildiğinde doğrudan `Yolda`ya fırlatılamaz; `Mal Kabul Uyuşmazlığı`na geçer.
- `Mal Kabul Uyuşmazlığı` statüsündeki irsaliyeler MRP netleştirmesinde **kesinlikle kullanılabilir arz sayılmaz (`receipts = 0`)**.
- Kullanıcı talimatı gereği tüm değişiklikler çalışma dizininde (working directory) tutulur, kullanıcı onayı gelene kadar commit atılmaz.

## Review Focus
1. Depocu (`Stock User`) `Mal Giriş` aşamasında ret verdiğinde zorunlu uyuşmazlık tipi ve açıklaması girmeden statü geçişi yapılamamalıdır.
2. `Gümrüklemede` statüsündeki ret işlemi doğrudan `Yolda`ya değil, tam bir önceki adım olan `Antrepoda`ya dönmelidir.
3. `Mal Kabul Uyuşmazlığı`na düşen ithalat evrakında çözüm aksiyonlarını (`Sorun Çözüldü`, `Gümrüğe İade`) sadece `KTA Gümrük Sorumlusu` görebilmelidir; yerli evrakta ise `Purchase User` görebilmelidir.
4. MRP motoru `Mal Kabul Uyuşmazlığı`ndaki irsaliyenin miktarını haftalık arza dahil etmemeli, ancak `supply_breakdown` içinde uyuşmazlık tipiyle birlikte raporlamalıdır.
5. `workflow.json` fixture'ı sisteme aktarıldığında mevcut taslak irsaliyeler bozulmamalıdır.

---

### Task 1: Rol, Statü ve Özel Alanların Tanımlanması (Role, States, Custom Fields)

**Files:**
- Create/Modify: `erpnextkta/fixtures/workflow_state.json`
- Create/Modify: `erpnextkta/fixtures/workflow_action_master.json`
- Create/Modify: `erpnextkta/erpnextkta/custom/purchase_receipt.json`
- Create: `erpnextkta/patches/v3_0_3/add_kta_gumruk_sorumlusu_role.py`
- Modify: `erpnextkta/patches.txt`
- Test: `erpnextkta/tests/test_purchase_receipt_workflow.py`

- [x] **Step 1: Write failing test for Role and Custom Fields**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement Role patch, Workflow State fixture, and Custom Fields**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Staged/Held without commit (User constraint: no commits)**

---

### Task 2: İş Akışı Matrisi ve Yetki İzolasyonu (`workflow.json`)

**Files:**
- Modify: `erpnextkta/fixtures/workflow.json`
- Test: `erpnextkta/tests/test_purchase_receipt_workflow.py`

- [x] **Step 1: Write failing tests for workflow transitions and role restrictions**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Update `workflow.json` with new permissions and rollback logic**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Staged/Held without commit (User constraint: no commits)**

---

### Task 3: Uyuşmazlık Bildirim Diyaloğu (`purchase_receipt.js`)

**Files:**
- Modify: `erpnextkta/public/js/purchase_receipt.js`
- Modify: `erpnextkta/overrides/KTAPurchaseReceipt.py`
- Test: `erpnextkta/tests/test_purchase_receipt_workflow.py`

- [x] **Step 1: Implement Dialog Prompt in `purchase_receipt.js` and backend validation in `KTAPurchaseReceipt.py`**
- [x] **Step 2: Staged/Held without commit (User constraint: no commits)**

---

### Task 4: MRP Motoru Güvenli Netleştirme ve Tedarik Kırılımı Entegrasyonu (`supply.py`, `service.py`)

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/supply.py`
- Modify: `erpnextkta/kta_mrp/mrp_engine/service.py`
- Test: `erpnextkta/kta_mrp/mrp_engine/test_supply.py`
- Test: `erpnextkta/kta_mrp/mrp_engine/test_service.py`
- Modify: `erpnextkta/public/material-requirement/` (Vue components & types)

- [x] **Step 1: Write failing tests in `test_supply.py` for `Mal Kabul Uyuşmazlığı`**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement `Mal Kabul Uyuşmazlığı` handling in `supply.py`, `service.py`, and Vue components**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Staged/Held without commit (User constraint: no commits)**

---

### Task 5: Uçtan Uca Doğrulama ve Dokümantasyon Güncellemesi

**Files:**
- Modify: `docs/kta_stok_lojistik_kilavuzu.md`
- Modify: `docs/material_requirement.md`
- Execute: Full test suite

- [x] **Step 1: Update documentation files**
- [x] **Step 2: Run full automated test suite (All 8 suites pass)**
- [x] **Step 3: Staged/Held without commit (User constraint: no commits)**
