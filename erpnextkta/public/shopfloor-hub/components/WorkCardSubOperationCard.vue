<script setup lang="ts">
import { ref } from 'vue';
import type { SubOperationAnalytics } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  subOp: SubOperationAnalytics;
}>();

const isOpen = ref<boolean>(false);

function toggleOpen() {
  isOpen.value = !isOpen.value;
}

function getStatusClass(status: string): string {
  if (status === 'Tamamlandı' || status === 'Completed') return 'status-completed';
  if (status === 'Devam Ediyor' || status === 'In Process') return 'status-progress';
  return 'status-pending';
}

function formatSubOpBadge(status: string): string {
  const isDone = status === 'Tamamlandı' || status === 'Completed';
  const isInProgress = status === 'Devam Ediyor' || status === 'In Process';
  const icon = isDone ? '🟢' : isInProgress ? '🔵' : '⚪';
  return `${icon} ${__(status)}`;
}
</script>

<template>
  <div class="sub-op-card" :class="{ 'is-open': isOpen }">
    <div
      class="sub-op-header"
      role="button"
      tabindex="0"
      :aria-expanded="isOpen"
      @click="toggleOpen"
      @keydown.enter.space.prevent="toggleOpen"
    >
      <div class="sub-op-header-left">
        <span class="badge-sequence">#{{ subOp.sequence }}</span>
        <span class="sub-op-title">{{ __(subOp.title) }}</span>
        <span class="badge-status" :class="getStatusClass(subOp.status)">
          {{ formatSubOpBadge(subOp.status) }}
        </span>
        <span
          v-if="subOp.is_tuketim_hesaplanir === 0"
          class="badge-non-consumption"
          :title="__('Süreç Adımı (Tüketim Hesaplanmaz)')"
        >
          ℹ️ {{ __('Süreç Adımı (Tüketim Hesaplanmaz)') }}
        </span>
      </div>

      <div class="sub-op-header-right">
        <span class="badge-metric metric-qty" :title="__('Toplam İşlem Miktarı')">
          📦 {{ subOp.total_process_qty }} {{ __('Adet') }}
        </span>
        <span class="badge-metric metric-duration" :title="__('Toplam Süre')">
          ⏱️ {{ subOp.total_duration_mins }} {{ __('dk') }}
        </span>
        <span class="toggle-indicator" aria-hidden="true">
          {{ isOpen ? '▲' : '▼' }}
        </span>
      </div>
    </div>

    <div v-if="isOpen" class="sub-op-body">
      <!-- Hammadde Tüketimleri -->
      <div
        v-if="subOp.consumptions && subOp.consumptions.length > 0"
        class="sub-op-section"
      >
        <h5 class="section-title">
          <span>⚙️</span>
          <span>{{ __('Hammadde Tüketimleri') }}</span>
        </h5>
        <div class="table-responsive">
          <table class="detail-table">
            <thead>
              <tr>
                <th>{{ __('Malzeme Kodu') }}</th>
                <th>{{ __('Malzeme Adı') }}</th>
                <th class="text-right">{{ __('Toplam Miktar') }}</th>
                <th>{{ __('Birim') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="mat in subOp.consumptions" :key="mat.item_code">
                <td class="font-mono">
                  <a
                    :href="`/app/item/${mat.item_code}`"
                    target="_blank"
                    class="cell-link"
                  >
                    {{ mat.item_code }}
                  </a>
                </td>
                <td>{{ mat.item_name || '-' }}</td>
                <td class="text-right font-semibold">{{ mat.total_qty }}</td>
                <td><span class="uom-pill">{{ mat.uom }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Hurda Kayıtları -->
      <div
        v-if="subOp.scraps && subOp.scraps.length > 0"
        class="sub-op-section"
      >
        <h5 class="section-title text-scrap">
          <span>⚠️</span>
          <span>{{ __('Hurda Kayıtları') }}</span>
        </h5>
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
              <tr v-for="(scrap, idx) in subOp.scraps" :key="idx">
                <td class="font-mono">{{ scrap.item_code }}</td>
                <td class="text-right font-semibold text-danger">{{ scrap.qty }}</td>
                <td><span class="uom-pill">{{ scrap.uom }}</span></td>
                <td>{{ scrap.reason || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Bağlı Çalışma Kartları -->
      <div class="sub-op-section">
        <h5 class="section-title">
          <span>📇</span>
          <span>{{ __('Bağlı Çalışma Kartları') }}</span>
        </h5>
        <div
          v-if="subOp.cards && subOp.cards.length > 0"
          class="table-responsive"
        >
          <table class="detail-table">
            <thead>
              <tr>
                <th>{{ __('Kart No') }}</th>
                <th>{{ __('Operatör') }}</th>
                <th>{{ __('Durum') }}</th>
                <th class="text-right">{{ __('Çalışma Süresi') }}</th>
                <th class="text-right">{{ __('İşlem Adedi') }}</th>
                <th>{{ __('Kayıt Tarihi') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="card in subOp.cards" :key="card.card_name">
                <td class="font-mono">
                  <a
                    :href="`/app/calisma-karti/${card.card_name}`"
                    target="_blank"
                    class="cell-link"
                  >
                    {{ card.card_name }}
                  </a>
                </td>
                <td>{{ card.operator || '-' }}</td>
                <td>
                  <span class="status-pill" :class="getStatusClass(card.durum)">
                    {{ __(card.durum) }}
                  </span>
                </td>
                <td class="text-right">
                  {{ card.net_calisma_suresi }} {{ __('dk') }}
                </td>
                <td class="text-right font-semibold">{{ card.islem_adedi }}</td>
                <td class="text-muted text-xs">{{ card.creation }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-cards-notice">
          <span>⚪</span>
          <span>{{ __('Henüz Kart Açılmadı') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sub-op-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  margin-bottom: 0.6rem;
  overflow: hidden;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

[data-theme='dark'] .sub-op-card {
  background: var(--ck-glass-bg, #1a202c);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.sub-op-card:hover {
  border-color: var(--primary, #3b82f6);
}

.sub-op-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  cursor: pointer;
  background: var(--sub-header-bg, #f8fafc);
  gap: 0.75rem;
  user-select: none;
}

[data-theme='dark'] .sub-op-header {
  background: rgba(255, 255, 255, 0.03);
}

.sub-op-card.is-open .sub-op-header {
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

[data-theme='dark'] .sub-op-card.is-open .sub-op-header {
  border-bottom-color: var(--ck-glass-border, rgba(255, 255, 255, 0.08));
}

.sub-op-header-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.sub-op-header-right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
}

.badge-sequence {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-muted, #64748b);
  background: rgba(100, 116, 139, 0.12);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-family: monospace;
}

.sub-op-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-color, #0f172a);
}

.badge-status {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
  white-space: nowrap;
}

.status-completed {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

[data-theme='dark'] .status-completed {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.status-progress {
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

[data-theme='dark'] .status-progress {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.status-pending {
  background: rgba(100, 116, 139, 0.12);
  color: var(--text-muted, #64748b);
}

.badge-non-consumption {
  font-size: 0.72rem;
  font-weight: 500;
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
  border: 1px dashed rgba(217, 119, 6, 0.4);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

[data-theme='dark'] .badge-non-consumption {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.badge-metric {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  color: var(--text-color, #1e293b);
  white-space: nowrap;
}

[data-theme='dark'] .badge-metric {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.toggle-indicator {
  font-size: 0.7rem;
  color: var(--text-muted, #94a3b8);
  margin-left: 0.2rem;
}

.sub-op-body {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--body-bg, #fbfcfe);
}

[data-theme='dark'] .sub-op-body {
  background: rgba(0, 0, 0, 0.15);
}

.sub-op-section {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #64748b);
  margin: 0;
}

.section-title.text-scrap {
  color: #dc2626;
}

[data-theme='dark'] .section-title.text-scrap {
  color: #f87171;
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

.detail-table tbody tr:last-child td {
  border-bottom: none;
}

.detail-table tbody tr:hover {
  background: rgba(59, 130, 246, 0.03);
}

[data-theme='dark'] .detail-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.02);
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

.text-muted {
  color: var(--text-muted, #94a3b8);
}

.text-xs {
  font-size: 0.72rem;
}

.cell-link {
  color: var(--primary, #3b82f6);
  text-decoration: none;
}

.cell-link:hover {
  text-decoration: underline;
}

.uom-pill {
  font-size: 0.72rem;
  background: rgba(100, 116, 139, 0.08);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.status-pill {
  font-size: 0.72rem;
  padding: 0.15rem 0.45rem;
  border-radius: 9999px;
  font-weight: 600;
}

.empty-cards-notice {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 0.8rem;
  font-size: 0.8rem;
  color: var(--text-muted, #64748b);
  background: rgba(100, 116, 139, 0.06);
  border-radius: 6px;
  border: 1px dashed var(--border-color, #cbd5e1);
}

[data-theme='dark'] .empty-cards-notice {
  border-color: rgba(255, 255, 255, 0.1);
}
</style>
