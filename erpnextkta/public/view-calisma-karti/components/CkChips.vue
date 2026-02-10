<script setup lang="ts">
const props = defineProps<{
  durumLabel: string;
  statusClass: string;
  qcLabel: string;
  qcClass: string;
}>();
</script>

<template>
  <div class="row no-gutters ck-chips">
    <span class="col-6 p-2" :class="['ck-status-badge', props.statusClass]">{{ props.durumLabel }}</span>
    <span class="col-6 p-2" :class="['ck-chip', props.qcClass]">QC: {{ props.qcLabel }}</span>
  </div>
</template>