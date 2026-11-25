<script setup lang="ts">
import type { ConfirmationRecord, OperationCompletionRow } from "../../types";
import {
  formatQty,
  formatTimestamp,
  getCompletionPct,
  getConfirmedQty,
  getLastConfirmedAt,
  hasFinalConfirmation,
  isOpCompleted,
  opRowKey,
} from "../../reports/operationFormatters";
import OperationCompletionDetail from "./OperationCompletionDetail.vue";

const __ = (...args: any[]) => (window as any).__(...args);

defineProps<{
  workOrder: string;
  operations: OperationCompletionRow[];
  expandedOps: Record<string, boolean>;
  confirmationsCache: Record<string, ConfirmationRecord[]>;
}>();

const emit = defineEmits<{
  (e: "toggle-op", row: OperationCompletionRow): void;
  (e: "detail-loaded", workOrder: string, records: ConfirmationRecord[]): void;
}>();

function opStatusMeta(op: OperationCompletionRow): { cls: string; label: string } {
  if (op.status === "completed" || isOpCompleted(op)) {
    return { cls: "st-completed", label: __("Tamamlandı") };
  }
  if (op.status === "unconfirmed") {
    return { cls: "st-unconfirmed", label: __("Teyit Yok") };
  }
  return { cls: "st-partial", label: __("Kısmi") };
}
</script>

