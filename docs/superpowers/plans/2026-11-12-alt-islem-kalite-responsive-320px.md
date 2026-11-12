# Alt İşlem ve Kalite Responsive UI (<= 320px) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 320px ve altındaki ultra dar ekranlarda (operatör el terminalleri ve küçük mobil ekranlar) Çalışma Kartı'nın Alt İşlem ve Kalite sekmelerindeki yatay taşmaları (horizontal overflow) sıfırlamak ve butonları dikey yığınlanan ergonomik dokunmatik hedeflere dönüştürmek.

**Architecture:** Vue 3 scoped CSS medya sorguları (`@media (max-width: 480px)`, `@media (max-width: 360px)`, `@media (max-width: 320px)`) ve şablon iyileştirmeleri ile: 10 haneli kalıp numaraları 22px dev kutudan çıkarılıp başlık altına çip olarak alınır; aksiyon ve kalite onay butonları alt satırda tam genişlikte (`width: 100%`) esnek butonlara dönüştürülür; enjeksiyon ölçüm ızgarası dar ekranlarda sıkışmayı önleyen padding/font ölçeklemesine kavuşturulur.

**Tech Stack:** Vue 3, TypeScript, Vanilla CSS (scoped), Frappe Framework v15, Vite.

**Spec:** `docs/superpowers/specs/2026-11-12-alt-islem-kalite-responsive-320px-design.md`

## Global Constraints

* Target Branch: `feat/enjeksiyon-kalip-no` / `main`.
* Commit Message Convention: Conventional Commits (`fix(view-calisma-karti): ...`, `style(view-calisma-karti): ...`).
* Build Rule: NEVER use `yarn build` directly. ALWAYS use `bench build --app erpnextkta --production`.
* Desktop & Tablet Guarantee: Screens > 480px must retain their exact existing layout, font sizes, and spacing without regressions.

## Review Focus

1. **Ultra Narrow Viewport (320px / 280px):** On 320px width, document body and cards must not trigger any horizontal scrollbar (`overflow-x`).
2. **10-Digit Mold Number (`8718645633`):** When `satir_no` is absent, the mold number must render as a readable metadata pill under the title, not in a 22px fixed bold circle badge.
3. **Accordion Chevron Access:** In mobile collapsed and expanded states, the accordion toggle button must remain accessible and cleanly aligned without clipping or overlapping the title.
4. **Touch Target Sizing:** Action buttons (`Kalite Onayı Ver`, `Reddet`, `Düzenle`, `Sil`) must remain at least 36px tall and easy to tap with gloved fingers on rugged terminals.
5. **No Desktop Regressions:** The desktop views (Krimp, Enjeksiyon, Alt Operasyon) must maintain side-by-side flex headers and status badges.

---

### Task 1: `AltOperasyonView.vue` Responsive Layout & Mold Pill Optimization

**Files:**
- Modify: `erpnextkta/public/view-calisma-karti/views/AltOperasyonView.vue:266-352,388-424`

**Interfaces:**
- Updates row display logic: Only `h.satir_no` renders the 22px left number box. `h.kalip_no` renders as a chip/sub-line under the title.
- Updates mobile CSS: `@media (max-width: 480px)` and `@media (max-width: 340px)` for full-width action buttons and comfortable spacing.

- [x] **Step 1: Update template in `AltOperasyonView.vue`**
Only render the large left box if `h.satir_no` is present. When `h.kalip_no` is present without `satir_no`, display it cleanly under the title as a mold pill:
```html
<div v-if="h.satir_no" class="ck-satir-badge">
    <span>{{ h.satir_no }}</span>
</div>
<div class="ck-mini-content">
    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
        <b class="ck-mini-title">{{ __(h.alt_operasyon_title || h.alt_operasyon) }}</b>
        <span v-if="h.kalip_no" class="ck-mold-pill">🏷️ {{ h.kalip_no }}</span>
    </div>
```

