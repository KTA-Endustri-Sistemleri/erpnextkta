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
  <!-- QC header -->
  <div class="ck-row" style="justify-content:space-between; align-items:center;">
    <span>Kalite Kontrol</span>
    <b>{{ props.qcLabel }}</b>
  </div>

  <div v-if="props.canEditQC" style="margin-top:10px; position: relative;">
    <div class="ck-qc-toggle" :class="{ 'is-loading': props.qcSaving }" role="group" aria-label="Kalite durumu">
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

    <!-- Loading Overlay -->
    <Transition name="ck-fade">
      <div v-if="props.qcSaving" class="ck-qc-loader">
        <div class="ck-spinner-mini"></div>
        <span>İşleniyor...</span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.ck-qc-loader {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--ck-info);
  border-radius: 12px;
  backdrop-filter: blur(2px);
  z-index: 10;
}

[data-theme="dark"] .ck-qc-loader {
  background: rgba(0, 0, 0, 0.5);
}

.ck-spinner-mini {
  width: 16px;
  height: 16px;
  border: 2px solid var(--ck-info-bg);
  border-top-color: var(--ck-info);
  border-radius: 50%;
  animation: ck-spin 0.8s linear infinite;
}

@keyframes ck-spin {
  to { transform: rotate(360deg); }
}

.is-loading {
  filter: grayscale(0.5) blur(1px);
  pointer-events: none;
}

.ck-fade-enter-active,
.ck-fade-leave-active {
  transition: opacity 0.2s ease;
}

.ck-fade-enter-from,
.ck-fade-leave-to {
  opacity: 0;
}
</style>