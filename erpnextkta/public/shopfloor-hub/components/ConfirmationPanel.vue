<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { OperationInfo } from '../types';

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  selectedOperation: OperationInfo | null;
  targetQty: number;
  modelValue: number;
  isFinalConfirmation: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: number): void;
  (e: 'update:isFinalConfirmation', val: boolean): void;
  (e: 'submit'): void;
}>();

const userOverridden = ref<boolean>(false);

const currentConfirmedQty = computed<number>(() => {
  return Number(props.selectedOperation?.completed_qty) || 0;
});

const currentOpenQty = computed<number>(() => {
  return Number(props.selectedOperation?.pending_qty) || 0;
});

watch(
  () => props.selectedOperation,
  () => {
    userOverridden.value = false;
  }
);

watch(
  () => props.modelValue,
  (newVal) => {
    if (userOverridden.value) return;
    const openQty = currentOpenQty.value;
    if (openQty > 0) {
      if (newVal >= openQty && !props.isFinalConfirmation) {
        emit('update:isFinalConfirmation', true);
      } else if (newVal < openQty && props.isFinalConfirmation) {
        emit('update:isFinalConfirmation', false);
      }
    }
  }
);

function setFullPending() {
  const pending = Math.max(0, currentOpenQty.value);
  emit('update:modelValue', pending);
  emit('update:isFinalConfirmation', true);
  userOverridden.value = false;
}

function handleInput(e: Event) {
  const target = e.target as HTMLInputElement | null;
  const val = Number(target?.value) || 0;
  emit('update:modelValue', val);
}

function toggleFinalConfirmation() {
  if (props.submitting || !props.selectedOperation) return;
  userOverridden.value = true;
  emit('update:isFinalConfirmation', !props.isFinalConfirmation);
}
</script>

<template>
  <div class="co11n-card action-card">
    <h3 class="section-title">{{ __('Teyit Girişi') }}</h3>

    <!-- Selected Operation Summary -->
    <div v-if="selectedOperation" class="selected-op-summary">
      <div class="summary-label">{{ __('Seçili Operasyon') }}</div>
      <div class="summary-name">{{ __(selectedOperation.operation) }}</div>
      <div v-if="selectedOperation.is_last_op" class="summary-milestone-note">
        {{ __('Bu son operasyondur: Teyit verildiğinde mamul girişi yapılacaktır.') }}
      </div>
    </div>

    <!-- Quantity Indicators -->
    <div class="qty-indicators-grid">
      <div class="indicator-item">
        <span class="ind-label">{{ __('Hedef Miktar') }}</span>
        <span class="ind-value">{{ targetQty }}</span>
      </div>
      <div class="indicator-item">
        <span class="ind-label">{{ __('Teyit Edilen') }}</span>
        <span class="ind-value text-success">{{ currentConfirmedQty }}</span>
      </div>
      <div class="indicator-item">
        <span class="ind-label">{{ __('Açık Bakiye') }}</span>
        <span class="ind-value text-accent">{{ currentOpenQty }}</span>
      </div>
    </div>

    <!-- Yield Qty Input Row with Overflow Protection -->
    <div class="form-group">
      <label class="form-label" for="yield-input">
        {{ __('Sağlam Miktar (Yield Qty)') }}
      </label>
      <div class="yield-input-row">
        <input
          id="yield-input"
          :value="modelValue"
          type="number"
          min="0"
          step="any"
          class="yield-input"
          :disabled="submitting || !selectedOperation"
          @input="handleInput"
        />
        <button
          type="button"
          class="btn-quick-fill"
          :disabled="submitting || !selectedOperation || currentOpenQty <= 0"
          :title="__('Açık bakiyenin tamamını aktar')"
          @click="setFullPending"
        >
          ⚡ {{ __('Kalanın Tümü') }}
        </button>
      </div>
    </div>

    <!-- Modern Checkbox / Option Card (Final Confirmation) -->
    <div
      class="final-conf-card"
      :class="{
        'is-active': isFinalConfirmation,
        'is-disabled': submitting || !selectedOperation,
      }"
      @click="toggleFinalConfirmation"
    >
      <div class="custom-checkbox" :class="{ checked: isFinalConfirmation }">
        <svg
          v-if="isFinalConfirmation"
          class="check-icon"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fill-rule="evenodd"
            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
            clip-rule="evenodd"
          />
        </svg>
      </div>
      <div class="checkbox-text-group">
        <strong class="checkbox-title">{{ __('Son Teyit (Kalanı Kapat)') }}</strong>
        <span class="checkbox-desc">
          {{ __('Hedef adede tam ulaşılmasa bile açık bakiyeyi ve İş Kartını kapatır.') }}
        </span>
      </div>
    </div>

    <!-- Confirm Submit Button -->
    <button
      type="button"
      class="btn-submit"
      :disabled="submitting || !selectedOperation || !modelValue || modelValue <= 0"
      @click="emit('submit')"
    >
      <span v-if="submitting" class="spinner" />
      <span v-else>🚀 {{ __('Teyit Et') }} ({{ modelValue }} {{ __('Adet') }})</span>
    </button>
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

