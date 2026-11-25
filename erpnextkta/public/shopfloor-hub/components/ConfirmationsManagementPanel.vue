<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type {
  BulkCancelConfirmationsResponse,
  ConfirmationManagementStatusFilter,
  ConfirmationWorkOrderGroup,
  ConfirmationsManagementResponse,
  ManagementConfirmationRow,
} from "../types";
import { formatQty, groupConfirmationsByWorkOrder } from "../reports/operationFormatters";
import { sortItems, toggleSortState, type SortDirection } from "../reports/tableSort";
import ConfirmationsFilters from "./ConfirmationsFilters.vue";
import ConfirmationsWorkOrderGroupRows from "./ConfirmationsWorkOrderGroupRows.vue";
import BulkCancelResultModal from "./BulkCancelResultModal.vue";
import SortableTh from "./reports/SortableTh.vue";

type WoConfSortKey = "work_order" | "production_item" | "confirmation_count" | "total_yield_qty" | "last_confirmation_at";
const __ = (...args: any[]) => (window as any).__(...args);
const emit = defineEmits<{ (e: "select-work-order", workOrder: string, operation: string): void }>();

const statusFilter = ref<ConfirmationManagementStatusFilter>("active");
const searchQuery = ref<string>("");
const operationFilter = ref<string>("");
const confirmedByFilter = ref<string>("");
const fromDate = ref<string>("");
const toDate = ref<string>("");
const limit = ref<number>(200);
const loading = ref<boolean>(false);
const errorMessage = ref<string | null>(null);
const data = ref<ConfirmationsManagementResponse | null>(null);
const selectedNames = ref<string[]>([]);
const expandedWorkOrders = ref<Record<string, boolean>>({});
const sortKey = ref<WoConfSortKey>("last_confirmation_at");
const sortDir = ref<SortDirection>("desc");
const modalShow = ref<boolean>(false);
const modalMode = ref<"confirm" | "result">("confirm");
const modalTargetRows = ref<ManagementConfirmationRow[]>([]);
const modalSubmitting = ref<boolean>(false);
const modalResult = ref<BulkCancelConfirmationsResponse | null>(null);

let latestRequestId = 0;
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const rows = computed(() => data.value?.rows || []);
const totalCount = computed(() => data.value?.total_count ?? 0);
const counts = computed(() => data.value?.counts || { active: 0, cancelled: 0, all: 0 });
const summary = computed(() => data.value?.summary || { active_confirmations: 0, unique_work_orders: 0, total_yield_qty: 0 });
const filterOptions = computed(() => data.value?.filter_options || { operations: [], users: [] });
const canCancel = computed(() => Boolean(data.value?.can_cancel));
const hasActiveFilters = computed(() =>
  Boolean(searchQuery.value.trim() || operationFilter.value || confirmedByFilter.value || fromDate.value || toDate.value)
);

const activeRows = computed(() => rows.value.filter((r) => r.docstatus === 1));
const selectedSet = computed(() => new Set(selectedNames.value));
const selectedRows = computed(() => activeRows.value.filter((r) => selectedSet.value.has(r.name)));
const selectedWorkOrderCount = computed(() => new Set(selectedRows.value.map((r) => r.work_order)).size);
const allActiveSelected = computed(() => activeRows.value.length > 0 && activeRows.value.every((r) => selectedSet.value.has(r.name)));
const isIndeterminate = computed(() => selectedRows.value.length > 0 && !allActiveSelected.value);

const groupedWorkOrders = computed<ConfirmationWorkOrderGroup[]>(() => groupConfirmationsByWorkOrder(rows.value));
const WO_SORT_ACCESSORS: Record<WoConfSortKey, (g: ConfirmationWorkOrderGroup) => string | number> = {
  work_order: (g) => g.work_order,
  production_item: (g) => g.production_item,
  confirmation_count: (g) => g.confirmations.length,
  total_yield_qty: (g) => g.total_yield_qty,
  last_confirmation_at: (g) => g.last_confirmation_at,
};
const sortedWorkOrders = computed<ConfirmationWorkOrderGroup[]>(() =>
  sortItems(groupedWorkOrders.value, WO_SORT_ACCESSORS[sortKey.value], sortDir.value, (g) => g.work_order)
);
const allExpanded = computed<boolean>(
  () => sortedWorkOrders.value.length > 0 && sortedWorkOrders.value.every((g) => Boolean(expandedWorkOrders.value[g.work_order]))
);

