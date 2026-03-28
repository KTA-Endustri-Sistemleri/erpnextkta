<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  showStart: boolean;
  showResume: boolean;
  showStop: boolean;
  showFinish: boolean;
  qcApproved: boolean;
  onBaslatDevam: () => void;
  onDurus: () => void;
  onBitir: () => void;
}>();

const isVisible = computed(() => {
  return props.showStart || props.showResume || props.showStop || props.showFinish;
});
</script>

<template>
  <div v-if="isVisible" class="ck-actionbar">
    <button
      v-if="props.showStart"
      class="ck-btn ck-btn--success ck-btn--wide"
      @click="props.onBaslatDevam"
    >
      Başlat
    </button>

    <button
      v-if="props.showResume"
      class="ck-btn ck-btn--success ck-btn--wide"
      @click="props.onBaslatDevam"
    >
      Devam Et
    </button>

    <button
      v-if="props.showStop"
      class="ck-btn ck-btn--warning ck-btn--wide"
      @click="props.onDurus"
    >
      Duruş
    </button>

    <button
      v-if="props.showFinish"
      :disabled="!props.qcApproved"
      class="ck-btn ck-btn--danger ck-btn--wide"
      @click="props.onBitir"
    >
      Bitir
    </button>
  </div>
</template>