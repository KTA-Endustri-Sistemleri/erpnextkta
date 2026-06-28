<template>
  <div class="ck-filters-container">
    <div class="ck-search">
      <span class="ck-search-ic">🔎</span>
      <input
        :value="q"
        @input="$emit('update:q', $event.target.value)"
        class="ck-search-input"
        type="text"
        :placeholder="__('Ara: iş emri, kart, operasyon...')"
        inputmode="search"
      />
      <button v-if="q" class="ck-clear" @click="$emit('update:q', '')">✕</button>
    </div>

    <!-- Premium Sort Bar (Custom Toggle) -->
    <div class="ck-sort-row">
      <div class="ck-sort-container">
        <button 
          v-for="cat in sortCategories" 
          :key="cat.key"
          class="ck-sort-btn"
          :class="{ active: currentSortKey === cat.key }"
          @click="handleSort(cat.key)"
        >
          <span class="ck-sort-label">{{ cat.label }}</span>
          <div v-if="currentSortKey === cat.key" class="ck-sort-icon-wrap">
            <svg 
              class="ck-sort-arrow" 
              :class="{ 'is-asc': currentSortDir === 'asc' }"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"
            >
              <polyline points="7 13 12 18 17 13"></polyline>
              <polyline points="7 6 12 11 17 6"></polyline>
            </svg>
          </div>
        </button>
      </div>
    </div>

    <div class="ck-filters-toggle-row">
      <button class="ck-filters-toggle-btn" @click="isFiltersOpen = !isFiltersOpen">
        Filtreler
        <div class="ck-active-labels" v-if="activeFilterLabels.length > 0">
          <span v-for="l in activeFilterLabels" :key="l" class="ck-filter-label-badge">{{ l }}</span>
        </div>
        <svg v-if="!isFiltersOpen" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>
      </button>
    </div>

    <div v-show="isFiltersOpen" class="ck-filters-wrapper">
      <div class="ck-filters">
        <button 
          v-for="f in statusFilters" 
          :key="f.key"
          class="ck-filter" 
          :class="{ active: statusFilter === f.key }" 
          @click="$emit('update:statusFilter', f.key)"
        >
          {{ f.label }} <span class="ck-filter-count">{{ statusCounts[f.key] }}</span>
        </button>
      </div>

      <div class="ck-filters ck-filters--sub">
        <button 
          v-for="f in qcFilters" 
          :key="f.key"
          class="ck-filter ck-filter--qc" 
          :class="{ active: qcFilter === f.key }" 
          @click="$emit('update:qcFilter', f.key)"
        >
          {{ f.label }} <span class="ck-filter-count">{{ qcCounts[f.key] }}</span>
        </button>
      </div>

      <!-- Customer Group Filters -->
      <div class="ck-filters ck-filters--sub" v-if="availableCustomerGroups.length">
        <button
          class="ck-filter ck-filter--qc"
          :class="{ active: customerGroupFilter === 'all' }"
          @click="$emit('update:customerGroupFilter', 'all')"
        >{{ __("Tüm Müşteriler") }}<span class="ck-filter-count">{{ customerGroupCounts.all }}</span>
        </button>

        <button
          v-for="g in availableCustomerGroups"
          :key="g"
          class="ck-filter ck-filter--qc"
          :class="{ active: customerGroupFilter === g }"
          @click="$emit('update:customerGroupFilter', g)"
          :title="g"
        >
          {{ g }} <span class="ck-filter-count">{{ customerGroupCounts[g] || 0 }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
const __ = (...args) => window.__(...args);

const props = defineProps({
  q: String,
  sortKey: String,
  statusFilter: String,
  qcFilter: String,
  customerGroupFilter: String,
  statusCounts: Object,
  qcCounts: Object,
  customerGroupCounts: Object,
  availableCustomerGroups: Array
});

const emit = defineEmits([
  "update:q", 
  "update:sortKey", 
  "update:statusFilter", 
  "update:qcFilter", 
  "update:customerGroupFilter"
]);

const isFiltersOpen = ref(false);

// (Removed activeFilterCount, replaced with activeFilterLabels below)

const sortCategories = [
  { key: "modified", label: __("Güncellenme") },
  { key: "creation", label: __("Oluşturulma") },
  { key: "name", label: __("İsim") }
];

const currentSortKey = computed(() => (props.sortKey || "modified_desc").split('_')[0]);
const currentSortDir = computed(() => (props.sortKey || "modified_desc").split('_')[1] || 'desc');

function handleSort(key) {
  let dir = 'desc';
  if (currentSortKey.value === key) {
    dir = currentSortDir.value === 'desc' ? 'asc' : 'desc';
  }
  emit('update:sortKey', `${key}_${dir}`);
}

const statusFilters = [
  { key: "all", label: __("Tümü") },
  { key: "ready", label: __("Hazır") },
  { key: "running", label: __("Çalışıyor") },
  { key: "paused", label: __("Duruşta") },
  { key: "finished", label: __("Bitmiş") },
  { key: "rejected", label: __("Reddedildi") },
  { key: "cancelled", label: __("İptal Edildi") },
];

const qcFilters = [
  { key: "all", label: __("Tüm Kalite Kontroller") },
  { key: "waiting", label: __("Onay Bekliyor") },
  { key: "approved", label: __("Onaylandı") },
  { key: "rejected", label: __("Reddedildi") },
];

const activeFilterLabels = computed(() => {
  const labels = [];
  
  if (props.statusFilter && props.statusFilter !== "all") {
    const f = statusFilters.find(x => x.key === props.statusFilter);
    if (f) labels.push(f.label);
  }
  
  if (props.qcFilter && props.qcFilter !== "all") {
    const f = qcFilters.find(x => x.key === props.qcFilter);
    if (f) labels.push(f.label);
  }
  
  if (props.customerGroupFilter && props.customerGroupFilter !== "all") {
    labels.push(props.customerGroupFilter);
  }
  
  return labels;
});
</script>

<style scoped>
.ck-filters-container {
  display: flex;
  flex-direction: column;
}

.ck-filters-toggle-row {
  margin-top: 10px;
  display: flex;
}

.ck-filters-toggle-btn {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text-color);
  width: 100%;
  justify-content: space-between;
  box-shadow: 0 1px 2px var(--ck-glass-shadow);
  transition: background 0.2s;
}
.ck-filters-toggle-btn:hover {
  background: var(--ck-glass-border-soft);
}
.ck-active-labels {
  display: flex;
  gap: 4px;
  margin-left: auto;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.ck-filter-label-badge {
  background: var(--ck-info, #3b82f6);
  color: white;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 11px;
  white-space: nowrap;
}
.ck-filters-wrapper {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
}

/* Glass Search */
.ck-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--ck-glass-border-soft); /* subtly inset */
  border: 1px solid var(--ck-glass-border);
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); /* inset shadow for depth */
  border-radius: 14px;
  padding: 10px 12px;
}

