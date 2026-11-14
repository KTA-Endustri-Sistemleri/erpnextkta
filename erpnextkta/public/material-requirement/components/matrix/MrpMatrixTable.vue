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
            <!-- Sticky Fixed Left Column Header -->
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

            <!-- Weekly Timeline Column Headers -->
            <th
              v-for="w in weeks"
              :key="w.key"
              :class="[
                'mrp-th-week',
                'mrp-th-sticky-top',
                {
                  'mrp-th-current-week': w.is_current,
                  'mrp-th-sorted': sortBy === w.key
                }
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
          <template v-for="m in filteredMaterials" :key="m.item_code">
            <!-- Main Material Row -->
            <tr
              class="mrp-row-main"
              :class="{ 'mrp-row-expanded': isRowExpanded(m.item_code) }"
            >
              <!-- Left Frozen Cell -->
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

            <!-- Accordion Details Row -->
            <tr
              v-if="isRowExpanded(m.item_code)"
              class="mrp-row-accordion"
            >
              <td :colspan="1 + weeks.length" class="mrp-td-accordion">
                <div class="mrp-accordion-wrapper">
                  <!-- Selected Week Calculation Summary Strip (Replaces Modal!) -->
                  <div
                    v-if="activeWeekFilter[m.item_code] && getSelectedWeekMetrics(m)"
                    class="mrp-week-summary-strip mb-3"
                  >
                    <div class="mrp-strip-header d-flex justify-content-between align-items-center mb-2">
                      <div class="d-flex align-items-center">
                        <i class="fa fa-calculator text-primary mr-2"></i>
                        <span class="font-weight-bold" style="font-size: 12px;">
                          📅 {{ __("{0} Netleştirme Hesabı Özeti", [getWeekLabel(activeWeekFilter[m.item_code])]) }}
                        </span>
                        <span class="badge badge-light border ml-2 text-muted" style="font-size: 11px;">
                          {{ m.item_code }}
                        </span>
                      </div>
                      <button
                        type="button"
                        class="btn btn-xs btn-link text-muted"
                        @click="clearWeekFilter(m.item_code)"
                      >
                        <i class="fa fa-times mr-1"></i>{{ __("Hafta Filtresini Kaldır") }}
                      </button>
                    </div>

                    <div class="mrp-strip-cards">
                      <div class="mrp-strip-card">
                        <span class="mrp-strip-label">1. {{ __("Devreden Bakiye") }}</span>
                        <span
                          class="mrp-strip-val"
                          :class="getBalanceBefore(m, activeWeekFilter[m.item_code]) < 0 ? 'text-danger' : 'text-success'"
                        >
                          {{ formatQty(getBalanceBefore(m, activeWeekFilter[m.item_code])) }} {{ m.uom }}
                        </span>
                      </div>
                      <div class="mrp-strip-card">
                        <span class="mrp-strip-label">2. {{ __("Açık Teslimat") }} (+)</span>
                        <span class="mrp-strip-val text-primary">
                          +{{ formatQty(getSelectedWeekMetrics(m).po) }} {{ m.uom }}
                        </span>
                      </div>
                      <div class="mrp-strip-card">
                        <span class="mrp-strip-label">3. {{ __("Brüt İhtiyaç") }} (-)</span>
                        <span class="mrp-strip-val text-danger">
                          -{{ formatQty(getSelectedWeekMetrics(m).gross) }} {{ m.uom }}
                        </span>
                      </div>
                      <div
                        class="mrp-strip-card"
                        :class="{ 'card-shortage': getSelectedWeekMetrics(m).net > 0 }"
                      >
                        <span class="mrp-strip-label">4. {{ __("Net Eksik") }}</span>
                        <span
                          class="mrp-strip-val"
                          :class="getSelectedWeekMetrics(m).net > 0 ? 'text-danger font-weight-bold' : 'text-muted'"
                        >
                          {{ formatQty(getSelectedWeekMetrics(m).net) }} {{ m.uom }}
                        </span>
                      </div>
                      <div class="mrp-strip-card card-order">
                        <span class="mrp-strip-label">5. {{ __("Önerilen Sipariş") }}</span>
                        <span class="mrp-strip-val text-purple font-weight-bold">
                          {{ formatQty(getSelectedWeekMetrics(m).order) }} {{ m.uom }}
                        </span>
                      </div>
                      <div class="mrp-strip-card">
                        <span class="mrp-strip-label">6. {{ __("Projeksiyon Bakiye") }}</span>
                        <span
                          class="mrp-strip-val"
                          :class="getSelectedWeekMetrics(m).projected < 0 ? 'text-danger' : 'text-success'"
                        >
                          {{ formatQty(getSelectedWeekMetrics(m).projected) }} {{ m.uom }}
                        </span>
                      </div>
                    </div>
                  </div>

                  <!-- Sourcing Strategy & Supplier Planned Orders Breakdown -->
                  <MrpSupplierPlannedOrders
                    v-if="m.planned_orders_by_supplier && Object.keys(m.planned_orders_by_supplier).length > 1"
                    :material="m"
                    :weeks="weeks"
                    :selected-week="activeWeekFilter[m.item_code]"
                  />

                  <!-- Demand Pegging Breakdown -->
                  <MrpPeggingList
                    v-if="m.pegging && m.pegging.length > 0"
                    :pegging="m.pegging"
                    :weeks="weeks"
                    :uom="m.uom"
                    :selected-week="activeWeekFilter[m.item_code]"
                  />

                  <!-- Open Delivery & PO Breakdown -->
                  <MrpPoReceiptList
                    v-if="(m.open_supplies && m.open_supplies.length > 0) || (m.open_pos && m.open_pos.length > 0) || activeWeekFilter[m.item_code]"
                    :supplies="m.open_supplies"
                    :pos="m.open_pos"
                    :uom="m.uom"
                    :selected-week="activeWeekFilter[m.item_code]"
                    @select-week="(w) => setWeekFilter(m.item_code, w)"
                  />

                  <!-- If neither exists -->
                  <div
                    v-if="(!m.pegging || m.pegging.length === 0) && (!m.open_supplies || m.open_supplies.length === 0) && (!m.open_pos || m.open_pos.length === 0) && (!m.planned_orders_by_supplier || Object.keys(m.planned_orders_by_supplier).length <= 1) && !activeWeekFilter[m.item_code]"
                    class="text-muted small py-2 px-3 text-center"
                  >
                    <i>{{ __("Bu malzeme için bekleyen açık teslimat veya mamul kırılımı bulunmamaktadır.") }}</i>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useMrpState } from "../../composables/useMrpState";
