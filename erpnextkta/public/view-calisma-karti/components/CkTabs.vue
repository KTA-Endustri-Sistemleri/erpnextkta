<script setup lang="ts">
export type TabKey = "info" | "alt_operasyon" | "hurda" | "durus" | "kalite" | "bakim";

const props = defineProps<{
  modelValue: TabKey;
  onChange: (t: TabKey) => void;
}>();

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "info", label: "Bilgiler" },
  { key: "alt_operasyon", label: "Alt İşlem" },
  { key: "hurda", label: "Hurda" },
  { key: "durus", label: "Duruş" },
  { key: "kalite", label: "Kalite" },
  { key: "bakim", label: "Bakım" },
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