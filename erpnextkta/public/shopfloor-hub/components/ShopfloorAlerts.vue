<script setup lang="ts">
import type { ConfirmationResponse } from "../types";

const __ = (...args: any[]) => (window as any).__(...args);

defineProps<{
  errorMessage: string | null;
  successResult: ConfirmationResponse | null;
}>();

const emit = defineEmits<{
  (e: "clear-error"): void;
  (e: "clear-success"): void;
}>();
</script>

<template>
  <div v-if="errorMessage" class="co11n-alert alert-danger" role="alert">
    <div class="alert-content">
      <span class="alert-icon" aria-hidden="true">⚠️</span>
      <div>{{ errorMessage }}</div>
    </div>
    <button
      type="button"
      class="alert-close"
      :title="__('Kapat')"
      @click="emit('clear-error')"
    >
      ✕
    </button>
  </div>

  <div v-if="successResult" class="co11n-alert alert-success" role="status">
    <div class="alert-content">
      <span class="alert-icon" aria-hidden="true">✓</span>
      <div>
        <strong class="alert-title">{{ __("Teyit Başarıyla Tamamlandı") }}</strong>
        <div class="alert-links">
          <a
            :href="`/app/kta-production-confirmation/${successResult.confirmation}`"
            target="_blank"
            class="doc-link"
          >
            📄 {{ __("Teyit Belgesi") }}: {{ successResult.confirmation }}
          </a>
          <template
            v-if="successResult.stock_entries && successResult.stock_entries.length > 0"
          >
            <a
              v-for="se in successResult.stock_entries"
              :key="se.name"
              :href="`/app/stock-entry/${se.name}`"
              target="_blank"
              class="doc-link"
            >
              <span v-if="se.type === 'manufacture'">📦</span>
              <span v-else>⚙️</span>
              {{
                se.label ||
                (se.type === "manufacture" ? __("Üretim Fişi") : __("Tüketim Fişi"))
              }}: {{ se.name }}
            </a>
          </template>
          <a
            v-else-if="successResult.stock_entry"
            :href="`/app/stock-entry/${successResult.stock_entry}`"
            target="_blank"
            class="doc-link"
          >
            📦 {{ __("Stok Fişi") }}: {{ successResult.stock_entry }}
          </a>
        </div>
      </div>
    </div>
    <button
      type="button"
      class="alert-close"
      :title="__('Kapat')"
      @click="emit('clear-success')"
    >
      ✕
    </button>
  </div>
</template>

<style scoped>
.co11n-alert {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.85rem 1.15rem;
  border-radius: 0.6rem;
}

.alert-danger {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

[data-theme="dark"] .alert-danger {
  background: rgba(239, 68, 68, 0.16);
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}

.alert-success {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

[data-theme="dark"] .alert-success {
  background: rgba(34, 197, 94, 0.14);
  border-color: rgba(74, 222, 128, 0.35);
  color: #86efac;
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.alert-icon {
  font-size: 1.25rem;
}

.alert-title {
  font-size: 0.9rem;
  display: block;
}

.alert-links {
  display: flex;
  gap: 0.85rem;
  margin-top: 0.2rem;
  flex-wrap: wrap;
}

.doc-link {
  color: #15803d;
  font-weight: 600;
  text-decoration: underline;
  font-size: 0.82rem;
}

[data-theme="dark"] .doc-link {
  color: #4ade80;
}

.alert-close {
  background: none;
  border: none;
  font-size: 1.15rem;
  cursor: pointer;
  color: inherit;
  opacity: 0.65;
  transition: opacity 0.15s;
}

.alert-close:hover {
  opacity: 1;
}
</style>
