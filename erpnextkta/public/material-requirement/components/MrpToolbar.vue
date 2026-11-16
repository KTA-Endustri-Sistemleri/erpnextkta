<template>
  <div class="mrp-toolbar">
    <!-- Left: Search & Weekly View Selector -->
    <div class="mrp-toolbar-left">
      <div class="mrp-search-box">
        <i class="fa fa-search mrp-search-icon"></i>
        <input
          v-model="filters.search_query"
          type="text"
          class="form-control form-control-sm mrp-search-input"
          :placeholder="__('Hammadde, açıklama veya tedarikçi ara...')"
        />
        <i
          v-if="filters.search_query"
          class="fa fa-times mrp-clear-search"
          :title="__('Aramayı Temizle')"
          @click="filters.search_query = ''"
        ></i>
      </div>

      <div class="mrp-view-selector-wrap" :title="__('Haftalık Gösterim Modu')">
        <i class="fa fa-eye mrp-view-icon"></i>
        <select
          v-model="filters.weekly_view"
          class="form-control form-control-sm mrp-view-select"
        >
          <option value="Önerilen Sipariş">{{ __("Önerilen Sipariş") }}</option>
          <option value="Net İhtiyaç">{{ __("Net İhtiyaç") }}</option>
          <option value="Brüt İhtiyaç">{{ __("Brüt İhtiyaç") }}</option>
          <option value="Projeksiyon Bakiye">{{ __("Projeksiyon Bakiye") }}</option>
        </select>
      </div>
    </div>

    <!-- Middle: Quick Status Filter Chips -->
    <div class="mrp-toolbar-middle">
      <MrpToolbarStatusChips />
    </div>

    <!-- Right: Horizon Tag, Filter Popover, Sort, Expand, Exports, Count -->
    <div class="mrp-toolbar-right">
      <!-- Horizon Tag Pill -->
      <span class="mrp-horizon-pill" :title="__('MRP Planlama Ufku Süresi')">
        <i class="fa fa-calendar-o mr-1"></i>
        <span>{{ settings.planning_horizon_days }} {{ __("Gün") }}</span>
      </span>

      <!-- Advanced Filter Popover Button -->
      <div class="mrp-popover-wrapper">
        <button
          type="button"
          :class="[
            'btn btn-xs mrp-filter-toggle-btn',
            {
              active: isFilterPopoverOpen || activeFilterCount > 0,
              'has-active-filters': activeFilterCount > 0,
            },
          ]"
          :title="__('Gelişmiş Filtreleri Aç / Kapat')"
          @click="isFilterPopoverOpen = !isFilterPopoverOpen"
        >
          <i class="fa fa-sliders mr-1"></i>
          <span>{{ __("Filtreler") }}</span>
          <span v-if="activeFilterCount > 0" class="badge mrp-active-badge">
            {{ activeFilterCount }}
          </span>
        </button>

        <MrpFilterPopover
          v-if="isFilterPopoverOpen"
          @close="isFilterPopoverOpen = false"
        />
      </div>

      <!-- Quick Sorting Control -->
      <div class="mrp-sort-control">
        <span class="mrp-sort-label" :title="__('Sıralama Seçenekleri')">
          <i class="fa fa-sort-amount-desc"></i>
        </span>
        <select
          v-model="sortPreset"
          class="form-control form-control-sm mrp-sort-select"
          @change="setSortPreset(sortPreset)"
        >
          <option value="urgent">{{ __("En Acil Eksikler") }}</option>
          <option value="amount_desc">{{ __("En Yüksek Sipariş Tutarı") }}</option>
          <option value="net_desc">{{ __("En Yüksek Net Eksik") }}</option>
          <option value="code_asc">{{ __("Hammadde Kodu (A-Z)") }}</option>
        </select>

        <span
          v-if="sortBy"
          class="mrp-active-sort-pill"
          :title="__('Sıralamayı varsayılana sıfırla')"
          @click="resetSort"
        >
          <span>{{ activeSortLabel }}</span>
          <i class="fa fa-times ml-1 mrp-sort-clear-icon"></i>
        </span>
      </div>

      <!-- Export Buttons -->
      <div class="btn-group mrp-export-group">
        <button
          type="button"
          class="btn btn-xs mrp-export-btn"
          :title="__('Excel Olarak İndir')"
          @click="exportExcel"
        >
          <i class="fa fa-file-excel-o text-success mr-1"></i> {{ __("Excel") }}
        </button>
        <button
          type="button"
          class="btn btn-xs mrp-export-btn"
          :title="__('CSV Olarak İndir')"
          @click="exportCsv"
        >
          <i class="fa fa-file-text-o text-primary mr-1"></i> {{ __("CSV") }}
        </button>
        <button
          type="button"
          class="btn btn-xs mrp-export-btn"
          :title="__('Sayfayı Yazdır veya PDF Al')"
          @click="triggerPrint"
        >
          <i class="fa fa-print text-muted mr-1"></i> {{ __("Yazdır") }}
        </button>
      </div>

      <!-- Showing Count Indicator -->
      <span class="text-muted small ml-1 mrp-showing-count">
        {{ __("Gösterilen") }}: <b>{{ filteredMaterials.length }}</b> /
        {{ summary.total_items }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useMrpState } from "../composables/useMrpState";
