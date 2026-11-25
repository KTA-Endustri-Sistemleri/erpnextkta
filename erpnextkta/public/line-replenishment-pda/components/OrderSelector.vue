<template>
  <div class="order-selector-card">
    <div class="selector-field">
      <label for="pda-order-select" class="selector-label">
        {{ __("Aktif İkmal Siparişi") }}
      </label>
      <div class="selector-row">
        <select
          id="pda-order-select"
          class="order-select"
          :value="selectedOrderName"
          :disabled="loading"
          @change="onSelectChange"
        >
          <option value="">{{ __("-- Sipariş Seçiniz --") }}</option>
          <option v-for="order in orders" :key="order.name" :value="order.name">
            {{ order.name }} | {{ order.target_warehouse }} ({{
              __(order.status)
            }})
          </option>
        </select>

        <button
          type="button"
          class="btn-refresh"
          :title="__('Yenile')"
          :disabled="loading"
          @click="emit('refresh')"
        >
          <span :class="['refresh-icon', { 'is-spinning': loading }]">🔄</span>
        </button>
      </div>
    </div>

    <!-- Active Order Meta Badges -->
    <div v-if="activeOrder" class="order-meta-info">
      <span class="pda-badge badge-target-warehouse">
        📍 {{ __("Hedef") }}: {{ activeOrder.target_warehouse }}
      </span>
      <span
        :class="[
          'pda-badge',
          'badge-status',
          getStatusClass(activeOrder.status),
        ]"
      >
        {{ __("Durum") }}: {{ __(activeOrder.status) }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ReplenishmentOrder } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

interface Props {
  orders: ReplenishmentOrder[];
  selectedOrderName: string;
  activeOrder: ReplenishmentOrder | null;
  loading: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "select", orderName: string): void;
  (e: "refresh"): void;
}>();

function onSelectChange(event: Event) {
  const target = event.target as HTMLSelectElement | null;
  const value = target ? target.value : "";
  emit("select", value);
}

function getStatusClass(status?: string): string {
  switch (status) {
    case "Completed":
      return "status-completed";
    case "In Progress":
      return "status-in-progress";
    case "Draft":
      return "status-draft";
    default:
      return "status-default";
  }
}
</script>

<style scoped>
.order-selector-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.selector-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selector-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-color, #1e293b);
  margin-bottom: 2px;
}

.selector-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.order-select {
  flex: 1;
  min-height: 44px;
  padding: 8px 12px;
  font-size: 0.95rem;
  font-weight: 500;
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 6px;
  background-color: var(--control-bg, #ffffff);
  color: var(--text-color, #0f172a);
}

.order-select:focus {
  outline: none;
  border-color: var(--primary-color, #2563eb);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
}

.btn-refresh {
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 6px;
  background-color: var(--btn-default-bg, #f8fafc);
  color: var(--text-color, #0f172a);
  cursor: pointer;
  font-size: 1.1rem;
}

[data-theme="dark"] .order-select {
  background-color: var(--bg-color, #0f172a);
  color: var(--text-color, #f8fafc);
  border-color: var(--border-color, rgba(255, 255, 255, 0.16));
}

[data-theme="dark"] .btn-refresh {
  background-color: var(--pda-surface-alt, #1e293b);
  color: var(--text-color, #f8fafc);
  border-color: var(--border-color, rgba(255, 255, 255, 0.16));
}

.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.refresh-icon.is-spinning {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

.order-meta-info {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color, #e2e8f0);
}

.pda-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-target-warehouse {
  background-color: #e0f2fe;
  color: #0369a1;
}

.badge-status {
  background-color: #f3f4f6;
  color: #374151;
}

.status-completed {
  background-color: #dcfce7;
  color: #15803d;
}

.status-in-progress {
  background-color: #fef3c7;
  color: #b45309;
}

.status-draft {
  background-color: #ede9fe;
  color: #6d28d9;
}

[data-theme="dark"] .badge-target-warehouse {
  background-color: rgba(14, 165, 233, 0.22);
  color: #7dd3fc;
}

[data-theme="dark"] .badge-status {
  background-color: rgba(148, 163, 184, 0.2);
  color: #cbd5e1;
}

[data-theme="dark"] .status-completed {
  background-color: rgba(34, 197, 94, 0.22);
  color: #86efac;
}

[data-theme="dark"] .status-in-progress {
  background-color: rgba(245, 158, 11, 0.22);
  color: #fcd34d;
}

[data-theme="dark"] .status-draft {
  background-color: rgba(139, 92, 246, 0.22);
  color: #c4b5fd;
}
</style>
