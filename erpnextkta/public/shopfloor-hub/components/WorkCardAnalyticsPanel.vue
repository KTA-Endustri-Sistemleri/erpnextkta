<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import type { WorkCardAnalyticsResponse } from '../types';
import WorkCardSubOperationCard from './WorkCardSubOperationCard.vue';
import WorkCardMaterialReconciliation from './WorkCardMaterialReconciliation.vue';

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    workOrder: string;
    loadingWorkOrder?: boolean;
  }>(),
  {
    loadingWorkOrder: false,
  }
);

const analyticsData = ref<WorkCardAnalyticsResponse | null>(null);
const loading = ref<boolean>(false);
const error = ref<string | null>(null);
const openOps = ref<Record<string, boolean>>({});

function isOpOpen(opName: string): boolean {
  return !!openOps.value[opName];
}

function toggleOp(opName: string) {
  openOps.value[opName] = !openOps.value[opName];
}

async function fetchAnalytics() {
  if (!props.workOrder) {
    analyticsData.value = null;
    openOps.value = {};
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const res = await new Promise<WorkCardAnalyticsResponse>((resolve, reject) => {
      frappe.call({
        method:
          'erpnextkta.kta_calisma_karti.api.get_work_order_card_analytics',
        args: { work_order: props.workOrder },
        quiet: true,
        callback: (r: { message?: WorkCardAnalyticsResponse }) => {
          if (r.message) {
            resolve(r.message);
          } else {
            reject(new Error(__('Analitik verisi alınamadı.')));
          }
        },
        error: (err: any) => reject(err),
      });
    });
    analyticsData.value = res;
    if (res?.operations) {
      res.operations.forEach((op: any) => {
        openOps.value[op.operation_name] = true;
      });
    }
  } catch (err: any) {
    console.error('fetchAnalytics error:', err);
    error.value =
      err?.message ||
      err?._server_messages ||
      __('Çalışma Kartı verileri yüklenirken bir hata oluştu.');
    analyticsData.value = null;
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.workOrder,
  () => {
    fetchAnalytics();
  }
);

onMounted(() => {
  fetchAnalytics();
});
</script>

<template>
  <div class="card-analytics-root">
    <!-- Üst Başlık ve Yenileme Çubuğu -->
    <div class="analytics-header-card">
      <div class="header-left">
        <div class="wo-title-badge">
          <span class="badge-icon">📇</span>
          <span class="wo-code">{{ workOrder }}</span>
          <a
            :href="`/app/work-order/${workOrder}`"
            target="_blank"
            class="external-link"
            :title="__('İş Emrini Yeni Sekmede Aç')"
          >
            ↗
          </a>
        </div>
        <div v-if="analyticsData" class="item-info">
          <span class="item-code">{{ analyticsData.production_item }}</span>
          <span v-if="analyticsData.item_name" class="item-name">
            — {{ analyticsData.item_name }}
          </span>
          <span class="qty-pill">
            🎯 {{ analyticsData.qty }} {{ __('Adet') }}
          </span>
        </div>
      </div>

      <div class="header-right">
        <button
          type="button"
          class="btn-refresh"
          :disabled="loading"
          @click="fetchAnalytics"
        >
          <span class="refresh-icon" :class="{ spinning: loading }">🔄</span>
          <span>{{ __('Yenile') }}</span>
        </button>
      </div>
    </div>

    <!-- Hata Mesajı -->
    <div v-if="error" class="co11n-alert alert-danger">
      <div class="alert-content">
        <span class="alert-icon">⚠️</span>
        <div>{{ error }}</div>
      </div>
      <button type="button" class="btn-retry" @click="fetchAnalytics">
        {{ __('Tekrar Dene') }}
      </button>
    </div>

    <!-- Yükleniyor Durumu -->
    <div v-if="loading" class="loading-state">
      <div class="workspace-spinner" />
      <div class="loading-text">
        {{ __('Çalışma Kartı Verileri Yükleniyor…') }}
      </div>
    </div>

    <template v-else-if="analyticsData">
      <!-- KPI Özet Kartları -->
      <div class="kpi-grid">
        <!-- Toplam Kart -->
        <div class="kpi-card kpi-total">
          <div class="kpi-header">
            <span class="kpi-icon">📇</span>
            <span class="kpi-label">{{ __('Toplam Kart') }}</span>
          </div>
          <div class="kpi-value">{{ analyticsData.summary.total_cards }}</div>
        </div>

        <!-- Tamamlanan Kart -->
        <div class="kpi-card kpi-completed">
          <div class="kpi-header">
            <span class="kpi-icon">✓</span>
            <span class="kpi-label">{{ __('Tamamlanan Kart') }}</span>
          </div>
          <div class="kpi-value text-green">
            {{ analyticsData.summary.completed_cards }}
          </div>
        </div>

        <!-- Devam Eden Kart -->
        <div class="kpi-card kpi-progress">
          <div class="kpi-header">
            <span class="kpi-icon">🔵</span>
            <span class="kpi-label">{{ __('Devam Eden Kart') }}</span>
          </div>
          <div class="kpi-value text-blue">
            {{ analyticsData.summary.in_progress_cards }}
          </div>
        </div>

        <!-- Toplam Süre -->
        <div class="kpi-card kpi-duration">
          <div class="kpi-header">
            <span class="kpi-icon">⏱️</span>
            <span class="kpi-label">{{ __('Toplam Çalışma Süresi') }}</span>
          </div>
          <div class="kpi-value">
            {{ analyticsData.summary.total_duration_mins }}
            <small class="unit">{{ __('dk') }}</small>
          </div>
        </div>

        <!-- Toplam Hurda -->
        <div class="kpi-card kpi-scrap">
          <div class="kpi-header">
            <span class="kpi-icon">⚠️</span>
            <span class="kpi-label">{{ __('Toplam Hurda') }}</span>
          </div>
          <div class="kpi-value text-red">
            {{ analyticsData.summary.total_scrap_qty }}
          </div>
        </div>
      </div>

      <!-- Hammadde Tüketim ve Fire Mutabakatı -->
      <WorkCardMaterialReconciliation
        v-if="analyticsData?.material_reconciliation"
        :items="analyticsData.material_reconciliation"
      />

      <!-- Operasyonlar ve Alt Operasyonlar Ağacı -->
      <div class="operations-flow">
        <h4 class="flow-title">
          <span>📋</span>
          <span>{{ __('Rota ve Alt Operasyon Kontrol Listesi') }}</span>
        </h4>

        <div
          v-if="!analyticsData.operations || analyticsData.operations.length === 0"
          class="empty-ops-box"
        >
          <span>⚪</span>
          <span>{{ __('Bu iş emrine ait operasyon kaydı bulunamadı.') }}</span>
        </div>

        <div
          v-for="op in analyticsData.operations"
          :key="op.operation_name"
          class="op-accordion-card"
        >
          <!-- Operasyon Başlığı -->
          <div
            class="op-header"
            role="button"
            tabindex="0"
            :aria-expanded="isOpOpen(op.operation_name)"
            @click="toggleOp(op.operation_name)"
            @keydown.enter.space.prevent="toggleOp(op.operation_name)"
          >
            <div class="op-header-left">
              <span class="op-icon">⚙️</span>
              <strong class="op-name">
                [#{{ op.sequence_id || 1 }}] {{ __(op.operation_name) }}
              </strong>
              <a
                v-if="op.job_card"
                :href="`/app/job-card/${op.job_card}`"
                target="_blank"
                class="job-card-link"
                :title="__('Job Card Belgesini Aç')"
                @click.stop
              >
                📄 {{ op.job_card }}
              </a>
              <span class="badge-op-status">
                {{ __(op.status) }}
              </span>
            </div>

            <div class="op-header-right">
              <span class="op-duration-badge" :title="__('Operasyon Toplam Süresi')">
                ⏱️ {{ op.total_duration_mins }} {{ __('dk') }}
              </span>
              <span class="accordion-arrow">
                {{ isOpOpen(op.operation_name) ? '▲' : '▼' }}
              </span>
            </div>
          </div>

          <!-- Operasyon İçeriği -->
          <div v-if="isOpOpen(op.operation_name)" class="op-content">
            <!-- Eşleşmeyen Hurdalar (Varsa) -->
            <div
              v-if="op.unmatched_scraps && op.unmatched_scraps.length > 0"
              class="unmatched-scrap-box"
            >
              <div class="unmatched-scrap-header">
                <span class="warning-icon">⚠️</span>
                <strong>{{ __('Eşleşmeyen Hurdalar (Unassigned Scraps)') }}</strong>
              </div>
              <div class="table-responsive">
                <table class="detail-table scrap-table">
                  <thead>
                    <tr>
                      <th>{{ __('Malzeme Kodu') }}</th>
                      <th class="text-right">{{ __('Miktar') }}</th>
                      <th>{{ __('Birim') }}</th>
                      <th>{{ __('Hurda Nedeni') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(scrap, idx) in op.unmatched_scraps" :key="idx">
                      <td class="font-mono">{{ scrap.item_code }}</td>
                      <td class="text-right font-semibold text-danger">
                        {{ scrap.qty }}
                      </td>
                      <td>
                        <span class="uom-pill">{{ scrap.uom }}</span>
                      </td>
                      <td>{{ scrap.reason || '-' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- KTA Operasyon Grupları veya Alt Operasyonlar Listesi -->
            <div
              v-if="op.kta_operations && op.kta_operations.length > 0"
              class="kta-groups-container"
            >
              <div
                v-for="kta in op.kta_operations"
                :key="kta.op_code"
                class="kta-op-group"
              >
                <div class="kta-op-header">
                  <div class="kta-op-title">
                    <span class="kta-op-icon">📁</span>
                    <span>{{ kta.op_code }} — {{ __(kta.op_title) }}</span>
                  </div>
                  <span class="kta-duration-badge">
                    ⏱️ {{ kta.total_duration_mins }} {{ __('dk') }}
                  </span>
                </div>
                <div class="sub-ops-container">
                  <WorkCardSubOperationCard
                    v-for="sub in kta.sub_operations"
                    :key="sub.sub_op_id"
                    :sub-op="sub"
                  />
                </div>
              </div>
            </div>

            <!-- Fallback: Doğrudan Alt Operasyonlar Listesi -->
            <div v-else class="sub-ops-container">
              <WorkCardSubOperationCard
                v-for="sub in op.sub_operations"
                :key="sub.sub_op_id"
                :sub-op="sub"
              />
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.card-analytics-root {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
}

.analytics-header-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
  flex-wrap: wrap;
  gap: 0.75rem;
}

[data-theme='dark'] .analytics-header-card {
  background: var(--ck-glass-bg, #1a202c);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.wo-title-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(59, 130, 246, 0.1);
  color: var(--primary, #2563eb);
  padding: 0.35rem 0.65rem;
  border-radius: 6px;
  font-weight: 700;
  font-size: 0.95rem;
}

[data-theme='dark'] .wo-title-badge {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.external-link {
  color: inherit;
  text-decoration: none;
  font-size: 0.85rem;
}

.external-link:hover {
  text-decoration: underline;
}

.item-info {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-color, #334155);
}

.item-code {
  font-weight: 700;
  font-family: monospace;
}

.item-name {
  color: var(--text-muted, #64748b);
}

.qty-pill {
  background: rgba(100, 116, 139, 0.1);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
  font-size: 0.78rem;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.8rem;
  font-size: 0.82rem;
  font-weight: 600;
  border-radius: 6px;
  border: 1px solid var(--border-color, #cbd5e1);
  background: var(--card-bg, #ffffff);
  color: var(--text-color, #334155);
  cursor: pointer;
  transition: all 0.15s ease;
}

[data-theme='dark'] .btn-refresh {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.12);
  color: #e2e8f0;
}

.btn-refresh:hover:not(:disabled) {
  background: rgba(100, 116, 139, 0.08);
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.co11n-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.15rem;
  border-radius: 8px;
  font-size: 0.85rem;
}

.alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #b91c1c;
}

[data-theme='dark'] .alert-danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.btn-retry {
  padding: 0.3rem 0.6rem;
  font-size: 0.78rem;
  font-weight: 600;
  border-radius: 4px;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  gap: 1rem;
}

.loading-text {
  font-size: 0.9rem;
  color: var(--text-muted, #64748b);
  font-weight: 500;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.85rem;
}

.kpi-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.75rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

[data-theme='dark'] .kpi-card {
  background: var(--ck-glass-bg, #1a202c);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.kpi-header {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.kpi-icon {
  font-size: 1rem;
}

.kpi-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.kpi-value {
  font-size: 1.45rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.kpi-value .unit {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted, #64748b);
  margin-left: 0.2rem;
}

.text-green {
  color: #16a34a;
}

[data-theme='dark'] .text-green {
  color: #4ade80;
}

.text-blue {
  color: #2563eb;
}

[data-theme='dark'] .text-blue {
  color: #60a5fa;
}

.text-red {
  color: #dc2626;
}

[data-theme='dark'] .text-red {
  color: #f87171;
}

.operations-flow {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.flow-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-color, #1e293b);
  margin: 0 0 0.25rem 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.empty-ops-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1.25rem;
  background: var(--card-bg, #ffffff);
  border: 1px dashed var(--border-color, #cbd5e1);
  border-radius: 8px;
  color: var(--text-muted, #64748b);
  font-size: 0.88rem;
}

.op-accordion-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.75rem;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

[data-theme='dark'] .op-accordion-card {
  background: var(--ck-glass-bg, #1a202c);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.op-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.15rem;
  background: rgba(100, 116, 139, 0.04);
  cursor: pointer;
  user-select: none;
  gap: 0.75rem;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
}

[data-theme='dark'] .op-header {
  background: rgba(255, 255, 255, 0.03);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.op-header-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.op-name {
  font-size: 0.95rem;
  color: var(--text-color, #0f172a);
}

.job-card-link {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--primary, #3b82f6);
  background: rgba(59, 130, 246, 0.08);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  text-decoration: none;
}

.job-card-link:hover {
  text-decoration: underline;
}

.badge-op-status {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted, #64748b);
  background: rgba(100, 116, 139, 0.1);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

.op-header-right {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}

.op-duration-badge {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-color, #1e293b);
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
}

[data-theme='dark'] .op-duration-badge {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.accordion-arrow {
  font-size: 0.72rem;
  color: var(--text-muted, #94a3b8);
}

.op-content {
  padding: 1rem 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.unmatched-scrap-box {
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 6px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

[data-theme='dark'] .unmatched-scrap-box {
  background: rgba(239, 68, 68, 0.1);
}

.unmatched-scrap-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: #dc2626;
}

[data-theme='dark'] .unmatched-scrap-header {
  color: #f87171;
}

.kta-groups-container {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.kta-op-group {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
}

[data-theme='dark'] .kta-op-group {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.08);
}

.kta-op-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 0.9rem;
  background: rgba(100, 116, 139, 0.06);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  gap: 0.6rem;
}

[data-theme='dark'] .kta-op-header {
  background: rgba(255, 255, 255, 0.04);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.kta-op-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-color, #1e293b);
}

[data-theme='dark'] .kta-op-title {
  color: #f1f5f9;
}

.kta-op-icon {
  font-size: 0.9rem;
}

.kta-duration-badge {
  font-size: 0.74rem;
  font-weight: 600;
  color: var(--text-color, #334155);
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #cbd5e1);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

[data-theme='dark'] .kta-duration-badge {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: #cbd5e1;
}

.sub-ops-container {
  display: flex;
  flex-direction: column;
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 6px;
  background: var(--card-bg, #ffffff);
}

[data-theme='dark'] .table-responsive {
  background: var(--ck-glass-bg, #1a202c);
  border-color: rgba(255, 255, 255, 0.08);
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  text-align: left;
}

.detail-table th {
  padding: 0.45rem 0.65rem;
  font-weight: 600;
  color: var(--text-muted, #64748b);
  background: rgba(100, 116, 139, 0.05);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  white-space: nowrap;
}

[data-theme='dark'] .detail-table th {
  background: rgba(255, 255, 255, 0.03);
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.detail-table td {
  padding: 0.45rem 0.65rem;
  color: var(--text-color, #1e293b);
  border-bottom: 1px solid var(--border-color, #f1f5f9);
}

[data-theme='dark'] .detail-table td {
  border-bottom-color: rgba(255, 255, 255, 0.04);
}

.font-mono {
  font-family: monospace;
}

.font-semibold {
  font-weight: 600;
}

.text-right {
  text-align: right;
}

.text-danger {
  color: #dc2626;
}

[data-theme='dark'] .text-danger {
  color: #f87171;
}

.uom-pill {
  font-size: 0.72rem;
  background: rgba(100, 116, 139, 0.08);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}
</style>
