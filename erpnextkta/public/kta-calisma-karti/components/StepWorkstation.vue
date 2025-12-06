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
      <div>
        <h2 class="step-ws__title">3️⃣ İş İstasyonu</h2>
        <p class="step-ws__subtitle">
          Bu Çalışma Kartı'nın üretileceği <strong>iş istasyonunu</strong> belirle.
          Job Card üzerinde zaten tanımlı bir istasyon varsa otomatik olarak doldurulur,
          istersen değiştirebilirsin.
        </p>
      </div>

      <div
        v-if="hasJobCardWorkstation"
        class="step-ws__hint"
      >
        Job Card istasyonu: <strong>{{ jobCard.workstation }}</strong>
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
      <input
        type="text"
        class="step-ws__input"
        :class="{ 'step-ws__input--highlight': autoFilled }"
        :value="workstation || ''"
        placeholder="Örn: IST-01"
        @input="onInput"
      />

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
  gap: 0.75rem;
}

.step-ws__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.step-ws__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
}

.step-ws__subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: #4b5563;
}

.step-ws__hint {
  font-size: 0.75rem;
  color: #1d4ed8;
  background: #eff6ff;
  border-radius: 999px;
  padding: 0.15rem 0.6rem;
  border: 1px solid #bfdbfe;
  white-space: nowrap;
}

.step-ws__info {
  font-size: 0.8rem;
  color: #374151;
  background: #f9fafb;
  border-radius: 0.5rem;
  border: 1px dashed #d1d5db;
  padding: 0.4rem 0.6rem;
}

.step-ws__input-row {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

@media (min-width: 640px) {
  .step-ws__input-row {
    flex-direction: row;
    align-items: center;
  }
}

.step-ws__input {
  flex: 1 1 auto;
  font-size: 0.9rem;
  padding: 0.45rem 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid #d1d5db;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.step-ws__input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15);
}

.step-ws__input--highlight {
  border-color: #16a34a;
  box-shadow: 0 0 0 1px rgba(22, 163, 74, 0.2);
  background: #f0fdf4;
}

.step-ws__btn-apply {
  flex: 0 0 auto;
  font-size: 0.8rem;
  padding: 0.4rem 0.7rem;
  border-radius: 0.5rem;
  border: 1px solid #d1d5db;
  background: #f3f4f6;
  color: #374151;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.step-ws__btn-apply:hover {
  background: #e5e7eb;
  border-color: #9ca3af;
}

.step-ws__help {
  margin: 0;
  font-size: 0.75rem;
  color: #6b7280;
}
</style>