import { useMrpExport } from "../composables/useMrpExport";
import MrpToolbarStatusChips from "./MrpToolbarStatusChips.vue";
import MrpFilterPopover from "./MrpFilterPopover.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const isFilterPopoverOpen = ref(false);

const {
  filters,
  summary,
  settings,
  filteredMaterials,
  activeFilterCount,
  sortBy,
  sortPreset,
  activeSortLabel,
  setSortPreset,
  resetSort,
} = useMrpState();

const { exportExcel, exportCsv, triggerPrint } = useMrpExport();
</script>

<style scoped>
.mrp-toolbar {
  position: static;
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
  background: var(--mrp-glass-bg, rgba(255, 255, 255, 0.82));
  backdrop-filter: var(--mrp-glass-blur, blur(8px));
  -webkit-backdrop-filter: var(--mrp-glass-blur, blur(8px));
  padding: 8px 12px;
  border: 1px solid var(--mrp-border);
  border-radius: 8px;
  box-shadow: var(--mrp-shadow);
  margin-bottom: 8px;
  min-height: 48px;
}

.mrp-toolbar-left,
.mrp-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.mrp-toolbar-middle {
  display: flex;
  align-items: center;
}

.mrp-search-box {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 210px;
}
.mrp-search-icon {
  position: absolute;
  left: 10px;
  color: var(--mrp-text-muted);
  font-size: 12px;
  pointer-events: none;
}
.mrp-search-input {
  padding-left: 28px;
  padding-right: 28px;
  border-radius: 6px;
  border: 1px solid var(--mrp-border);
  background-color: var(--mrp-card-bg);
  color: var(--mrp-text);
  font-size: 12px;
  height: 28px;
}
.mrp-search-input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
}
.mrp-clear-search {
  position: absolute;
  right: 10px;
  cursor: pointer;
  color: var(--mrp-text-muted);
  font-size: 12px;
}
.mrp-clear-search:hover {
  color: var(--mrp-text);
}

.mrp-view-selector-wrap {
  display: inline-flex;
  align-items: center;
  background: var(--mrp-card-subtle);
  border: 1px solid var(--mrp-border);
  border-radius: 6px;
  padding: 0 4px 0 8px;
  height: 28px;
}
.mrp-view-icon {
  font-size: 12px;
  margin-right: 6px;
  color: #6366f1;
}
.mrp-view-select {
  border: none;
  background: transparent;
  color: var(--mrp-text);
  font-size: 11px;
  font-weight: 600;
  height: 26px;
  padding: 0 4px;
  box-shadow: none;
  cursor: pointer;
}
.mrp-view-select:focus,
.mrp-sort-select:focus {
  outline: none;
  box-shadow: none;
}

