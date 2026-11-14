<template>
  <div class="mrp-toolbar">
    <!-- Left: Search & View Badge -->
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
          @click="filters.search_query = ''"
        ></i>
      </div>

      <span class="mrp-view-badge" :title="__('Aktif Haftalık Gösterim Modu')">
        <i class="fa fa-eye text-primary"></i>
        <span>{{ __(filters.weekly_view) }}</span>
      </span>
    </div>

    <!-- Middle: Quick Status Filter Chips -->
    <div class="mrp-toolbar-middle">
      <div class="mrp-filter-chips">
        <button
          type="button"
          :class="['mrp-chip-btn', { active: filters.status_filter === 'all' }]"
          @click="setStatusFilter('all')"
        >
          {{ __("Tümü") }} <span class="badge">{{ summary.total_items }}</span>
        </button>

        <button
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-urgent',
            { active: filters.status_filter === 'urgent' },
          ]"
          @click="setStatusFilter('urgent')"
        >
          <span class="mrp-dot mrp-dot-urgent"></span>
          {{ __("Acil Eksikler") }}
          <span class="badge">{{ summary.urgent_count }}</span>
        </button>

        <button
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-shortage',
            { active: filters.status_filter === 'shortages' },
          ]"
          @click="setStatusFilter('shortages')"
        >
          <span class="mrp-dot mrp-dot-shortage"></span>
          {{ __("Tüm Eksikler") }}
          <span class="badge">{{ summary.shortage_count }}</span>
        </button>

        <button
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-po',
            { active: filters.status_filter === 'has_po' },
          ]"
          @click="setStatusFilter('has_po')"
        >
          <i class="fa fa-truck mr-1"></i>
          {{ __("Açık PO'su Olanlar") }}
          <span class="badge">{{ summary.po_count }}</span>
        </button>

        <button
          v-if="summary.antrepo_count && summary.antrepo_count > 0"
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-antrepo',
            { active: filters.status_filter === 'antrepoda' },
          ]"
          @click="setStatusFilter('antrepoda')"
          :title="__('Gümrüklü antrepoda bekleyen hammaddeleri göster')"
        >
          <i class="fa fa-university mr-1"></i>
          {{ __("Antrepoda") }}
          <span class="badge">{{ summary.antrepo_count }}</span>
        </button>

        <button
          v-if="summary.gumruk_count && summary.gumruk_count > 0"
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-gumruk',
            { active: filters.status_filter === 'gumruklemede' },
          ]"
          @click="setStatusFilter('gumruklemede')"
          :title="
            __(
              'Gümrükleme / çekim işlemi başlatılmış teslimatları göster (+2 gün)'
            )
          "
        >
          <i class="fa fa-hourglass-half mr-1"></i>
          {{ __("Gümrükte") }}
          <span class="badge">{{ summary.gumruk_count }}</span>
        </button>

        <button
          v-if="summary.yolda_count && summary.yolda_count > 0"
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-yolda',
            { active: filters.status_filter === 'yolda' },
          ]"
          @click="setStatusFilter('yolda')"
          :title="__('Sevkiyatta / Yolda olan hammaddeleri göster')"
        >
          <i class="fa fa-ship mr-1"></i>
          {{ __("Yolda") }} <span class="badge">{{ summary.yolda_count }}</span>
        </button>

        <button
          v-if="summary.uyusmazlik_count && summary.uyusmazlik_count > 0"
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-dispute',
            { active: filters.status_filter === 'uyusmazlikta' },
          ]"
          @click="setStatusFilter('uyusmazlikta')"
          :title="
            __(
              'Kapıda uyuşmazlık veya kalite problemi nedeniyle bloke olan teslimatları göster'
            )
          "
        >
          <i class="fa fa-exclamation-triangle mr-1"></i>
          {{ __("Uyuşmazlık") }}
          <span class="badge">{{ summary.uyusmazlik_count }}</span>
        </button>

        <button
          type="button"
          :class="[
            'mrp-chip-btn',
            'mrp-chip-sufficient',
            { active: filters.status_filter === 'sufficient' },
          ]"
          @click="setStatusFilter('sufficient')"
        >
          <span class="mrp-dot mrp-dot-sufficient"></span>
          {{ __("Yeterli Stok") }}
          <span class="badge">{{ summary.sufficient_count }}</span>
        </button>
      </div>

      <!-- Quick Sorting Control -->
      <div class="mrp-sort-control">
        <span class="mrp-sort-label">
          <i class="fa fa-sort-amount-desc mr-1"></i>{{ __("Sıralama") }}:
        </span>
        <select
          v-model="sortPreset"
          class="form-control form-control-sm mrp-sort-select"
          @change="setSortPreset(sortPreset)"
        >
          <option value="urgent">
            {{ __("En Acil Eksikler (Varsayılan)") }}
          </option>
          <option value="amount_desc">
            {{ __("En Yüksek Sipariş Tutarı") }}
          </option>
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
    </div>

    <!-- Right: Expand All & Export Buttons -->
    <div class="mrp-toolbar-right">
      <button
        type="button"
        class="btn btn-xs btn-default"
        @click="toggleAllRows"
      >
        <i :class="['fa mr-1', allExpanded ? 'fa-compress' : 'fa-expand']"></i>
        <span>{{ allExpanded ? __("Tümünü Kapat") : __("Tümünü Aç") }}</span>
      </button>

      <div class="btn-group">
        <button
          type="button"
          class="btn btn-xs btn-default"
          :title="__('Excel Olarak İndir')"
          @click="exportExcel"
        >
          <i class="fa fa-file-excel-o text-success mr-1"></i> {{ __("Excel") }}
        </button>
        <button
          type="button"
          class="btn btn-xs btn-default"
          :title="__('CSV Olarak İndir')"
          @click="exportCsv"
        >
          <i class="fa fa-file-text-o text-primary mr-1"></i> {{ __("CSV") }}
        </button>
        <button
          type="button"
          class="btn btn-xs btn-default"
          :title="__('Sayfayı Yazdır veya PDF Al')"
          @click="triggerPrint"
        >
          <i class="fa fa-print text-muted mr-1"></i> {{ __("Yazdır") }}
        </button>
      </div>

      <span class="text-muted small ml-1">
        {{ __("Gösterilen") }}: <b>{{ filteredMaterials.length }}</b> /
        {{ summary.total_items }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useMrpState } from "../composables/useMrpState";
