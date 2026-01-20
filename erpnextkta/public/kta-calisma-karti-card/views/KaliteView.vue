<script setup lang="ts">
const props = defineProps<{
  qcLabel: string;
  qcOptions: string[];
  qcFormValue: string;
  canEditQC: boolean;
  qcSaving: boolean;
  onSetQC: (next: string) => void;
}>();
</script>

<template>
  <div class="ck-card">
    <div class="ck-row" style="justify-content:space-between; align-items:center;">
      <span>Kalite Kontrol</span>
      <b>{{ props.qcLabel }}</b>
    </div>

    <div v-if="!props.canEditQC" class="ck-muted" style="margin-top:10px;">
      Bu sekmeyi görüntüleyebilirsiniz ancak güncelleme yetkiniz yok.
    </div>

    <div v-else style="margin-top:10px;">
      <div class="ck-qc-toggle" role="group" aria-label="Kalite durumu">
        <button
          v-for="o in props.qcOptions"
          :key="o"
          type="button"
          class="ck-qc-toggle__btn"
          :class="[
            props.qcFormValue === o && 'is-active',
            o === 'Onay Bekliyor' && 'is-pending',
            o === 'Onaylandı' && 'is-ok',
            o === 'Reddedildi' && 'is-reject',
          ]"
          :disabled="props.qcSaving"
          @click="props.onSetQC(o)"
        >
          {{ o }}
        </button>
      </div>
    </div>
  </div>
</template>