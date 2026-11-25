<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  ConfirmationRecord,
  OperationCompletionResponse,
  OperationCompletionRow,
  OperationCompletionStatusFilter,
  OperationCompletionWorkOrderGroup,
} from "../../types";
import { exportRowsToCsv, formatCsvToday } from "../../reports/csvExport";
import {
  formatQty,
  formatTimestamp,
  getCompletionPct,
  getConfirmedQty,
  getLastConfirmedAt,
  getWoQty,
  groupRowsByWorkOrder,
  isOpCompleted,
  opRowKey,
} from "../../reports/operationFormatters";
import { sortItems, toggleSortState, type SortDirection } from "../../reports/tableSort";
import OperationCompletionFilters from "./OperationCompletionFilters.vue";
import OperationCompletionGroupRows from "./OperationCompletionGroupRows.vue";
import SortableTh from "./SortableTh.vue";

type OpSortKey =
  | "work_order"
  | "production_item"
  | "operations_count"
  | "qty"
  | "overall_pct"
  | "wo_creation"
  | "last_confirmation_at";

const __ = (...args: any[]) => (window as any).__(...args);
const emit = defineEmits<{ (e: "select-work-order", workOrder: string, operation: string): void }>();

const statusFilter = ref<OperationCompletionStatusFilter>("completed");
const operationFilter = ref<string>("");
const workstationFilter = ref<string>("");
const fromDate = ref<string>("");
const toDate = ref<string>("");
const searchQuery = ref<string>("");
const loading = ref<boolean>(false);
const errorMessage = ref<string | null>(null);
const reportData = ref<OperationCompletionResponse | null>(null);
const expandedWorkOrders = ref<Record<string, boolean>>({});
const expandedOps = ref<Record<string, boolean>>({});
const confirmationsCache = ref<Record<string, ConfirmationRecord[]>>({});
const sortKey = ref<OpSortKey>("wo_creation");
const sortDir = ref<SortDirection>("desc");

let latestRequestId = 0;
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const EMPTY_SUMMARY = {
  completed_operations: 0,
  partial_operations: 0,
  unconfirmed_operations: 0,
  unique_work_orders: 0,
  total_confirmed_qty: 0,
};
const EMPTY_COUNTS = { completed: 0, partial: 0, unconfirmed: 0, all: 0 };

const rows = computed(() => reportData.value?.rows || []);
const counts = computed(() => reportData.value?.counts || EMPTY_COUNTS);
const summary = computed(() => reportData.value?.summary || EMPTY_SUMMARY);
const filterOptions = computed(() => reportData.value?.filter_options || { operations: [], workstations: [] });
const hasActiveFilters = computed(() =>
  Boolean(operationFilter.value || workstationFilter.value || fromDate.value || toDate.value || searchQuery.value.trim())
);

const statusTabs = computed(() => [
  { id: "completed" as const, label: __("Tamamlananlar"), count: counts.value.completed },
  { id: "partial" as const, label: __("Kısmi Üretimler"), count: counts.value.partial },
  { id: "unconfirmed" as const, label: __("Teyit Olmayanlar"), count: counts.value.unconfirmed ?? 0 },
  { id: "all" as const, label: __("Tümü"), count: counts.value.all },
]);

const groupedWorkOrders = computed<OperationCompletionWorkOrderGroup[]>(() =>
  groupRowsByWorkOrder(rows.value)
);

const OP_SORT_ACCESSORS: Record<OpSortKey, (g: OperationCompletionWorkOrderGroup) => string | number> = {
  work_order: (g) => g.work_order,
  production_item: (g) => g.production_item,
  operations_count: (g) => g.operations.length,
  qty: (g) => g.qty,
  overall_pct: (g) => g.overall_pct,
  wo_creation: (g) => g.wo_creation,
  last_confirmation_at: (g) => g.last_confirmation_at,
};

