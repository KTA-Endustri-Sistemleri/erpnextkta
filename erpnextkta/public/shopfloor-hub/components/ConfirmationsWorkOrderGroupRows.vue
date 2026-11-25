<script setup lang="ts">
import { computed, ref } from "vue";
import type { ManagementConfirmationRow } from "../types";
import { formatQty, getConfirmationTimestamp, getConfirmedByLabel } from "../reports/operationFormatters";
import { sortItems, toggleSortState, type SortDirection } from "../reports/tableSort";
import SortableTh from "./reports/SortableTh.vue";

type ConfSortKey =
  | "name"
  | "operation"
  | "yield_qty"
  | "creation"
  | "confirmed_by_name"
  | "docstatus";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  confirmations: ManagementConfirmationRow[];
  canCancel: boolean;
  selectedSet: Set<string>;
  colspan: number;
}>();

const emit = defineEmits<{
  (e: "toggle-select", name: string): void;
  (e: "cancel-single", row: ManagementConfirmationRow): void;
}>();

const sortKey = ref<ConfSortKey>("creation");
const sortDir = ref<SortDirection>("desc");

const SORT_ACCESSORS: Record<ConfSortKey, (row: ManagementConfirmationRow) => string | number> = {
  name: (r) => r.name,
  operation: (r) => __(r.operation || ""),
  yield_qty: (r) => Number(r.yield_qty) || 0,
  creation: (r) => getConfirmationTimestamp(r),
  confirmed_by_name: (r) => getConfirmedByLabel(r),
  docstatus: (r) => Number(r.docstatus) || 0,
};

const sortedConfirmations = computed<ManagementConfirmationRow[]>(() =>
  sortItems(props.confirmations, SORT_ACCESSORS[sortKey.value], sortDir.value, (r) => r.name)
);

function handleSort(key: string) {
  const next = toggleSortState(sortKey.value, sortDir.value, key as ConfSortKey);
  sortKey.value = next.key;
  sortDir.value = next.dir;
}
</script>

