# MRP Material Requirement Desk Tema Harmonizasyonu ve Responsive 320px Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `erpnextkta/public/material-requirement` altındaki Vue 3 SPA uygulamasını Frappe Desk (`desk.bundle.css`) ve KTA (`erpnextkta.bundle.css`) renk değişkenleriyle senkronize etmek, lojistik durum rozetlerini birbirinden kesin olarak ayrıştırmak, tablo okunabilirliğini %100 opak zeminlerle korumak ve en az 320px mobil genişlik desteği kazandırmak.

**Architecture:** `App.vue` üzerinde `--mrp-*` CSS token'ları doğrudan Frappe Desk ve KTA native değişkenlerine (`--bg-color`, `--card-bg`, `--control-bg`, `--border-color`, `--text-color`, `--text-muted`, vb.) bağlanır. Toolbar, popover ve drawer bileşenlerine KTA cam efekti (`backdrop-filter: blur(8px)`) uygulanırken; matris tablosunun dondurulmuş sol sütunu ve yapışkan başlıkları kaydırma sırasında metin karmaşası olmaması için opak tutulur. 8 lojistik rozeti birbirinden ayrık renk spektrumlarına taşınır. 320px dar mobil ekranlar için responsive flex-wrap ve medya sorguları eklenir.

**Tech Stack:** Vue 3 (Composition API, `<script setup>`), TypeScript, CSS Custom Properties (Frappe / KTA Desk Theme), esbuild (`bench build`).

**Spec:** `docs/superpowers/specs/2026-11-16-mrp-desk-theme-harmonization-design.md`

## Global Constraints
- Her `.vue` dosyası 500 satır sınırını aşamaz.
- Kullanıcıya görünen metinlerde `const __ = (...args) => (window as any).__(...args);` kullanılmalıdır.
- Tüm tasarımlar en dar mobil genişlik olan 320px'den masaüstüne kadar kesintisiz ve yatay taşma olmadan çalışmalıdır.
- Lojistik durum rozetleri (PO, Yolda, Antrepo, Gümrük, Uyuşmazlık, Stok, Eksik, Kota) birbirine asla benzer tonlarda olamaz.
- Dondurulmuş tablo başlıkları ve sütunları kaydırma sırasında arkadaki hücreleri göstermeyecek şekilde %100 opak kalmalıdır.
- Derleme komutu kuralı: Yalnızca `bench build --app erpnextkta --production` çalıştırılır.

## Review Focus
1. **Dark Mod Metin Kontrastı:** Frappe Desk karanlık moda alındığında gri veya renkli metinlerin görünmez hale gelmemesi veya düşük kontrast oluşturmaması.
2. **Tablo Dondurulmuş Başlık/Sütun Opaklığı:** Yatay ve dikey kaydırma esnasında dondurulmuş sol sütun (`MrpItemIdentity`) ve sütun başlıklarının arkasındaki hücrelerin transparan görünmemesi.
3. **Rozet Ayrışımı:** PO (İndigo), Yolda (Amber), Antrepo (Sky Blue), Gümrük (Turuncu) ve Uyuşmazlık (Kırmızı) rozetlerinin yan yana geldiğinde plancılar tarafından anında ayırt edilebilmesi.
4. **320px Ekran Düzeni:** 320px genişlikte Toolbar'daki filtre butonlarının ve arama kutusunun yatay scroll taşması yapmadan alt alta sarmalanması.
5. **Yan Çekmece (Drawer) Mobil Genişliği:** 320px-576px ekranlarda çekmecenin ekran dışına taşmayıp `max-width: 100vw` ile tam ekrana oturması.

---

### Task 1: `App.vue` Tema Değişkenleri ve Glassmorphism Temeli

**Files:**
- Modify: `erpnextkta/public/material-requirement/App.vue`

**Interfaces:**
- Consumes: Frappe Desk CSS değişkenleri (`--bg-color`, `--card-bg`, `--control-bg`, `--border-color`, `--text-color`, `--text-muted`, `--primary`)
- Produces: Global `--mrp-*` tasarım token'ları ve cam yardımcıları (`--mrp-glass-bg`, `--mrp-glass-blur`)

