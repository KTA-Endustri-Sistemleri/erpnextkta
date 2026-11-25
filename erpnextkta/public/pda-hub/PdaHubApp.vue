<script setup lang="ts">
import { computed, ref } from "vue";
import type {
  PdaBootData,
  PdaMenuCategory,
  PdaModuleKey,
  PdaOperator,
  PdaScreenKey,
  VerifyPdaPinResponse,
} from "./types";
import { initFrappeShim, updateCsrfToken } from "./utils/frappeShim";
import { useInactivityLock } from "./composables/useInactivityLock";
import PdaOverlays from "./components/PdaOverlays.vue";
import PdaMenuDrawer from "./components/PdaMenuDrawer.vue";
import PinLockScreen from "./components/PinLockScreen.vue";
import LauncherHome from "./components/LauncherHome.vue";
import PickingModuleView from "./views/PickingModuleView.vue";
import PackageSplitView from "./views/PackageSplitView.vue";
import PackageMergeView from "./views/PackageMergeView.vue";
import MaterialTransferView from "./views/MaterialTransferView.vue";
import StockLookupView from "./views/StockLookupView.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const rawBoot: PdaBootData | null =
  typeof window !== "undefined" && window.__KTA_PDA_BOOT__ ? window.__KTA_PDA_BOOT__ : null;

const boot: PdaBootData = {
  is_locked: rawBoot?.is_locked ?? true,
  current_user: rawBoot?.current_user || "Guest",
  active_operator: rawBoot?.active_operator || null,
  device_authorized: Boolean(rawBoot?.device_authorized),
  inactivity_timeout_sec: Number(rawBoot?.inactivity_timeout_sec || 300),
  operators: Array.isArray(rawBoot?.operators) ? rawBoot.operators : [],
  open_picking_count: Number(rawBoot?.open_picking_count || 0),
  menu_categories: Array.isArray(rawBoot?.menu_categories) ? rawBoot.menu_categories : [],
};

const isLocked = ref<boolean>(Boolean(boot.is_locked));
const currentUser = ref<string>(boot.current_user);
const activeOperator = ref<PdaOperator | null>(boot.active_operator);
const operators = ref<PdaOperator[]>(boot.operators);
const openPickingCount = ref<number>(boot.open_picking_count);
const menuCategories = ref<PdaMenuCategory[]>(boot.menu_categories);
const selectedCategoryKey = ref<string | null>(
  boot.menu_categories.length === 1 ? boot.menu_categories[0].key : null,
);
const activeModule = ref<PdaModuleKey>("home");
const isDrawerOpen = ref<boolean>(false);
const authExpiredWarning = ref<boolean>(false);
const handingOver = ref<boolean>(false);

function clearMenuSessionState() {
  activeModule.value = "home";
  menuCategories.value = [];
  selectedCategoryKey.value = null;
  isDrawerOpen.value = false;
}

function handleAuthExpired() {
  isLocked.value = true;
  activeOperator.value = null;
  clearMenuSessionState();
  authExpiredWarning.value = true;
}

initFrappeShim({ onAuthExpired: handleAuthExpired });

async function handleHandoverLogout() {
  if (handingOver.value) return;
  handingOver.value = true;
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.pda_handover_logout",
    });
    if (res?.message?.csrf_token) {
      updateCsrfToken(res.message.csrf_token);
    }
  } catch {
    // Always fall back to locked state on device handover even if network drops.
  } finally {
    isLocked.value = true;
    activeOperator.value = null;
    clearMenuSessionState();
    handingOver.value = false;
  }
}

const lockEnabled = computed(() => !isLocked.value);
const timeoutMs = Math.max(10_000, Number(boot.inactivity_timeout_sec || 300) * 1000);

const { remainingSeconds } = useInactivityLock({
  timeoutMs,
  enabled: lockEnabled,
  onLock: () => {
    void handleHandoverLogout();
  },
});

const formattedCountdown = computed(() => {
  const total = Math.max(0, remainingSeconds.value);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
});

const activeModuleTitle = computed(() => {
  switch (activeModule.value) {
    case "picking":
      return __("Hat İkmal Toplama");
    case "split":
      return __("Koli Bölme");
    case "merge":
      return __("Koli Birleştirme");
    case "transfer":
      return __("Malzeme Transfer");
    case "lookup":
      return __("Stok Sorgu");
    default:
      return __("KTA PDA");
  }
});

