<script setup>
const props = defineProps({
  jobCards: {
    type: Array,
    default: () => []
  },
  // v-model:selectedJobCard -> "selectedJobCard"
  selectedJobCard: {
    type: String,
    default: null
  },
  // Bilgi göstermek için seçili Job Card objesi
  selectedJobCardObj: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['update:selectedJobCard']);

function selectCard(name) {
  emit('update:selectedJobCard', name);
}

function isSelected(name) {
  return props.selectedJobCard === name;
}
</script>

<template>
  <section class="step-jobcard">
    <div class="step-jobcard__header">
      <div>
        <h2 class="step-jobcard__title">2️⃣ İş Kartı</h2>
        <p class="step-jobcard__subtitle">
          Seçilen İş Emri'ne bağlı <strong>İş Kartı</strong>lardan birini seç.
        </p>
      </div>

      <div
        v-if="jobCards.length"
        class="step-jobcard__count"
      >
        {{ jobCards.length }} iş kartı bulundu
      </div>
    </div>

    <!-- Hiç Job Card yoksa -->
    <div
      v-if="!jobCards.length"
      class="step-jobcard__empty"
    >
      Bu İş Emri'ne bağlı herhangi bir İş Kartı bulunamadı.
    </div>

    <!-- Kart grid -->
    <div
      v-else
      class="step-jobcard__grid"
    >
      <button
        v-for="jc in jobCards"
        :key="jc.name"
        type="button"
        class="step-jobcard__card"
        :class="{ 'step-jobcard__card--selected': isSelected(jc.name) }"
        @click="selectCard(jc.name)"
      >
        <div class="step-jobcard__card-header">
          <div class="step-jobcard__card-name">
            {{ jc.name }}
          </div>
          <div
            class="step-jobcard__badge"
            :class="isSelected(jc.name)
              ? 'step-jobcard__badge--selected'
              : 'step-jobcard__badge--default'"
          >
            {{ isSelected(jc.name) ? 'Seçili' : 'Seç' }}
          </div>
        </div>

        <div class="step-jobcard__card-body">
          <div v-if="jc.operation" class="step-jobcard__row">
            <span class="step-jobcard__label">Operasyon:</span>
            <span> {{ jc.operation }}</span>
          </div>
          <div v-if="jc.workstation" class="step-jobcard__row">
            <span class="step-jobcard__label">İş İstasyonu:</span>
            <span> {{ jc.workstation }}</span>
          </div>
        </div>
      </button>
    </div>
    
  </section>
</template>

<style scoped>
.step-jobcard {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.step-jobcard__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.step-jobcard__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827; /* koyu gri */
}

.step-jobcard__subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: #4b5563; /* gri */
}

.step-jobcard__count {
  font-size: 0.75rem;
  color: #6b7280;
  white-space: nowrap;
}

.step-jobcard__empty {
  padding: 0.6rem 0.75rem;
  font-size: 0.85rem;
  color: #4b5563;
  border: 1px dashed #d1d5db;
  border-radius: 0.5rem;
  background: #f9fafb;
}

/* Kart grid */
.step-jobcard__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
}

@media (min-width: 640px) {
  .step-jobcard__grid {
    grid-template-columns: 1fr 1fr;
  }
}

.step-jobcard__card {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 0.6rem 0.75rem;
  background: #ffffff;
  text-align: left;
  font-size: 0.85rem;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.step-jobcard__card:hover {
  border-color: #bfdbfe;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.15);
}

.step-jobcard__card--selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.2);
  background: #eff6ff;
}

.step-jobcard__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.step-jobcard__card-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-jobcard__badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  border: 1px solid transparent;
}

.step-jobcard__badge--default {
  border-color: #d1d5db;
  background: #f9fafb;
  color: #4b5563;
}

.step-jobcard__badge--selected {
  border-color: #3b82f6;
  background: #dbeafe;
  color: #1d4ed8;
}

.step-jobcard__card-body {
  font-size: 0.8rem;
  color: #4b5563;
}

.step-jobcard__row {
  margin-top: 0.15rem;
}

.step-jobcard__label {
  font-weight: 500;
  color: #374151;
}

/* Summary */
.step-jobcard__summary {
  margin-top: 0.25rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  font-size: 0.8rem;
  color: #1e3a8a;
}

.step-jobcard__summary-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.step-jobcard__summary-rows {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
}

.step-jobcard__summary-row {
  display: flex;
  gap: 0.25rem;
}
</style>