import { useMrpExport } from "../composables/useMrpExport";

const __ = (...args: any[]) => (window as any).__(...args);

const {
  filters,
  summary,
  filteredMaterials,
  expandedRows,
  sortBy,
  sortPreset,
  activeSortLabel,
  setSortPreset,
  resetSort,
  setStatusFilter,
  expandAllRows,
  collapseAllRows,
} = useMrpState();

const { exportExcel, exportCsv, triggerPrint } = useMrpExport();

const allExpanded = computed(() => {
  return (
    filteredMaterials.value.length > 0 &&
    filteredMaterials.value.every((m) => expandedRows.has(m.item_code))
  );
});

function toggleAllRows() {
  if (allExpanded.value) {
    collapseAllRows();
  } else {
    expandAllRows();
  }
}
</script>

<style scoped>
.mrp-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--card-bg, #ffffff);
  padding: 8px 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  margin-bottom: 12px;
}

.mrp-toolbar-left,
.mrp-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mrp-search-box {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 250px;
}

.mrp-search-icon {
  position: absolute;
  left: 10px;
  color: var(--text-muted, #94a3b8);
  font-size: 12px;
}

.mrp-search-input {
  padding-left: 28px;
  padding-right: 28px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #cbd5e1);
  font-size: 12px;
}

.mrp-clear-search {
  position: absolute;
  right: 10px;
  cursor: pointer;
  color: var(--text-muted, #94a3b8);
}

.mrp-view-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--bg-light-gray, #f1f5f9);
  color: var(--text-color, #1e293b);
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e2e8f0);
}

.mrp-filter-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.mrp-chip-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 6px;
  background: var(--card-bg, #ffffff);
  color: var(--text-color, #334155);
  cursor: pointer;
  transition: all 0.15s ease;
}

.mrp-chip-btn:hover {
  background: var(--bg-light-gray, #f8fafc);
}

.mrp-chip-btn.active {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}

.mrp-chip-antrepo.active {
  background: #0284c7;
  border-color: #0284c7;
}

.mrp-chip-gumruk.active {
  background: #ea580c;
  border-color: #ea580c;
}

.mrp-chip-yolda.active {
  background: #d97706;
  border-color: #d97706;
}

.mrp-chip-dispute.active {
  background: #dc2626;
  border-color: #dc2626;
  color: #ffffff;
}

.mrp-chip-dispute:not(.active) {
  color: #991b1b;
  border-color: #fca5a5;
  background: #fef2f2;
}

.mrp-chip-btn .badge {
  background: rgba(0, 0, 0, 0.08);
  color: inherit;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
}

.mrp-chip-btn.active .badge {
  background: rgba(255, 255, 255, 0.25);
  color: #ffffff;
}

.mrp-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.mrp-dot-urgent {
  background: #ef4444;
}

.mrp-dot-shortage {
  background: #f97316;
}

.mrp-dot-sufficient {
  background: #22c55e;
}

/* Sort Controls */
.mrp-sort-control {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #f8fafc;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e2e8f0);
}

.mrp-sort-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted, #64748b);
  white-space: nowrap;
}

.mrp-sort-select {
  font-size: 11px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #cbd5e1);
  padding: 1px 6px;
  height: 24px;
  background: var(--card-bg, #ffffff);
  color: var(--text-color, #334155);
}

.mrp-active-sort-pill {
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  font-weight: 600;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 2px 7px;
  border-radius: 12px;
  cursor: pointer;
  white-space: nowrap;
  border: 1px solid #bfdbfe;
  transition: all 0.12s ease;
}

.mrp-active-sort-pill:hover {
  background: #bfdbfe;
}

.mrp-sort-clear-icon {
  font-size: 9px;
  opacity: 0.7;
}

.mrp-active-sort-pill:hover .mrp-sort-clear-icon {
  opacity: 1;
}
</style>