const sortedWorkOrders = computed<OperationCompletionWorkOrderGroup[]>(() =>
  sortItems(groupedWorkOrders.value, OP_SORT_ACCESSORS[sortKey.value], sortDir.value, (g) => g.work_order)
);

const allExpanded = computed<boolean>(
  () => sortedWorkOrders.value.length > 0 && sortedWorkOrders.value.every((g) => Boolean(expandedWorkOrders.value[g.work_order]))
);

function handleSort(key: string) {
  const next = toggleSortState(sortKey.value, sortDir.value, key as OpSortKey);
  sortKey.value = next.key;
  sortDir.value = next.dir;
}

async function fetchReport(clearDetailCache = false) {
  const reqId = ++latestRequestId;
  loading.value = true;
  errorMessage.value = null;
  if (clearDetailCache) confirmationsCache.value = {};

  try {
    const res = await new Promise<OperationCompletionResponse>((resolve, reject) => {
      frappe.call({
        method: "erpnextkta.kta_shopfloor.api.get_operation_completion_report",
        args: {
          status_filter: statusFilter.value,
          operation: operationFilter.value || null,
          workstation: workstationFilter.value || null,
          from_date: fromDate.value || null,
          to_date: toDate.value || null,
          search: searchQuery.value.trim() || null,
        },
        quiet: true,
        callback: (r: { message?: OperationCompletionResponse }) => {
          if ((window as any).frappe) (window as any).frappe.messages = [];
          resolve(r.message as OperationCompletionResponse);
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
      filter_options: { operations: [], workstations: [] },
    };
  } catch (err: any) {
    if (reqId !== latestRequestId) return;
    errorMessage.value = err?.message || __("Operasyon tamamlanma raporu alınamadı.");
  } finally {
    if (reqId === latestRequestId) loading.value = false;
  }
}

function setStatusTab(tab: OperationCompletionStatusFilter) {
  if (statusFilter.value === tab) return;
  statusFilter.value = tab;
  fetchReport();
}

function clearFilters() {
  operationFilter.value = "";
  workstationFilter.value = "";
  fromDate.value = "";
  toDate.value = "";
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
    for (const g of sortedWorkOrders.value) next[g.work_order] = true;
  }
  expandedWorkOrders.value = next;
}

function toggleOp(row: OperationCompletionRow) {
  const key = opRowKey(row);
  expandedOps.value[key] = !expandedOps.value[key];
}

function handleDetailLoaded(woName: string, records: ConfirmationRecord[]) {
  confirmationsCache.value[woName] = records;
}

function opNamesPreview(ops: OperationCompletionRow[]): string {
  return ops.map((o) => __(o.operation)).join(", ");
}

function handleExportCsv() {
  if (!rows.value.length) return;
  const headers = [
    __("İş Emri"), __("İş Emri Durumu"), __("Eksik Malzeme"), __("Ürün Kodu"), __("Ürün Adı"),
    __("Operasyon"), __("İş İstasyonu"), __("Planlanan"), __("Birim"),
    __("Tamamlanan"), __("Onaylı (CO11N)"), __("İlerleme %"), __("Durum"),
    __("Teyit Sayısı"), __("Oluşturma Tarihi"), __("Son Onay"), __("Teyit Eden"),
  ];
  const csvRows = rows.value.map((r) => [
    r.work_order, r.wo_status || "", r.custom_released_with_shortage ? __("Evet") : __("Hayır"),
    r.production_item, r.item_name || "", r.operation, r.workstation || "", getWoQty(r), r.stock_uom || "",
    r.completed_qty, getConfirmedQty(r), getCompletionPct(r),
    r.status === "completed" || isOpCompleted(r) ? __("Tamamlandı") : r.status === "unconfirmed" ? __("Teyit Yok") : __("Kısmi"),
    r.confirmation_count || 0, r.wo_creation || "", getLastConfirmedAt(r), r.last_confirmed_by || "",
  ]);
  exportRowsToCsv(`shopfloor-operasyon-tamamlanma-${formatCsvToday()}.csv`, headers, csvRows);
}

watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => fetchReport(), 300);
});

