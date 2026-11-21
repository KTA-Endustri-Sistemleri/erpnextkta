<script setup lang="ts">
import { computed } from "vue";
import type {
  LineTransferSubMode,
  ProductionWarehouseOption,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  mode: LineTransferSubMode;
  selectedWarehouse: string;
  productionWarehouses: ProductionWarehouseOption[];
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: "update:mode", val: LineTransferSubMode): void;
  (e: "update:selectedWarehouse", val: string): void;
  (e: "refresh"): void;
  (e: "open-manual"): void;
}>();

const fallbackWarehouses: ProductionWarehouseOption[] = [
  { warehouse: "1501 KESMELER - KTA", label: "1501 KESMELER" },
  { warehouse: "1502 JK - KTA", label: "1502 JK" },
  { warehouse: "1503 RATIONAL - KTA", label: "1503 RATIONAL" },
  {
    warehouse: "1504 ARCELIK / GRAMMER - KTA",
    label: "1504 ARCELIK / GRAMMER",
  },
  { warehouse: "1509 BOSCH - KTA", label: "1509 BOSCH" },
];

const pillOptions = computed<ProductionWarehouseOption[]>(() =>
  props.productionWarehouses && props.productionWarehouses.length > 0
    ? props.productionWarehouses
    : fallbackWarehouses
);

const roleLabel = computed(() =>
  props.mode === "deficit_pull"
    ? __("Hedef Üretim Hattı")
    : __("Kaynak Üretim Hattı")
);

const isCustomActive = computed(() => {
  if (!props.selectedWarehouse) return false;
  return !pillOptions.value.some((p) => p.warehouse === props.selectedWarehouse);
});

const customPillLabel = computed(() => {
  if (isCustomActive.value && props.selectedWarehouse) {
    return props.selectedWarehouse;
  }
  return __("Diğer Üretim Deposu...");
});

function selectMode(nextMode: LineTransferSubMode) {
  if (props.mode === nextMode) return;
  emit("update:mode", nextMode);
}

function selectWarehouse(warehouse: string) {
  emit("update:selectedWarehouse", warehouse);
}

function openCustomWarehouseDialog() {
  if (typeof frappe !== "undefined" && frappe.prompt) {
    frappe.prompt(
      [
        {
          fieldname: "warehouse",
          label: roleLabel.value,
          fieldtype: "Link",
          options: "Warehouse",
          reqd: 1,
          default: isCustomActive.value ? props.selectedWarehouse : "",
          get_query: () => ({
            filters: [
              ["Warehouse", "is_group", "=", 0],
              ["Warehouse", "disabled", "=", 0],
              ["Warehouse", "warehouse_name", "not like", "%HAMMADDE%"],
            ],
          }),
        },
      ],
      (values: { warehouse: string }) => {
        if (values && values.warehouse) {
          emit("update:selectedWarehouse", values.warehouse.trim());
        }
      },
      __("Üretim Deposu Seçin"),
      __("Uygula")
    );
  } else {
    const val = window.prompt(
      __("Üretim Deposu Girin (örn. 1501 KESMELER - KTA):"),
      props.selectedWarehouse || ""
    );
    if (val && val.trim()) {
      emit("update:selectedWarehouse", val.trim());
    }
  }
}
</script>

<template>
  <section class="lt-header-card">
    <div class="lt-header-top">
      <div class="lt-mode-group">
        <div
          class="lt-segment"
          role="tablist"
          :aria-label="__('Transfer Modu')"
        >
          <button
            type="button"
            role="tab"
            :aria-selected="mode === 'deficit_pull'"
            class="lt-segment-btn"
            :class="{ active: mode === 'deficit_pull' }"
            :disabled="loading"
            @click="selectMode('deficit_pull')"
          >
            <span>📥</span>
            <span>{{ __("Açık Karşılama") }}</span>
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="mode === 'idle_push'"
            class="lt-segment-btn"
            :class="{ active: mode === 'idle_push' }"
            :disabled="loading"
            @click="selectMode('idle_push')"
          >
            <span>📤</span>
            <span>{{ __("Atıl Hat Stoğu") }}</span>
          </button>
        </div>

        <span
          class="lt-role-pill"
          :class="mode === 'deficit_pull' ? 'role-target' : 'role-source'"
        >
          {{ roleLabel }}
        </span>
      </div>

      <div class="lt-actions">
        <button
          type="button"
          class="lt-btn lt-btn-manual"
          :disabled="loading"
          @click="emit('open-manual')"
        >
          <span>+</span>
          <span>{{ __("Manuel Transfer") }}</span>
        </button>
        <button
          type="button"
          class="lt-btn lt-btn-refresh"
          :disabled="loading || !selectedWarehouse"
          :title="__('Listeyi Yenile')"
          @click="emit('refresh')"
        >
          <span class="refresh-icon" :class="{ spinning: loading }">🔄</span>
          <span>{{ loading ? __("Yükleniyor...") : __("Yenile") }}</span>
        </button>
      </div>
    </div>

    <div class="lt-pills-bar">
      <span class="lt-pills-label">
        ⚡ {{ __("Hat Seçimi") }} ({{ roleLabel }}):
      </span>
      <div class="lt-pills-list">
        <button
          v-for="opt in pillOptions"
          :key="opt.warehouse"
          type="button"
          class="lt-pill-btn"
          :class="{ active: selectedWarehouse === opt.warehouse }"
          :disabled="loading"
          :title="opt.warehouse"
          @click="selectWarehouse(opt.warehouse)"
        >
          <span class="pill-dot" />
          <span>{{ __(opt.label) }}</span>
        </button>

        <button
          type="button"
          class="lt-pill-btn lt-pill-custom"
          :class="{ active: isCustomActive }"
          :disabled="loading"
          @click="openCustomWarehouseDialog"
        >
          <span>🔍</span>
          <span>{{ customPillLabel }}</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.lt-header-card { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; padding: 1rem 1.25rem; box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04); display: flex; flex-direction: column; gap: 0.85rem; }