.mrp-horizon-pill {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--mrp-card-subtle);
  color: var(--mrp-text-muted);
  border: 1px solid var(--mrp-border);
  height: 26px;
  white-space: nowrap;
}
.mrp-popover-wrapper {
  position: relative;
  display: inline-flex;
}
.mrp-filter-toggle-btn {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid var(--mrp-border);
  background: var(--mrp-card-bg);
  color: var(--mrp-text);
  height: 26px;
  transition: all 0.15s ease;
}
.mrp-filter-toggle-btn:hover {
  background: var(--mrp-cell-hover);
}
.mrp-filter-toggle-btn.has-active-filters {
  border-color: #6366f1;
  color: #6366f1;
  background: rgba(99, 102, 241, 0.08);
}
.mrp-filter-toggle-btn.active {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}
.mrp-active-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 10px;
  background: #6366f1;
  color: #ffffff;
  margin-left: 5px;
}

.mrp-sort-control {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--mrp-card-subtle);
  padding: 1px 6px;
  border-radius: 6px;
  border: 1px solid var(--mrp-border);
  height: 26px;
}
.mrp-sort-label {
  font-size: 11px;
  color: var(--mrp-text-muted);
  display: flex;
  align-items: center;
}
.mrp-sort-select {
  font-size: 11px;
  border: none;
  background: transparent;
  color: var(--mrp-text);
  height: 22px;
  padding: 0 4px;
  box-shadow: none;
  cursor: pointer;
}
.mrp-active-sort-pill {
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  font-weight: 600;
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
  padding: 1px 6px;
  border-radius: 10px;
  cursor: pointer;
  white-space: nowrap;
  border: 1px solid rgba(99, 102, 241, 0.3);
  transition: all 0.12s ease;
}
.mrp-active-sort-pill:hover {
  background: rgba(99, 102, 241, 0.25);
}
.mrp-sort-clear-icon {
  font-size: 9px;
  opacity: 0.7;
}

.mrp-sort-select option,
.mrp-view-select option {
  background-color: var(--mrp-card-bg);
  color: var(--mrp-text);
}

.mrp-export-btn {
  font-size: 11px;
  height: 26px;
  padding: 3px 8px;
  background: var(--mrp-card-bg);
  color: var(--mrp-text);
  border: 1px solid var(--mrp-border);
}
.mrp-export-btn:hover {
  background: var(--mrp-cell-hover);
}
.mrp-showing-count {
  white-space: nowrap;
  font-size: 11px;
  color: var(--mrp-text-muted);
}

/* 320px & Responsive Rules */
@media (max-width: 768px) {
  .mrp-toolbar-left,
  .mrp-toolbar-middle,
  .mrp-toolbar-right {
    width: 100%;
  }
}

@media (max-width: 576px) {
  .mrp-toolbar {
    padding: 6px 8px;
    gap: 6px;
  }
  .mrp-toolbar-left {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
    width: 100%;
  }
  .mrp-search-box {
    width: 100%;
    min-width: 0;
  }
  .mrp-view-selector-wrap {
    width: 100%;
    justify-content: space-between;
  }
  .mrp-view-select {
    flex: 1;
  }
  .mrp-toolbar-middle {
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    padding-bottom: 2px;
  }
  .mrp-toolbar-right {
    width: 100%;
    justify-content: flex-start;
    gap: 6px;
  }
  .mrp-sort-control {
    flex: 1;
    min-width: 130px;
  }
  .mrp-sort-select {
    width: 100%;
  }
}

@media (max-width: 320px) {
  .mrp-toolbar {
    padding: 4px 6px;
  }
  .mrp-export-group {
    width: 100%;
    display: flex;
  }
  .mrp-export-btn {
    flex: 1;
    padding: 2px 4px;
    font-size: 10px;
    text-align: center;
  }
  .mrp-showing-count {
    width: 100%;
    text-align: right;
  }
}
</style>
