<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  MaterialShortageItemRow,
  MaterialShortageResponse,
  MaterialShortageStatusFilter,
  MaterialShortageWorkOrderRow,
} from "../../types";
import { exportRowsToCsv, formatCsvToday } from "../../reports/csvExport";
import { formatQty, formatTimestamp } from "../../reports/operationFormatters";
import { sortItems, toggleSortState, type SortDirection } from "../../reports/tableSort";
import MaterialShortageItemsRow from "./MaterialShortageItemsRow.vue";
import SortableTh from "./SortableTh.vue";

type ShortageSortKey =
  | "work_order"
  | "production_item"
  | "qty"
  | "shortage_status"
  | "readiness_pct"
  | "wo_creation"
  | "planned_start_date";

const __ = (...args: any[]) => (window as any).__(...args);
const emit = defineEmits<{ (e: "select-work-order", workOrder: string): void }>();

const statusFilter = ref<MaterialShortageStatusFilter>("all");
const warehouseFilter = ref<string>("");
const searchQuery = ref<string>("");
const loading = ref<boolean>(false);
const errorMessage = ref<string | null>(null);
const reportData = ref<MaterialShortageResponse | null>(null);
const expandedWorkOrders = ref<Record<string, boolean>>({});
const sortKey = ref<ShortageSortKey>("wo_creation");
const sortDir = ref<SortDirection>("desc");

let latestRequestId = 0;
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const EMPTY_SUMMARY = {
  total_work_orders: 0,
  critical_work_orders: 0,
  transfer_work_orders: 0,
  resolved_work_orders: 0,
  total_shortage_items: 0,
};
const EMPTY_COUNTS = { all: 0, active_shortage: 0, critical: 0, transfer_required: 0, resolved: 0 };

const rows = computed<MaterialShortageWorkOrderRow[]>(() => reportData.value?.rows || []);
const counts = computed(() => reportData.value?.counts || EMPTY_COUNTS);
const summary = computed(() => reportData.value?.summary || EMPTY_SUMMARY);
const warehouses = computed(() => reportData.value?.filter_options?.warehouses || []);
const hasActiveFilters = computed(() => Boolean(warehouseFilter.value || searchQuery.value.trim()));

const statusTabs = computed(() => [
  { id: "all" as const, label: __("Tümü"), count: counts.value.all },
  { id: "critical" as const, label: __("Kritik Eksik"), count: counts.value.critical },
  { id: "transfer_required" as const, label: __("Transfer Gerekli"), count: counts.value.transfer_required },
  { id: "resolved" as const, label: __("Stok Tamamlandı"), count: counts.value.resolved },
]);

const SEVERITY_RANK: Record<MaterialShortageWorkOrderRow["shortage_status"], number> = {
  critical: 0,
  transfer_required: 1,
  resolved: 2,
};

const SHORTAGE_SORT_ACCESSORS: Record<ShortageSortKey, (r: MaterialShortageWorkOrderRow) => string | number> = {
  work_order: (r) => r.work_order,
  production_item: (r) => r.production_item,
  qty: (r) => r.qty,
  shortage_status: (r) => SEVERITY_RANK[r.shortage_status] ?? 9,
  readiness_pct: (r) => r.readiness_pct,
  wo_creation: (r) => r.wo_creation || "",
  planned_start_date: (r) => r.planned_start_date || "",
};

const sortedRows = computed<MaterialShortageWorkOrderRow[]>(() =>
  sortItems(rows.value, SHORTAGE_SORT_ACCESSORS[sortKey.value], sortDir.value, (r) => r.work_order)
);

const allExpanded = computed<boolean>(
  () => sortedRows.value.length > 0 && sortedRows.value.every((r) => Boolean(expandedWorkOrders.value[r.work_order]))
);

function handleSort(key: string) {
  const next = toggleSortState(sortKey.value, sortDir.value, key as ShortageSortKey);
  sortKey.value = next.key;
  sortDir.value = next.dir;
}

function severityLabel(status: MaterialShortageWorkOrderRow["shortage_status"]): string {
  if (status === "critical") return __("Kritik Eksik");
  if (status === "transfer_required") return __("Transfer Gerekli");
  return __("Stok Tamamlandı");
}

function severityIcon(status: MaterialShortageWorkOrderRow["shortage_status"]): string {
  if (status === "critical") return "🚫";
  if (status === "transfer_required") return "⚠️";
  return "✅";
}

function itemStatusLabel(item: MaterialShortageItemRow): string {
  if (item.availability_status === "critical" || item.availability_status === "critical_shortage") {
    return __("Kritik Eksik");
  }
  if (item.availability_status === "transfer_required") return __("Transfer Gerekli");
  return __("Mevcut");
}

