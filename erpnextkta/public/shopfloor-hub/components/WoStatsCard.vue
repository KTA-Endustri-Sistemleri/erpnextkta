<script setup lang="ts">
import { ref, computed } from 'vue';
import type { WorkOrderContext } from '../types';
import WorkOrderPrintButton from './WorkOrderPrintButton.vue';

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  context: WorkOrderContext;
}>();

const copied = ref<boolean>(false);

const targetQty = computed<number>(() => Number(props.context?.qty) || 0);
const producedQty = computed<number>(() => Number(props.context?.produced_qty) || 0);
const remainingQty = computed<number>(() => Math.max(0, targetQty.value - producedQty.value));

const progressPercent = computed<number>(() => {
  if (targetQty.value <= 0) return 0;
  return Math.min(100, Math.round((producedQty.value / targetQty.value) * 100));
});

const statusClass = computed<string>(() => {
  const s = (props.context?.status || '').toLowerCase().replace(/\s+/g, '-');
  return `status-${s}`;
});

function copyWorkOrderNumber() {
  if (!props.context?.work_order) return;
  navigator.clipboard?.writeText(props.context.work_order);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 1800);
}
</script>

<template>
  <div class="co11n-card wo-card">
    <!-- Header: WO Badge + Link + Status Pill -->
    <div class="wo-header-row">
      <div class="wo-chip-wrapper">
        <a
          :href="`/app/work-order/${context.work_order}`"
          target="_blank"
          class="wo-badge-link"
          :title="__('İş Emrini Yeni Sekmede Aç')"
        >
          <span class="wo-icon">⚡</span>
          <span class="wo-text">{{ context.work_order }}</span>
          <span class="external-icon">↗</span>
        </a>
        <button
          type="button"
          class="btn-copy-chip"
          :title="__('Numarayı Kopyala')"
          @click="copyWorkOrderNumber"
        >
          <span v-if="copied" class="copied-text">{{ __('Kopyalandı!') }}</span>
          <span v-else class="copy-icon">📋</span>
        </button>
      </div>

      <div class="wo-header-right">
        <WorkOrderPrintButton v-if="context?.work_order" :work-order="context.work_order" compact />
        <span class="status-pill" :class="statusClass">
          <span class="status-dot" />
          {{ __(context.status) }}
        </span>
      </div>
    </div>

    <!-- Product Details -->
    <div class="wo-product-row">
      <div class="product-badge">
        <span class="product-tag">{{ __('Ürün') }}</span>
        <span class="item-code">{{ context.item_code }}</span>
      </div>
      <div v-if="context.item_name && context.item_name !== context.item_code" class="item-name">
        {{ context.item_name }}
      </div>
    </div>

    <!-- Modern KPI Cards -->
    <div class="kpi-grid">
      <!-- Target Qty -->
      <div class="kpi-card kpi-target">
        <div class="kpi-header">
          <span class="kpi-icon">🎯</span>
          <span class="kpi-label">{{ __('Hedef Miktar') }}</span>
        </div>
        <div class="kpi-value">{{ targetQty }}</div>
      </div>

      <!-- Produced Qty -->
      <div class="kpi-card kpi-produced">
        <div class="kpi-header">
          <span class="kpi-icon">✓</span>
          <span class="kpi-label">{{ __('Üretilen Mamul') }}</span>
        </div>
        <div class="kpi-value highlight-green">{{ producedQty }}</div>
      </div>

      <!-- Remaining Qty -->
      <div class="kpi-card kpi-remaining">
        <div class="kpi-header">
          <span class="kpi-icon">⏳</span>
          <span class="kpi-label">{{ __('Kalan Mamul') }}</span>
        </div>
        <div class="kpi-value highlight-blue">{{ remainingQty }}</div>
      </div>
    </div>

    <!-- Gradient Progress Bar -->
    <div class="progress-section">
      <div class="progress-labels">
        <span class="progress-title">{{ __('Üretim İlerlemesi') }}</span>
        <span class="progress-pct-badge" :class="{ 'pct-complete': progressPercent >= 100 }">
          %{{ progressPercent }} {{ __('Tamamlandı') }}
        </span>
      </div>
      <div class="progress-track">
        <div
          class="progress-fill-gradient"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.co11n-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.85rem;
  padding: 1.35rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.wo-card {
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
}