- [x] **Step 1: `App.vue` içindeki harici Tailwind Slate renklerini Frappe Desk CSS değişkenleriyle eşleştir**
  - Light mode:
    ```css
    --mrp-bg: var(--bg-color, #f0f2f5);
    --mrp-card-bg: var(--card-bg, #ffffff);
    --mrp-card-subtle: var(--control-bg, #f3f3f3);
    --mrp-text: var(--text-color, #171717);
    --mrp-text-muted: var(--text-muted, #7c7c7c);
    --mrp-border: var(--border-color, #ededed);
    --mrp-border-subtle: var(--border-color, #f3f3f3);
    --mrp-header-bg: var(--subtle-accent, #f8f8f8);
    --mrp-current-week-header-bg: rgba(99, 102, 241, 0.08);
    --mrp-cell-hover: rgba(99, 102, 241, 0.06);
    --mrp-cell-selected: rgba(99, 102, 241, 0.15);
    --mrp-table-zebra: rgba(255, 255, 255, 0.6);
    --mrp-glass-bg: rgba(255, 255, 255, 0.82);
    --mrp-glass-blur: blur(8px);
    ```
  - Dark mode (`[data-theme="dark"]`, `body.dark`, `html.dark`):
    ```css
    --mrp-bg: var(--bg-color, #0c111b);
    --mrp-card-bg: var(--card-bg, #171717);
    --mrp-card-subtle: var(--control-bg, #232323);
    --mrp-text: var(--text-color, #f8f8f8);
    --mrp-text-muted: var(--text-muted, #c7c7c7);
    --mrp-border: var(--border-color, #282828);
    --mrp-border-subtle: var(--border-color, #1f1f1f);
    --mrp-header-bg: var(--control-bg, #1c1c1c);
    --mrp-current-week-header-bg: rgba(129, 140, 248, 0.15);
    --mrp-cell-hover: rgba(129, 140, 248, 0.1);
    --mrp-cell-selected: rgba(129, 140, 248, 0.25);
    --mrp-table-zebra: rgba(25, 25, 25, 0.5);
    --mrp-glass-bg: rgba(23, 23, 23, 0.85);
    --mrp-glass-blur: blur(10px);
    ```
  - `page-head` pinned kurallarını ve tam genişlik tuval resetlerini koruyarak güncelle.

- [x] **Step 2: Derleme kontrolü yap**
  Run: `docker exec -u frappe erpnext-dev-frappe-1 bash -c "bench build --app erpnextkta --production"`
  Expected: PASS (0 error)

- [x] **Step 3: Commit**
  ```bash
  git add erpnextkta/public/material-requirement/App.vue
  git commit -m "feat(mrp): bind mrp semantic tokens to frappe desk css variables"
  ```

---

### Task 2: `MrpToolbar.vue` ve `MrpFilterPopover.vue` Cam Stili ve 320px Responsive Uyumu

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/MrpToolbar.vue`
- Modify: `erpnextkta/public/material-requirement/components/MrpFilterPopover.vue`

**Interfaces:**
- Consumes: `--mrp-glass-bg`, `--mrp-glass-blur`, `--mrp-border`, `--mrp-text`, `--mrp-card-subtle`
- Produces: 320px responsive araç çubuğu ve popover filtreler

- [x] **Step 1: `MrpToolbar.vue` stillerini KTA cam efekti ve Frappe Desk form bileşenlerine dönüştür**
  - `.mrp-toolbar`: `background: var(--mrp-glass-bg); backdrop-filter: var(--mrp-glass-blur); border-bottom: 1px solid var(--mrp-border);`
  - `.mrp-search-input`: Frappe `form-control` stilinde `background: var(--mrp-card-bg); color: var(--mrp-text); border: 1px solid var(--mrp-border); border-radius: 8px;`
  - `.mrp-chip-btn`: Standart `background: var(--mrp-card-bg); color: var(--mrp-text); border: 1px solid var(--mrp-border);`
  - Ayrışık aktif çip renkleri: Antrepo (Sky Blue `#0284c7`), Gümrük (Turuncu `#ea580c`), Yolda (Amber `#d97706`), Uyuşmazlık (Kırmızı `#dc2626`).

- [x] **Step 2: `MrpToolbar.vue` için 320px responsive kuralları ekle**
  - `.mrp-toolbar`: `flex-wrap: wrap; height: auto; min-height: var(--mrp-toolbar-height, 48px); padding: 8px 12px; gap: 8px;`
  - `@media (max-width: 576px)` ve `@media (max-width: 320px)`:
    - `.mrp-search-box`: `width: 100%; min-width: 0;`
    - `.mrp-toolbar-left, .mrp-toolbar-middle, .mrp-toolbar-right`: `width: 100%; justify-content: flex-start; gap: 6px;`
    - `.mrp-view-selector-wrap`: `width: 100%; justify-content: space-between;`

- [x] **Step 3: `MrpFilterPopover.vue` stillerini ve responsive genişliğini güncelle**
  - Popover kartı: `background: var(--mrp-glass-bg); backdrop-filter: blur(16px); border: 1px solid var(--mrp-border); box-shadow: var(--card-shadow);`
  - Mobil genişlik kısıtı: `width: 340px; max-width: calc(100vw - 24px);`

- [x] **Step 4: Derleme kontrolü yap**
  Run: `docker exec -u frappe erpnext-dev-frappe-1 bash -c "bench build --app erpnextkta --production"`
  Expected: PASS

