<script setup lang="ts">
const __ = (...args: any[]) => (window as any).__(...args);

defineProps<{
  searchQuery: string;
  operationFilter: string;
  workstationFilter: string;
  fromDate: string;
  toDate: string;
  operations: string[];
  workstations: string[];
  hasActiveFilters: boolean;
}>();

const emit = defineEmits<{
  (e: "update:searchQuery", value: string): void;
  (e: "update:operationFilter", value: string): void;
  (e: "update:workstationFilter", value: string): void;
  (e: "update:fromDate", value: string): void;
  (e: "update:toDate", value: string): void;
  (e: "change"): void;
  (e: "clear"): void;
}>();

function onSearchInput(event: Event) {
  emit("update:searchQuery", (event.target as HTMLInputElement).value);
}

function onSelectChange(
  eventName: "update:operationFilter" | "update:workstationFilter",
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
  <div class="filter-bar">
    <input
      :value="searchQuery"
      type="text"
      class="filter-input filter-search"
      :placeholder="__('İş Emri, Ürün, Operasyon veya Kullanıcı Ara…')"
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
      :value="workstationFilter"
      class="filter-select"
      @change="onSelectChange('update:workstationFilter', $event)"
    >
      <option value="">{{ __("Tüm İş İstasyonları") }}</option>
      <option v-for="ws in workstations" :key="ws" :value="ws">{{ ws }}</option>
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
</template>

<style scoped>
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
  background: #14181d; border-color: rgba(255, 255, 255, 0.18);
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
