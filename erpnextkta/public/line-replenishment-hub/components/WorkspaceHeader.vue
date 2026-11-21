<template>
  <header class="hub-header">
    <div class="hub-header-top">
      <div class="hub-title-block">
        <h1 class="hub-title">
          <span class="hub-icon">📦</span>
          {{ __("Line Replenishment Hub") }}
        </h1>
        <p class="hub-subtitle">
          {{ __("Ana Hammadde Ambarından Hatlara Çekme İkmal Yönetimi") }}
        </p>
      </div>

      <div class="hub-header-actions">
        <!-- Refresh Button -->
        <button
          type="button"
          class="btn-refresh"
          :disabled="loading || !targetWarehouse"
          :title="__('Açıkları Yenile')"
          @click="emit('refresh')"
        >
          <span class="refresh-icon" :class="{ 'is-spinning': loading }"
            >🔄</span
          >
          <span>{{ loading ? __("Taranıyor...") : __("Yenile") }}</span>
        </button>
      </div>
    </div>

    <!-- Quick Line Warehouse Pills Row -->
    <div class="pills-bar">
      <span class="pills-label">⚡ {{ __("Hızlı Hat Seçimi:") }}</span>
      <div class="pills-container">
        <button
          v-for="line in quickLines"
          :key="line.label"
          type="button"
          class="pill-btn"
          :class="{ active: isLineActive(line) }"
          :disabled="loading"
          @click="selectLine(line.warehouse)"
        >
          <span class="pill-dot"></span>
          {{ __(line.label) }}
        </button>

        <!-- Custom Warehouse Pill / Button -->
        <button
          type="button"
          class="pill-btn custom-pill"
          :class="{ active: isCustomActive }"
          :disabled="loading"
          @click="openCustomWarehouseDialog"
        >
          <span class="pill-icon">🔍</span>
          <span>{{ customPillLabel }}</span>
        </button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { QuickLinePill } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface Props {
  targetWarehouse: string;
  loading: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "update:targetWarehouse", val: string): void;
  (e: "refresh"): void;
}>();

const quickLines: QuickLinePill[] = [
  { label: "1501 KESMELER", warehouse: "1501 KESMELER - KTA" },
  { label: "1502 JK", warehouse: "1502 JK - KTA" },
  { label: "1503 RATIONAL", warehouse: "1503 RATIONAL - KTA" },
  { label: "1504 ARCELIK", warehouse: "1504 ARCELIK / GRAMMER - KTA" },
  { label: "1509 BOSCH", warehouse: "1509 BOSCH - KTA" },
];

function isLineActive(line: QuickLinePill): boolean {
  if (!props.targetWarehouse) return false;
  return (
    props.targetWarehouse === line.warehouse ||
    props.targetWarehouse.startsWith(line.label)
  );
}

const isCustomActive = computed(() => {
  if (!props.targetWarehouse) return false;
  return !quickLines.some((l) => isLineActive(l));
});

const customPillLabel = computed(() => {
  if (isCustomActive.value && props.targetWarehouse) {
    return props.targetWarehouse;
  }
  return __("Diğer Depo...");
});

function selectLine(wh: string) {
  emit("update:targetWarehouse", wh);
}

function openCustomWarehouseDialog() {
  if (typeof frappe !== "undefined" && frappe.prompt) {
    frappe.prompt(
      [
        {
          fieldname: "warehouse",
          label: __("Hedef WIP Deposu"),
          fieldtype: "Link",
          options: "Warehouse",
          reqd: 1,
          default: isCustomActive.value ? props.targetWarehouse : "",
          get_query: () => ({
            filters: {
              is_group: 0,
            },
          }),
        },
      ],
      (values: { warehouse: string }) => {
        if (values && values.warehouse) {
          emit("update:targetWarehouse", values.warehouse.trim());
        }
      },
      __("Hedef Depo Seçin"),
      __("Uygula")
    );
  } else {
    const val = window.prompt(
      __("Hedef WIP Ambarını Girin (örn. 1501 KESMELER - KTA):"),
      props.targetWarehouse || ""
    );
    if (val && val.trim()) {
      emit("update:targetWarehouse", val.trim());
    }
  }
}
</script>

<style scoped>
.hub-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--card-bg, #ffffff);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
  padding: 1rem 1.5rem 0.85rem 1.5rem;
  margin-bottom: 1.25rem;
  transition: all 0.2s ease;
}

[data-theme="dark"] .hub-header {
  background: var(--ck-glass-bg, #1c2127);
  border-bottom-color: var(--ck-glass-border, rgba(255, 255, 255, 0.12));
}

.hub-header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.85rem;
}

.hub-title-block {
  display: flex;
  flex-direction: column;
}

.hub-title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.hub-icon {
  font-size: 1.35rem;
}

.hub-subtitle {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: var(--text-muted, #64748b);
}

.hub-header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.42rem 0.9rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-color, #1e293b);
  background: var(--control-bg, #f1f5f9);
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-refresh:hover:not(:disabled) {
  background: var(--border-color, #e2e8f0);
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-icon {
  display: inline-block;
  font-size: 0.95rem;
  transition: transform 0.3s linear;
}

.refresh-icon.is-spinning {
  animation: spin 1s infinite linear;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.pills-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding-top: 0.65rem;
  border-top: 1px dashed var(--border-color, #e2e8f0);
}

.pills-label {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-muted, #64748b);
}

.pills-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.8rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-color, #334155);
  background: var(--control-bg, #f8fafc);
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 9999px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.pill-btn:hover:not(:disabled) {
  background: var(--border-color, #e2e8f0);
  border-color: #94a3b8;
}

.pill-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pill-btn.active {
  background: var(--primary, #2563eb);
  color: #ffffff;
  border-color: var(--primary, #2563eb);
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.3);
}

.pill-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
  display: inline-block;
}

.pill-btn.active .pill-dot {
  background: #ffffff;
}

.custom-pill {
  border-style: dashed;
}

.custom-pill.active {
  border-style: solid;
}

.pill-icon {
  font-size: 0.8rem;
}
</style>