const activeCategory = computed<PdaMenuCategory | null>(() => {
  if (menuCategories.value.length === 0) return null;
  if (menuCategories.value.length === 1) return menuCategories.value[0];
  if (!selectedCategoryKey.value) return null;
  return menuCategories.value.find((cat) => cat.key === selectedCategoryKey.value) || null;
});

const showSubbar = computed(
  () =>
    activeModule.value !== "home" ||
    (menuCategories.value.length > 1 && selectedCategoryKey.value !== null),
);

function handleSubbarBack() {
  if (activeModule.value !== "home") {
    activeModule.value = "home";
    return;
  }
  selectedCategoryKey.value = null;
}

const breadcrumbText = computed(() => {
  if (activeModule.value !== "home") {
    const ownerCategory =
      menuCategories.value.find((cat) =>
        cat.items.some((item) => item.key === activeModule.value),
      ) || activeCategory.value;
    return ownerCategory
      ? `${__(ownerCategory.title)} › ${activeModuleTitle.value}`
      : activeModuleTitle.value;
  }
  if (menuCategories.value.length > 1 && activeCategory.value) {
    return `${__("Ana Modüller")} › ${__(activeCategory.value.title)}`;
  }
  return activeCategory.value ? __(activeCategory.value.title) : __("KTA PDA");
});

const operatorDisplayName = computed(
  () => activeOperator.value?.employee_name || currentUser.value || __("Operatör"),
);

async function refreshBootState() {
  try {
    const res = await window.frappe.call({
      method: "erpnextkta.kta_stock.services.pda_service.get_pda_boot_data",
      type: "GET",
    });
    if (isLocked.value) return;
    const nextBoot = res?.message as PdaBootData | undefined;
    if (!nextBoot) return;
    if (typeof nextBoot.open_picking_count === "number") {
      openPickingCount.value = nextBoot.open_picking_count;
    }
    if (Array.isArray(nextBoot.operators)) {
      operators.value = nextBoot.operators;
    }
    if (nextBoot.current_user) {
      currentUser.value = nextBoot.current_user;
    }
    if (Array.isArray(nextBoot.menu_categories)) {
      menuCategories.value = nextBoot.menu_categories;
      if (nextBoot.menu_categories.length === 1) {
        selectedCategoryKey.value = nextBoot.menu_categories[0].key;
      } else if (
        selectedCategoryKey.value &&
        !nextBoot.menu_categories.some((c) => c.key === selectedCategoryKey.value)
      ) {
        selectedCategoryKey.value = null;
      }
    }
  } catch {
    // Best-effort refresh after unlock.
  }
}

function handleUnlocked(payload: { response: VerifyPdaPinResponse; operator: PdaOperator }) {
  if (payload.response?.csrf_token) {
    updateCsrfToken(payload.response.csrf_token);
  }
  const nextCategories = Array.isArray(payload.response?.menu_categories)
    ? payload.response.menu_categories
    : [];
  menuCategories.value = nextCategories;
  if (typeof payload.response?.open_picking_count === "number") {
    openPickingCount.value = payload.response.open_picking_count;
  }
  selectedCategoryKey.value = nextCategories.length === 1 ? nextCategories[0].key : null;
  activeOperator.value = payload.operator;
  isLocked.value = false;
  authExpiredWarning.value = false;
  activeModule.value = "home";
  isDrawerOpen.value = false;
  void refreshBootState();
}

function onSelectModule(moduleKey: PdaScreenKey) {
  activeModule.value = moduleKey;
}

function onSelectScreenFromDrawer(screenKey: PdaScreenKey) {
  const ownerCategory = menuCategories.value.find((cat) =>
    cat.items.some((item) => item.key === screenKey),
  );
  if (ownerCategory) {
    selectedCategoryKey.value = ownerCategory.key;
  }
  activeModule.value = screenKey;
  isDrawerOpen.value = false;
}

function onSelectCategoryFromDrawer(categoryKey: string) {
  selectedCategoryKey.value = categoryKey;
  activeModule.value = "home";
  isDrawerOpen.value = false;
}

function onSelectAllModulesFromDrawer() {
  selectedCategoryKey.value = null;
  activeModule.value = "home";
  isDrawerOpen.value = false;
}
</script>

