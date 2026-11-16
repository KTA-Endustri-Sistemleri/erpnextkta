# Malzeme İhtiyacı (MRP) Matrisi: Side Drawer ve %100 Light/Dark Tema Uyumu Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the in-table accordion in Material Requirement Planning (`material-requirement` Vue 3 SPA) into a non-modal right-side drawer and achieve 100% Light & Dark theme compliance across all 8 SPA components.

**Architecture:** 
1. State Management: Expand `useMrpState.ts` with `isDrawerOpen`, `drawerItemCode`, `drawerWeekKey`, `openDrawer()`, `closeDrawer()`, and `setDrawerWeek()`.
2. Component Decoupling: Create `components/drawer/MrpDetailDrawer.vue` (`<Teleport to="body">`, fixed right-side overlay without dark backdrop, scrollable week metrics, PO receipts, pegging, and supplier distribution).
3. Accordion Deactivation: Disable the in-table accordion row in `MrpMatrixTable.vue` without deleting existing code; route cell and item identity clicks to `openDrawer()`.
4. Theme System: Define semantic CSS variables in `App.vue` (`--mrp-bg`, `--mrp-card-bg`, `--mrp-text`, `--mrp-border`, `--mrp-cell-hover`, etc.) under `:root`, `[data-theme="light"]`, and `[data-theme="dark"]`; refactor all 8 components to use these variables instead of hardcoded hex values.

**Tech Stack:** Vue 3 (Composition API), TypeScript, Frappe Framework UI / Assets Pipeline, CSS Variables.

**Spec:** [docs/superpowers/specs/2026-11-16-mrp-matrix-side-drawer-design.md](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/superpowers/specs/2026-11-16-mrp-matrix-side-drawer-design.md)

## Global Constraints

- Target branch is `feat/mrp-modular-refactor`.
- Do not delete existing accordion code in `MrpMatrixTable.vue`; comment out or disable via `v-if="false"`.
- `MrpDetailDrawer.vue` and `MrpMatrixTable.vue` must stay strictly under 500 lines.
- Build command strictly: `bench build --app erpnextkta --production` (never direct package manager commands).
- Full Light and Dark theme compliance with zero hardcoded backgrounds or invisible texts in `[data-theme="dark"]`.

## Review Focus

- Non-modal interaction: Table cells must remain clickable while the drawer is open without requiring the user to close the drawer first.
- Default week resolution: Opening the drawer from an item identity click without a `weekKey` must resolve to `first_shortage_week` or `is_current` week.
- Component isolation: Modal teleportation `<Teleport to="body">` must not cause scrollbar duplication or body layout shifts.
- Contrast verification: In dark mode, check pills, status badges, table borders, and nested accordion lists for legibility.
- Line limit enforcement: Verify `wc -l` on modified and newly created `.vue` files.

---

### Task 1: Extend State Management for Side Drawer in `useMrpState.ts`

**Files:**
- Modify: `erpnextkta/public/material-requirement/composables/useMrpState.ts`

**Interfaces:**
- Produces:
  - `isDrawerOpen`: `Ref<boolean>`
  - `drawerItemCode`: `Ref<string | null>`
  - `drawerWeekKey`: `Ref<string | null>`
  - `openDrawer(itemCode: string, weekKey?: string): void`
  - `closeDrawer(): void`
  - `setDrawerWeek(weekKey: string): void`
  - `selectedDrawerMaterial`: `ComputedRef<MaterialRequirementItem | null>`

- [ ] **Step 1: Add drawer state and functions to `useMrpState.ts`**

In `erpnextkta/public/material-requirement/composables/useMrpState.ts`:
- Define reactive refs:
  ```typescript
  const isDrawerOpen = ref(false);
  const drawerItemCode = ref<string | null>(null);
  const drawerWeekKey = ref<string | null>(null);
  ```
- Implement `openDrawer(itemCode: string, weekKey?: string)`:
  - Find material by `itemCode` in `materials.value`.
  - If `weekKey` is supplied, set `drawerWeekKey.value = weekKey`.
  - Else if material has `first_shortage_week` and that week exists in `weeks.value`, use `first_shortage_week`.
  - Else default to current week (`weeks.value.find(w => w.is_current)?.key || weeks.value[0]?.key`).
  - Set `drawerItemCode.value = itemCode`.
  - Set `activeWeekFilter.value[itemCode] = drawerWeekKey.value`.
  - Set `isDrawerOpen.value = true`.
