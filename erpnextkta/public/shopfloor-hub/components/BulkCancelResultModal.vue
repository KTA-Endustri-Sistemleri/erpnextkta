<script setup lang="ts">
import { computed } from "vue";
import type { BulkCancelConfirmationsResponse, ManagementConfirmationRow } from "../types";
import { formatQty } from "../reports/operationFormatters";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  show: boolean;
  mode: "confirm" | "result";
  selectedRows: ManagementConfirmationRow[];
  submitting: boolean;
  result: BulkCancelConfirmationsResponse | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm"): void;
}>();

const uniqueWorkOrderCount = computed(() => new Set(props.selectedRows.map((r) => r.work_order)).size);
const totalYieldQty = computed(() => props.selectedRows.reduce((sum, r) => sum + (Number(r.yield_qty) || 0), 0));
const previewRows = computed(() => props.selectedRows.slice(0, 10));
const remainingCount = computed(() => Math.max(0, props.selectedRows.length - 10));

interface ResultEntry {
  key: string;
  confirmation: string;
  workOrder: string | null;
  operation: string | null;
  kind: "cancelled" | "cascade" | "failed";
  note: string;
}

const resultEntries = computed<ResultEntry[]>(() => {
  if (!props.result) return [];
  const cancelled = (props.result.cancelled || []).map((c) => ({
    key: `c-${c.confirmation}`,
    confirmation: c.confirmation,
    workOrder: c.work_order,
    operation: c.operation,
    kind: "cancelled" as const,
    note: c.cancelled_stock_entries?.length
      ? __("İptal Edilen Stok Fişleri: {0}", [c.cancelled_stock_entries.join(", ")])
      : "",
  }));
  const cascade = (props.result.cascade_cancelled || []).map((cc) => ({
    key: `cc-${cc.confirmation}`,
    confirmation: cc.confirmation,
    workOrder: cc.work_order,
    operation: cc.operation,
    kind: "cascade" as const,
    note: cc.cancelled_by ? __("Tetikleyen Teyit: {0}", [cc.cancelled_by]) : "",
  }));
  const failed = (props.result.failed || []).map((f) => ({
    key: `f-${f.confirmation}`,
    confirmation: f.confirmation,
    workOrder: f.work_order,
    operation: f.operation,
    kind: "failed" as const,
    note: f.error || __("Bilinmeyen Hata"),
  }));
  return [...cancelled, ...cascade, ...failed];
});

