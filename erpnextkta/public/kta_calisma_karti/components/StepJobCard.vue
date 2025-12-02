<script setup>
const props = defineProps({
  jobCards: {
    type: Array,
    default: () => []
  },
  // v-model:selectedJobCard -> "selectedJobCard" string
  selectedJobCard: {
    type: String,
    default: null
  },
  // ek detay göstermek için objeyi de alıyoruz
  selectedJobCardObj: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['update:selectedJobCard']);

function onChange(event) {
  emit('update:selectedJobCard', event.target.value || null);
}
</script>

<template>
  <section class="space-y-3">
    <h2 class="font-semibold text-lg">2️⃣ İş Kartı (Job Card)</h2>
    <p class="text-sm text-gray-600">
      Seçilen İş Emri'ne bağlı <strong>Job Card</strong> listesinden bir tanesini seç.
    </p>

    <select
      class="w-full border rounded px-3 py-2"
      :value="selectedJobCard"
      @change="onChange"
    >
      <option disabled value="">Job Card seçin...</option>
      <option
        v-for="jc in jobCards"
        :key="jc.name"
        :value="jc.name"
      >
        {{ jc.name }} - {{ jc.operation || 'Operasyon yok' }}
      </option>
    </select>

    <div
      v-if="selectedJobCardObj"
      class="text-sm text-gray-700 space-y-1 mt-2"
    >
      <div><strong>Job Card:</strong> {{ selectedJobCardObj.name }}</div>
      <div v-if="selectedJobCardObj.operation">
        <strong>Operasyon (Job Card):</strong> {{ selectedJobCardObj.operation }}
      </div>
      <div v-if="selectedJobCardObj.workstation">
        <strong>Varsayılan İş İstasyonu:</strong> {{ selectedJobCardObj.workstation }}
      </div>
    </div>
  </section>
</template>