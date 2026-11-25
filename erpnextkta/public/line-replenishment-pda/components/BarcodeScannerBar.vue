<template>
  <div class="barcode-scan-card">
    <label for="pda-barcode-input" class="scan-label">
      <span class="scan-icon">🔍</span>
      {{ __("Barkod Okut (PDA Scanner)") }}
    </label>

    <div class="barcode-input-wrapper">
      <input
        id="pda-barcode-input"
        ref="inputRef"
        v-model="barcodeVal"
        type="text"
        class="barcode-input"
        :placeholder="__('Ürün / SUT / Parti Barkodu Okutun...')"
        :disabled="disabled"
        autocomplete="off"
        autocapitalize="off"
        autocorrect="off"
        spellcheck="false"
        @keydown.enter.prevent="onEnter"
      />
      <button
        v-if="barcodeVal"
        type="button"
        class="btn-clear"
        :title="__('Temizle')"
        @click="clearInput"
      >
        ✕
      </button>
    </div>

    <div
      v-if="feedbackMsg"
      data-testid="scan-feedback"
      :class="['scan-feedback', `feedback-${feedbackType}`]"
    >
      {{ feedbackMsg }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

interface Props {
  disabled?: boolean;
  feedbackMsg?: string;
  feedbackType?: "success" | "error" | "info" | "";
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  feedbackMsg: "",
  feedbackType: "",
});

const emit = defineEmits<{
  (e: "scan", barcode: string): void;
  (e: "clear"): void;
}>();

const barcodeVal = ref<string>("");
const inputRef = ref<HTMLInputElement | null>(null);

function onEnter() {
  const code = barcodeVal.value.trim();
  if (code) {
    barcodeVal.value = "";
    emit("scan", code);
  }
}

function clearInput() {
  barcodeVal.value = "";
  emit("clear");
  focusInput();
}

function focusInput(clear = false) {
  if (clear) {
    barcodeVal.value = "";
  }
  nextTick(() => {
    if (inputRef.value && !props.disabled) {
      inputRef.value.focus();
    }
  });
}

defineExpose({
  focusInput,
  clearInput,
});

onMounted(() => {
  focusInput();
});
</script>

<style scoped>
.barcode-scan-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 10px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.scan-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-color, #1e293b);
  margin-bottom: 6px;
}

.scan-icon {
  font-size: 0.95rem;
}

.barcode-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.barcode-input {
  width: 100%;
  min-height: 48px;
  padding: 10px 42px 10px 14px;
  font-size: 1.02rem;
  font-family: monospace, var(--font-family, sans-serif);
  font-weight: 600;
  border: 2px solid var(--border-color, #94a3b8);
  border-radius: 6px;
  background-color: var(--control-bg, #ffffff);
  color: var(--text-color, #0f172a);
  transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
}

.barcode-input:focus {
  outline: none;
  border-color: var(--pda-primary, #2563eb);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
}

[data-theme="dark"] .barcode-input {
  background-color: var(--bg-color, #0f172a);
  color: var(--text-color, #f8fafc);
  border-color: var(--border-color, rgba(255, 255, 255, 0.22));
}

.btn-clear {
  position: absolute;
  right: 6px;
  min-width: 36px;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--text-muted, #64748b);
  font-size: 1.1rem;
  cursor: pointer;
}

.btn-clear:hover {
  background-color: var(--pda-surface-alt, #f1f5f9);
  color: var(--text-color, #0f172a);
}

.scan-feedback {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  animation: fadeIn 0.2s ease-in;
}

.feedback-success {
  background-color: #dcfce7;
  border: 1px solid #86efac;
  color: #166534;
}

.feedback-error {
  background-color: #fee2e2;
  border: 1px solid #fca5a5;
  color: #991b1b;
}

.feedback-info {
  background-color: #e0f2fe;
  border: 1px solid #7dd3fc;
  color: #075985;
}

[data-theme="dark"] .feedback-success {
  background-color: rgba(34, 197, 94, 0.18);
  border-color: rgba(74, 222, 128, 0.45);
  color: #86efac;
}

[data-theme="dark"] .feedback-error {
  background-color: rgba(239, 68, 68, 0.2);
  border-color: rgba(248, 113, 113, 0.45);
  color: #fecaca;
}

[data-theme="dark"] .feedback-info {
  background-color: rgba(56, 189, 248, 0.2);
  border-color: rgba(125, 211, 252, 0.45);
  color: #bae6fd;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (min-width: 768px) {
  .barcode-scan-card {
    padding: 10px;
  }

  .barcode-input {
    min-height: 40px;
    padding: 8px 38px 8px 12px;
    font-size: 0.95rem;
  }
}
</style>
