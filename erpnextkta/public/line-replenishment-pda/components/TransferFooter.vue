<template>
  <div class="pda-footer-sticky">
    <div class="footer-summary">
      <span class="summary-text">
        {{ __("{0} / {1} Kalem Toplandı", [pickedCount, totalCount]) }}
      </span>
      <span v-if="!canComplete && totalCount > 0" class="summary-hint">
        {{ __("Tüm kalemler toplanmalıdır") }}
      </span>
    </div>

    <button
      type="button"
      class="btn-complete-transfer"
      :disabled="!canComplete || loading"
      @click="emit('complete')"
    >
      <span v-if="loading" class="spinner">⏳</span>
      <span v-else class="btn-icon">📦</span>
      <span class="btn-text">{{ __("Transferi Tamamla") }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
const __ = (...args: any[]) => (window as any).__(...args);

interface Props {
  canComplete: boolean;
  pickedCount: number;
  totalCount: number;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
});

const emit = defineEmits<{
  (e: "complete"): void;
}>();
</script>

<style scoped>
.pda-footer-sticky {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: var(--card-bg, #ffffff);
  border-top: 2px solid var(--border-color, #cbd5e1);
  padding: 10px 14px;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 40;
}

.footer-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
  font-weight: 600;
  color: #334155;
}

[data-theme="dark"] .footer-summary {
  color: var(--text-color, #e2e8f0);
}

.summary-hint {
  font-size: 0.78rem;
  color: #d97706;
}

[data-theme="dark"] .summary-hint {
  color: #fbbf24;
}

.btn-complete-transfer {
  width: 100%;
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background-color: #16a34a;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 1.05rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(22, 163, 74, 0.3);
  transition: all 0.15s ease-in-out;
}

.btn-complete-transfer:hover:not(:disabled) {
  background-color: #15803d;
}

.btn-complete-transfer:active:not(:disabled) {
  transform: translateY(1px);
}

.btn-complete-transfer:disabled {
  background-color: #94a3b8;
  box-shadow: none;
  cursor: not-allowed;
  opacity: 0.65;
}

[data-theme="dark"] .btn-complete-transfer:disabled {
  background-color: #475569;
  color: #cbd5e1;
}

.btn-icon {
  font-size: 1.25rem;
}

.spinner {
  display: inline-block;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}
</style>