import MrpItemIdentity from "./MrpItemIdentity.vue";
import MrpWeekCell from "./MrpWeekCell.vue";
import MrpPeggingList from "../accordion/MrpPeggingList.vue";
import MrpPoReceiptList from "../accordion/MrpPoReceiptList.vue";
import MrpSupplierPlannedOrders from "../accordion/MrpSupplierPlannedOrders.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const {
  weeks,
  filteredMaterials,
  loading,
  isRowExpanded,
  activeWeekFilter,
  setWeekFilter,
  clearWeekFilter,
  sortBy,
  sortOrder,
  setSortColumn,
} = useMrpState();

function getWeekLabel(weekKey: string): string {
  const w = weeks.value.find((x) => x.key === weekKey);
  return w ? w.label : weekKey;
}

function getBalanceBefore(m: any, weekKey: string): number {
  const wIdx = weeks.value.findIndex((x) => x.key === weekKey);
  if (wIdx <= 0) return Number(m.free_stock || 0);
  const prevWk = weeks.value[wIdx - 1]?.key;
  return Number(m.weeks?.[prevWk]?.projected ?? m.free_stock ?? 0);
}

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

function getSelectedWeekMetrics(m: any) {
  const wk = activeWeekFilter[m.item_code];
  if (!wk || !m.weeks) return null;
  return m.weeks[wk] || null;
}
</script>

