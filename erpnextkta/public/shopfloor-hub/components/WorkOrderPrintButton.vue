<script setup lang="ts">
import { ref } from "vue";
import WorkOrderPrintModal from "./WorkOrderPrintModal.vue";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    workOrder: string;
    compact?: boolean;
    disabled?: boolean;
  }>(),
  {
    compact: false,
    disabled: false,
  }
);

const showModal = ref<boolean>(false);

function handleOpen() {
  if (props.disabled || !props.workOrder) return;
  showModal.value = true;
}
</script>

<template>
  <button
    type="button"
    class="btn-wo-print"
    :class="{ 'is-compact': compact }"
    :disabled="disabled || !workOrder"
    :title="__('İş Emrini Yazdır / Şablon Seç')"
    @click="handleOpen"
  >
    <span aria-hidden="true">🖨️</span>
    <span>{{ __("Yazdır") }}</span>
  </button>

  <WorkOrderPrintModal
    :show="showModal"
    :work-order="workOrder"
    @close="showModal = false"
  />
</template>

<style scoped>
.btn-wo-print {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.75rem;
  background: var(--bg-color, #f8fafc);
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 0.45rem;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-color, #334155);
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  white-space: nowrap;
}

.btn-wo-print.is-compact {
  padding: 0.28rem 0.65rem;
  font-size: 0.75rem;
}

.btn-wo-print:hover:not(:disabled) {
  background: #e2e8f0;
  border-color: #94a3b8;
  color: #0f172a;
}

[data-theme="dark"] .btn-wo-print {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.16);
  color: var(--text-color, #f1f5f9);
}

[data-theme="dark"] .btn-wo-print:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.28);
  color: #ffffff;
}

.btn-wo-print:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