[data-theme='dark'] .wo-card {
  background: var(--ck-glass-bg, #1c2127);
  border-color: var(--ck-glass-border, rgba(255, 255, 255, 0.1));
}

/* Header Row */
.wo-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.wo-header-right {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.wo-chip-wrapper {
  display: inline-flex;
  align-items: center;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.2);
  border-radius: 0.6rem;
  padding: 0.2rem 0.4rem 0.2rem 0.75rem;
  gap: 0.4rem;
}

.wo-badge-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 1.15rem;
  font-weight: 800;
  color: #2563eb;
  text-decoration: none;
  letter-spacing: -0.01em;
}

.wo-badge-link:hover {
  text-decoration: underline;
}

.wo-icon {
  font-size: 1rem;
}

.external-icon {
  font-size: 0.8rem;
  opacity: 0.7;
}

.btn-copy-chip {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem 0.4rem;
  border-radius: 0.35rem;
  color: #2563eb;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  transition: background 0.15s;
}

.btn-copy-chip:hover {
  background: rgba(37, 99, 235, 0.15);
}

.copied-text {
  font-size: 0.7rem;
  font-weight: 700;
  color: #16a34a;
}

/* Status Pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.85rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-completed {
  background: #dcfce7;
  color: #15803d;
}

.status-in-process {
  background: #dbeafe;
  color: #1d4ed8;
}

.status-not-started {
  background: #f1f5f9;
  color: #475569;
}

/* Product Info */
.wo-product-row {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.25rem 0;
}

.product-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
}

.product-tag {
  background: #f1f5f9;
  color: #64748b;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: 0.35rem;
  text-transform: uppercase;
}

[data-theme='dark'] .product-tag {
  background: rgba(255, 255, 255, 0.1);
  color: #94a3b8;
}

.item-code {
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.item-name {
  font-size: 0.88rem;
  color: var(--text-muted, #64748b);
  line-height: 1.4;
}

/* KPI Cards */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.85rem;
}

@media (max-width: 600px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}

.kpi-card {
  padding: 0.85rem 1rem;
  border-radius: 0.65rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-color, #f8fafc);
  transition: transform 0.15s, box-shadow 0.15s;
}

.kpi-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.04);
}

.kpi-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.kpi-icon {
  font-size: 0.95rem;
}

.kpi-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted, #64748b);
}

.kpi-value {
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--text-color, #0f172a);
}

.kpi-produced {
  background: rgba(22, 163, 74, 0.04);
  border-color: rgba(22, 163, 74, 0.2);
}

.highlight-green {
  color: #16a34a;
}

.kpi-remaining {
  background: rgba(37, 99, 235, 0.04);
  border-color: rgba(37, 99, 235, 0.2);
}

.highlight-blue {
  color: #2563eb;
}

/* Progress Section */
.progress-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.2rem;
}

.progress-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.progress-pct-badge {
  font-size: 0.75rem;
  font-weight: 700;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.1);
  padding: 0.15rem 0.55rem;
  border-radius: 9999px;
}

.progress-pct-badge.pct-complete {
  color: #16a34a;
  background: #dcfce7;
}

.progress-track {
  height: 9px;
  background: #e2e8f0;
  border-radius: 9999px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
}

[data-theme='dark'] .progress-track {
  background: rgba(255, 255, 255, 0.1);
}

.progress-fill-gradient {
  height: 100%;
  background: linear-gradient(90deg, #2563eb 0%, #16a34a 100%);
  border-radius: 9999px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
