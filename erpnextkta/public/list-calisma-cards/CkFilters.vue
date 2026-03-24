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

    <div class="ck-sort">
      <select 
        :value="sortKey" 
        @change="$emit('update:sortKey', $event.target.value)"
        class="ck-sort-select"
      >
        <option value="modified_desc">Son Güncellenen ↓</option>
        <option value="modified_asc">Son Güncellenen ↑</option>
        <option value="creation_desc">Yeni Oluşturulan ↓</option>
        <option value="creation_asc">Yeni Oluşturulan ↑</option>
        <option value="name_asc">Kart No A → Z</option>
        <option value="name_desc">Kart No Z → A</option>
      </select>
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
defineProps({
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

defineEmits([
  "update:q", 
  "update:sortKey", 
  "update:statusFilter", 
  "update:qcFilter", 
  "update:customerGroupFilter"
]);

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

/* Sort */
.ck-sort {
  margin-top: 10px;
}

.ck-sort-select {
  width: 100%;
  border: 1px solid var(--ck-glass-border);
  border-top: 1px solid var(--ck-glass-highlight);
  background: var(--ck-glass-bg);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: 14px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-color);
  box-shadow: 0 4px 6px var(--ck-glass-shadow);
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
</style>