<template>
  <tr class="detail-row">
    <td colspan="9" class="detail-td">
      <div class="group-ops-panel">
        <table class="inner-ops-table">
          <thead>
            <tr>
              <th class="col-exp" />
              <th>{{ __("Operasyon") }}</th>
              <th>{{ __("İş İstasyonu") }}</th>
              <th class="text-right">{{ __("Tamamlanan") }}</th>
              <th class="text-right">{{ __("Onaylı (CO11N)") }}</th>
              <th>{{ __("İlerleme %") }}</th>
              <th>{{ __("Son Onay") }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="op in operations" :key="opRowKey(op)">
              <tr
                class="inner-op-row"
                :class="{ expanded: expandedOps[opRowKey(op)] }"
                @click="emit('toggle-op', op)"
              >
                <td class="col-exp">
                  <button
                    type="button"
                    class="btn-expand"
                    :aria-expanded="Boolean(expandedOps[opRowKey(op)])"
                    @click.stop="emit('toggle-op', op)"
                  >
                    {{ expandedOps[opRowKey(op)] ? "▼" : "▶" }}
                  </button>
                </td>
                <td>
                  <div class="op-cell">
                    <span class="op-name">{{ __(op.operation) }}</span>
                    <span class="st-badge" :class="opStatusMeta(op).cls">
                      {{ opStatusMeta(op).label }}
                    </span>
                    <span v-if="hasFinalConfirmation(op)" class="tag-mini tag-final">{{ __("Son") }}</span>
                    <span v-else-if="op.source_type === 'legacy'" class="tag-mini tag-legacy">{{ __("Eski Usul") }}</span>
                  </div>
                </td>
                <td class="muted-cell">{{ op.workstation || "—" }}</td>
                <td class="text-right num-cell strong-num">{{ formatQty(op.completed_qty) }}</td>
                <td class="text-right num-cell">
                  {{ formatQty(getConfirmedQty(op)) }}
                  <span v-if="op.confirmation_count > 0" class="conf-count-pill">{{ op.confirmation_count }}</span>
                </td>
                <td>
                  <div class="pct-wrap">
                    <div class="pct-track">
                      <div
                        class="pct-fill"
                        :class="{ complete: op.status === 'completed' || isOpCompleted(op) }"
                        :style="{ width: `${Math.min(100, getCompletionPct(op))}%` }"
                      />
                    </div>
                    <span class="pct-text">%{{ getCompletionPct(op) }}</span>
                  </div>
                </td>
                <td>
                  <div class="last-cell">
                    <span>{{ formatTimestamp(getLastConfirmedAt(op)) }}</span>
                    <small v-if="op.last_confirmed_by" class="muted-sub">{{ op.last_confirmed_by.split("@")[0] }}</small>
                  </div>
                </td>
              </tr>
              <tr v-if="expandedOps[opRowKey(op)]" class="op-detail-subrow">
                <td colspan="7" class="detail-td">
                  <OperationCompletionDetail
                    :work-order="op.work_order"
                    :operation="op.operation"
                    :source-type="op.source_type"
                    :cached-records="confirmationsCache[workOrder] || null"
                    @loaded="(wo, recs) => emit('detail-loaded', wo, recs)"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </td>
  </tr>
</template>

<style scoped>
.detail-td { padding: 0 !important; }
.group-ops-panel {
  padding: 0.65rem 0.9rem 0.75rem 1.85rem;
  background: var(--bg-color, #f8fafc);
  border-left: 3px solid #2563eb;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}
[data-theme="dark"] .group-ops-panel {
  background: rgba(255, 255, 255, 0.03);
  border-left-color: #60a5fa;
  border-bottom-color: rgba(255, 255, 255, 0.1);
}
.inner-ops-table {
  width: 100%; border-collapse: collapse; font-size: 0.78rem;
  background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.5rem; overflow: hidden;
}
[data-theme="dark"] .inner-ops-table {
  background: var(--ck-glass-bg, #181d23); border-color: rgba(255, 255, 255, 0.1);
}
.inner-ops-table th {
  text-align: left; padding: 0.45rem 0.65rem; background: var(--bg-color, #f1f5f9);
  color: var(--text-muted, #64748b); font-weight: 700; border-bottom: 1px solid var(--border-color, #e2e8f0); white-space: nowrap;
}
[data-theme="dark"] .inner-ops-table th { background: rgba(255, 255, 255, 0.04); }
.inner-op-row { cursor: pointer; transition: background-color 0.12s; }
.inner-op-row:hover { background: rgba(37, 99, 235, 0.05); }
.inner-op-row td { padding: 0.5rem 0.65rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle; }
.col-exp { width: 28px; text-align: center; }
.btn-expand { background: transparent; border: none; color: var(--text-muted, #64748b); cursor: pointer; font-size: 0.7rem; }
.op-cell { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }
.op-name { font-weight: 700; color: var(--text-color, #0f172a); }
.st-badge { font-size: 0.65rem; padding: 0.08rem 0.42rem; border-radius: 9999px; font-weight: 800; white-space: nowrap; }
.st-completed { background: #dcfce7; color: #15803d; }
.st-partial { background: #fef3c7; color: #b45309; }
.st-unconfirmed { background: #f1f5f9; color: #475569; }
[data-theme="dark"] .st-completed { background: rgba(34, 197, 94, 0.18); color: #86efac; }
[data-theme="dark"] .st-partial { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
[data-theme="dark"] .st-unconfirmed { background: rgba(148, 163, 184, 0.18); color: #cbd5e1; }
.tag-mini { font-size: 0.64rem; padding: 0.06rem 0.35rem; border-radius: 0.25rem; font-weight: 800; }
.tag-final { background: #fef3c7; color: #b45309; }
.tag-legacy { background: #e2e8f0; color: #475569; }
[data-theme="dark"] .tag-final { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
[data-theme="dark"] .tag-legacy { background: rgba(148, 163, 184, 0.18); color: #cbd5e1; }
.muted-cell { color: var(--text-muted, #64748b); }
.num-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
.strong-num { font-weight: 800; }
.conf-count-pill {
  margin-left: 0.25rem; padding: 0.05rem 0.35rem; border-radius: 9999px;
  font-size: 0.68rem; font-weight: 700; background: #eff6ff; color: #1d4ed8;
}
[data-theme="dark"] .conf-count-pill { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
.pct-wrap { display: flex; align-items: center; gap: 0.45rem; min-width: 96px; }
.pct-track { flex: 1; height: 6px; border-radius: 9999px; background: #e2e8f0; overflow: hidden; }
[data-theme="dark"] .pct-track { background: rgba(255, 255, 255, 0.12); }
.pct-fill { height: 100%; background: #2563eb; border-radius: 9999px; }
.pct-fill.complete { background: #16a34a; }
.pct-text { font-size: 0.74rem; font-weight: 800; min-width: 38px; text-align: right; }
.last-cell { display: flex; flex-direction: column; gap: 0.1rem; }
.muted-sub { font-size: 0.7rem; color: var(--text-muted, #64748b); }
.text-right { text-align: right; }
</style>