- Implement `closeDrawer()`:
  - Set `isDrawerOpen.value = false`.
- Implement `setDrawerWeek(weekKey: string)`:
  - Set `drawerWeekKey.value = weekKey`.
  - If `drawerItemCode.value`, set `activeWeekFilter.value[drawerItemCode.value] = weekKey`.
- Define computed `selectedDrawerMaterial`:
  - `computed(() => materials.value.find(m => m.item_code === drawerItemCode.value) || null)`.
- Update `focusWeekForMaterial(itemCode: string, weekKey: string)`:
  - Call `openDrawer(itemCode, weekKey)`.
- Export the new properties from `useMrpState()`.

- [ ] **Step 2: Verify typescript compilation**

Run: `bench build --app erpnextkta --production`
Expected: PASS

- [ ] **Step 3: Commit state extension**

```bash
git add erpnextkta/public/material-requirement/composables/useMrpState.ts
git commit -m "feat(mrp): add drawer state and week resolution to useMrpState"
```

---

### Task 2: Implement `MrpDetailDrawer.vue` Component

**Files:**
- Create: `erpnextkta/public/material-requirement/components/drawer/MrpDetailDrawer.vue`
- Modify: `erpnextkta/public/material-requirement/App.vue`

**Interfaces:**
- Consumes: `useMrpState.ts` (`isDrawerOpen`, `drawerItemCode`, `drawerWeekKey`, `selectedDrawerMaterial`, `closeDrawer`, `setDrawerWeek`, `weeks`, `getSelectedWeekMetrics`).
- Produces: Non-modal slide-over drawer mounted at body level via `<Teleport to="body">`.

- [ ] **Step 1: Create `MrpDetailDrawer.vue`**

Structure:
- `<Teleport to="body">` with `<Transition name="mrp-drawer">`.
- Container: `fixed top-0 right-0 h-full w-[460px] max-w-[95vw] z-[1050] flex flex-col shadow-2xl mrp-drawer-panel border-l`.
- Header section:
  - Title: Item Code, Item Name, UOM, Current Available Stock badge.
  - Close button (`X`) and `ESC` key listener on window.
  - Horizontal scrollable Week Selector Tabs/Pills: Render all `weeks`, highlight `drawerWeekKey`, clicking changes week via `setDrawerWeek(w.key)`.
- Body section (Scrollable `flex-1 overflow-y-auto p-4`):
  - 1. Selected Week Metric Summary Card (Brüt İhtiyaç, Planlanan Giriş, Net İhtiyaç, Önerilen Sipariş).
  - 2. PO & Receipt Breakdown using `<MrpPoReceiptList>` (with `:selected-week="drawerWeekKey"`).
  - 3. Pegging Breakdown using `<MrpPeggingList>` (with `:selected-week="drawerWeekKey"`).
  - 4. Supplier Planned Orders Breakdown using `<MrpSupplierPlannedOrders>`.
- Empty state fallback if material has no transactions.

- [ ] **Step 2: Mount `MrpDetailDrawer` in `App.vue`**

In `erpnextkta/public/material-requirement/App.vue`:
- Import `MrpDetailDrawer` from `./components/drawer/MrpDetailDrawer.vue`.
- Add `<MrpDetailDrawer />` inside the root container.

- [ ] **Step 3: Check line count of `MrpDetailDrawer.vue`**

Run: `wc -l erpnextkta/public/material-requirement/components/drawer/MrpDetailDrawer.vue`
Expected: Under 500 lines.

- [ ] **Step 4: Build assets to verify syntax and bundle**

Run: `bench build --app erpnextkta --production`
Expected: PASS

- [ ] **Step 5: Commit `MrpDetailDrawer` component**

```bash
git add erpnextkta/public/material-requirement/components/drawer/MrpDetailDrawer.vue erpnextkta/public/material-requirement/App.vue
git commit -m "feat(mrp): implement MrpDetailDrawer slide-over panel"
```

---

### Task 3: Deactivate Table Accordion and Connect Matrix to Side Drawer

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue`
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpItemIdentity.vue`

