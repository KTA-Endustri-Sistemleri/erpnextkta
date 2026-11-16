<template>
  <div class="mrp-matrix-container">
    <!-- Loading overlay -->
    <div v-if="loading" class="mrp-loading-overlay">
      <div class="spinner-border text-primary mr-2" role="status"></div>
      <span class="text-muted">{{ __("Veriler hesaplanıyor...") }}</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="filteredMaterials.length === 0" class="mrp-empty-state">
      <i class="fa fa-cubes mrp-empty-icon"></i>
      <h5>{{ __("Kayıt Bulunamadı") }}</h5>
      <p class="text-muted small">
        {{ __("Seçilen filtrelere uygun hammadde bulunamadı.") }}
      </p>
    </div>

    <!-- Matrix Table Viewport -->
    <div v-else class="mrp-table-viewport">
      <table class="mrp-table">
        <thead>
          <tr>
            <!-- Sticky Fixed Left Column Header (100% Opaque) -->
            <th
              class="mrp-th-fixed mrp-th-sticky-top"
              :class="{ 'mrp-th-sorted': sortBy === 'item_code' }"
              :title="__('Hammadde koduna göre sırala')"
              @click="setSortColumn('item_code')"
            >
              <div class="mrp-th-fixed-content">
                <div class="d-flex align-items-center justify-content-between">
                  <span class="mrp-th-main-title">{{ __("Hammadde Bilgisi") }}</span>
                  <i
                    v-if="sortBy === 'item_code'"
                    :class="['fa mrp-sort-indicator', sortOrder === 'asc' ? 'fa-sort-asc' : 'fa-sort-desc']"
                  ></i>
                  <i v-else class="fa fa-sort mrp-sort-ghost"></i>
                </div>
                <span class="mrp-th-sub-title">{{ __("Stok, İhtiyaç ve Kapsama") }}</span>
              </div>
            </th>

            <!-- Weekly Timeline Column Headers (100% Opaque Sticky Top) -->
            <th
              v-for="w in weeks"
              :key="w.key"
              :class="[
                'mrp-th-week',
                'mrp-th-sticky-top',
                {
                  'mrp-th-current-week': w.is_current,
                  'mrp-th-sorted': sortBy === w.key,
                },
              ]"
              :title="__('{0} haftasına göre sırala (Eksik / Sipariş)', [w.label])"
              @click="setSortColumn(w.key)"
            >
              <div class="mrp-week-title">
                <span>{{ w.label }}</span>
                <i
                  v-if="sortBy === w.key"
                  :class="['fa ml-1 mrp-sort-indicator', sortOrder === 'asc' ? 'fa-sort-asc' : 'fa-sort-desc']"
                ></i>
                <i v-else class="fa fa-sort ml-1 mrp-sort-ghost"></i>
              </div>
              <span v-if="w.is_current" class="mrp-current-badge">
                {{ __("Bu Hafta") }}
              </span>
            </th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="m in filteredMaterials"
            :key="m.item_code"
            class="mrp-row-main"
          >
            <!-- Left Frozen Cell (100% Opaque) -->
            <td class="mrp-td-fixed">
              <MrpItemIdentity :material="m" />
            </td>

            <!-- Weekly Timeline Cells -->
            <MrpWeekCell
              v-for="w in weeks"
              :key="`${m.item_code}-${w.key}`"
              :material="m"
              :week="w"
            />
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useMrpState } from "../../composables/useMrpState";
import MrpItemIdentity from "./MrpItemIdentity.vue";
import MrpWeekCell from "./MrpWeekCell.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const {
  weeks,
  filteredMaterials,
  loading,
  sortBy,
  sortOrder,
  setSortColumn,
} = useMrpState();
</script>

<style scoped>
.mrp-matrix-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  background: var(--mrp-card-bg);
  border: 1px solid var(--mrp-border);
  border-radius: 8px;
  box-shadow: var(--mrp-shadow);
}
.mrp-loading-overlay {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background: var(--mrp-card-bg);
}
.mrp-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 50px 20px;
  color: var(--mrp-text-muted);
}
.mrp-empty-icon {
  font-size: 32px;
  color: var(--mrp-text-muted);
  margin-bottom: 12px;
}
.mrp-table-viewport {
  flex: 1 1 0% !important;
  min-height: 0 !important;
  width: 100% !important;
  height: 100% !important;
  overflow-x: auto !important;
  overflow-y: auto !important;
  scrollbar-width: thin !important;
  scrollbar-color: rgba(99, 102, 241, 0.45) transparent !important;
  -webkit-overflow-scrolling: touch;
  position: relative;
}

.mrp-table-viewport::-webkit-scrollbar {
  width: 8px !important;
  height: 8px !important;
}

.mrp-table-viewport::-webkit-scrollbar-track {
  background: transparent !important;
}

.mrp-table-viewport::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.4) !important;
  border-radius: 4px !important;
}

