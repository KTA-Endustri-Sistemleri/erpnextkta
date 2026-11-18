<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import type { ConfirmationRecord } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    workOrder: string;
    refreshKey?: number;
  }>(),
  {
    refreshKey: 0,
  }
);

const emit = defineEmits<{
  (e: 'confirmation-cancelled', name: string): void;
}>();

const confirmations = ref<ConfirmationRecord[]>([]);
const loading = ref<boolean>(false);
const cancellingId = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

async function fetchHistory() {
  if (!props.workOrder) {
    confirmations.value = [];
    return;
  }
  loading.value = true;
  errorMessage.value = null;
  try {
    const res = await new Promise<ConfirmationRecord[]>((resolve, reject) => {
      frappe.call({
        method: 'erpnextkta.kta_shopfloor.api.get_production_confirmations',
        args: { work_order: props.workOrder },
        quiet: true,
        callback: (r: { message?: ConfirmationRecord[] }) => resolve(r.message || []),
        error: () => {
          frappe.call({
            method: 'erpnextkta.kta_shopfloor.api.get_co11n_confirmations',
            args: { work_order: props.workOrder },
            quiet: true,
            callback: (r1: { message?: ConfirmationRecord[] }) => resolve(r1.message || []),
            error: () => {
              frappe.call({
                method: 'frappe.client.get_list',
                args: {
                  doctype: 'KTA Production Confirmation',
                  filters: { work_order: props.workOrder },
                  fields: [
                    'name', 'operation', 'yield_qty', 'posting_date', 'posting_time',
                    'confirmed_by', 'stock_entry', 'docstatus', 'is_final_confirmation', 'creation',
                  ],
                  order_by: 'creation desc',
                  limit: 30,
                },
                quiet: true,
                callback: (r2: { message?: ConfirmationRecord[] }) => resolve(r2.message || []),
                error: (err2: any) => reject(err2),
              });
            },
          });
        },
      });
    });
    confirmations.value = Array.isArray(res) ? res : [];
  } catch (err: any) {
    console.error('fetchHistory error:', err);
    errorMessage.value = err?.message || __('Teyit Geçmişi Alınamadı');
    confirmations.value = [];
  } finally {
    loading.value = false;
  }
}

function handleCancel(conf: ConfirmationRecord) {
  if (cancellingId.value || conf.docstatus === 2) return;
  const msg = __(
    '"{0}" numaralı teyit belgesini ve ilişkili stok hareketlerini ters kayıt ' +
      '(storno) ile iptal etmek istediğinize emin misiniz? Bu işlem geri alınamaz.',
    [conf.name]
  );
  const performCancel = async () => {
    cancellingId.value = conf.name;
    errorMessage.value = null;
    try {
      const res = await new Promise<{ success?: boolean; message?: string }>((resolve, reject) => {
        frappe.call({
          method: 'erpnextkta.kta_shopfloor.api.cancel_production_confirmation',
          args: { confirmation_name: conf.name },
          quiet: true,
          callback: (r: { message?: any }) => resolve(r.message),
          error: () => {
            frappe.call({
              method: 'erpnextkta.kta_shopfloor.api.cancel_co11n_confirmation',
              args: { confirmation_name: conf.name },
              quiet: true,
              callback: (r2: { message?: any }) => resolve(r2.message),
              error: (err2: any) => reject(err2),
            });
          },
        });
      });
      if (res && res.success) {
        frappe.show_alert?.({
          message: __('Teyit Başarıyla İptal Edildi: {0}', [conf.name]),
          indicator: 'orange',
        });
        emit('confirmation-cancelled', conf.name);
        fetchHistory();
      } else {
        throw new Error(res?.message || __('İptal İşlemi Başarısız'));
      }
    } catch (err: any) {
      console.error('cancel_co11n_confirmation error:', err);
      errorMessage.value =
        err?.message ||
        err?._server_messages ||
        __('Teyit iptal edilirken bir hata oluştu.');
    } finally {
      cancellingId.value = null;
    }
  };

  if ((window as any).frappe?.confirm) (window as any).frappe.confirm(msg, performCancel);
  else if (confirm(msg)) performCancel();
}

watch(
  () => [props.workOrder, props.refreshKey],
  () => fetchHistory()
);

onMounted(() => fetchHistory());
</script>

