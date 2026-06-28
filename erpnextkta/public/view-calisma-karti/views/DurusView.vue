<script setup lang="ts">
import { formatDuration } from "../utils/format";
const props = defineProps<{ doc: any }>();
</script>

<template>
  <div class="ck-card">
    <div v-if="(props.doc.duruslar||[]).length===0" class="ck-empty-state">{{ __("Duruş kaydı yok.") }}</div>

    <div v-else class="ck-mini-list">
      <div v-for="(d, i) in props.doc.duruslar" :key="i" class="ck-mini-item">
        <div class="ck-mini-content">
          <b class="ck-mini-title">{{ d.durus_nedeni || ('Duruş #' + (i+1)) }}</b>
          <div class="ck-muted ck-mini-sub">{{ d.durus_baslangic || "-" }} → {{ d.durus_bitis || __("Devam ediyor") }}</div>
          <div class="ck-muted ck-mini-sub">{{ __("Süre:") }} <strong style="color:var(--ck-text);">{{ formatDuration(d.durus_suresi) }}</strong></div>
          <div v-if="d.aciklama" class="ck-muted ck-mini-sub">{{ d.aciklama }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ck-empty-state {
  padding: 10px;
  text-align: center;
  color: var(--ck-text-muted);
  font-size: 13px;
  opacity: 0.7;
}
.ck-mini-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 10px 10px;
}
.ck-mini-item {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  box-shadow: var(--ck-glass-highlight), 0 2px 8px rgba(0,0,0,0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ck-mini-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--ck-glass-highlight), 0 6px 16px rgba(0,0,0,0.06);
}
.ck-mini-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ck-mini-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--ck-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ck-mini-sub {
  font-size: 12px;
  opacity: 0.8;
}
</style>