[data-theme="dark"] .lt-header-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12)); }
.lt-header-top { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
.lt-mode-group { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.lt-segment { display: inline-flex; padding: 0.25rem; background: var(--bg-color, #f1f5f9); border: 1px solid var(--border-color, #cbd5e1); border-radius: 0.6rem; gap: 0.25rem; }
[data-theme="dark"] .lt-segment { background: rgba(15, 23, 42, 0.55); border-color: rgba(255, 255, 255, 0.14); }
.lt-segment-btn { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.42rem 0.9rem; border: none; border-radius: 0.45rem; background: transparent; color: var(--text-muted, #64748b); font-size: 0.84rem; font-weight: 700; cursor: pointer; transition: all 0.16s ease; }
.lt-segment-btn:hover:not(:disabled) { color: var(--text-color, #0f172a); }
.lt-segment-btn.active { background: var(--card-bg, #ffffff); color: #2563eb; box-shadow: 0 1px 4px rgba(15, 23, 42, 0.1); }
[data-theme="dark"] .lt-segment-btn.active { background: #2563eb; color: #ffffff; }
.lt-role-pill { display: inline-flex; align-items: center; padding: 0.28rem 0.7rem; border-radius: 9999px; font-size: 0.76rem; font-weight: 700; }
.lt-role-pill.role-target { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }
.lt-role-pill.role-source { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
[data-theme="dark"] .lt-role-pill.role-target { background: rgba(37, 99, 235, 0.2); color: #93c5fd; border-color: rgba(96, 165, 250, 0.35); }
[data-theme="dark"] .lt-role-pill.role-source { background: rgba(245, 158, 11, 0.2); color: #fcd34d; border-color: rgba(251, 191, 36, 0.35); }
.lt-actions { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.lt-btn { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.45rem 0.9rem; border-radius: 0.5rem; font-size: 0.83rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease; }
.lt-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.lt-btn-manual { background: #2563eb; color: #ffffff; border: 1px solid #2563eb; }
.lt-btn-manual:hover:not(:disabled) { background: #1d4ed8; }
.lt-btn-refresh { background: var(--bg-color, #f8fafc); color: var(--text-color, #1e293b); border: 1px solid var(--border-color, #cbd5e1); }
[data-theme="dark"] .lt-btn-refresh { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.16); color: #f8fafc; }
.lt-btn-refresh:hover:not(:disabled) { background: var(--border-color, #e2e8f0); }
.refresh-icon { display: inline-block; }
.refresh-icon.spinning { animation: lt-spin 1s linear infinite; }
@keyframes lt-spin { to { transform: rotate(360deg); } }
.lt-pills-bar { display: flex; align-items: center; gap: 0.65rem; flex-wrap: wrap; padding-top: 0.7rem; border-top: 1px dashed var(--border-color, #e2e8f0); }
.lt-pills-label { font-size: 0.79rem; font-weight: 700; color: var(--text-muted, #64748b); white-space: nowrap; }
.lt-pills-list { display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; }
.lt-pill-btn { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.32rem 0.78rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; background: var(--bg-color, #f8fafc); color: var(--text-color, #334155); border: 1px solid var(--border-color, #cbd5e1); cursor: pointer; transition: all 0.15s ease; }
[data-theme="dark"] .lt-pill-btn { background: rgba(255, 255, 255, 0.05); border-color: rgba(255, 255, 255, 0.15); color: #e2e8f0; }
.lt-pill-btn:hover:not(:disabled) { border-color: #2563eb; background: rgba(37, 99, 235, 0.08); }
.lt-pill-btn.active { background: #2563eb; border-color: #2563eb; color: #ffffff; box-shadow: 0 1px 4px rgba(37, 99, 235, 0.3); }
.pill-dot { width: 7px; height: 7px; border-radius: 50%; background: #94a3b8; }
.lt-pill-btn.active .pill-dot { background: #ffffff; }
.lt-pill-custom { border-style: dashed; }
.lt-pill-custom.active { border-style: solid; }
</style>