<template>
  <div class="pda-hub-root">
    <PinLockScreen
      v-if="isLocked"
      :operators="operators"
      :auth-expired-warning="authExpiredWarning"
      @unlocked="handleUnlocked"
    />

    <div v-else class="pda-hub-shell">
      <header class="pda-topbar">
        <div class="pda-topbar-left">
          <button
            type="button"
            class="pda-topbar-btn pda-menu-btn"
            data-testid="topbar-menu-btn"
            @click="isDrawerOpen = true"
          >
            ☰ {{ __("Menü") }}
          </button>
          <span class="pda-brand" data-testid="topbar-brand">📱 {{ __("KTA PDA") }}</span>
        </div>

        <div class="pda-topbar-right">
          <span class="pda-operator-pill" :title="operatorDisplayName">
            👤 {{ operatorDisplayName }}
          </span>
          <span class="pda-timer-pill" data-testid="inactivity-timer">
            {{ formattedCountdown }}
          </span>
          <button
            type="button"
            class="pda-topbar-btn pda-handover-btn"
            data-testid="handover-btn"
            :disabled="handingOver"
            @click="handleHandoverLogout"
          >
            {{ __("Devret") }} ↩
          </button>
        </div>
      </header>

      <nav v-if="showSubbar" class="pda-subbar" data-testid="pda-subbar">
        <button
          type="button"
          class="pda-subbar-back-btn"
          data-testid="topbar-back-btn"
          :aria-label="__('Geri')"
          @click="handleSubbarBack"
        >
          ← {{ __("Geri") }}
        </button>
        <span class="pda-subbar-breadcrumb" data-testid="topbar-breadcrumb" :title="breadcrumbText">
          {{ breadcrumbText }}
        </span>
      </nav>

      <main class="pda-hub-main">
        <LauncherHome
          v-if="activeModule === 'home'"
          :menu-categories="menuCategories"
          :selected-category-key="selectedCategoryKey"
          :open-picking-count="openPickingCount"
          :operator-name="operatorDisplayName"
          @select="onSelectModule"
          @select-category="selectedCategoryKey = $event"
        />
        <PickingModuleView
          v-else-if="activeModule === 'picking'"
          @orders-updated="openPickingCount = $event"
        />
        <PackageSplitView v-else-if="activeModule === 'split'" />
        <PackageMergeView v-else-if="activeModule === 'merge'" />
        <MaterialTransferView v-else-if="activeModule === 'transfer'" />
        <StockLookupView v-else-if="activeModule === 'lookup'" />
      </main>
    </div>

    <PdaMenuDrawer
      :is-open="isDrawerOpen"
      :categories="menuCategories"
      :active-screen="activeModule"
      :selected-category-key="selectedCategoryKey"
      :open-picking-count="openPickingCount"
      @close="isDrawerOpen = false"
      @select-screen="onSelectScreenFromDrawer"
      @select-category="onSelectCategoryFromDrawer"
      @select-all-modules="onSelectAllModulesFromDrawer"
    />

    <PdaOverlays />
  </div>
</template>

<style scoped>
.pda-hub-root { min-height: 100vh; background: var(--bg-color); color: var(--text-color); }
.pda-hub-shell { min-height: 100vh; display: flex; flex-direction: column; }
.pda-topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 56px;
  padding: 8px 12px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}
.pda-topbar-left, .pda-topbar-right { display: flex; align-items: center; gap: 8px; min-width: 0; }
.pda-brand { font-size: 0.96rem; font-weight: 800; color: var(--text-color); white-space: nowrap; }
.pda-subbar {
  position: sticky;
  top: 56px;
  z-index: 35;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 6px 12px;
  background: var(--pda-surface-alt);
  border-bottom: 1px solid var(--border-color);
}
.pda-subbar-back-btn {
  flex-shrink: 0;
  min-height: 34px;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  color: var(--text-color);
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}
.pda-subbar-breadcrumb {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.88rem;
  font-weight: 800;
  color: var(--text-color);
}
.pda-operator-pill {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-color);
  background: var(--pda-surface-alt);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 4px 10px;
  max-width: 130px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pda-timer-pill { font-size: 0.75rem; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text-muted); }
.pda-topbar-btn {
  min-height: 38px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--pda-surface-alt);
  color: var(--text-color);
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}
.pda-handover-btn { background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.25); color: var(--pda-danger); }
.pda-handover-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.pda-hub-main { flex: 1; min-height: 0; }
@media (max-width: 420px) { .pda-operator-pill { display: none; } }
</style>
