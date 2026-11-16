# MRP Matrisi: Tam Ekran Grid ve Page-Head Kaldırma Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Material Requirement sayfasını dış sayfa kaydırmasından arındırıp `100vh` tam ekran grid düzenine geçirmek, `.page-head` alanını gizlemek, matris tablosu içinde bağımsız dikey (sağda) ve yatay (tabanda) scroll deneyimini sağlamak.

**Architecture:** `App.vue` içinde Frappe Desk container sınıflarının yüksekliği `calc(100vh - 48px)` olarak kilitlenir ve `.page-head` gizlenir. `MrpToolbar.vue` sabit üst araç çubuğu olarak tutulur. `MrpMatrixTable.vue` içerisindeki `.mrp-table-viewport` dikey ve yatay kaydırma konteyneri (`overflow: auto`) haline getirilerek `thead th` başlıkları `top: 0`, sol sütun `left: 0` konumuna sabitlenir.

**Tech Stack:** Vue 3, TypeScript, CSS (Flexbox & Sticky Positioning), Frappe Desk v15.

**Spec:** [`docs/superpowers/specs/2026-11-17-mrp-fullscreen-grid-viewport-design.md`](file:///d:/WEB_PROJECTS/erpnext/apps/erpnextkta/docs/superpowers/specs/2026-11-17-mrp-fullscreen-grid-viewport-design.md)

## Global Constraints
- Hedef SPA: `erpnextkta/public/material-requirement/`
- `.page-head` yalnızca `[data-page-route="material-requirement"]` rotasında gizlenmelidir; diğer Desk sayfaları etkilenmemelidir.
- Dış tarayıcı kaydırması (`body/html`) tamamen sıfırlanmalıdır.
- Başlık hücreleri (`th`) `top: 0` konumunda %100 opak kalmalıdır.
- 320px mobil ve tablet responsive uyumu korunmalıdır.
- Derleme kuralı: Yalnızca `bench build --app erpnextkta --production`.

---

### Task 1: Frappe Desk Canvas Sıfırlaması ve Sayfa Başlığının Kaldırılması (`frontend-public`)

**Files:**
- Modify: `erpnextkta/public/material-requirement/App.vue`

**Interfaces:**
- Produces: Tam ekran viewport kilidi, gizlenmiş `.page-head`, flex layout `.mrp-app-container`

- [x] **Step 1: Update `App.vue` style block**
  - Gizle: `[data-page-route="material-requirement"] .page-head { display: none !important; }`
  - Kilit: `[data-page-route="material-requirement"] body, .page-container, .page-content, .layout-main, .layout-main-section-wrapper, .layout-main-section, .page-body.container` için:
    - `overflow: hidden !important;`
    - `height: calc(100vh - var(--navbar-height, 48px)) !important;`
    - `max-height: calc(100vh - var(--navbar-height, 48px)) !important;`
    - `margin: 0 !important;`
    - `padding: 0 !important;`
  - `.mrp-app-container`:
    - `height: 100% !important;`
    - `max-height: 100% !important;`
    - `display: flex !important;`
    - `flex-direction: column !important;`
    - `overflow: hidden !important;`
    - `padding: 8px 12px 8px 12px !important;`

---

### Task 2: Araç Çubuğu ve Matris Tablosu Viewport Düzenlemesi (`frontend-public`)

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/MrpToolbar.vue`
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue`

**Interfaces:**
- Produces: Viewport konteynerinde bağımsız çalışan dikey ve yatay kaydırma, basitleştirilmiş `top: 0` ve `left: 0` sticky başlıkları.

- [x] **Step 1: Update `MrpToolbar.vue` styling**
  - `.mrp-toolbar`:
    - `position: static;` (veya `flex-shrink: 0;`)
    - `top` tanımlarını kaldır (çünkü üst `.mrp-app-container` artık kaymıyor, flex container içinde en üstte duruyor).
    - `margin-bottom: 8px;`

- [x] **Step 2: Update `MrpMatrixTable.vue` container and viewport styling**
  - `.mrp-matrix-container`:
    - `flex: 1;`
    - `min-height: 0;`
    - `display: flex;`
    - `flex-direction: column;`
    - `overflow: hidden;`
  - `.mrp-table-viewport`:
    - `flex: 1;`
    - `min-height: 0;`
    - `width: 100%;`
    - `height: 100%;`
    - `overflow-x: auto;`
    - `overflow-y: auto;`
  - Sticky Headers:
    - `.mrp-th-sticky-top`:
      - `position: sticky;`
      - `top: 0;` (karmaşık `calc(...)` kaldırılır, doğrudan viewport tepesine yapışır).
      - `z-index: 25;`
    - `.mrp-th-fixed.mrp-th-sticky-top`:
      - `position: sticky;`
      - `top: 0;`
      - `left: 0;`
      - `z-index: 35;`
    - `.mrp-th-fixed`:
      - `position: sticky;`
      - `left: 0;`
      - `z-index: 30;`
    - `.mrp-td-fixed`:
      - `position: sticky;`
      - `left: 0;`
      - `z-index: 10;`

---

### Task 3: Koordinatör Kalite Kapısı ve Üretim Derlemesi (Coordinator Quality Gate)

**Files:**
- Output bundles: `erpnextkta/dist/js/material-requirement.bundle.*.js`

- [x] **Step 1: Frontend Production Build**
  Run: `bench build --app erpnextkta --production`
  Expected: Code 0, clean build.

- [x] **Step 2: Restart Bench Services and Clear Cache**
  Run:
  `bench restart`
  `bench --site development.localhost clear-cache`