.mrp-table-viewport::-webkit-scrollbar-thumb:hover {
  background: rgba(99, 102, 241, 0.7) !important;
}

[data-theme="dark"] .mrp-table-viewport {
  scrollbar-color: rgba(129, 140, 248, 0.45) transparent !important;
}
[data-theme="dark"] .mrp-table-viewport::-webkit-scrollbar-thumb {
  background: rgba(129, 140, 248, 0.4) !important;
}
[data-theme="dark"] .mrp-table-viewport::-webkit-scrollbar-thumb:hover {
  background: rgba(129, 140, 248, 0.7) !important;
}
.mrp-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-family: inherit;
  font-size: 12px;
}

.mrp-table thead th {
  background-color: var(--mrp-card-bg, #ffffff);
}

/* Opaque Frozen Headers & Column Protection */
.mrp-th-sticky-top {
  position: sticky;
  top: 0;
  z-index: 25;
  background-color: var(--mrp-header-bg, #f8f8f8);
  border-bottom: 2px solid var(--mrp-border);
}
.mrp-th-fixed {
  position: sticky;
  left: 0;
  z-index: 30;
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  background-color: var(--mrp-header-bg, #f8f8f8);
  border-right: 2px solid var(--mrp-border);
  padding: 8px 12px;
  text-align: left;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.12s ease;
}
.mrp-th-fixed.mrp-th-sticky-top {
  position: sticky;
  top: 0;
  left: 0;
  z-index: 35;
  background-color: var(--mrp-header-bg, #f8f8f8);
}
.mrp-th-fixed:hover {
  background-color: #f1f5f9;
}
[data-theme="dark"] .mrp-th-fixed:hover {
  background-color: #252836;
}
.mrp-td-fixed {
  position: sticky;
  left: 0;
  z-index: 10;
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  background-color: var(--mrp-card-bg, #ffffff);
  border-right: 2px solid var(--mrp-border);
  border-bottom: 1px solid var(--mrp-border);
  padding: 8px 12px;
}
.mrp-row-main:hover {
  background-color: var(--mrp-row-hover-bg, #f8faff);
}
.mrp-row-main:hover .mrp-td-fixed {
  background-color: var(--mrp-row-hover-bg, #f8faff) !important;
}
[data-theme="dark"] .mrp-row-main:hover,
[data-theme="dark"] .mrp-row-main:hover .mrp-td-fixed {
  background-color: var(--mrp-row-hover-bg, #212332) !important;
}
.mrp-th-fixed-content {
  display: flex;
  flex-direction: column;
}
.mrp-th-main-title {
  font-weight: 700;
  font-size: 12px;
  color: var(--mrp-text);
}
.mrp-th-sub-title {
  font-size: 10px;
  color: var(--mrp-text-muted);
  font-weight: normal;
}

.mrp-th-week {
  min-width: 90px;
  padding: 6px 8px;
  text-align: right;
  border-right: 1px solid var(--mrp-border);
  vertical-align: bottom;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.12s ease;
  color: var(--mrp-text);
}
.mrp-th-week:hover {
  background-color: #f1f5f9;
}
[data-theme="dark"] .mrp-th-week:hover {
  background-color: #252836;
}
.mrp-th-sorted {
  background-color: #e0e7ff !important;
  color: #4338ca !important;
  border-bottom: 2px solid #4338ca !important;
}
.mrp-th-sorted:hover {
  background-color: #c7d2fe !important;
}
.mrp-sort-indicator {
  color: #4338ca;
  font-size: 11px;
}
.mrp-sort-ghost {
  opacity: 0;
  font-size: 10px;
  transition: opacity 0.15s ease;
}
.mrp-th-week:hover .mrp-sort-ghost,
.mrp-th-fixed:hover .mrp-sort-ghost {
  opacity: 0.35;
}
.mrp-week-title {
  font-weight: 700;
  font-size: 11px;
  color: var(--mrp-text);
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.mrp-th-current-week {
  background-color: var(--mrp-current-week-header-bg, #eef2ff) !important;
  border-bottom: 2px solid #6366f1 !important;
  z-index: 26;
}
.mrp-th-current-week:hover {
  background-color: #e0e7ff !important;
}
.mrp-current-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  color: #4338ca;
  background: rgba(99, 102, 241, 0.15);
  padding: 1px 4px;
  border-radius: 3px;
  margin-top: 2px;
}

[data-theme="dark"] .mrp-current-badge {
  color: #a5b4fc;
  background: rgba(129, 140, 248, 0.2);
}
[data-theme="dark"] .mrp-th-sorted {
  background-color: #232544 !important;
  color: #a5b4fc !important;
  border-bottom-color: #a5b4fc !important;
}
[data-theme="dark"] .mrp-th-sorted:hover {
  background-color: #2e325c !important;
}
[data-theme="dark"] .mrp-th-current-week:hover {
  background-color: #232544 !important;
}
[data-theme="dark"] .mrp-sort-indicator {
  color: #a5b4fc;
}
</style>