**Interfaces:**
- Consumes: `openDrawer` from `useMrpState.ts`.
- Behavior: Clicking any week cell or item identity row opens/updates the side drawer; table accordion row is deactivated without deleting code.

- [ ] **Step 1: Update `MrpMatrixTable.vue`**
  - Disable the accordion row:
    Change `<tr v-if="isRowExpanded(m.item_code)" class="mrp-row-accordion">`
    To: `<!-- Akordiyon Deaktif: Yerine MrpDetailDrawer kullanilmaktadir -->\n<tr v-if="false && isRowExpanded(m.item_code)" class="mrp-row-accordion">`
  - In `toggleAccordion(itemCode: string)`:
    Keep state tracking for backward compatibility, but call `openDrawer(itemCode)`.
  - Remove unused template references if needed while keeping line count under 500 lines.

- [ ] **Step 2: Update `MrpItemIdentity.vue`**
  - Ensure clicking the row header / item name triggers `openDrawer(material.item_code)`.

- [ ] **Step 3: Check line count of `MrpMatrixTable.vue`**

Run: `wc -l erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue`
Expected: Under 500 lines.

- [ ] **Step 4: Build assets**

Run: `bench build --app erpnextkta --production`
Expected: PASS

- [ ] **Step 5: Commit matrix table updates**

```bash
git add erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue erpnextkta/public/material-requirement/components/matrix/MrpItemIdentity.vue
git commit -m "refactor(mrp): deactivate table accordion and connect clicks to side drawer"
```

---

### Task 4: Establish Semantic CSS Theme Tokens in `App.vue`

**Files:**
- Modify: `erpnextkta/public/material-requirement/App.vue`

**Interfaces:**
- Produces: Full set of CSS variables under `:root, [data-theme="light"]` and `[data-theme="dark"], body.dark, html.dark`.

- [ ] **Step 1: Define CSS variable system in `App.vue` style block**

Add comprehensive variables:
```css
:root, [data-theme="light"] {
  --mrp-bg: #f8fafc;
  --mrp-card-bg: #ffffff;
  --mrp-card-subtle: #f1f5f9;
  --mrp-text: #0f172a;
  --mrp-text-muted: #64748b;
  --mrp-border: #e2e8f0;
  --mrp-border-subtle: #f1f5f9;
  --mrp-header-bg: #f8fafc;
  --mrp-cell-hover: rgba(37, 99, 235, 0.08);
  --mrp-cell-selected: rgba(37, 99, 235, 0.16);
  --mrp-table-zebra: #fafcff;
  --mrp-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
}

[data-theme="dark"], body.dark, html.dark {
  --mrp-bg: #0f172a;
  --mrp-card-bg: #1e293b;
  --mrp-card-subtle: #24344d;
  --mrp-text: #f1f5f9;
  --mrp-text-muted: #94a3b8;
  --mrp-border: #334155;
  --mrp-border-subtle: #1e293b;
  --mrp-header-bg: #182234;
  --mrp-cell-hover: rgba(59, 130, 246, 0.15);
  --mrp-cell-selected: rgba(59, 130, 246, 0.25);
  --mrp-table-zebra: #131d2e;
  --mrp-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.2);
}
```

- [ ] **Step 2: Test asset build**

Run: `bench build --app erpnextkta --production`
Expected: PASS

- [ ] **Step 3: Commit theme token foundations**

```bash
git add erpnextkta/public/material-requirement/App.vue
git commit -m "style(mrp): establish semantic Light and Dark theme CSS variables in App.vue"
```

---

### Task 5: Refactor Matrix Components for 100% Light/Dark Theme Compliance

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue`
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpItemIdentity.vue`
- Modify: `erpnextkta/public/material-requirement/components/matrix/MrpWeekCell.vue`

**Interfaces:**
- Consumes: `--mrp-*` CSS variables from `App.vue`.
- Guarantees: Zero hardcoded background/border colors causing contrast loss in dark mode.

- [ ] **Step 1: Refactor `MrpMatrixTable.vue` styles**
  - Replace hardcoded table headers, sticky columns, and zebra rows with `--mrp-header-bg`, `--mrp-card-bg`, `--mrp-border`, `--mrp-table-zebra`.