async function fetchReport() {
  const reqId = ++latestRequestId;
  loading.value = true;
  errorMessage.value = null;

  try {
    const res = await new Promise<MaterialShortageResponse>((resolve, reject) => {
      frappe.call({
        method: "erpnextkta.kta_shopfloor.api.get_material_shortage_report",
        args: {
          shortage_filter: statusFilter.value,
          warehouse: warehouseFilter.value || null,
          search: searchQuery.value.trim() || null,
        },
        quiet: true,
        callback: (r: { message?: MaterialShortageResponse }) => {
          if ((window as any).frappe) (window as any).frappe.messages = [];
          resolve(r.message as MaterialShortageResponse);
        },
        error: (err: any) => {
          if ((window as any).frappe) (window as any).frappe.messages = [];
          reject(err);
        },
      });
    });
    if (reqId !== latestRequestId) return;
    reportData.value = res || {
      rows: [],
      summary: { ...EMPTY_SUMMARY },
      counts: { ...EMPTY_COUNTS },
      filter_options: { warehouses: [] },
    };
  } catch (err: any) {
    if (reqId !== latestRequestId) return;
    errorMessage.value = err?.message || __("Eksik malzeme raporu alınamadı.");
  } finally {
    if (reqId === latestRequestId) loading.value = false;
  }
}

function setStatusTab(tab: MaterialShortageStatusFilter) {
  if (statusFilter.value === tab) return;
  statusFilter.value = tab;
  fetchReport();
}

function clearFilters() {
  warehouseFilter.value = "";
  searchQuery.value = "";
  if (searchTimer) { clearTimeout(searchTimer); searchTimer = null; }
  fetchReport();
}

function toggleWorkOrder(wo: string) {
  expandedWorkOrders.value[wo] = !expandedWorkOrders.value[wo];
}

function toggleExpandAll() {
  const expand = !allExpanded.value;
  const next: Record<string, boolean> = {};
  if (expand) {
    for (const r of sortedRows.value) next[r.work_order] = true;
  }
  expandedWorkOrders.value = next;
}

function handleExportCsv() {
  if (!sortedRows.value.length) return;
  const headers = [
    __("İş Emri"), __("İş Emri Durumu"), __("Ürün Kodu"), __("Ürün Adı"),
    __("Planlanan"), __("Üretilen"), __("Birim"), __("Stok Durumu"),
    __("Hazırlık %"), __("Oluşturma Tarihi"), __("Planlanan Başlangıç"), __("Hammadde"),
    __("Hammadde Adı"), __("Operasyon"), __("Kaynak Depo"),
    __("Kalan İhtiyaç"), __("Hammadde Birimi"), __("Hat Deposu"),
    __("Diğer Depolar"), __("Eksik Miktar"), __("Kalem Durumu"),
  ];
  const csvRows: unknown[][] = [];
  for (const r of sortedRows.value) {
    const items = r.items && r.items.length > 0 ? r.items : [null];
    for (const item of items) {
      csvRows.push([
        r.work_order, r.wo_status || "", r.production_item, r.item_name || "",
        r.qty, r.produced_qty, r.stock_uom || "", severityLabel(r.shortage_status),
        r.readiness_pct, r.wo_creation || "", r.planned_start_date || "",
        item ? item.item_code : "", item ? item.item_name || "" : "",
        item ? item.operation || "" : "", item ? item.source_warehouse || "" : "",
        item ? item.remaining_required_qty : "", item ? item.stock_uom || "" : "",
        item ? item.line_actual_qty : "", item ? item.other_warehouses_qty : "",
        item ? item.shortage_qty : "", item ? itemStatusLabel(item) : "",
      ]);
    }
  }
  exportRowsToCsv(`shopfloor-eksik-malzeme-${formatCsvToday()}.csv`, headers, csvRows);
}

watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => fetchReport(), 300);
});

onMounted(() => fetchReport());
onUnmounted(() => { if (searchTimer) clearTimeout(searchTimer); });
</script>