- [x] **Step 5: Commit**
  ```bash
  git add erpnextkta/public/material-requirement/components/MrpToolbar.vue erpnextkta/public/material-requirement/components/MrpFilterPopover.vue
  git commit -m "feat(mrp): add glassmorphism and 320px responsive layout to toolbar and filter popover"
  ```

---

### Task 3: `MrpMatrixTable.vue` Opak Başlık/Sütun Koruması ve Tema Uyumlaştırması

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue`

**Interfaces:**
- Consumes: `--mrp-header-bg`, `--mrp-card-bg`, `--mrp-border`, `--mrp-cell-hover`
- Produces: Kaydırma sırasında transparanlık hatası vermeyen %100 opak dondurulmuş matris tablosu

- [x] **Step 1: Dondurulmuş başlık ve sol sütun arka planlarını tam opak kıl**
  - `.mrp-th-sticky-top`: `background: var(--mrp-header-bg); border-bottom: 2px solid var(--mrp-border); z-index: 25;`
  - `.mrp-th-fixed`: `background: var(--mrp-header-bg); border-right: 2px solid var(--mrp-border); z-index: 30;`
  - `.mrp-th-fixed.mrp-th-sticky-top`: `z-index: 35; background: var(--mrp-header-bg);`
  - `.mrp-td-fixed`: `background: var(--mrp-card-bg); border-right: 2px solid var(--mrp-border); border-bottom: 1px solid var(--mrp-border); z-index: 10;`
  - `.mrp-row-main:hover .mrp-td-fixed`: `background: var(--mrp-cell-hover);`
  - Saydam/yarı saydam arka plan tanımlarını (`rgba` veya transparan) bu sınıflardan tamamen kaldır.

- [x] **Step 2: Tablo çizgileri, sıralama göstergeleri ve akıcı mobil kaydırma desteği**
  - `.mrp-table-viewport`: `overflow-x: auto; -webkit-overflow-scrolling: touch; width: 100%;`
  - `.mrp-th-week`: `border-right: 1px solid var(--mrp-border); color: var(--mrp-text);`
  - Hafta başlığı geçerli hafta rozeti (`.mrp-current-badge`): Frappe primary/indigo tonlarında uyumlu kontrast.

- [x] **Step 3: Derleme kontrolü yap**
  Run: `docker exec -u frappe erpnext-dev-frappe-1 bash -c "bench build --app erpnextkta --production"`
  Expected: PASS

- [x] **Step 4: Commit**
  ```bash
  git add erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue
  git commit -m "fix(mrp): enforce opaque backgrounds on frozen columns and headers in matrix table"
  ```

---

### Task 4: `MrpWeekCell.vue` ve `MrpItemIdentity.vue` Ayrışık Rozet Renk Spektrumu

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpWeekCell.vue`
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpItemIdentity.vue`

**Interfaces:**
- Consumes: Durum kategorileri (`po`, `yolda`, `antrepoda`, `gumruklemede`, `uyusmazlikta`, `free_stock`, `urgent`, `quota`)
- Produces: Asla birbirine benzemeyen, yüksek kontrastlı ve dark/light uyumlu 8 rozet stili

- [x] **Step 1: `MrpWeekCell.vue` rozetlerini ayrışık spektruma uyarla**
  - `.mrp-pill-po`:
    - Light: `color: #4338ca; background: #eef2ff; border: 1px solid rgba(67, 56, 202, 0.3);` (İndigo)
    - Dark: `color: #a5b4fc; background: rgba(99, 102, 241, 0.2); border: 1px solid rgba(165, 180, 252, 0.3);`
  - `.mrp-pill-yolda`:
    - Light: `color: #b45309; background: #fef3c7; border: 1px solid rgba(180, 83, 9, 0.3);` (Amber / Altın Sarısı)
    - Dark: `color: #fcd34d; background: rgba(245, 158, 11, 0.2); border: 1px solid rgba(252, 211, 77, 0.3);`
  - `.mrp-pill-antrepo`:
    - Light: `color: #0369a1; background: #e0f2fe; border: 1px solid rgba(3, 105, 161, 0.3);` (Sky Blue / Camgöbeği)
    - Dark: `color: #7dd3fc; background: rgba(14, 165, 233, 0.2); border: 1px solid rgba(125, 211, 252, 0.3);`
  - `.mrp-pill-gumruk`:
    - Light: `color: #c2410c; background: #ffedd5; border: 1px solid rgba(194, 65, 12, 0.3);` (Canlı Turuncu)
    - Dark: `color: #fdba74; background: rgba(249, 115, 22, 0.2); border: 1px solid rgba(253, 186, 116, 0.3);`
  - `.mrp-pill-dispute`:
    - Light: `color: #b91c1c; background: #fee2e2; border: 1px solid rgba(185, 28, 28, 0.3);` (Koyu Kırmızı)
    - Dark: `color: #fca5a5; background: rgba(239, 68, 68, 0.25); border: 1px solid rgba(252, 165, 165, 0.3);`

