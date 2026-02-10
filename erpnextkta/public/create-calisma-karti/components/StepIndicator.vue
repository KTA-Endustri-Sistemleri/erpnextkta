<!-- StepIndicator.vue -->
<script setup>
import { computed } from 'vue';

const props = defineProps({
  currentStep: {
    type: Number,
    required: true,
  },
  steps: {
    type: Array,
    required: true,
    // e.g. [{ id: 1, label: 'İş Emri', description: '...' }, ...]
  },
});

const currentStepObj = computed(() =>
  props.steps.find((s) => s.id === props.currentStep) || null
);

const totalSteps = computed(() => props.steps.length);
</script>

<template>
  <nav class="step-indicator">
    <!-- Mobile compact görünüm -->
    <div class="step-compact">
      <div class="step-compact__row">
        <span class="step-compact__stage">
          Aşama {{ currentStep }} / {{ totalSteps }}
        </span>
        <span v-if="currentStepObj" class="step-compact__label">
          · {{ currentStepObj.label }}
        </span>
      </div>

      <!-- Çok segmentli mobil progress bar -->
      <div class="step-compact__segments">
        <div
          v-for="step in steps"
          :key="'mobile-' + step.id"
          class="step-compact__segment"
          :class="{
            'segment--done': step.id < currentStep,
            'segment--active': step.id === currentStep,
            'segment--pending': step.id > currentStep
          }"
        />
      </div>
    </div>

    <!-- 🔹 Desktop / geniş ekran tam step listesi -->
    <ol class="step-list">
      <li
        v-for="step in steps"
        :key="step.id"
        class="step-item"
      >
        <div class="step-content">
          <div
            class="step-circle"
            :class="{
              'step-circle--done': step.id < currentStep,
              'step-circle--active': step.id === currentStep
            }"
          >
            <span class="step-circle__text">
              {{ step.id < currentStep ? '✓' : step.id }}
            </span>
          </div>
          <div class="step-label">
            <div class="step-label__title">{{ step.label }}</div>
            <div v-if="step.description" class="step-label__desc">
              {{ step.description }}
            </div>
          </div>
        </div>

        <!-- Connector line (except last) -->
        <div
          v-if="step.id !== steps.length"
          class="step-connector"
          :class="{
            'step-connector--active': step.id < currentStep
          }"
        />
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.step-indicator {
  width: 100%;
  margin-bottom: 0.75rem;
}

/* ---------- Desktop step list (mevcut tasarım) ---------- */

.step-list {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

.step-item {
  display: flex;
  align-items: center;
  flex: 1 1 0;
  min-width: 0; /* prevent overflow */
}

.step-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.step-circle {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 2px solid #d1d5db; /* gray-300 */
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f9fafb; /* gray-50 */
  flex-shrink: 0;
  transition: all 0.16s ease-out;
}

.step-circle__text {
  font-size: 0.75rem;
  font-weight: 600;
  color: #6b7280; /* gray-500 */
}

.step-circle--active {
  border-color: #2563eb; /* blue-600 */
  background: #2563eb;
}

.step-circle--active .step-circle__text {
  color: #ffffff;
}

.step-circle--done {
  border-color: #16a34a; /* green-600 */
  background: #16a34a;
}

.step-circle--done .step-circle__text {
  color: #ffffff;
}

.step-label {
  min-width: 0;
}

.step-label__title {
  font-size: 0.8rem;
  font-weight: 600;
  color: #111827; /* gray-900 */
  white-space: nowrap;
}

.step-label__desc {
  font-size: 0.7rem;
  color: #6b7280; /* gray-500 */
  white-space: nowrap;
}

.step-connector {
  flex: 1 1 0;
  height: 2px;
  background: #e5e7eb; /* gray-200 */
  margin-left: 0.5rem;
  margin-right: 0.5rem;
  border-radius: 999px;
  transition: background 0.16s ease-out;
}

.step-connector--active {
  background: #2563eb; /* blue-600 */
}

/* ---------- Mobile compact görünüm ---------- */

.step-compact {
  display: none; /* desktop'ta gizli */
}

.step-compact__row {
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
  font-size: 0.78rem;
  color: #4b5563; /* gray-600 */
  margin-bottom: 0.25rem;
}

.step-compact__stage {
  font-weight: 600;
  color: #111827; /* gray-900 */
}

.step-compact__label {
  font-size: 0.75rem;
  color: #6b7280;
}

/* MOBILE multi-segment progress bar */
.step-compact__segments {
  display: flex;
  width: 100%;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  gap: 2px; /* segmentler arası mini boşluk */
}

.step-compact__segment {
  flex: 1;
  border-radius: 999px;
  transition: background 0.2s ease-out;
}

/* Bitti -> Yeşil */
.segment--done {
  background: #16a34a; /* green-600 */
}

/* Şu anki aşama -> Mavi */
.segment--active {
  background: #2563eb; /* blue-600 */
}

/* Gelecek aşama -> Gri */
.segment--pending {
  background: #d1d5db; /* gray-300 */
}

/* 🔹 Ekran daraldığında: sadece compact görünüm kalsın */
@media (max-width: 640px) {
  .step-compact {
    display: block;
  }

  .step-list {
    display: none;
  }
}
</style>