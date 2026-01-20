<script setup lang="ts">
const props = defineProps<{
  durumLabel: string;
  statusClass: string;
  qcLabel: string;
  qcClass: string;
}>();
</script>

<template>
  <div class="ck-chips">
    <span :class="['ck-status-badge', props.statusClass]">{{ props.durumLabel }}</span>
    <span :class="['ck-chip', props.qcClass]">QC: {{ props.qcLabel }}</span>
  </div>
</template>