# Shopfloor Hub UI Fixes & Smart Final Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement smart reactive final confirmation check, fix sidebar badge crowding, repair
cancelled row text contrast in dark theme, remove residual SAP CORS terminology, and build a
modular template/slot-based sticky workspace header.

**Architecture:** Frontend components in `erpnextkta/public/shopfloor-hub/components/` and
`App.vue` updated with modular slot architecture, reactive input watchers, and robust
theme-aware CSS.

**Tech Stack:** Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript, Frappe Framework,
CSS Custom Properties.

**Spec:** Current conversation design decisions.

## Global Constraints

- Line length strictly <= 100 characters in code, commits, and documentation.
- No commercial or confidential information in commit messages or code.
- Always use lazy translation wrapper `const __ = (...args) => window.__(...args);` in Vue.
- Production build command strictly: `bench build --app erpnextkta --production`.
- DocType Language Invariant: Route link must strictly be `/app/kta-production-confirmation/`.
- Never use Turkish characters or Turkish terms for DocType route links.

## Review Focus

1. **Manual Override State:** When user manually toggles final confirmation, subsequent typing
   must not clobber manual intent until operation changes or quick-fill is pressed.
2. **Sticky Header Hierarchy:** `WorkspaceHeader.vue` must stay fixed at the top of workspace
   with proper z-index and blurred glass background in both light and dark themes.
3. **Sidebar Badge Overflow:** Status pills and active badges must not wrap or squeeze when
   work order names or statuses are long.
4. **Storno Terminology Consistency:** All references to "SAP CORS" must be replaced with
   "Ters Kayıt (Storno)" across UI and dialog messages.
5. **Theme-Aware Row Contrast:** Cancelled confirmation rows in `ConfirmationHistory.vue`
   must use translucent red background without blanket opacity reduction.

---

### Task 1: Modular Sticky Workspace Header (`WorkspaceHeader.vue`)

**Files:**
- Create: `erpnextkta/public/shopfloor-hub/components/WorkspaceHeader.vue`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue:276-299`

**Interfaces:**
- Produces: `WorkspaceHeader.vue` component with `#title`, `#subtitle`, and `#actions` slots.
- Consumes: `App.vue` header section and route link to `/app/kta-production-confirmation/`.

- [ ] **Step 1: Create `WorkspaceHeader.vue`**
Create `erpnextkta/public/shopfloor-hub/components/WorkspaceHeader.vue` with:
- Sticky position (`position: sticky; top: 0; z-index: 10;`)
- Backdrop filter blur (`backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);`)
- Theme-aware background:
  - Light mode: `background: rgba(255, 255, 255, 0.85); border-bottom: 1px solid #e5e7eb;`
  - Dark mode: `[data-theme='dark']` uses `rgba(15, 23, 42, 0.85);`
    with `border-bottom: 1px solid rgba(255, 255, 255, 0.1);`
- Slots:
  - `<slot name="title" />` with default text
  - `<slot name="subtitle" />` with default text
  - `<slot name="actions" />` for action buttons (e.g. "Seçimi Temizle")

- [ ] **Step 2: Update `App.vue` to use `WorkspaceHeader`**
In `erpnextkta/public/shopfloor-hub/App.vue`:
- Import `WorkspaceHeader` from `./components/WorkspaceHeader.vue`.
- Replace the static `<div class="workspace-header">...</div>` with:
```html
<WorkspaceHeader>
  <template #title>{{ __('Shopfloor Hub') }}</template>
  <template #subtitle>
    {{ __('Gerçek Zamanlı İş Emri Yürütme ve Üretim Teyidi') }}
  </template>
  <template #actions>
    <button
      v-if="selectedWorkOrder || context"
      type="button"
      class="btn-clear-selection"
      @click="clearSelection"
    >
      ✕ {{ __('Seçimi Temizle') }}
    </button>
  </template>
</WorkspaceHeader>
```

- [ ] **Step 3: Fix DocType route link in `App.vue`**
In `erpnextkta/public/shopfloor-hub/App.vue`:
- Replace `/app/kta-uretim-teyidi/${successResult.confirmation}` with:
  `/app/kta-production-confirmation/${successResult.confirmation}`

- [ ] **Step 4: Verify build**
Run: `bench build --app erpnextkta --production`
Expected: Build succeeds without TypeScript or bundling errors.

- [ ] **Step 5: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/WorkspaceHeader.vue \
  erpnextkta/public/shopfloor-hub/App.vue