<template>
  <tr class="detail-row">
    <td :colspan="colspan" class="detail-td">
      <div class="group-conf-panel">
        <table class="inner-conf-table">
          <thead>
            <tr>
              <th v-if="canCancel" class="col-chk" />
              <SortableTh :label="__('Teyit No')" sort-key="name" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Operasyon')" sort-key="operation" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Miktar')" sort-key="yield_qty" :active-key="sortKey" :sort-dir="sortDir" align="right" @sort="handleSort" />
              <SortableTh :label="__('Tarih / Saat')" sort-key="creation" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <SortableTh :label="__('Teyit Eden')" sort-key="confirmed_by_name" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <th>{{ __("İlişkili Stok Fişleri") }}</th>
              <SortableTh :label="__('Durum')" sort-key="docstatus" :active-key="sortKey" :sort-dir="sortDir" @sort="handleSort" />
              <th v-if="canCancel" class="text-center">{{ __("İşlem") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in sortedConfirmations" :key="row.name" :class="{ cancelled: row.docstatus === 2 }">
              <td v-if="canCancel" class="col-chk">
                <input
                  v-if="row.docstatus === 1"
                  type="checkbox"
                  :checked="selectedSet.has(row.name)"
                  @click.stop
                  @change="emit('toggle-select', row.name)"
                />
              </td>
              <td>
                <div class="conf-id-wrap">
                  <a :href="`/app/kta-production-confirmation/${row.name}`" target="_blank" class="link-conf">{{ row.name }}</a>
                  <span v-if="row.is_final_confirmation" class="badge-final">{{ __("Son") }}</span>
                </div>
              </td>
              <td><span class="op-label">{{ __(row.operation) }}</span></td>
              <td class="text-right num-cell">
                <strong>{{ formatQty(row.yield_qty) }}</strong><small v-if="row.stock_uom" class="uom-sub"> {{ row.stock_uom }}</small>
              </td>
              <td class="time-cell">
                <span>{{ row.posting_date }}</span>
                <small v-if="row.posting_time" class="muted-sub">{{ (row.posting_time || "").slice(0, 5) }}</small>
              </td>
              <td class="user-cell">{{ getConfirmedByLabel(row) }}</td>
              <td>
                <div v-if="row.stock_entries && row.stock_entries.length > 0" class="se-badges">
                  <a
                    v-for="se in row.stock_entries"
                    :key="se.name"
                    :href="`/app/stock-entry/${se.name}`"
                    target="_blank"
                    class="badge-se"
                    :class="'badge-se-' + se.type"
                  >
                    {{ se.type === "manufacture" ? "📦" : "⚙️" }} {{ se.label || (se.type === "manufacture" ? __("Üretim") : __("Tüketim")) }}: {{ se.name }}
                  </a>
                </div>
                <a v-else-if="row.stock_entry" :href="`/app/stock-entry/${row.stock_entry}`" target="_blank" class="link-se">📦 {{ row.stock_entry }}</a>
                <span v-else class="muted-sub">—</span>
              </td>
              <td>
                <span class="status-tag" :class="row.docstatus === 2 ? 'tag-cancelled' : 'tag-active'">
                  {{ row.docstatus === 2 ? __("İptal Edildi") : __("Tamamlandı") }}
                </span>
              </td>
              <td v-if="canCancel" class="text-center">
                <button v-if="row.docstatus === 1" type="button" class="btn-row-cancel" @click="emit('cancel-single', row)">
                  ↩ {{ __("İptal") }}
                </button>
                <span v-else class="muted-sub">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </td>
  </tr>
</template>

<style scoped>
.detail-td { padding: 0 !important; }
.group-conf-panel {
  padding: 0.65rem 0.9rem 0.75rem 1.85rem;
  background: var(--bg-color, #f8fafc);
  border-left: 3px solid #2563eb;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}
[data-theme="dark"] .group-conf-panel {
  background: rgba(255, 255, 255, 0.03);
  border-left-color: #60a5fa;
  border-bottom-color: rgba(255, 255, 255, 0.1);
}
.inner-conf-table {
  width: 100%; border-collapse: collapse; font-size: 0.78rem;
  background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.5rem; overflow: hidden;
}
[data-theme="dark"] .inner-conf-table {
  background: var(--ck-glass-bg, #181d23); border-color: rgba(255, 255, 255, 0.1);
}
.inner-conf-table th,
.inner-conf-table :deep(.sortable-th) {
  text-align: left; padding: 0.45rem 0.65rem; background: var(--bg-color, #f1f5f9);
  color: var(--text-muted, #64748b); font-weight: 700; border-bottom: 1px solid var(--border-color, #e2e8f0); white-space: nowrap;
}
[data-theme="dark"] .inner-conf-table th,
[data-theme="dark"] .inner-conf-table :deep(.sortable-th) {
  background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.1);
}
.inner-conf-table td { padding: 0.5rem 0.65rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
[data-theme="dark"] .inner-conf-table td { border-color: rgba(255, 255, 255, 0.08); }
.inner-conf-table tbody tr:last-child td { border-bottom: none; }
.inner-conf-table tr.cancelled { background: rgba(239, 68, 68, 0.05); }
[data-theme="dark"] .inner-conf-table tr.cancelled { background: rgba(239, 68, 68, 0.12); }
.col-chk { width: 34px; text-align: center; }
.conf-id-wrap { display: flex; align-items: center; gap: 0.35rem; font-weight: 700; white-space: nowrap; }
.link-conf { color: #2563eb; text-decoration: none; }
[data-theme="dark"] .link-conf { color: #60a5fa; }
.link-conf:hover { text-decoration: underline; }
.badge-final { background: #fef3c7; color: #b45309; font-size: 0.64rem; padding: 0.08rem 0.35rem; border-radius: 0.25rem; font-weight: 800; }
[data-theme="dark"] .badge-final { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
.op-label { font-weight: 600; }
.num-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
.uom-sub { font-size: 0.7rem; color: var(--text-muted, #64748b); }
.time-cell { white-space: nowrap; display: flex; flex-direction: column; gap: 0.08rem; }
.muted-sub { font-size: 0.7rem; color: var(--text-muted, #64748b); }
.se-badges { display: flex; flex-direction: column; gap: 0.2rem; }
.badge-se { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.72rem; font-weight: 600; padding: 0.12rem 0.4rem; border-radius: 0.3rem; text-decoration: none; white-space: nowrap; width: fit-content; }
.badge-se-manufacture { background: #dcfce7; color: #15803d; }
.badge-se-consumption { background: #eff6ff; color: #1d4ed8; }
[data-theme="dark"] .badge-se-manufacture { background: rgba(34, 197, 94, 0.18); color: #86efac; }
[data-theme="dark"] .badge-se-consumption { background: rgba(59, 130, 246, 0.18); color: #93c5fd; }
.link-se { color: #059669; font-weight: 600; text-decoration: none; font-size: 0.76rem; }
[data-theme="dark"] .link-se { color: #34d399; }
.status-tag { display: inline-block; padding: 0.14rem 0.48rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 700; white-space: nowrap; }
.tag-active { background: #dcfce7; color: #15803d; }
.tag-cancelled { background: #fee2e2; color: #b91c1c; }
[data-theme="dark"] .tag-active { background: rgba(34, 197, 94, 0.18); color: #86efac; }
[data-theme="dark"] .tag-cancelled { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
.btn-row-cancel { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; padding: 0.22rem 0.55rem; border-radius: 0.35rem; font-size: 0.74rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
[data-theme="dark"] .btn-row-cancel { background: rgba(239, 68, 68, 0.18); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.text-right { text-align: right; }
.text-center { text-align: center; }
</style>