- [x] **Step 2: `MrpItemIdentity.vue` etiketlerini (`.mrp-tag-*`) aynı spektrumla eşleştir**
  - `.mrp-tag-stock`: Light `#15803d` / `#dcfce7`; Dark `#86efac` / `rgba(34, 197, 94, 0.2)` (Zümrüt Yeşili)
  - `.mrp-badge-urgent`: Light `#be123c` / `#ffe4e6`; Dark `#fda4af` / `rgba(244, 63, 94, 0.25)` (Kızıl Gül / Coral)
  - `.mrp-tag-quota`: Light `#7e22ce` / `#f3e8ff`; Dark `#d8b4fe` / `rgba(168, 85, 247, 0.2)` (Menekşe Moru)
  - Pipeline etiketleri (`.mrp-tag-po`, `.mrp-tag-yolda`, `.mrp-tag-antrepo`, `.mrp-tag-gumruk`, `.mrp-tag-dispute`) Step 1'deki tam renk ve kenarlık eşleşmesini alsın.
  - `.mrp-item-code-link`: KTA primary indigo rengi (`#6366f1` / `#818cf8`).

- [x] **Step 3: Derleme kontrolü yap**
  Run: `docker exec -u frappe erpnext-dev-frappe-1 bash -c "bench build --app erpnextkta --production"`
  Expected: PASS

- [x] **Step 4: Commit**
  ```bash
  git add erpnextkta/public/material-requirement/components/matrix/MrpWeekCell.vue erpnextkta/public/material-requirement/components/matrix/MrpItemIdentity.vue
  git commit -m "feat(mrp): harmonize distinct high-contrast badge spectrum for all supply stages"
  ```

---

### Task 5: `MrpDetailDrawer.vue` Cam Stili ve 320px Tam Ekran Mobil Desteği

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/drawer/MrpDetailDrawer.vue`

**Interfaces:**
- Consumes: `--mrp-glass-bg`, `--mrp-border`, `--mrp-text`, `--card-shadow`
- Produces: 320px mobilde taşmayan tam ekran yan çekmece

- [x] **Step 1: Çekmece paneline KTA cam efekti ve Frappe Desk renklerini uygula**
  - `.mrp-drawer-panel`: `background: var(--mrp-glass-bg); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-left: 1px solid var(--mrp-border); box-shadow: var(--card-shadow); color: var(--mrp-text);`
  - `.mrp-drawer-header`: `border-bottom: 1px solid var(--mrp-border); background: var(--mrp-header-bg);`
  - `.mrp-tab-btn.active`: Frappe primary/indigo vurgusu ve açık/koyu mod uyumlu metin rengi.

- [x] **Step 2: 320px responsive genişlik kuralını ekle**
  - `.mrp-drawer-panel`:
    ```css
    width: 520px;
    max-width: 100vw;
    ```
  - `@media (max-width: 576px)` ve `@media (max-width: 320px)`:
    - `.mrp-drawer-panel`: `width: 100vw; max-width: 100vw; border-left: none;`
    - `.mrp-drawer-header`: `padding: 10px 12px;`
    - `.mrp-drawer-body`: `padding: 12px 10px;`

- [x] **Step 3: Derleme kontrolü yap**
  Run: `docker exec -u frappe erpnext-dev-frappe-1 bash -c "bench build --app erpnextkta --production"`
  Expected: PASS

- [x] **Step 4: Commit**
  ```bash
  git add erpnextkta/public/material-requirement/components/drawer/MrpDetailDrawer.vue
  git commit -m "feat(mrp): apply frosted glass style and 320px mobile full-width to detail drawer"
  ```

---

### Task 6: Koordinatör Kalite Kapısı ve Nihai Doğrulama

**Files:**
- Verification: `erpnextkta/public/material-requirement/**`

- [x] **Step 1: Üretim derlemesi doğrulaması**
  Run: `docker exec -u frappe erpnext-dev-frappe-1 bash -c "bench build --app erpnextkta --production"`
  Expected: `material-requirement.bundle.*.js` ve `.css` başarıyla üretilmeli, hata kodu 0 olmalı.

- [x] **Step 2: Python / Ruff kontrolleri**
  Run: `docker exec -u frappe erpnext-dev-frappe-1 bash -c "/home/frappe/frappe-bench/env/bin/ruff check erpnextkta/kta_mrp"`
  Expected: All checks passed.

- [x] **Step 3: Nihai Git durumu kontrolü ve özet raporu**
  Run: `git status`
  Expected: Temiz çalışma dizini, planlanan tüm commit'ler atılmış.
