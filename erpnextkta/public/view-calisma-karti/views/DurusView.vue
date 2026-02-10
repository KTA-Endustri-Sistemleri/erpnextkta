<script setup lang="ts">
const props = defineProps<{ doc: any }>();
</script>

<template>
  <div class="ck-card">
    <div v-if="(props.doc.duruslar||[]).length===0" class="ck-muted">Duruş kaydı yok.</div>

    <div v-else class="ck-mini-list">
      <div v-for="(d, i) in props.doc.duruslar" :key="i" class="ck-mini-item">
        <b>{{ d.durus_nedeni || ('Duruş #' + (i+1)) }}</b>
        <div class="ck-muted">{{ d.durus_baslangic || "-" }} → {{ d.durus_bitis || "Devam ediyor" }}</div>
        <div class="ck-muted">Süre: {{ d.durus_suresi ?? "-" }} dk</div>
        <div v-if="d.aciklama" class="ck-muted">{{ d.aciklama }}</div>
      </div>
    </div>
  </div>
</template>