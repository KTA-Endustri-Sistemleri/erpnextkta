<script setup>
const props = defineProps({
  barcode: {
    type: String,
    default: ''
  },
  jobCard: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:barcode', 'submit']);

function onInput(e) {
  emit('update:barcode', e.target.value);
}

function onKeyup(e) {
  if (e.key === 'Enter') {
    emit('submit');
  }
}
</script>

<template>
  <section class="space-y-3">
    <header class="flex items-center justify-between gap-2">
      <div>
        <h2 class="font-semibold text-lg">1️⃣ İş Kartı</h2>
        <p class="text-xs text-gray-500">
          Job Card barkodunu okut veya Job Card numarasını gir.
        </p>
      </div>

      <div
        v-if="jobCard && jobCard.name"
        class="px-2 py-1 rounded text-xs bg-slate-50 border border-slate-200 text-slate-700"
      >
        <span class="font-semibold">JC:</span> {{ jobCard.name }}
        <span v-if="jobCard.work_order"> · {{ jobCard.work_order }}</span>
      </div>
    </header>

    <div class="space-y-1">
      <label class="block text-xs font-medium text-gray-700">
        İş Kartı Barkodu / Numarası
      </label>
      <input
        type="text"
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm
               focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
               disabled:bg-gray-100 disabled:text-gray-400"
        :value="barcode"
        :disabled="loading"
        autocomplete="off"
        placeholder="Ör: JC-00045"
        @input="onInput"
        @keyup="onKeyup"
      />
      <p class="text-[11px] text-gray-400">
        Barkod okuyucu ile okuttuğunda Enter otomatik gelir; manuel girişte Enter ile ilerleyebilirsin.
      </p>
    </div>
  </section>
</template>