function handleSort(key: string) {
  const next = toggleSortState(sortKey.value, sortDir.value, key as WoConfSortKey);
  sortKey.value = next.key;
  sortDir.value = next.dir;
}

function toggleWorkOrder(wo: string) {
  expandedWorkOrders.value[wo] = !expandedWorkOrders.value[wo];
}

function toggleExpandAll() {
  const next: Record<string, boolean> = {};
  if (!allExpanded.value) {
    for (const g of sortedWorkOrders.value) next[g.work_order] = true;
  }
  expandedWorkOrders.value = next;
}

function selectedCountInWo(group: ConfirmationWorkOrderGroup): number {
  return group.confirmations.reduce((acc, c) => acc + (c.docstatus === 1 && selectedSet.value.has(c.name) ? 1 : 0), 0);
}

function isWoAllSelected(group: ConfirmationWorkOrderGroup): boolean {
  return group.active_count > 0 && selectedCountInWo(group) === group.active_count;
}

function isWoIndeterminate(group: ConfirmationWorkOrderGroup): boolean {
  const cnt = selectedCountInWo(group);
  return cnt > 0 && cnt < group.active_count;
}

function toggleWorkOrderSelection(group: ConfirmationWorkOrderGroup) {
  const activeIds = group.confirmations.filter((c) => c.docstatus === 1).map((c) => c.name);
  if (activeIds.length === 0) return;
  const next = new Set(selectedNames.value);
  if (isWoAllSelected(group)) {
    for (const id of activeIds) next.delete(id);
  } else {
    for (const id of activeIds) next.add(id);
  }
  selectedNames.value = Array.from(next);
}

function callApi<T>(method: string, args: Record<string, any>, type: "GET" | "POST" = "GET"): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    frappe.call({
      method,
      type,
      args,
      quiet: true,
      callback: (r: { message?: T }) => {
        if ((window as any).frappe) (window as any).frappe.messages = [];
        resolve(r.message as T);
      },
      error: (err: any) => {
        if ((window as any).frappe) (window as any).frappe.messages = [];
        reject(err);
      },
    });
  });
}

async function fetchConfirmations() {
  const reqId = ++latestRequestId;
  loading.value = true;
  errorMessage.value = null;
  try {
    const res = await callApi<ConfirmationsManagementResponse>("erpnextkta.kta_shopfloor.api.get_confirmations_for_management", {
      status_filter: statusFilter.value,
      search: searchQuery.value.trim() || null,
      operation: operationFilter.value || null,
      confirmed_by: confirmedByFilter.value || null,
      work_order: null,
      from_date: fromDate.value || null,
      to_date: toDate.value || null,
      limit: limit.value,
    });
    if (reqId !== latestRequestId) return;
    data.value = res;
    const validActiveIds = new Set((res?.rows || []).filter((r) => r.docstatus === 1).map((r) => r.name));
    selectedNames.value = selectedNames.value.filter((id) => validActiveIds.has(id));
  } catch (err: any) {
    if (reqId !== latestRequestId) return;
    errorMessage.value = err?.message || err?._server_messages || __("Teyit listesi alınamadı.");
  } finally {
    if (reqId === latestRequestId) loading.value = false;
  }
}

function handleFilterChange() {
  limit.value = 200;
  fetchConfirmations();
}

function clearFilters() {
  searchQuery.value = "";
  operationFilter.value = "";
  confirmedByFilter.value = "";
  fromDate.value = "";
  toDate.value = "";
  limit.value = 200;
  if (searchTimer) { clearTimeout(searchTimer); searchTimer = null; }
  fetchConfirmations();
}

function toggleAllActive() {
  selectedNames.value = allActiveSelected.value ? [] : activeRows.value.map((r) => r.name);
}

function toggleRowSelection(name: string) {
  selectedNames.value = selectedSet.value.has(name) ? selectedNames.value.filter((id) => id !== name) : [...selectedNames.value, name];
}

function openCancelModal(targetRows: ManagementConfirmationRow[]) {
  if (!canCancel.value || targetRows.length === 0) return;
  modalTargetRows.value = targetRows;
  modalMode.value = "confirm";
  modalResult.value = null;
  modalShow.value = true;
}