- [x] **Step 2: Update styles in `AltOperasyonView.vue`**
Add responsive rules for `.ck-mini-item`, `.ck-mini-actions`, `.ck-satir-badge`, and `.ck-mold-pill`:
```css
.ck-satir-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-right: 12px;
  border-right: 2px solid var(--ck-glass-border-soft);
  margin-right: 4px;
  font-size: 22px;
  font-weight: 900;
  color: var(--ck-text);
  opacity: 0.9;
  flex-shrink: 0;
}
.ck-mold-pill {
  font-size: 11px;
  font-weight: 700;
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  padding: 1px 6px;
  border-radius: 6px;
  color: var(--ck-text);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
@media (max-width: 480px) {
  .ck-mini-item {
    flex-direction: column;
    align-items: stretch;
    padding: 12px 10px;
    gap: 10px;
  }
  .ck-mini-actions {
    width: 100%;
    display: flex;
    gap: 6px;
  }
  .ck-mini-actions > * {
    flex: 1;
    text-align: center;
    justify-content: center;
  }
}
@media (max-width: 340px) {
  .ck-mini-item {
    padding: 10px 8px;
  }
  .ck-btn-small {
    padding: 6px 8px;
    font-size: 12px;
  }
}
```

- [x] **Step 3: Run production build check**
Run: `bench build --app erpnextkta --production`
Expected: Build succeeds with exit code 0.

- [x] **Step 4: Commit**
```bash
git add erpnextkta/public/view-calisma-karti/views/AltOperasyonView.vue
git commit -m "fix(view-calisma-karti): make alt operasyon list responsive for 320px screens"
```

---

### Task 2: `AltOperasyonKaliteSection.vue` Vertical Stacking & Actions Optimization

**Files:**
- Modify: `erpnextkta/public/view-calisma-karti/components/AltOperasyonKaliteSection.vue:46-93,132-177`

**Interfaces:**
- Solves horizontal overflow in general sub-operation QC list by stacking row details and QC action buttons vertically on mobile.
- Ensures 10-digit mold numbers do not consume fixed 22px column.

- [x] **Step 1: Update template in `AltOperasyonKaliteSection.vue`**
Only show large circle for `h.satir_no`. Show `h.kalip_no` as a metadata pill next to or under title:
```html
<div v-if="h.satir_no" class="ck-satir-badge">
  <span>{{ h.satir_no }}</span>
</div>
<div class="ck-mini-content">
  <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
    <b class="ck-mini-title">{{ __(h.title || h.alt_operasyon_title || h.alt_operasyon) }}</b>
    <span v-if="h.kalip_no" class="ck-mold-pill">🏷️ {{ h.kalip_no }}</span>
  </div>
  <div class="ck-muted ck-mini-sub" v-if="h.hammadde"><b>{{ __("Hammadde") }}:</b> {{ h.hammadde }}</div>
</div>
```

- [x] **Step 2: Add responsive mobile styles in `AltOperasyonKaliteSection.vue`**
Add media query for `@media (max-width: 480px)`:
```css
@media (max-width: 480px) {
  .ck-mini-item {
    flex-direction: column;
    align-items: stretch;
    padding: 12px 10px;
    gap: 10px;
  }
  .ck-mini-actions {
    width: 100%;
    flex-wrap: wrap;
    gap: 6px;
  }
  .ck-mini-actions .ck-btn {
    flex: 1 1 calc(50% - 6px);
    text-align: center;
    padding: 8px 6px;
    font-size: 12px;
  }
  .ck-mini-actions .ck-badge {
    width: 100%;
    text-align: center;
    box-sizing: border-box;
  }
}
@media (max-width: 340px) {
  .ck-mini-item {
    padding: 10px 8px;
  }
  .ck-mini-actions .ck-btn {
    font-size: 11px;
    padding: 6px 4px;
  }
}
```

- [x] **Step 3: Run production build check**
Run: `bench build --app erpnextkta --production`
Expected: Build succeeds with exit code 0.

- [x] **Step 4: Commit**
```bash
git add erpnextkta/public/view-calisma-karti/components/AltOperasyonKaliteSection.vue
git commit -m "fix(view-calisma-karti): stack QC action buttons on mobile in alt operasyon kalite section"
```

---

### Task 3: `EnjeksiyonSection.vue` Accordion Header & Parameter Grid Responsive Optimization

**Files:**
- Modify: `erpnextkta/public/view-calisma-karti/components/EnjeksiyonSection.vue:245-312,596-762`

**Interfaces:**
- Refactors `.ck-accordion-header` on `@media (max-width: 480px)` to stack left title/details and right QC actions/date vertically, positioning toggle chevron cleanly on top-right.
- Refactors `.ck-enjeksiyon-grid` to prevent parameter text clipping on `<= 340px` screens.

