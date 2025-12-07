<script setup>
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
        <h2 class="step-operation__title">Operasyon</h2>
        <p class="step-operation__subtitle">
          <strong>KTA Çalışma Kartı Operasyonları</strong> listesinden bir operasyon seç.
          Seçilen değer ilgili <code>operasyon</code> alanına yazılacak.
        </p>
      </div>

      <div
        v-if="operations.length"
        class="step-operation__count"
      >
        {{ operations.length }} operasyon bulundu
      </div>
    </div>

    <!-- Hiç operasyon yoksa -->
    <div
      v-if="!operations.length"
      class="step-operation__empty"
    >
      Bu İş Kartı için tanımlı herhangi bir operasyon bulunamadı.
    </div>

    <!-- Kart grid -->
    <div
      v-else
      class="step-operation__grid"
    >
      <button
        v-for="(op, index) in operations"
        :key="index"
        type="button"
        class="step-operation__card"
        :class="{ 'step-operation__card--selected': isSelected(op.calisma_karti_op) }"
        @click="selectOperation(op.calisma_karti_op)"
      >
        <div class="step-operation__card-header">
          <div class="step-operation__card-name">
            {{ op.calisma_karti_op }}
          </div>
          <div
            class="step-operation__badge"
            :class="isSelected(op.calisma_karti_op)
              ? 'step-operation__badge--selected'
              : 'step-operation__badge--default'"
          >
            {{ isSelected(op.calisma_karti_op) ? 'Seçili' : 'Seç' }}
          </div>
        </div>

        <!-- İleride detay eklemek istersen buraya extra satırlar koyabilirsin -->
        <!--
        <div class="step-operation__card-body">
          <div v-if="op.aciklama" class="step-operation__row">
            <span class="step-operation__label">Açıklama:</span>
            <span>{{ op.aciklama }}</span>
          </div>
        </div>
        -->
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
  color: #111827;
}

.step-operation__subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: #4b5563;
}

.step-operation__count {
  font-size: 0.75rem;
  color: #6b7280;
  white-space: nowrap;
}

.step-operation__empty {
  padding: 0.6rem 0.75rem;
  font-size: 0.85rem;
  color: #4b5563;
  border: 1px dashed #d1d5db;
  border-radius: 0.5rem;
  background: #f9fafb;
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
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 0.6rem 0.75rem;
  background: #ffffff;
  text-align: left;
  font-size: 0.85rem;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.step-operation__card:hover {
  border-color: #bfdbfe;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.15);
}

.step-operation__card--selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.2);
  background: #eff6ff;
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
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-operation__badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  border: 1px solid transparent;
}

.step-operation__badge--default {
  border-color: #d1d5db;
  background: #f9fafb;
  color: #4b5563;
}

.step-operation__badge--selected {
  border-color: #3b82f6;
  background: #dbeafe;
  color: #1d4ed8;
}

/* İleride body/row/label kullanırsan hazır dursun */
.step-operation__card-body {
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: #4b5563;
}

.step-operation__row {
  margin-top: 0.15rem;
}

.step-operation__label {
  font-weight: 500;
  color: #374151;
}
</style>