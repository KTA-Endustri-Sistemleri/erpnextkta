<script setup>
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

function onInput(event) {
  emit('update:barcode', event.target.value);
}

function onKeyupEnter() {
  // USB barkod okuyucu Enter gönderince
  emit('submit');
}
</script>

<template>
  <section class="space-y-3">
    <h2 class="font-semibold text-lg">1️⃣ İş Emri (Work Order)</h2>
    <p class="text-sm text-gray-600">
      Barkod okuyucu ile <strong>İş Emri</strong> etiketini okut. Okutma sonrası
      genelde otomatik <code>Enter</code> geleceği için Work Order bilgileri
      otomatik çekilecektir.
    </p>

    <input
      type="text"
      :value="barcode"
      placeholder="Work Order barkod / numara"
      class="w-full border rounded px-3 py-2"
      @input="onInput"
      @keyup.enter="onKeyupEnter"
    />

    <div
      v-if="workOrder"
      class="mt-3 text-sm text-gray-700 space-y-1"
    >
      <div><strong>WO:</strong> {{ workOrder.name }}</div>
      <div v-if="workOrder.production_item">
        <strong>Ürün:</strong> {{ workOrder.production_item }}
      </div>
      <div v-if="workOrder.qty != null">
        <strong>Miktar:</strong> {{ workOrder.qty }}</div>
    </div>

    <div v-if="loading" class="text-xs text-gray-500">
      Work Order bilgileri yükleniyor...
    </div>
  </section>
</template>