<template>
  <div class="shortage-report-root">
    <!-- Top Toolbar -->
    <div class="report-toolbar">
      <div class="status-pills" role="tablist">
        <button
          v-for="tab in statusTabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="statusFilter === tab.id"
          class="status-pill-btn"
          :class="{ active: statusFilter === tab.id }"
          @click="setStatusTab(tab.id)"
        >
          <span>{{ tab.label }}</span>
          <span class="pill-count">{{ tab.count }}</span>
        </button>
      </div>
      <div class="toolbar-actions">
        <button type="button" class="btn-tool" :disabled="loading" @click="fetchReport()">
          <span :class="{ spinning: loading }">↻</span> {{ __("Yenile") }}
        </button>
        <button type="button" class="btn-tool btn-export" :disabled="loading || rows.length === 0" @click="handleExportCsv">
          ⬇ {{ __("CSV İndir") }}
        </button>
      </div>
    </div>

    <!-- KPI Strip -->
    <div class="kpi-strip">
      <div class="kpi-box">
        <span class="kpi-lbl">{{ __("Eksikle Açılan İş Emri") }}</span>
        <strong class="kpi-val">{{ summary.total_work_orders }}</strong>
      </div>
      <div class="kpi-box kpi-red">
        <span class="kpi-lbl">{{ __("Kritik Eksik") }}</span>
        <strong class="kpi-val">{{ summary.critical_work_orders }}</strong>
      </div>
      <div class="kpi-box kpi-amber">
        <span class="kpi-lbl">{{ __("Transfer Gerekli") }}</span>
        <strong class="kpi-val">{{ summary.transfer_work_orders }}</strong>
      </div>
      <div class="kpi-box kpi-blue">
        <span class="kpi-lbl">{{ __("Toplam Eksik Kalem") }}</span>
        <strong class="kpi-val">{{ summary.total_shortage_items }}</strong>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <input
        v-model="searchQuery"
        type="text"
        class="filter-input filter-search"
        :placeholder="__('İş Emri, Ürün veya Hammadde Ara…')"
      />
      <select v-model="warehouseFilter" class="filter-select" @change="fetchReport()">
        <option value="">{{ __("Tüm Kaynak Depolar") }}</option>
        <option v-for="wh in warehouses" :key="wh" :value="wh">{{ wh }}</option>
      </select>
      <button v-if="hasActiveFilters" type="button" class="btn-clear-filters" @click="clearFilters">
        ✕ {{ __("Filtreleri Temizle") }}
      </button>
    </div>

    <!-- States & Table -->
    <div v-if="errorMessage" class="report-state report-error">
      <span>⚠️ {{ errorMessage }}</span>
      <button type="button" class="btn-tool" @click="fetchReport()">{{ __("Tekrar Dene") }}</button>
    </div>

    <div v-else-if="loading && !reportData" class="report-state">
      <div class="report-spinner" aria-hidden="true" />
      <span>{{ __("Rapor verileri yükleniyor…") }}</span>
    </div>

    <div v-else-if="sortedRows.length === 0" class="report-state">
      <span class="empty-emoji">📭</span>
      <strong>{{ __("Kayıt Bulunamadı") }}</strong>
      <span class="empty-sub">{{ __("Seçili filtrelere uygun eksik malzemeli aktif iş emri yok.") }}</span>
    </div>

    <div v-else class="table-card">
      <div class="table-scroll">
        <table class="report-table">
          <thead>
            <tr>
              <th class="col-exp">
                <button type="button" class="btn-expand" :title="allExpanded ? __('Tümünü Daralt') : __('Tümünü Genişlet')" @click="toggleExpandAll">
                  {{ allExpanded ? "▼" : "▶" }}
                </button>
              </th>
              <SortableTh :label="__('İş Emri')" sort-key="work_order" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Ürün')" sort-key="production_item" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Planlanan / Üretilen')" sort-key="qty" :active-key="sortKey" :sort-dir="sortDir" align="right" @sort="handleSort" />
              <SortableTh :label="__('Stok Durumu')" sort-key="shortage_status" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Hazırlık %')" sort-key="readiness_pct" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Oluşturma')" sort-key="wo_creation" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Planlanan Başlangıç')" sort-key="planned_start_date" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <th class="text-right">{{ __("İşlem") }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in sortedRows" :key="row.work_order">
              <tr
                class="data-row"
                :class="{ expanded: expandedWorkOrders[row.work_order] }"
                @click="toggleWorkOrder(row.work_order)"
              >
                <td class="col-exp">
                  <button type="button" class="btn-expand" :aria-expanded="Boolean(expandedWorkOrders[row.work_order])" @click.stop="toggleWorkOrder(row.work_order)">
                    {{ expandedWorkOrders[row.work_order] ? "▼" : "▶" }}
                  </button>
                </td>
                <td>
                  <div class="wo-cell">
                    <a :href="`/app/work-order/${row.work_order}`" target="_blank" class="wo-link" @click.stop>{{ row.work_order }}</a>
                    <span v-if="row.wo_status" class="wo-status-tag">{{ __(row.wo_status) }}</span>
                  </div>
                </td>
                <td>
                  <div class="item-cell">
                    <span class="item-code">{{ row.production_item }}</span>
                    <span v-if="row.item_name && row.item_name !== row.production_item" class="item-name" :title="row.item_name">
                      {{ row.item_name }}
                    </span>
                  </div>
                </td>
                <td class="text-right num-cell">
                  <strong>{{ formatQty(row.qty) }}</strong> <small v-if="row.stock_uom">{{ row.stock_uom }}</small>
                  <span class="qty-sep">/</span>
                  <span class="muted-cell">{{ formatQty(row.produced_qty) }}</span>
                </td>
                <td>
                  <div class="sev-cell">
                    <span class="sev-badge" :class="`sev-${row.shortage_status}`">
                      <span aria-hidden="true">{{ severityIcon(row.shortage_status) }}</span>
                      <span>{{ severityLabel(row.shortage_status) }}</span>
                    </span>
                    <span class="sev-sub">{{ __("{0}/{1} Eksik", [row.shortage_items_count, row.total_items]) }}</span>
                  </div>
                </td>
                <td>
                  <div class="pct-wrap">
                    <div class="pct-track">
                      <div class="pct-fill" :class="`fill-${row.shortage_status}`" :style="{ width: `${Math.min(100, Math.max(0, Number(row.readiness_pct) || 0))}%` }" />
                    </div>
                    <span class="pct-text">%{{ row.readiness_pct }}</span>
                  </div>
                </td>
                <td class="muted-cell num-cell">{{ formatTimestamp(row.wo_creation || "") }}</td>
                <td class="muted-cell num-cell">{{ row.planned_start_date || "—" }}</td>
                <td class="text-right">
                  <button
                    type="button"
                    class="btn-go-wo"
                    @click.stop="emit('select-work-order', row.work_order)"
                  >
                    {{ __("İş Emrine Git") }} →
                  </button>
                </td>
              </tr>
              <MaterialShortageItemsRow
                v-if="expandedWorkOrders[row.work_order]"
                :items="row.items || []"
              />
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shortage-report-root { display: flex; flex-direction: column; gap: 1rem; color: var(--text-color, #0f172a); }
.report-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; }
.status-pills { display: inline-flex; flex-wrap: wrap; gap: 0.45rem; }
.status-pill-btn {
  display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.42rem 0.85rem; border-radius: 9999px;
  border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-muted, #64748b);
  font-size: 0.8rem; font-weight: 700; cursor: pointer; transition: all 0.15s;
}
.status-pill-btn.active { background: #2563eb; border-color: #2563eb; color: #ffffff; }
.pill-count { padding: 0.08rem 0.42rem; border-radius: 9999px; font-size: 0.72rem; background: rgba(148, 163, 184, 0.2); }
.status-pill-btn.active .pill-count { background: rgba(255, 255, 255, 0.24); }
.toolbar-actions { display: inline-flex; gap: 0.5rem; flex-wrap: wrap; }
.btn-tool {
  display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.42rem 0.8rem; border-radius: 0.45rem;
  border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #334155);
  font-size: 0.8rem; font-weight: 700; cursor: pointer;
}
.btn-tool:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-export { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
[data-theme="dark"] .btn-export { background: rgba(59, 130, 246, 0.16); border-color: rgba(96, 165, 250, 0.35); color: #93c5fd; }
.kpi-strip { display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 0.75rem; }
@media (max-width: 900px) { .kpi-strip { grid-template-columns: repeat(2, 1fr); } }
.kpi-box { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.65rem; padding: 0.75rem 1rem; display: flex; flex-direction: column; gap: 0.25rem; }
[data-theme="dark"] .kpi-box { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.kpi-lbl { font-size: 0.72rem; font-weight: 700; color: var(--text-muted, #64748b); }
.kpi-val { font-size: 1.35rem; font-weight: 800; }
.kpi-red .kpi-val { color: #dc2626; }
[data-theme="dark"] .kpi-red .kpi-val { color: #f87171; }
.kpi-amber .kpi-val { color: #d97706; }
[data-theme="dark"] .kpi-amber .kpi-val { color: #fbbf24; }
.kpi-blue .kpi-val { color: #2563eb; }
[data-theme="dark"] .kpi-blue .kpi-val { color: #60a5fa; }
.filter-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; padding: 0.8rem; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.65rem; }
[data-theme="dark"] .filter-bar { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.filter-input, .filter-select { height: 34px; padding: 0 0.6rem; border-radius: 0.42rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--bg-color, #f8fafc); color: var(--text-color, #0f172a); font-size: 0.8rem; outline: none; }
[data-theme="dark"] .filter-input, [data-theme="dark"] .filter-select { background: #14181d; border-color: rgba(255, 255, 255, 0.18); }
.filter-search { flex: 1 1 240px; min-width: 200px; }
.filter-select { flex: 0 1 220px; }
.btn-clear-filters { height: 34px; padding: 0 0.7rem; border-radius: 0.42rem; border: 1px solid #fecaca; background: #fef2f2; color: #b91c1c; font-size: 0.76rem; font-weight: 700; cursor: pointer; }
[data-theme="dark"] .btn-clear-filters { background: rgba(239, 68, 68, 0.16); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.report-state { padding: 3rem 1rem; text-align: center; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; color: var(--text-muted, #64748b); font-size: 0.85rem; }
[data-theme="dark"] .report-state { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.report-error { color: #b91c1c; }
.report-spinner { width: 26px; height: 26px; border: 3px solid rgba(37, 99, 235, 0.2); border-top-color: #2563eb; border-radius: 50%; animation: spin 0.8s linear infinite; }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.table-card { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; overflow: hidden; }
[data-theme="dark"] .table-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.table-scroll { overflow-x: auto; }
.report-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.report-table th { text-align: left; padding: 0.65rem 0.7rem; background: var(--bg-color, #f8fafc); color: var(--text-muted, #64748b); font-weight: 700; border-bottom: 1px solid var(--border-color, #e2e8f0); white-space: nowrap; }
[data-theme="dark"] .report-table th { background: rgba(255, 255, 255, 0.04); }
.data-row { cursor: pointer; transition: background-color 0.12s; }
.data-row:hover { background: rgba(37, 99, 235, 0.04); }
.data-row td { padding: 0.62rem 0.7rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
.col-exp { width: 32px; text-align: center; }
.btn-expand { background: transparent; border: none; color: var(--text-muted, #64748b); cursor: pointer; font-size: 0.72rem; }
.wo-cell, .item-cell, .sev-cell { display: flex; flex-direction: column; gap: 0.15rem; }
.wo-link { font-weight: 800; color: #2563eb; text-decoration: none; white-space: nowrap; }
.wo-link:hover { text-decoration: underline; }
[data-theme="dark"] .wo-link { color: #60a5fa; }
.wo-status-tag { font-size: 0.68rem; color: var(--text-muted, #64748b); font-weight: 600; }
.item-code { font-weight: 700; }
.item-name { font-size: 0.7rem; color: var(--text-muted, #64748b); max-width: 190px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted-cell { color: var(--text-muted, #64748b); }
.num-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
.qty-sep { margin: 0 0.2rem; color: var(--text-muted, #94a3b8); }
.sev-badge { display: inline-flex; align-items: center; gap: 0.25rem; width: fit-content; font-size: 0.7rem; font-weight: 800; padding: 0.12rem 0.5rem; border-radius: 9999px; white-space: nowrap; }
.sev-critical { background: #fee2e2; color: #b91c1c; }
.sev-transfer_required { background: #fef3c7; color: #b45309; }
.sev-resolved { background: #dcfce7; color: #15803d; }
[data-theme="dark"] .sev-critical { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
[data-theme="dark"] .sev-transfer_required { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
[data-theme="dark"] .sev-resolved { background: rgba(34, 197, 94, 0.18); color: #86efac; }
.sev-sub { font-size: 0.68rem; color: var(--text-muted, #64748b); font-weight: 600; }
.pct-wrap { display: flex; align-items: center; gap: 0.45rem; min-width: 100px; }
.pct-track { flex: 1; height: 6px; border-radius: 9999px; background: #e2e8f0; overflow: hidden; }
[data-theme="dark"] .pct-track { background: rgba(255, 255, 255, 0.12); }
.pct-fill { height: 100%; border-radius: 9999px; background: #2563eb; }
.fill-critical { background: #dc2626; }
.fill-transfer_required { background: #f59e0b; }
.fill-resolved { background: #16a34a; }
.pct-text { font-size: 0.74rem; font-weight: 800; min-width: 38px; text-align: right; }
.btn-go-wo { padding: 0.3rem 0.6rem; border-radius: 0.4rem; border: 1px solid rgba(37, 99, 235, 0.3); background: rgba(37, 99, 235, 0.08); color: #2563eb; font-size: 0.74rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
.btn-go-wo:hover { background: #2563eb; color: #ffffff; }
[data-theme="dark"] .btn-go-wo { color: #93c5fd; border-color: rgba(96, 165, 250, 0.35); }
.text-right { text-align: right; }
</style>
