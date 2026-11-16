<template>
  <Teleport to="body">
    <Transition name="mrp-drawer">
      <aside
        v-if="isDrawerOpen && selectedDrawerMaterial"
        class="mrp-drawer-panel"
        aria-label="Material Requirement Details"
      >
        <!-- Drawer Header -->
        <div class="mrp-drawer-header">
          <div class="mrp-drawer-title-row">
            <div class="mrp-drawer-item-info">
              <div class="d-flex align-items-center gap-2">
                <a
                  :href="`/app/item/${encodeURIComponent(selectedDrawerMaterial.item_code)}`"
                  target="_blank"
                  class="mrp-drawer-item-code"
                >
                  {{ selectedDrawerMaterial.item_code }}
                </a>
                <span
                  v-if="selectedDrawerMaterial.first_shortage_week"
                  :class="['mrp-badge', selectedDrawerMaterial.is_urgent ? 'mrp-badge-urgent' : 'mrp-badge-shortage']"
                >
                  <i class="fa fa-exclamation-triangle mr-1"></i>{{ selectedDrawerMaterial.first_shortage_week }}
                </span>
              </div>
              <div class="mrp-drawer-item-name" :title="selectedDrawerMaterial.item_name">
                {{ selectedDrawerMaterial.item_name || "-" }}
              </div>
            </div>

            <!-- Close Button -->
            <button type="button" class="mrp-drawer-close-btn" :title="__('Kapat (ESC)')" @click="closeDrawer">
              <i class="fa fa-times"></i>
            </button>
          </div>

          <!-- Quick Stock & Supplier Meta Row -->
          <div class="mrp-drawer-meta-row">
            <span class="mrp-tag mrp-tag-stock" :title="__('Serbest Stok')">
              <i class="fa fa-cubes mr-1"></i>{{ formatQty(selectedDrawerMaterial.free_stock) }} {{ selectedDrawerMaterial.uom }}
            </span>
            <span v-if="selectedDrawerMaterial.order_amount > 0" class="mrp-tag mrp-tag-amount" :title="__('Önerilen Sipariş Tutarı')">
              <i class="fa fa-money mr-1"></i>{{ formatMoney(selectedDrawerMaterial.order_amount, selectedDrawerMaterial.currency) }}
            </span>
            <span v-if="selectedDrawerMaterial.supplier" class="mrp-tag mrp-tag-supplier" :title="__('Varsayılan Tedarikçi')">
              <i class="fa fa-building-o mr-1"></i>{{ selectedDrawerMaterial.supplier }}
            </span>
          </div>

          <!-- Prominent Selected Week Banner -->
          <div v-if="drawerWeekKey" class="mrp-drawer-week-banner">
            <div class="mrp-drawer-week-info">
              <i class="fa fa-calendar-check-o text-primary mr-1"></i>
              <span class="mrp-week-label-prefix">{{ __("İncelenen Hafta") }}:</span>
              <span class="mrp-week-label-title">{{ activeWeekLabel }}</span>
              <span v-if="isCurrentWeek" class="mrp-badge mrp-badge-current">
                {{ __("Bu Hafta") }}
              </span>
            </div>
            <div v-if="currentWeekNet > 0" class="mrp-drawer-week-alert">
              <span class="mrp-badge mrp-badge-shortage-alert">
                <i class="fa fa-exclamation-triangle mr-1"></i>
                {{ __("Net Eksik") }}: {{ formatQty(currentWeekNet) }} {{ selectedDrawerMaterial.uom }}
              </span>
            </div>
          </div>
        </div>

        <!-- Drawer Body (Scrollable) -->
        <div class="mrp-drawer-body">
          <!-- 1. Sabit Netleştirme Hesabı Özeti Strip (Sub-component) -->
          <MrpDrawerSummaryCards />

          <!-- 2. İhtiyaç Yaratan Bitmiş Ürünler (Talep Dağılımı) Accordion Card -->
          <div
            v-if="selectedDrawerMaterial.pegging && selectedDrawerMaterial.pegging.length > 0"
            class="mrp-drawer-accordion-card"
          >
            <button
              type="button"
              :class="['mrp-drawer-accordion-header', { 'is-collapsed': activeSection !== 'pegging' }]"
              :aria-expanded="activeSection === 'pegging'"
              @click="toggleSection('pegging')"
            >
              <div class="mrp-accordion-title-wrap">
                <i class="fa fa-cogs text-danger mr-2"></i>
                <span class="mrp-accordion-title">
                  {{ __("İhtiyaç Yaratan Bitmiş Ürünler (Talep Dağılımı)") }}
                </span>
                <span
                  v-if="weekPeggingCount > 0"
                  class="badge badge-danger-subtle ml-2"
                  :title="__('Bu hafta talep yaratan model sayısı')"
                >
                  {{ weekPeggingCount }} {{ __("Model") }}
                </span>
                <span
                  v-else-if="drawerWeekKey"
                  class="badge badge-light-subtle ml-2"
                  :title="__('Bu hafta talep yok')"
                >
                  0 {{ __("Model") }}
                </span>
              </div>
              <div class="mrp-accordion-actions">
                <i :class="['fa', activeSection === 'pegging' ? 'fa-chevron-up' : 'fa-chevron-down', 'mrp-chevron-icon']"></i>
              </div>
            </button>

            <div v-show="activeSection === 'pegging'" class="mrp-drawer-accordion-body p-0">
              <MrpPeggingList
                :pegging="selectedDrawerMaterial.pegging"
                :weeks="weeks"
                :uom="selectedDrawerMaterial.uom"
                :selected-week="drawerWeekKey"
                :hide-header="true"
              />
            </div>
          </div>

          <!-- 3. Açık Siparişler ve Teslimatlar Accordion Card -->
          <div
            v-if="hasOpenOrdersSection"
            class="mrp-drawer-accordion-card"
          >
            <button
              type="button"
              :class="['mrp-drawer-accordion-header', { 'is-collapsed': activeSection !== 'openOrders' }]"
              :aria-expanded="activeSection === 'openOrders'"
              @click="toggleSection('openOrders')"
            >
              <div class="mrp-accordion-title-wrap">
                <i class="fa fa-truck text-info mr-2"></i>
                <span class="mrp-accordion-title">
                  {{ __("Açık Siparişler ve Teslimatlar") }}
                </span>
                <span v-if="openOrdersCount > 0" class="badge badge-info-subtle ml-2">
                  {{ openOrdersCount }} {{ __("Kayıt") }}
                </span>
                <span v-else-if="drawerWeekKey" class="badge badge-light-subtle ml-2">
                  0 {{ __("Kayıt") }}
                </span>
              </div>
              <div class="mrp-accordion-actions">
                <i :class="['fa', activeSection === 'openOrders' ? 'fa-chevron-up' : 'fa-chevron-down', 'mrp-chevron-icon']"></i>
              </div>
            </button>

            <div v-show="activeSection === 'openOrders'" class="mrp-drawer-accordion-body p-0">
              <MrpPoReceiptList
                :supplies="selectedDrawerMaterial.open_supplies"
                :pos="selectedDrawerMaterial.open_pos"
                :uom="selectedDrawerMaterial.uom"
                :selected-week="drawerWeekKey"
                :flush="true"
                @select-week="(w) => setDrawerWeek(w)"
              />
            </div>
          </div>

          <!-- 4. Tedarikçi Sipariş Dağılımı Accordion Card -->
          <div
            v-if="selectedDrawerMaterial.planned_orders_by_supplier && Object.keys(selectedDrawerMaterial.planned_orders_by_supplier).length > 1"
            class="mrp-drawer-accordion-card"
          >
            <button
              type="button"
              :class="['mrp-drawer-accordion-header', { 'is-collapsed': activeSection !== 'suppliers' }]"
              :aria-expanded="activeSection === 'suppliers'"
              @click="toggleSection('suppliers')"
            >
              <div class="mrp-accordion-title-wrap">
                <i class="fa fa-pie-chart text-purple mr-2"></i>
                <span class="mrp-accordion-title">
                  {{ __("Tedarikçi Sipariş Dağılımı") }}
                </span>
                <span v-if="selectedDrawerMaterial.sourcing_strategy" class="badge badge-purple ml-2">
                  {{ __(selectedDrawerMaterial.sourcing_strategy) }}
                </span>
              </div>
              <div class="mrp-accordion-actions">
                <i :class="['fa', activeSection === 'suppliers' ? 'fa-chevron-up' : 'fa-chevron-down', 'mrp-chevron-icon']"></i>
              </div>
            </button>

            <div v-show="activeSection === 'suppliers'" class="mrp-drawer-accordion-body p-0">
              <MrpSupplierPlannedOrders
                :material="selectedDrawerMaterial"
                :weeks="weeks"
                :selected-week="drawerWeekKey"
                :hide-header="true"
              />
            </div>
          </div>

          <!-- Empty Fallback -->
          <div v-if="isMaterialEmpty" class="text-muted small py-4 px-3 text-center mrp-drawer-empty">
            <i class="fa fa-info-circle mr-1"></i>
            {{ __("Bu malzeme için bekleyen açık teslimat veya mamul kırılımı bulunmamaktadır.") }}
          </div>
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { useMrpState } from "../../composables/useMrpState";
import MrpDrawerSummaryCards from "./MrpDrawerSummaryCards.vue";
import MrpPeggingList from "../accordion/MrpPeggingList.vue";
import MrpPoReceiptList from "../accordion/MrpPoReceiptList.vue";
import MrpSupplierPlannedOrders from "../accordion/MrpSupplierPlannedOrders.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const { weeks, isDrawerOpen, drawerWeekKey, selectedDrawerMaterial, closeDrawer, setDrawerWeek } = useMrpState();