async function handleExecuteBulkCancel() {
  if (modalSubmitting.value || modalTargetRows.value.length === 0) return;
  modalSubmitting.value = true;
  errorMessage.value = null;
  try {
    const res = await callApi<BulkCancelConfirmationsResponse>(
      "erpnextkta.kta_shopfloor.api.bulk_cancel_production_confirmations",
      { confirmation_names: modalTargetRows.value.map((r) => r.name) },
      "POST"
    );
    modalResult.value = res;
    modalMode.value = "result";
    const processed = new Set<string>([
      ...(res?.cancelled || []).map((x) => x.confirmation),
      ...(res?.cascade_cancelled || []).map((x) => x.confirmation),
    ]);
    selectedNames.value = selectedNames.value.filter((id) => !processed.has(id));
    await fetchConfirmations();
  } catch (err: any) {
    errorMessage.value = err?.message || err?._server_messages || __("Toplu iptal işlemi sırasında bir hata oluştu.");
    modalShow.value = false;
  } finally {
    modalSubmitting.value = false;
  }
}

function loadMore() {
  if (limit.value >= 500) return;
  limit.value = Math.min(500, limit.value + 200);
  fetchConfirmations();
}

watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { limit.value = 200; fetchConfirmations(); }, 250);
});

onMounted(() => fetchConfirmations());
onUnmounted(() => { if (searchTimer) clearTimeout(searchTimer); });
</script>