.ck-search-ic { opacity: .6; font-size: 14px; }
.ck-search-input {
  flex: 1;
  border: 0;
  outline: none;
  font-size: 14px;
  background: transparent;
  color: var(--text-color);
}
.ck-clear {
  border: 0;
  background: transparent;
  font-size: 14px;
  opacity: .6;
  color: var(--text-color);
}

/* Premium Sort UI */
.ck-sort-row {
  margin-top: 12px;
  position: relative;
}

.ck-sort-container {
  display: flex;
  gap: 8px;
  background: var(--ck-glass-border-soft);
  padding: 4px;
  border-radius: 16px;
  border: 1px solid var(--ck-glass-border);
}

.ck-sort-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 12px;
  border: 0;
  background: transparent;
  border-radius: 12px;
  color: var(--text-color);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  opacity: 0.6;
  white-space: nowrap;
}

.ck-sort-btn.active {
  background: var(--ck-glass-highlight);
  box-shadow: 0 4px 12px var(--ck-glass-shadow);
  opacity: 1;
  color: var(--blue-600);
}

.ck-sort-label {
  text-transform: uppercase;
}

.ck-sort-icon-wrap {
  display: flex;
  align-items: center;
}

.ck-sort-arrow {
  width: 14px;
  height: 14px;
  transition: transform 0.4s ease;
  color: var(--blue-600);
}

.ck-sort-arrow.is-asc {
  transform: rotate(180deg);
}

/* Filters */
.ck-filters {
  display: flex;
  gap: 8px;
  overflow: auto;
  padding: 12px 0 0;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: var(--scrollbar-thumb-color) solid 1px;
}
.ck-filters::-webkit-scrollbar { display: none; }

.ck-filters--sub {
  padding-top: 10px;
  justify-content: space-between;
}

.ck-filter {
  border: 1px solid var(--ck-glass-border-soft);
  border-top: 1px solid var(--ck-glass-highlight);
  border-bottom: 1px solid var(--ck-glass-bottom-edge);
  background: var(--ck-glass-bg);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  box-shadow: 0 2px 6px var(--ck-glass-shadow);
  border-radius: 999px;
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s ease;
  color: var(--text-color);
  width: 100%;
  justify-content: space-between;
}
.ck-filter:active { transform: scale(.96); box-shadow: 0 1px 2px var(--ck-glass-shadow); }

.ck-filter.active {
  background: var(--blue-500);
  color: #fff !important;
  border-color: var(--blue-600);
  border-top-color: rgba(255,255,255,0.4);
}

.ck-filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 900;
  background: var(--ck-glass-border);
  color: inherit;
}
.ck-filter.active .ck-filter-count {
  background: rgba(0,0,0,0.25);
}

/* Theme Adjustments */
[data-theme="dark"] .ck-sort-btn.active {
  background: rgba(255, 255, 255, 0.1);
  color: #60a5fa;
}

[data-theme="dark"] .ck-sort-arrow {
  color: #60a5fa;
}
</style>