type SectionKey = "pegging" | "openOrders" | "suppliers";
const activeSection = ref<SectionKey | null>("pegging");

function toggleSection(key: SectionKey) {
  activeSection.value = activeSection.value === key ? null : key;
}

const currentWeekObj = computed(() => {
  if (!drawerWeekKey.value) return null;
  return weeks.value.find((w) => w.key === drawerWeekKey.value) || null;
});

const isCurrentWeek = computed(() => Boolean(currentWeekObj.value?.is_current));

const activeWeekLabel = computed(() => {
  if (!drawerWeekKey.value) return "";
  return currentWeekObj.value ? currentWeekObj.value.label : drawerWeekKey.value;
});

const currentWeekNet = computed(() => {
  const m = selectedDrawerMaterial.value;
  const wk = drawerWeekKey.value;
  if (!m || !wk || !m.weeks) return 0;
  return Number(m.weeks[wk]?.net || 0);
});

const weekPeggingCount = computed(() => {
  const wk = drawerWeekKey.value;
  const peggingList = selectedDrawerMaterial.value?.pegging || [];
  if (!wk) return peggingList.length;
  return peggingList.filter((p) => (p.weeks?.[wk] || 0) > 0).length;
});

const openOrdersCount = computed(() => {
  const m = selectedDrawerMaterial.value;
  const wk = drawerWeekKey.value;
  if (!m) return 0;
  const list = (m.open_supplies && m.open_supplies.length > 0) ? m.open_supplies : (m.open_pos || []);
  if (!wk) return list.length;
  return list.filter((s: any) => s.week === wk).length;
});