git commit -m "feat(shopfloor): add sticky WorkspaceHeader component and fix route link"
```

---

### Task 2: Smart Reactive Final Confirmation in `ConfirmationPanel.vue`

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/components/ConfirmationPanel.vue:20-45`

**Interfaces:**
- Produces:
  - Automatic check of `isFinalConfirmation` when `yieldQty >= currentOpenQty`
  - Automatic uncheck when `yieldQty < currentOpenQty`
  - Manual override persistence via `userOverridden` flag
  - Immediate check on "⚡ Kalanın Tümü" button click

- [ ] **Step 1: Add user override state and watcher in `ConfirmationPanel.vue`**
In `erpnextkta/public/shopfloor-hub/components/ConfirmationPanel.vue`:
- Add `const userOverridden = ref<boolean>(false);`
- Watch `() => props.selectedOperation` to reset `userOverridden.value = false;`.
- Watch `() => props.modelValue` to trigger smart auto-sync:
```ts
watch(
  () => props.modelValue,
  (newVal) => {
    if (userOverridden.value) return;
    const openQty = currentOpenQty.value;
    if (openQty > 0) {
      if (newVal >= openQty && !props.isFinalConfirmation) {
        emit('update:isFinalConfirmation', true);
      } else if (newVal < openQty && props.isFinalConfirmation) {
        emit('update:isFinalConfirmation', false);
      }
    }
  }
);
```

- [ ] **Step 2: Update `setFullPending` and `toggleFinalConfirmation`**
In `erpnextkta/public/shopfloor-hub/components/ConfirmationPanel.vue`:
- In `setFullPending()`:
  - Calculate `pending = Math.max(0, currentOpenQty.value);`
  - Emit `update:modelValue` with `pending`
  - Emit `update:isFinalConfirmation` with `true`
  - Set `userOverridden.value = false;` (syncing with full balance)
- In `toggleFinalConfirmation()`:
  - Toggle `isFinalConfirmation`
  - Set `userOverridden.value = true;` (user made explicit manual choice)

- [ ] **Step 3: Verify build**
Run: `bench build --app erpnextkta --production`
Expected: PASS with no compilation errors.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/ConfirmationPanel.vue
git commit -m "feat(shopfloor): add smart reactive final confirmation check logic"
```

---

### Task 3: Sidebar Badge Squeeze Fix in `WorkOrderSidebar.vue`

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/components/WorkOrderSidebar.vue:369-382`

**Interfaces:**
- Produces: Resilient non-wrapping badges and pills in `.wo-card-top`.

- [ ] **Step 1: Update `.wo-card-top` and `.wo-name-group` layout**
In `erpnextkta/public/shopfloor-hub/components/WorkOrderSidebar.vue`:
- Set `.wo-card-top` to `gap: 0.5rem; min-width: 0;`
- Set `.wo-name-group` to `min-width: 0; flex: 1; overflow: hidden;`
- Ensure `.wo-name` has `overflow: hidden; text-overflow: ellipsis; white-space: nowrap;`

- [ ] **Step 2: Update `.status-pill` and `.active-badge` styling**
In `erpnextkta/public/shopfloor-hub/components/WorkOrderSidebar.vue`:
- In `.status-pill`:
  - Add `white-space: nowrap; flex-shrink: 0; display: inline-flex; align-items: center;`
- In `.active-badge`:
  - Add `white-space: nowrap; flex-shrink: 0; font-size: 0.58rem; padding: 0.08rem 0.3rem;`

- [ ] **Step 3: Verify build**
Run: `bench build --app erpnextkta --production`
Expected: PASS.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/WorkOrderSidebar.vue
git commit -m "fix(shopfloor): prevent sidebar badge squeezing and text wrap"
```

---

### Task 4: Confirmation History Contrast & Terminology Fixes

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/components/ConfirmationHistory.vue`

**Interfaces:**
- Produces:
  - Replaces "SAP CORS" with "Ters Kayıt (Storno)" across labels, messages, and titles
  - Replaces route link with `/app/kta-production-confirmation/`
  - High-contrast dark mode styling for `tr.cancelled`

- [ ] **Step 1: Replace terminology in `ConfirmationHistory.vue`**
In `erpnextkta/public/shopfloor-hub/components/ConfirmationHistory.vue`:
- In `handleCancel`:
  - Replace `SAP CORS protokolüyle` with `Ters Kayıt (Storno) protokolüyle`
