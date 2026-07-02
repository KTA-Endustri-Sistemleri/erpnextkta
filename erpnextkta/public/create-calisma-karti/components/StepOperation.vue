<script setup>
const __ = (...args) => window.__(...args);

const props = defineProps({
  operations: {
    type: Array,
    default: () => []
  },
  // v-model:selectedOperation -> string (calisma_karti_op)
  selectedOperation: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['update:selectedOperation']);

function selectOperation(name) {
  emit('update:selectedOperation', name || null);
}

function isSelected(name) {
  return props.selectedOperation === name;
}
</script>

<template>
  <section class="step-operation">
    <div class="step-operation__header">
      <div>
        <h2 class="step-operation__title">{{ __('Operasyon') }}</h2>
        <p class="step-operation__subtitle">
          {{ __('Çalışma Kartı Operasyonları listesinden bir operasyon seç.') }}
        </p>
      </div>

      <div
        v-if="operations.length"
        class="step-operation__count"
      >
        {{ operations.length }} {{ __('operasyon bulundu') }}
      </div>
    </div>

    <!-- Hiç operasyon yoksa -->
    <div
      v-if="!operations.length"
      class="step-operation__empty"
    >
      {{ __('Bu İş Kartı için tanımlı herhangi bir operasyon bulunamadı.') }}
    </div>

    <!-- Kart grid -->
    <div
      v-else
      class="step-operation__grid"
    >
      <button
        v-for="(op, index) in operations"
        :key="op.name || index"
        type="button"
        class="step-operation__card"
        :class="{ 'step-operation__card--selected': isSelected(op.name) }"
        @click="selectOperation(op.name)"
      >
        <div class="step-operation__card-header">
          <div class="step-operation__card-name">
            {{ __(op.calisma_karti_op) }}
          </div>
          <div
            class="step-operation__badge"
            :class="isSelected(op.name)
              ? 'step-operation__badge--selected'
              : 'step-operation__badge--default'"
          >
            {{ isSelected(op.name) ? __('Seçili') : __('Seç') }}
          </div>
        </div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.step-operation {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.step-operation__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.step-operation__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--ck-text);
}

.step-operation__subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: var(--ck-text-muted);
}

.step-operation__count {
  font-size: 0.75rem;
  color: var(--ck-text-muted);
  white-space: nowrap;
}

.step-operation__empty {
  padding: 0.6rem 0.75rem;
  font-size: 0.85rem;
  color: var(--ck-text-muted);
  border: 1px dashed var(--ck-border);
  border-radius: 0.5rem;
  background: var(--ck-ghost-bg);
}

/* Kart grid */
.step-operation__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
}

@media (min-width: 640px) {
  .step-operation__grid {
    grid-template-columns: 1fr 1fr;
  }
}

.step-operation__card {
  border: 1px solid var(--ck-border);
  border-radius: 0.5rem;
  padding: 0.6rem 0.75rem;
  background: var(--ck-card-bg);
  text-align: left;
  font-size: 0.85rem;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.step-operation__card:hover {
  border-color: var(--ck-accent);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  background: var(--ck-ghost-bg);
}

.step-operation__card--selected {
  border-color: var(--ck-accent);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.2);
  background: var(--ck-ghost-bg);
}

.step-operation__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.step-operation__card-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ck-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-operation__badge {
  font-size: 0.75rem;
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  border: 1px solid var(--ck-border);
  background: var(--ck-bg);
  color: var(--ck-text-muted);
}

.step-operation__card--selected .step-operation__badge {
  background: var(--ck-accent);
  border-color: var(--ck-accent);
  color: #ffffff;
}

.step-operation__badge--selected {
  border-color: var(--ck-accent);
  background: var(--ck-accent);
  color: #ffffff;
}

/* İleride body/row/label kullanırsan hazır dursun */
.step-operation__card-body {
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: var(--ck-text-muted);
}

.step-operation__row {
  margin-top: 0.15rem;
}

.step-operation__label {
  font-weight: 500;
  color: var(--ck-text);
}
</style>