onMounted(() => fetchReport());
onUnmounted(() => { if (searchTimer) clearTimeout(searchTimer); });
</script>

<template>
  <div class="op-report-root">
    <!-- Top Toolbar: Status Tabs + Actions -->
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
        <button type="button" class="btn-tool" :disabled="loading" @click="fetchReport(true)">
          <span :class="{ spinning: loading }">↻</span> {{ __("Yenile") }}
        </button>
        <button type="button" class="btn-tool btn-export" :disabled="loading || rows.length === 0" @click="handleExportCsv">
          ⬇ {{ __("CSV İndir") }}
        </button>
      </div>
    </div>

    <!-- KPI Strip -->
    <div class="kpi-strip">
      <div class="kpi-box kpi-green">
        <span class="kpi-lbl">{{ __("Tamamlanan Operasyon") }}</span>
        <strong class="kpi-val">{{ summary.completed_operations }}</strong>
      </div>
      <div class="kpi-box kpi-amber">
        <span class="kpi-lbl">{{ __("Kısmi Operasyon") }}</span>
        <strong class="kpi-val">{{ summary.partial_operations }}</strong>
      </div>
      <div class="kpi-box kpi-slate">
        <span class="kpi-lbl">{{ __("Teyit Olmayan Operasyon") }}</span>
        <strong class="kpi-val">{{ summary.unconfirmed_operations ?? 0 }}</strong>
      </div>
      <div class="kpi-box kpi-blue">
        <span class="kpi-lbl">{{ __("Aktif İş Emri") }}</span>
        <strong class="kpi-val">{{ summary.unique_work_orders }}</strong>
      </div>
      <div class="kpi-box">
        <span class="kpi-lbl">{{ __("Toplam Onaylanan Miktar") }}</span>
        <strong class="kpi-val">{{ formatQty(summary.total_confirmed_qty) }}</strong>
      </div>
    </div>

    <!-- Filter Bar -->
    <OperationCompletionFilters
      v-model:search-query="searchQuery"
      v-model:operation-filter="operationFilter"
      v-model:workstation-filter="workstationFilter"
      v-model:from-date="fromDate"
      v-model:to-date="toDate"
      :operations="filterOptions.operations"
      :workstations="filterOptions.workstations"
      :has-active-filters="hasActiveFilters"
      @change="fetchReport()"
      @clear="clearFilters"
    />

    <!-- Error / Loading / Empty / Data Table -->
    <div v-if="errorMessage" class="report-state report-error">
      <span>⚠️ {{ errorMessage }}</span>
      <button type="button" class="btn-tool" @click="fetchReport()">{{ __("Tekrar Dene") }}</button>
    </div>

    <div v-else-if="loading && !reportData" class="report-state">
      <div class="report-spinner" aria-hidden="true" />
      <span>{{ __("Rapor verileri yükleniyor…") }}</span>
    </div>

    <div v-else-if="sortedWorkOrders.length === 0" class="report-state">
      <span class="empty-emoji">📭</span>
      <strong>{{ __("Kayıt Bulunamadı") }}</strong>
      <span class="empty-sub">{{ __("Seçili filtrelere uygun aktif iş emri operasyonu yok.") }}</span>
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
              <SortableTh :label="__('Operasyonlar')" sort-key="operations_count" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Planlanan')" sort-key="qty" :active-key="sortKey" :sort-dir="sortDir" align="right" @sort="handleSort" />
              <SortableTh :label="__('İlerleme %')" sort-key="overall_pct" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Oluşturma')" sort-key="wo_creation" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Son Onay')" sort-key="last_confirmation_at" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <th class="text-right">{{ __("İşlem") }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in sortedWorkOrders" :key="group.work_order">
              <tr
                class="data-row"
                :class="{ expanded: expandedWorkOrders[group.work_order] }"
                @click="toggleWorkOrder(group.work_order)"
              >
                <td class="col-exp">
                  <button type="button" class="btn-expand" :aria-expanded="Boolean(expandedWorkOrders[group.work_order])" @click.stop="toggleWorkOrder(group.work_order)">
                    {{ expandedWorkOrders[group.work_order] ? "▼" : "▶" }}
                  </button>
                </td>
                <td>
                  <div class="wo-cell">
                    <a :href="`/app/work-order/${group.work_order}`" target="_blank" class="wo-link" @click.stop>{{ group.work_order }}</a>
                    <span v-if="group.wo_status" class="wo-status-tag">{{ __(group.wo_status) }}</span>
                    <span v-if="group.custom_released_with_shortage" class="tag-mini tag-shortage" :title="__('Eksik Hammadde ile Serbest Bırakıldı')">
                      ⚠️ {{ __("Eksik Malzeme") }}
                    </span>
                  </div>
                </td>
                <td>
                  <div class="item-cell">
                    <span class="item-code">{{ group.production_item }}</span>
                    <span v-if="group.item_name && group.item_name !== group.production_item" class="item-name" :title="group.item_name">
                      {{ group.item_name }}
                    </span>
                  </div>
                </td>
                <td>
                  <div class="ops-summary-cell">
                    <div class="ops-badges-row">
                      <span class="op-count-pill">{{ __("{0} Operasyon", [group.operations.length]) }}</span>
                      <span v-if="group.completed_count > 0" class="mini-st st-completed">✓ {{ group.completed_count }}</span>
                      <span v-if="group.partial_count > 0" class="mini-st st-partial">◐ {{ group.partial_count }}</span>
                      <span v-if="group.unconfirmed_count > 0" class="mini-st st-unconfirmed">○ {{ group.unconfirmed_count }}</span>
                    </div>
                    <span class="ops-preview" :title="opNamesPreview(group.operations)">{{ opNamesPreview(group.operations) }}</span>
                  </div>
                </td>
                <td class="text-right num-cell">
                  {{ formatQty(group.qty) }} <small v-if="group.stock_uom">{{ group.stock_uom }}</small>
                </td>
                <td>
                  <div class="pct-wrap">
                    <div class="pct-track">
                      <div class="pct-fill" :class="{ complete: group.completed_count === group.operations.length }" :style="{ width: `${Math.min(100, group.overall_pct)}%` }" />
                    </div>
                    <span class="pct-text">%{{ group.overall_pct }}</span>
                  </div>
                </td>
                <td class="muted-cell num-cell">{{ formatTimestamp(group.wo_creation) }}</td>
                <td>
                  <div class="last-cell">
                    <span>{{ formatTimestamp(group.last_confirmation_at) }}</span>
                    <small v-if="group.last_confirmed_by" class="muted-sub">{{ group.last_confirmed_by.split("@")[0] }}</small>
                  </div>
                </td>
                <td class="text-right">
                  <button
                    type="button"
                    class="btn-go-wo"
                    @click.stop="emit('select-work-order', group.work_order, group.operations[0]?.operation || '')"
                  >
                    {{ __("İş Emrine Git") }} →
                  </button>
                </td>
              </tr>
              <OperationCompletionGroupRows
                v-if="expandedWorkOrders[group.work_order]"
                :work-order="group.work_order"
                :operations="group.operations"
                :expanded-ops="expandedOps"
                :confirmations-cache="confirmationsCache"
                @toggle-op="toggleOp"
                @detail-loaded="handleDetailLoaded"
              />
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.op-report-root { display: flex; flex-direction: column; gap: 1rem; color: var(--text-color, #0f172a); }
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
.kpi-strip { display: grid; grid-template-columns: repeat(5, minmax(130px, 1fr)); gap: 0.75rem; }
@media (max-width: 960px) { .kpi-strip { grid-template-columns: repeat(2, 1fr); } }
.kpi-box { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.65rem; padding: 0.75rem 1rem; display: flex; flex-direction: column; gap: 0.25rem; }
[data-theme="dark"] .kpi-box { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.kpi-lbl { font-size: 0.72rem; font-weight: 700; color: var(--text-muted, #64748b); }
.kpi-val { font-size: 1.35rem; font-weight: 800; }
.kpi-green .kpi-val { color: #16a34a; }
.kpi-amber .kpi-val { color: #d97706; }
.kpi-slate .kpi-val { color: #475569; }
[data-theme="dark"] .kpi-slate .kpi-val { color: #cbd5e1; }
.kpi-blue .kpi-val { color: #2563eb; }
[data-theme="dark"] .kpi-blue .kpi-val { color: #60a5fa; }
.report-state { padding: 3rem 1rem; text-align: center; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; color: var(--text-muted, #64748b); font-size: 0.85rem; }
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
.wo-cell, .item-cell, .last-cell, .ops-summary-cell { display: flex; flex-direction: column; gap: 0.15rem; }
.wo-link { font-weight: 800; color: #2563eb; text-decoration: none; white-space: nowrap; }
.wo-link:hover { text-decoration: underline; }
[data-theme="dark"] .wo-link { color: #60a5fa; }
.wo-status-tag { font-size: 0.68rem; color: var(--text-muted, #64748b); font-weight: 600; }
.item-code { font-weight: 700; }
.item-name, .muted-sub { font-size: 0.7rem; color: var(--text-muted, #64748b); max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ops-badges-row { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 0.3rem; }
.op-count-pill { font-size: 0.72rem; font-weight: 800; color: var(--text-color, #0f172a); background: var(--bg-color, #f1f5f9); padding: 0.1rem 0.45rem; border-radius: 9999px; }
[data-theme="dark"] .op-count-pill { background: rgba(255, 255, 255, 0.1); color: #f8fafc; }
.mini-st { font-size: 0.68rem; font-weight: 800; padding: 0.08rem 0.38rem; border-radius: 9999px; }
.st-completed { background: #dcfce7; color: #15803d; }
.st-partial { background: #fef3c7; color: #b45309; }
.st-unconfirmed { background: #f1f5f9; color: #475569; }
[data-theme="dark"] .st-completed { background: rgba(34, 197, 94, 0.18); color: #86efac; }
[data-theme="dark"] .st-partial { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
[data-theme="dark"] .st-unconfirmed { background: rgba(148, 163, 184, 0.18); color: #cbd5e1; }
.ops-preview { font-size: 0.71rem; color: var(--text-muted, #64748b); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-mini { font-size: 0.64rem; padding: 0.06rem 0.35rem; border-radius: 0.25rem; font-weight: 800; }
.tag-shortage { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; width: fit-content; }
[data-theme="dark"] .tag-shortage { background: rgba(245, 158, 11, 0.16); color: #fcd34d; border-color: rgba(251, 191, 36, 0.35); }
.num-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
.pct-wrap { display: flex; align-items: center; gap: 0.45rem; min-width: 100px; }
.pct-track { flex: 1; height: 6px; border-radius: 9999px; background: #e2e8f0; overflow: hidden; }
[data-theme="dark"] .pct-track { background: rgba(255, 255, 255, 0.12); }
.pct-fill { height: 100%; background: #2563eb; border-radius: 9999px; }
.pct-fill.complete { background: #16a34a; }
.pct-text { font-size: 0.74rem; font-weight: 800; min-width: 38px; text-align: right; }
.btn-go-wo { padding: 0.3rem 0.6rem; border-radius: 0.4rem; border: 1px solid rgba(37, 99, 235, 0.3); background: rgba(37, 99, 235, 0.08); color: #2563eb; font-size: 0.74rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
.btn-go-wo:hover { background: #2563eb; color: #ffffff; }
[data-theme="dark"] .btn-go-wo { color: #93c5fd; border-color: rgba(96, 165, 250, 0.35); }
.text-right { text-align: right; }
</style>
