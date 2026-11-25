<template>
  <div class="pda-footer-fixed" data-testid="transfer-footer">
    <div class="pda-footer-inner">
      <div class="footer-summary">
        <span class="summary-text">
          {{ __("{0} / {1} Tamamlandı", [completedCount, totalCount]) }}
          <span v-if="skippedCount > 0" class="skipped-hint">
            {{ __("({0} Atlandı)", [skippedCount]) }}
          </span>
        </span>
        <span v-if="pendingCount > 0" class="summary-hint">
          {{ __("{0} koli bekliyor", [pendingCount]) }}
        </span>
      </div>

      <button
        type="button"
        data-testid="complete-transfer-btn"
        :class="[
          'btn-complete-transfer',
          { 'btn-cancel-all-skipped': allSkipped && pendingCount === 0 },
        ]"
        :disabled="pendingCount > 0 || !canComplete || loading"
        @click="emit('complete')"
      >
        <span v-if="loading" class="spinner">⏳</span>
        <span v-else class="btn-icon">{{ allSkipped ? "⊘" : "📦" }}</span>
        <span class="btn-text">{{ buttonLabel }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

interface Props {
  canComplete: boolean;
  pickedCount: number;
  skippedCount?: number;
  pendingCount?: number;
  totalCount: number;
  allSkipped?: boolean;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  skippedCount: 0,
  pendingCount: 0,
  allSkipped: false,
  loading: false,
});

const emit = defineEmits<{
  (e: "complete"): void;
}>();

const completedCount = computed(() => props.pickedCount + props.skippedCount);

const buttonLabel = computed(() =>
  props.allSkipped
    ? __("Emri İptal Et (Tümü Atlandı)")
    : __("Transferi Tamamla"),
);
</script>

<style scoped>
.pda-footer-fixed {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 38;
  background-color: var(--card-bg, #ffffff);
  border-top: 2px solid var(--border-color, #cbd5e1);
  padding: 10px 14px calc(10px + env(safe-area-inset-bottom, 0px));
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.08);
}

.pda-footer-inner {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.footer-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-color, #334155);
}

.skipped-hint {
  color: #d97706;
  margin-left: 4px;
}

[data-theme="dark"] .skipped-hint {
  color: #fbbf24;
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
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background-color: var(--pda-success, #16a34a);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(22, 163, 74, 0.28);
  transition: all 0.15s ease-in-out;
}

.btn-complete-transfer.btn-cancel-all-skipped {
  background-color: #d97706;
  box-shadow: 0 2px 4px rgba(217, 119, 6, 0.3);
}

.btn-complete-transfer:hover:not(:disabled) {
  filter: brightness(0.94);
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
  font-size: 1.15rem;
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

@media (min-width: 768px) {
  .pda-footer-inner {
    max-width: 960px;
    margin: 0 auto;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }

  .footer-summary {
    justify-content: flex-start;
    gap: 12px;
  }

  .btn-complete-transfer {
    width: auto;
    min-width: 240px;
    min-height: 44px;
    padding: 8px 22px;
    font-size: 0.95rem;
  }
}
</style>