- In cancel button tooltip:
  - Replace `title="__('SAP CORS Protokolüyle Bu Teyidi İptal Et')"` with
    `title="__('Ters Kayıt (Storno) İle Bu Teyidi İptal Et')"`
- In DocType route link:
  - Replace `/app/kta-uretim-teyidi/${c.name}` with `/app/kta-production-confirmation/${c.name}`

- [ ] **Step 2: Update cancelled row styling**
In `erpnextkta/public/shopfloor-hub/components/ConfirmationHistory.vue`:
- Replace:
```css
.history-table tr.cancelled { opacity: 0.6; background: #fdf2f2; }
```
With:
```css
.history-table tr.cancelled {
  background: rgba(239, 68, 68, 0.06);
}
[data-theme='dark'] .history-table tr.cancelled {
  background: rgba(239, 68, 68, 0.12);
}
```
(Removes blanket `opacity: 0.6` so text remains crisp in dark theme).

- [ ] **Step 3: Verify build**
Run: `bench build --app erpnextkta --production`
Expected: PASS.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/ConfirmationHistory.vue
git commit -m "fix(shopfloor): replace CORS terminology with Storno and fix dark contrast"
```

---

### Task 5: Reactive Draft Work Order Quantity Update (`WorkOrderReleasePanel.vue` & `App.vue`)

**Files:**
- Modify: `erpnextkta/public/shopfloor-hub/components/WorkOrderReleasePanel.vue`
- Modify: `erpnextkta/public/shopfloor-hub/App.vue`

**Interfaces:**
- Produces:
  - Immediate optimistic UI update of `props.context.qty` when draft quantity is saved
  - `@qty-updated` event emission alongside existing `@refresh`
  - Reactively re-fetches work order context and triggers sidebar list refresh in `App.vue`

**Root Cause:**
1. `WorkOrderReleasePanel.vue`'s `saveQty()` only updates its local `availability.value`, but
   `targetQty` is computed from `props.context.qty`.
2. `saveQty()` emits `emit("refresh")`, but `App.vue` never listens to `@refresh` on
   `<WorkOrderReleasePanel>`.
3. Consequently, `props.context` in `App.vue` is never re-fetched or updated, and the sidebar
   (`WorkOrderSidebar.vue`) also never re-fetches its work orders list, leaving the old quantity
   displayed across the UI.

- [ ] **Step 1: Update `WorkOrderReleasePanel.vue` `saveQty()`**
In `erpnextkta/public/shopfloor-hub/components/WorkOrderReleasePanel.vue`:
- In `saveQty()`, after successful API response:
  - Optimistically update context: `if (props.context) props.context.qty = tempQty.value;` so
    `targetQty` and headers update instantly.
  - Emit refresh and quantity update:
    ```ts
    emit('refresh');
    emit('qty-updated', tempQty.value);
    ```

- [ ] **Step 2: Wire `@refresh` in `App.vue` to reload work order and sidebar**
In `erpnextkta/public/shopfloor-hub/App.vue`:
- Add `@refresh="handleRefreshCurrentWorkOrder"` on `<WorkOrderReleasePanel>`.
- Define `handleRefreshCurrentWorkOrder`:
  ```ts
  const handleRefreshCurrentWorkOrder = async () => {
    if (selectedWorkOrder.value) {
      await loadWorkOrder(selectedWorkOrder.value);
    }
    await sidebarRef.value?.fetchWorkOrders();
  };
  ```

- [ ] **Step 3: Verify build**
Run: `bench build --app erpnextkta --production`
Expected: PASS with no compilation errors.

- [ ] **Step 4: Commit**
```bash
git add erpnextkta/public/shopfloor-hub/components/WorkOrderReleasePanel.vue \
  erpnextkta/public/shopfloor-hub/App.vue
git commit -m "fix(shopfloor): reactively sync work order quantity updates across UI"
```

---

### Task 6: Quality Gate & Production Verification

**Files:**
- Verification only across affected files.

- [ ] **Step 1: Execute production build**
Run: `bench build --app erpnextkta --production`
Expected: Exit code 0, all bundles compiled successfully.

- [ ] **Step 2: Execute python lint check**
Run: `/home/frappe/frappe-bench/env/bin/ruff check erpnextkta`
Expected: All checks pass without errors.

- [ ] **Step 3: Run shopfloor test suite**
Run:
```bash
bench --site old.kta-endustri.com.tr run-tests \
  --app erpnextkta --module erpnextkta.kta_shopfloor.tests
```
Expected: All tests pass.
