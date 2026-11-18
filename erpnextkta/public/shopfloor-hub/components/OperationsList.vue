<script setup lang="ts">
import type { OperationInfo } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    operations?: OperationInfo[];
    selectedOperation?: OperationInfo | null;
    targetQty?: number;
  }>(),
  {
    operations: () => [],
    selectedOperation: null,
    targetQty: 0,
  }
);

const emit = defineEmits<{
  (e: 'select', op: OperationInfo): void;
}>();

function isSelected(op: OperationInfo): boolean {
  return props.selectedOperation?.operation === op.operation;
}

function isCompleted(op: OperationInfo): boolean {
  const completed = Number(op.completed_qty) || 0;
  const target = Number(props.targetQty) || 0;
  return target > 0 && completed >= target;
}
</script>

<template>
  <div class="co11n-card ops-card">
    <div class="ops-header">
      <h3 class="section-title">{{ __('Operasyonlar') }}</h3>
      <span class="ops-count">{{ __('{0} Adım', [operations.length]) }}</span>
    </div>

    <div class="ops-list">
      <div
        v-for="op in operations"
        :key="op.operation"
        class="op-item"
        :class="{
          active: isSelected(op),
          completed: isCompleted(op),
        }"
        @click="emit('select', op)"
      >
        <!-- Sequence Circle -->
        <div class="op-seq-box">
          <span class="op-seq">{{ op.sequence_id }}</span>
        </div>

        <!-- Body: Name, Milestone, Workstation, Job Card -->
        <div class="op-body">
          <div class="op-title-row">
            <span class="op-name">{{ __(op.operation) }}</span>
            <span v-if="op.is_last_op" class="milestone-badge" :title="__('Son Operasyon (Milestone)')">
              ★ {{ __('Son Operasyon') }}
            </span>
          </div>

          <div class="op-meta-row">
            <span v-if="op.workstation" class="op-meta">
              🏭 {{ __(op.workstation) }}
            </span>
            <span v-if="op.job_card" class="op-meta">
              🏷️ {{ op.job_card }}
            </span>
          </div>
        </div>

        <!-- Quantities: Completed / Target & Pending Badge -->
        <div class="op-qtys">
          <div class="op-completed">
            <span class="qty-num">{{ op.completed_qty || 0 }}</span>
            <span class="qty-sep">/</span>
            <span class="qty-total">{{ targetQty }}</span>
          </div>
          <div
            class="op-pending-badge"
            :class="{ 'zero-pending': (op.pending_qty || 0) <= 0 }"
          >
            {{ __('Kalan') }}: {{ op.pending_qty || 0 }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.co11n-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.75rem;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.ops-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-color, #111827);
}

.ops-count {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
  font-weight: 600;
}

.ops-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.op-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1rem;
  border: 2px solid var(--border-color, #e5e7eb);
  border-radius: 0.6rem;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--card-bg, #ffffff);
}

.op-item:hover {
  border-color: #93c5fd;
  transform: translateY(-1px);
}

.op-item.active {
  border-color: #2563eb;
  background: rgba(37, 99, 235, 0.04);
}

.op-item.completed {
  border-left: 5px solid #16a34a;
}

.op-seq-box {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 0.85rem;
  color: #374151;
  flex-shrink: 0;
}

.op-item.active .op-seq-box {
  background: #2563eb;
  color: #ffffff;
}

.op-body {
  flex: 1;
  min-width: 0;
}

.op-title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.op-name {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-color, #111827);
}

.milestone-badge {
  font-size: 0.7rem;
  font-weight: 700;
  background: #fef3c7;
  color: #b45309;
  padding: 0.15rem 0.45rem;
  border-radius: 0.35rem;
  white-space: nowrap;
}

.op-meta-row {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.25rem;
  flex-wrap: wrap;
}

.op-meta {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
}

.op-qtys {
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex-shrink: 0;
}

.op-completed {
  font-weight: 800;
  font-size: 0.95rem;
}

.qty-sep,
.qty-total {
  color: var(--text-muted, #9ca3af);
  font-weight: 500;
}

.op-pending-badge {
  font-size: 0.7rem;
  font-weight: 700;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  white-space: nowrap;
}

.op-pending-badge.zero-pending {
  background: #f3f4f6;
  color: #9ca3af;
}
</style>