<template>
  <div class="conf-mgmt-root">
    <div class="kpi-strip">
      <div class="kpi-box kpi-blue"><span class="kpi-lbl">{{ __("Aktif Teyit") }}</span><strong class="kpi-val">{{ summary.active_confirmations }}</strong></div>
      <div class="kpi-box kpi-slate"><span class="kpi-lbl">{{ __("İş Emri") }}</span><strong class="kpi-val">{{ summary.unique_work_orders }}</strong></div>
      <div class="kpi-box kpi-green"><span class="kpi-lbl">{{ __("Toplam Miktar") }}</span><strong class="kpi-val">{{ formatQty(summary.total_yield_qty) }}</strong></div>
    </div>

    <div v-if="data && !canCancel" class="readonly-banner">
      <span>ℹ️</span><span>{{ __("Bu ekranda salt-okunur yetkiye sahipsiniz. İptal işlemi için Manufacturing Manager yetkisi gerekir.") }}</span>
    </div>

    <ConfirmationsFilters
      v-model:status-filter="statusFilter"
      v-model:search-query="searchQuery"
      v-model:operation-filter="operationFilter"
      v-model:confirmed-by-filter="confirmedByFilter"
      v-model:from-date="fromDate"
      v-model:to-date="toDate"
      :counts="counts"
      :operations="filterOptions.operations"
      :users="filterOptions.users"
      :has-active-filters="hasActiveFilters"
      :loading="loading"
      @change="handleFilterChange"
      @refresh="fetchConfirmations"
      @clear="clearFilters"
    />

    <div v-if="canCancel && selectedRows.length > 0" class="sticky-bulk-bar">
      <span class="bulk-count-text">{{ __("{0} Teyit Seçildi ({1} İş Emri)", [selectedRows.length, selectedWorkOrderCount]) }}</span>
      <div class="bulk-bar-actions">
        <button type="button" class="btn-bar-clear" @click="selectedNames = []">{{ __("Seçimi Temizle") }}</button>
        <button type="button" class="btn-bar-cancel" @click="openCancelModal(selectedRows)">↩ {{ __("Seçilenleri İptal Et") }}</button>
      </div>
    </div>

    <div v-if="errorMessage" class="panel-state panel-error">
      <span>⚠️ {{ errorMessage }}</span>
      <button type="button" class="btn-retry" @click="fetchConfirmations">{{ __("Tekrar Dene") }}</button>
    </div>
    <div v-else-if="loading && !data" class="panel-state">
      <div class="panel-spinner" aria-hidden="true" /><span>{{ __("Teyit Kayıtları Yükleniyor…") }}</span>
    </div>
    <div v-else-if="sortedWorkOrders.length === 0" class="panel-state">
      <span class="empty-emoji">📭</span><strong>{{ __("Kayıt Bulunamadı") }}</strong>
      <span class="empty-sub">{{ __("Seçili filtrelere uygun üretim teyidi bulunmuyor.") }}</span>
    </div>
    <div v-else class="table-card">
      <div class="table-toolbar">
        <span class="toolbar-summary">{{ __("{0} İş Emri · {1} Teyit", [sortedWorkOrders.length, rows.length]) }}</span>
        <button type="button" class="btn-expand-all" @click="toggleExpandAll">
          {{ allExpanded ? "▼" : "▶" }} {{ allExpanded ? __("Tümünü Daralt") : __("Tümünü Genişlet") }}
        </button>
      </div>
      <div class="table-scroll">
        <table class="mgmt-table">
          <thead>
            <tr>
              <th v-if="canCancel" class="col-chk">
                <input type="checkbox" :checked="allActiveSelected" :indeterminate="isIndeterminate" :disabled="activeRows.length === 0" :title="__('Tüm Aktif Teyitleri Seç')" @change="toggleAllActive" />
              </th>
              <th class="col-exp">
                <button type="button" class="btn-expand" :title="allExpanded ? __('Tümünü Daralt') : __('Tümünü Genişlet')" @click="toggleExpandAll">{{ allExpanded ? "▼" : "▶" }}</button>
              </th>
              <SortableTh :label="__('İş Emri')" sort-key="work_order" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Ürün')" sort-key="production_item" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Teyit Sayısı')" sort-key="confirmation_count" :active-key="sortKey" :sort-dir="sortDir" align="right" @sort="handleSort" />
              <SortableTh :label="__('Toplam Miktar')" sort-key="total_yield_qty" :active-key="sortKey" :sort-dir="sortDir" align="right" @sort="handleSort" />
              <SortableTh :label="__('Son Teyit')" sort-key="last_confirmation_at" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <th v-if="canCancel" class="text-center">{{ __("İşlem") }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in sortedWorkOrders" :key="group.work_order">
              <tr class="data-row" :class="{ expanded: expandedWorkOrders[group.work_order] }" @click="toggleWorkOrder(group.work_order)">
                <td v-if="canCancel" class="col-chk" @click.stop>
                  <input type="checkbox" :checked="isWoAllSelected(group)" :indeterminate="isWoIndeterminate(group)" :disabled="group.active_count === 0" :title="__('Bu İş Emrinin Aktif Teyitlerini Seç')" @click.stop @change="toggleWorkOrderSelection(group)" />
                </td>
                <td class="col-exp">
                  <button type="button" class="btn-expand" :aria-expanded="Boolean(expandedWorkOrders[group.work_order])" @click.stop="toggleWorkOrder(group.work_order)">
                    {{ expandedWorkOrders[group.work_order] ? "▼" : "▶" }}
                  </button>
                </td>
                <td>
                  <div class="wo-cell">
                    <button type="button" class="btn-wo-link" @click.stop="emit('select-work-order', group.work_order, group.confirmations[0]?.operation || '')">{{ group.work_order }}</button>
                    <span v-if="group.wo_status" class="wo-status-tag">{{ __(group.wo_status) }}</span>
                  </div>
                </td>
                <td>
                  <div class="item-cell">
                    <span class="item-code">{{ group.production_item }}</span>
                    <span v-if="group.item_name && group.item_name !== group.production_item" class="item-sub" :title="group.item_name">{{ group.item_name }}</span>
                  </div>
                </td>
                <td class="text-right">
                  <div class="count-badges">
                    <span class="count-pill">{{ group.cancelled_count > 0 ? `${group.active_count} / ${group.confirmations.length}` : __("{0} Teyit", [group.confirmations.length]) }}</span>
                    <span v-if="group.cancelled_count > 0" class="mini-st st-cancelled">{{ __("{0} İptal", [group.cancelled_count]) }}</span>
                    <span v-if="selectedCountInWo(group) > 0" class="mini-st st-selected">{{ __("{0} Seçili", [selectedCountInWo(group)]) }}</span>
                  </div>
                </td>
                <td class="text-right num-cell">
                  <strong>{{ formatQty(group.total_yield_qty) }}</strong><small v-if="group.stock_uom" class="uom-sub"> {{ group.stock_uom }}</small>
                </td>
                <td class="time-cell">
                  <div class="last-cell">
                    <span>{{ group.last_posting_date || "—" }} <small v-if="group.last_posting_time" class="time-part">{{ group.last_posting_time.slice(0, 5) }}</small></span>
                    <small v-if="group.last_confirmed_by" class="muted-sub">{{ group.last_confirmed_by }}</small>
                  </div>
                </td>
                <td v-if="canCancel" class="text-center">
                  <button v-if="group.active_count > 0" type="button" class="btn-row-cancel" @click.stop="openCancelModal(group.confirmations.filter((c) => c.docstatus === 1))">
                    ↩ {{ __("Tümünü İptal Et") }}
                  </button>
                  <span v-else class="muted-sub">—</span>
                </td>
              </tr>
              <ConfirmationsWorkOrderGroupRows
                v-if="expandedWorkOrders[group.work_order]"
                :confirmations="group.confirmations" :can-cancel="canCancel" :selected-set="selectedSet" :colspan="canCancel ? 8 : 6"
                @toggle-select="toggleRowSelection" @cancel-single="(row) => openCancelModal([row])"
              />
            </template>
          </tbody>
        </table>
      </div>
      <div v-if="totalCount > rows.length" class="table-footer">
        <span class="footer-info">{{ __("Toplam {0} kayıttan {1} tanesi gösteriliyor.", [totalCount, rows.length]) }}</span>
        <button v-if="limit < 500" type="button" class="btn-load-more" :disabled="loading" @click="loadMore">{{ __("Daha Fazla Göster") }}</button>
      </div>
    </div>

    <BulkCancelResultModal :show="modalShow" :mode="modalMode" :selected-rows="modalTargetRows" :submitting="modalSubmitting" :result="modalResult" @close="modalShow = false" @confirm="handleExecuteBulkCancel" />
  </div>
</template>

<style scoped>
.conf-mgmt-root { display: flex; flex-direction: column; gap: 1rem; color: var(--text-color, #0f172a); }
.kpi-strip { display: grid; grid-template-columns: repeat(3, minmax(140px, 1fr)); gap: 0.75rem; }
@media (max-width: 720px) { .kpi-strip { grid-template-columns: 1fr; } }
.kpi-box { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.65rem; padding: 0.75rem 1rem; display: flex; flex-direction: column; gap: 0.2rem; }
[data-theme="dark"] .kpi-box { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.kpi-lbl { font-size: 0.72rem; font-weight: 700; color: var(--text-muted, #64748b); }
.kpi-val { font-size: 1.35rem; font-weight: 800; }
.kpi-blue .kpi-val { color: #2563eb; }
[data-theme="dark"] .kpi-blue .kpi-val { color: #60a5fa; }
.kpi-green .kpi-val { color: #16a34a; }
[data-theme="dark"] .kpi-green .kpi-val { color: #4ade80; }
.readonly-banner { display: flex; align-items: center; gap: 0.55rem; padding: 0.65rem 0.9rem; border-radius: 0.55rem; font-size: 0.8rem; font-weight: 600; background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
[data-theme="dark"] .readonly-banner { background: rgba(59, 130, 246, 0.14); border-color: rgba(96, 165, 250, 0.3); color: #93c5fd; }
.sticky-bulk-bar { position: sticky; top: 0; z-index: 15; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.65rem; padding: 0.65rem 1rem; border-radius: 0.6rem; background: #1e293b; color: #f8fafc; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.22); }
[data-theme="dark"] .sticky-bulk-bar { background: #0f172a; border: 1px solid rgba(96, 165, 250, 0.35); }
.bulk-count-text { font-size: 0.84rem; font-weight: 800; }
.bulk-bar-actions { display: flex; gap: 0.5rem; }
.btn-bar-clear { padding: 0.38rem 0.75rem; border-radius: 0.4rem; border: 1px solid rgba(255, 255, 255, 0.25); background: transparent; color: #e2e8f0; font-size: 0.78rem; font-weight: 700; cursor: pointer; }
.btn-bar-cancel { padding: 0.38rem 0.85rem; border-radius: 0.4rem; border: none; background: #dc2626; color: #ffffff; font-size: 0.78rem; font-weight: 800; cursor: pointer; }
.btn-bar-cancel:hover { background: #b91c1c; }
.panel-state { padding: 3rem 1rem; text-align: center; background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; display: flex; flex-direction: column; align-items: center; gap: 0.45rem; color: var(--text-muted, #64748b); font-size: 0.85rem; }
[data-theme="dark"] .panel-state { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.panel-error { color: #b91c1c; }
[data-theme="dark"] .panel-error { color: #fca5a5; }
.btn-retry { padding: 0.35rem 0.75rem; border-radius: 0.4rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); font-weight: 700; cursor: pointer; }
.panel-spinner { width: 26px; height: 26px; border: 3px solid rgba(37, 99, 235, 0.2); border-top-color: #2563eb; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.table-card { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.75rem; overflow: hidden; }
[data-theme="dark"] .table-card { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1)); }
.table-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; padding: 0.55rem 0.9rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .table-toolbar { background: rgba(255, 255, 255, 0.03); border-color: rgba(255, 255, 255, 0.1); }
.toolbar-summary { font-size: 0.76rem; font-weight: 700; color: var(--text-muted, #64748b); }
.btn-expand-all { padding: 0.28rem 0.65rem; border-radius: 0.4rem; border: 1px solid var(--border-color, #cbd5e1); background: var(--card-bg, #ffffff); color: var(--text-color, #334155); font-size: 0.74rem; font-weight: 700; cursor: pointer; }
[data-theme="dark"] .btn-expand-all { background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.14); color: #e2e8f0; }
.table-scroll { overflow-x: auto; }
.mgmt-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.mgmt-table th { text-align: left; padding: 0.65rem 0.7rem; background: var(--bg-color, #f8fafc); color: var(--text-muted, #64748b); font-weight: 700; border-bottom: 1px solid var(--border-color, #e2e8f0); white-space: nowrap; }
[data-theme="dark"] .mgmt-table th { background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.1); }
.data-row { cursor: pointer; transition: background-color 0.12s; }
.data-row:hover { background: rgba(37, 99, 235, 0.04); }
.data-row.expanded { background: rgba(37, 99, 235, 0.06); }
[data-theme="dark"] .data-row.expanded { background: rgba(96, 165, 250, 0.08); }
.data-row td { padding: 0.6rem 0.7rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
[data-theme="dark"] .data-row td { border-color: rgba(255, 255, 255, 0.08); }
.col-chk { width: 34px; text-align: center; }
.col-exp { width: 32px; text-align: center; }
.btn-expand { background: transparent; border: none; color: var(--text-muted, #64748b); cursor: pointer; font-size: 0.72rem; }
.wo-cell, .item-cell, .last-cell { display: flex; flex-direction: column; gap: 0.15rem; }
.btn-wo-link { background: transparent; border: none; padding: 0; font-weight: 800; color: #2563eb; cursor: pointer; font-size: 0.8rem; text-align: left; width: fit-content; }
[data-theme="dark"] .btn-wo-link { color: #60a5fa; }
.btn-wo-link:hover { text-decoration: underline; }
.wo-status-tag { font-size: 0.68rem; color: var(--text-muted, #64748b); font-weight: 600; }
.item-code { font-weight: 700; }
.item-sub, .muted-sub { font-size: 0.71rem; color: var(--text-muted, #64748b); display: block; max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.count-badges { display: inline-flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 0.3rem; }
.count-pill { font-size: 0.72rem; font-weight: 800; color: var(--text-color, #0f172a); background: var(--bg-color, #f1f5f9); padding: 0.1rem 0.45rem; border-radius: 9999px; white-space: nowrap; }
[data-theme="dark"] .count-pill { background: rgba(255, 255, 255, 0.1); color: #f8fafc; }
.mini-st { font-size: 0.68rem; font-weight: 800; padding: 0.08rem 0.38rem; border-radius: 9999px; white-space: nowrap; }
.st-cancelled { background: #fee2e2; color: #b91c1c; }
[data-theme="dark"] .st-cancelled { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
.st-selected { background: #dbeafe; color: #1d4ed8; }
[data-theme="dark"] .st-selected { background: rgba(59, 130, 246, 0.24); color: #93c5fd; }
.num-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
.uom-sub, .time-part { font-size: 0.7rem; color: var(--text-muted, #64748b); }
.time-cell { white-space: nowrap; }
.btn-row-cancel { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; padding: 0.22rem 0.55rem; border-radius: 0.35rem; font-size: 0.74rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
[data-theme="dark"] .btn-row-cancel { background: rgba(239, 68, 68, 0.18); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.table-footer { display: flex; justify-content: space-between; align-items: center; padding: 0.7rem 1rem; border-top: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .table-footer { background: rgba(255, 255, 255, 0.03); border-color: rgba(255, 255, 255, 0.1); }
.footer-info { font-size: 0.76rem; color: var(--text-muted, #64748b); font-weight: 600; }
.btn-load-more { padding: 0.35rem 0.85rem; border-radius: 0.42rem; border: 1px solid #2563eb; background: #eff6ff; color: #1d4ed8; font-size: 0.76rem; font-weight: 700; cursor: pointer; }
[data-theme="dark"] .btn-load-more { background: rgba(59, 130, 246, 0.16); border-color: rgba(96, 165, 250, 0.4); color: #93c5fd; }
.text-right { text-align: right; }
.text-center { text-align: center; }
</style>