.action-card {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  border-top: 4px solid #2563eb;
}

.section-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-color, #111827);
}

.selected-op-summary {
  padding: 0.75rem 1rem;
  background: rgba(37, 99, 235, 0.05);
  border-radius: 0.5rem;
  border-left: 3px solid #2563eb;
}

.summary-label {
  font-size: 0.7rem;
  font-weight: 700;
  color: #2563eb;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.summary-name {
  font-size: 1.05rem;
  font-weight: 800;
  margin-top: 0.2rem;
  color: var(--text-color, #111827);
}

.summary-milestone-note {
  margin-top: 0.35rem;
  font-size: 0.75rem;
  color: #b45309;
  font-weight: 500;
}

.qty-indicators-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.indicator-item {
  padding: 0.65rem;
  background: var(--bg-color, #f9fafb);
  border-radius: 0.5rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  border: 1px solid var(--border-color, #f1f5f9);
}

.ind-label {
  font-size: 0.7rem;
  color: var(--text-muted, #6b7280);
}

.ind-value {
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--text-color, #111827);
}

.text-success {
  color: #16a34a;
}

.text-accent {
  color: #2563eb;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-color, #111827);
}

/* Yield Input Row with Defensive Overflow Handling */
.yield-input-row {
  width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: stretch;
  gap: 0.5rem;
}

.yield-input {
  min-width: 0;
  flex: 1;
  height: 52px;
  padding: 0 1rem;
  font-size: 1.5rem;
  font-weight: 800;
  border: 2px solid var(--border-color, #d1d5db);
  border-radius: 0.6rem;
  background: var(--card-bg, #ffffff);
  color: var(--text-color, #111827);
  outline: none;
  text-align: center;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.yield-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.btn-quick-fill {
  flex-shrink: 0;
  white-space: nowrap;
  padding: 0 1.15rem;
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 0.6rem;
  font-size: 0.85rem;
  font-weight: 700;
  color: #1e293b;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-quick-fill:hover:not(:disabled) {
  background: #e2e8f0;
  border-color: #94a3b8;
}

.btn-quick-fill:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Modern Checkbox / Option Card */
.final-conf-card {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1.5px solid var(--border-color, #e5e7eb);
  border-radius: 0.6rem;
  background: var(--bg-color, #f9fafb);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.final-conf-card:hover:not(.is-disabled) {
  border-color: #93c5fd;
  background: rgba(37, 99, 235, 0.02);
}

.final-conf-card.is-active {
  background: rgba(37, 99, 235, 0.05);
  border-color: #2563eb;
}

.final-conf-card.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.custom-checkbox {
  width: 20px;
  height: 20px;
  min-width: 20px;
  border-radius: 0.35rem;
  border: 2px solid var(--border-color, #9ca3af);
  background: var(--card-bg, #ffffff);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 0.1rem;
  transition: all 0.2s ease;
}

.custom-checkbox.checked {
  background: #2563eb;
  border-color: #2563eb;
}

.check-icon {
  width: 14px;
  height: 14px;
  color: #ffffff;
}

.checkbox-text-group {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.checkbox-title {
  font-size: 0.85rem;
  color: var(--text-color, #111827);
}

.checkbox-desc {
  font-size: 0.75rem;
  color: var(--text-muted, #6b7280);
  line-height: 1.35;
}

/* Submit Button */
.btn-submit {
  height: 58px;
  background: #16a34a;
  color: #ffffff;
  border: none;
  border-radius: 0.6rem;
  font-size: 1.15rem;
  font-weight: 800;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: background 0.2s, transform 0.1s;
  box-shadow: 0 2px 6px rgba(22, 163, 74, 0.3);
}

.btn-submit:hover:not(:disabled) {
  background: #15803d;
  transform: translateY(-1px);
}

.btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.spinner {
  width: 22px;
  height: 22px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #ffffff;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