- [x] **Step 1: Update accordion header template in `EnjeksiyonSection.vue`**
Only show large 22px badge for `ao.satir_no`. Display `ao.kalip_no` as a clear pill tag. Position chevron button appropriately on mobile:
```html
<div class="ck-accordion-left">
  <div v-if="ao.satir_no" class="ck-satir-badge">
    <span>{{ ao.satir_no }}</span>
  </div>
  <div class="ck-accordion-title-col">
    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
      <span class="ck-op-title">{{ __(ao.title || ao.alt_operasyon_title || ao.alt_operasyon) }}</span>
      <span v-if="ao.kalip_no" class="ck-mold-pill">🏷️ {{ ao.kalip_no }}</span>
    </div>
    ...
  </div>
</div>
```

- [x] **Step 2: Add responsive styles in `EnjeksiyonSection.vue`**
Add media queries for `@media (max-width: 480px)` and `@media (max-width: 340px)`:
```css
@media (max-width: 480px) {
  .ck-accordion-header {
    flex-direction: column;
    align-items: stretch;
    position: relative;
    padding-right: 28px;
    gap: 8px;
  }
  .ck-accordion-toggle-btn {
    position: absolute;
    right: 0;
    top: 0;
    padding: 6px;
  }
  .ck-accordion-right {
    width: 100%;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
    border-top: 1px dashed var(--ck-glass-border-soft);
    padding-top: 8px;
  }
  .ck-accordion-right .ck-btn {
    flex: 1 1 calc(50% - 6px);
    text-align: center;
  }
}
@media (max-width: 340px) {
  .ck-enjeksiyon-grid {
    gap: 6px;
  }
  .ck-enjeksiyon-box {
    padding: 4px 6px;
    min-width: 0;
  }
  .ck-enjeksiyon-box span {
    font-size: 9px;
    word-break: break-word;
  }
  .ck-enjeksiyon-box b {
    font-size: 13px;
  }
  .ck-target-val {
    font-size: 8.5px !important;
  }
}
```

- [x] **Step 3: Run production build check**
Run: `bench build --app erpnextkta --production`
Expected: Build succeeds with exit code 0.

- [x] **Step 4: Commit**
```bash
git add erpnextkta/public/view-calisma-karti/components/EnjeksiyonSection.vue
git commit -m "fix(view-calisma-karti): make enjeksiyon accordion header and parameter grid responsive at 320px"
```

---

### Task 4: `KrimpSection.vue` Accordion Header Mobile Alignment

**Files:**
- Modify: `erpnextkta/public/view-calisma-karti/components/KrimpSection.vue:110-178,540-575`

**Interfaces:**
- Ensures Krimp section accordion headers follow the same robust vertical-stacking pattern on `@media (max-width: 480px)` and `<= 320px`.

- [x] **Step 1: Add mobile media queries to `KrimpSection.vue`**
```css
@media (max-width: 480px) {
  .ck-accordion-header {
    flex-direction: column;
    align-items: stretch;
    position: relative;
    padding-right: 28px;
    gap: 8px;
  }
  .ck-accordion-toggle-btn {
    position: absolute;
    right: 0;
    top: 0;
    padding: 6px;
  }
  .ck-accordion-right {
    width: 100%;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
    border-top: 1px dashed var(--ck-glass-border-soft);
    padding-top: 8px;
  }
  .ck-accordion-right .ck-btn {
    flex: 1 1 calc(50% - 6px);
    text-align: center;
  }
}
```

- [x] **Step 2: Run production build check**
Run: `bench build --app erpnextkta --production`
Expected: Build succeeds with exit code 0.

- [x] **Step 3: Commit**
```bash
git add erpnextkta/public/view-calisma-karti/components/KrimpSection.vue
git commit -m "fix(view-calisma-karti): align krimp accordion header layout on mobile screens"
```

---

### Task 5: Final Comprehensive Verification

**Files:**
- All modified Vue components

- [x] **Step 1: Run production build**
Run: `bench build --app erpnextkta --production`
Expected: Exit code 0, 0 build errors.

- [x] **Step 2: Run backend test suites**
Run: `/home/frappe/frappe-bench/env/bin/python -m unittest erpnextkta.tests.test_enjeksiyon_kalip_full`
Expected: All 4 tests PASS.

- [x] **Step 3: Update documentation and mark all tasks complete**
Update plan checklist with `- [x]`.
Commit: `docs: mark 320px responsive UI plan complete`.
