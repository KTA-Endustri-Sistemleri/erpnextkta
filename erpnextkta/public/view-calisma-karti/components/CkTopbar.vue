<script setup lang="ts">
const props = defineProps<{
  onBack: () => void;
  onOpenForm?: () => void;
}>();
</script>

<template>
  <div class="ck-topbar">
    <button class="ck-btn ck-btn--ghost" @click="props.onBack">← {{ __("Geri") }}</button>

    <div class="ck-topbar-title">
      <div class="ck-title">{{ __("Çalışma Kartı") }}</div>
    </div>

    <!-- Optional -->
    <!-- <button class="ck-btn ck-btn--ghost" @click="props.onOpenForm && props.onOpenForm()">Form</button> -->
  </div>
</template>