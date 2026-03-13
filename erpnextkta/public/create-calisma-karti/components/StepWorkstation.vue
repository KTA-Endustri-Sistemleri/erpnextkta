<script setup>
import { computed } from 'vue';

const props = defineProps({
  jobCard: {
    type: Object,
    default: null
  },
  // v-model:workstation
  workstation: {
    type: String,
    default: null
  },
  // Job Card'dan auto-fill olduğunda kısa süreli highlight için
  autoFilled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:workstation']);

function onInput(event) {
  emit('update:workstation', event.target.value || null);
}

const hasJobCardWorkstation = computed(() => {
  return !!(props.jobCard && props.jobCard.workstation);
});

function useJobCardWorkstation() {
  if (hasJobCardWorkstation.value) {
    emit('update:workstation', props.jobCard.workstation);
  }
}
</script>

<template>
  <section class="step-ws">
    <div class="step-ws__header">
      <h2 class="step-ws__title">İş İstasyonu</h2>
      <p class="step-ws__subtitle">
        Bu Çalışma Kartı'nın üretileceği <strong>iş istasyonunu</strong> belirle.
        Job Card üzerinde zaten tanımlı bir istasyon varsa otomatik olarak doldurulur.
      </p>

      <div
        v-if="hasJobCardWorkstation"
        class="step-ws__badge"
      >
        <span class="label">Önerilen:</span>
        <span class="value">{{ jobCard.workstation }}</span>
      </div>
    </div>

    <!-- Info / uyarı satırı -->
    <div
      v-if="hasJobCardWorkstation && !workstation"
      class="step-ws__info"
    >
      Job Card üzerinde tanımlı istasyon <strong>{{ jobCard.workstation }}</strong>.
      İstersen aşağıdaki buton ile bu değeri kullanabilirsin.
    </div>

    <!-- Input alanı -->
    <div class="step-ws__input-row">
      <div class="step-ws__input-wrapper">
        <input
          type="text"
          class="step-ws__input"
          :class="{ 'step-ws__input--highlight': autoFilled }"
          :value="workstation || ''"
          placeholder="Örn: IST-01"
          @input="onInput"
        />
        <div v-if="autoFilled" class="step-ws__success-dot"></div>
      </div>

      <button
        v-if="hasJobCardWorkstation"
        type="button"
        class="step-ws__btn-apply"
        @click="useJobCardWorkstation"
      >
        Job Card istasyonunu kullan
      </button>
    </div>

    <p class="step-ws__help">
      Bu alan <code>İş İstasyonu</code> alanına yazılacak. Zorunlu bir alandır.
    </p>
  </section>
</template>

<style scoped>
.step-ws {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.step-ws__header {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.step-ws__title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--ck-text);
}

.step-ws__subtitle {
  margin: 0;
  font-size: 0.85rem;
  color: var(--ck-text-muted);
  line-height: 1.5;
}

.step-ws__badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  align-self: flex-start;
  font-size: 0.75rem;
  background: var(--ck-ghost-bg);
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  border: 1px solid var(--ck-accent);
  margin-top: 0.25rem;
}

.step-ws__badge .label {
  color: var(--ck-text-muted);
}

.step-ws__badge .value {
  color: var(--ck-accent);
  font-weight: 600;
}

.step-ws__info {
  font-size: 0.8rem;
  color: var(--ck-text);
  background: var(--ck-ghost-bg);
  border-radius: 0.5rem;
  border: 1px dashed var(--ck-border);
  padding: 0.6rem 0.8rem;
  line-height: 1.4;
}

.step-ws__input-row {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

@media (min-width: 640px) {
  .step-ws__input-row {
    flex-direction: row;
    align-items: stretch;
  }
}

.step-ws__input-wrapper {
  position: relative;
  flex: 1;
}

.step-ws__input {
  width: 100%;
  font-size: 0.95rem;
  padding: 0.6rem 0.8rem;
  border-radius: 0.5rem;
  border: 1px solid var(--ck-border);
  background: var(--ck-input-bg);
  color: var(--ck-input-text);
  outline: none;
  transition: all 0.2s ease;
}

.step-ws__input:focus {
  border-color: var(--ck-accent);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.step-ws__input--highlight {
  border-color: var(--ck-success);
  background: rgba(34, 197, 94, 0.05);
}

.step-ws__success-dot {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  width: 8px;
  height: 8px;
  background: var(--ck-success);
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.15);
}

.step-ws__btn-apply {
  flex: 0 0 auto;
  font-size: 0.85rem;
  font-weight: 600;
  padding: 0.6rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid var(--ck-accent);
  background: var(--ck-ghost-bg);
  color: var(--ck-accent);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.step-ws__btn-apply:hover {
  background: var(--ck-accent);
  color: #ffffff;
}

.step-ws__help {
  margin: 0;
  font-size: 0.75rem;
  color: var(--ck-text-muted);
}
</style>