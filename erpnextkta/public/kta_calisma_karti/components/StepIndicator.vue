<!-- StepIndicator.vue -->
<script setup>
const props = defineProps({
  currentStep: {
    type: Number,
    required: true,
  },
  steps: {
    type: Array,
    required: true,
    // e.g. [{ id: 1, label: 'İş Emri' }, ...]
  },
});
</script>

<template>
  <nav class="step-indicator">
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

/* Mobile tweak */
@media (max-width: 640px) {
  .step-label__desc {
    display: none;
  }
  .step-label__title {
    font-size: 0.75rem;
  }
}
</style>