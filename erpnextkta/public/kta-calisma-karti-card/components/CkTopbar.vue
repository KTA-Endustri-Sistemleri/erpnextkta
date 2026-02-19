<script setup lang="ts">
const props = defineProps<{
  onBack: () => void;
  onOpenForm?: () => void;
}>();
</script>

<template>
  <div class="ck-topbar">
    <button class="ck-btn ck-btn--ghost" @click="props.onBack">← Geri</button>

    <div class="ck-topbar-title">
      <div class="ck-title">Çalışma Kartı</div>
    </div>

    <!-- Optional -->
    <!-- <button class="ck-btn ck-btn--ghost" @click="props.onOpenForm && props.onOpenForm()">Form</button> -->
  </div>
</template>