<script setup>
import { ref, onMounted, watch } from 'vue';

const props = defineProps({
  barcode: {
    type: String,
    default: ''
  },
  jobCard: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:barcode', 'submit']);

const inputRef = ref(null);

// Input'u otomatik fokusla
onMounted(() => {
  focusInput();
});

// Job Card reset olursa tekrar fokus
watch(
  () => props.jobCard,
  (val, oldVal) => {
    if (!val && oldVal) focusInput();
  }
);

function focusInput() {
  if (inputRef.value) {
    inputRef.value.focus();
    inputRef.value.select();
  }
}

function onInput(event) {
  emit('update:barcode', event.target.value || '');
}

function onKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    emit('submit');
  }
}
</script>

<template>
  <section class="step-wo">
    <div>
      <h2 class="step-wo__title">İş Kartı Barkodu</h2>
      <p class="step-wo__subtitle">
        Barkod okuyucu ile <strong>İş Kartı barkodunu</strong> okut
        veya Job Card numarasını gir. Okuyucu genelde Enter ile bittiği için
        ek işlem yapman gerekmez.
      </p>
    </div>

    <!-- Tek alan: İş Kartı Barkod / Numara giriş alanı -->
    <div class="step-wo__input-wrapper">
      <input
        ref="inputRef"
        type="text"
        class="step-wo__input"
        :readonly="loading"
        :value="barcode"
        placeholder="İş Kartı barkodunu okutun veya JC-00045 girin..."
        autocomplete="off"
        @input="onInput"
        @keydown="onKeydown"
      />
      <div class="step-wo__input-icon">
        <div class="step-wo__scan-line" />
      </div>
    </div>

    <!-- Loading sırasında mini açıklama -->
    <div v-if="loading" class="step-wo__loading-text">
      İş Kartı doğrulanıyor...
    </div>

    <!-- Seçili İş Kartı Özeti -->
    <Transition name="fade-step">
      <div v-if="jobCard && !loading" class="step-wo__summary">
        <div class="step-wo__summary-header">
          <span class="step-wo__summary-icon">✓</span>
          <span class="step-wo__summary-title">Seçili İş Kartı Bilgisi</span>
        </div>
        <div class="step-wo__summary-body">
          <div class="step-wo__summary-row">
            <span class="label">İş Kartı:</span>
            <span class="value">{{ jobCard.name }}</span>
          </div>
          <div v-if="jobCard.work_order" class="step-wo__summary-row">
            <span class="label">İş Emri:</span>
            <span class="value">{{ jobCard.work_order }}</span>
          </div>
          <div v-if="jobCard.production_item" class="step-wo__summary-row">
            <span class="label">Ürün:</span>
            <span class="value">{{ jobCard.production_item }}</span>
          </div>
        </div>
      </div>
    </Transition>
  </section>
</template>

<style scoped>
.step-wo {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.step-wo__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--ck-text);
}

.step-wo__subtitle {
  margin-top: 0.25rem;
  font-size: 0.85rem;
  color: var(--ck-text-muted);
}

/* Input alanı */
.step-wo__input-wrapper {
  position: relative;
  flex: 1 1 auto;
}

.step-wo__input {
  width: 100%;
  font-size: 1rem;
  padding: 0.55rem 0.7rem;
  padding-right: 2.4rem;
  border-radius: 0.5rem;
  border: 1px solid var(--ck-border);
  background: var(--ck-input-bg);
  color: var(--ck-input-text);
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.step-wo__input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.18);
}

.step-wo__input[readonly] {
  background: var(--ck-ghost-bg);
}

/* Scanner ikonu */
.step-wo__input-icon {
  position: absolute;
  right: 0.55rem;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid #9ca3af;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.step-wo__scan-line {
  width: 80%;
  height: 2px;
  background: #22c55e;
}

.step-wo__loading-text {
  font-size: 0.8rem;
  color: var(--ck-text-muted);
}

/* Seçili Özet Paneli */
.step-wo__summary {
  margin-top: 0.5rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid var(--ck-accent);
  background: var(--ck-ghost-bg) !important;
  color: var(--ck-text) !important;
}

.step-wo__summary-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.step-wo__summary-icon {
  width: 18px;
  height: 18px;
  background: var(--ck-success);
  color: white;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: bold;
}

.step-wo__summary-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ck-text);
}

.step-wo__summary-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.step-wo__summary-row {
  display: flex;
  font-size: 0.8rem;
  gap: 0.5rem;
}

.step-wo__summary-row .label {
  font-weight: 500;
  color: var(--ck-text-muted);
  min-width: 70px;
}

.step-wo__summary-row .value {
  color: var(--ck-text);
  font-weight: 600;
}
</style>