<template>
  <div class="co11n-card history-card">
    <div class="history-head">
      <div class="title-with-badge">
        <h3 class="section-title">{{ __('Teyit Geçmişi ve Hareketler') }}</h3>
        <span class="count-badge">{{ __('{0} Kayıt', [confirmations.length]) }}</span>
      </div>
      <button
        type="button"
        class="btn-refresh"
        :title="__('Yenile')"
        :disabled="loading"
        @click="fetchHistory"
      >
        <span :class="{ spinning: loading }">↻</span> {{ __('Yenile') }}
      </button>
    </div>

    <div v-if="errorMessage" class="history-error-alert">
      <span>⚠️ {{ errorMessage }}</span>
      <button type="button" class="btn-alert-close" @click="errorMessage = null">✕</button>
    </div>

    <div v-if="loading && confirmations.length === 0" class="history-state-box">
      <div class="loading-spinner" />
      <span>{{ __('Teyit Kayıtları Yükleniyor…') }}</span>
    </div>

    <div v-else-if="confirmations.length === 0" class="history-state-box">
      <span class="empty-icon">📝</span>
      <p>{{ __('Bu iş emrine ait henüz bir üretim teyidi kaydedilmemiş.') }}</p>
    </div>

    <div v-else class="table-responsive">
      <table class="history-table">
        <thead>
          <tr>
            <th>{{ __('Teyit No') }}</th>
            <th>{{ __('Operasyon') }}</th>
            <th class="text-right">{{ __('Miktar') }}</th>
            <th>{{ __('Tarih / Saat') }}</th>
            <th>{{ __('Kullanıcı') }}</th>
            <th>{{ __('İlişkili Stok Fişleri') }}</th>
            <th>{{ __('Durum') }}</th>
            <th class="text-center">{{ __('İşlem') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in confirmations" :key="c.name" :class="{ cancelled: c.docstatus === 2 }">
            <!-- Teyit No -->
            <td>
              <div class="cell-conf-wrapper">
                <a
                  :href="`/app/kta-production-confirmation/${c.name}`"
                  target="_blank"
                  class="link-conf"
                >
                  {{ c.name }}
                </a>
                <span
                  v-if="c.is_final_confirmation"
                  class="badge-final"
                  :title="__('Son Teyit Olarak Kaydedildi')"
                >
                  {{ __('Son') }}
                </span>
              </div>
            </td>

            <!-- Operasyon -->
            <td><span class="op-cell">{{ __(c.operation) }}</span></td>

            <!-- Miktar -->
            <td class="text-right cell-qty"><strong>{{ c.yield_qty }}</strong></td>

            <!-- Tarih / Saat -->
            <td class="cell-time">
              <span>{{ c.posting_date }}</span>
              <small class="time-sub">{{ (c.posting_time || '').substring(0, 5) }}</small>
            </td>

            <!-- Kullanıcı -->
            <td class="cell-user">{{ (c.confirmed_by || '').split('@')[0] }}</td>

            <!-- Stok Fişleri (Çoklu / Tekli) -->
            <td>
              <div v-if="c.stock_entries && c.stock_entries.length > 0" class="stock-entries-col">
                <a
                  v-for="se in c.stock_entries"
                  :key="se.name"
                  :href="`/app/stock-entry/${se.name}`"
                  target="_blank"
                  class="badge-se"
                  :class="'badge-se-' + se.type"
                  :title="se.purpose"
                >
                  <span v-if="se.type === 'manufacture'">📦</span>
                  <span v-else>⚙️</span>
                  <span>{{ se.label || (se.type === 'manufacture' ? __('Üretim') : __('Tüketim')) }}: {{ se.name }}</span>
                </a>
              </div>
              <a v-else-if="c.stock_entry" :href="`/app/stock-entry/${c.stock_entry}`" target="_blank" class="link-stock">
                📦 {{ c.stock_entry }}
              </a>
              <span v-else class="text-muted">-</span>
            </td>

            <!-- Durum -->
            <td>
              <span class="status-tag" :class="c.docstatus === 2 ? 'tag-cancelled' : 'tag-active'">
                {{ c.docstatus === 2 ? __('İptal Edildi') : __('Tamamlandı') }}
              </span>
            </td>

            <!-- İptal Aksiyonu -->
            <td class="text-center">
              <button
                v-if="c.docstatus !== 2"
                type="button"
                class="btn-cors-cancel"
                :disabled="cancellingId === c.name"
                :title="__('Ters Kayıt (Storno) ile Bu Teyidi İptal Et')"
                @click="handleCancel(c)"
              >
                <span v-if="cancellingId === c.name" class="mini-spinner" />
                <span v-else>↩ {{ __('İptal') }}</span>
              </button>
              <span v-else class="cancelled-dash">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.co11n-card {
  background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.75rem; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.history-card { display: flex; flex-direction: column; gap: 1rem; }
.history-head { display: flex; justify-content: space-between; align-items: center; }
.title-with-badge { display: flex; align-items: center; gap: 0.75rem; }
.section-title { margin: 0; font-size: 1.1rem; font-weight: 700; color: var(--text-color, #111827); }
.count-badge { font-size: 0.75rem; background: #f3f4f6; color: #4b5563; padding: 0.15rem 0.5rem; border-radius: 9999px; font-weight: 700; }
.btn-refresh {
  background: var(--bg-color, #f3f4f6); border: 1px solid var(--border-color, #d1d5db);
  padding: 0.35rem 0.75rem; border-radius: 0.45rem; font-size: 0.8rem; font-weight: 600;
  cursor: pointer; display: flex; align-items: center; gap: 0.35rem; transition: all 0.2s;
}
.btn-refresh:hover:not(:disabled) { background: #e5e7eb; }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }
.history-error-alert { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; border-radius: 0.5rem; font-size: 0.85rem; }
.btn-alert-close { background: none; border: none; cursor: pointer; color: inherit; font-weight: bold; }
.history-state-box { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2.5rem 1rem; color: var(--text-muted, #6b7280); gap: 0.5rem; text-align: center; }
.loading-spinner { width: 24px; height: 24px; border: 2px solid rgba(37, 99, 235, 0.2); border-radius: 50%; border-top-color: #2563eb; animation: spin 0.8s linear infinite; }
.empty-icon { font-size: 2rem; }
.table-responsive { overflow-x: auto; }
.history-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.history-table th { background: var(--bg-color, #f9fafb); padding: 0.65rem 0.75rem; text-align: left; font-weight: 700; color: var(--text-muted, #6b7280); border-bottom: 2px solid var(--border-color, #e5e7eb); white-space: nowrap; }
.history-table td { padding: 0.7rem 0.75rem; border-bottom: 1px solid var(--border-color, #e5e7eb); vertical-align: middle; }
.history-table tr:hover { background: rgba(37, 99, 235, 0.02); }
.history-table tr.cancelled {
  background: rgba(239, 68, 68, 0.06);
}
[data-theme='dark'] .history-table tr.cancelled {
  background: rgba(239, 68, 68, 0.14);
}
.cell-conf-wrapper { font-weight: 700; display: flex; align-items: center; gap: 0.35rem; }
.link-conf { color: #2563eb; text-decoration: none; }
.link-conf:hover { text-decoration: underline; }
.badge-final { background: #fef3c7; color: #b45309; font-size: 0.65rem; padding: 0.1rem 0.35rem; border-radius: 0.25rem; font-weight: 800; }
.op-cell { font-weight: 600; }
.cell-qty { font-size: 0.95rem; }
.cell-time { white-space: nowrap; }
.time-sub { display: block; font-size: 0.72rem; color: var(--text-muted, #9ca3af); }
.cell-user { color: var(--text-muted, #6b7280); font-size: 0.8rem; }
.stock-entries-col { display: flex; flex-direction: column; gap: 0.25rem; }
.badge-se { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; font-weight: 600; padding: 0.15rem 0.45rem; border-radius: 0.35rem; text-decoration: none; }
.badge-se-manufacture { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
.badge-se-manufacture:hover { background: #bbf7d0; }
.badge-se-consumption { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
.badge-se-consumption:hover { background: #dbeafe; }
.link-stock { color: #059669; font-weight: 600; text-decoration: none; font-size: 0.8rem; }
.link-stock:hover { text-decoration: underline; }
.status-tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; }
.tag-active { background: #dcfce7; color: #15803d; }
.tag-cancelled { background: #fee2e2; color: #b91c1c; }
.btn-cors-cancel { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; padding: 0.25rem 0.6rem; border-radius: 0.35rem; font-size: 0.75rem; font-weight: 700; cursor: pointer; transition: all 0.15s; white-space: nowrap; }
.btn-cors-cancel:hover:not(:disabled) { background: #fecaca; transform: scale(1.02); }
.btn-cors-cancel:disabled { opacity: 0.5; cursor: not-allowed; }
.cancelled-dash { color: var(--text-muted, #9ca3af); font-weight: bold; }
.mini-spinner { display: inline-block; width: 12px; height: 12px; border: 2px solid rgba(185, 28, 28, 0.3); border-radius: 50%; border-top-color: #b91c1c; animation: spin 0.8s linear infinite; }
.text-right { text-align: right; }
.text-center { text-align: center; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
