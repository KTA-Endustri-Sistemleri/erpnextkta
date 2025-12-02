<script setup>
const props = defineProps({
  workstation: {
    type: String,
    default: ''
  },
  jobCard: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['update:workstation']);

function onInput(event) {
  emit('update:workstation', event.target.value);
}
</script>

<template>
  <section class="space-y-3">
    <h2 class="font-semibold text-lg">4️⃣ İş İstasyonu (Workstation)</h2>
    <p class="text-sm text-gray-600">
      Seçilen Job Card'daki varsayılan iş istasyonu otomatik gelir.
      Bu değer, <code>is_istasyonu</code> alanına yazılacak.
    </p>

    <input
      type="text"
      :value="workstation"
      class="w-full border rounded px-3 py-2"
      placeholder="İş İstasyonu"
      @input="onInput"
    />

    <div v-if="jobCard && jobCard.workstation" class="text-xs text-gray-500">
      Job Card'dan gelen: {{ jobCard.workstation }}
    </div>
  </section>
</template>