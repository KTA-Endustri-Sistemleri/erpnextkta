<template>
  <div class="ck-filters-container">
    <div class="ck-search">
      <span class="ck-search-ic">🔎</span>
      <input
        :value="q"
        @input="$emit('update:q', $event.target.value)"
        class="ck-search-input"
        type="text"
        placeholder="Ara: iş emri, kart, operasyon..."
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
      >
        Customer Tümü <span class="ck-filter-count">{{ customerGroupCounts.all }}</span>
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
</template>

<script setup>
import { computed } from "vue";

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

const sortCategories = [
  { key: "modified", label: "Güncellenme" },
  { key: "creation", label: "Oluşturulma" },
  { key: "name", label: "İsim" }
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
  { key: "all", label: "Tümü" },
  { key: "ready", label: "Hazır" },
  { key: "running", label: "Çalışıyor" },
  { key: "paused", label: "Duruşta" },
  { key: "finished", label: "Bitmiş" },
  { key: "rejected", label: "Reddedildi" },
];

const qcFilters = [
  { key: "all", label: "QC Tümü" },
  { key: "waiting", label: "Onay Bekliyor" },
  { key: "approved", label: "Onaylandı" },
  { key: "rejected", label: "Reddedildi" },
];
</script>

<style scoped>
.ck-filters-container {
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
