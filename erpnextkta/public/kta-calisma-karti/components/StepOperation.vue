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

function onChange(event) {
  emit('update:selectedOperation', event.target.value || null);
}
</script>

<template>
  <section class="space-y-3">
    <h2 class="font-semibold text-lg">3️⃣ Operasyon</h2>
    <p class="text-sm text-gray-600">
      <strong>KTA Calisma Karti Operasyonlari</strong> doctype'ından gelen kayıtlardan
      bir operasyon seç. Bu değer, <code>operasyon</code> alanına yazılacak.
    </p>

    <select
      class="w-full border rounded px-3 py-2"
      :value="selectedOperation"
      @change="onChange"
    >
      <option disabled value="">Operasyon seçin...</option>
      <option
        v-for="(op, index) in operations"
        :key="index"
        :value="op.calisma_karti_op"
      >
        {{ op.calisma_karti_op }}
      </option>
    </select>
  </section>
</template>