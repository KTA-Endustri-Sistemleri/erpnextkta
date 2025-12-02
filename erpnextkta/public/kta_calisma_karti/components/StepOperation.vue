<script setup>
const props = defineProps({
  operations: {
    type: Array,
    default: () => []
  },
  // v-model:selectedOperation -> "selectedOperation"
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
        v-for="op in operations"
        :key="op.name"
        :value="op.name"
      >
        {{ op.operation_name || op.name }}
      </option>
    </select>
  </section>
</template>