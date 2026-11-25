<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import type { ConfirmationRecord } from "../../types";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  workOrder: string;
  operation: string;
  sourceType?: string;
  cachedRecords?: ConfirmationRecord[] | null;
}>();

const emit = defineEmits<{
  (e: "loaded", workOrder: string, records: ConfirmationRecord[]): void;
}>();

const records = ref<ConfirmationRecord[]>([]);
const loading = ref<boolean>(false);
const errorMessage = ref<string | null>(null);
let latestRequestId = 0;

async function fetchConfirmations(force = false) {
  if (!props.workOrder) return;
  if (props.sourceType === "none") {
    records.value = [];
    errorMessage.value = null;
    loading.value = false;
    return;
  }
  if (!force && Array.isArray(props.cachedRecords)) {
    records.value = props.cachedRecords;
    errorMessage.value = null;
    loading.value = false;
    return;
  }

  const reqId = ++latestRequestId;
  loading.value = true;
  errorMessage.value = null;

  try {
    const res = await new Promise<ConfirmationRecord[]>((resolve, reject) => {
      frappe.call({
        method: "erpnextkta.kta_shopfloor.api.get_production_confirmations",
        args: { work_order: props.workOrder },
        quiet: true,
        callback: (r: { message?: ConfirmationRecord[] }) => {
          if ((window as any).frappe) (window as any).frappe.messages = [];
          resolve(Array.isArray(r.message) ? r.message : []);
        },
        error: (err: any) => {
          if ((window as any).frappe) (window as any).frappe.messages = [];
          reject(err);
        },
      });
    });
    if (reqId !== latestRequestId) return;
    records.value = res;
    emit("loaded", props.workOrder, res);
  } catch (err: any) {
    if (reqId !== latestRequestId) return;
    errorMessage.value = err?.message || __("Teyit Geçmişi Alınamadı");
    records.value = [];
  } finally {
    if (reqId === latestRequestId) loading.value = false;
  }
}

const filteredRecords = computed<ConfirmationRecord[]>(() =>
  records.value.filter(
    (c) => c.docstatus === 1 && (!props.operation || c.operation === props.operation)
  )
);

watch(
  () => [props.workOrder, props.operation, props.cachedRecords],
  () => fetchConfirmations(false)
);

onMounted(() => fetchConfirmations(false));
</script>