const hasOpenOrdersSection = computed(() => {
  const m = selectedDrawerMaterial.value;
  if (!m) return false;
  return (m.open_supplies && m.open_supplies.length > 0) || (m.open_pos && m.open_pos.length > 0) || Boolean(drawerWeekKey.value);
});

const isMaterialEmpty = computed(() => {
  const m = selectedDrawerMaterial.value;
  if (!m) return true;
  const noPegging = !m.pegging || m.pegging.length === 0;
  const noSupplies = !m.open_supplies || m.open_supplies.length === 0;
  const noPos = !m.open_pos || m.open_pos.length === 0;
  const noMultiSupplier = !m.planned_orders_by_supplier || Object.keys(m.planned_orders_by_supplier).length <= 1;
  return noPegging && noSupplies && noPos && noMultiSupplier && !drawerWeekKey.value;
});

watch(
  [() => selectedDrawerMaterial.value?.item_code, () => drawerWeekKey.value],
  () => {
    if (weekPeggingCount.value > 0) {
      activeSection.value = "pegging";
    } else if (openOrdersCount.value > 0) {
      activeSection.value = "openOrders";
    } else {
      activeSection.value = "pegging";
    }
  },
  { immediate: true }
);

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

function formatMoney(val: number, currency: string): string {
  if (!val) return "0";
  const formatted = Number(val).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${formatted} ${currency}` : formatted;
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Escape" && isDrawerOpen.value) {
    closeDrawer();
  }
}

onMounted(() => window.addEventListener("keydown", handleKeydown));
onUnmounted(() => window.removeEventListener("keydown", handleKeydown));
</script>

<style scoped>
.mrp-drawer-panel {
  position: fixed; top: 0; right: 0; width: 520px; max-width: 100vw; height: 100vh;
  z-index: 1050; background: var(--mrp-glass-bg, rgba(255, 255, 255, 0.95));
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-left: 1px solid var(--mrp-border); box-shadow: var(--card-shadow, -4px 0 24px rgba(0, 0, 0, 0.15));
  display: flex; flex-direction: column; overflow: hidden; color: var(--mrp-text);
}
.mrp-drawer-enter-active, .mrp-drawer-leave-active {
  transition: transform 0.24s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
}
.mrp-drawer-enter-from, .mrp-drawer-leave-to {
  transform: translateX(100%); opacity: 0.8;
}
.mrp-drawer-header {
  padding: 14px 16px 12px 16px; border-bottom: 1px solid var(--mrp-border);
  background: var(--mrp-header-bg); flex-shrink: 0;
}
.mrp-drawer-title-row {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
}
.mrp-drawer-item-info { flex: 1; min-width: 0; }
.mrp-drawer-item-code {
  font-weight: 700; font-size: 15px; color: #4338ca; text-decoration: none;
}
.mrp-drawer-item-code:hover { text-decoration: underline; }
[data-theme="dark"] .mrp-drawer-item-code { color: #a5b4fc; }
.mrp-drawer-item-name {
  font-size: 12px; color: var(--mrp-text-muted); margin-top: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.mrp-drawer-close-btn {
  background: transparent; border: 1px solid var(--mrp-border);
  color: var(--mrp-text-muted); border-radius: 6px; width: 28px; height: 28px;
  display: inline-flex; align-items: center; justify-content: center; cursor: pointer;
  transition: all 0.15s ease; flex-shrink: 0;
}
.mrp-drawer-close-btn:hover {
  background: var(--mrp-cell-hover); color: #4338ca; border-color: #4338ca;
}
[data-theme="dark"] .mrp-drawer-close-btn:hover { color: #a5b4fc; border-color: #a5b4fc; }
.mrp-drawer-meta-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.mrp-drawer-week-banner {
  margin-top: 10px; padding: 8px 12px; background: var(--mrp-card-subtle);
  border: 1px solid var(--mrp-border); border-radius: 6px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
}
.mrp-drawer-week-info { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.mrp-week-label-prefix { color: var(--mrp-text-muted); font-weight: 500; }
.mrp-week-label-title { font-weight: 700; color: var(--mrp-text); }
.mrp-badge-current {
  background: rgba(99, 102, 241, 0.15); color: #4338ca; border: 1px solid rgba(99, 102, 241, 0.3);
  font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
}
[data-theme="dark"] .mrp-badge-current { color: #a5b4fc; }
.mrp-badge-shortage-alert {
  background: #ffe4e6; color: #be123c; border: 1px solid rgba(190, 18, 60, 0.3);
  font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px;
}
[data-theme="dark"] .mrp-badge-shortage-alert { color: #fda4af; background: rgba(244, 63, 94, 0.25); }
.mrp-drawer-body {
  flex: 1; overflow-y: auto; padding: 0; background: var(--mrp-bg);
}

/* Accordion sections */
.mrp-drawer-accordion-card {
  background: var(--mrp-card-bg); border-bottom: 1px solid var(--mrp-border); overflow: hidden;
}
.mrp-drawer-accordion-header {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; background: var(--mrp-header-bg); border: none;
  border-bottom: 1px solid var(--mrp-border); cursor: pointer;
  text-align: left; font-size: 12px; font-weight: 600; color: var(--mrp-text);
  transition: background 0.15s ease;
}
.mrp-drawer-accordion-header.is-collapsed { border-bottom: none; }
.mrp-drawer-accordion-header:hover { background: var(--mrp-cell-hover); }
.mrp-accordion-title-wrap { display: flex; align-items: center; flex: 1; min-width: 0; }
.mrp-accordion-title { font-weight: 600; font-size: 12px; }
.mrp-accordion-actions { display: flex; align-items: center; margin-left: 8px; }
.mrp-chevron-icon { font-size: 11px; color: var(--mrp-text-muted); }
.mrp-drawer-accordion-body { padding: 12px 16px; background: var(--mrp-card-bg); }
.mrp-drawer-accordion-body.p-0 { padding: 0 !important; }

.mrp-drawer-empty { margin: 16px; background: var(--mrp-card-bg); border: 1px dashed var(--mrp-border); border-radius: 8px; }
.mrp-tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; border: 1px solid var(--mrp-border); }
.mrp-tag-stock {
  font-weight: 600; color: #15803d; background: #dcfce7; border-color: rgba(21, 128, 61, 0.28);
}
[data-theme="dark"] .mrp-tag-stock { color: #86efac; background: rgba(34, 197, 94, 0.2); border-color: rgba(134, 239, 172, 0.3); }
.mrp-tag-amount {
  font-weight: 600; color: #15803d; background: #dcfce7; border-color: rgba(21, 128, 61, 0.28);
}
[data-theme="dark"] .mrp-tag-amount { color: #86efac; background: rgba(34, 197, 94, 0.2); border-color: rgba(134, 239, 172, 0.3); }
.mrp-tag-supplier { color: var(--mrp-text-muted); background: var(--mrp-card-subtle); }
.mrp-badge { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; white-space: nowrap; }
.mrp-badge-urgent {
  background: #ffe4e6; color: #be123c; border: 1px solid rgba(190, 18, 60, 0.3);
}
[data-theme="dark"] .mrp-badge-urgent { color: #fda4af; background: rgba(244, 63, 94, 0.25); border-color: rgba(253, 164, 175, 0.3); }
.mrp-badge-shortage {
  background: #ffedd5; color: #c2410c; border: 1px solid rgba(194, 65, 12, 0.3);
}
[data-theme="dark"] .mrp-badge-shortage { color: #fdba74; background: rgba(249, 115, 22, 0.2); border-color: rgba(253, 186, 116, 0.3); }
.badge-danger-subtle {
  background: rgba(190, 18, 60, 0.12); color: #be123c; border: 1px solid rgba(190, 18, 60, 0.25);
  font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
}
.badge-info-subtle {
  background: rgba(3, 105, 161, 0.12); color: #0369a1; border: 1px solid rgba(3, 105, 161, 0.25);
  font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
}
.badge-light-subtle {
  background: var(--mrp-card-subtle); color: var(--mrp-text-muted); border: 1px solid var(--mrp-border);
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
}
.badge-purple {
  background-color: rgba(126, 34, 206, 0.12); color: #7e22ce; border: 1px solid rgba(126, 34, 206, 0.3);
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
}
.text-purple { color: #7e22ce !important; }

/* 320px & Responsive Rules */
@media (max-width: 576px) {
  .mrp-drawer-panel { width: 100vw; max-width: 100vw; border-left: none; }
  .mrp-drawer-header { padding: 10px 12px; }
}
@media (max-width: 320px) {
  .mrp-drawer-accordion-header { padding: 10px 8px; }
}
</style>
