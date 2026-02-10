<script setup lang="ts">
export type TabKey = "info" | "hurda" | "durus" | "kalite";

const props = defineProps<{
  modelValue: TabKey;
  onChange: (t: TabKey) => void;
}>();

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "info", label: "Bilgiler" },
  { key: "hurda", label: "Hurda" },
  { key: "durus", label: "Duruş" },
  { key: "kalite", label: "Kalite" },
];
</script>

<template>
  <div class="ck-tabs">
    <button
      v-for="t in tabs"
      :key="t.key"
      :class="['ck-tab', props.modelValue === t.key && 'is-active']"
      @click="props.onChange(t.key)"
    >
      {{ t.label }}
    </button>
  </div>
</template>