<script setup lang="ts">
import { computed } from "vue";
import type {
  ConfirmationManagementStatusFilter,
  ConfirmationsManagementCounts,
  ConfirmationsUserOption,
} from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  statusFilter: ConfirmationManagementStatusFilter;
  counts: ConfirmationsManagementCounts;
  searchQuery: string;
  operationFilter: string;
  confirmedByFilter: string;
  fromDate: string;
  toDate: string;
  operations: string[];
  users: ConfirmationsUserOption[];
  hasActiveFilters: boolean;
  loading?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:statusFilter", value: ConfirmationManagementStatusFilter): void;
  (e: "update:searchQuery", value: string): void;
  (e: "update:operationFilter", value: string): void;
  (e: "update:confirmedByFilter", value: string): void;
  (e: "update:fromDate", value: string): void;
  (e: "update:toDate", value: string): void;
  (e: "change"): void;
  (e: "refresh"): void;
  (e: "clear"): void;
}>();

const statusTabs = computed(() => [
  { id: "active" as const, label: __("Aktif"), count: props.counts.active ?? 0 },
  { id: "cancelled" as const, label: __("İptal Edildi"), count: props.counts.cancelled ?? 0 },
  { id: "all" as const, label: __("Tümü"), count: props.counts.all ?? 0 },
]);

function selectStatusTab(tab: ConfirmationManagementStatusFilter) {
  if (props.statusFilter === tab) return;
  emit("update:statusFilter", tab);
  emit("change");
}

function onSearchInput(event: Event) {
  emit("update:searchQuery", (event.target as HTMLInputElement).value);
}

function onSelectChange(
  eventName: "update:operationFilter" | "update:confirmedByFilter",
  event: Event
) {
  emit(eventName as any, (event.target as HTMLSelectElement).value);
  emit("change");
}

function onDateChange(eventName: "update:fromDate" | "update:toDate", event: Event) {
  emit(eventName as any, (event.target as HTMLInputElement).value);
  emit("change");
}
</script>

<template>
  <div class="confirmations-filters-wrap">
    <div class="toolbar-row">
      <div class="status-pills" role="tablist">
        <button
          v-for="tab in statusTabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="statusFilter === tab.id"
          class="status-pill-btn"
          :class="{ active: statusFilter === tab.id }"
          @click="selectStatusTab(tab.id)"
        >
          <span>{{ tab.label }}</span>
          <span class="pill-count">{{ tab.count }}</span>
        </button>
      </div>
      <button type="button" class="btn-tool" :disabled="loading" @click="emit('refresh')">
        <span :class="{ spinning: loading }">↻</span> {{ __("Yenile") }}
      </button>
    </div>

    <div class="filter-bar">
      <input
        :value="searchQuery"
        type="text"
        class="filter-input filter-search"
        :placeholder="__('İş Emri, Ürün veya Teyit No Ara…')"
        @input="onSearchInput($event)"
      />
      <select
        :value="operationFilter"
        class="filter-select"
        @change="onSelectChange('update:operationFilter', $event)"
      >
        <option value="">{{ __("Tüm Operasyonlar") }}</option>
        <option v-for="op in operations" :key="op" :value="op">{{ __(op) }}</option>
      </select>
      <select
        :value="confirmedByFilter"
        class="filter-select"
        @change="onSelectChange('update:confirmedByFilter', $event)"
      >
        <option value="">{{ __("Tüm Kullanıcılar") }}</option>
        <option v-for="u in users" :key="u.value" :value="u.value">
          {{ u.label || u.value }}
        </option>
      </select>
      <label class="date-field">
        <span>{{ __("Başlangıç") }}</span>
        <input
          :value="fromDate"
          type="date"
          class="filter-input"
          @change="onDateChange('update:fromDate', $event)"
        />
      </label>
      <label class="date-field">
        <span>{{ __("Bitiş") }}</span>
        <input
          :value="toDate"
          type="date"
          class="filter-input"
          @change="onDateChange('update:toDate', $event)"
        />
      </label>
      <button v-if="hasActiveFilters" type="button" class="btn-clear-filters" @click="emit('clear')">
        ✕ {{ __("Filtreleri Temizle") }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.confirmations-filters-wrap { display: flex; flex-direction: column; gap: 0.75rem; }
.toolbar-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; }
.status-pills { display: inline-flex; flex-wrap: wrap; gap: 0.45rem; }
.status-pill-btn {
  display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.42rem 0.85rem; border-radius: 9999px;
  border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-muted, #64748b);
  font-size: 0.8rem; font-weight: 700; cursor: pointer; transition: all 0.15s;
}
[data-theme="dark"] .status-pill-btn {
  background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #94a3b8;
}
.status-pill-btn.active { background: #2563eb; border-color: #2563eb; color: #ffffff; }
.pill-count { padding: 0.08rem 0.42rem; border-radius: 9999px; font-size: 0.72rem; background: rgba(148, 163, 184, 0.2); }
.status-pill-btn.active .pill-count { background: rgba(255, 255, 255, 0.24); }
.btn-tool {
  display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.42rem 0.8rem; border-radius: 0.45rem;
  border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #334155);
  font-size: 0.8rem; font-weight: 700; cursor: pointer;
}
[data-theme="dark"] .btn-tool {
  background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #e2e8f0;
}
.btn-tool:disabled { opacity: 0.55; cursor: not-allowed; }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.filter-bar {
  display: flex; flex-wrap: wrap; align-items: flex-end; gap: 0.6rem; padding: 0.8rem;
  background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.65rem;
}
[data-theme="dark"] .filter-bar {
  background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1));
}
.filter-input, .filter-select {
  height: 34px; padding: 0 0.6rem; border-radius: 0.42rem; border: 1px solid var(--border-color, #cbd5e1);
  background: var(--bg-color, #f8fafc); color: var(--text-color, #0f172a); font-size: 0.8rem; outline: none;
}
[data-theme="dark"] .filter-input, [data-theme="dark"] .filter-select {
  background: #14181d; border-color: rgba(255, 255, 255, 0.18); color: #f8fafc;
}
.filter-search { flex: 1 1 210px; min-width: 180px; }
.filter-select { flex: 0 1 175px; }
.date-field {
  display: flex; flex-direction: column; gap: 0.2rem;
  font-size: 0.68rem; font-weight: 700; color: var(--text-muted, #64748b); margin: 0;
}
.btn-clear-filters {
  height: 34px; padding: 0 0.7rem; border-radius: 0.42rem; border: 1px solid #fecaca;
  background: #fef2f2; color: #b91c1c; font-size: 0.76rem; font-weight: 700; cursor: pointer;
}
[data-theme="dark"] .btn-clear-filters {
  background: rgba(239, 68, 68, 0.16); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5;
}
</style>
