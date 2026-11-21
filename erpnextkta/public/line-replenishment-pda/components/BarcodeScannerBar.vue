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
  feedbackType?: "success" | "error" | "";
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
    if (inputRef.value) {
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
  border-radius: 8px;
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
  font-size: 1.05rem;
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
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
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
  color: #64748b;
  font-size: 1.1rem;
  cursor: pointer;
}

.btn-clear:hover {
  background-color: #f1f5f9;
  color: #0f172a;
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
</style>
