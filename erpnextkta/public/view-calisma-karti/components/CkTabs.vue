<script setup lang="ts">
export type TabKey = "info" | "alt_operasyon" | "hurda" | "durus" | "kalite" | "bakim";

const props = defineProps<{
  modelValue: TabKey;
  onChange: (t: TabKey) => void;
}>();

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "info", label: __("Bilgiler") },
  { key: "alt_operasyon", label: __("Alt İşlem") },
  { key: "hurda", label: __("Hurda") },
  { key: "durus", label: __("Duruş Geçmişi") },
  { key: "kalite", label: __("Kalite") },
  { key: "bakim", label: __("Bakım") },
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
