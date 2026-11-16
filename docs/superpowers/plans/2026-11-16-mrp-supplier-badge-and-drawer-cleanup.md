# MRP Tedarikçi Rozeti, Çift Yüzde Düzeltmesi, Çekmece Sadeleştirmesi ve Çeviri Senkronizasyonu Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `tabItem` veritabanındaki 13.627 kalemde yer alan `%%100` hatasını kalıcı patch ve motor normalizasyonu ile düzeltmek, `MrpItemIdentity.vue`'da varsayılan tedarikçi adının (`Stocko Contact...`) düzgün görüntülenmesini sağlamak, Drawer'daki iç içe akordiyonu kaldırıp tek düz liste haline getirmek ve eksik İngilizce/Almanca çevirileri senkronize etmek.

**Architecture:** 
1. `overrides-hooks`: `patches/v15_0/fix_item_sourcing_strategy_percent.py` patch'i ile veritabanını temizler ve `patches.txt`'ye kaydeder.
2. `kta-mrp`: `kta_mrp/mrp_engine/supply.py` içinde `custom_sourcing_strategy` çıktısını defansif olarak `.replace("%%100", "%100")` ile garantiye alır.
3. `frontend-public`: `MrpItemIdentity.vue` içindeki strateji kontrolünü `!material.sourcing_strategy?.startsWith('Varsayılan Tedarikçi')` olarak günceller; `MrpPoReceiptList.vue` içindeki gereksiz iç içe akordiyon butonunu kaldırarak tüm teslimatları tek akıcı kart listesine bağlar.
4. `docs-i18n`: Eksik kalan tüm çeviri string'lerini `translations/en.csv`, `de.csv` ve `tr.csv` içine işler.

**Spec:** `docs/superpowers/specs/2026-11-16-mrp-supplier-badge-and-drawer-cleanup-design.md`

## Global Constraints
- `frontend-public`: Sadece `erpnextkta/public/**` yollarını düzenler; 500 satır sınırını aşamaz.
- `kta-mrp`: Sadece `erpnextkta/kta_mrp/**` yollarını düzenler.
- `overrides-hooks`: Sadece `erpnextkta/patches/**`, `patches.txt` yollarını düzenler.
- `docs-i18n`: Sadece `erpnextkta/translations/**` yollarını düzenler.
- Derleme doğrulaması istisnasız `bench build --app erpnextkta --production` ile yapılır.

---

### Task 1: Kalıcı Veritabanı Patch'i (`overrides-hooks`)

**Files:**
- Create: `erpnextkta/patches/v15_0/fix_item_sourcing_strategy_percent.py`
- Modify: `erpnextkta/patches.txt`

- [x] **Step 1: Patch dosyasını oluştur**
  `erpnextkta/patches/v15_0/fix_item_sourcing_strategy_percent.py`:
  ```python
  import frappe

  def execute():
      frappe.db.sql("""
          UPDATE `tabItem`
          SET custom_sourcing_strategy = 'Varsayılan Tedarikçi (%100)'
          WHERE custom_sourcing_strategy = 'Varsayılan Tedarikçi (%%100)'
      """)
  ```

- [x] **Step 2: `patches.txt` dosyasına kaydet ve çalıştır**
  `erpnextkta/patches.txt` sonuna ekle:
  `erpnextkta.patches.v15_0.fix_item_sourcing_strategy_percent`
  Komut: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost migrate`

- [x] **Step 3: Commit**

---

### Task 2: MRP Motoru Normalizasyonu (`kta-mrp`)

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/supply.py`

- [x] **Step 1: `supply.py:474` içinde `d.custom_sourcing_strategy` çıktısını temizle**
  ```python
  raw_strat = d.custom_sourcing_strategy or "Varsayılan Tedarikçi (%100)"
  cleaned_strat = raw_strat.replace("%%100", "%100")
  ```

- [x] **Step 2: MRP motoru testlerini çalıştır**
  `bench --site development.localhost run-tests --app erpnextkta --module erpnextkta.kta_mrp.tests.test_service`

- [x] **Step 3: Commit**

---

### Task 3: Frontend Tedarikçi Rozeti ve Çekmece Sadeleştirmesi (`frontend-public`)

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpItemIdentity.vue`
- Modify: `erpnextkta/public/material-requirement/components/accordion/MrpPoReceiptList.vue`

- [x] **Step 1: `MrpItemIdentity.vue` içindeki strateji / tedarikçi kontrolünü güncelle**
  `v-else-if="material.sourcing_strategy && !material.sourcing_strategy.startsWith('Varsayılan Tedarikçi')"`

- [x] **Step 2: `MrpPoReceiptList.vue` içindeki iç içe akordiyon butonunu kaldır**
  `mrp-antrepo-pool-section` altındaki açılır-kapanır butonu kaldır, antrepo havuzundaki teslimatları da ana açık teslimat kartları listesine dahil et veya net statik kart grubu olarak göster.

- [x] **Step 3: Üretim derlemesini doğrula**
  `bench build --app erpnextkta --production`

- [x] **Step 4: Commit**

---

### Task 4: Çeviri Senkronizasyonu (`docs-i18n`)

**Files:**
- Modify: `erpnextkta/translations/en.csv`
- Modify: `erpnextkta/translations/de.csv`
- Modify: `erpnextkta/translations/tr.csv`

- [x] **Step 1: Eksik çeviri çiftlerini CSV dosyalarına ekle**
- [x] **Step 2: Çevirileri derle**
  `bench build --app erpnextkta --production`
- [x] **Step 3: Commit**

---

### Task 5: Koordinatör Kalite Kapısı ve Doğrulama
- 10024373 nolu kalemin API ve arayüz çıktısının doğrulanması.
- `bench build --app erpnextkta --production` doğrulaması.
- Ruff ve Git durumu kontrolü.
