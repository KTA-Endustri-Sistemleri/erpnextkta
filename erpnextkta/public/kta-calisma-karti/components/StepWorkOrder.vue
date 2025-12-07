<script setup>
import { ref, onMounted, watch } from 'vue';

const props = defineProps({
  barcode: {
    type: String,
    default: ''
  },
  workOrder: {
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

// WO reset olursa tekrar fokus
watch(
  () => props.workOrder,
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
      <h2 class="step-wo__title">İş Emri Barkodu</h2>
      <p class="step-wo__subtitle">
        Barkod okuyucu ile <strong>İş Emri barkodunu</strong> okut.
        Okuyucu genelde Enter ile bittiği için ek işlem yapman gerekmez.
      </p>
    </div>

    <!-- Tek alan: Barkod giriş alanı -->
    <div class="step-wo__input-wrapper">
      <input
        ref="inputRef"
        type="text"
        class="step-wo__input"
        :readonly="loading"
        :value="barcode"
        placeholder="Barkodu okutun..."
        @input="onInput"
        @keydown="onKeydown"
      />
      <div class="step-wo__input-icon">
        <div class="step-wo__scan-line" />
      </div>
    </div>

    <!-- Loading sırasında mini açıklama -->
    <div v-if="loading" class="step-wo__loading-text">
      İş Emri doğrulanıyor...
    </div>
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
  color: #111827;
}

.step-wo__subtitle {
  margin-top: 0.25rem;
  font-size: 0.85rem;
  color: #4b5563;
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
  border: 1px solid #d1d5db;
  background: #ffffff;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.step-wo__input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.18);
}

.step-wo__input[readonly] {
  background: #f3f4f6;
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
  color: #6b7280;
}
</style>