<style scoped>
.mrp-matrix-container {
  position: relative;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.mrp-loading-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background: rgba(255, 255, 255, 0.85);
}

.mrp-empty-state {
  text-align: center;
  padding: 50px 20px;
}

.mrp-empty-icon {
  font-size: 32px;
  color: #94a3b8;
  margin-bottom: 12px;
}

.mrp-table-viewport {
  overflow-x: auto;
  overflow-y: visible;
  max-height: calc(100vh - 240px);
  position: relative;
}

.mrp-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-family: inherit;
  font-size: 12px;
}

/* Sticky Headers */
.mrp-th-sticky-top {
  position: sticky;
  top: 0;
  z-index: 20;
  background: #f8fafc;
  border-bottom: 2px solid #cbd5e1;
}

/* Sticky Fixed Left Column */
.mrp-th-fixed {
  position: sticky;
  left: 0;
  z-index: 30;
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  background: #f1f5f9;
  border-right: 2px solid #cbd5e1;
  padding: 8px 12px;
  text-align: left;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.12s ease;
}

.mrp-th-fixed:hover {
  background: #e2e8f0;
}

.mrp-td-fixed {
  position: sticky;
  left: 0;
  z-index: 10;
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  background: #ffffff;
  border-right: 2px solid #cbd5e1;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  padding: 8px 12px;
}

.mrp-row-main:hover .mrp-td-fixed {
  background: #f8fafc;
}

.mrp-th-fixed-content {
  display: flex;
  flex-direction: column;
}

.mrp-th-main-title {
  font-weight: 700;
  font-size: 12px;
  color: #1e293b;
}

.mrp-th-sub-title {
  font-size: 10px;
  color: #64748b;
  font-weight: normal;
}

/* Week Columns */
.mrp-th-week {
  min-width: 90px;
  padding: 6px 8px;
  text-align: right;
  border-right: 1px solid #e2e8f0;
  vertical-align: bottom;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.12s ease;
}

.mrp-th-week:hover {
  background: #f1f5f9;
}

.mrp-th-sorted {
  background: #e0f2fe !important;
  color: #0369a1 !important;
  border-bottom: 2px solid #0284c7 !important;
}

.mrp-sort-indicator {
  color: #0284c7;
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
  color: #334155;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.mrp-th-current-week {
  background: #eff6ff !important;
  border-bottom: 2px solid #3b82f6 !important;
}

.mrp-current-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  color: #2563eb;
  background: #dbeafe;
  padding: 1px 4px;
  border-radius: 3px;
  margin-top: 2px;
}

/* Accordion Row */
.mrp-row-accordion {
  background: #f8fafc;
}

.mrp-td-accordion {
  padding: 0 !important;
  border-bottom: 2px solid #cbd5e1;
}

.mrp-accordion-wrapper {
  padding: 12px 16px 16px 12px;
  background: #f8fafc;
}

.mrp-row-expanded .mrp-td-fixed {
  border-bottom: none !important;
}

/* Selected Week Netting Summary Strip */
.mrp-week-summary-strip {
  background: #ffffff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 10px 14px;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.06);
}

.mrp-strip-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}

@media (max-width: 992px) {
  .mrp-strip-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

.mrp-strip-card {
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 6px 10px;
  text-align: right;
}

.mrp-strip-label {
  font-size: 10px;
  color: #64748b;
  font-weight: 600;
  text-align: left;
  margin-bottom: 3px;
}

.mrp-strip-val {
  font-size: 13px;
  font-weight: 600;
}

.mrp-strip-card.card-shortage {
  background: #fff7ed;
  border-color: #fdba74;
}

.mrp-strip-card.card-order {
  background: #f5f3ff;
  border-color: #c4b5fd;
}
</style>