- [ ] **Step 2: Refactor `MrpItemIdentity.vue` styles**
  - Replace background badges, link colors, and text colors with `--mrp-card-bg`, `--mrp-text`, `--mrp-text-muted`, and dark-mode safe badge backgrounds.
- [ ] **Step 3: Refactor `MrpWeekCell.vue` styles**
  - Ensure metric numbers, shortage indicators, and badges maintain readability on both light and dark backgrounds. Use transparent RGBA accents (`--mrp-cell-hover`, `--mrp-cell-selected`).
- [ ] **Step 4: Check line counts**

Run: `wc -l erpnextkta/public/material-requirement/components/matrix/MrpMatrixTable.vue erpnextkta/public/material-requirement/components/matrix/MrpItemIdentity.vue erpnextkta/public/material-requirement/components/matrix/MrpWeekCell.vue`
Expected: All under 500 lines.

- [ ] **Step 5: Test asset build**

Run: `bench build --app erpnextkta --production`
Expected: PASS

- [ ] **Step 6: Commit matrix component theme refactor**

```bash
git add erpnextkta/public/material-requirement/components/matrix/
git commit -m "style(mrp): apply full Light and Dark theme styling to matrix components"
```

---

### Task 6: Refactor Toolbar, Filter Bar, and Detail Lists for Light/Dark Theme

**Files:**
- Modify: `erpnextkta/public/material-requirement/components/MrpFilterBar.vue`
- Modify: `erpnextkta/public/material-requirement/components/MrpToolbar.vue`
- Modify: `erpnextkta/public/material-requirement/components/accordion/MrpPeggingList.vue`
- Modify: `erpnextkta/public/material-requirement/components/accordion/MrpPoReceiptList.vue`
- Modify: `erpnextkta/public/material-requirement/components/accordion/MrpSupplierPlannedOrders.vue`
- Modify: `erpnextkta/public/material-requirement/components/drawer/MrpDetailDrawer.vue`

**Interfaces:**
- Consumes: `--mrp-*` CSS variables.
- Completes: 100% theme coverage across all remaining components.

- [ ] **Step 1: Refactor `MrpFilterBar.vue` & `MrpToolbar.vue`**
  - Replace inputs, selects, metric summary chips, search inputs, and action buttons with `--mrp-card-bg`, `--mrp-text`, `--mrp-border`.
- [ ] **Step 2: Refactor `MrpPoReceiptList.vue`, `MrpPeggingList.vue`, `MrpSupplierPlannedOrders.vue`**
  - Replace internal list backgrounds, table headers, and status cards with theme variables.
- [ ] **Step 3: Refactor `MrpDetailDrawer.vue`**
  - Ensure drawer background is `--mrp-card-bg`, header border is `--mrp-border`, and week pills highlight smoothly in dark mode.
- [ ] **Step 4: Test asset build**

Run: `bench build --app erpnextkta --production`
Expected: PASS

- [ ] **Step 5: Commit remaining components theme refactor**

```bash
git add erpnextkta/public/material-requirement/components/
git commit -m "style(mrp): complete Light and Dark theme styling across all MRP components"
```

---

### Task 7: End-to-End Verification & Production Build Gate

**Files:**
- Verify: Full bundle build, absence of hardcoded black-on-white or white-on-black anomalies, line counts.

- [ ] **Step 1: Check line count limits across all `.vue` files**

Run: `wc -l erpnextkta/public/material-requirement/**/*.vue`
Expected: All modified/new files (except existing `MrpPoReceiptList.vue`) under 500 lines.

- [ ] **Step 2: Run production asset build**

Run: `bench build --app erpnextkta --production`
Expected: Compiled successfully with zero errors.

- [ ] **Step 3: Run git status and diff check**

Run: `git status`
Expected: Clean working directory.

- [ ] **Step 4: Check acceptance criteria**
  - [x] Side drawer opens smoothly without vertical/horizontal table displacement.
  - [x] Table accordion row deactivated without deleting legacy code.
  - [x] Drawer is non-modal (allows direct clicking on other cells while open).
  - [x] Item identity click resolves default week intelligently.
  - [x] Full Light & Dark theme compliance across all 8 components.
  - [x] Production build passes cleanly.