function handleOverlayClick() {
  if (!props.submitting) emit("close");
}
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="bulk-modal-overlay" @click.self="handleOverlayClick">
      <div class="bulk-modal" role="dialog" aria-modal="true">
        <div class="bulk-modal-header">
          <div class="header-title-wrap">
            <span class="header-icon" aria-hidden="true">{{ mode === "confirm" ? "⚠️" : "📋" }}</span>
            <div>
              <h3 class="modal-title">
                {{ mode === "confirm" ? __("Toplu Teyit İptali Onayı") : __("Toplu Teyit İptal Sonucu") }}
              </h3>
              <p class="modal-subtitle">
                {{
                  mode === "confirm"
                    ? __("Seçili teyitler için ters kayıt (storno) işlemi başlatılacak.")
                    : __("İşlem tamamlandı. Detaylar aşağıda listelenmiştir.")
                }}
              </p>
            </div>
          </div>
          <button type="button" class="close-btn" :disabled="submitting" @click="emit('close')">×</button>
        </div>

        <div v-if="mode === 'confirm'" class="bulk-modal-body">
          <div class="summary-chips">
            <div class="chip-box">
              <span class="chip-lbl">{{ __("Seçili Teyit") }}</span>
              <strong class="chip-val">{{ selectedRows.length }}</strong>
            </div>
            <div class="chip-box">
              <span class="chip-lbl">{{ __("İş Emri") }}</span>
              <strong class="chip-val">{{ uniqueWorkOrderCount }}</strong>
            </div>
            <div class="chip-box">
              <span class="chip-lbl">{{ __("Toplam Miktar") }}</span>
              <strong class="chip-val">{{ formatQty(totalYieldQty) }}</strong>
            </div>
          </div>

          <div class="warning-banner">
            <span>🛑</span>
            <span>{{ __("Seçilen üretim teyitleri ve ilişkili stok hareketleri ters kayıt (storno) ile kalıcı olarak iptal edilecektir. Bu işlem geri alınamaz.") }}</span>
          </div>

          <div class="preview-list">
            <div v-for="row in previewRows" :key="row.name" class="preview-row">
              <span class="pv-id">{{ row.name }}</span>
              <span class="pv-wo">{{ row.work_order }}</span>
              <span class="pv-op">{{ __(row.operation) }}</span>
              <strong class="pv-qty">{{ formatQty(row.yield_qty) }} {{ row.stock_uom || "" }}</strong>
            </div>
            <div v-if="remainingCount > 0" class="preview-more">{{ __("+{0} Kayıt Daha", [remainingCount]) }}</div>
          </div>
        </div>

        <div v-else class="bulk-modal-body">
          <div class="result-kpis">
            <div class="kpi-pill kpi-ok">
              <span>{{ __("İptal Edildi") }}</span>
              <strong>{{ result?.cancelled_count ?? 0 }}</strong>
            </div>
            <div class="kpi-pill kpi-cascade">
              <span>{{ __("Zincirleme İptal") }}</span>
              <strong>{{ result?.cascade_cancelled_count ?? 0 }}</strong>
            </div>
            <div class="kpi-pill kpi-err">
              <span>{{ __("Hatalı") }}</span>
              <strong>{{ result?.failed_count ?? 0 }}</strong>
            </div>
          </div>

          <div class="result-list">
            <div v-for="item in resultEntries" :key="item.key" class="result-row" :class="'row-' + item.kind">
              <div class="result-row-top">
                <div class="result-row-ids">
                  <strong class="res-id">{{ item.confirmation }}</strong>
                  <span v-if="item.workOrder" class="res-meta">{{ item.workOrder }}</span>
                  <span v-if="item.operation" class="res-meta">• {{ __(item.operation) }}</span>
                </div>
                <span class="res-badge" :class="'badge-' + item.kind">
                  {{ item.kind === "cancelled" ? __("İptal Edildi") : item.kind === "cascade" ? __("Zincirleme İptal") : __("Hatalı") }}
                </span>
              </div>
              <div v-if="item.note" class="res-note">{{ item.note }}</div>
            </div>
          </div>
        </div>

        <div class="bulk-modal-footer">
          <template v-if="mode === 'confirm'">
            <button type="button" class="m-btn m-btn-sec" :disabled="submitting" @click="emit('close')">{{ __("Vazgeç") }}</button>
            <button type="button" class="m-btn m-btn-danger" :disabled="submitting || selectedRows.length === 0" @click="emit('confirm')">
              <span v-if="submitting" class="m-spinner" aria-hidden="true" />
              <span>{{ submitting ? __("İptal Ediliyor…") : __("Evet, Toplu İptal Et") }}</span>
            </button>
          </template>
          <button v-else type="button" class="m-btn m-btn-primary" @click="emit('close')">{{ __("Kapat") }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.bulk-modal-overlay { position: fixed; inset: 0; z-index: 1065; background: rgba(15, 23, 42, 0.58); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: 1.25rem; }
.bulk-modal { width: 100%; max-width: 680px; max-height: 88vh; background: var(--card-bg, #ffffff); color: var(--text-color, #0f172a); border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.85rem; box-shadow: 0 22px 48px rgba(15, 23, 42, 0.25); display: flex; flex-direction: column; overflow: hidden; }
[data-theme="dark"] .bulk-modal { background: var(--ck-glass-bg, #1c2127); border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.14)); color: #f8fafc; }
.bulk-modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; border-bottom: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .bulk-modal-header { background: rgba(255, 255, 255, 0.03); border-color: rgba(255, 255, 255, 0.1); }
.header-title-wrap { display: flex; align-items: center; gap: 0.65rem; }
.header-icon { font-size: 1.35rem; }
.modal-title { margin: 0; font-size: 1rem; font-weight: 800; }
.modal-subtitle { margin: 0.12rem 0 0; font-size: 0.76rem; color: var(--text-muted, #64748b); }
.close-btn { background: transparent; border: none; font-size: 1.35rem; color: var(--text-muted, #64748b); cursor: pointer; width: 30px; height: 30px; border-radius: 0.4rem; }
.close-btn:hover:not(:disabled) { background: rgba(148, 163, 184, 0.18); }
.bulk-modal-body { padding: 1.1rem 1.25rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.9rem; }
.summary-chips, .result-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.6rem; }
.chip-box, .kpi-pill { padding: 0.65rem 0.8rem; border-radius: 0.55rem; border: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); display: flex; flex-direction: column; gap: 0.15rem; }
[data-theme="dark"] .chip-box { background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.1); }
.chip-lbl, .kpi-pill span { font-size: 0.7rem; font-weight: 700; color: var(--text-muted, #64748b); }
.chip-val, .kpi-pill strong { font-size: 1.15rem; font-weight: 800; }
.kpi-ok { background: #f0fdf4; border-color: #bbf7d0; color: #15803d; }
.kpi-cascade { background: #fffbeb; border-color: #fde68a; color: #b45309; }
.kpi-err { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }
[data-theme="dark"] .kpi-ok { background: rgba(34, 197, 94, 0.15); border-color: rgba(74, 222, 128, 0.35); color: #86efac; }
[data-theme="dark"] .kpi-cascade { background: rgba(245, 158, 11, 0.15); border-color: rgba(251, 191, 36, 0.35); color: #fcd34d; }
[data-theme="dark"] .kpi-err { background: rgba(239, 68, 68, 0.15); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.warning-banner { display: flex; gap: 0.6rem; padding: 0.75rem 0.9rem; border-radius: 0.55rem; font-size: 0.8rem; font-weight: 600; background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; line-height: 1.4; }
[data-theme="dark"] .warning-banner { background: rgba(239, 68, 68, 0.16); border-color: rgba(248, 113, 113, 0.35); color: #fca5a5; }
.preview-list, .result-list { border: 1px solid var(--border-color, #e2e8f0); border-radius: 0.55rem; max-height: 260px; overflow-y: auto; }
[data-theme="dark"] .preview-list, [data-theme="dark"] .result-list { border-color: rgba(255, 255, 255, 0.12); }
.preview-row { display: grid; grid-template-columns: 1.2fr 1.1fr 1fr auto; gap: 0.5rem; align-items: center; padding: 0.5rem 0.75rem; font-size: 0.78rem; border-bottom: 1px solid var(--border-color, #e2e8f0); }
[data-theme="dark"] .preview-row { border-color: rgba(255, 255, 255, 0.08); }
.preview-row:last-child { border-bottom: none; }
.pv-id { font-weight: 700; color: #2563eb; }
[data-theme="dark"] .pv-id { color: #60a5fa; }
.pv-wo, .pv-op { color: var(--text-muted, #64748b); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-more { padding: 0.5rem 0.75rem; font-size: 0.76rem; font-weight: 700; text-align: center; color: var(--text-muted, #64748b); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .preview-more { background: rgba(255, 255, 255, 0.04); }
.result-row { padding: 0.6rem 0.8rem; border-bottom: 1px solid var(--border-color, #e2e8f0); display: flex; flex-direction: column; gap: 0.25rem; }
[data-theme="dark"] .result-row { border-color: rgba(255, 255, 255, 0.08); }
.result-row:last-child { border-bottom: none; }
.result-row-top { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.result-row-ids { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; font-size: 0.8rem; }
.res-meta { font-size: 0.74rem; color: var(--text-muted, #64748b); }
.res-badge { padding: 0.12rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 700; white-space: nowrap; }
.badge-cancelled { background: #dcfce7; color: #15803d; }
.badge-cascade { background: #fef3c7; color: #b45309; }
.badge-failed { background: #fee2e2; color: #b91c1c; }
[data-theme="dark"] .badge-cancelled { background: rgba(34, 197, 94, 0.18); color: #86efac; }
[data-theme="dark"] .badge-cascade { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
[data-theme="dark"] .badge-failed { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
.res-note { font-size: 0.74rem; color: var(--text-muted, #64748b); word-break: break-word; }
.row-failed .res-note { color: #b91c1c; font-weight: 600; }
[data-theme="dark"] .row-failed .res-note { color: #fca5a5; }
.bulk-modal-footer { display: flex; justify-content: flex-end; gap: 0.65rem; padding: 0.9rem 1.25rem; border-top: 1px solid var(--border-color, #e2e8f0); background: var(--bg-color, #f8fafc); }
[data-theme="dark"] .bulk-modal-footer { background: rgba(255, 255, 255, 0.02); border-color: rgba(255, 255, 255, 0.1); }
.m-btn { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.5rem 1rem; border-radius: 0.48rem; font-size: 0.82rem; font-weight: 700; cursor: pointer; border: none; }
.m-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.m-btn-sec { background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #cbd5e1); color: var(--text-muted, #64748b); }
[data-theme="dark"] .m-btn-sec { background: #14181d; border-color: rgba(255, 255, 255, 0.18); }
.m-btn-danger { background: #dc2626; color: #ffffff; }
.m-btn-danger:hover:not(:disabled) { background: #b91c1c; }
.m-btn-primary { background: #2563eb; color: #ffffff; }
.m-spinner { width: 13px; height: 13px; border: 2px solid rgba(255, 255, 255, 0.35); border-top-color: #ffffff; border-radius: 50%; animation: spin 0.75s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