<template>
  <div class="op-detail-box">
    <div v-if="loading" class="detail-state">
      <div class="detail-spinner" aria-hidden="true" />
      <span>{{ __("Teyit Kayıtları Yükleniyor…") }}</span>
    </div>

    <div v-else-if="errorMessage" class="detail-error">
      <span>⚠️ {{ errorMessage }}</span>
      <button type="button" class="btn-detail-retry" @click="fetchConfirmations(true)">
        {{ __("Tekrar Dene") }}
      </button>
    </div>

    <div v-else-if="filteredRecords.length === 0" class="detail-empty">
      <span v-if="sourceType === 'legacy'">
        ℹ️ {{ __("Bu ilerleme doğrudan standart Üretim (Manufacture) stok fişinden gelmektedir.") }}
      </span>
      <span v-else>
        📝 {{ __("Bu operasyon için onaylı üretim teyidi bulunamadı.") }}
      </span>
    </div>

    <div v-else class="detail-table-wrap">
      <table class="detail-table">
        <thead>
          <tr>
            <th>{{ __("Teyit No") }}</th>
            <th>{{ __("Tarih / Saat") }}</th>
            <th>{{ __("Teyit Eden") }}</th>
            <th class="text-right">{{ __("Miktar") }}</th>
            <th>{{ __("İlişkili Stok Fişleri") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in filteredRecords" :key="c.name">
            <td>
              <div class="conf-cell">
                <a :href="`/app/kta-production-confirmation/${c.name}`" target="_blank" class="link-conf">
                  {{ c.name }}
                </a>
                <span v-if="c.is_final_confirmation" class="badge-final" :title="__('Son Teyit Olarak Kaydedildi')">
                  {{ __("Son") }}
                </span>
              </div>
            </td>
            <td class="cell-time">
              <span>{{ c.posting_date }}</span>
              <small v-if="c.posting_time" class="time-sub">{{ c.posting_time.substring(0, 5) }}</small>
            </td>
            <td class="cell-user" :title="c.confirmed_by || ''">{{ (c.confirmed_by || "—").split("@")[0] }}</td>
            <td class="text-right cell-qty">{{ c.yield_qty }}</td>
            <td>
              <div v-if="c.stock_entries && c.stock_entries.length > 0" class="se-badges">
                <a
                  v-for="se in c.stock_entries"
                  :key="se.name"
                  :href="`/app/stock-entry/${se.name}`"
                  target="_blank"
                  class="badge-se"
                  :class="'badge-se-' + se.type"
                  :title="se.purpose"
                >
                  <span aria-hidden="true">{{ se.type === "manufacture" ? "📦" : "⚙️" }}</span>
                  <span>{{ se.label || (se.type === "manufacture" ? __("Üretim") : __("Tüketim")) }}: {{ se.name }}</span>
                </a>
              </div>
              <a v-else-if="c.stock_entry" :href="`/app/stock-entry/${c.stock_entry}`" target="_blank" class="badge-se badge-se-manufacture">
                📦 {{ c.stock_entry }}
              </a>
              <span v-else class="text-muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.op-detail-box {
  padding: 0.75rem 1rem;
  background: var(--bg-color, #f8fafc);
  border-top: 1px dashed var(--border-color, #cbd5e1);
}
[data-theme="dark"] .op-detail-box {
  background: rgba(255, 255, 255, 0.025);
  border-top-color: rgba(255, 255, 255, 0.12);
}
.detail-state, .detail-empty, .detail-error {
  display: flex; align-items: center; gap: 0.6rem; padding: 0.45rem 0.25rem;
  font-size: 0.8rem; color: var(--text-muted, #64748b); font-weight: 600;
}
.detail-error { color: #b91c1c; justify-content: space-between; }
[data-theme="dark"] .detail-error { color: #fca5a5; }
.detail-spinner {
  width: 16px; height: 16px; border: 2px solid rgba(37, 99, 235, 0.25);
  border-top-color: #2563eb; border-radius: 50%; animation: detail-spin 0.75s linear infinite;
}
@keyframes detail-spin { to { transform: rotate(360deg); } }
.btn-detail-retry {
  padding: 0.2rem 0.55rem; border-radius: 0.35rem; border: 1px solid currentColor;
  background: transparent; color: inherit; font-size: 0.75rem; font-weight: 700; cursor: pointer;
}
.detail-table-wrap { overflow-x: auto; }
.detail-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.detail-table th {
  text-align: left; padding: 0.4rem 0.6rem; color: var(--text-muted, #64748b);
  font-weight: 700; border-bottom: 1px solid var(--border-color, #e2e8f0); white-space: nowrap;
}
.detail-table td {
  padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border-color, #e2e8f0); vertical-align: middle;
}
.detail-table tr:last-child td { border-bottom: none; }
.conf-cell { display: inline-flex; align-items: center; gap: 0.35rem; }
.link-conf { color: #2563eb; font-weight: 700; text-decoration: none; }
.link-conf:hover { text-decoration: underline; }
[data-theme="dark"] .link-conf { color: #60a5fa; }
.badge-final {
  background: #fef3c7; color: #b45309; font-size: 0.65rem; padding: 0.08rem 0.35rem;
  border-radius: 0.25rem; font-weight: 800;
}
[data-theme="dark"] .badge-final { background: rgba(245, 158, 11, 0.22); color: #fcd34d; }
.cell-time { white-space: nowrap; }
.time-sub { margin-left: 0.3rem; color: var(--text-muted, #64748b); font-size: 0.72rem; }
.cell-user { color: var(--text-muted, #64748b); }
.cell-qty { font-weight: 800; color: var(--text-color, #0f172a); }
.se-badges { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.badge-se {
  display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.72rem; font-weight: 600;
  padding: 0.12rem 0.45rem; border-radius: 0.35rem; text-decoration: none; white-space: nowrap;
}
.badge-se-manufacture { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
.badge-se-consumption { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
[data-theme="dark"] .badge-se-manufacture { background: rgba(34, 197, 94, 0.16); color: #86efac; border-color: rgba(74, 222, 128, 0.35); }
[data-theme="dark"] .badge-se-consumption { background: rgba(59, 130, 246, 0.16); color: #93c5fd; border-color: rgba(96, 165, 250, 0.35); }
.text-right { text-align: right; }
.text-muted { color: var(--text-muted, #64748b); }
</style>
